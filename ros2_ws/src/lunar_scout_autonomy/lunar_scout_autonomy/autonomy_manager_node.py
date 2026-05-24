#!/usr/bin/env python3
"""
Lunar PSR Autonomy Scout - Autonomy Manager Node
=================================================
ROS2 Lifecycle Node implementing a hierarchical state machine for autonomous
lunar rover operations. Designed for NASA-grade reliability in permanently
shadowed region (PSR) environments with Earth communication delays of ~1.3s.

State Machine:
    IDLE -> STANDBY -> TRAVERSE -> SCIENCE_OPS -> STANDBY
    Any state -> SAFE_MODE (on power/thermal/fault trigger)
    Any state -> FAULT (on critical subsystem failure)
    Any state -> COMMS_BLACKOUT (on LOS loss > timeout)

Author: Lunar Scout Engineering Team
Version: 1.0.0
"""

from __future__ import annotations

import json
import math
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup, ReentrantCallbackGroup
from rclpy.lifecycle import LifecycleNode, LifecycleState, TransitionCallbackReturn
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)
from rclpy.timer import Timer

from action_msgs.msg import GoalStatus
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from geometry_msgs.msg import PoseStamped
from lifecycle_msgs.msg import State as LCState
from lifecycle_msgs.msg import Transition
from nav_msgs.msg import Path as NavPath
from rcl_interfaces.msg import SetParametersResult
from std_msgs.msg import Bool, Float32, Header, String
from std_srvs.srv import SetBool, Trigger

# ---------------------------------------------------------------------------
# QoS PROFILES
# ---------------------------------------------------------------------------
# Reliable QoS for critical state data
RELIABLE_QOS = QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
    history=HistoryPolicy.KEEP_LAST,
    depth=10,
)

# Best-effort QoS for high-frequency sensor data
SENSOR_QOS = QoSProfile(
    reliability=ReliabilityPolicy.BEST_EFFORT,
    durability=DurabilityPolicy.VOLATILE,
    history=HistoryPolicy.KEEP_LAST,
    depth=5,
)


# ---------------------------------------------------------------------------
# ENUMERATIONS
# ---------------------------------------------------------------------------
class AutonomyState(Enum):
    """Primary rover autonomy operating states."""
    IDLE            = auto()   # Powered on, no active mission
    STANDBY         = auto()   # Ready to execute, systems nominal
    TRAVERSE        = auto()   # Actively driving to waypoint
    SCIENCE_OPS     = auto()   # Science payload active, stationary
    SAFE_MODE       = auto()   # Minimal power, await ground command
    FAULT           = auto()   # One or more critical faults active
    COMMS_BLACKOUT  = auto()   # LOS lost, operating autonomously


class SubsystemHealth(Enum):
    """Health classification for individual subsystems."""
    NOMINAL  = auto()
    DEGRADED = auto()
    CRITICAL = auto()
    OFFLINE  = auto()


class FaultSeverity(Enum):
    """FDIR fault severity levels."""
    INFO     = 0
    WARNING  = 1
    CRITICAL = 2
    FATAL    = 3


# ---------------------------------------------------------------------------
# DATA STRUCTURES
# ---------------------------------------------------------------------------
@dataclass
class SubsystemStatus:
    """Tracks health and watchdog state for a single subsystem."""
    name: str
    last_heartbeat: float = field(default_factory=time.monotonic)
    health: SubsystemHealth = SubsystemHealth.NOMINAL
    heartbeat_timeout_sec: float = 5.0
    fault_count: int = 0
    last_fault_msg: str = ""

    def is_alive(self) -> bool:
        return (time.monotonic() - self.last_heartbeat) < self.heartbeat_timeout_sec

    def update_heartbeat(self) -> None:
        self.last_heartbeat = time.monotonic()

    def age_seconds(self) -> float:
        return time.monotonic() - self.last_heartbeat


@dataclass
class MissionWaypoint:
    """Single waypoint in a mission timeline."""
    waypoint_id: str
    x: float
    y: float
    z: float = 0.0
    heading_deg: float = 0.0
    task: str = "TRAVERSE"       # TRAVERSE | SCIENCE | SAMPLE | SURVEY
    dwell_sec: float = 0.0
    science_ops: List[str] = field(default_factory=list)
    priority: int = 5            # 1=highest, 10=lowest
    completed: bool = False
    arrival_time: Optional[float] = None


@dataclass
class MissionTimeline:
    """Container for a complete mission plan."""
    mission_id: str
    name: str
    created_utc: str
    waypoints: List[MissionWaypoint]
    total_distance_m: float = 0.0
    estimated_duration_sec: float = 0.0
    power_budget_wh: float = 0.0
    current_waypoint_idx: int = 0
    start_time: Optional[float] = None
    abort_on_fault: bool = True


@dataclass
class FaultRecord:
    """Single fault event record for the fault log."""
    timestamp_utc: str
    severity: FaultSeverity
    subsystem: str
    code: str
    description: str
    auto_recovered: bool = False
    recovery_action: str = ""


@dataclass
class AutonomyTelemetry:
    """Snapshot of autonomy system state for telemetry."""
    state: str
    mission_id: str
    waypoint_idx: int
    waypoints_total: int
    progress_pct: float
    elapsed_sec: float
    estimated_remaining_sec: float
    distance_traveled_m: float
    active_faults: int
    subsystem_health: Dict[str, str]


# ---------------------------------------------------------------------------
# BEHAVIOR TREE NODES (py_trees integration)
# ---------------------------------------------------------------------------
try:
    import py_trees
    from py_trees.behaviour import Behaviour
    from py_trees.common import Status
    PY_TREES_AVAILABLE = True
except ImportError:
    PY_TREES_AVAILABLE = False


def build_traverse_tree(autonomy_node: 'AutonomyManagerNode') -> Optional[Any]:
    """Build the behavior tree for traverse operations."""
    if not PY_TREES_AVAILABLE:
        return None

    root = py_trees.composites.Sequence(
        name="TraverseRoot",
        memory=True
    )

    # Check preconditions
    preconditions = py_trees.composites.Parallel(
        name="Preconditions",
        policy=py_trees.common.ParallelPolicy.SuccessOnAll()
    )

    class CheckPower(Behaviour):
        def __init__(self, node_ref):
            super().__init__(name="CheckPower")
            self._node = node_ref

        def update(self) -> Status:
            soc = self._node.current_battery_soc
            if soc > 20.0:
                return Status.SUCCESS
            self._node.get_logger().warn(f"BT: Power too low for traverse: SOC={soc:.1f}%")
            return Status.FAILURE

    class CheckThermal(Behaviour):
        def __init__(self, node_ref):
            super().__init__(name="CheckThermal")
            self._node = node_ref

        def update(self) -> Status:
            if not self._node.thermal_safe_mode_active:
                return Status.SUCCESS
            self._node.get_logger().warn("BT: Thermal safe mode active, blocking traverse")
            return Status.FAILURE

    class CheckNavHealth(Behaviour):
        def __init__(self, node_ref):
            super().__init__(name="CheckNavHealth")
            self._node = node_ref

        def update(self) -> Status:
            nav_sys = self._node.subsystems.get("navigation")
            if nav_sys and nav_sys.health in (SubsystemHealth.NOMINAL, SubsystemHealth.DEGRADED):
                return Status.SUCCESS
            self._node.get_logger().warn("BT: Navigation subsystem unhealthy")
            return Status.FAILURE

    preconditions.add_children([
        CheckPower(autonomy_node),
        CheckThermal(autonomy_node),
        CheckNavHealth(autonomy_node),
    ])

    # Execute traverse
    class ExecuteTraverse(Behaviour):
        def __init__(self, node_ref):
            super().__init__(name="ExecuteTraverse")
            self._node = node_ref
            self._started = False

        def initialise(self) -> None:
            self._started = False

        def update(self) -> Status:
            if not self._started:
                self._node.get_logger().info("BT: Starting traverse execution")
                self._started = True
            if self._node.current_state == AutonomyState.TRAVERSE:
                return Status.RUNNING
            if self._node.current_waypoint_reached:
                return Status.SUCCESS
            return Status.RUNNING

    root.add_children([preconditions, ExecuteTraverse(autonomy_node)])
    return root


def build_science_tree(autonomy_node: 'AutonomyManagerNode') -> Optional[Any]:
    """Build the behavior tree for science operations."""
    if not PY_TREES_AVAILABLE:
        return None

    root = py_trees.composites.Sequence(
        name="ScienceRoot",
        memory=True
    )

    class DeployInstruments(py_trees.behaviour.Behaviour):
        def __init__(self, node_ref):
            super().__init__(name="DeployInstruments")
            self._node = node_ref
            self._deploy_start = None

        def initialise(self):
            self._deploy_start = time.monotonic()
            self._node.get_logger().info("BT: Deploying science instruments")

        def update(self) -> Status:
            elapsed = time.monotonic() - self._deploy_start
            if elapsed > 5.0:  # 5 second deploy time
                self._node.get_logger().info("BT: Instruments deployed")
                return Status.SUCCESS
            return Status.RUNNING

    class RunSpectrometer(py_trees.behaviour.Behaviour):
        def __init__(self, node_ref):
            super().__init__(name="RunSpectrometer")
            self._node = node_ref
            self._start = None
            self._duration = 120.0  # 2 minute integration

        def initialise(self):
            self._start = time.monotonic()
            self._node.get_logger().info(
                f"BT: Starting neutron spectrometer integration ({self._duration}s)"
            )

        def update(self) -> Status:
            elapsed = time.monotonic() - self._start
            if elapsed >= self._duration:
                self._node.get_logger().info("BT: Spectrometer integration complete")
                return Status.SUCCESS
            return Status.RUNNING

    class StowInstruments(py_trees.behaviour.Behaviour):
        def __init__(self, node_ref):
            super().__init__(name="StowInstruments")
            self._node = node_ref

        def update(self) -> Status:
            self._node.get_logger().info("BT: Instruments stowed")
            return Status.SUCCESS

    root.add_children([
        DeployInstruments(autonomy_node),
        RunSpectrometer(autonomy_node),
        StowInstruments(autonomy_node),
    ])
    return root


# ---------------------------------------------------------------------------
# AUTONOMY MANAGER NODE
# ---------------------------------------------------------------------------
class AutonomyManagerNode(LifecycleNode):
    """
    Central autonomy manager for the Lunar PSR Autonomy Scout.

    Implements ROS2 lifecycle management, hierarchical state machine,
    BehaviorTree-based task execution, watchdog monitoring, and
    mission timeline execution from JSON configuration.
    """

    # State transition table: (current_state, trigger) -> next_state
    TRANSITIONS: Dict[Tuple[AutonomyState, str], AutonomyState] = {
        (AutonomyState.IDLE,            "activate"):     AutonomyState.STANDBY,
        (AutonomyState.STANDBY,         "start_traverse"):AutonomyState.TRAVERSE,
        (AutonomyState.STANDBY,         "start_science"): AutonomyState.SCIENCE_OPS,
        (AutonomyState.TRAVERSE,        "waypoint_reached"):AutonomyState.STANDBY,
        (AutonomyState.TRAVERSE,        "science_at_waypoint"):AutonomyState.SCIENCE_OPS,
        (AutonomyState.SCIENCE_OPS,     "science_complete"):AutonomyState.STANDBY,
        (AutonomyState.STANDBY,         "deactivate"):   AutonomyState.IDLE,
        # Any-state triggers (handled specially in transition logic)
        (AutonomyState.IDLE,            "safe_mode"):    AutonomyState.SAFE_MODE,
        (AutonomyState.STANDBY,         "safe_mode"):    AutonomyState.SAFE_MODE,
        (AutonomyState.TRAVERSE,        "safe_mode"):    AutonomyState.SAFE_MODE,
        (AutonomyState.SCIENCE_OPS,     "safe_mode"):    AutonomyState.SAFE_MODE,
        (AutonomyState.FAULT,           "safe_mode"):    AutonomyState.SAFE_MODE,
        (AutonomyState.SAFE_MODE,       "recover"):      AutonomyState.STANDBY,
        (AutonomyState.FAULT,           "recover"):      AutonomyState.STANDBY,
        (AutonomyState.COMMS_BLACKOUT,  "comms_restored"):AutonomyState.STANDBY,
    }

    def __init__(self) -> None:
        super().__init__("autonomy_manager")

        # ------------------------------------------------------------------
        # Internal state
        # ------------------------------------------------------------------
        self.current_state: AutonomyState = AutonomyState.IDLE
        self._state_entry_time: float = time.monotonic()
        self._state_lock = threading.Lock()

        # Mission execution state
        self.current_mission: Optional[MissionTimeline] = None
        self.current_waypoint_reached: bool = False
        self.distance_traveled_m: float = 0.0
        self.last_position: Optional[Tuple[float, float]] = None

        # Sensor / subsystem state (populated by subscribers)
        self.current_battery_soc: float = 95.0       # %
        self.current_power_w: float = 0.0            # W draw
        self.solar_power_w: float = 150.0            # W input
        self.thermal_safe_mode_active: bool = False
        self.comms_los_active: bool = True
        self.last_comms_time: float = time.monotonic()

        # Fault log
        self.fault_log: List[FaultRecord] = []
        self.active_faults: Dict[str, FaultRecord] = {}

        # Behavior trees
        self.traverse_tree: Optional[Any] = None
        self.science_tree: Optional[Any] = None

        # Subsystem watchdog registry
        self.subsystems: Dict[str, SubsystemStatus] = {
            "navigation":     SubsystemStatus("navigation",     heartbeat_timeout_sec=5.0),
            "power":          SubsystemStatus("power",          heartbeat_timeout_sec=3.0),
            "thermal":        SubsystemStatus("thermal",        heartbeat_timeout_sec=5.0),
            "comms":          SubsystemStatus("comms",          heartbeat_timeout_sec=10.0),
            "fault_detection":SubsystemStatus("fault_detection",heartbeat_timeout_sec=5.0),
        }

        # Callback groups for concurrent execution
        self._timer_cbg   = MutuallyExclusiveCallbackGroup()
        self._action_cbg  = ReentrantCallbackGroup()
        self._service_cbg = MutuallyExclusiveCallbackGroup()
        self._sub_cbg     = ReentrantCallbackGroup()

        # Declare parameters
        self._declare_parameters()

        self.get_logger().info("AutonomyManagerNode instantiated (UNCONFIGURED)")

    # ------------------------------------------------------------------
    # LIFECYCLE CALLBACKS
    # ------------------------------------------------------------------
    def on_configure(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Configure node: create publishers, subscribers, servers."""
        self.get_logger().info("Lifecycle: Configuring autonomy manager...")

        try:
            self._create_publishers()
            self._create_subscribers()
            self._create_service_servers()
            self._create_action_servers()
            self._build_behavior_trees()
            self.get_logger().info("Lifecycle: Configuration complete")
            return TransitionCallbackReturn.SUCCESS
        except Exception as exc:
            self.get_logger().error(f"Lifecycle: Configuration failed: {exc}")
            return TransitionCallbackReturn.FAILURE

    def on_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Activate node: start timers and transition to STANDBY."""
        self.get_logger().info("Lifecycle: Activating autonomy manager...")

        try:
            self._create_timers()
            self._transition_state("activate")
            self._publish_autonomy_state()
            self.get_logger().info("Lifecycle: Activation complete - state: STANDBY")
            return TransitionCallbackReturn.SUCCESS
        except Exception as exc:
            self.get_logger().error(f"Lifecycle: Activation failed: {exc}")
            return TransitionCallbackReturn.FAILURE

    def on_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Deactivate node: cancel timers, transition to IDLE."""
        self.get_logger().info("Lifecycle: Deactivating autonomy manager...")
        self._cancel_timers()
        self._transition_state("deactivate")
        self._publish_autonomy_state()
        return TransitionCallbackReturn.SUCCESS

    def on_cleanup(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Cleanup all resources."""
        self.get_logger().info("Lifecycle: Cleaning up...")
        self._cancel_timers()
        self.current_mission = None
        self.fault_log.clear()
        self.active_faults.clear()
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Shutdown node gracefully."""
        self.get_logger().info("Lifecycle: Shutting down autonomy manager")
        self._cancel_timers()
        return TransitionCallbackReturn.SUCCESS

    # ------------------------------------------------------------------
    # PARAMETER DECLARATION
    # ------------------------------------------------------------------
    def _declare_parameters(self) -> None:
        """Declare all ROS2 parameters with defaults."""
        self.declare_parameter("mission_config_path",
                               "/home/user/lspace/ros2_ws/missions/default_mission.json")
        self.declare_parameter("watchdog_check_hz", 2.0)
        self.declare_parameter("state_publish_hz", 1.0)
        self.declare_parameter("progress_publish_hz", 0.5)
        self.declare_parameter("safe_mode_battery_threshold_pct", 15.0)
        self.declare_parameter("safe_mode_power_threshold_w", 10.0)
        self.declare_parameter("comms_blackout_timeout_sec", 600.0)  # 10 minutes
        self.declare_parameter("max_traverse_slope_deg", 20.0)
        self.declare_parameter("auto_safe_mode_on_fault", True)
        self.declare_parameter("enable_behavior_trees", True)
        self.declare_parameter("rover_name", "lunar_scout_01")
        self.declare_parameter("debug_verbose", False)

        self.add_on_set_parameters_callback(self._on_parameter_change)

    def _on_parameter_change(self, params: List[Parameter]) -> SetParametersResult:
        """Handle dynamic parameter changes."""
        for param in params:
            self.get_logger().info(f"Parameter update: {param.name} = {param.value}")
        return SetParametersResult(successful=True)

    # ------------------------------------------------------------------
    # PUBLISHER CREATION
    # ------------------------------------------------------------------
    def _create_publishers(self) -> None:
        """Create all publishers."""
        self._pub_state = self.create_lifecycle_publisher(
            String, "/autonomy/state", RELIABLE_QOS
        )
        self._pub_mission_progress = self.create_lifecycle_publisher(
            String, "/autonomy/mission_progress", RELIABLE_QOS
        )
        self._pub_diagnostics = self.create_lifecycle_publisher(
            DiagnosticArray, "/diagnostics", RELIABLE_QOS
        )
        self._pub_active_faults = self.create_lifecycle_publisher(
            String, "/autonomy/active_faults", RELIABLE_QOS
        )
        self.get_logger().info("Publishers created")

    # ------------------------------------------------------------------
    # SUBSCRIBER CREATION
    # ------------------------------------------------------------------
    def _create_subscribers(self) -> None:
        """Create all subscribers."""
        # Power system heartbeat
        self._sub_power = self.create_subscription(
            String, "/power/state",
            self._cb_power_state,
            RELIABLE_QOS,
            callback_group=self._sub_cbg,
        )

        # Thermal system heartbeat
        self._sub_thermal = self.create_subscription(
            String, "/thermal/state",
            self._cb_thermal_state,
            RELIABLE_QOS,
            callback_group=self._sub_cbg,
        )

        # Comms link state
        self._sub_comms = self.create_subscription(
            String, "/comms/link_state",
            self._cb_comms_state,
            RELIABLE_QOS,
            callback_group=self._sub_cbg,
        )

        # Fault detection feed
        self._sub_faults = self.create_subscription(
            String, "/faults/active",
            self._cb_fault_feed,
            RELIABLE_QOS,
            callback_group=self._sub_cbg,
        )

        # Navigation subsystem heartbeat
        self._sub_nav = self.create_subscription(
            String, "/navigation/current_path",
            self._cb_nav_state,
            SENSOR_QOS,
            callback_group=self._sub_cbg,
        )

        self.get_logger().info("Subscribers created")

    # ------------------------------------------------------------------
    # SERVICE SERVERS
    # ------------------------------------------------------------------
    def _create_service_servers(self) -> None:
        """Create ROS2 service servers."""
        self._srv_set_safe_mode = self.create_service(
            SetBool, "/autonomy/set_safe_mode",
            self._srv_cb_set_safe_mode,
            callback_group=self._service_cbg,
        )

        self._srv_abort_mission = self.create_service(
            Trigger, "/autonomy/abort_mission",
            self._srv_cb_abort_mission,
            callback_group=self._service_cbg,
        )

        self._srv_load_mission = self.create_service(
            Trigger, "/autonomy/load_mission",
            self._srv_cb_load_mission,
            callback_group=self._service_cbg,
        )

        self._srv_recover = self.create_service(
            Trigger, "/autonomy/recover",
            self._srv_cb_recover,
            callback_group=self._service_cbg,
        )

        self._srv_get_state = self.create_service(
            Trigger, "/autonomy/get_state",
            self._srv_cb_get_state,
            callback_group=self._service_cbg,
        )

        self.get_logger().info("Service servers created")

    # ------------------------------------------------------------------
    # ACTION SERVERS
    # ------------------------------------------------------------------
    def _create_action_servers(self) -> None:
        """Create ROS2 action servers for mission commands."""
        # Note: For a real implementation these would use custom action types.
        # Using a workaround with Trigger service for now to avoid custom msg build deps.
        self.get_logger().info("Action server infrastructure ready (using service callbacks)")

    def _build_behavior_trees(self) -> None:
        """Build py_trees behavior trees for task execution."""
        if not self.get_parameter("enable_behavior_trees").value:
            self.get_logger().info("Behavior trees disabled by parameter")
            return

        self.traverse_tree = build_traverse_tree(self)
        self.science_tree  = build_science_tree(self)

        if PY_TREES_AVAILABLE:
            self.get_logger().info("Behavior trees constructed successfully")
        else:
            self.get_logger().warn(
                "py_trees not available - behavior tree execution disabled"
            )

    # ------------------------------------------------------------------
    # TIMER CREATION
    # ------------------------------------------------------------------
    def _create_timers(self) -> None:
        """Create all recurring timers."""
        watchdog_hz   = self.get_parameter("watchdog_check_hz").value
        state_hz      = self.get_parameter("state_publish_hz").value
        progress_hz   = self.get_parameter("progress_publish_hz").value

        self._timer_watchdog = self.create_timer(
            1.0 / watchdog_hz,
            self._cb_watchdog,
            callback_group=self._timer_cbg,
        )
        self._timer_state_pub = self.create_timer(
            1.0 / state_hz,
            self._publish_autonomy_state,
            callback_group=self._timer_cbg,
        )
        self._timer_progress = self.create_timer(
            1.0 / progress_hz,
            self._publish_mission_progress,
            callback_group=self._timer_cbg,
        )
        self._timer_mission_exec = self.create_timer(
            0.5,  # 2 Hz mission executor tick
            self._cb_mission_executor,
            callback_group=self._timer_cbg,
        )
        self._timer_bt_tick = self.create_timer(
            0.1,  # 10 Hz BT tick
            self._cb_bt_tick,
            callback_group=self._timer_cbg,
        )
        self._timer_diagnostics = self.create_timer(
            2.0,  # 0.5 Hz diagnostics
            self._cb_publish_diagnostics,
            callback_group=self._timer_cbg,
        )
        self.get_logger().info(
            f"Timers created: watchdog@{watchdog_hz}Hz, state@{state_hz}Hz"
        )

    def _cancel_timers(self) -> None:
        """Cancel all active timers."""
        for attr in ["_timer_watchdog", "_timer_state_pub", "_timer_progress",
                     "_timer_mission_exec", "_timer_bt_tick", "_timer_diagnostics"]:
            timer = getattr(self, attr, None)
            if timer is not None:
                timer.cancel()
                timer.destroy()
                setattr(self, attr, None)

    # ------------------------------------------------------------------
    # STATE MACHINE
    # ------------------------------------------------------------------
    def _transition_state(self, trigger: str) -> bool:
        """
        Attempt a state transition via trigger.
        Returns True if transition succeeded.
        """
        with self._state_lock:
            key = (self.current_state, trigger)
            if key not in self.TRANSITIONS:
                self.get_logger().warn(
                    f"Invalid transition: {self.current_state.name} + '{trigger}'"
                )
                return False

            next_state = self.TRANSITIONS[key]
            old_state = self.current_state
            self.current_state = next_state
            self._state_entry_time = time.monotonic()

            self.get_logger().info(
                f"State transition: {old_state.name} -> {next_state.name} "
                f"(trigger='{trigger}')"
            )

            # Execute entry actions for new state
            self._on_state_entry(next_state, old_state)
            return True

    def _force_state(self, new_state: AutonomyState, reason: str) -> None:
        """Force a state change regardless of transition table (for emergencies)."""
        with self._state_lock:
            old_state = self.current_state
            self.current_state = new_state
            self._state_entry_time = time.monotonic()
            self.get_logger().warn(
                f"FORCED state change: {old_state.name} -> {new_state.name} "
                f"(reason='{reason}')"
            )
            self._on_state_entry(new_state, old_state)

    def _on_state_entry(self, new_state: AutonomyState,
                        old_state: AutonomyState) -> None:
        """Execute actions upon entering a new state."""
        ts = datetime.now(timezone.utc).isoformat()

        if new_state == AutonomyState.SAFE_MODE:
            self.get_logger().warn(
                f"[{ts}] ENTERING SAFE MODE from {old_state.name} - "
                "shedding non-critical loads"
            )
            self._execute_safe_mode_entry()

        elif new_state == AutonomyState.FAULT:
            self.get_logger().error(
                f"[{ts}] ENTERING FAULT STATE from {old_state.name}"
            )

        elif new_state == AutonomyState.COMMS_BLACKOUT:
            self.get_logger().warn(
                f"[{ts}] COMMS BLACKOUT - activating autonomous ops mode"
            )
            self._execute_comms_blackout_entry()

        elif new_state == AutonomyState.TRAVERSE:
            self.get_logger().info(
                f"[{ts}] Starting traverse to waypoint "
                f"{self._current_waypoint_id()}"
            )
            self.current_waypoint_reached = False

        elif new_state == AutonomyState.SCIENCE_OPS:
            self.get_logger().info(
                f"[{ts}] Starting science operations at "
                f"{self._current_waypoint_id()}"
            )

        elif new_state == AutonomyState.STANDBY:
            self.get_logger().info(f"[{ts}] Entered STANDBY - awaiting next command")

    def _execute_safe_mode_entry(self) -> None:
        """Actions taken when entering safe mode."""
        # In a real system, this would publish load-shed commands
        self.get_logger().warn("SAFE MODE: Science payload powered down")
        self.get_logger().warn("SAFE MODE: Navigation throttled to minimum")
        self.get_logger().warn("SAFE MODE: Cameras in standby")
        self.get_logger().warn("SAFE MODE: Thermal heaters maintaining minimum temps")

        # Abort any active mission
        if self.current_mission is not None:
            self.get_logger().warn(
                f"SAFE MODE: Aborting mission {self.current_mission.mission_id}"
            )

    def _execute_comms_blackout_entry(self) -> None:
        """Actions taken when entering comms blackout."""
        self.get_logger().info(
            "COMMS BLACKOUT: Switching to autonomous timeline execution"
        )
        self.get_logger().info(
            "COMMS BLACKOUT: Store-and-forward buffer active"
        )

    def _current_waypoint_id(self) -> str:
        """Get current waypoint ID or 'none'."""
        if self.current_mission is None:
            return "none"
        idx = self.current_mission.current_waypoint_idx
        if idx < len(self.current_mission.waypoints):
            return self.current_mission.waypoints[idx].waypoint_id
        return "mission_complete"

    # ------------------------------------------------------------------
    # WATCHDOG TIMER CALLBACK
    # ------------------------------------------------------------------
    def _cb_watchdog(self) -> None:
        """
        Periodic watchdog check for all subsystems.
        Triggers state transitions on timeout or health degradation.
        """
        current_time = time.monotonic()
        any_critical = False
        any_fatal = False

        for name, sys_status in self.subsystems.items():
            age = sys_status.age_seconds()

            if not sys_status.is_alive():
                if sys_status.health != SubsystemHealth.OFFLINE:
                    sys_status.health = SubsystemHealth.OFFLINE
                    self.get_logger().error(
                        f"WATCHDOG: Subsystem '{name}' OFFLINE "
                        f"(last heartbeat {age:.1f}s ago)"
                    )
                    fault = FaultRecord(
                        timestamp_utc=datetime.now(timezone.utc).isoformat(),
                        severity=FaultSeverity.CRITICAL,
                        subsystem=name,
                        code=f"WATCHDOG_TIMEOUT_{name.upper()}",
                        description=f"Subsystem '{name}' missed heartbeat for {age:.1f}s",
                    )
                    self._record_fault(fault)
                    any_critical = True

        # Check battery SOC
        soc_threshold = self.get_parameter("safe_mode_battery_threshold_pct").value
        if self.current_battery_soc < soc_threshold:
            if self.current_state not in (AutonomyState.SAFE_MODE, AutonomyState.FAULT):
                self.get_logger().error(
                    f"WATCHDOG: Battery SOC critical: {self.current_battery_soc:.1f}% "
                    f"< {soc_threshold:.1f}% threshold - triggering SAFE MODE"
                )
                self._force_state(AutonomyState.SAFE_MODE,
                                  f"Battery SOC={self.current_battery_soc:.1f}%")

        # Check comms blackout timeout
        blackout_timeout = self.get_parameter("comms_blackout_timeout_sec").value
        comms_age = current_time - self.last_comms_time
        if (not self.comms_los_active and
                comms_age > blackout_timeout and
                self.current_state not in (
                    AutonomyState.COMMS_BLACKOUT,
                    AutonomyState.SAFE_MODE,
                    AutonomyState.FAULT,
                )):
            self.get_logger().warn(
                f"WATCHDOG: Comms blackout for {comms_age:.0f}s > "
                f"{blackout_timeout:.0f}s threshold"
            )
            self._force_state(AutonomyState.COMMS_BLACKOUT,
                              f"LOS lost for {comms_age:.0f}s")

        # Escalate to FAULT if critical subsystems offline
        if any_critical and self.get_parameter("auto_safe_mode_on_fault").value:
            if self.current_state not in (
                AutonomyState.SAFE_MODE,
                AutonomyState.FAULT,
            ):
                self._force_state(AutonomyState.SAFE_MODE, "Critical subsystem offline")

    # ------------------------------------------------------------------
    # MISSION EXECUTOR CALLBACK
    # ------------------------------------------------------------------
    def _cb_mission_executor(self) -> None:
        """
        Mission timeline execution tick.
        Advances through waypoints based on current state.
        """
        if self.current_mission is None:
            return

        if self.current_state not in (
            AutonomyState.STANDBY,
            AutonomyState.TRAVERSE,
            AutonomyState.SCIENCE_OPS,
            AutonomyState.COMMS_BLACKOUT,  # Continue in blackout
        ):
            return

        mission = self.current_mission
        idx = mission.current_waypoint_idx

        if idx >= len(mission.waypoints):
            self.get_logger().info(
                f"Mission '{mission.mission_id}' COMPLETE - "
                f"all {len(mission.waypoints)} waypoints reached"
            )
            self.current_mission = None
            if self.current_state == AutonomyState.TRAVERSE:
                self._transition_state("waypoint_reached")
            return

        waypoint = mission.waypoints[idx]

        # Initiate traverse if in STANDBY
        if self.current_state == AutonomyState.STANDBY:
            if not waypoint.completed:
                if mission.start_time is None:
                    mission.start_time = time.monotonic()
                self.get_logger().info(
                    f"Mission executor: Advancing to waypoint [{idx}] "
                    f"'{waypoint.waypoint_id}' ({waypoint.task})"
                )
                self._transition_state("start_traverse")

        # Handle waypoint arrival (simulated: based on timer/distance)
        elif self.current_state == AutonomyState.TRAVERSE:
            # In simulation, mark reached after dwell time
            if waypoint.arrival_time is None:
                waypoint.arrival_time = time.monotonic()

            elapsed_at_wp = time.monotonic() - waypoint.arrival_time
            if elapsed_at_wp >= max(waypoint.dwell_sec, 3.0):
                self.get_logger().info(
                    f"Waypoint '{waypoint.waypoint_id}' reached after "
                    f"{elapsed_at_wp:.1f}s"
                )
                self.current_waypoint_reached = True
                waypoint.completed = True

                if waypoint.task == "SCIENCE":
                    self._transition_state("science_at_waypoint")
                else:
                    mission.current_waypoint_idx += 1
                    self._transition_state("waypoint_reached")

        elif self.current_state == AutonomyState.SCIENCE_OPS:
            if waypoint.arrival_time is None:
                waypoint.arrival_time = time.monotonic()
            elapsed = time.monotonic() - waypoint.arrival_time
            # Science ops complete after dwell time
            if elapsed >= waypoint.dwell_sec:
                self.get_logger().info(
                    f"Science ops complete at '{waypoint.waypoint_id}' "
                    f"({elapsed:.1f}s)"
                )
                mission.current_waypoint_idx += 1
                self._transition_state("science_complete")

    # ------------------------------------------------------------------
    # BEHAVIOR TREE TICK
    # ------------------------------------------------------------------
    def _cb_bt_tick(self) -> None:
        """Tick the active behavior tree based on current state."""
        if not PY_TREES_AVAILABLE:
            return

        if self.current_state == AutonomyState.TRAVERSE and self.traverse_tree:
            self.traverse_tree.tick_once()
        elif self.current_state == AutonomyState.SCIENCE_OPS and self.science_tree:
            self.science_tree.tick_once()

    # ------------------------------------------------------------------
    # SUBSCRIBER CALLBACKS
    # ------------------------------------------------------------------
    def _cb_power_state(self, msg: String) -> None:
        """Process power system state updates."""
        self.subsystems["power"].update_heartbeat()
        try:
            data = json.loads(msg.data)
            self.current_battery_soc = float(data.get("soc_pct", self.current_battery_soc))
            self.current_power_w     = float(data.get("load_w", self.current_power_w))
            self.solar_power_w       = float(data.get("solar_w", self.solar_power_w))

            thermal_sm = data.get("thermal_safe_mode", False)
            if thermal_sm and not self.thermal_safe_mode_active:
                self.get_logger().warn("Power: Thermal safe mode signal received")

            if self.get_parameter("debug_verbose").value:
                self.get_logger().debug(
                    f"Power: SOC={self.current_battery_soc:.1f}% "
                    f"Load={self.current_power_w:.1f}W "
                    f"Solar={self.solar_power_w:.1f}W"
                )
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            self.get_logger().warn(f"Power state parse error: {exc}")

    def _cb_thermal_state(self, msg: String) -> None:
        """Process thermal system state updates."""
        self.subsystems["thermal"].update_heartbeat()
        try:
            data = json.loads(msg.data)
            self.thermal_safe_mode_active = bool(data.get("safe_mode_active", False))
            if self.thermal_safe_mode_active:
                if self.current_state not in (AutonomyState.SAFE_MODE,):
                    self.get_logger().error(
                        "THERMAL: Safe mode triggered - forcing SAFE_MODE state"
                    )
                    self._force_state(AutonomyState.SAFE_MODE, "Thermal safe mode")
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            self.get_logger().warn(f"Thermal state parse error: {exc}")

    def _cb_comms_state(self, msg: String) -> None:
        """Process comms link state updates."""
        self.subsystems["comms"].update_heartbeat()
        try:
            data = json.loads(msg.data)
            prev_los = self.comms_los_active
            self.comms_los_active = bool(data.get("los_active", True))

            if self.comms_los_active:
                self.last_comms_time = time.monotonic()
                # Restore from blackout if comms re-established
                if self.current_state == AutonomyState.COMMS_BLACKOUT:
                    self.get_logger().info("COMMS: LOS restored - exiting blackout mode")
                    self._transition_state("comms_restored")
            elif prev_los and not self.comms_los_active:
                self.get_logger().warn("COMMS: LOS lost - blackout timer started")

        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            self.get_logger().warn(f"Comms state parse error: {exc}")

    def _cb_fault_feed(self, msg: String) -> None:
        """Process incoming faults from the fault detection node."""
        self.subsystems["fault_detection"].update_heartbeat()
        try:
            fault_data = json.loads(msg.data)
            severity_str = fault_data.get("severity", "WARNING")
            severity = FaultSeverity[severity_str.upper()]

            fault = FaultRecord(
                timestamp_utc=fault_data.get("timestamp", datetime.now(timezone.utc).isoformat()),
                severity=severity,
                subsystem=fault_data.get("subsystem", "unknown"),
                code=fault_data.get("code", "UNKNOWN"),
                description=fault_data.get("description", ""),
            )
            self._record_fault(fault)

            if severity == FaultSeverity.FATAL:
                self.get_logger().fatal(
                    f"FATAL FAULT from '{fault.subsystem}': {fault.description}"
                )
                self._force_state(AutonomyState.FAULT, f"Fatal: {fault.code}")
            elif severity == FaultSeverity.CRITICAL:
                self.get_logger().error(
                    f"CRITICAL FAULT from '{fault.subsystem}': {fault.description}"
                )
                if self.get_parameter("auto_safe_mode_on_fault").value:
                    if self.current_state not in (AutonomyState.SAFE_MODE, AutonomyState.FAULT):
                        self._force_state(AutonomyState.SAFE_MODE, f"Critical: {fault.code}")

        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            self.get_logger().warn(f"Fault feed parse error: {exc}")

    def _cb_nav_state(self, msg: String) -> None:
        """Process navigation state updates."""
        self.subsystems["navigation"].update_heartbeat()

    # ------------------------------------------------------------------
    # FAULT MANAGEMENT
    # ------------------------------------------------------------------
    def _record_fault(self, fault: FaultRecord) -> None:
        """Record a fault to the log and active fault dictionary."""
        self.fault_log.append(fault)
        if fault.severity.value >= FaultSeverity.WARNING.value:
            self.active_faults[fault.code] = fault

        # Trim fault log to last 1000 entries
        if len(self.fault_log) > 1000:
            self.fault_log = self.fault_log[-1000:]

        self.get_logger().warn(
            f"FAULT [{fault.severity.name}] {fault.subsystem}/{fault.code}: "
            f"{fault.description}"
        )

    def _clear_fault(self, fault_code: str) -> None:
        """Clear a specific fault from active faults."""
        if fault_code in self.active_faults:
            fault = self.active_faults.pop(fault_code)
            fault.auto_recovered = True
            self.get_logger().info(f"Fault cleared: {fault_code}")

    # ------------------------------------------------------------------
    # PUBLISHER CALLBACKS
    # ------------------------------------------------------------------
    def _publish_autonomy_state(self) -> None:
        """Publish current autonomy state."""
        if not hasattr(self, "_pub_state") or self._pub_state is None:
            return

        state_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "state": self.current_state.name,
            "state_duration_sec": round(time.monotonic() - self._state_entry_time, 2),
            "battery_soc_pct": round(self.current_battery_soc, 1),
            "solar_w": round(self.solar_power_w, 1),
            "comms_los": self.comms_los_active,
            "thermal_safe_mode": self.thermal_safe_mode_active,
            "active_fault_count": len(self.active_faults),
            "subsystem_health": {
                name: ss.health.name for name, ss in self.subsystems.items()
            },
            "mission_id": self.current_mission.mission_id if self.current_mission else None,
        }
        msg = String()
        msg.data = json.dumps(state_data)
        self._pub_state.publish(msg)

    def _publish_mission_progress(self) -> None:
        """Publish mission progress telemetry."""
        if not hasattr(self, "_pub_mission_progress") or self._pub_mission_progress is None:
            return

        if self.current_mission is None:
            progress_data = {
                "mission_active": False,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        else:
            mission = self.current_mission
            total_wps = len(mission.waypoints)
            completed_wps = sum(1 for wp in mission.waypoints if wp.completed)
            progress_pct = (completed_wps / total_wps * 100.0) if total_wps > 0 else 0.0
            elapsed = (time.monotonic() - mission.start_time) if mission.start_time else 0.0

            progress_data = {
                "mission_active": True,
                "mission_id": mission.mission_id,
                "mission_name": mission.name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "current_waypoint_idx": mission.current_waypoint_idx,
                "total_waypoints": total_wps,
                "completed_waypoints": completed_wps,
                "progress_pct": round(progress_pct, 1),
                "elapsed_sec": round(elapsed, 1),
                "distance_traveled_m": round(self.distance_traveled_m, 2),
                "current_state": self.current_state.name,
            }

        msg = String()
        msg.data = json.dumps(progress_data)
        self._pub_mission_progress.publish(msg)

    def _cb_publish_diagnostics(self) -> None:
        """Publish diagnostic array for rqt_robot_monitor."""
        if not hasattr(self, "_pub_diagnostics") or self._pub_diagnostics is None:
            return

        diag_array = DiagnosticArray()
        diag_array.header.stamp = self.get_clock().now().to_msg()

        # Overall autonomy status
        status = DiagnosticStatus()
        status.name = "Autonomy Manager"
        status.hardware_id = self.get_parameter("rover_name").value
        status.message = f"State: {self.current_state.name}"
        status.values = [
            KeyValue(key="state", value=self.current_state.name),
            KeyValue(key="battery_soc", value=f"{self.current_battery_soc:.1f}%"),
            KeyValue(key="active_faults", value=str(len(self.active_faults))),
            KeyValue(key="comms_los", value=str(self.comms_los_active)),
        ]

        if self.current_state in (AutonomyState.FAULT, AutonomyState.SAFE_MODE):
            status.level = DiagnosticStatus.ERROR
        elif len(self.active_faults) > 0:
            status.level = DiagnosticStatus.WARN
        else:
            status.level = DiagnosticStatus.OK

        diag_array.status.append(status)

        # Per-subsystem diagnostics
        for name, ss in self.subsystems.items():
            sub_status = DiagnosticStatus()
            sub_status.name = f"Subsystem/{name}"
            sub_status.hardware_id = self.get_parameter("rover_name").value
            sub_status.message = f"{ss.health.name} (age: {ss.age_seconds():.1f}s)"
            sub_status.values = [
                KeyValue(key="health", value=ss.health.name),
                KeyValue(key="age_sec", value=f"{ss.age_seconds():.1f}"),
                KeyValue(key="fault_count", value=str(ss.fault_count)),
                KeyValue(key="alive", value=str(ss.is_alive())),
            ]
            if ss.health == SubsystemHealth.OFFLINE:
                sub_status.level = DiagnosticStatus.ERROR
            elif ss.health == SubsystemHealth.CRITICAL:
                sub_status.level = DiagnosticStatus.ERROR
            elif ss.health == SubsystemHealth.DEGRADED:
                sub_status.level = DiagnosticStatus.WARN
            else:
                sub_status.level = DiagnosticStatus.OK

            diag_array.status.append(sub_status)

        self._pub_diagnostics.publish(diag_array)

    # ------------------------------------------------------------------
    # SERVICE CALLBACKS
    # ------------------------------------------------------------------
    def _srv_cb_set_safe_mode(self, request: SetBool.Request,
                               response: SetBool.Response) -> SetBool.Response:
        """Service: Manually set or clear safe mode."""
        if request.data:
            self._force_state(AutonomyState.SAFE_MODE, "Ground command")
            response.success = True
            response.message = "Entered SAFE_MODE via ground command"
        else:
            if self.current_state == AutonomyState.SAFE_MODE:
                result = self._transition_state("recover")
                response.success = result
                response.message = "Exited SAFE_MODE" if result else "Transition failed"
            else:
                response.success = True
                response.message = f"Already in {self.current_state.name}, no change"
        self.get_logger().info(f"SetSafeMode service: {response.message}")
        return response

    def _srv_cb_abort_mission(self, request: Trigger.Request,
                               response: Trigger.Response) -> Trigger.Response:
        """Service: Abort current mission."""
        if self.current_mission is not None:
            mission_id = self.current_mission.mission_id
            self.current_mission = None
            if self.current_state in (AutonomyState.TRAVERSE, AutonomyState.SCIENCE_OPS):
                self._force_state(AutonomyState.STANDBY, "Mission aborted by ground command")
            response.success = True
            response.message = f"Mission '{mission_id}' aborted"
            self.get_logger().warn(f"Mission '{mission_id}' aborted via service")
        else:
            response.success = True
            response.message = "No active mission to abort"
        return response

    def _srv_cb_load_mission(self, request: Trigger.Request,
                              response: Trigger.Response) -> Trigger.Response:
        """Service: Load mission timeline from configured JSON file."""
        config_path = self.get_parameter("mission_config_path").value
        try:
            mission = self._load_mission_from_file(config_path)
            if mission:
                self.current_mission = mission
                response.success = True
                response.message = (
                    f"Mission '{mission.mission_id}' loaded: "
                    f"{len(mission.waypoints)} waypoints"
                )
                self.get_logger().info(response.message)
            else:
                response.success = False
                response.message = "Mission file not found or invalid"
        except Exception as exc:
            response.success = False
            response.message = f"Mission load failed: {exc}"
            self.get_logger().error(response.message)
        return response

    def _srv_cb_recover(self, request: Trigger.Request,
                         response: Trigger.Response) -> Trigger.Response:
        """Service: Attempt recovery from FAULT or SAFE_MODE."""
        if self.current_state in (AutonomyState.FAULT, AutonomyState.SAFE_MODE):
            # Clear non-fatal faults before recovery
            codes_to_clear = [
                code for code, fault in self.active_faults.items()
                if fault.severity != FaultSeverity.FATAL
            ]
            for code in codes_to_clear:
                self._clear_fault(code)

            result = self._transition_state("recover")
            response.success = result
            response.message = "Recovery successful" if result else "Recovery transition failed"
        else:
            response.success = True
            response.message = f"No recovery needed in state {self.current_state.name}"
        return response

    def _srv_cb_get_state(self, request: Trigger.Request,
                           response: Trigger.Response) -> Trigger.Response:
        """Service: Get current state as JSON."""
        state_info = {
            "state": self.current_state.name,
            "state_duration_sec": round(time.monotonic() - self._state_entry_time, 2),
            "active_faults": len(self.active_faults),
            "mission_active": self.current_mission is not None,
            "battery_soc": round(self.current_battery_soc, 1),
            "comms_los": self.comms_los_active,
        }
        response.success = True
        response.message = json.dumps(state_info)
        return response

    # ------------------------------------------------------------------
    # MISSION LOADING
    # ------------------------------------------------------------------
    def _load_mission_from_file(self, path: str) -> Optional[MissionTimeline]:
        """Load mission timeline from JSON file."""
        p = Path(path)
        if not p.exists():
            self.get_logger().warn(f"Mission file not found: {path}")
            return self._generate_default_mission()

        with open(p, "r") as f:
            raw = json.load(f)

        waypoints = []
        for wp_data in raw.get("waypoints", []):
            waypoints.append(MissionWaypoint(
                waypoint_id=wp_data["id"],
                x=float(wp_data["x"]),
                y=float(wp_data["y"]),
                z=float(wp_data.get("z", 0.0)),
                heading_deg=float(wp_data.get("heading_deg", 0.0)),
                task=wp_data.get("task", "TRAVERSE"),
                dwell_sec=float(wp_data.get("dwell_sec", 0.0)),
                science_ops=wp_data.get("science_ops", []),
                priority=int(wp_data.get("priority", 5)),
            ))

        mission = MissionTimeline(
            mission_id=raw["mission_id"],
            name=raw.get("name", "Unnamed Mission"),
            created_utc=raw.get("created_utc", datetime.now(timezone.utc).isoformat()),
            waypoints=waypoints,
            total_distance_m=float(raw.get("total_distance_m", 0.0)),
            estimated_duration_sec=float(raw.get("estimated_duration_sec", 0.0)),
            power_budget_wh=float(raw.get("power_budget_wh", 0.0)),
            abort_on_fault=bool(raw.get("abort_on_fault", True)),
        )

        # Compute total distance if not provided
        if mission.total_distance_m == 0.0 and len(waypoints) > 1:
            total = 0.0
            for i in range(1, len(waypoints)):
                dx = waypoints[i].x - waypoints[i-1].x
                dy = waypoints[i].y - waypoints[i-1].y
                total += math.sqrt(dx*dx + dy*dy)
            mission.total_distance_m = total

        self.get_logger().info(
            f"Loaded mission '{mission.mission_id}': {len(waypoints)} waypoints, "
            f"{mission.total_distance_m:.1f}m estimated distance"
        )
        return mission

    def _generate_default_mission(self) -> MissionTimeline:
        """Generate a default test mission for simulation."""
        self.get_logger().info("Generating default test mission")
        waypoints = [
            MissionWaypoint("WP_01", 10.0, 0.0,  task="TRAVERSE",    dwell_sec=5.0),
            MissionWaypoint("WP_02", 20.0, 5.0,  task="SCIENCE",     dwell_sec=180.0,
                            science_ops=["NEUTRON_SPEC", "THERMAL_IR"]),
            MissionWaypoint("WP_03", 30.0, 0.0,  task="TRAVERSE",    dwell_sec=5.0),
            MissionWaypoint("WP_04", 40.0, -5.0, task="SCIENCE",     dwell_sec=120.0,
                            science_ops=["NEUTRON_SPEC", "DRILL"]),
            MissionWaypoint("WP_05", 0.0,  0.0,  task="TRAVERSE",    dwell_sec=10.0),
        ]
        return MissionTimeline(
            mission_id="DEFAULT_SIM_001",
            name="Default Simulation Mission",
            created_utc=datetime.now(timezone.utc).isoformat(),
            waypoints=waypoints,
            total_distance_m=85.0,
            estimated_duration_sec=3600.0,
            power_budget_wh=45.0,
        )


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------
def main(args=None) -> None:
    rclpy.init(args=args)

    executor = rclpy.executors.MultiThreadedExecutor(num_threads=8)
    node = AutonomyManagerNode()
    executor.add_node(node)

    try:
        node.get_logger().info("Autonomy Manager starting - awaiting lifecycle transitions")
        executor.spin()
    except KeyboardInterrupt:
        node.get_logger().info("Keyboard interrupt received, shutting down")
    except Exception as exc:
        node.get_logger().fatal(f"Unhandled exception: {exc}")
        raise
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
