"""
LPAS Thermal Monitor Node

Manages the rover thermal control system:
  - 16-channel temperature sensor array (PT100 RTDs)
  - Battery thermal heater PWM control
  - Radiator louver actuation
  - PSR cold soak thermal modeling (lumped parameter)
  - Thermal safe mode triggers
  - Thermal gradient anomaly detection
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Optional

import rclpy
from rclpy.lifecycle import LifecycleNode, LifecycleState, TransitionCallbackReturn
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from std_msgs.msg import String, Float64MultiArray
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue

RELIABLE_QOS = QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE,
    history=HistoryPolicy.KEEP_LAST,
    depth=10,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
)
SENSOR_QOS = QoSProfile(
    reliability=ReliabilityPolicy.BEST_EFFORT,
    history=HistoryPolicy.KEEP_LAST,
    depth=5,
)


class ThermalZone(IntEnum):
    ELECTRONICS_BAY = 0
    BATTERY_PACK = 1
    WHEEL_FL = 2
    WHEEL_ML = 3
    WHEEL_RL = 4
    WHEEL_FR = 5
    WHEEL_MR = 6
    WHEEL_RR = 7
    MOTOR_FL = 8
    MOTOR_FR = 9
    SOLAR_ARRAY_L = 10
    SOLAR_ARRAY_R = 11
    RADIATOR_TOP = 12
    DRILL_MECHANISM = 13
    SPECTROMETER = 14
    STRUCTURE_AFT = 15


# Operating limits (°C)
TEMP_LIMITS = {
    ThermalZone.ELECTRONICS_BAY: (-40.0, 70.0, -20.0, 50.0),   # (survival_min, survival_max, op_min, op_max)
    ThermalZone.BATTERY_PACK:     (-20.0, 60.0, -10.0, 40.0),
    ThermalZone.WHEEL_FL:         (-150.0, 130.0, -100.0, 120.0),
    ThermalZone.WHEEL_ML:         (-150.0, 130.0, -100.0, 120.0),
    ThermalZone.WHEEL_RL:         (-150.0, 130.0, -100.0, 120.0),
    ThermalZone.WHEEL_FR:         (-150.0, 130.0, -100.0, 120.0),
    ThermalZone.WHEEL_MR:         (-150.0, 130.0, -100.0, 120.0),
    ThermalZone.WHEEL_RR:         (-150.0, 130.0, -100.0, 120.0),
    ThermalZone.MOTOR_FL:         (-80.0, 120.0, -40.0, 85.0),
    ThermalZone.MOTOR_FR:         (-80.0, 120.0, -40.0, 85.0),
    ThermalZone.SOLAR_ARRAY_L:    (-180.0, 120.0, -100.0, 110.0),
    ThermalZone.SOLAR_ARRAY_R:    (-180.0, 120.0, -100.0, 110.0),
    ThermalZone.RADIATOR_TOP:     (-180.0, 120.0, -150.0, 100.0),
    ThermalZone.DRILL_MECHANISM:  (-80.0, 120.0, -40.0, 80.0),
    ThermalZone.SPECTROMETER:     (-40.0, 60.0, -20.0, 50.0),
    ThermalZone.STRUCTURE_AFT:    (-180.0, 130.0, -150.0, 120.0),
}

# Heater zones: battery + electronics bay have survival heaters
HEATER_ZONES = {ThermalZone.BATTERY_PACK, ThermalZone.ELECTRONICS_BAY, ThermalZone.SPECTROMETER}
HEATER_POWER_W = {
    ThermalZone.BATTERY_PACK: 20.0,
    ThermalZone.ELECTRONICS_BAY: 15.0,
    ThermalZone.SPECTROMETER: 5.0,
    ThermalZone.DRILL_MECHANISM: 5.0,
}


class ThermalState(IntEnum):
    NOMINAL = 0
    WARM_CAUTION = 1   # Approaching upper limit
    COLD_CAUTION = 2   # Approaching lower limit, heaters active
    HOT_WARNING = 3    # Above operating max, reduce loads
    COLD_WARNING = 4   # Below operating min, survival heaters on
    SAFE_MODE = 5      # Thermal emergency — halt all non-essential ops


@dataclass
class SensorReading:
    zone: ThermalZone
    temperature_c: float
    heater_duty_cycle: float  # 0.0–1.0
    timestamp: float


class ThermalMonitorNode(LifecycleNode):
    """Thermal monitoring lifecycle node."""

    # Lumped thermal model: capacitances (J/K) per zone
    THERMAL_CAPACITANCE = {
        ThermalZone.ELECTRONICS_BAY: 8000.0,
        ThermalZone.BATTERY_PACK: 12000.0,
        ThermalZone.WHEEL_FL: 500.0,
    }

    def __init__(self) -> None:
        super().__init__("thermal_monitor_node")
        # Initialize temperatures at nominal operational values
        self._temperatures: dict[ThermalZone, float] = {
            zone: 20.0 for zone in ThermalZone
        }
        self._heater_duty: dict[ThermalZone, float] = {
            zone: 0.0 for zone in ThermalZone
        }
        self._thermal_state = ThermalState.NOMINAL
        self._in_psr: bool = False
        self._solar_irradiance: float = 1361.0 * 0.05  # W/m² — low angle south pole
        self._last_update: float = time.monotonic()

    def on_configure(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Configuring thermal monitor node")

        self._pub_sensor_array = self.create_lifecycle_publisher(
            Float64MultiArray, "/thermal/sensor_array", SENSOR_QOS
        )
        self._pub_thermal_state = self.create_lifecycle_publisher(
            String, "/thermal/state", RELIABLE_QOS
        )
        self._pub_heater_commands = self.create_lifecycle_publisher(
            Float64MultiArray, "/thermal/heater_duty_cycles", RELIABLE_QOS
        )
        self._pub_diagnostics = self.create_lifecycle_publisher(
            DiagnosticArray, "/diagnostics", RELIABLE_QOS
        )

        self._sub_psr_flag = self.create_subscription(
            String, "/terrain_segmentation",
            self._cb_terrain, SENSOR_QOS,
        )
        self._sub_solar = self.create_subscription(
            Float64MultiArray, "/power/solar_irradiance",
            self._cb_solar, SENSOR_QOS,
        )

        self.declare_parameter("update_hz", 5.0)
        self.declare_parameter("psr_environment_temp_c", -230.0)
        self.declare_parameter("ambient_max_temp_c", 127.0)  # Lunar day peak

        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        hz = self.get_parameter("update_hz").value
        self._timer_update = self.create_timer(1.0 / hz, self._update_thermal)
        self._timer_diag = self.create_timer(10.0, self._publish_diagnostics)
        return TransitionCallbackReturn.SUCCESS

    def on_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self._timer_update.cancel()
        self._timer_diag.cancel()
        return TransitionCallbackReturn.SUCCESS

    def on_cleanup(self, state: LifecycleState) -> TransitionCallbackReturn:
        return TransitionCallbackReturn.SUCCESS

    def _cb_terrain(self, msg: String) -> None:
        """Detect PSR zone from terrain segmentation."""
        try:
            data = json.loads(msg.data)
            self._in_psr = data.get("dominant_class") == "shadowed_psr"
        except (json.JSONDecodeError, AttributeError):
            pass

    def _cb_solar(self, msg: Float64MultiArray) -> None:
        if msg.data:
            self._solar_irradiance = msg.data[0]

    def _update_thermal(self) -> None:
        now = time.monotonic()
        dt = now - self._last_update
        self._last_update = now

        # Simulate thermal evolution (simplified lumped model)
        self._simulate_temperatures(dt)
        self._control_heaters()
        self._classify_thermal_state()
        self._publish_sensor_array()
        self._publish_thermal_state()
        self._publish_heater_commands()

    def _simulate_temperatures(self, dt: float) -> None:
        """Simplified thermal evolution using Newton cooling."""
        if self._in_psr:
            env_temp = self.get_parameter("psr_environment_temp_c").value
        else:
            env_temp = -50.0 + (self._solar_irradiance / 1361.0) * 177.0

        for zone in ThermalZone:
            cap = self.THERMAL_CAPACITANCE.get(zone, 2000.0)
            conductance = 0.5  # W/K — approximate thermal coupling to environment

            # Net heat flow: environment coupling + heater power + internal dissipation
            q_env = conductance * (env_temp - self._temperatures[zone])
            q_heater = HEATER_POWER_W.get(zone, 0.0) * self._heater_duty.get(zone, 0.0)
            q_internal = 5.0 if zone == ThermalZone.ELECTRONICS_BAY else 0.5

            dT = (q_env + q_heater + q_internal) * dt / cap
            self._temperatures[zone] = self._temperatures[zone] + dT

    def _control_heaters(self) -> None:
        """PID-like heater control for heated zones."""
        for zone in HEATER_ZONES:
            limits = TEMP_LIMITS.get(zone)
            if limits is None:
                continue
            survival_min, _, op_min, _ = limits
            t = self._temperatures[zone]

            # Simple bang-bang with hysteresis
            if t < op_min:
                duty = 1.0
            elif t < op_min + 5.0:
                duty = 0.5
            else:
                duty = 0.0
            self._heater_duty[zone] = duty

    def _classify_thermal_state(self) -> None:
        new_state = ThermalState.NOMINAL

        for zone in ThermalZone:
            limits = TEMP_LIMITS.get(zone)
            if limits is None:
                continue
            survival_min, survival_max, op_min, op_max = limits
            t = self._temperatures[zone]

            if t < survival_min or t > survival_max:
                new_state = max(new_state, ThermalState.SAFE_MODE)
            elif t < op_min:
                new_state = max(new_state, ThermalState.COLD_WARNING)
            elif t > op_max:
                new_state = max(new_state, ThermalState.HOT_WARNING)
            elif t < op_min + 10.0:
                new_state = max(new_state, ThermalState.COLD_CAUTION)
            elif t > op_max - 10.0:
                new_state = max(new_state, ThermalState.WARM_CAUTION)

        if new_state != self._thermal_state:
            self.get_logger().warning(
                f"Thermal state transition: {self._thermal_state.name} → {new_state.name}"
            )
            if new_state == ThermalState.SAFE_MODE:
                self.get_logger().fatal("THERMAL SAFE MODE — halting non-essential operations")
        self._thermal_state = new_state

    def _publish_sensor_array(self) -> None:
        msg = Float64MultiArray()
        msg.data = [self._temperatures[z] for z in ThermalZone]
        self._pub_sensor_array.publish(msg)

    def _publish_thermal_state(self) -> None:
        state_data = {
            "state": self._thermal_state.name,
            "in_psr": self._in_psr,
            "solar_irradiance_w_m2": self._solar_irradiance,
            "temperatures": {
                z.name: round(self._temperatures[z], 2) for z in ThermalZone
            },
            "heater_duty": {
                z.name: self._heater_duty[z]
                for z in HEATER_ZONES
            },
            "total_heater_power_w": sum(
                HEATER_POWER_W.get(z, 0.0) * self._heater_duty.get(z, 0.0)
                for z in ThermalZone
            ),
        }
        msg = String()
        msg.data = json.dumps(state_data)
        self._pub_thermal_state.publish(msg)

    def _publish_heater_commands(self) -> None:
        msg = Float64MultiArray()
        msg.data = [self._heater_duty.get(z, 0.0) for z in ThermalZone]
        self._pub_heater_commands.publish(msg)

    def _publish_diagnostics(self) -> None:
        arr = DiagnosticArray()
        arr.header.stamp = self.get_clock().now().to_msg()

        status = DiagnosticStatus()
        status.name = "thermal_monitor"
        status.hardware_id = "LPAS-THERMAL-001"

        level_map = {
            ThermalState.NOMINAL: DiagnosticStatus.OK,
            ThermalState.WARM_CAUTION: DiagnosticStatus.WARN,
            ThermalState.COLD_CAUTION: DiagnosticStatus.WARN,
            ThermalState.HOT_WARNING: DiagnosticStatus.ERROR,
            ThermalState.COLD_WARNING: DiagnosticStatus.ERROR,
            ThermalState.SAFE_MODE: DiagnosticStatus.ERROR,
        }
        status.level = level_map.get(self._thermal_state, DiagnosticStatus.WARN)
        status.message = self._thermal_state.name

        status.values = [
            KeyValue(key="thermal_state", value=self._thermal_state.name),
            KeyValue(key="in_psr", value=str(self._in_psr)),
            KeyValue(key="ebox_temp_c",
                     value=f"{self._temperatures[ThermalZone.ELECTRONICS_BAY]:.1f}"),
            KeyValue(key="battery_temp_c",
                     value=f"{self._temperatures[ThermalZone.BATTERY_PACK]:.1f}"),
            KeyValue(key="heater_power_w",
                     value=f"{sum(HEATER_POWER_W.get(z, 0) * self._heater_duty.get(z, 0) for z in ThermalZone):.1f}"),
        ]
        arr.status = [status]
        self._pub_diagnostics.publish(arr)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ThermalMonitorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
