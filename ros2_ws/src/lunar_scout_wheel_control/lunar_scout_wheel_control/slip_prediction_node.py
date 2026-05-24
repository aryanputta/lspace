# LPAS Slip Prediction Node — MC-Dropout MLP, per-wheel slip ratio estimation
from __future__ import annotations

import math
import time
from collections import deque
from typing import Optional

import numpy as np
import rclpy
from rclpy.lifecycle import LifecycleNode, LifecycleState, TransitionCallbackReturn
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Imu
from std_msgs.msg import Float32MultiArray, String

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

WINDOW_SIZE: int = 50
MC_PASSES: int = 10
SLIP_WARN: float = 0.3
SLIP_CRIT: float = 0.6
N_WHEELS: int = 6
EVENT_BUFFER: int = 200

# MLP architecture: input=5, hidden=[32,16], output=1
_RNG = np.random.default_rng(42)

def _init_weights() -> dict[str, np.ndarray]:
    w: dict[str, np.ndarray] = {}
    w["W1"] = _RNG.standard_normal((5, 32)).astype(np.float32) * 0.1
    w["b1"] = np.zeros(32, dtype=np.float32)
    w["W2"] = _RNG.standard_normal((32, 16)).astype(np.float32) * 0.1
    w["b2"] = np.zeros(16, dtype=np.float32)
    w["W3"] = _RNG.standard_normal((16, 1)).astype(np.float32) * 0.1
    w["b3"] = np.zeros(1, dtype=np.float32)
    return w


def _relu(x: np.ndarray) -> np.ndarray:
    return np.maximum(0.0, x)


def _mlp_forward(
    x: np.ndarray,
    weights: dict[str, np.ndarray],
    dropout_p: float = 0.0,
    rng: Optional[np.random.Generator] = None,
) -> float:
    if rng is None:
        rng = np.random.default_rng()

    h1 = _relu(x @ weights["W1"] + weights["b1"])
    if dropout_p > 0.0:
        mask1 = (rng.random(h1.shape) > dropout_p).astype(np.float32)
        h1 = h1 * mask1 / (1.0 - dropout_p)

    h2 = _relu(h1 @ weights["W2"] + weights["b2"])
    if dropout_p > 0.0:
        mask2 = (rng.random(h2.shape) > dropout_p).astype(np.float32)
        h2 = h2 * mask2 / (1.0 - dropout_p)

    out = h2 @ weights["W3"] + weights["b3"]
    return float(np.clip(out[0], 0.0, 1.0))


class SlipPredictionNode(LifecycleNode):
    def __init__(self) -> None:
        super().__init__("slip_prediction_node")
        self._weights = _init_weights()
        self._mc_rng = np.random.default_rng(0)

        # Sliding window buffers
        self._accel_x_buf: deque[float] = deque(maxlen=WINDOW_SIZE)
        self._accel_z_buf: deque[float] = deque(maxlen=WINDOW_SIZE)
        self._wheel_vel_buf: deque[float] = deque(maxlen=WINDOW_SIZE)
        self._cmd_vel_buf: deque[float] = deque(maxlen=WINDOW_SIZE)
        self._pitch_buf: deque[float] = deque(maxlen=WINDOW_SIZE)

        # Latest values
        self._latest_accel_x: float = 0.0
        self._latest_accel_z: float = -1.62  # lunar gravity
        self._latest_wheel_vel: float = 0.0
        self._latest_cmd_vel: float = 0.0
        self._latest_pitch_deg: float = 0.0
        self._latest_body_vel: float = 0.0
        self._latest_wheel_vels: list[float] = [0.0] * N_WHEELS

        # Slip event history for trend analysis
        self._slip_events: deque[dict] = deque(maxlen=EVENT_BUFFER)

        # Current predictions
        self._slip_ratios: list[float] = [0.0] * N_WHEELS
        self._uncertainties: list[float] = [0.0] * N_WHEELS

    # --- Lifecycle ---

    def on_configure(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Configuring slip prediction node")

        self._pub_slip = self.create_lifecycle_publisher(
            Float32MultiArray, "/slip/prediction", SENSOR_QOS
        )
        self._pub_alert = self.create_lifecycle_publisher(
            String, "/slip/alert", RELIABLE_QOS
        )
        self._pub_uncertainty = self.create_lifecycle_publisher(
            Float32MultiArray, "/slip/uncertainty", SENSOR_QOS
        )
        self._pub_advisory = self.create_lifecycle_publisher(
            String, "/slip/traction_advisory", RELIABLE_QOS
        )

        self._sub_odom = self.create_subscription(
            Odometry, "/wheel_odom", self._cb_odom, SENSOR_QOS
        )
        self._sub_imu = self.create_subscription(
            Imu, "/imu/data", self._cb_imu, SENSOR_QOS
        )
        self._sub_cmd_vel = self.create_subscription(
            Twist, "/cmd_vel", self._cb_cmd_vel, RELIABLE_QOS
        )

        self.declare_parameter("publish_hz", 10.0)
        self.declare_parameter("slip_warn_threshold", SLIP_WARN)
        self.declare_parameter("slip_crit_threshold", SLIP_CRIT)
        self.declare_parameter("dropout_p", 0.1)

        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        hz = self.get_parameter("publish_hz").value
        self._timer = self.create_timer(1.0 / hz, self._inference_loop)
        return TransitionCallbackReturn.SUCCESS

    def on_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self._timer.cancel()
        return TransitionCallbackReturn.SUCCESS

    def on_cleanup(self, state: LifecycleState) -> TransitionCallbackReturn:
        self._slip_events.clear()
        for buf in (
            self._accel_x_buf, self._accel_z_buf,
            self._wheel_vel_buf, self._cmd_vel_buf, self._pitch_buf,
        ):
            buf.clear()
        return TransitionCallbackReturn.SUCCESS

    # --- Subscribers ---

    def _cb_odom(self, msg: Odometry) -> None:
        self._latest_body_vel = msg.twist.twist.linear.x
        # Approximate per-wheel velocity from body linear velocity
        # (wheel-specific encoders would override this via /wheel_encoders)
        self._latest_wheel_vels = [self._latest_body_vel] * N_WHEELS
        self._latest_wheel_vel = abs(self._latest_body_vel)
        self._wheel_vel_buf.append(self._latest_wheel_vel)

    def _cb_imu(self, msg: Imu) -> None:
        self._latest_accel_x = msg.linear_acceleration.x
        self._latest_accel_z = msg.linear_acceleration.z

        # Pitch from accelerometer (small-angle approximation)
        az = msg.linear_acceleration.z
        ax = msg.linear_acceleration.x
        g = math.sqrt(ax ** 2 + az ** 2) if (ax ** 2 + az ** 2) > 0 else 1.62
        pitch_rad = math.asin(max(-1.0, min(1.0, ax / g)))
        self._latest_pitch_deg = math.degrees(pitch_rad)

        self._accel_x_buf.append(self._latest_accel_x)
        self._accel_z_buf.append(self._latest_accel_z)
        self._pitch_buf.append(self._latest_pitch_deg)

    def _cb_cmd_vel(self, msg: Twist) -> None:
        self._latest_cmd_vel = msg.linear.x
        self._cmd_vel_buf.append(self._latest_cmd_vel)

    # --- Inference ---

    def _build_feature_vector(self) -> np.ndarray:
        accel_x = (
            float(np.mean(self._accel_x_buf)) if self._accel_x_buf
            else self._latest_accel_x
        )
        accel_z = (
            float(np.mean(self._accel_z_buf)) if self._accel_z_buf
            else self._latest_accel_z
        )
        wheel_vel = (
            float(np.mean(self._wheel_vel_buf)) if self._wheel_vel_buf
            else self._latest_wheel_vel
        )
        cmd_vel = (
            float(np.mean(self._cmd_vel_buf)) if self._cmd_vel_buf
            else self._latest_cmd_vel
        )
        pitch = (
            float(np.mean(self._pitch_buf)) if self._pitch_buf
            else self._latest_pitch_deg
        )
        return np.array([accel_x, accel_z, wheel_vel, cmd_vel, pitch], dtype=np.float32)

    def _mc_dropout_predict(self, features: np.ndarray) -> tuple[float, float]:
        dropout_p = self.get_parameter("dropout_p").value
        preds = [
            _mlp_forward(features, self._weights, dropout_p=dropout_p, rng=self._mc_rng)
            for _ in range(MC_PASSES)
        ]
        return float(np.mean(preds)), float(np.std(preds))

    def _compute_slip_ratio(self, v_wheel: float, v_body: float) -> float:
        denom = max(abs(v_wheel), 0.01)
        return abs(v_wheel - v_body) / denom

    def _inference_loop(self) -> None:
        features = self._build_feature_vector()
        mean_slip, uncertainty = self._mc_dropout_predict(features)

        warn_thr = self.get_parameter("slip_warn_threshold").value
        crit_thr = self.get_parameter("slip_crit_threshold").value

        slip_ratios: list[float] = []
        uncertainties: list[float] = []

        for i in range(N_WHEELS):
            v_wheel = self._latest_wheel_vels[i]
            v_body = self._latest_body_vel
            kinematic_slip = self._compute_slip_ratio(v_wheel, v_body)

            # Blend kinematic slip with ML prediction
            blended = 0.6 * kinematic_slip + 0.4 * mean_slip
            slip_ratios.append(round(blended, 4))
            uncertainties.append(round(uncertainty, 4))

        self._slip_ratios = slip_ratios
        self._uncertainties = uncertainties

        # Alerts
        max_slip = max(slip_ratios)
        critical_wheels = [i for i, s in enumerate(slip_ratios) if s > crit_thr]
        warn_wheels = [i for i, s in enumerate(slip_ratios) if warn_thr < s <= crit_thr]

        alert_level = "NOMINAL"
        if critical_wheels:
            alert_level = f"CRITICAL wheels={critical_wheels} slip={max_slip:.3f}"
        elif warn_wheels:
            alert_level = f"WARNING wheels={warn_wheels} slip={max_slip:.3f}"

        # Traction advisory
        if critical_wheels:
            advisory = "STOP"
        elif warn_wheels:
            advisory = "REDUCE_SPEED"
        else:
            advisory = "NORMAL"

        # Record slip events above warning
        if max_slip > warn_thr:
            self._slip_events.append({
                "t": time.monotonic(),
                "slip": max_slip,
                "level": advisory,
            })

        # Publish
        slip_msg = Float32MultiArray()
        slip_msg.data = [float(s) for s in slip_ratios]
        self._pub_slip.publish(slip_msg)

        unc_msg = Float32MultiArray()
        unc_msg.data = [float(u) for u in uncertainties]
        self._pub_uncertainty.publish(unc_msg)

        alert_msg = String()
        alert_msg.data = alert_level
        self._pub_alert.publish(alert_msg)

        advisory_msg = String()
        advisory_msg.data = advisory
        self._pub_advisory.publish(advisory_msg)

        if critical_wheels:
            self.get_logger().warn(f"Slip CRITICAL: {alert_level}")

    def get_slip_trend(self) -> str:
        if len(self._slip_events) < 5:
            return "INSUFFICIENT_DATA"
        recent = list(self._slip_events)[-5:]
        avg = sum(e["slip"] for e in recent) / len(recent)
        if avg > SLIP_CRIT:
            return "DETERIORATING"
        if avg > SLIP_WARN:
            return "ELEVATED"
        return "STABLE"


def main(args: Optional[list[str]] = None) -> None:
    rclpy.init(args=args)
    node = SlipPredictionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
