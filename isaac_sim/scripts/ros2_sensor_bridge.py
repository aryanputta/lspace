"""
LPAS Isaac Sim → ROS2 Sensor Bridge
Streams simulated sensor data to ROS2 topics for autonomy stack testing.

Requires: Isaac Sim 2023.1+ with ROS2 bridge extension enabled
"""
from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import Optional
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy

from sensor_msgs.msg import Image, Imu, LaserScan, NavSatFix
from geometry_msgs.msg import PoseStamped, TwistStamped
from nav_msgs.msg import Odometry
from std_msgs.msg import Float64MultiArray, Header
from builtin_interfaces.msg import Time

import omni
from omni.isaac.core.utils.rotations import quat_to_euler_angles, euler_angles_to_quat


SENSOR_QOS = QoSProfile(
    reliability=ReliabilityPolicy.BEST_EFFORT,
    history=HistoryPolicy.KEEP_LAST,
    depth=5,
    durability=DurabilityPolicy.VOLATILE,
)

RELIABLE_QOS = QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE,
    history=HistoryPolicy.KEEP_LAST,
    depth=10,
)


@dataclass
class SensorConfig:
    nav_cam_hz: float = 15.0
    hazard_cam_hz: float = 30.0
    lidar_hz: float = 10.0
    imu_hz: float = 100.0
    wheel_encoder_hz: float = 50.0
    gps_hz: float = 1.0
    stereo_baseline_m: float = 0.3
    lidar_min_range_m: float = 0.1
    lidar_max_range_m: float = 30.0
    lidar_num_beams: int = 360


class IsaacROS2Bridge(Node):
    """ROS2 node that publishes Isaac Sim sensor data."""

    def __init__(self, rover_prim_path: str, config: Optional[SensorConfig] = None):
        super().__init__("isaac_ros2_bridge")
        self._prim_path = rover_prim_path
        self._cfg = config or SensorConfig()
        self._t0 = self.get_clock().now()

        self._setup_publishers()
        self._setup_timers()
        self.get_logger().info("Isaac ROS2 bridge initialized")

    def _setup_publishers(self) -> None:
        self._pub_nav_cam_left = self.create_publisher(
            Image, "/stereo/left/image_raw", SENSOR_QOS
        )
        self._pub_nav_cam_right = self.create_publisher(
            Image, "/stereo/right/image_raw", SENSOR_QOS
        )
        self._pub_hazard_cam_front = self.create_publisher(
            Image, "/hazard_cam/front/image_raw", SENSOR_QOS
        )
        self._pub_lidar = self.create_publisher(
            LaserScan, "/scan", SENSOR_QOS
        )
        self._pub_imu = self.create_publisher(
            Imu, "/imu/data", SENSOR_QOS
        )
        self._pub_odom = self.create_publisher(
            Odometry, "/wheel_control/odometry", RELIABLE_QOS
        )
        self._pub_wheel_enc = self.create_publisher(
            Float64MultiArray, "/wheel_encoders", SENSOR_QOS
        )
        self._pub_ground_truth_pose = self.create_publisher(
            PoseStamped, "/ground_truth/pose", RELIABLE_QOS
        )

    def _setup_timers(self) -> None:
        self.create_timer(1.0 / self._cfg.nav_cam_hz, self._publish_nav_cameras)
        self.create_timer(1.0 / self._cfg.lidar_hz, self._publish_lidar)
        self.create_timer(1.0 / self._cfg.imu_hz, self._publish_imu)
        self.create_timer(1.0 / self._cfg.wheel_encoder_hz, self._publish_wheel_encoders)
        self.create_timer(1.0 / self._cfg.gps_hz, self._publish_ground_truth)

    def _get_rover_state(self) -> dict:
        """Read rover state from Isaac Sim scene."""
        try:
            stage = omni.usd.get_context().get_stage()
            prim = stage.GetPrimAtPath(self._prim_path)
            if not prim.IsValid():
                return {}

            from pxr import UsdGeom
            xform = UsdGeom.Xformable(prim)
            time_code = omni.usd.get_context().get_stage().GetEditTarget().GetLayer().GetTimeCodesPerSecond()
            matrix = xform.GetLocalTransformation()

            translation = matrix.ExtractTranslation()
            rotation = matrix.ExtractRotationQuat()

            return {
                "position": [translation[0], translation[1], translation[2]],
                "orientation": [
                    rotation.GetImaginary()[0],
                    rotation.GetImaginary()[1],
                    rotation.GetImaginary()[2],
                    rotation.GetReal(),
                ],
                "linear_velocity": [0.0, 0.0, 0.0],  # Would read from physics sim
                "angular_velocity": [0.0, 0.0, 0.0],
            }
        except Exception as e:
            self.get_logger().debug(f"Could not read rover state: {e}")
            return {}

    def _now_msg(self) -> Time:
        t = self.get_clock().now()
        msg = Time()
        msg.sec = t.nanoseconds // 10**9
        msg.nanosec = t.nanoseconds % 10**9
        return msg

    def _make_header(self, frame_id: str) -> Header:
        h = Header()
        h.stamp = self._now_msg()
        h.frame_id = frame_id
        return h

    def _publish_nav_cameras(self) -> None:
        """Publish simulated stereo camera images."""
        h_left = self._make_header("nav_cam_left_optical")
        h_right = self._make_header("nav_cam_right_optical")

        # In production: read from Isaac Sim camera sensor
        # Here: generate placeholder (dark with noise — lunar scene)
        img_array = np.random.randint(5, 25, (480, 640, 3), dtype=np.uint8)

        msg = Image()
        msg.header = h_left
        msg.height = 480
        msg.width = 640
        msg.encoding = "rgb8"
        msg.is_bigendian = 0
        msg.step = 640 * 3
        msg.data = img_array.tobytes()

        self._pub_nav_cam_left.publish(msg)

        msg_right = Image()
        msg_right.header = h_right
        msg_right.height = 480
        msg_right.width = 640
        msg_right.encoding = "rgb8"
        msg_right.is_bigendian = 0
        msg_right.step = 640 * 3
        # Slight rightward offset simulation for stereo baseline
        msg_right.data = np.roll(img_array, -12, axis=1).tobytes()
        self._pub_nav_cam_right.publish(msg_right)

    def _publish_lidar(self) -> None:
        """Publish simulated LIDAR scan."""
        scan = LaserScan()
        scan.header = self._make_header("lidar_link")
        scan.angle_min = -math.pi
        scan.angle_max = math.pi
        scan.angle_increment = 2 * math.pi / self._cfg.lidar_num_beams
        scan.time_increment = (1.0 / self._cfg.lidar_hz) / self._cfg.lidar_num_beams
        scan.range_min = self._cfg.lidar_min_range_m
        scan.range_max = self._cfg.lidar_max_range_m

        # Simulated ranges with terrain features
        angles = np.linspace(-np.pi, np.pi, self._cfg.lidar_num_beams)
        ranges = np.ones(self._cfg.lidar_num_beams) * 10.0
        # Add simulated obstacles (boulders)
        ranges[90:95] = 3.2   # Boulder at ~90°
        ranges[180:184] = 7.8  # Crater rim at ~180°
        ranges += np.random.normal(0, 0.02, self._cfg.lidar_num_beams)  # 2cm noise

        scan.ranges = ranges.clip(
            self._cfg.lidar_min_range_m, self._cfg.lidar_max_range_m
        ).tolist()
        scan.intensities = (np.ones(self._cfg.lidar_num_beams) * 100.0).tolist()

        self._pub_lidar.publish(scan)

    def _publish_imu(self) -> None:
        """Publish IMU data with lunar gravity."""
        imu_msg = Imu()
        imu_msg.header = self._make_header("imu_link")

        # Lunar gravity (rover at rest on flat surface → z-axis acceleration = +1.62 m/s²)
        imu_msg.linear_acceleration.x = np.random.normal(0.0, 0.005)
        imu_msg.linear_acceleration.y = np.random.normal(0.0, 0.005)
        imu_msg.linear_acceleration.z = 1.62 + np.random.normal(0.0, 0.005)

        imu_msg.angular_velocity.x = np.random.normal(0.0, 0.001)
        imu_msg.angular_velocity.y = np.random.normal(0.0, 0.001)
        imu_msg.angular_velocity.z = np.random.normal(0.0, 0.001)

        # Identity orientation (rover at rest)
        imu_msg.orientation.w = 1.0
        imu_msg.orientation.x = 0.0
        imu_msg.orientation.y = 0.0
        imu_msg.orientation.z = 0.0

        # Covariance matrices
        imu_msg.angular_velocity_covariance = [
            0.000001, 0, 0, 0, 0.000001, 0, 0, 0, 0.000001
        ]
        imu_msg.linear_acceleration_covariance = [
            0.000025, 0, 0, 0, 0.000025, 0, 0, 0, 0.000025
        ]

        self._pub_imu.publish(imu_msg)

    def _publish_wheel_encoders(self) -> None:
        """Publish simulated wheel encoder velocities (rad/s)."""
        msg = Float64MultiArray()
        # 6 wheels: [FL, ML, RL, FR, MR, RR]
        msg.data = [
            np.random.normal(0.0, 0.01) for _ in range(6)
        ]
        self._pub_wheel_enc.publish(msg)

    def _publish_ground_truth(self) -> None:
        """Publish ground truth rover pose from Isaac Sim."""
        state = self._get_rover_state()
        if not state:
            return

        pose = PoseStamped()
        pose.header = self._make_header("moon_fixed")
        pos = state.get("position", [0, 0, 0])
        ori = state.get("orientation", [0, 0, 0, 1])

        pose.pose.position.x = pos[0]
        pose.pose.position.y = pos[1]
        pose.pose.position.z = pos[2]
        pose.pose.orientation.x = ori[0]
        pose.pose.orientation.y = ori[1]
        pose.pose.orientation.z = ori[2]
        pose.pose.orientation.w = ori[3]

        self._pub_ground_truth_pose.publish(pose)


import math  # Needed for LaserScan angles


def main() -> None:
    rclpy.init()
    bridge = IsaacROS2Bridge(
        rover_prim_path="/World/LPASRover",
        config=SensorConfig(),
    )
    try:
        rclpy.spin(bridge)
    except KeyboardInterrupt:
        pass
    finally:
        bridge.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
