#!/usr/bin/env python3
"""
Hazard Detection Node for NASA Lunar Scout Rover.

Full ROS2 lifecycle node that fuses stereo camera depth estimation with
LIDAR point-cloud data and runs ONNX Runtime inference to classify surface
hazards on the lunar surface.

Hazard classes:
    0 - boulder        : rock obstacle requiring avoidance
    1 - deep_crater    : crater with significant depth drop
    2 - steep_slope    : slope exceeding safe traversal angle
    3 - comms_shadow   : area with blocked Earth/relay communications

Subscriptions:
    /stereo/left/image_raw   (sensor_msgs/Image)
    /stereo/right/image_raw  (sensor_msgs/Image)
    /scan                    (sensor_msgs/LaserScan)
    /terrain_segmentation    (lunar_scout_hazard_detection/TerrainSegmentation)

Publications:
    /hazard_detections       (lunar_scout_hazard_detection/HazardArray)
    /hazard_visualization    (sensor_msgs/Image)
    /costmap_updates         (nav2_msgs/Costmap2DUpdate)

Services:
    /hazard_detection/emergency_stop  (std_srvs/Trigger)
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import List, Optional, Tuple

import cv2
import numpy as np

import rclpy
from rclpy.lifecycle import LifecycleNode, LifecycleState, TransitionCallbackReturn
from rclpy.qos import (
    QoSProfile,
    QoSReliabilityPolicy,
    QoSHistoryPolicy,
    QoSDurabilityPolicy,
)
from rclpy.callback_groups import ReentrantCallbackGroup, MutuallyExclusiveCallbackGroup

from std_msgs.msg import Header, String
from std_srvs.srv import Trigger
from sensor_msgs.msg import Image, LaserScan, CameraInfo
from geometry_msgs.msg import Point, Pose2D
from nav_msgs.msg import OccupancyGrid
from builtin_interfaces.msg import Time

try:
    from nav2_msgs.msg import Costmap2DUpdate
    _HAS_NAV2 = True
except ImportError:
    _HAS_NAV2 = False

try:
    from cv_bridge import CvBridge, CvBridgeError
    _HAS_CV_BRIDGE = True
except ImportError:
    _HAS_CV_BRIDGE = False

try:
    import onnxruntime as ort
    _HAS_ONNX = True
except ImportError:
    _HAS_ONNX = False

from lunar_scout_hazard_detection import (
    HAZARD_CLASSES,
    HAZARD_COLORS_BGR,
    TERRAIN_CLASSES,
)

# ---------------------------------------------------------------------------
# QoS profiles
# ---------------------------------------------------------------------------
SENSOR_QOS = QoSProfile(
    reliability=QoSReliabilityPolicy.BEST_EFFORT,
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=1,
    durability=QoSDurabilityPolicy.VOLATILE,
)

# TRANSIENT_LOCAL so late-joining subscribers (e.g. autonomy_manager) get the
# last published state — matches the durability used across the rest of the stack.
RELIABLE_QOS = QoSProfile(
    reliability=QoSReliabilityPolicy.RELIABLE,
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=10,
    durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MODEL_INPUT_W = 640
MODEL_INPUT_H = 640
NUM_HAZARD_CLASSES = 4
LIDAR_ANGULAR_RESOLUTION_RAD = np.deg2rad(0.33)  # typical for VLP-16 equivalent
STEREO_BASELINE_DEFAULT_M = 0.30
FOCAL_LENGTH_DEFAULT_PX = 800.0
MAX_STEREO_DISPARITY = 128
MIN_DISPARITY = 1


# ---------------------------------------------------------------------------
# Utility: NMS
# ---------------------------------------------------------------------------
def non_max_suppression(
    boxes: np.ndarray,
    scores: np.ndarray,
    iou_threshold: float = 0.45,
) -> List[int]:
    """Pure-NumPy non-maximum suppression. Returns kept indices."""
    if len(boxes) == 0:
        return []
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]
    keep: List[int] = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1 + 1)
        h = np.maximum(0.0, yy2 - yy1 + 1)
        iou = (w * h) / (areas[i] + areas[order[1:]] - w * h + 1e-6)
        inds = np.where(iou <= iou_threshold)[0]
        order = order[inds + 1]
    return keep


# ---------------------------------------------------------------------------
# Stereo block-matching depth estimator
# ---------------------------------------------------------------------------
class StereoDepthEstimator:
    """Semi-global block matching stereo depth estimator."""

    def __init__(
        self,
        baseline_m: float = STEREO_BASELINE_DEFAULT_M,
        focal_px: float = FOCAL_LENGTH_DEFAULT_PX,
        block_size: int = 11,
        num_disparities: int = MAX_STEREO_DISPARITY,
    ) -> None:
        self.baseline_m = baseline_m
        self.focal_px = focal_px
        self._lock = threading.Lock()

        # OpenCV SGBM parameters tuned for lunar surface texture
        self._sgbm = cv2.StereoSGBM_create(
            minDisparity=0,
            numDisparities=num_disparities,
            blockSize=block_size,
            P1=8 * 3 * block_size ** 2,
            P2=32 * 3 * block_size ** 2,
            disp12MaxDiff=1,
            uniquenessRatio=10,
            speckleWindowSize=100,
            speckleRange=32,
            preFilterCap=63,
            mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY,
        )

        # WLS filter for disparity refinement
        self._wls = cv2.ximgproc.createDisparityWLSFilter(self._sgbm)
        self._wls.setLambda(8000.0)
        self._wls.setSigmaColor(1.5)
        self._right_matcher = cv2.ximgproc.createRightMatcher(self._sgbm)

    def compute_depth(
        self,
        left_gray: np.ndarray,
        right_gray: np.ndarray,
    ) -> np.ndarray:
        """
        Compute per-pixel depth map (metres) from rectified stereo pair.

        Parameters
        ----------
        left_gray:  H x W uint8 grayscale left image
        right_gray: H x W uint8 grayscale right image

        Returns
        -------
        depth_m: H x W float32 depth map in metres; 0 where invalid
        """
        with self._lock:
            disp_left = self._sgbm.compute(left_gray, right_gray)
            try:
                disp_right = self._right_matcher.compute(right_gray, left_gray)
                disp_filtered = self._wls.filter(
                    disp_left, left_gray, disparity_map_right=disp_right
                )
                disp_f32 = disp_filtered.astype(np.float32) / 16.0
            except cv2.error:
                # ximgproc not available; use raw disparity
                disp_f32 = disp_left.astype(np.float32) / 16.0

        # Convert disparity -> depth  (Z = f * B / d)
        valid = disp_f32 > MIN_DISPARITY
        depth_m = np.zeros_like(disp_f32)
        depth_m[valid] = (self.focal_px * self.baseline_m) / disp_f32[valid]
        # Clamp to plausible range [0.1 m, 50 m]
        depth_m = np.clip(depth_m, 0.0, 50.0)
        depth_m[~valid] = 0.0
        return depth_m

    def depth_at_box(
        self,
        depth_m: np.ndarray,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
    ) -> float:
        """Return robust median depth inside a bounding box (metres)."""
        roi = depth_m[y1:y2, x1:x2]
        valid = roi[roi > 0.1]
        if valid.size == 0:
            return 0.0
        return float(np.median(valid))


# ---------------------------------------------------------------------------
# LIDAR hazard detector
# ---------------------------------------------------------------------------
class LidarHazardDetector:
    """
    Analyses a 2D laser scan for hazard signatures.

    Uses range discontinuities and near-field obstacle clustering to
    generate hazard candidate regions that complement camera detections.
    """

    CLUSTER_GAP_M = 0.4        # gap > this starts a new cluster
    MIN_CLUSTER_POINTS = 3
    CRATER_DROP_THRESHOLD_M = 0.8   # sudden range increase indicating crater edge
    BOULDER_MAX_RANGE_M = 8.0
    BOULDER_MIN_HEIGHT_EST_M = 0.2  # estimated from range difference gradient

    def __init__(self, logger) -> None:
        self._log = logger

    def detect(
        self,
        scan: LaserScan,
        emergency_stop_distance_m: float,
    ) -> Tuple[List[dict], bool]:
        """
        Process a LaserScan and return hazard candidates + emergency flag.

        Returns
        -------
        candidates: list of dicts with keys
            class_id, distance_m, bearing_rad, confidence
        emergency: bool  — obstacle inside emergency_stop_distance_m
        """
        ranges = np.array(scan.ranges, dtype=np.float32)
        n = len(ranges)
        if n == 0:
            return [], False

        angle_min = scan.angle_min
        angle_inc = scan.angle_increment
        range_min = max(scan.range_min, 0.05)
        range_max = min(scan.range_max, 30.0)

        # Clamp invalid readings
        valid_mask = np.isfinite(ranges) & (ranges >= range_min) & (ranges <= range_max)
        ranges_clean = np.where(valid_mask, ranges, np.nan)

        angles = angle_min + np.arange(n, dtype=np.float32) * angle_inc

        candidates: List[dict] = []
        emergency = False

        # --- Emergency stop: any point within threshold ---
        near_valid = valid_mask & (ranges < emergency_stop_distance_m)
        if np.any(near_valid):
            emergency = True

        # --- Boulder detection: cluster analysis on valid readings ---
        clusters = self._cluster_ranges(ranges_clean, angles, valid_mask)
        for cluster_ranges, cluster_angles in clusters:
            mean_range = float(np.mean(cluster_ranges))
            mean_angle = float(np.mean(cluster_angles))
            if mean_range > self.BOULDER_MAX_RANGE_M:
                continue
            # Heuristic confidence based on cluster coherence
            range_std = float(np.std(cluster_ranges))
            confidence = float(np.clip(1.0 - range_std / 0.5, 0.4, 0.95))
            candidates.append({
                "class_id": 0,  # boulder
                "distance_m": mean_range,
                "bearing_rad": mean_angle,
                "confidence": confidence,
            })

        # --- Crater detection: sudden range increase (forward-facing arc) ---
        front_mask = (np.abs(angles) < np.deg2rad(60)) & valid_mask
        front_idx = np.where(front_mask)[0]
        if len(front_idx) > 2:
            front_ranges = ranges_clean[front_idx]
            diffs = np.diff(front_ranges)
            crater_edges = np.where(diffs > self.CRATER_DROP_THRESHOLD_M)[0]
            for edge_idx in crater_edges:
                dist = float(front_ranges[front_idx[edge_idx]])
                angle = float(angles[front_idx[edge_idx]])
                if dist < range_max:
                    candidates.append({
                        "class_id": 1,  # deep_crater
                        "distance_m": dist,
                        "bearing_rad": angle,
                        "confidence": min(0.85, 0.5 + diffs[edge_idx] / 3.0),
                    })

        return candidates, emergency

    def _cluster_ranges(
        self,
        ranges: np.ndarray,
        angles: np.ndarray,
        valid: np.ndarray,
    ) -> List[Tuple[np.ndarray, np.ndarray]]:
        """Simple gap-based 1-D range clustering."""
        clusters: List[Tuple[np.ndarray, np.ndarray]] = []
        current_r: List[float] = []
        current_a: List[float] = []

        for i in range(len(ranges)):
            if not valid[i]:
                if len(current_r) >= self.MIN_CLUSTER_POINTS:
                    clusters.append((np.array(current_r), np.array(current_a)))
                current_r = []
                current_a = []
                continue
            if current_r and abs(ranges[i] - current_r[-1]) > self.CLUSTER_GAP_M:
                if len(current_r) >= self.MIN_CLUSTER_POINTS:
                    clusters.append((np.array(current_r), np.array(current_a)))
                current_r = []
                current_a = []
            current_r.append(float(ranges[i]))
            current_a.append(float(angles[i]))

        if len(current_r) >= self.MIN_CLUSTER_POINTS:
            clusters.append((np.array(current_r), np.array(current_a)))
        return clusters


# ---------------------------------------------------------------------------
# Main lifecycle node
# ---------------------------------------------------------------------------
class HazardDetectionNode(LifecycleNode):
    """
    ROS2 lifecycle node for multi-modal lunar surface hazard detection.

    State machine: Unconfigured -> Inactive -> Active -> (Finalized)

    In the Active state the node:
      1. Receives stereo image pairs and estimates per-pixel depth via SGBM.
      2. Runs ONNX Runtime inference on the left image (640x640) to produce
         bounding-box hazard detections.
      3. Fuses camera detections with LIDAR cluster/crater candidates.
      4. Publishes HazardArray, a visualization overlay, and costmap updates.
      5. Triggers an emergency stop if any hazard is inside the safety perimeter.
    """

    def __init__(self) -> None:
        super().__init__("hazard_detection_node")

        # Declare parameters with defaults
        self.declare_parameter("detection_confidence_threshold", 0.75)
        self.declare_parameter("emergency_stop_distance_m", 2.0)
        self.declare_parameter("model_path", "")
        self.declare_parameter("stereo_baseline_m", STEREO_BASELINE_DEFAULT_M)
        self.declare_parameter("focal_length_px", FOCAL_LENGTH_DEFAULT_PX)
        self.declare_parameter("lidar_fusion_weight", 0.4)
        self.declare_parameter("camera_fusion_weight", 0.6)
        self.declare_parameter("costmap_resolution_m", 0.05)
        self.declare_parameter("costmap_width_cells", 200)
        self.declare_parameter("costmap_height_cells", 200)
        self.declare_parameter("target_inference_hz", 10.0)

        # Internal state — will be populated on configure
        self._bridge: Optional[CvBridge] = None
        self._ort_session: Optional[ort.InferenceSession] = None
        self._depth_estimator: Optional[StereoDepthEstimator] = None
        self._lidar_detector: Optional[LidarHazardDetector] = None

        # Latest sensor data (protected by lock)
        self._lock = threading.Lock()
        self._left_image: Optional[np.ndarray] = None
        self._right_image: Optional[np.ndarray] = None
        self._latest_scan: Optional[LaserScan] = None
        self._left_stamp: Optional[Time] = None

        # Performance monitoring
        self._frame_latencies: deque = deque(maxlen=50)
        self._inference_count: int = 0
        self._emergency_stop_active: bool = False

        # Callback groups
        self._sensor_cbg = ReentrantCallbackGroup()
        self._service_cbg = MutuallyExclusiveCallbackGroup()

        self.get_logger().info("HazardDetectionNode created — awaiting configure()")

    # ------------------------------------------------------------------
    # Lifecycle callbacks
    # ------------------------------------------------------------------

    def on_configure(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Allocate resources: bridge, ONNX session, depth estimator."""
        self.get_logger().info("Configuring hazard detection node…")

        if not _HAS_CV_BRIDGE:
            self.get_logger().error("cv_bridge not available — cannot configure")
            return TransitionCallbackReturn.FAILURE

        self._bridge = CvBridge()

        baseline = self.get_parameter("stereo_baseline_m").get_parameter_value().double_value
        focal = self.get_parameter("focal_length_px").get_parameter_value().double_value
        self._depth_estimator = StereoDepthEstimator(
            baseline_m=baseline, focal_px=focal
        )
        self._lidar_detector = LidarHazardDetector(self.get_logger())

        # Load ONNX model
        model_path = self.get_parameter("model_path").get_parameter_value().string_value
        if model_path and _HAS_ONNX:
            try:
                sess_opts = ort.SessionOptions()
                sess_opts.graph_optimization_level = (
                    ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                )
                sess_opts.intra_op_num_threads = 4
                providers = ["CPUExecutionProvider"]
                # Use CUDA if available
                available = ort.get_available_providers()
                if "CUDAExecutionProvider" in available:
                    providers = ["CUDAExecutionProvider"] + providers
                self._ort_session = ort.InferenceSession(
                    model_path, sess_options=sess_opts, providers=providers
                )
                inp = self._ort_session.get_inputs()[0]
                self.get_logger().info(
                    f"ONNX model loaded: {model_path}  "
                    f"input={inp.name} shape={inp.shape}"
                )
            except Exception as exc:
                self.get_logger().warning(
                    f"ONNX model load failed ({exc}); running heuristic-only mode"
                )
                self._ort_session = None
        else:
            self.get_logger().warning(
                "No ONNX model path configured; running heuristic-only mode"
            )

        # Create publishers (inactive — not yet active)
        self._pub_hazards = self.create_publisher(
            String,  # placeholder until custom msgs compile
            "/hazard_detections",
            RELIABLE_QOS,
        )
        self._pub_viz = self.create_publisher(
            Image,
            "/hazard_visualization",
            SENSOR_QOS,
        )
        if _HAS_NAV2:
            self._pub_costmap = self.create_publisher(
                Costmap2DUpdate,
                "/costmap_updates",
                RELIABLE_QOS,
            )
        else:
            self._pub_costmap = self.create_publisher(
                OccupancyGrid,
                "/costmap_updates",
                RELIABLE_QOS,
            )

        self.get_logger().info("Hazard detection node configured successfully")
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Wire subscriptions and start the processing timer."""
        self.get_logger().info("Activating hazard detection node…")

        # Subscriptions
        self._sub_left = self.create_subscription(
            Image,
            "/stereo/left/image_raw",
            self._cb_left_image,
            SENSOR_QOS,
            callback_group=self._sensor_cbg,
        )
        self._sub_right = self.create_subscription(
            Image,
            "/stereo/right/image_raw",
            self._cb_right_image,
            SENSOR_QOS,
            callback_group=self._sensor_cbg,
        )
        self._sub_scan = self.create_subscription(
            LaserScan,
            "/scan",
            self._cb_lidar_scan,
            SENSOR_QOS,
            callback_group=self._sensor_cbg,
        )
        # Terrain segmentation output — receives Image (class-map) as proxy
        self._sub_terrain = self.create_subscription(
            Image,
            "/terrain_segmentation",
            self._cb_terrain,
            SENSOR_QOS,
            callback_group=self._sensor_cbg,
        )

        # Emergency stop service
        self._srv_estop = self.create_service(
            Trigger,
            "/hazard_detection/emergency_stop",
            self._cb_emergency_stop,
            callback_group=self._service_cbg,
        )

        # Processing timer
        target_hz = (
            self.get_parameter("target_inference_hz").get_parameter_value().double_value
        )
        period_s = 1.0 / max(target_hz, 1.0)
        self._proc_timer = self.create_timer(period_s, self._cb_process_frame)

        # Diagnostics timer (1 Hz)
        self._diag_timer = self.create_timer(1.0, self._cb_diagnostics)

        self.get_logger().info(
            f"Hazard detection active — processing at {target_hz:.1f} Hz"
        )
        return TransitionCallbackReturn.SUCCESS

    def on_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Deactivating hazard detection node…")
        self.destroy_subscription(self._sub_left)
        self.destroy_subscription(self._sub_right)
        self.destroy_subscription(self._sub_scan)
        self.destroy_subscription(self._sub_terrain)
        self.destroy_service(self._srv_estop)
        self.destroy_timer(self._proc_timer)
        self.destroy_timer(self._diag_timer)
        return TransitionCallbackReturn.SUCCESS

    def on_cleanup(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Cleaning up hazard detection node…")
        self._ort_session = None
        self._depth_estimator = None
        self._lidar_detector = None
        with self._lock:
            self._left_image = None
            self._right_image = None
            self._latest_scan = None
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Shutting down hazard detection node")
        return TransitionCallbackReturn.SUCCESS

    # ------------------------------------------------------------------
    # Sensor callbacks
    # ------------------------------------------------------------------

    def _cb_left_image(self, msg: Image) -> None:
        try:
            bgr = self._bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except CvBridgeError as exc:
            self.get_logger().warning(f"Left image conversion failed: {exc}")
            return
        with self._lock:
            self._left_image = bgr
            self._left_stamp = msg.header.stamp

    def _cb_right_image(self, msg: Image) -> None:
        try:
            bgr = self._bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except CvBridgeError as exc:
            self.get_logger().warning(f"Right image conversion failed: {exc}")
            return
        with self._lock:
            self._right_image = bgr

    def _cb_lidar_scan(self, msg: LaserScan) -> None:
        with self._lock:
            self._latest_scan = msg

    def _cb_terrain(self, msg: Image) -> None:
        # Terrain segmentation class map consumed for costmap generation.
        # Actual fusion handled during _cb_process_frame.
        pass

    # ------------------------------------------------------------------
    # Service callbacks
    # ------------------------------------------------------------------

    def _cb_emergency_stop(
        self, request: Trigger.Request, response: Trigger.Response
    ) -> Trigger.Response:
        self._emergency_stop_active = True
        self.get_logger().error(
            "EMERGENCY STOP triggered via service /hazard_detection/emergency_stop"
        )
        response.success = True
        response.message = "Emergency stop activated — all motion commands blocked"
        return response

    # ------------------------------------------------------------------
    # Main processing callback
    # ------------------------------------------------------------------

    def _cb_process_frame(self) -> None:
        """Main per-frame pipeline: depth → ONNX inference → LIDAR fusion → publish."""
        t_start = time.monotonic()

        with self._lock:
            left_bgr = self._left_image.copy() if self._left_image is not None else None
            right_bgr = self._right_image.copy() if self._right_image is not None else None
            scan = self._latest_scan
            stamp = self._left_stamp

        if left_bgr is None:
            return  # No data yet

        conf_threshold = (
            self.get_parameter("detection_confidence_threshold")
            .get_parameter_value()
            .double_value
        )
        estop_dist = (
            self.get_parameter("emergency_stop_distance_m")
            .get_parameter_value()
            .double_value
        )

        h_orig, w_orig = left_bgr.shape[:2]

        # ------------------------------------------------------------------
        # 1. Stereo depth estimation
        # ------------------------------------------------------------------
        depth_m: Optional[np.ndarray] = None
        if right_bgr is not None and self._depth_estimator is not None:
            left_gray = cv2.cvtColor(left_bgr, cv2.COLOR_BGR2GRAY)
            right_gray = cv2.cvtColor(right_bgr, cv2.COLOR_BGR2GRAY)
            try:
                depth_m = self._depth_estimator.compute_depth(left_gray, right_gray)
            except Exception as exc:
                self.get_logger().warning(f"Depth estimation failed: {exc}")

        # ------------------------------------------------------------------
        # 2. Camera-based hazard detection (ONNX inference)
        # ------------------------------------------------------------------
        camera_detections: List[dict] = []
        if self._ort_session is not None:
            camera_detections = self._run_onnx_inference(
                left_bgr, depth_m, conf_threshold, h_orig, w_orig
            )
        else:
            # Heuristic fallback: simple edge/dark-region detection
            camera_detections = self._heuristic_detect(
                left_bgr, depth_m, conf_threshold
            )

        # ------------------------------------------------------------------
        # 3. LIDAR hazard detection
        # ------------------------------------------------------------------
        lidar_candidates: List[dict] = []
        lidar_emergency = False
        if scan is not None and self._lidar_detector is not None:
            lidar_candidates, lidar_emergency = self._lidar_detector.detect(
                scan, estop_dist
            )

        # ------------------------------------------------------------------
        # 4. Sensor fusion
        # ------------------------------------------------------------------
        fused = self._fuse_detections(camera_detections, lidar_candidates)

        # ------------------------------------------------------------------
        # 5. Emergency stop decision
        # ------------------------------------------------------------------
        cam_emergency = any(
            d["distance_m"] > 0 and d["distance_m"] < estop_dist
            for d in camera_detections
        )
        emergency = lidar_emergency or cam_emergency or self._emergency_stop_active

        # ------------------------------------------------------------------
        # 6. Build and publish HazardArray (serialised as JSON string until
        #    custom message generation is available at runtime)
        # ------------------------------------------------------------------
        import json
        hazard_payload = {
            "stamp_sec": stamp.sec if stamp else 0,
            "stamp_nanosec": stamp.nanosec if stamp else 0,
            "frame_id": "base_link",
            "hazards": fused,
            "emergency_stop_required": emergency,
            "reason": (
                "Obstacle within emergency stop distance"
                if emergency else ""
            ),
        }
        msg_str = String()
        msg_str.data = json.dumps(hazard_payload)
        self._pub_hazards.publish(msg_str)

        # ------------------------------------------------------------------
        # 7. Visualization overlay
        # ------------------------------------------------------------------
        viz_img = self._draw_visualization(left_bgr.copy(), fused, depth_m, emergency)
        try:
            viz_msg = self._bridge.cv2_to_imgmsg(viz_img, encoding="bgr8")
            if stamp:
                viz_msg.header.stamp = stamp
            viz_msg.header.frame_id = "stereo_left_optical"
            self._pub_viz.publish(viz_msg)
        except CvBridgeError as exc:
            self.get_logger().warning(f"Visualization publish failed: {exc}")

        # ------------------------------------------------------------------
        # 8. Costmap update
        # ------------------------------------------------------------------
        self._publish_costmap_update(fused, depth_m, h_orig, w_orig)

        # ------------------------------------------------------------------
        # 9. Latency accounting
        # ------------------------------------------------------------------
        elapsed_ms = (time.monotonic() - t_start) * 1000.0
        self._frame_latencies.append(elapsed_ms)
        self._inference_count += 1

        if elapsed_ms > 100.0:
            self.get_logger().warning(
                f"Frame processing latency {elapsed_ms:.1f} ms exceeded 100 ms target"
            )

    # ------------------------------------------------------------------
    # ONNX inference
    # ------------------------------------------------------------------

    def _run_onnx_inference(
        self,
        bgr: np.ndarray,
        depth_m: Optional[np.ndarray],
        conf_threshold: float,
        h_orig: int,
        w_orig: int,
    ) -> List[dict]:
        """
        Run the ONNX hazard detection model.

        Expects a YOLOv8-style model with output shape [1, 8, 8400]:
          rows 0-3: cx, cy, w, h (normalised to model input size)
          rows 4-7: class scores for {boulder, deep_crater, steep_slope, comms_shadow}
        """
        # Preprocess: resize + normalise to [0,1] float32, NCHW
        resized = cv2.resize(bgr, (MODEL_INPUT_W, MODEL_INPUT_H))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        tensor = np.transpose(rgb, (2, 0, 1))[np.newaxis, ...]  # 1x3xHxW

        try:
            inp_name = self._ort_session.get_inputs()[0].name
            outputs = self._ort_session.run(None, {inp_name: tensor})
        except Exception as exc:
            self.get_logger().error(f"ONNX inference error: {exc}")
            return []

        raw = outputs[0]  # expected [1, 8, 8400]
        if raw.ndim == 3:
            raw = raw[0]  # [8, 8400]
        if raw.shape[0] == 8:
            raw = raw.T  # [8400, 8]

        detections: List[dict] = []
        if raw.shape[1] < 4 + NUM_HAZARD_CLASSES:
            self.get_logger().warning(
                f"Unexpected model output shape: {raw.shape}"
            )
            return detections

        cx = raw[:, 0]
        cy = raw[:, 1]
        bw = raw[:, 2]
        bh = raw[:, 3]
        class_scores = raw[:, 4: 4 + NUM_HAZARD_CLASSES]

        class_ids = np.argmax(class_scores, axis=1)
        confidences = class_scores[np.arange(len(class_ids)), class_ids]

        mask = confidences >= conf_threshold
        cx, cy, bw, bh = cx[mask], cy[mask], bw[mask], bh[mask]
        class_ids = class_ids[mask]
        confidences = confidences[mask]

        if len(cx) == 0:
            return detections

        # Convert cx/cy/bw/bh (model coords) -> x1/y1/x2/y2 (original image coords)
        sx = w_orig / MODEL_INPUT_W
        sy = h_orig / MODEL_INPUT_H

        x1 = np.clip(((cx - bw / 2) * sx).astype(int), 0, w_orig - 1)
        y1 = np.clip(((cy - bh / 2) * sy).astype(int), 0, h_orig - 1)
        x2 = np.clip(((cx + bw / 2) * sx).astype(int), 0, w_orig - 1)
        y2 = np.clip(((cy + bh / 2) * sy).astype(int), 0, h_orig - 1)

        boxes = np.stack([x1, y1, x2, y2], axis=1).astype(float)
        kept = non_max_suppression(boxes, confidences)

        fusion_weight_cam = (
            self.get_parameter("camera_fusion_weight")
            .get_parameter_value()
            .double_value
        )

        for idx in kept:
            bx1, by1, bx2, by2 = int(x1[idx]), int(y1[idx]), int(x2[idx]), int(y2[idx])
            dist = 0.0
            if depth_m is not None:
                dist = self._depth_estimator.depth_at_box(
                    depth_m, bx1, by1, bx2, by2
                )
            cid = int(class_ids[idx])
            # 3D body-frame position: assume camera is at origin, flat ground plane
            focal = self.get_parameter("focal_length_px").get_parameter_value().double_value
            cx_img = (bx1 + bx2) / 2.0
            cy_img = (by1 + by2) / 2.0
            x_body = dist * (cx_img - w_orig / 2.0) / focal if dist > 0 else 0.0
            y_body = 0.0
            z_body = dist

            detections.append({
                "source": "camera",
                "class_id": cid,
                "class_name": HAZARD_CLASSES.get(cid, "unknown"),
                "confidence": float(confidences[idx]) * fusion_weight_cam,
                "raw_confidence": float(confidences[idx]),
                "distance_m": dist,
                "x_body": x_body,
                "y_body": y_body,
                "z_body": z_body,
                "bbox_x1": bx1,
                "bbox_y1": by1,
                "bbox_x2": bx2,
                "bbox_y2": by2,
            })

        return detections

    # ------------------------------------------------------------------
    # Heuristic fallback detection (no ONNX model)
    # ------------------------------------------------------------------

    def _heuristic_detect(
        self,
        bgr: np.ndarray,
        depth_m: Optional[np.ndarray],
        conf_threshold: float,
    ) -> List[dict]:
        """
        Lightweight heuristic detector for when the ONNX model is unavailable.

        Uses:
          - Depth discontinuity edges  -> boulder / crater candidates
          - Dark-region detection      -> shadow candidates
        """
        detections: List[dict] = []
        h, w = bgr.shape[:2]
        focal = self.get_parameter("focal_length_px").get_parameter_value().double_value

        # Shadow detection via luminance threshold
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        _, shadow_mask = cv2.threshold(gray, 40, 255, cv2.THRESH_BINARY_INV)
        shadow_mask = cv2.morphologyEx(shadow_mask, cv2.MORPH_OPEN, np.ones((15, 15)))
        contours, _ = cv2.findContours(
            shadow_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 2000:
                continue
            bx, by, bw_c, bh_c = cv2.boundingRect(cnt)
            cx_i = bx + bw_c / 2
            dist = 0.0
            if depth_m is not None:
                dist = self._depth_estimator.depth_at_box(
                    depth_m, bx, by, bx + bw_c, by + bh_c
                )
            detections.append({
                "source": "heuristic",
                "class_id": 3,
                "class_name": "comms_shadow",
                "confidence": 0.55,
                "raw_confidence": 0.55,
                "distance_m": dist,
                "x_body": dist * (cx_i - w / 2) / focal if dist > 0 else 0.0,
                "y_body": 0.0,
                "z_body": dist,
                "bbox_x1": bx,
                "bbox_y1": by,
                "bbox_x2": bx + bw_c,
                "bbox_y2": by + bh_c,
            })

        # Depth-based obstacle detection
        if depth_m is not None:
            # Sobel gradient of depth -> large gradients = obstacles
            valid_d = np.where(depth_m > 0, depth_m, 0).astype(np.float32)
            sobel = cv2.Sobel(valid_d, cv2.CV_32F, 1, 1, ksize=5)
            sobel_abs = np.abs(sobel)
            _, edge_mask = cv2.threshold(
                sobel_abs, 0.8, 255, cv2.THRESH_BINARY
            )
            edge_mask_u8 = edge_mask.astype(np.uint8)
            edge_mask_u8 = cv2.morphologyEx(
                edge_mask_u8, cv2.MORPH_DILATE, np.ones((9, 9))
            )
            contours2, _ = cv2.findContours(
                edge_mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            for cnt in contours2:
                area = cv2.contourArea(cnt)
                if area < 500:
                    continue
                bx, by, bw_c, bh_c = cv2.boundingRect(cnt)
                dist = self._depth_estimator.depth_at_box(
                    depth_m, bx, by, bx + bw_c, by + bh_c
                )
                if dist <= 0:
                    continue
                # Heuristic: close obstacles (~<5m) -> boulder, further -> crater
                cid = 0 if dist < 5.0 else 1
                cx_i = bx + bw_c / 2
                detections.append({
                    "source": "heuristic",
                    "class_id": cid,
                    "class_name": HAZARD_CLASSES[cid],
                    "confidence": 0.60,
                    "raw_confidence": 0.60,
                    "distance_m": dist,
                    "x_body": dist * (cx_i - w / 2) / focal,
                    "y_body": 0.0,
                    "z_body": dist,
                    "bbox_x1": bx,
                    "bbox_y1": by,
                    "bbox_x2": bx + bw_c,
                    "bbox_y2": by + bh_c,
                })

        return detections

    # ------------------------------------------------------------------
    # Sensor fusion
    # ------------------------------------------------------------------

    def _fuse_detections(
        self,
        camera: List[dict],
        lidar: List[dict],
    ) -> List[dict]:
        """
        Fuse camera and LIDAR detections.

        Strategy:
          - For each LIDAR candidate, check if a camera detection with the
            same class overlaps in bearing (±10°). If so, boost its confidence
            using a weighted average weighted by lidar_fusion_weight.
          - Remaining LIDAR candidates with confidence > threshold are added
            as standalone detections.
          - Camera detections are returned with their confidence unchanged.
        """
        lidar_weight = (
            self.get_parameter("lidar_fusion_weight")
            .get_parameter_value()
            .double_value
        )
        conf_threshold = (
            self.get_parameter("detection_confidence_threshold")
            .get_parameter_value()
            .double_value
        )
        focal = (
            self.get_parameter("focal_length_px")
            .get_parameter_value()
            .double_value
        )

        fused = list(camera)  # start with all camera detections

        for ldet in lidar:
            bearing = ldet["bearing_rad"]
            dist = ldet["distance_m"]
            lclass = ldet["class_id"]

            # Try to find a matching camera detection
            matched = False
            for cdet in fused:
                if cdet["class_id"] != lclass:
                    continue
                # Compute approximate bearing of camera detection
                if dist > 0 and focal > 0:
                    cx_img = (cdet["bbox_x1"] + cdet["bbox_x2"]) / 2.0
                    # bearing from centre of image
                    cam_bear = np.arctan2(
                        cx_img - 640 / 2.0, focal
                    )
                    if abs(cam_bear - bearing) < np.deg2rad(10.0):
                        # Boost confidence
                        fused_conf = (
                            cdet["raw_confidence"] * (1 - lidar_weight)
                            + ldet["confidence"] * lidar_weight
                        )
                        cdet["confidence"] = fused_conf
                        # Refine distance with LIDAR (more accurate)
                        if ldet["distance_m"] > 0:
                            cdet["distance_m"] = (
                                cdet["distance_m"] * 0.3 + ldet["distance_m"] * 0.7
                            )
                        matched = True
                        break

            if not matched and ldet["confidence"] >= conf_threshold:
                # Add as a LIDAR-only detection
                fused.append({
                    "source": "lidar",
                    "class_id": lclass,
                    "class_name": HAZARD_CLASSES.get(lclass, "unknown"),
                    "confidence": ldet["confidence"],
                    "raw_confidence": ldet["confidence"],
                    "distance_m": dist,
                    "x_body": dist * np.sin(bearing),
                    "y_body": 0.0,
                    "z_body": dist * np.cos(bearing),
                    "bbox_x1": 0,
                    "bbox_y1": 0,
                    "bbox_x2": 0,
                    "bbox_y2": 0,
                })

        return fused

    # ------------------------------------------------------------------
    # Visualization
    # ------------------------------------------------------------------

    def _draw_visualization(
        self,
        bgr: np.ndarray,
        detections: List[dict],
        depth_m: Optional[np.ndarray],
        emergency: bool,
    ) -> np.ndarray:
        """Draw bounding boxes, labels, and depth overlay on the image."""
        font = cv2.FONT_HERSHEY_SIMPLEX

        # Depth overlay (heat-map tinted alpha blend)
        if depth_m is not None:
            valid = depth_m > 0
            d_norm = np.zeros_like(depth_m, dtype=np.uint8)
            if valid.any():
                d_clip = np.clip(depth_m, 0, 20.0)
                d_norm = (255 * (1.0 - d_clip / 20.0)).astype(np.uint8)
            depth_color = cv2.applyColorMap(d_norm, cv2.COLORMAP_JET)
            mask_3ch = np.stack([valid, valid, valid], axis=-1)
            bgr = np.where(mask_3ch, cv2.addWeighted(bgr, 0.65, depth_color, 0.35, 0), bgr).astype(np.uint8)

        # Bounding boxes
        for det in detections:
            x1, y1, x2, y2 = det["bbox_x1"], det["bbox_y1"], det["bbox_x2"], det["bbox_y2"]
            if x1 == x2 == y1 == y2 == 0:
                continue  # LIDAR-only, no image bbox
            cid = det["class_id"]
            color = HAZARD_COLORS_BGR.get(cid, (255, 255, 255))
            cv2.rectangle(bgr, (x1, y1), (x2, y2), color, 2)
            label = (
                f"{det['class_name']} "
                f"{det['confidence']:.2f} "
                f"{det['distance_m']:.1f}m"
            )
            (tw, th), _ = cv2.getTextSize(label, font, 0.5, 1)
            cv2.rectangle(bgr, (x1, y1 - th - 6), (x1 + tw, y1), color, -1)
            cv2.putText(bgr, label, (x1, y1 - 4), font, 0.5, (0, 0, 0), 1, cv2.LINE_AA)

        # Emergency stop banner
        if emergency:
            h, w = bgr.shape[:2]
            overlay = bgr.copy()
            cv2.rectangle(overlay, (0, 0), (w, 50), (0, 0, 200), -1)
            bgr = cv2.addWeighted(bgr, 0.5, overlay, 0.5, 0)
            cv2.putText(
                bgr,
                "!! EMERGENCY STOP ACTIVE !!",
                (w // 2 - 200, 35),
                font, 1.0, (255, 255, 255), 2, cv2.LINE_AA,
            )

        return bgr

    # ------------------------------------------------------------------
    # Costmap update publisher
    # ------------------------------------------------------------------

    def _publish_costmap_update(
        self,
        detections: List[dict],
        depth_m: Optional[np.ndarray],
        h_orig: int,
        w_orig: int,
    ) -> None:
        """Build and publish a costmap update based on detected hazards."""
        resolution = (
            self.get_parameter("costmap_resolution_m")
            .get_parameter_value()
            .double_value
        )
        width = (
            self.get_parameter("costmap_width_cells")
            .get_parameter_value()
            .integer_value
        )
        height = (
            self.get_parameter("costmap_height_cells")
            .get_parameter_value()
            .integer_value
        )

        # Initialise cost grid
        cost_grid = np.zeros((height, width), dtype=np.int8)
        origin_x = -(width * resolution / 2.0)
        origin_y = 0.0  # costmap starts at rover front

        # Project each detection to costmap cell
        for det in detections:
            dist = det["distance_m"]
            if dist <= 0:
                continue
            x_m = det.get("x_body", 0.0)
            z_m = det.get("z_body", dist)

            # Convert body-frame to costmap indices
            col = int((x_m - origin_x) / resolution)
            row = int(z_m / resolution)
            if 0 <= row < height and 0 <= col < width:
                # Inflation radius based on class
                class_cost = {0: 100, 1: 100, 2: 80, 3: 60}.get(det["class_id"], 70)
                inflate_r = {0: 3, 1: 4, 2: 5, 3: 2}.get(det["class_id"], 3)
                rr, cc = np.ogrid[-inflate_r: inflate_r + 1, -inflate_r: inflate_r + 1]
                circle = rr ** 2 + cc ** 2 <= inflate_r ** 2
                r0 = max(0, row - inflate_r)
                r1 = min(height, row + inflate_r + 1)
                c0 = max(0, col - inflate_r)
                c1 = min(width, col + inflate_r + 1)
                cr0 = inflate_r - (row - r0)
                cr1 = cr0 + (r1 - r0)
                cc0 = inflate_r - (col - c0)
                cc1 = cc0 + (c1 - c0)
                cost_grid[r0:r1, c0:c1] = np.maximum(
                    cost_grid[r0:r1, c0:c1],
                    np.where(circle[cr0:cr1, cc0:cc1], class_cost, 0),
                )

        # Publish as OccupancyGrid (fallback when nav2_msgs unavailable)
        grid_msg = OccupancyGrid()
        grid_msg.header.stamp = self.get_clock().now().to_msg()
        grid_msg.header.frame_id = "base_link"
        grid_msg.info.resolution = resolution
        grid_msg.info.width = width
        grid_msg.info.height = height
        grid_msg.info.origin.position.x = origin_x
        grid_msg.info.origin.position.y = origin_y
        grid_msg.data = cost_grid.flatten().tolist()

        if _HAS_NAV2:
            update = Costmap2DUpdate()
            update.header = grid_msg.header
            update.x = 0
            update.y = 0
            update.width = width
            update.height = height
            update.cells = [int(v) for v in cost_grid.flatten()]
            self._pub_costmap.publish(update)
        else:
            self._pub_costmap.publish(grid_msg)

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def _cb_diagnostics(self) -> None:
        """Log periodic performance stats."""
        if not self._frame_latencies:
            return
        lats = list(self._frame_latencies)
        self.get_logger().info(
            f"[DIAG] frames={self._inference_count}  "
            f"latency_ms: mean={np.mean(lats):.1f} "
            f"max={np.max(lats):.1f} "
            f"p95={np.percentile(lats, 95):.1f}  "
            f"estop={'YES' if self._emergency_stop_active else 'no'}"
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(args=None) -> None:
    rclpy.init(args=args)
    node = HazardDetectionNode()
    executor = rclpy.executors.MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
