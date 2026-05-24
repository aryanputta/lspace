# LPAS Science Payload Node — TRIDENT drill + NIRVSS spectrometer
from __future__ import annotations

import json
import time
import uuid
from enum import Enum, auto
from threading import Lock
from typing import Optional

import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.lifecycle import LifecycleNode, LifecycleState, TransitionCallbackReturn
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Float32, Int32, String

from lunar_scout_science_payload.action import DrillSample, RunSpectrometer

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

# TRIDENT drill constants
DRILL_MAX_DEPTH_M: float = 0.5
DRILL_RATE_M_S: float = 0.002

# NIRVSS spectrometer constants
SPEC_WAVELENGTHS: list[int] = list(range(400, 2501, 5))
SPEC_WARMUP_S: float = 30.0
SPEC_MIN_TEMP_C: float = -40.0

# Power interlock
SCIENCE_MIN_SOC: float = 40.0


class PayloadState(Enum):
    IDLE = auto()
    DRILL_EXTEND = auto()
    DRILL_ROTATE = auto()
    DRILL_RETRACT = auto()
    SPECTROMETER_WARM = auto()
    SPECTROMETER_ACQUIRE = auto()
    ANALYZING = auto()


class SciencePayloadNode(LifecycleNode):
    def __init__(self) -> None:
        super().__init__("science_payload_node")
        self._lock = Lock()
        self._state: PayloadState = PayloadState.IDLE
        self._current_depth_m: float = 0.0
        self._detector_temp_c: float = 20.0
        self._sample_count: int = 0
        self._soc_pct: float = 100.0
        self._power_state_raw: dict = {}
        self._drill_fault: bool = False
        self._cb_group = ReentrantCallbackGroup()

    # --- Lifecycle ---

    def on_configure(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Configuring science payload node")

        self._pub_drill_depth = self.create_lifecycle_publisher(
            Float32, "/science/drill_depth", SENSOR_QOS
        )
        self._pub_spec_temp = self.create_lifecycle_publisher(
            Float32, "/science/spectrometer_temp", SENSOR_QOS
        )
        self._pub_sample_count = self.create_lifecycle_publisher(
            Int32, "/science/sample_count", RELIABLE_QOS
        )

        self._sub_power = self.create_subscription(
            String, "/power/state", self._cb_power_state, RELIABLE_QOS
        )

        self._action_drill = ActionServer(
            self,
            DrillSample,
            "drill_sample",
            execute_callback=self._execute_drill,
            goal_callback=self._goal_cb,
            cancel_callback=self._cancel_cb,
            callback_group=self._cb_group,
        )
        self._action_spec = ActionServer(
            self,
            RunSpectrometer,
            "run_spectrometer",
            execute_callback=self._execute_spectrometer,
            goal_callback=self._goal_cb,
            cancel_callback=self._cancel_cb,
            callback_group=self._cb_group,
        )

        self.declare_parameter("drill_max_depth_m", DRILL_MAX_DEPTH_M)
        self.declare_parameter("drill_rate_m_s", DRILL_RATE_M_S)
        self.declare_parameter("spec_warmup_s", SPEC_WARMUP_S)
        self.declare_parameter("science_min_soc_pct", SCIENCE_MIN_SOC)
        self.declare_parameter("telemetry_hz", 2.0)

        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        hz = self.get_parameter("telemetry_hz").value
        self._timer_telemetry = self.create_timer(1.0 / hz, self._publish_telemetry)
        self.get_logger().info("Science payload node active")
        return TransitionCallbackReturn.SUCCESS

    def on_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self._timer_telemetry.cancel()
        if self._state in (PayloadState.DRILL_EXTEND, PayloadState.DRILL_ROTATE):
            self._auto_retract_drill()
        return TransitionCallbackReturn.SUCCESS

    def on_cleanup(self, state: LifecycleState) -> TransitionCallbackReturn:
        self._state = PayloadState.IDLE
        self._current_depth_m = 0.0
        self._drill_fault = False
        return TransitionCallbackReturn.SUCCESS

    # --- Subscribers ---

    def _cb_power_state(self, msg: String) -> None:
        try:
            data = json.loads(msg.data)
            with self._lock:
                self._soc_pct = float(data.get("soc_pct", 100.0))
                self._power_state_raw = data
        except (json.JSONDecodeError, ValueError) as exc:
            self.get_logger().warn(f"Failed to parse power state: {exc}")

    # --- Action callbacks ---

    def _goal_cb(self, goal_request) -> GoalResponse:
        return GoalResponse.ACCEPT

    def _cancel_cb(self, goal_handle) -> CancelResponse:
        return CancelResponse.ACCEPT

    # --- Drill action ---

    async def _execute_drill(self, goal_handle) -> DrillSample.Result:
        result = DrillSample.Result()
        feedback = DrillSample.Feedback()

        target_depth = min(
            float(goal_handle.request.target_depth_m),
            self.get_parameter("drill_max_depth_m").value,
        )
        location_id: str = goal_handle.request.sample_location_id

        with self._lock:
            if self._soc_pct < self.get_parameter("science_min_soc_pct").value:
                self.get_logger().warn(
                    f"Drill denied — SOC {self._soc_pct:.1f}% < {SCIENCE_MIN_SOC}%"
                )
                goal_handle.abort()
                result.success = False
                result.status_message = f"Insufficient power: SOC={self._soc_pct:.1f}%"
                return result

            if self._state != PayloadState.IDLE:
                goal_handle.abort()
                result.success = False
                result.status_message = f"Payload busy: {self._state.name}"
                return result

            self._state = PayloadState.DRILL_EXTEND
            self._drill_fault = False

        self.get_logger().info(
            f"Drill starting: target={target_depth:.3f}m loc={location_id}"
        )

        drill_rate = self.get_parameter("drill_rate_m_s").value

        # DRILL_EXTEND phase
        with self._lock:
            self._state = PayloadState.DRILL_EXTEND
        feedback.phase = "DRILL_EXTEND"
        feedback.current_depth_m = 0.0
        feedback.drill_torque_nm = 0.0
        goal_handle.publish_feedback(feedback)
        time.sleep(2.0)

        # DRILL_ROTATE phase — drive to target depth
        with self._lock:
            self._state = PayloadState.DRILL_ROTATE

        step_s = 0.5
        depth_step = drill_rate * step_s

        while True:
            if goal_handle.is_cancel_requested:
                self.get_logger().info("Drill cancelled — retracting")
                break

            with self._lock:
                if self._drill_fault:
                    self.get_logger().error("Drill fault detected — auto-retracting")
                    break
                self._current_depth_m = min(
                    self._current_depth_m + depth_step, target_depth
                )
                current = self._current_depth_m

            # Simulated torque increases with depth (regolith compaction model)
            torque = 0.5 + current * 8.0

            feedback.phase = "DRILL_ROTATE"
            feedback.current_depth_m = current
            feedback.drill_torque_nm = torque
            goal_handle.publish_feedback(feedback)

            if current >= target_depth:
                break

            time.sleep(step_s)

        # DRILL_RETRACT phase
        with self._lock:
            self._state = PayloadState.DRILL_RETRACT
            final_depth = self._current_depth_m

        feedback.phase = "DRILL_RETRACT"
        feedback.current_depth_m = final_depth
        feedback.drill_torque_nm = 0.0
        goal_handle.publish_feedback(feedback)
        time.sleep(3.0)

        # Retract complete
        with self._lock:
            self._current_depth_m = 0.0
            self._state = PayloadState.IDLE

        if goal_handle.is_cancel_requested:
            goal_handle.canceled()
            result.success = False
            result.status_message = "Cancelled and retracted"
            result.final_depth_m = final_depth
            return result

        sample_id = f"DRILL-{location_id}-{uuid.uuid4().hex[:8].upper()}"
        with self._lock:
            self._sample_count += 1

        goal_handle.succeed()
        result.success = True
        result.sample_id = sample_id
        result.final_depth_m = final_depth
        result.status_message = f"Sample acquired at {final_depth:.3f}m"
        self.get_logger().info(f"Drill complete: {sample_id}")
        return result

    # --- Spectrometer action ---

    async def _execute_spectrometer(self, goal_handle) -> RunSpectrometer.Result:
        result = RunSpectrometer.Result()
        feedback = RunSpectrometer.Feedback()

        integration_s = float(goal_handle.request.integration_time_s)
        wl_min = float(goal_handle.request.wavelength_min_nm)
        wl_max = float(goal_handle.request.wavelength_max_nm)
        sample_id: str = goal_handle.request.sample_id

        with self._lock:
            if self._soc_pct < self.get_parameter("science_min_soc_pct").value:
                self.get_logger().warn(
                    f"Spectrometer denied — SOC {self._soc_pct:.1f}% < {SCIENCE_MIN_SOC}%"
                )
                goal_handle.abort()
                result.success = False
                result.calibration_status = f"Insufficient power: SOC={self._soc_pct:.1f}%"
                return result

            if self._detector_temp_c < SPEC_MIN_TEMP_C:
                goal_handle.abort()
                result.success = False
                result.calibration_status = (
                    f"Detector too cold: {self._detector_temp_c:.1f}°C < {SPEC_MIN_TEMP_C}°C"
                )
                return result

            if self._state != PayloadState.IDLE:
                goal_handle.abort()
                result.success = False
                result.calibration_status = f"Payload busy: {self._state.name}"
                return result

            self._state = PayloadState.SPECTROMETER_WARM

        self.get_logger().info(
            f"Spectrometer starting: int={integration_s:.1f}s "
            f"wl=[{wl_min:.0f},{wl_max:.0f}]nm sample={sample_id}"
        )

        warmup_s = self.get_parameter("spec_warmup_s").value

        # SPECTROMETER_WARM phase
        warmup_steps = 10
        for i in range(warmup_steps):
            if goal_handle.is_cancel_requested:
                with self._lock:
                    self._state = PayloadState.IDLE
                goal_handle.canceled()
                result.success = False
                result.calibration_status = "Cancelled during warmup"
                return result

            pct = float(i) / warmup_steps * 40.0
            with self._lock:
                temp = self._detector_temp_c

            feedback.phase = "SPECTROMETER_WARM"
            feedback.progress_pct = pct
            feedback.detector_temp_c = temp
            goal_handle.publish_feedback(feedback)
            time.sleep(warmup_s / warmup_steps)

        # SPECTROMETER_ACQUIRE phase
        with self._lock:
            self._state = PayloadState.SPECTROMETER_ACQUIRE

        acquire_steps = 20
        for i in range(acquire_steps):
            if goal_handle.is_cancel_requested:
                with self._lock:
                    self._state = PayloadState.IDLE
                goal_handle.canceled()
                result.success = False
                result.calibration_status = "Cancelled during acquisition"
                return result

            pct = 40.0 + float(i) / acquire_steps * 50.0
            with self._lock:
                temp = self._detector_temp_c

            feedback.phase = "SPECTROMETER_ACQUIRE"
            feedback.progress_pct = pct
            feedback.detector_temp_c = temp
            goal_handle.publish_feedback(feedback)
            time.sleep(integration_s / acquire_steps)

        # ANALYZING phase
        with self._lock:
            self._state = PayloadState.ANALYZING
            temp = self._detector_temp_c

        feedback.phase = "ANALYZING"
        feedback.progress_pct = 90.0
        feedback.detector_temp_c = temp
        goal_handle.publish_feedback(feedback)
        time.sleep(1.0)

        # Build wavelength axis filtered to requested range
        wavelength_axis = [
            float(w) for w in SPEC_WAVELENGTHS if wl_min <= w <= wl_max
        ]
        # Synthetic spectrum: blackbody-like + noise placeholder
        spectrum_data = [
            1000.0 / (1.0 + ((w - 1500.0) / 500.0) ** 2) + 5.0
            for w in wavelength_axis
        ]

        with self._lock:
            self._state = PayloadState.IDLE
            self._sample_count += 1

        feedback.phase = "COMPLETE"
        feedback.progress_pct = 100.0
        feedback.detector_temp_c = temp
        goal_handle.publish_feedback(feedback)

        goal_handle.succeed()
        result.success = True
        result.spectrum_data = spectrum_data
        result.wavelength_axis_nm = wavelength_axis
        result.detector_temp_c = temp
        result.calibration_status = "NOMINAL"
        self.get_logger().info(
            f"Spectrometer complete: {len(spectrum_data)} channels, sample={sample_id}"
        )
        return result

    # --- Safety ---

    def _auto_retract_drill(self) -> None:
        self.get_logger().error("AUTO-RETRACT: drill fault or deactivation")
        with self._lock:
            self._drill_fault = True
            self._current_depth_m = 0.0
            self._state = PayloadState.IDLE

    # --- Telemetry ---

    def _publish_telemetry(self) -> None:
        with self._lock:
            depth = self._current_depth_m
            temp = self._detector_temp_c
            count = self._sample_count

        depth_msg = Float32()
        depth_msg.data = depth
        self._pub_drill_depth.publish(depth_msg)

        temp_msg = Float32()
        temp_msg.data = temp
        self._pub_spec_temp.publish(temp_msg)

        count_msg = Int32()
        count_msg.data = count
        self._pub_sample_count.publish(count_msg)


def main(args: Optional[list[str]] = None) -> None:
    rclpy.init(args=args)
    executor = rclpy.executors.MultiThreadedExecutor()
    node = SciencePayloadNode()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
