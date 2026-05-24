"""
LPAS Wheel Control Node

Implements rocker-bogie kinematics for 6-wheel lunar rover:
  - Differential drive inverse kinematics
  - Per-wheel velocity commands
  - Traction control via slip feedback
  - Wheel odometry computation
  - Motor safety limits enforcement
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Optional

import rclpy
from rclpy.lifecycle import LifecycleNode, LifecycleState, TransitionCallbackReturn
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from geometry_msgs.msg import Twist, Quaternion
from nav_msgs.msg import Odometry
from std_msgs.msg import Float64MultiArray
from sensor_msgs.msg import JointState

RELIABLE_QOS = QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE,
    history=HistoryPolicy.KEEP_LAST,
    depth=10,
)
SENSOR_QOS = QoSProfile(
    reliability=ReliabilityPolicy.BEST_EFFORT,
    history=HistoryPolicy.KEEP_LAST,
    depth=5,
)

# Rover geometry (meters)
WHEEL_RADIUS = 0.25          # 250mm radius Ti mesh wheel
WHEEL_SEPARATION = 1.75      # Track width (left-right)
WHEELBASE = 0.95             # Front-rear axle distance
BOGIE_OFFSET = 0.30          # Bogie pivot offset from mid-wheel axle

# Limits
MAX_WHEEL_SPEED_RAD_S = 2.0  # = 0.5 m/s at wheel
MAX_LINEAR_SPEED = 0.5       # m/s
MAX_ANGULAR_SPEED = 0.3      # rad/s
MAX_ANGULAR_ACCEL = 0.2      # rad/s²
MAX_LINEAR_ACCEL = 0.3       # m/s²

# Wheel index mapping
FL, ML, RL = 0, 1, 2         # Front-Left, Mid-Left, Rear-Left
FR, MR, RR = 3, 4, 5         # Front-Right, Mid-Right, Rear-Right
WHEEL_NAMES = ["FL", "ML", "RL", "FR", "MR", "RR"]
LEFT_WHEELS  = [FL, ML, RL]
RIGHT_WHEELS = [FR, MR, RR]


@dataclass
class WheelState:
    angular_velocity_rad_s: float = 0.0
    slip_ratio: float = 0.0
    encoder_angle_rad: float = 0.0
    torque_nm: float = 0.0


def euler_to_quat(roll: float, pitch: float, yaw: float) -> Quaternion:
    """Convert RPY (radians) to quaternion."""
    cy, sy = math.cos(yaw / 2), math.sin(yaw / 2)
    cp, sp = math.cos(pitch / 2), math.sin(pitch / 2)
    cr, sr = math.cos(roll / 2), math.sin(roll / 2)
    q = Quaternion()
    q.w = cr * cp * cy + sr * sp * sy
    q.x = sr * cp * cy - cr * sp * sy
    q.y = cr * sp * cy + sr * cp * sy
    q.z = cr * cp * sy - sr * sp * cy
    return q


class WheelControlNode(LifecycleNode):
    """Rocker-bogie wheel control lifecycle node."""

    def __init__(self) -> None:
        super().__init__("wheel_control_node")
        self._wheel_states = [WheelState() for _ in range(6)]
        self._slip_predictions = [0.0] * 6
        self._cmd_linear = 0.0
        self._cmd_angular = 0.0
        self._actual_linear = 0.0
        self._actual_angular = 0.0
        # Odometry state
        self._x = 0.0
        self._y = 0.0
        self._yaw = 0.0
        self._last_odom_time = time.monotonic()
        # Velocity smoothing
        self._vel_linear_cmd = 0.0
        self._vel_angular_cmd = 0.0
        self._last_cmd_time = time.monotonic()

    def on_configure(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Configuring wheel control node")

        self._pub_wheel_velocities = self.create_lifecycle_publisher(
            Float64MultiArray, "/wheel_velocities", SENSOR_QOS
        )
        self._pub_odometry = self.create_lifecycle_publisher(
            Odometry, "/wheel_control/odometry", RELIABLE_QOS
        )
        self._pub_slip_status = self.create_lifecycle_publisher(
            Float64MultiArray, "/wheel_control/slip_status", SENSOR_QOS
        )
        self._pub_joint_states = self.create_lifecycle_publisher(
            JointState, "/joint_states", SENSOR_QOS
        )

        self._sub_cmd_vel = self.create_subscription(
            Twist, "/cmd_vel", self._cb_cmd_vel, RELIABLE_QOS
        )
        self._sub_slip = self.create_subscription(
            Float64MultiArray, "/wheel_slip_predictions",
            self._cb_slip_predictions, SENSOR_QOS,
        )
        self._sub_encoders = self.create_subscription(
            Float64MultiArray, "/wheel_encoders",
            self._cb_encoders, SENSOR_QOS,
        )

        self.declare_parameter("max_linear_speed_m_s", MAX_LINEAR_SPEED)
        self.declare_parameter("max_angular_speed_rad_s", MAX_ANGULAR_SPEED)
        self.declare_parameter("traction_control_enabled", True)
        self.declare_parameter("slip_limit", 0.35)
        self.declare_parameter("control_hz", 20.0)
        self.declare_parameter("odom_hz", 50.0)

        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        hz = self.get_parameter("control_hz").value
        odom_hz = self.get_parameter("odom_hz").value
        self._timer_control = self.create_timer(1.0 / hz, self._control_loop)
        self._timer_odom = self.create_timer(1.0 / odom_hz, self._publish_odometry)
        self._last_odom_time = time.monotonic()
        return TransitionCallbackReturn.SUCCESS

    def on_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self._timer_control.cancel()
        self._timer_odom.cancel()
        # Send zero velocities on deactivation
        self._send_wheel_velocities([0.0] * 6)
        return TransitionCallbackReturn.SUCCESS

    def on_cleanup(self, state: LifecycleState) -> TransitionCallbackReturn:
        return TransitionCallbackReturn.SUCCESS

    def _cb_cmd_vel(self, msg: Twist) -> None:
        max_lin = self.get_parameter("max_linear_speed_m_s").value
        max_ang = self.get_parameter("max_angular_speed_rad_s").value
        self._vel_linear_cmd = max(-max_lin, min(max_lin, msg.linear.x))
        self._vel_angular_cmd = max(-max_ang, min(max_ang, msg.angular.z))
        self._last_cmd_time = time.monotonic()

    def _cb_slip_predictions(self, msg: Float64MultiArray) -> None:
        if len(msg.data) >= 6:
            self._slip_predictions = list(msg.data[:6])

    def _cb_encoders(self, msg: Float64MultiArray) -> None:
        if len(msg.data) >= 6:
            for i in range(6):
                self._wheel_states[i].angular_velocity_rad_s = msg.data[i]

    def _control_loop(self) -> None:
        now = time.monotonic()
        # Command timeout — zero velocities if no cmd_vel for 1s
        if now - self._last_cmd_time > 1.0:
            self._vel_linear_cmd = 0.0
            self._vel_angular_cmd = 0.0

        # Smooth velocity commands (rate limiting)
        dt = 1.0 / self.get_parameter("control_hz").value
        self._cmd_linear = self._rate_limit(
            self._cmd_linear, self._vel_linear_cmd, MAX_LINEAR_ACCEL, dt
        )
        self._cmd_angular = self._rate_limit(
            self._cmd_angular, self._vel_angular_cmd, MAX_ANGULAR_ACCEL, dt
        )

        wheel_velocities = self._compute_wheel_velocities(
            self._cmd_linear, self._cmd_angular
        )

        if self.get_parameter("traction_control_enabled").value:
            wheel_velocities = self._apply_traction_control(wheel_velocities)

        self._send_wheel_velocities(wheel_velocities)

    @staticmethod
    def _rate_limit(current: float, target: float, max_rate: float, dt: float) -> float:
        delta = target - current
        max_delta = max_rate * dt
        return current + max(-max_delta, min(max_delta, delta))

    def _compute_wheel_velocities(
        self, linear: float, angular: float
    ) -> list[float]:
        """
        Differential drive inverse kinematics for 6-wheel rover.
        Mid-wheels (passive) set to average of front/rear on each side.
        Rocker-bogie: outer wheels steer by speed difference.
        """
        v_left  = linear - angular * WHEEL_SEPARATION / 2.0
        v_right = linear + angular * WHEEL_SEPARATION / 2.0

        # Convert body speed to wheel angular velocity (rad/s)
        omega_left  = v_left  / WHEEL_RADIUS
        omega_right = v_right / WHEEL_RADIUS

        # 6-wheel assignment: all left wheels same speed, all right same
        velocities = [0.0] * 6
        for i in LEFT_WHEELS:
            velocities[i] = omega_left
        for i in RIGHT_WHEELS:
            velocities[i] = omega_right

        # Clip to hardware limits
        return [max(-MAX_WHEEL_SPEED_RAD_S, min(MAX_WHEEL_SPEED_RAD_S, v))
                for v in velocities]

    def _apply_traction_control(self, velocities: list[float]) -> list[float]:
        """
        Reduce wheel speed if slip ratio exceeds threshold.
        Uses ONNX-predicted slip ratios for proactive control.
        """
        slip_limit = self.get_parameter("slip_limit").value
        corrected = list(velocities)

        for i, (v, slip) in enumerate(zip(velocities, self._slip_predictions)):
            if abs(slip) > slip_limit:
                # Reduce speed proportional to excess slip
                scale = slip_limit / max(abs(slip), 1e-6)
                corrected[i] = v * scale
                self.get_logger().debug(
                    f"Wheel {WHEEL_NAMES[i]} traction correction: "
                    f"slip={slip:.3f} → scale={scale:.2f}"
                )
        return corrected

    def _send_wheel_velocities(self, velocities: list[float]) -> None:
        msg = Float64MultiArray()
        msg.data = velocities
        self._pub_wheel_velocities.publish(msg)

        # Update slip status
        slip_msg = Float64MultiArray()
        slip_msg.data = self._slip_predictions
        self._pub_slip_status.publish(slip_msg)

    def _publish_odometry(self) -> None:
        now = time.monotonic()
        dt = now - self._last_odom_time
        self._last_odom_time = now

        # Dead-reckoning integration
        v_left  = sum(self._wheel_states[i].angular_velocity_rad_s
                      for i in LEFT_WHEELS) / 3.0 * WHEEL_RADIUS
        v_right = sum(self._wheel_states[i].angular_velocity_rad_s
                      for i in RIGHT_WHEELS) / 3.0 * WHEEL_RADIUS

        linear  = (v_left + v_right) / 2.0
        angular = (v_right - v_left) / WHEEL_SEPARATION

        self._x   += linear * math.cos(self._yaw) * dt
        self._y   += linear * math.sin(self._yaw) * dt
        self._yaw += angular * dt

        odom = Odometry()
        odom.header.stamp = self.get_clock().now().to_msg()
        odom.header.frame_id = "odom"
        odom.child_frame_id = "base_footprint"

        odom.pose.pose.position.x = self._x
        odom.pose.pose.position.y = self._y
        odom.pose.pose.position.z = 0.0
        odom.pose.pose.orientation = euler_to_quat(0.0, 0.0, self._yaw)

        odom.twist.twist.linear.x  = linear
        odom.twist.twist.angular.z = angular

        # Diagonal covariance (dead-reckoning degrades over time in lunar regolith)
        odom.pose.covariance[0]  = 0.01   # x variance (m²)
        odom.pose.covariance[7]  = 0.01   # y variance
        odom.pose.covariance[35] = 0.005  # yaw variance (rad²)

        self._pub_odometry.publish(odom)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = WheelControlNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
