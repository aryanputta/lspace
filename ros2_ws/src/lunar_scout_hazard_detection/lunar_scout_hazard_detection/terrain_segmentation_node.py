#!/usr/bin/env python3
"""
Terrain Segmentation Node for NASA Lunar Scout Rover.

Runs per-pixel terrain classification at 10 Hz using a dual-input ONNX model
that fuses visible-light stereo left imagery with thermal IR imagery.

Output classes (8 terrain types):
    0 - unknown
    1 - regolith_flat     : safe, low traversal cost
    2 - regolith_rough    : moderate caution required
    3 - rock_field        : high traversal cost
    4 - crater_floor      : very high cost, avoid
    5 - crater_rim        : high cost
    6 - bedrock           : moderate cost
    7 - shadow            : near-impassable (thermal / comms risk)

Subscriptions:
    /stereo/left/image_raw  (sensor_msgs/Image)
    /thermal/image_raw      (sensor_msgs/Image)

Publications:
    /terrain_segmentation   (sensor_msgs/Image, mono8 class map)
    /terrain_visualization  (sensor_msgs/Image, RGB colour overlay)
    /traversability_map     (nav_msgs/OccupancyGrid)
"""

from __future__ import annotations

import threading
import time
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

import rclpy
from rclpy.node import Node
from rclpy.qos import (
    QoSProfile,
    QoSReliabilityPolicy,
    QoSHistoryPolicy,
    QoSDurabilityPolicy,
)
from rclpy.callback_groups import ReentrantCallbackGroup, MutuallyExclusiveCallbackGroup

from sensor_msgs.msg import Image
from nav_msgs.msg import OccupancyGrid

try:
    from cv_bridge import CvBridge, CvBridgeError
    _HAS_CV_BRIDGE = True
except (ImportError, AttributeError):
    # AttributeError: _ARRAY_API not found — numpy 2.x ABI mismatch with cv_bridge 1.x
    _HAS_CV_BRIDGE = False
    CvBridgeError = Exception  # type: ignore[assignment,misc]

try:
    import onnxruntime as ort
    _HAS_ONNX = True
except ImportError:
    _HAS_ONNX = False

from lunar_scout_hazard_detection import (
    TERRAIN_CLASSES,
    TERRAIN_COLORS_BGR,
    TRAVERSABILITY_COST,
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

RELIABLE_QOS = QoSProfile(
    reliability=QoSReliabilityPolicy.RELIABLE,
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=5,
    durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SEG_INPUT_H = 512
SEG_INPUT_W = 512
NUM_TERRAIN_CLASSES = 8

# Thermal normalisation range (Kelvin, typical lunar surface 90–400 K)
THERMAL_MIN_K = 90.0
THERMAL_MAX_K = 400.0

# Morphological post-processing kernel sizes
MORPH_OPEN_SIZE = 5
MORPH_CLOSE_SIZE = 7


# ---------------------------------------------------------------------------
# CRF-lite post-processor
# ---------------------------------------------------------------------------
class DenseCRFLite:
    """
    Lightweight approximation of DenseCRF for segmentation smoothing.

    Uses bilateral filtering as a spatial-colour consistency prior,
    equivalent in effect to a single mean-field CRF iteration but
    executable without the pydensecrf dependency.
    """

    def __init__(
        self,
        num_classes: int = NUM_TERRAIN_CLASSES,
        spatial_sigma: float = 3.0,
        colour_sigma: float = 10.0,
        num_iterations: int = 2,
    ) -> None:
        self.num_classes = num_classes
        self.spatial_sigma = spatial_sigma
        self.colour_sigma = colour_sigma
        self.num_iterations = num_iterations

    def apply(
        self, logits: np.ndarray, reference_bgr: np.ndarray
    ) -> np.ndarray:
        """
        Refine per-class probability maps using guided bilateral smoothing.

        Parameters
        ----------
        logits: C x H x W float32 probability maps (softmax applied)
        reference_bgr: H x W x 3 uint8 reference image for edge guidance

        Returns
        -------
        refined: C x H x W float32
        """
        h, w = reference_bgr.shape[:2]
        guide = cv2.resize(reference_bgr, (w, h)).astype(np.float32)
        refined = logits.copy()

        for _ in range(self.num_iterations):
            for c in range(self.num_classes):
                prob_c = refined[c]  # H x W
                # Guided bilateral filter as spatial-colour pairwise term
                filtered = cv2.ximgproc.guidedFilter(
                    guide.astype(np.float32),
                    prob_c.astype(np.float32),
                    radius=int(self.spatial_sigma * 3),
                    eps=self.colour_sigma ** 2,
                )
                refined[c] = np.clip(filtered, 1e-6, 1.0)
            # Re-normalise to sum-to-one
            sum_probs = refined.sum(axis=0, keepdims=True) + 1e-6
            refined = refined / sum_probs

        return refined


# ---------------------------------------------------------------------------
# Heuristic segmentation fallback
# ---------------------------------------------------------------------------
class HeuristicSegmenter:
    """
    Fallback terrain segmenter for when the ONNX model is unavailable.

    Uses brightness, colour ratios, and thermal temperature bands to
    produce a coarse class map.
    """

    def segment(
        self,
        bgr: np.ndarray,
        thermal_k: Optional[np.ndarray],
    ) -> np.ndarray:
        """
        Produce H x W uint8 class map.

        Parameters
        ----------
        bgr:       H x W x 3 uint8 visible image
        thermal_k: H x W float32 thermal map in Kelvin (or None)
        """
        h, w = bgr.shape[:2]
        class_map = np.zeros((h, w), dtype=np.uint8)

        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)

        # Shadow: very dark pixels
        shadow = gray < 40
        class_map[shadow] = 7

        # Rock field: high gradient variance
        sobel_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        gradient_mag = np.sqrt(sobel_x ** 2 + sobel_y ** 2)
        rock_field = (gradient_mag > 30) & ~shadow
        class_map[rock_field] = 3

        # Crater floor: very low local variance (uniformly dark/flat)
        var_map = cv2.GaussianBlur(gray ** 2, (15, 15), 5) - cv2.GaussianBlur(gray, (15, 15), 5) ** 2
        crater = (var_map < 15) & (gray < 80) & ~shadow
        class_map[crater] = 4

        # Thermal overlays
        if thermal_k is not None:
            thermal_resized = cv2.resize(thermal_k, (w, h))
            # Very hot regions (>380K) in sunlight = bedrock
            hot = thermal_resized > 380
            class_map[hot & ~shadow] = 6
            # Cold regions in shadow (<120K)
            cold = thermal_resized < 120
            class_map[cold] = 7

        # Remaining bright flat regions: flat regolith
        flat = (gray > 120) & (gradient_mag < 10) & (class_map == 0)
        class_map[flat] = 1

        # Rough regolith: everything else unlabelled
        class_map[class_map == 0] = 2

        return class_map


# ---------------------------------------------------------------------------
# Main segmentation node
# ---------------------------------------------------------------------------
class TerrainSegmentationNode(Node):
    """
    Terrain segmentation inference node for the Lunar Scout rover.

    Processes stereo left + thermal frames at 10 Hz using an ONNX model
    (encoder-decoder architecture, e.g. SegFormer-B2 trained on lunar sim data).
    Falls back to heuristic segmentation if no model is loaded.
    """

    def __init__(self) -> None:
        super().__init__("terrain_segmentation_node")

        # Declare parameters
        self.declare_parameter("model_path", "")
        self.declare_parameter("inference_hz", 10.0)
        self.declare_parameter("costmap_resolution_m", 0.05)
        self.declare_parameter("costmap_width_m", 10.0)
        self.declare_parameter("costmap_height_m", 10.0)
        self.declare_parameter("use_crf_postprocessing", True)
        self.declare_parameter("confidence_threshold", 0.60)
        self.declare_parameter("camera_hfov_deg", 70.0)
        self.declare_parameter("camera_height_m", 1.2)
        self.declare_parameter("camera_pitch_deg", -15.0)

        # Internal state
        self._lock = threading.Lock()
        self._bridge: Optional[CvBridge] = None
        self._ort_session: Optional[ort.InferenceSession] = None
        self._heuristic: HeuristicSegmenter = HeuristicSegmenter()
        self._crf: Optional[DenseCRFLite] = None

        self._left_bgr: Optional[np.ndarray] = None
        self._thermal_k: Optional[np.ndarray] = None
        self._left_stamp = None

        self._frame_count: int = 0
        self._total_infer_ms: float = 0.0

        # Callback groups
        self._sensor_cbg = ReentrantCallbackGroup()
        self._timer_cbg = MutuallyExclusiveCallbackGroup()

        self._setup()

    def _setup(self) -> None:
        if not _HAS_CV_BRIDGE:
            self.get_logger().error("cv_bridge not available")
            return

        self._bridge = CvBridge()

        # Load ONNX model
        model_path = self.get_parameter("model_path").get_parameter_value().string_value
        if model_path and _HAS_ONNX:
            try:
                opts = ort.SessionOptions()
                opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                opts.intra_op_num_threads = 4
                providers = ["CPUExecutionProvider"]
                if "CUDAExecutionProvider" in ort.get_available_providers():
                    providers = ["CUDAExecutionProvider"] + providers
                self._ort_session = ort.InferenceSession(
                    model_path, sess_options=opts, providers=providers
                )
                self.get_logger().info(f"Terrain segmentation ONNX model loaded: {model_path}")
            except Exception as exc:
                self.get_logger().warning(
                    f"ONNX model load failed ({exc}); using heuristic fallback"
                )

        # CRF post-processor
        if self.get_parameter("use_crf_postprocessing").get_parameter_value().bool_value:
            self._crf = DenseCRFLite()

        # Subscriptions
        self._sub_left = self.create_subscription(
            Image,
            "/stereo/left/image_raw",
            self._cb_left,
            SENSOR_QOS,
            callback_group=self._sensor_cbg,
        )
        self._sub_thermal = self.create_subscription(
            Image,
            "/thermal/image_raw",
            self._cb_thermal,
            SENSOR_QOS,
            callback_group=self._sensor_cbg,
        )

        # Publishers
        self._pub_seg = self.create_publisher(
            Image,
            "/terrain_segmentation",
            RELIABLE_QOS,
        )
        self._pub_viz = self.create_publisher(
            Image,
            "/terrain_visualization",
            SENSOR_QOS,
        )
        self._pub_trav = self.create_publisher(
            OccupancyGrid,
            "/traversability_map",
            RELIABLE_QOS,
        )

        # Processing timer
        hz = self.get_parameter("inference_hz").get_parameter_value().double_value
        period = 1.0 / max(hz, 1.0)
        self._timer = self.create_timer(
            period, self._cb_process, callback_group=self._timer_cbg
        )

        self.get_logger().info(
            f"TerrainSegmentationNode ready — "
            f"{'ONNX' if self._ort_session else 'heuristic'} mode @ {hz:.1f} Hz"
        )

    # ------------------------------------------------------------------
    # Sensor callbacks
    # ------------------------------------------------------------------

    def _cb_left(self, msg: Image) -> None:
        try:
            bgr = self._bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except CvBridgeError as exc:
            self.get_logger().warning(f"Left image conversion error: {exc}")
            return
        with self._lock:
            self._left_bgr = bgr
            self._left_stamp = msg.header.stamp

    def _cb_thermal(self, msg: Image) -> None:
        """
        Accept 16-bit thermal images (raw DN) or 32-bit float Kelvin maps.
        Convert to float32 Kelvin internally.
        """
        try:
            if msg.encoding in ("16UC1", "mono16"):
                raw = self._bridge.imgmsg_to_cv2(msg, desired_encoding="16UC1")
                # Convert raw DN to Kelvin: assume 0.01 K/DN scaling
                thermal_k = raw.astype(np.float32) * 0.01
            elif msg.encoding in ("32FC1",):
                thermal_k = self._bridge.imgmsg_to_cv2(msg, desired_encoding="32FC1")
            else:
                gray = self._bridge.imgmsg_to_cv2(msg, desired_encoding="mono8")
                # Scale 0-255 -> 90-400 K
                thermal_k = gray.astype(np.float32) / 255.0 * (THERMAL_MAX_K - THERMAL_MIN_K) + THERMAL_MIN_K
        except CvBridgeError as exc:
            self.get_logger().warning(f"Thermal image conversion error: {exc}")
            return
        with self._lock:
            self._thermal_k = thermal_k

    # ------------------------------------------------------------------
    # Processing timer callback
    # ------------------------------------------------------------------

    def _cb_process(self) -> None:
        t_start = time.monotonic()

        with self._lock:
            bgr = self._left_bgr.copy() if self._left_bgr is not None else None
            thermal = self._thermal_k.copy() if self._thermal_k is not None else None
            stamp = self._left_stamp

        if bgr is None:
            return

        h_orig, w_orig = bgr.shape[:2]

        # ------------------------------------------------------------------
        # 1. Inference
        # ------------------------------------------------------------------
        if self._ort_session is not None:
            class_map, prob_map = self._run_onnx(bgr, thermal)
        else:
            class_map = self._heuristic.segment(bgr, thermal)
            # Build a trivial one-hot probability map for downstream CRF
            prob_map = np.zeros(
                (NUM_TERRAIN_CLASSES, h_orig, w_orig), dtype=np.float32
            )
            for c in range(NUM_TERRAIN_CLASSES):
                prob_map[c] = (class_map == c).astype(np.float32)

        # ------------------------------------------------------------------
        # 2. CRF post-processing
        # ------------------------------------------------------------------
        if self._crf is not None:
            try:
                prob_map_r = cv2.resize(
                    prob_map.transpose(1, 2, 0),
                    (w_orig, h_orig),
                    interpolation=cv2.INTER_LINEAR,
                ).transpose(2, 0, 1)
                prob_refined = self._crf.apply(prob_map_r, bgr)
                class_map = np.argmax(prob_refined, axis=0).astype(np.uint8)
            except Exception as exc:
                self.get_logger().debug(f"CRF post-processing failed: {exc}")

        # ------------------------------------------------------------------
        # 3. Morphological cleanup
        # ------------------------------------------------------------------
        class_map = self._morph_clean(class_map)

        # ------------------------------------------------------------------
        # 4. Publish class map (mono8 image)
        # ------------------------------------------------------------------
        try:
            seg_msg = self._bridge.cv2_to_imgmsg(class_map, encoding="mono8")
            if stamp:
                seg_msg.header.stamp = stamp
            seg_msg.header.frame_id = "stereo_left_optical"
            self._pub_seg.publish(seg_msg)
        except CvBridgeError as exc:
            self.get_logger().warning(f"Seg map publish failed: {exc}")

        # ------------------------------------------------------------------
        # 5. Colour visualization
        # ------------------------------------------------------------------
        viz = self._colourise(class_map, bgr)
        try:
            viz_msg = self._bridge.cv2_to_imgmsg(viz, encoding="bgr8")
            if stamp:
                viz_msg.header.stamp = stamp
            viz_msg.header.frame_id = "stereo_left_optical"
            self._pub_viz.publish(viz_msg)
        except CvBridgeError as exc:
            self.get_logger().warning(f"Viz publish failed: {exc}")

        # ------------------------------------------------------------------
        # 6. Traversability map (OccupancyGrid)
        # ------------------------------------------------------------------
        self._publish_traversability(class_map, stamp)

        # ------------------------------------------------------------------
        # Timing
        # ------------------------------------------------------------------
        elapsed_ms = (time.monotonic() - t_start) * 1000.0
        self._total_infer_ms += elapsed_ms
        self._frame_count += 1

        if self._frame_count % 50 == 0:
            mean_ms = self._total_infer_ms / self._frame_count
            self.get_logger().info(
                f"[TERRAIN] frames={self._frame_count}  "
                f"mean_latency={mean_ms:.1f} ms"
            )

    # ------------------------------------------------------------------
    # ONNX inference
    # ------------------------------------------------------------------

    def _run_onnx(
        self,
        bgr: np.ndarray,
        thermal_k: Optional[np.ndarray],
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Run the ONNX terrain segmentation model.

        The model expects either:
          - A single 4-channel RGBT tensor [1, 4, H, W]  (RGB + thermal)
          - Or a single 3-channel RGB tensor [1, 3, H, W]

        Returns (class_map HxW uint8, prob_map CxHxW float32)
        """
        h_orig, w_orig = bgr.shape[:2]

        rgb = cv2.cvtColor(
            cv2.resize(bgr, (SEG_INPUT_W, SEG_INPUT_H)), cv2.COLOR_BGR2RGB
        ).astype(np.float32) / 255.0

        inputs = self._ort_session.get_inputs()
        inp_name = inputs[0].name
        inp_shape = inputs[0].shape  # e.g. [1, C, H, W] or dynamic

        if len(inputs) == 1:
            # Single input: check if 4-channel (RGBT) or 3-channel (RGB)
            channels = inp_shape[1] if isinstance(inp_shape[1], int) else 4
            if channels == 4 and thermal_k is not None:
                t_norm = cv2.resize(thermal_k, (SEG_INPUT_W, SEG_INPUT_H))
                t_norm = np.clip(
                    (t_norm - THERMAL_MIN_K) / (THERMAL_MAX_K - THERMAL_MIN_K), 0, 1
                ).astype(np.float32)
                tensor = np.concatenate(
                    [rgb.transpose(2, 0, 1), t_norm[np.newaxis]], axis=0
                )[np.newaxis]
            else:
                tensor = rgb.transpose(2, 0, 1)[np.newaxis]
            feed = {inp_name: tensor}
        else:
            # Dual input model
            tensor_vis = rgb.transpose(2, 0, 1)[np.newaxis]
            feed = {inp_name: tensor_vis}
            if len(inputs) > 1 and thermal_k is not None:
                t_norm = cv2.resize(thermal_k, (SEG_INPUT_W, SEG_INPUT_H))
                t_norm = np.clip(
                    (t_norm - THERMAL_MIN_K) / (THERMAL_MAX_K - THERMAL_MIN_K), 0, 1
                ).astype(np.float32)[np.newaxis, np.newaxis]
                feed[inputs[1].name] = t_norm

        try:
            outputs = self._ort_session.run(None, feed)
        except Exception as exc:
            self.get_logger().error(f"Terrain ONNX inference error: {exc}")
            # Return uniform unknown map on error
            class_map = np.zeros((h_orig, w_orig), dtype=np.uint8)
            prob_map = np.zeros((NUM_TERRAIN_CLASSES, h_orig, w_orig), dtype=np.float32)
            prob_map[0] = 1.0
            return class_map, prob_map

        # Expect output [1, C, H, W] logits
        raw = outputs[0]  # [1, C, H, W]
        if raw.ndim == 4:
            raw = raw[0]  # [C, H, W]

        # Apply softmax
        raw_exp = np.exp(raw - raw.max(axis=0, keepdims=True))
        prob_map = (raw_exp / raw_exp.sum(axis=0, keepdims=True)).astype(np.float32)

        # Argmax for class map, resize to original resolution
        class_map_small = np.argmax(prob_map, axis=0).astype(np.uint8)
        class_map = cv2.resize(
            class_map_small, (w_orig, h_orig), interpolation=cv2.INTER_NEAREST
        )

        return class_map, prob_map

    # ------------------------------------------------------------------
    # Morphological post-processing
    # ------------------------------------------------------------------

    def _morph_clean(self, class_map: np.ndarray) -> np.ndarray:
        """Remove salt-and-pepper noise via per-class open+close."""
        result = class_map.copy()
        for c in range(1, NUM_TERRAIN_CLASSES):
            mask = (class_map == c).astype(np.uint8)
            if not mask.any():
                continue
            kernel_open = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (MORPH_OPEN_SIZE, MORPH_OPEN_SIZE)
            )
            kernel_close = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (MORPH_CLOSE_SIZE, MORPH_CLOSE_SIZE)
            )
            cleaned = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_open)
            cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel_close)
            result[cleaned == 1] = c
        return result

    # ------------------------------------------------------------------
    # Colour visualisation
    # ------------------------------------------------------------------

    def _colourise(self, class_map: np.ndarray, bgr: np.ndarray) -> np.ndarray:
        """
        Produce an RGB colour overlay fusing the class map with the original image.

        Uses a 50% alpha blend so the underlying image texture is preserved.
        """
        h, w = class_map.shape
        colour_layer = np.zeros((h, w, 3), dtype=np.uint8)

        for class_id, colour_bgr in TERRAIN_COLORS_BGR.items():
            mask = class_map == class_id
            colour_layer[mask] = colour_bgr

        # Build legend strip
        legend_h = 20
        legend = np.zeros((legend_h * NUM_TERRAIN_CLASSES, 200, 3), dtype=np.uint8)
        for c in range(NUM_TERRAIN_CLASSES):
            y0 = c * legend_h
            y1 = y0 + legend_h
            colour = TERRAIN_COLORS_BGR.get(c, (128, 128, 128))
            legend[y0:y1, :40] = colour
            cv2.putText(
                legend,
                f"{c}: {TERRAIN_CLASSES.get(c, '?')}",
                (45, y0 + 14),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

        bgr_resized = cv2.resize(bgr, (w, h))
        overlay = cv2.addWeighted(bgr_resized, 0.5, colour_layer, 0.5, 0)

        # Attach legend (right side, padded)
        leg_h = min(legend.shape[0], h)
        legend_crop = legend[:leg_h, :]
        pad = np.zeros((h, legend.shape[1], 3), dtype=np.uint8)
        pad[:leg_h, :] = legend_crop

        return np.concatenate([overlay, pad], axis=1)

    # ------------------------------------------------------------------
    # Traversability map
    # ------------------------------------------------------------------

    def _publish_traversability(
        self, class_map: np.ndarray, stamp
    ) -> None:
        """
        Project the terrain class map into a forward-looking OccupancyGrid.

        Uses a pinhole camera projection inverse to map image pixels to
        ground-plane coordinates assuming flat terrain.
        """
        resolution = (
            self.get_parameter("costmap_resolution_m")
            .get_parameter_value()
            .double_value
        )
        grid_w_m = (
            self.get_parameter("costmap_width_m")
            .get_parameter_value()
            .double_value
        )
        grid_h_m = (
            self.get_parameter("costmap_height_m")
            .get_parameter_value()
            .double_value
        )
        cam_h = (
            self.get_parameter("camera_height_m")
            .get_parameter_value()
            .double_value
        )
        cam_pitch_deg = (
            self.get_parameter("camera_pitch_deg")
            .get_parameter_value()
            .double_value
        )
        hfov_deg = (
            self.get_parameter("camera_hfov_deg")
            .get_parameter_value()
            .double_value
        )

        grid_cols = int(grid_w_m / resolution)
        grid_rows = int(grid_h_m / resolution)
        cost_grid = np.full((grid_rows, grid_cols), 50, dtype=np.int8)  # default unknown

        img_h, img_w = class_map.shape
        fx = img_w / (2.0 * np.tan(np.deg2rad(hfov_deg / 2)))
        fy = fx
        cx = img_w / 2.0
        cy = img_h / 2.0
        pitch = np.deg2rad(cam_pitch_deg)

        # For each pixel, compute ground-plane hit via ray casting
        # This is a simplified inverse projection for flat terrain
        v_coords, u_coords = np.meshgrid(
            np.arange(img_h), np.arange(img_w), indexing="ij"
        )
        # Normalised ray direction (camera frame)
        ray_y = (v_coords - cy) / fy
        ray_x = (u_coords - cx) / fx
        ray_z = np.ones_like(ray_x)

        # Rotate by camera pitch angle (tilted downward)
        cos_p = np.cos(pitch)
        sin_p = np.sin(pitch)
        world_y = ray_y * cos_p - ray_z * sin_p
        world_z = ray_y * sin_p + ray_z * cos_p

        # Avoid upward rays (world_y must be positive downward)
        hit_mask = world_y > 0.01
        ground_dist = np.where(hit_mask, cam_h / world_y, 0.0)
        ground_x = np.where(hit_mask, ray_x * ground_dist, 0.0)
        ground_z = np.where(hit_mask, world_z * ground_dist, 0.0)

        # Map to grid indices
        col_idx = ((ground_x + grid_w_m / 2) / resolution).astype(int)
        row_idx = (ground_z / resolution).astype(int)

        valid = (
            hit_mask
            & (col_idx >= 0) & (col_idx < grid_cols)
            & (row_idx >= 0) & (row_idx < grid_rows)
        )

        classes_flat = class_map[valid]
        rows_flat = row_idx[valid]
        cols_flat = col_idx[valid]

        for ci, ri, cls in zip(cols_flat, rows_flat, classes_flat):
            cost = TRAVERSABILITY_COST.get(int(cls), 50)
            cost_grid[ri, ci] = max(cost_grid[ri, ci], cost)

        # Gaussian blur for smooth transitions
        cost_f32 = cost_grid.astype(np.float32)
        cost_f32 = cv2.GaussianBlur(cost_f32, (5, 5), 1.5)
        cost_grid = np.clip(cost_f32, 0, 100).astype(np.int8)

        grid_msg = OccupancyGrid()
        grid_msg.header.stamp = stamp if stamp else self.get_clock().now().to_msg()
        grid_msg.header.frame_id = "base_link"
        grid_msg.info.resolution = resolution
        grid_msg.info.width = grid_cols
        grid_msg.info.height = grid_rows
        grid_msg.info.origin.position.x = -(grid_w_m / 2.0)
        grid_msg.info.origin.position.y = 0.0
        grid_msg.info.origin.position.z = 0.0
        grid_msg.data = cost_grid.flatten().tolist()
        self._pub_trav.publish(grid_msg)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(args=None) -> None:
    rclpy.init(args=args)
    node = TerrainSegmentationNode()
    executor = rclpy.executors.MultiThreadedExecutor(num_threads=3)
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
