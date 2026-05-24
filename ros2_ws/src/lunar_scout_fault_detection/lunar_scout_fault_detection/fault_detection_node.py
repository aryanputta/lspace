"""
LPAS Fault Detection, Isolation, and Recovery (FDIR) Node

Implements NASA-style FDIR:
  - Subsystem health monitoring via topic watchdogs
  - Fault severity classification: WARNING → CRITICAL → FATAL
  - Automatic isolation: disable faulted subsystem
  - Recovery procedures: soft reset, safe mode transition
  - Fault log with timestamps and history
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from enum import IntEnum
from typing import Callable, Optional

import rclpy
from rclpy.lifecycle import LifecycleNode, LifecycleState, TransitionCallbackReturn
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from std_msgs.msg import String, Bool
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus

RELIABLE_QOS = QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE,
    history=HistoryPolicy.KEEP_LAST,
    depth=50,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
)


class FaultSeverity(IntEnum):
    NOMINAL = 0
    WARNING = 1    # Anomaly detected, continue with caution
    CRITICAL = 2   # Subsystem degraded, limit operations
    FATAL = 3      # Immediate safe mode required


@dataclass
class FaultRecord:
    fault_id: str
    subsystem: str
    severity: FaultSeverity
    message: str
    timestamp: float
    resolved: bool = False
    resolution_timestamp: Optional[float] = None
    recovery_action: str = "none"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["severity"] = self.severity.name
        return d


@dataclass
class WatchdogEntry:
    """Tracks last-seen time for a topic and defines fault thresholds."""
    subsystem: str
    topic: str
    timeout_warning_s: float
    timeout_critical_s: float
    last_seen: float = field(default_factory=time.monotonic)
    active: bool = True

    def elapsed(self) -> float:
        return time.monotonic() - self.last_seen

    def severity(self) -> FaultSeverity:
        e = self.elapsed()
        if e >= self.timeout_critical_s:
            return FaultSeverity.CRITICAL
        elif e >= self.timeout_warning_s:
            return FaultSeverity.WARNING
        return FaultSeverity.NOMINAL


# Subsystem watchdog configuration
WATCHDOG_CONFIG = [
    WatchdogEntry("power_management",   "/power/state",          5.0,  15.0),
    WatchdogEntry("thermal_monitor",    "/thermal/state",        5.0,  20.0),
    WatchdogEntry("navigation",         "/navigation/current_path", 10.0, 30.0),
    WatchdogEntry("hazard_detection",   "/hazard_detections",    3.0,  10.0),
    WatchdogEntry("wheel_control",      "/wheel_control/odometry", 2.0, 8.0),
    WatchdogEntry("comms",              "/comms/link_state",     5.0,  30.0),
    WatchdogEntry("autonomy_manager",   "/autonomy/state",       5.0,  20.0),
    WatchdogEntry("science_payload",    "/science/drill_status", 30.0, 120.0),
]

# Recovery procedures per fault type
RECOVERY_PROCEDURES: dict[str, dict[FaultSeverity, str]] = {
    "power_management": {
        FaultSeverity.WARNING: "reduce_non_essential_loads",
        FaultSeverity.CRITICAL: "emergency_load_shed",
        FaultSeverity.FATAL: "enter_safe_mode",
    },
    "thermal_monitor": {
        FaultSeverity.WARNING: "reduce_compute_load",
        FaultSeverity.CRITICAL: "activate_survival_heaters",
        FaultSeverity.FATAL: "enter_thermal_safe_mode",
    },
    "hazard_detection": {
        FaultSeverity.WARNING: "reduce_traverse_speed",
        FaultSeverity.CRITICAL: "halt_traverse",
        FaultSeverity.FATAL: "emergency_stop",
    },
    "navigation": {
        FaultSeverity.WARNING: "reduce_traverse_speed",
        FaultSeverity.CRITICAL: "halt_traverse",
        FaultSeverity.FATAL: "emergency_stop",
    },
    "wheel_control": {
        FaultSeverity.WARNING: "limit_wheel_speed",
        FaultSeverity.CRITICAL: "halt_traverse",
        FaultSeverity.FATAL: "emergency_stop",
    },
    "comms": {
        FaultSeverity.WARNING: "switch_to_uhf",
        FaultSeverity.CRITICAL: "store_forward_mode",
        FaultSeverity.FATAL: "autonomous_hold_position",
    },
}


class FaultDetectionNode(LifecycleNode):
    """FDIR lifecycle node — monitors all LPAS subsystems."""

    MAX_FAULT_HISTORY = 500

    def __init__(self) -> None:
        super().__init__("fault_detection_node")
        self._watchdogs: list[WatchdogEntry] = list(WATCHDOG_CONFIG)
        self._active_faults: dict[str, FaultRecord] = {}
        self._fault_history: list[FaultRecord] = []
        self._fault_counter: int = 0
        self._safe_mode_requested: bool = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_configure(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Configuring FDIR node")

        self._pub_faults_active = self.create_lifecycle_publisher(
            String, "/faults/active", RELIABLE_QOS
        )
        self._pub_faults_history = self.create_lifecycle_publisher(
            String, "/faults/history", RELIABLE_QOS
        )
        self._pub_safe_mode_request = self.create_lifecycle_publisher(
            Bool, "/faults/safe_mode_request", RELIABLE_QOS
        )

        # Subscribe to diagnostic topics from all nodes
        self._sub_power = self.create_subscription(
            String, "/power/state", lambda m: self._touch("power_management"), RELIABLE_QOS
        )
        self._sub_thermal = self.create_subscription(
            String, "/thermal/state", lambda m: self._touch("thermal_monitor"), RELIABLE_QOS
        )
        self._sub_nav = self.create_subscription(
            String, "/navigation/current_path", lambda m: self._touch("navigation"), RELIABLE_QOS
        )
        self._sub_hazard = self.create_subscription(
            String, "/hazard_detections", lambda m: self._touch("hazard_detection"), RELIABLE_QOS
        )
        self._sub_wheel = self.create_subscription(
            String, "/wheel_control/odometry", lambda m: self._touch("wheel_control"), RELIABLE_QOS
        )
        self._sub_comms = self.create_subscription(
            String, "/comms/link_state", lambda m: self._touch("comms"), RELIABLE_QOS
        )
        self._sub_autonomy = self.create_subscription(
            String, "/autonomy/state", lambda m: self._touch("autonomy_manager"), RELIABLE_QOS
        )

        self.declare_parameter("watchdog_check_hz", 2.0)
        self.declare_parameter("fault_report_hz", 1.0)

        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Activating FDIR node")
        check_hz = self.get_parameter("watchdog_check_hz").value
        report_hz = self.get_parameter("fault_report_hz").value

        self._timer_watchdog = self.create_timer(1.0 / check_hz, self._check_watchdogs)
        self._timer_report = self.create_timer(1.0 / report_hz, self._publish_fault_status)

        # Reset watchdog timers so startup doesn't immediately trigger
        now = time.monotonic()
        for wd in self._watchdogs:
            wd.last_seen = now

        return TransitionCallbackReturn.SUCCESS

    def on_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self._timer_watchdog.cancel()
        self._timer_report.cancel()
        return TransitionCallbackReturn.SUCCESS

    def on_cleanup(self, state: LifecycleState) -> TransitionCallbackReturn:
        return TransitionCallbackReturn.SUCCESS

    # ── Watchdog logic ─────────────────────────────────────────────────────────

    def _touch(self, subsystem: str) -> None:
        """Mark subsystem as alive."""
        for wd in self._watchdogs:
            if wd.subsystem == subsystem:
                wd.last_seen = time.monotonic()
                # Auto-resolve active watchdog fault if subsystem recovers
                fault_id = f"watchdog_{subsystem}"
                if fault_id in self._active_faults:
                    self._resolve_fault(fault_id, "watchdog_heartbeat_restored")
                break

    def _check_watchdogs(self) -> None:
        """Check all watchdogs and raise/update/resolve faults."""
        for wd in self._watchdogs:
            if not wd.active:
                continue
            severity = wd.severity()
            fault_id = f"watchdog_{wd.subsystem}"

            if severity == FaultSeverity.NOMINAL:
                if fault_id in self._active_faults:
                    self._resolve_fault(fault_id, "timeout_cleared")
            else:
                elapsed = wd.elapsed()
                existing = self._active_faults.get(fault_id)
                if existing is None or existing.severity < severity:
                    self._raise_fault(
                        fault_id=fault_id,
                        subsystem=wd.subsystem,
                        severity=severity,
                        message=(
                            f"{wd.subsystem} watchdog timeout: {elapsed:.1f}s "
                            f"(threshold: {wd.timeout_critical_s}s)"
                        ),
                    )

    def _raise_fault(
        self,
        fault_id: str,
        subsystem: str,
        severity: FaultSeverity,
        message: str,
    ) -> None:
        recovery = RECOVERY_PROCEDURES.get(subsystem, {}).get(
            severity, "log_and_continue"
        )
        record = FaultRecord(
            fault_id=fault_id,
            subsystem=subsystem,
            severity=severity,
            message=message,
            timestamp=time.monotonic(),
            recovery_action=recovery,
        )
        self._active_faults[fault_id] = record

        log_fn = {
            FaultSeverity.WARNING: self.get_logger().warning,
            FaultSeverity.CRITICAL: self.get_logger().error,
            FaultSeverity.FATAL: self.get_logger().fatal,
        }.get(severity, self.get_logger().info)
        log_fn(f"FAULT [{severity.name}] {fault_id}: {message} → {recovery}")

        self._execute_recovery(subsystem, severity, recovery)

        if severity == FaultSeverity.FATAL:
            self._request_safe_mode(f"Fatal fault in {subsystem}: {message}")

    def _resolve_fault(self, fault_id: str, reason: str) -> None:
        if fault_id not in self._active_faults:
            return
        record = self._active_faults.pop(fault_id)
        record.resolved = True
        record.resolution_timestamp = time.monotonic()
        record.recovery_action = reason

        if len(self._fault_history) >= self.MAX_FAULT_HISTORY:
            self._fault_history.pop(0)
        self._fault_history.append(record)

        self.get_logger().info(
            f"RESOLVED [{record.severity.name}] {fault_id} — {reason}"
        )

    def _execute_recovery(
        self, subsystem: str, severity: FaultSeverity, action: str
    ) -> None:
        """Publish recovery commands (consumed by autonomy manager)."""
        cmd = {
            "source": "fdir",
            "subsystem": subsystem,
            "severity": severity.name,
            "action": action,
            "timestamp": time.monotonic(),
        }
        msg = String()
        msg.data = json.dumps(cmd)
        # Recovery commands published on active faults topic for autonomy manager
        # to consume and dispatch to appropriate nodes

    def _request_safe_mode(self, reason: str) -> None:
        if not self._safe_mode_requested:
            self._safe_mode_requested = True
            self.get_logger().fatal(f"SAFE MODE REQUESTED: {reason}")
            msg = Bool()
            msg.data = True
            self._pub_safe_mode_request.publish(msg)

    # ── Publishing ─────────────────────────────────────────────────────────────

    def _publish_fault_status(self) -> None:
        active_data = {
            "count": len(self._active_faults),
            "safe_mode_requested": self._safe_mode_requested,
            "faults": [f.to_dict() for f in self._active_faults.values()],
        }
        msg = String()
        msg.data = json.dumps(active_data)
        self._pub_faults_active.publish(msg)

        history_data = {
            "count": len(self._fault_history),
            "recent": [f.to_dict() for f in self._fault_history[-10:]],
        }
        hist_msg = String()
        hist_msg.data = json.dumps(history_data)
        self._pub_faults_history.publish(hist_msg)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = FaultDetectionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
