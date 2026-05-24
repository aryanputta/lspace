"""
LPAS Communications Management Node

Manages rover communication links:
  - UHF relay link (rover ↔ base station, 400 MHz, 5W TX)
  - HGA direct-to-Earth link (Ka-band, 26 GHz, 20W TX, 0.5m dish)
  - LOS tracking and blackout detection
  - Message priority queuing with store-and-forward
  - Bandwidth-aware telemetry throttling
"""
from __future__ import annotations

import collections
import heapq
import json
import math
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Deque, Optional

import rclpy
from rclpy.lifecycle import LifecycleNode, LifecycleState, TransitionCallbackReturn
from rclpy.qos import (
    QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
)
from std_msgs.msg import String, Bool, Float64, Header
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue

RELIABLE_QOS = QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE,
    history=HistoryPolicy.KEEP_LAST,
    depth=20,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
)

SENSOR_QOS = QoSProfile(
    reliability=ReliabilityPolicy.BEST_EFFORT,
    history=HistoryPolicy.KEEP_LAST,
    depth=5,
)


class LinkMode(IntEnum):
    UNKNOWN = 0
    UHF_RELAY = 1        # Rover → Relay station → Earth
    HGA_DIRECT = 2       # Rover → Earth direct
    BLACKOUT = 3         # No link available
    DEGRADED = 4         # Link available but margin < 3 dB


class MessagePriority(IntEnum):
    """Telemetry priority levels — lower value = higher priority."""
    CRITICAL_FAULT = 0   # Fault/safe-mode alerts — always transmitted
    ENGINEERING = 1      # Housekeeping: power, thermal, health
    SCIENCE_PRIORITY = 2 # High-value science data
    NAVIGATION = 3       # Position, path data
    SCIENCE_BULK = 4     # Large science datasets
    IMAGERY = 5          # Camera downlink


@dataclass(order=True)
class QueuedMessage:
    """Priority-queued message for store-and-forward."""
    priority: int
    timestamp: float = field(compare=False)
    topic: str = field(compare=False)
    payload_bytes: int = field(compare=False)
    payload: str = field(compare=False)
    max_age_s: float = field(compare=False, default=86400.0)  # 1 day TTL

    def is_expired(self, now: float) -> bool:
        return (now - self.timestamp) > self.max_age_s


@dataclass
class LinkBudget:
    """RF link budget parameters."""
    tx_power_w: float
    tx_gain_dbi: float
    rx_gain_dbi: float
    frequency_hz: float
    range_m: float
    noise_temp_k: float
    required_eb_n0_db: float
    data_rate_bps: float
    system_losses_db: float = 1.5

    @property
    def wavelength_m(self) -> float:
        return 3e8 / self.frequency_hz

    @property
    def fspl_db(self) -> float:
        """Free-space path loss (dB)."""
        return 20 * math.log10(4 * math.pi * self.range_m / self.wavelength_m)

    @property
    def eirp_dbw(self) -> float:
        return 10 * math.log10(self.tx_power_w) + self.tx_gain_dbi

    @property
    def received_power_dbw(self) -> float:
        return self.eirp_dbw - self.fspl_db + self.rx_gain_dbi - self.system_losses_db

    @property
    def noise_density_dbw_hz(self) -> float:
        k_boltzmann = 1.38e-23
        return 10 * math.log10(k_boltzmann * self.noise_temp_k)

    @property
    def eb_n0_db(self) -> float:
        return (
            self.received_power_dbw
            - self.noise_density_dbw_hz
            - 10 * math.log10(self.data_rate_bps)
        )

    @property
    def link_margin_db(self) -> float:
        return self.eb_n0_db - self.required_eb_n0_db

    def is_closed(self, margin_threshold_db: float = 0.0) -> bool:
        return self.link_margin_db >= margin_threshold_db


# Link budget definitions
UHF_RELAY_BUDGET = LinkBudget(
    tx_power_w=5.0,
    tx_gain_dbi=5.0,
    rx_gain_dbi=8.0,
    frequency_hz=437.5e6,
    range_m=5000.0,        # 5km max relay distance
    noise_temp_k=300.0,
    required_eb_n0_db=9.6,  # BPSK, BER=1e-5
    data_rate_bps=128_000,  # 128 kbps
    system_losses_db=2.0,
)

HGA_DIRECT_BUDGET = LinkBudget(
    tx_power_w=20.0,
    tx_gain_dbi=46.0,       # 0.5m dish @ 26 GHz → ~46 dBi
    rx_gain_dbi=68.0,       # DSN 34m dish → ~68 dBi at Ka
    frequency_hz=26.0e9,
    range_m=384_400_000.0,  # Nominal Earth-Moon distance
    noise_temp_k=30.0,      # Cryogenic DSN receiver
    required_eb_n0_db=12.0,
    data_rate_bps=1_000_000,  # 1 Mbps downlink
    system_losses_db=3.0,   # Atmospheric + pointing losses
)


class CommsNode(LifecycleNode):
    """
    Lifecycle communications management node.

    State machine: unconfigured → inactive → active
    Publishes link state, bandwidth estimates, and manages message queue.
    """

    # Maximum store-and-forward queue depth (bytes)
    MAX_QUEUE_BYTES = 500 * 1024 * 1024  # 500 MB

    def __init__(self) -> None:
        super().__init__("comms_node")
        self._link_mode = LinkMode.UNKNOWN
        self._los_uhf: bool = False
        self._los_hga: bool = False
        self._current_bandwidth_bps: float = 0.0
        self._message_queue: list[QueuedMessage] = []  # min-heap by priority
        self._queue_bytes: int = 0
        self._blackout_start: Optional[float] = None
        self._total_blackout_s: float = 0.0
        self._bytes_transmitted: int = 0
        self._bytes_queued: int = 0

        # Rover position (received from navigation)
        self._rover_lat: float = -89.5
        self._rover_lon: float = 0.0
        self._rover_alt: float = 0.0

        # Relay station position (fixed)
        self._relay_lat: float = -88.0
        self._relay_lon: float = 0.0
        self._relay_alt: float = 1500.0  # 1.5km elevation on crater rim

    # ── Lifecycle callbacks ────────────────────────────────────────────────────

    def on_configure(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Configuring communications node")

        # Publishers
        self._pub_link_state = self.create_lifecycle_publisher(
            String, "/comms/link_state", RELIABLE_QOS
        )
        self._pub_bandwidth = self.create_lifecycle_publisher(
            Float64, "/comms/bandwidth_bps", SENSOR_QOS
        )
        self._pub_blackout = self.create_lifecycle_publisher(
            Bool, "/comms/blackout", RELIABLE_QOS
        )
        self._pub_diagnostics = self.create_lifecycle_publisher(
            DiagnosticArray, "/diagnostics", RELIABLE_QOS
        )

        # Subscriptions
        self._sub_rover_pose = self.create_subscription(
            String, "/navigation/current_pose_json",
            self._cb_rover_pose, RELIABLE_QOS,
        )
        self._sub_queue_msg = self.create_subscription(
            String, "/comms/queue_message",
            self._cb_queue_message, RELIABLE_QOS,
        )

        # Parameters
        self.declare_parameter("uhf_max_range_m", 5000.0)
        self.declare_parameter("hga_pointing_accuracy_deg", 0.5)
        self.declare_parameter("blackout_timeout_s", 300.0)
        self.declare_parameter("link_update_hz", 1.0)
        self.declare_parameter("queue_flush_hz", 2.0)

        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Activating communications node")
        update_hz = self.get_parameter("link_update_hz").value
        flush_hz = self.get_parameter("queue_flush_hz").value

        self._timer_link = self.create_timer(1.0 / update_hz, self._update_link_state)
        self._timer_flush = self.create_timer(1.0 / flush_hz, self._flush_queue)
        self._timer_diag = self.create_timer(5.0, self._publish_diagnostics)

        self._link_mode = LinkMode.UNKNOWN
        return TransitionCallbackReturn.SUCCESS

    def on_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Deactivating communications node")
        self._timer_link.cancel()
        self._timer_flush.cancel()
        self._timer_diag.cancel()
        return TransitionCallbackReturn.SUCCESS

    def on_cleanup(self, state: LifecycleState) -> TransitionCallbackReturn:
        return TransitionCallbackReturn.SUCCESS

    # ── Subscription callbacks ─────────────────────────────────────────────────

    def _cb_rover_pose(self, msg: String) -> None:
        try:
            data = json.loads(msg.data)
            self._rover_lat = data.get("lat", self._rover_lat)
            self._rover_lon = data.get("lon", self._rover_lon)
            self._rover_alt = data.get("alt", self._rover_alt)
        except json.JSONDecodeError:
            pass

    def _cb_queue_message(self, msg: String) -> None:
        """Accept incoming message for priority queue."""
        try:
            data = json.loads(msg.data)
            priority = data.get("priority", MessagePriority.ENGINEERING)
            payload = data.get("payload", "")
            topic = data.get("topic", "unknown")
            size_b = len(payload.encode())

            if self._queue_bytes + size_b > self.MAX_QUEUE_BYTES:
                self.get_logger().warning(
                    f"Queue full ({self._queue_bytes/1e6:.1f} MB) — dropping low-priority message"
                )
                self._drop_lowest_priority()

            queued = QueuedMessage(
                priority=priority,
                timestamp=time.monotonic(),
                topic=topic,
                payload_bytes=size_b,
                payload=payload,
            )
            heapq.heappush(self._message_queue, queued)
            self._queue_bytes += size_b
            self._bytes_queued += size_b
        except (json.JSONDecodeError, KeyError) as e:
            self.get_logger().error(f"Failed to queue message: {e}")

    # ── Core logic ─────────────────────────────────────────────────────────────

    def _compute_los_uhf(self) -> bool:
        """Estimate UHF LOS based on relay range and simple terrain model."""
        lat1 = math.radians(self._rover_lat)
        lon1 = math.radians(self._rover_lon)
        lat2 = math.radians(self._relay_lat)
        lon2 = math.radians(self._relay_lon)

        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = (math.sin(dlat / 2) ** 2
             + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        dist_m = 1_737_400.0 * c  # Lunar radius 1737.4 km

        max_range = self.get_parameter("uhf_max_range_m").value
        return dist_m <= max_range

    def _compute_los_hga(self) -> bool:
        """HGA LOS — available when relay station has Earth visibility.
        Simplified: Earth visible from relay station ~70% of the time at south pole.
        Actual STK analysis would provide precise windows.
        """
        # Simple sinusoidal model for demonstration
        t_hours = time.monotonic() / 3600.0
        # 14.75-day Earth visibility cycle, ~70% duty cycle
        cycle = math.sin(2 * math.pi * t_hours / (14.75 * 24))
        return cycle > -0.57  # sin⁻¹(-0.57) ≈ 70% above threshold

    def _select_link_mode(self) -> LinkMode:
        if not self._los_uhf and not self._los_hga:
            return LinkMode.BLACKOUT
        if self._los_hga:
            margin = HGA_DIRECT_BUDGET.link_margin_db
            if margin >= 3.0:
                return LinkMode.HGA_DIRECT
            elif margin >= 0.0:
                return LinkMode.DEGRADED
        if self._los_uhf:
            margin = UHF_RELAY_BUDGET.link_margin_db
            if margin >= 3.0:
                return LinkMode.UHF_RELAY
            elif margin >= 0.0:
                return LinkMode.DEGRADED
        return LinkMode.BLACKOUT

    def _bandwidth_for_mode(self, mode: LinkMode) -> float:
        if mode == LinkMode.HGA_DIRECT:
            return HGA_DIRECT_BUDGET.data_rate_bps
        elif mode == LinkMode.UHF_RELAY:
            return UHF_RELAY_BUDGET.data_rate_bps
        elif mode == LinkMode.DEGRADED:
            return UHF_RELAY_BUDGET.data_rate_bps * 0.3  # 30% rate when degraded
        return 0.0

    def _update_link_state(self) -> None:
        now = time.monotonic()
        self._los_uhf = self._compute_los_uhf()
        self._los_hga = self._compute_los_hga()
        prev_mode = self._link_mode
        self._link_mode = self._select_link_mode()
        self._current_bandwidth_bps = self._bandwidth_for_mode(self._link_mode)

        # Blackout tracking
        if self._link_mode == LinkMode.BLACKOUT and prev_mode != LinkMode.BLACKOUT:
            self._blackout_start = now
            self.get_logger().warning("Communications BLACKOUT started")
        elif self._link_mode != LinkMode.BLACKOUT and prev_mode == LinkMode.BLACKOUT:
            if self._blackout_start:
                duration = now - self._blackout_start
                self._total_blackout_s += duration
                self.get_logger().info(
                    f"Blackout ended — duration {duration:.0f}s, "
                    f"total blackout {self._total_blackout_s/3600:.2f}h"
                )
            self._blackout_start = None

        # Publish state
        state_data = {
            "mode": self._link_mode.name,
            "los_uhf": self._los_uhf,
            "los_hga": self._los_hga,
            "bandwidth_bps": self._current_bandwidth_bps,
            "uhf_margin_db": round(UHF_RELAY_BUDGET.link_margin_db, 2),
            "hga_margin_db": round(HGA_DIRECT_BUDGET.link_margin_db, 2),
            "queue_depth": len(self._message_queue),
            "queue_bytes": self._queue_bytes,
            "total_blackout_s": round(self._total_blackout_s, 1),
        }
        msg = String()
        msg.data = json.dumps(state_data)
        self._pub_link_state.publish(msg)

        bw_msg = Float64()
        bw_msg.data = self._current_bandwidth_bps
        self._pub_bandwidth.publish(bw_msg)

        blackout_msg = Bool()
        blackout_msg.data = (self._link_mode == LinkMode.BLACKOUT)
        self._pub_blackout.publish(blackout_msg)

    def _flush_queue(self) -> None:
        """Transmit queued messages in priority order when link is available."""
        if self._link_mode == LinkMode.BLACKOUT or not self._message_queue:
            return

        now = time.monotonic()
        bytes_per_flush = int(self._current_bandwidth_bps / 8 / 2)  # half-second budget
        transmitted = 0

        while self._message_queue and transmitted < bytes_per_flush:
            msg = self._message_queue[0]

            if msg.is_expired(now):
                heapq.heappop(self._message_queue)
                self._queue_bytes -= msg.payload_bytes
                self.get_logger().debug(f"Expired message dropped: {msg.topic}")
                continue

            if msg.payload_bytes <= (bytes_per_flush - transmitted):
                heapq.heappop(self._message_queue)
                self._queue_bytes -= msg.payload_bytes
                transmitted += msg.payload_bytes
                self._bytes_transmitted += msg.payload_bytes
                self.get_logger().debug(
                    f"Transmitted {msg.payload_bytes}B [{msg.topic}] "
                    f"via {self._link_mode.name}"
                )
            else:
                break  # Not enough budget for next message this cycle

    def _drop_lowest_priority(self) -> None:
        """Remove lowest-priority (highest int) message from queue."""
        if not self._message_queue:
            return
        # Find max priority item (worst = highest number)
        worst_idx = max(range(len(self._message_queue)),
                        key=lambda i: self._message_queue[i].priority)
        removed = self._message_queue.pop(worst_idx)
        heapq.heapify(self._message_queue)
        self._queue_bytes -= removed.payload_bytes

    def _publish_diagnostics(self) -> None:
        arr = DiagnosticArray()
        arr.header = Header()
        arr.header.stamp = self.get_clock().now().to_msg()

        status = DiagnosticStatus()
        status.name = "comms_node"
        status.hardware_id = "LPAS-COMMS-001"

        if self._link_mode == LinkMode.BLACKOUT:
            status.level = DiagnosticStatus.ERROR
            status.message = "Communications blackout"
        elif self._link_mode == LinkMode.DEGRADED:
            status.level = DiagnosticStatus.WARN
            status.message = "Degraded link — low margin"
        else:
            status.level = DiagnosticStatus.OK
            status.message = f"Link OK: {self._link_mode.name}"

        status.values = [
            KeyValue(key="link_mode", value=self._link_mode.name),
            KeyValue(key="bandwidth_kbps",
                     value=f"{self._current_bandwidth_bps/1000:.1f}"),
            KeyValue(key="queue_messages", value=str(len(self._message_queue))),
            KeyValue(key="queue_mb",
                     value=f"{self._queue_bytes/1e6:.2f}"),
            KeyValue(key="total_transmitted_mb",
                     value=f"{self._bytes_transmitted/1e6:.2f}"),
            KeyValue(key="total_blackout_h",
                     value=f"{self._total_blackout_s/3600:.2f}"),
            KeyValue(key="uhf_link_margin_db",
                     value=f"{UHF_RELAY_BUDGET.link_margin_db:.1f}"),
            KeyValue(key="hga_link_margin_db",
                     value=f"{HGA_DIRECT_BUDGET.link_margin_db:.1f}"),
        ]
        arr.status = [status]
        self._pub_diagnostics.publish(arr)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = CommsNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
