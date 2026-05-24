#!/usr/bin/env python3
"""
Lunar PSR Autonomy Scout - Power Management Node
=================================================
Full power budget tracking for a NASA-grade lunar rover.

Hardware Model:
  - Solar: 4x 50W panels = 200W peak (GaAs triple-junction, 30% efficiency)
  - Battery: 2x 75Wh Li-Ion cells = 150Wh total (at 25°C)
  - Battery voltage: 28V nominal (24V-33.6V range)
  - Battery chemistry: 18650-type cells in 7S2P configuration

Power Budget (nominal traverse):
  - Drive motors: 6x @ 8W avg = 48W
  - Computers (avionics + science): 20W + 15W = 35W
  - Communications (UHF + HGA): 12W + 25W = 37W
  - Thermal heaters: 0-30W (variable)
  - Science payload: 0-25W (when active)
  - Margin: 10W
  - Total peak: ~185W

Load Shedding Priority (higher number = shed first):
  Priority 1 (never shed): Safety-critical, thermal heaters
  Priority 2: Core avionics, comms minimum
  Priority 3: Navigation, mobility
  Priority 4: Science cameras
  Priority 5: Science payload (drill, spectrometer)
  Priority 6: Non-essential heaters, extra lighting

Author: Lunar Scout Engineering Team
"""

from __future__ import annotations

import json
import math
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple

import numpy as np

import rclpy
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup, ReentrantCallbackGroup
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy

from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from sensor_msgs.msg import BatteryState
from std_msgs.msg import Bool, Float32, Header, String
from std_srvs.srv import SetBool, Trigger

# ---------------------------------------------------------------------------
# QoS
# ---------------------------------------------------------------------------
RELIABLE_QOS = QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
    history=HistoryPolicy.KEEP_LAST,
    depth=10,
)

# ---------------------------------------------------------------------------
# CONSTANTS - Hardware spec
# ---------------------------------------------------------------------------
SOLAR_PEAK_W            = 200.0   # Peak solar output
BATTERY_CAPACITY_WH     = 150.0   # Nominal capacity at 25°C
BATTERY_VOLTAGE_NOMINAL = 28.0    # V
BATTERY_VOLTAGE_MIN     = 24.0    # V (5% SOC)
BATTERY_VOLTAGE_MAX     = 33.6    # V (100% SOC)
BATTERY_CAPACITY_AH     = BATTERY_CAPACITY_WH / BATTERY_VOLTAGE_NOMINAL  # ~5.36 Ah

# Temperature derating coefficients for Li-Ion
TEMP_DERATING_TABLE: List[Tuple[float, float]] = [
    (-40.0, 0.10),   # 10% capacity at -40°C (extreme cold soak)
    (-30.0, 0.25),   # 25% at -30°C
    (-20.0, 0.45),   # 45% at -20°C
    (-10.0, 0.65),   # 65% at -10°C
    (0.0,   0.80),   # 80% at 0°C
    (10.0,  0.90),   # 90% at 10°C
    (20.0,  0.97),   # 97% at 20°C
    (25.0,  1.00),   # 100% at 25°C (nominal)
    (40.0,  0.98),   # 98% at 40°C
    (60.0,  0.90),   # 90% at 60°C (aging accelerated)
]

# Battery internal resistance vs temperature (mΩ)
BATT_RESISTANCE_TABLE: List[Tuple[float, float]] = [
    (-40.0, 500.0),
    (-20.0, 200.0),
    (0.0,   80.0),
    (25.0,  30.0),
    (40.0,  25.0),
    (60.0,  35.0),
]

# Solar array incidence angle efficiency
SOLAR_ANGLE_DERATING: List[Tuple[float, float]] = [
    (0,   1.00),
    (30,  0.87),
    (45,  0.71),
    (60,  0.50),
    (80,  0.17),
    (90,  0.00),
]

# PSR illumination cycle (14.75 Earth days = 1 lunar day)
LUNAR_DAY_SEC = 14.75 * 24 * 3600


# ---------------------------------------------------------------------------
# DATA STRUCTURES
# ---------------------------------------------------------------------------
class PowerMode(Enum):
    """Rover power operating modes."""
    FULL_POWER      = auto()   # All systems nominal
    POWER_SAVE      = auto()   # Non-essential loads shed
    ECLIPSE_SURVIVE = auto()   # Minimum power for survival
    SAFE_MODE       = auto()   # Emergency: only safety-critical loads
    CHARGING        = auto()   # Stationary charging from solar


@dataclass
class PowerLoad:
    """Represents a single power consumer on the rover."""
    name: str
    subsystem: str
    power_w: float               # Nominal power draw in Watts
    priority: int                # 1 = critical, 6 = optional
    active: bool = True          # Currently powered
    dimmable: bool = False       # Can be reduced below nominal
    min_power_w: float = 0.0     # Minimum power if dimmable
    current_power_w: float = 0.0 # Current actual draw

    def __post_init__(self):
        self.current_power_w = self.power_w if self.active else 0.0


@dataclass
class BatteryCell:
    """Models a single battery cell (Li-Ion 7S2P)."""
    cell_id: int
    voltage_v: float = 4.2       # Full charge
    temp_c: float = 20.0
    soc_pct: float = 100.0
    capacity_wh: float = 75.0    # Per cell
    cycle_count: int = 0
    health_pct: float = 100.0    # Capacity fade


@dataclass
class SolarArray:
    """Models solar array power generation."""
    panel_id: str
    area_m2: float = 0.96        # 1.2m x 0.8m per panel
    efficiency: float = 0.30     # 30% GaAs triple-junction
    current_power_w: float = 0.0
    temperature_c: float = 50.0  # Solar panel operating temperature
    deployed: bool = False        # Stowed on launch, deployed on surface
    degradation_pct: float = 100.0  # Solar cell degradation over mission


@dataclass
class PowerBudgetReport:
    """Complete power budget snapshot."""
    timestamp: str
    mode: str
    solar_total_w: float
    battery_soc_pct: float
    battery_voltage_v: float
    battery_temp_c: float
    battery_capacity_available_wh: float
    total_load_w: float
    net_power_w: float           # solar - load (positive = charging)
    time_to_empty_min: float     # If net < 0
    time_to_full_min: float      # If net > 0
    load_breakdown: Dict[str, float]
    loads_shed: List[str]
    heater_pwm_pct: float
    eclipse_active: bool


# ---------------------------------------------------------------------------
# POWER MANAGEMENT NODE
# ---------------------------------------------------------------------------
class PowerManagementNode(Node):
    """
    Power management node for Lunar PSR Autonomy Scout.

    Models solar generation, battery state, and manages load shedding
    to ensure rover survival through lunar night.
    """

    def __init__(self) -> None:
        super().__init__("power_management")

        # ------------------------------------------------------------------
        # Hardware model initialization
        # ------------------------------------------------------------------
        self._lock = threading.Lock()

        # Battery cells (2 cells in pack)
        self.battery_cells: List[BatteryCell] = [
            BatteryCell(cell_id=0, voltage_v=4.2, temp_c=20.0, soc_pct=95.0, capacity_wh=75.0),
            BatteryCell(cell_id=1, voltage_v=4.2, temp_c=20.0, soc_pct=95.0, capacity_wh=75.0),
        ]

        # Solar array panels (2 deployable)
        self.solar_arrays: List[SolarArray] = [
            SolarArray("LEFT",  area_m2=0.96, efficiency=0.30),
            SolarArray("RIGHT", area_m2=0.96, efficiency=0.30),
        ]

        # Power loads registry
        self.loads: Dict[str, PowerLoad] = self._create_load_registry()

        # Operating state
        self.power_mode: PowerMode = PowerMode.FULL_POWER
        self.eclipse_active: bool = False
        self.solar_incidence_deg: float = 45.0   # Nominal incidence angle
        self.solar_irradiance_wm2: float = 1361.0  # Solar constant at 1 AU
        self.lunar_distance_factor: float = 1.0   # Lunar orbit correction

        # Thermal heater state
        self.heater_pwm_pct: float = 0.0          # 0-100%
        self.heater_target_temp_c: float = -20.0  # Minimum battery temp
        self.heater_power_w: float = 0.0

        # Simulation state
        self.sim_time_s: float = 0.0
        self.last_update_time: float = time.monotonic()
        self.shedding_active: bool = False
        self.shed_load_names: List[str] = []

        # Power consumption history (rolling 60-sample window)
        self.power_history: List[float] = [100.0] * 60  # Watts
        self.solar_history: List[float] = [150.0] * 60

        # Callback groups
        self._timer_cbg   = MutuallyExclusiveCallbackGroup()
        self._service_cbg = MutuallyExclusiveCallbackGroup()
        self._sub_cbg     = ReentrantCallbackGroup()

        # Declare parameters
        self._declare_parameters()

        # Create ROS interfaces
        self._create_publishers()
        self._create_subscribers()
        self._create_services()
        self._create_timers()

        self.get_logger().info(
            f"PowerManagementNode initialized - "
            f"Battery: {BATTERY_CAPACITY_WH}Wh, Solar: {SOLAR_PEAK_W}W peak"
        )

    # ------------------------------------------------------------------
    # LOAD REGISTRY
    # ------------------------------------------------------------------
    def _create_load_registry(self) -> Dict[str, PowerLoad]:
        """Create registry of all power consumers."""
        loads = {
            # Priority 1: Safety critical (never shed)
            "thermal_heaters":     PowerLoad("thermal_heaters",     "thermal",
                                              30.0, 1, dimmable=True, min_power_w=5.0),
            "fault_monitor":       PowerLoad("fault_monitor",       "safety",
                                              2.0,  1),
            "watchdog_cpu":        PowerLoad("watchdog_cpu",        "safety",
                                              1.0,  1),

            # Priority 2: Core avionics
            "main_computer":       PowerLoad("main_computer",       "avionics",
                                              15.0, 2),
            "imu":                 PowerLoad("imu",                 "sensors",
                                              1.5,  2),
            "uhf_comms_rx":        PowerLoad("uhf_comms_rx",        "comms",
                                              3.0,  2),

            # Priority 3: Navigation and mobility
            "motor_controllers":   PowerLoad("motor_controllers",   "mobility",
                                              5.0,  3),
            "drive_motors_fl":     PowerLoad("drive_motors_fl",     "mobility",
                                              8.0,  3, dimmable=True, min_power_w=2.0),
            "drive_motors_fr":     PowerLoad("drive_motors_fr",     "mobility",
                                              8.0,  3, dimmable=True, min_power_w=2.0),
            "drive_motors_ml":     PowerLoad("drive_motors_ml",     "mobility",
                                              8.0,  3, dimmable=True, min_power_w=2.0),
            "drive_motors_mr":     PowerLoad("drive_motors_mr",     "mobility",
                                              8.0,  3, dimmable=True, min_power_w=2.0),
            "drive_motors_rl":     PowerLoad("drive_motors_rl",     "mobility",
                                              8.0,  3, dimmable=True, min_power_w=2.0),
            "drive_motors_rr":     PowerLoad("drive_motors_rr",     "mobility",
                                              8.0,  3, dimmable=True, min_power_w=2.0),
            "nav_computer":        PowerLoad("nav_computer",        "navigation",
                                              10.0, 3),
            "lidar":               PowerLoad("lidar",               "sensors",
                                              8.0,  3),

            # Priority 4: Cameras and science instruments
            "nav_cameras":         PowerLoad("nav_cameras",         "sensors",
                                              4.0,  4),
            "hazard_cameras":      PowerLoad("hazard_cameras",      "sensors",
                                              2.0,  4),
            "uhf_comms_tx":        PowerLoad("uhf_comms_tx",        "comms",
                                              10.0, 4),
            "hga_comms":           PowerLoad("hga_comms",           "comms",
                                              25.0, 4),

            # Priority 5: Science payload
            "thermal_ir_camera":   PowerLoad("thermal_ir_camera",   "science",
                                              3.0,  5, active=False),
            "neutron_spectrometer":PowerLoad("neutron_spectrometer","science",
                                              8.0,  5, active=False),
            "science_computer":    PowerLoad("science_computer",    "science",
                                              12.0, 5, active=False),

            # Priority 6: Optional / background
            "drill_motor":         PowerLoad("drill_motor",         "science",
                                              15.0, 6, active=False),
            "led_illuminators":    PowerLoad("led_illuminators",    "lighting",
                                              5.0,  6, active=False),
            "aux_heater_bay":      PowerLoad("aux_heater_bay",      "thermal",
                                              8.0,  6, active=False),
        }
        return loads

    # ------------------------------------------------------------------
    # PARAMETER DECLARATION
    # ------------------------------------------------------------------
    def _declare_parameters(self) -> None:
        self.declare_parameter("update_hz", 1.0)
        self.declare_parameter("publish_hz", 1.0)
        self.declare_parameter("safe_mode_soc_threshold_pct", 15.0)
        self.declare_parameter("power_save_soc_threshold_pct", 30.0)
        self.declare_parameter("eclipse_survive_soc_threshold_pct", 10.0)
        self.declare_parameter("battery_heater_min_temp_c", -20.0)
        self.declare_parameter("battery_heater_max_temp_c", 5.0)
        self.declare_parameter("solar_simulation_enabled", True)
        self.declare_parameter("simulate_eclipse", False)
        self.declare_parameter("initial_soc_pct", 95.0)
        self.declare_parameter("science_ops_active", False)
        self.declare_parameter("traverse_active", False)

    # ------------------------------------------------------------------
    # PUBLISHERS / SUBSCRIBERS / SERVICES / TIMERS
    # ------------------------------------------------------------------
    def _create_publishers(self) -> None:
        self._pub_state = self.create_publisher(
            String, "/power/state", RELIABLE_QOS
        )
        self._pub_budget = self.create_publisher(
            String, "/power/budget_report", RELIABLE_QOS
        )
        self._pub_battery = self.create_publisher(
            BatteryState, "/power/battery", RELIABLE_QOS
        )
        self._pub_diagnostics = self.create_publisher(
            DiagnosticArray, "/diagnostics", RELIABLE_QOS
        )
        self.get_logger().info("Power publishers created")

    def _create_subscribers(self) -> None:
        self._sub_thermal = self.create_subscription(
            String, "/thermal/sensor_array",
            self._cb_thermal_sensors,
            RELIABLE_QOS,
            callback_group=self._sub_cbg,
        )
        self._sub_autonomy = self.create_subscription(
            String, "/autonomy/state",
            self._cb_autonomy_state,
            RELIABLE_QOS,
            callback_group=self._sub_cbg,
        )

    def _create_services(self) -> None:
        self._srv_set_load = self.create_service(
            SetBool, "/power/set_science_payload",
            self._srv_cb_set_science_payload,
            callback_group=self._service_cbg,
        )
        self._srv_deploy_solar = self.create_service(
            SetBool, "/power/deploy_solar_panels",
            self._srv_cb_deploy_solar_panels,
            callback_group=self._service_cbg,
        )
        self._srv_get_budget = self.create_service(
            Trigger, "/power/get_budget",
            self._srv_cb_get_budget,
            callback_group=self._service_cbg,
        )
        self._srv_force_safe = self.create_service(
            Trigger, "/power/force_safe_mode",
            self._srv_cb_force_safe_mode,
            callback_group=self._service_cbg,
        )

    def _create_timers(self) -> None:
        update_hz  = self.get_parameter("update_hz").value
        publish_hz = self.get_parameter("publish_hz").value

        self._timer_update = self.create_timer(
            1.0 / update_hz,
            self._cb_power_update,
            callback_group=self._timer_cbg,
        )
        self._timer_publish = self.create_timer(
            1.0 / publish_hz,
            self._cb_publish_power_state,
            callback_group=self._timer_cbg,
        )
        self._timer_heater = self.create_timer(
            0.5,   # 2 Hz heater control
            self._cb_heater_control,
            callback_group=self._timer_cbg,
        )

    # ------------------------------------------------------------------
    # SOLAR POWER MODEL
    # ------------------------------------------------------------------
    def _compute_solar_power(self) -> float:
        """
        Compute total solar array power output.
        Accounts for incidence angle, temperature, panel deployment, and degradation.
        """
        if self.eclipse_active or self.get_parameter("simulate_eclipse").value:
            return 0.0

        if not self.get_parameter("solar_simulation_enabled").value:
            return SOLAR_PEAK_W * 0.75  # Default 75% of peak

        total_w = 0.0
        for panel in self.solar_arrays:
            if not panel.deployed:
                continue

            # Cosine loss from incidence angle
            angle_factor = self._interpolate(
                SOLAR_ANGLE_DERATING, self.solar_incidence_deg
            )

            # Temperature derating (panels run hot in vacuum, ~60-80°C)
            # GaAs panels lose ~0.2%/°C above 25°C
            temp_delta = panel.temperature_c - 25.0
            temp_factor = max(0.5, 1.0 - 0.002 * max(0.0, temp_delta))

            # Cell degradation
            degradation_factor = panel.degradation_pct / 100.0

            # Compute output
            solar_input = self.solar_irradiance_wm2 * self.lunar_distance_factor
            power = (panel.area_m2 * panel.efficiency *
                     solar_input * angle_factor * temp_factor * degradation_factor)

            panel.current_power_w = power
            total_w += power

        return total_w

    @staticmethod
    def _interpolate(table: List[Tuple[float, float]], x: float) -> float:
        """Linear interpolation on a sorted table."""
        if x <= table[0][0]:
            return table[0][1]
        if x >= table[-1][0]:
            return table[-1][1]
        for i in range(1, len(table)):
            if table[i][0] >= x:
                x0, y0 = table[i-1]
                x1, y1 = table[i]
                t = (x - x0) / (x1 - x0)
                return y0 + t * (y1 - y0)
        return table[-1][1]

    # ------------------------------------------------------------------
    # BATTERY STATE MODEL
    # ------------------------------------------------------------------
    def _get_effective_capacity_wh(self) -> float:
        """
        Compute effective battery capacity accounting for temperature derating.
        Uses worst-case (coldest) cell temperature.
        """
        min_temp = min(c.temp_c for c in self.battery_cells)
        derating = self._interpolate(TEMP_DERATING_TABLE, min_temp)
        effective = BATTERY_CAPACITY_WH * derating
        return effective

    def _get_pack_soc(self) -> float:
        """Average SOC across all cells."""
        return sum(c.soc_pct for c in self.battery_cells) / len(self.battery_cells)

    def _get_pack_voltage(self) -> float:
        """Compute pack terminal voltage from SOC (simplified OCV model)."""
        soc = self._get_pack_soc() / 100.0
        # Open circuit voltage vs SOC (7S pack)
        # OCV_cell(soc) = 3.0 + 1.2*soc V (simplified)
        ocv_cell = 3.0 + 1.2 * soc
        pack_voltage = 7 * ocv_cell
        return pack_voltage

    def _update_battery_soc(self, net_power_w: float, dt_sec: float) -> None:
        """
        Update battery SOC based on net power flow.
        net_power_w > 0 means charging, < 0 means discharging.
        """
        effective_capacity_wh = self._get_effective_capacity_wh()
        if effective_capacity_wh <= 0:
            return

        # Energy transferred in this timestep
        energy_wh = net_power_w * (dt_sec / 3600.0)

        # Apply charge/discharge efficiency
        if net_power_w > 0:
            # Charging: ~95% efficiency
            actual_energy_wh = energy_wh * 0.95
        else:
            # Discharging: ~97% efficiency
            actual_energy_wh = energy_wh / 0.97

        # Update SOC for each cell
        delta_soc = (actual_energy_wh / effective_capacity_wh) * 100.0

        for cell in self.battery_cells:
            cell.soc_pct = max(0.0, min(100.0, cell.soc_pct + delta_soc))
            cell.voltage_v = self._get_pack_voltage() / 7.0

    # ------------------------------------------------------------------
    # LOAD MANAGEMENT
    # ------------------------------------------------------------------
    def _compute_total_load_w(self) -> float:
        """Compute total active power load."""
        return sum(
            load.current_power_w
            for load in self.loads.values()
            if load.active
        )

    def _get_load_breakdown(self) -> Dict[str, float]:
        """Get power breakdown by subsystem."""
        breakdown: Dict[str, float] = {}
        for load in self.loads.values():
            if load.active:
                subsystem = load.subsystem
                breakdown[subsystem] = breakdown.get(subsystem, 0.0) + load.current_power_w
        return breakdown

    def _set_load_active(self, load_name: str, active: bool) -> None:
        """Enable or disable a specific load."""
        if load_name in self.loads:
            load = self.loads[load_name]
            load.active = active
            load.current_power_w = load.power_w if active else 0.0
            self.get_logger().info(
                f"Power load '{load_name}': {'ON' if active else 'OFF'} "
                f"({load.power_w:.1f}W)"
            )

    def _shed_loads_to_target(self, target_max_w: float) -> List[str]:
        """
        Shed loads by priority to get total below target.
        Returns list of shed load names.
        """
        shed = []
        current_total = self._compute_total_load_w()

        # Sort shedable loads by priority (highest priority number = shed first)
        shedable = sorted(
            [l for l in self.loads.values() if l.active and l.priority > 2],
            key=lambda l: (-l.priority, -l.power_w)
        )

        for load in shedable:
            if current_total <= target_max_w:
                break
            if load.dimmable and current_total - (load.current_power_w - load.min_power_w) <= target_max_w:
                # Dim instead of full shed
                savings = load.current_power_w - load.min_power_w
                load.current_power_w = load.min_power_w
                current_total -= savings
                shed.append(f"{load.name}(dimmed)")
                self.get_logger().warn(
                    f"LOAD SHED: Dimming '{load.name}' to {load.min_power_w:.1f}W"
                )
            else:
                # Full shed
                current_total -= load.current_power_w
                load.active = False
                load.current_power_w = 0.0
                shed.append(load.name)
                self.get_logger().warn(
                    f"LOAD SHED: Powering off '{load.name}' ({load.power_w:.1f}W)"
                )

        return shed

    def _restore_shed_loads(self) -> None:
        """Restore previously shed loads (called when power improves)."""
        restored = []
        for load_name in list(self.shed_load_names):
            clean_name = load_name.replace("(dimmed)", "")
            if clean_name in self.loads:
                load = self.loads[clean_name]
                load.active = True
                load.current_power_w = load.power_w
                restored.append(clean_name)

        if restored:
            self.shed_load_names.clear()
            self.shedding_active = False
            self.get_logger().info(
                f"Load shedding ended - restored: {restored}"
            )

    # ------------------------------------------------------------------
    # POWER MODE MANAGEMENT
    # ------------------------------------------------------------------
    def _evaluate_power_mode(self, solar_w: float, net_w: float) -> None:
        """Determine and apply appropriate power mode based on state."""
        soc = self._get_pack_soc()
        safe_threshold   = self.get_parameter("safe_mode_soc_threshold_pct").value
        save_threshold   = self.get_parameter("power_save_soc_threshold_pct").value
        eclipse_threshold = self.get_parameter("eclipse_survive_soc_threshold_pct").value

        prev_mode = self.power_mode

        if soc <= eclipse_threshold:
            new_mode = PowerMode.ECLIPSE_SURVIVE
        elif soc <= safe_threshold:
            new_mode = PowerMode.SAFE_MODE
        elif soc <= save_threshold or (solar_w < 20.0 and net_w < -30.0):
            new_mode = PowerMode.POWER_SAVE
        elif solar_w > 0 and net_w > 5.0 and soc < 98.0:
            new_mode = PowerMode.CHARGING
        else:
            new_mode = PowerMode.FULL_POWER

        if new_mode != prev_mode:
            self.power_mode = new_mode
            self.get_logger().warn(
                f"POWER MODE: {prev_mode.name} -> {new_mode.name} "
                f"(SOC={soc:.1f}%, Solar={solar_w:.1f}W, Net={net_w:.1f}W)"
            )
            self._apply_power_mode(new_mode, solar_w)

    def _apply_power_mode(self, mode: PowerMode, solar_w: float) -> None:
        """Apply load shedding and operational changes for power mode."""
        # Maximum allowable load based on mode and solar availability
        # Eclipse survive: only heaters + watchdog
        # Safe mode: minimal systems
        # Power save: shed science + some comms
        if mode == PowerMode.ECLIPSE_SURVIVE:
            target = solar_w + 5.0  # Almost all from battery
            shed = self._shed_loads_to_target(target)
            self.shed_load_names = shed
            self.shedding_active = bool(shed)
            self.get_logger().error(
                "ECLIPSE SURVIVE MODE: Non-essential systems off"
            )
        elif mode == PowerMode.SAFE_MODE:
            # Keep priority <=2 loads only
            target = solar_w + 20.0
            for load in self.loads.values():
                if load.priority > 2:
                    load.active = False
                    load.current_power_w = 0.0
            self.shed_load_names = [l.name for l in self.loads.values() if not l.active]
            self.shedding_active = True
            self.get_logger().error("SAFE MODE: Science and mobility powered down")
        elif mode == PowerMode.POWER_SAVE:
            # Shed priority 5+ loads
            target = solar_w + 40.0
            for load in self.loads.values():
                if load.priority >= 5:
                    load.active = False
                    load.current_power_w = 0.0
            self.get_logger().warn("POWER SAVE: Science payload off")
        elif mode == PowerMode.FULL_POWER:
            if self.shedding_active:
                self._restore_shed_loads()

    # ------------------------------------------------------------------
    # HEATER CONTROL (PWM-based thermal regulation)
    # ------------------------------------------------------------------
    def _cb_heater_control(self) -> None:
        """
        Battery heater PWM control.
        Runs bang-bang with hysteresis around target temperature.
        Target: Keep battery >= -20°C (operational) or >= 5°C (charging).
        """
        battery_temps = [c.temp_c for c in self.battery_cells]
        min_temp = min(battery_temps)

        # Charging requires warmer battery (lithium plating risk below 0°C)
        if self._get_pack_soc() < 100.0:
            target_min = self.get_parameter("battery_heater_max_temp_c").value
        else:
            target_min = self.get_parameter("battery_heater_min_temp_c").value

        heater_max_w = 30.0  # Maximum heater power

        if min_temp < target_min - 2.0:
            # Full heater on
            self.heater_pwm_pct = 100.0
            self.heater_power_w = heater_max_w
            if self.loads["thermal_heaters"].power_w != heater_max_w:
                self.loads["thermal_heaters"].current_power_w = heater_max_w
                self.get_logger().info(
                    f"Battery heater ON: T_min={min_temp:.1f}°C < "
                    f"{target_min-2:.1f}°C target"
                )
        elif min_temp < target_min:
            # Proportional control
            error = target_min - min_temp
            self.heater_pwm_pct = min(100.0, error * 50.0)  # 2°C error = 100%
            self.heater_power_w = heater_max_w * (self.heater_pwm_pct / 100.0)
            self.loads["thermal_heaters"].current_power_w = self.heater_power_w
        else:
            # Heater off
            if self.heater_pwm_pct > 0:
                self.get_logger().debug(
                    f"Battery heater OFF: T_min={min_temp:.1f}°C >= {target_min:.1f}°C"
                )
            self.heater_pwm_pct = 0.0
            self.heater_power_w = 0.0
            self.loads["thermal_heaters"].current_power_w = 5.0  # Minimum keep-alive

    # ------------------------------------------------------------------
    # MAIN UPDATE LOOP
    # ------------------------------------------------------------------
    def _cb_power_update(self) -> None:
        """Main power system update loop."""
        now = time.monotonic()
        dt = now - self.last_update_time
        self.last_update_time = now

        if dt <= 0 or dt > 10.0:
            return

        with self._lock:
            # Update solar generation
            solar_w = self._compute_solar_power()

            # Compute total load
            total_load_w = self._compute_total_load_w()

            # Net power (positive = charging battery)
            net_w = solar_w - total_load_w

            # Update battery
            self._update_battery_soc(net_w, dt)

            # Simulate battery temperature (simplified thermal model)
            # Battery self-heats slightly under load
            for cell in self.battery_cells:
                # Ambient lunar surface (varies, use -40°C to 20°C)
                ambient = -30.0 + 50.0 * (math.sin(
                    2 * math.pi * self.sim_time_s / LUNAR_DAY_SEC
                ) * 0.5 + 0.5)
                # Heater contribution
                heater_contribution = self.heater_power_w * 0.1  # simplified
                # Self-heating from current draw
                i2r_heat = (total_load_w / BATTERY_VOLTAGE_NOMINAL) ** 2 * 0.03
                # Thermal equilibration
                tau = 600.0  # 10-minute thermal time constant
                cell.temp_c += (
                    (ambient + heater_contribution + i2r_heat - cell.temp_c) / tau
                ) * dt

            # Evaluate power mode
            self._evaluate_power_mode(solar_w, net_w)

            # Update simulation time
            self.sim_time_s += dt

            # Update history
            self.power_history.append(total_load_w)
            self.solar_history.append(solar_w)
            if len(self.power_history) > 60:
                self.power_history.pop(0)
            if len(self.solar_history) > 60:
                self.solar_history.pop(0)

    # ------------------------------------------------------------------
    # PUBLISHERS
    # ------------------------------------------------------------------
    def _cb_publish_power_state(self) -> None:
        """Publish power state and budget report."""
        with self._lock:
            soc = self._get_pack_soc()
            solar_w = sum(p.current_power_w for p in self.solar_arrays)
            total_load_w = self._compute_total_load_w()
            net_w = solar_w - total_load_w
            voltage = self._get_pack_voltage()
            effective_cap = self._get_effective_capacity_wh()
            min_temp = min(c.temp_c for c in self.battery_cells)

            # Time to empty/full
            if net_w < -0.1:
                remaining_wh = effective_cap * soc / 100.0
                tte_min = (remaining_wh / abs(net_w)) * 60.0
                ttf_min = float('inf')
            elif net_w > 0.1:
                tte_min = float('inf')
                remaining_wh = effective_cap * (1.0 - soc / 100.0)
                ttf_min = (remaining_wh / net_w) * 60.0
            else:
                tte_min = ttf_min = float('inf')

            state_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "mode": self.power_mode.name,
                "soc_pct": round(soc, 2),
                "battery_voltage_v": round(voltage, 2),
                "battery_temp_c": round(min_temp, 1),
                "solar_w": round(solar_w, 2),
                "load_w": round(total_load_w, 2),
                "net_w": round(net_w, 2),
                "effective_capacity_wh": round(effective_cap, 1),
                "time_to_empty_min": round(tte_min, 1) if tte_min != float('inf') else -1,
                "time_to_full_min": round(ttf_min, 1) if ttf_min != float('inf') else -1,
                "heater_pwm_pct": round(self.heater_pwm_pct, 1),
                "eclipse_active": self.eclipse_active,
                "shedding_active": self.shedding_active,
                "thermal_safe_mode": self.power_mode in (
                    PowerMode.SAFE_MODE, PowerMode.ECLIPSE_SURVIVE
                ),
                "load_breakdown": self._get_load_breakdown(),
                "solar_incidence_deg": round(self.solar_incidence_deg, 1),
            }

            state_msg = String()
            state_msg.data = json.dumps(state_data)
            self._pub_state.publish(state_msg)

            # Publish ROS BatteryState
            batt_msg = BatteryState()
            batt_msg.header.stamp = self.get_clock().now().to_msg()
            batt_msg.voltage = float(voltage)
            batt_msg.temperature = float(min_temp + 273.15)  # Kelvin
            batt_msg.current = float(net_w / voltage)        # Amps (+ = charging)
            batt_msg.charge = float(effective_cap * soc / 100.0)  # Wh (approx Ah if divide by voltage)
            batt_msg.capacity = float(effective_cap)
            batt_msg.design_capacity = float(BATTERY_CAPACITY_WH)
            batt_msg.percentage = float(soc / 100.0)
            batt_msg.power_supply_status = (
                BatteryState.POWER_SUPPLY_STATUS_CHARGING
                if net_w > 0
                else BatteryState.POWER_SUPPLY_STATUS_DISCHARGING
            )
            batt_msg.power_supply_health = (
                BatteryState.POWER_SUPPLY_HEALTH_GOOD
                if soc > 20.0
                else BatteryState.POWER_SUPPLY_HEALTH_DEAD
            )
            batt_msg.power_supply_technology = BatteryState.POWER_SUPPLY_TECHNOLOGY_LION
            batt_msg.present = True
            self._pub_battery.publish(batt_msg)

            # Diagnostics
            diag = DiagnosticArray()
            diag.header.stamp = batt_msg.header.stamp
            status = DiagnosticStatus()
            status.name = "Power System"
            status.message = (
                f"SOC={soc:.1f}% Solar={solar_w:.1f}W Load={total_load_w:.1f}W"
            )
            status.values = [
                KeyValue(key="mode",         value=self.power_mode.name),
                KeyValue(key="soc_pct",      value=f"{soc:.2f}"),
                KeyValue(key="solar_w",      value=f"{solar_w:.1f}"),
                KeyValue(key="load_w",       value=f"{total_load_w:.1f}"),
                KeyValue(key="net_w",        value=f"{net_w:.1f}"),
                KeyValue(key="voltage_v",    value=f"{voltage:.2f}"),
                KeyValue(key="temp_c",       value=f"{min_temp:.1f}"),
                KeyValue(key="heater_pct",   value=f"{self.heater_pwm_pct:.1f}"),
            ]
            if soc < 10.0:
                status.level = DiagnosticStatus.ERROR
            elif soc < 30.0:
                status.level = DiagnosticStatus.WARN
            else:
                status.level = DiagnosticStatus.OK
            diag.status.append(status)
            self._pub_diagnostics.publish(diag)

    # ------------------------------------------------------------------
    # SUBSCRIBER CALLBACKS
    # ------------------------------------------------------------------
    def _cb_thermal_sensors(self, msg: String) -> None:
        """Update battery temperatures from thermal sensor array."""
        try:
            data = json.loads(msg.data)
            sensors = data.get("sensors", {})
            # Map battery sensor readings to cell temperatures
            if "battery_pack_a" in sensors:
                self.battery_cells[0].temp_c = float(sensors["battery_pack_a"])
            if "battery_pack_b" in sensors:
                self.battery_cells[1].temp_c = float(sensors["battery_pack_b"])
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            self.get_logger().debug(f"Thermal sensor parse: {exc}")

    def _cb_autonomy_state(self, msg: String) -> None:
        """Update operational loads based on autonomy state."""
        try:
            data = json.loads(msg.data)
            state = data.get("state", "IDLE")

            # Enable/disable loads based on state
            if state == "TRAVERSE":
                for motor in ["drive_motors_fl", "drive_motors_fr", "drive_motors_ml",
                               "drive_motors_mr", "drive_motors_rl", "drive_motors_rr"]:
                    if self.power_mode == PowerMode.FULL_POWER:
                        self._set_load_active(motor, True)
            elif state in ("IDLE", "STANDBY", "SAFE_MODE"):
                for motor in ["drive_motors_fl", "drive_motors_fr", "drive_motors_ml",
                               "drive_motors_mr", "drive_motors_rl", "drive_motors_rr"]:
                    self._set_load_active(motor, False)

            if state == "SCIENCE_OPS":
                if self.power_mode == PowerMode.FULL_POWER:
                    self._set_load_active("neutron_spectrometer", True)
                    self._set_load_active("thermal_ir_camera", True)
                    self._set_load_active("science_computer", True)
            elif state not in ("SCIENCE_OPS",):
                self._set_load_active("neutron_spectrometer", False)
                self._set_load_active("thermal_ir_camera", False)
                self._set_load_active("drill_motor", False)

            if state == "SAFE_MODE":
                self._apply_power_mode(PowerMode.SAFE_MODE, 0.0)

        except (json.JSONDecodeError, KeyError) as exc:
            self.get_logger().debug(f"Autonomy state parse: {exc}")

    # ------------------------------------------------------------------
    # SERVICE CALLBACKS
    # ------------------------------------------------------------------
    def _srv_cb_set_science_payload(self, request: SetBool.Request,
                                     response: SetBool.Response) -> SetBool.Response:
        """Enable or disable science payload power."""
        science_loads = ["neutron_spectrometer", "thermal_ir_camera",
                         "science_computer", "drill_motor"]
        for name in science_loads:
            self._set_load_active(name, request.data)
        response.success = True
        response.message = f"Science payload {'enabled' if request.data else 'disabled'}"
        return response

    def _srv_cb_deploy_solar_panels(self, request: SetBool.Request,
                                     response: SetBool.Response) -> SetBool.Response:
        """Deploy or stow solar panels."""
        for panel in self.solar_arrays:
            panel.deployed = request.data
        total_area = sum(p.area_m2 for p in self.solar_arrays if p.deployed)
        response.success = True
        response.message = (
            f"Solar panels {'deployed' if request.data else 'stowed'} "
            f"(total area: {total_area:.2f}m²)"
        )
        self.get_logger().info(response.message)
        return response

    def _srv_cb_get_budget(self, request: Trigger.Request,
                            response: Trigger.Response) -> Trigger.Response:
        """Get full power budget as JSON."""
        soc      = self._get_pack_soc()
        solar_w  = sum(p.current_power_w for p in self.solar_arrays)
        load_w   = self._compute_total_load_w()
        response.success = True
        response.message = json.dumps({
            "soc_pct": round(soc, 2),
            "mode": self.power_mode.name,
            "solar_w": round(solar_w, 2),
            "load_w": round(load_w, 2),
            "net_w": round(solar_w - load_w, 2),
            "loads": {k: v.current_power_w for k, v in self.loads.items() if v.active},
        })
        return response

    def _srv_cb_force_safe_mode(self, request: Trigger.Request,
                                 response: Trigger.Response) -> Trigger.Response:
        """Force entry into safe mode."""
        self.power_mode = PowerMode.SAFE_MODE
        self._apply_power_mode(PowerMode.SAFE_MODE, 0.0)
        response.success = True
        response.message = "Forced power safe mode"
        self.get_logger().error("POWER: Forced safe mode via service")
        return response


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------
def main(args=None) -> None:
    rclpy.init(args=args)
    executor = rclpy.executors.MultiThreadedExecutor(num_threads=4)
    node = PowerManagementNode()
    # Deploy solar panels at startup (simulation)
    for panel in node.solar_arrays:
        panel.deployed = True
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
