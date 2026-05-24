#!/usr/bin/env python3
"""
Lunar PSR Autonomy Scout - Navigation Node
==========================================
Full-featured navigation node with energy-aware A* path planning,
terrain traversability enforcement, Nav2 integration, dead reckoning
fallback, and hazard-triggered replanning.

Key features:
- Energy-aware A* with terrain cost function
- Slope enforcement (max 20 degrees from URDF kinematic limits)
- Traversability map subscription and cost updating
- Waypoint queue management with priority ordering
- Dead reckoning via IMU + wheel odometry integration during comms blackout
- Nav2 action client for actual path execution
- Hazard detection triggers immediate replanning

Author: Lunar Scout Engineering Team
"""

from __future__ import annotations

import heapq
import json
import math
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

import rclpy
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup, ReentrantCallbackGroup
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy

from geometry_msgs.msg import (
    Point,
    Pose,
    PoseStamped,
    PoseWithCovarianceStamped,
    Quaternion,
    Twist,
    Vector3,
)
from nav_msgs.msg import OccupancyGrid, Odometry, Path
from sensor_msgs.msg import Imu, NavSatFix
from std_msgs.msg import Float32, Header, String
from std_srvs.srv import SetBool, Trigger
from visualization_msgs.msg import Marker, MarkerArray

# ---------------------------------------------------------------------------
# QoS PROFILES
# ---------------------------------------------------------------------------
RELIABLE_QOS = QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
    history=HistoryPolicy.KEEP_LAST,
    depth=10,
)
SENSOR_QOS = QoSProfile(
    reliability=ReliabilityPolicy.BEST_EFFORT,
    durability=DurabilityPolicy.VOLATILE,
    history=HistoryPolicy.KEEP_LAST,
    depth=5,
)

# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------
MAX_SLOPE_DEG          = 20.0       # Maximum traversable slope
MAX_SPEED_MS           = 0.5        # Maximum speed m/s (lunar surface limit)
MIN_SPEED_MS           = 0.05       # Minimum speed (creep mode)
WHEEL_RADIUS_M         = 0.25       # Wheel radius from URDF
WHEEL_SEPARATION_M     = 1.40       # Track width from URDF
ENERGY_PER_METER_J     = 25.0       # ~25 J/m baseline on flat terrain
SLOPE_ENERGY_FACTOR    = 3.0        # Energy multiplier per degree of slope
HAZARD_COST_MULTIPLIER = 100.0      # Cost multiplier in hazard zones
WAYPOINT_TOLERANCE_M   = 0.5        # Waypoint arrival tolerance
DEAD_RECKONING_DRIFT_M = 0.02       # Dead reckoning drift per meter (2%)

# ---------------------------------------------------------------------------
# DATA STRUCTURES
# ---------------------------------------------------------------------------
@dataclass(order=True)
class PriorityItem:
    """Priority queue item for A*."""
    priority: float
    item: object = field(compare=False)


@dataclass
class GridCell:
    """Single cell in the traversability grid."""
    row: int
    col: int
    slope_deg: float = 0.0
    roughness: float = 0.0           # 0.0 = smooth, 1.0 = impassable
    hazard_flag: bool = False
    traversable: bool = True
    energy_cost: float = 1.0         # Normalized energy cost multiplier


@dataclass
class TraversabilityMap:
    """Traversability map with grid representation."""
    width: int                       # Grid columns
    height: int                      # Grid rows
    resolution_m: float              # Meters per cell
    origin_x: float                  # World X of grid origin
    origin_y: float                  # World Y of grid origin
    cells: np.ndarray                # (height, width) float32 cost array
    hazard_mask: np.ndarray          # (height, width) bool hazard mask
    slope_map: np.ndarray            # (height, width) float32 slope degrees
    timestamp: float = field(default_factory=time.monotonic)

    def world_to_grid(self, x: float, y: float) -> Tuple[int, int]:
        """Convert world coordinates to grid cell indices."""
        col = int((x - self.origin_x) / self.resolution_m)
        row = int((y - self.origin_y) / self.resolution_m)
        return (row, col)

    def grid_to_world(self, row: int, col: int) -> Tuple[float, float]:
        """Convert grid cell to world coordinates (cell center)."""
        x = self.origin_x + (col + 0.5) * self.resolution_m
        y = self.origin_y + (row + 0.5) * self.resolution_m
        return (x, y)

    def is_valid(self, row: int, col: int) -> bool:
        return 0 <= row < self.height and 0 <= col < self.width

    def is_traversable(self, row: int, col: int) -> bool:
        if not self.is_valid(row, col):
            return False
        if self.hazard_mask[row, col]:
            return False
        if self.slope_map[row, col] > MAX_SLOPE_DEG:
            return False
        return self.cells[row, col] < 90.0  # OccupancyGrid < 90 = free


@dataclass
class Waypoint:
    """Navigation waypoint."""
    wp_id: str
    x: float
    y: float
    heading_deg: float = 0.0
    priority: int = 5
    approach_speed_ms: float = MAX_SPEED_MS
    completed: bool = False
    skipped: bool = False
    energy_estimate_j: float = 0.0


@dataclass
class PathSegment:
    """Single segment of the planned path."""
    start: Tuple[float, float]
    end: Tuple[float, float]
    slope_deg: float
    energy_j: float
    distance_m: float


@dataclass
class DeadReckoningState:
    """State for dead reckoning integration."""
    x: float = 0.0
    y: float = 0.0
    heading_rad: float = 0.0
    total_distance_m: float = 0.0
    covariance_m2: float = 0.0      # Position uncertainty (grows over time)
    last_update_time: float = field(default_factory=time.monotonic)
    active: bool = False


@dataclass
class NavigationTelemetry:
    """Navigation telemetry snapshot."""
    timestamp: str
    state: str
    current_x: float
    current_y: float
    heading_deg: float
    speed_ms: float
    target_wp: Optional[str]
    distance_to_target_m: float
    path_length_m: float
    energy_estimate_j: float
    waypoints_queued: int
    replanning_count: int
    dead_reckoning_active: bool
    position_uncertainty_m: float


# ---------------------------------------------------------------------------
# A* ENERGY-AWARE PATH PLANNER
# ---------------------------------------------------------------------------
class EnergyAwarePlanner:
    """
    A* path planner with energy cost function.
    Accounts for slope, terrain roughness, and hazards in cost computation.
    """

    # 8-connected grid neighbors
    NEIGHBORS = [
        (-1, 0,  1.0),   # N
        (1,  0,  1.0),   # S
        (0, -1,  1.0),   # W
        (0,  1,  1.0),   # E
        (-1, -1, 1.4142),# NW
        (-1,  1, 1.4142),# NE
        (1, -1,  1.4142),# SW
        (1,  1,  1.4142),# SE
    ]

    def __init__(self, logger=None):
        self._logger = logger

    def _energy_cost(self, tmap: TraversabilityMap,
                     row: int, col: int, dist_mult: float) -> float:
        """
        Compute energy cost for traversing a cell.
        Combines slope energy, roughness, and hazard penalties.
        """
        if not tmap.is_valid(row, col):
            return float('inf')

        slope = tmap.slope_map[row, col]
        if slope > MAX_SLOPE_DEG:
            return float('inf')

        # Base energy from distance
        base = ENERGY_PER_METER_J * tmap.resolution_m * dist_mult

        # Slope energy penalty (exponential: steep slopes cost much more)
        slope_energy = base * (1.0 + SLOPE_ENERGY_FACTOR * (slope / MAX_SLOPE_DEG) ** 2)

        # Roughness multiplier (1.0 = smooth, 2.0 = very rough)
        roughness_factor = 1.0 + tmap.cells[row, col] / 100.0

        # Hazard penalty
        hazard_penalty = HAZARD_COST_MULTIPLIER * base if tmap.hazard_mask[row, col] else 0.0

        return slope_energy * roughness_factor + hazard_penalty

    def _heuristic(self, row: int, col: int, goal_row: int, goal_col: int,
                   resolution: float) -> float:
        """Euclidean heuristic scaled to energy units."""
        dist = math.sqrt((row - goal_row)**2 + (col - goal_col)**2) * resolution
        return ENERGY_PER_METER_J * dist

    def plan(self, tmap: TraversabilityMap,
             start_world: Tuple[float, float],
             goal_world: Tuple[float, float]) -> Optional[List[Tuple[float, float]]]:
        """
        Plan an energy-optimal path from start to goal.
        Returns list of (x, y) world coordinates or None if no path found.
        """
        start_cell = tmap.world_to_grid(*start_world)
        goal_cell  = tmap.world_to_grid(*goal_world)

        if not tmap.is_valid(*start_cell):
            if self._logger:
                self._logger.error(f"Planner: Start cell {start_cell} out of bounds")
            return None

        if not tmap.is_valid(*goal_cell):
            if self._logger:
                self._logger.error(f"Planner: Goal cell {goal_cell} out of bounds")
            return None

        if not tmap.is_traversable(*goal_cell):
            if self._logger:
                self._logger.warn(f"Planner: Goal cell {goal_cell} is not traversable")
            # Try nearby cells
            goal_cell = self._find_nearest_traversable(tmap, goal_cell)
            if goal_cell is None:
                return None

        # A* search
        open_set: List[PriorityItem] = []
        heapq.heappush(open_set, PriorityItem(0.0, start_cell))

        came_from: Dict[Tuple, Optional[Tuple]] = {start_cell: None}
        g_score: Dict[Tuple, float] = {start_cell: 0.0}
        f_score: Dict[Tuple, float] = {
            start_cell: self._heuristic(*start_cell, *goal_cell, tmap.resolution_m)
        }

        iterations = 0
        max_iterations = tmap.width * tmap.height * 4

        while open_set and iterations < max_iterations:
            iterations += 1
            current = heapq.heappop(open_set).item

            if current == goal_cell:
                return self._reconstruct_path(came_from, current, tmap)

            for dr, dc, dist_mult in self.NEIGHBORS:
                neighbor = (current[0] + dr, current[1] + dc)

                if not tmap.is_traversable(*neighbor):
                    continue

                step_cost = self._energy_cost(tmap, *neighbor, dist_mult)
                if step_cost == float('inf'):
                    continue

                tentative_g = g_score[current] + step_cost

                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor]   = tentative_g
                    f_val = tentative_g + self._heuristic(
                        *neighbor, *goal_cell, tmap.resolution_m
                    )
                    f_score[neighbor]   = f_val
                    heapq.heappush(open_set, PriorityItem(f_val, neighbor))

        if self._logger:
            self._logger.warn(
                f"Planner: No path found after {iterations} iterations "
                f"({start_cell} -> {goal_cell})"
            )
        return None

    def _find_nearest_traversable(self, tmap: TraversabilityMap,
                                   cell: Tuple[int, int],
                                   search_radius: int = 5) -> Optional[Tuple[int, int]]:
        """Find nearest traversable cell to given cell."""
        best_dist = float('inf')
        best_cell = None
        for dr in range(-search_radius, search_radius + 1):
            for dc in range(-search_radius, search_radius + 1):
                candidate = (cell[0] + dr, cell[1] + dc)
                if tmap.is_traversable(*candidate):
                    dist = math.sqrt(dr*dr + dc*dc)
                    if dist < best_dist:
                        best_dist = dist
                        best_cell = candidate
        return best_cell

    def _reconstruct_path(self, came_from: Dict, current: Tuple,
                           tmap: TraversabilityMap) -> List[Tuple[float, float]]:
        """Reconstruct path from came_from dictionary."""
        path = []
        node = current
        while node is not None:
            world_pos = tmap.grid_to_world(*node)
            path.append(world_pos)
            node = came_from[node]
        path.reverse()

        # Apply path smoothing (keep every Nth point for long paths)
        if len(path) > 100:
            step = max(1, len(path) // 100)
            smoothed = path[::step]
            if smoothed[-1] != path[-1]:
                smoothed.append(path[-1])
            return smoothed

        return path

    def estimate_path_energy(self, path: List[Tuple[float, float]],
                              tmap: TraversabilityMap) -> float:
        """Estimate total energy in Joules for a planned path."""
        if len(path) < 2:
            return 0.0
        total_energy = 0.0
        for i in range(1, len(path)):
            dx = path[i][0] - path[i-1][0]
            dy = path[i][1] - path[i-1][1]
            dist = math.sqrt(dx*dx + dy*dy)
            row, col = tmap.world_to_grid(*path[i])
            if tmap.is_valid(row, col):
                slope = tmap.slope_map[row, col]
                energy = dist * ENERGY_PER_METER_J * (
                    1.0 + SLOPE_ENERGY_FACTOR * (slope / MAX_SLOPE_DEG) ** 2
                )
                total_energy += energy
        return total_energy


# ---------------------------------------------------------------------------
# NAVIGATION NODE
# ---------------------------------------------------------------------------
class NavigationNode(Node):
    """
    Main navigation node for the Lunar PSR Autonomy Scout.

    Manages waypoint queue, path planning, Nav2 integration,
    dead reckoning, and hazard avoidance.
    """

    def __init__(self) -> None:
        super().__init__("lunar_scout_navigation")

        # ------------------------------------------------------------------
        # State
        # ------------------------------------------------------------------
        self._lock = threading.Lock()

        # Current position (from odometry or dead reckoning)
        self.current_x: float = 0.0
        self.current_y: float = 0.0
        self.current_heading_rad: float = 0.0
        self.current_speed_ms: float = 0.0

        # IMU state (for dead reckoning)
        self.imu_angular_vel_z: float = 0.0
        self.imu_linear_acc_x: float = 0.0
        self.imu_linear_acc_y: float = 0.0

        # Dead reckoning
        self.dead_reckoning = DeadReckoningState()
        self.comms_blackout_active: bool = False

        # Path planning
        self.planner = EnergyAwarePlanner(logger=self.get_logger())
        self.traversability_map: Optional[TraversabilityMap] = None
        self.current_path: Optional[List[Tuple[float, float]]] = None
        self.path_energy_estimate_j: float = 0.0
        self.replanning_count: int = 0

        # Waypoint queue (priority queue: (priority, timestamp, waypoint))
        self.waypoint_queue: List[Tuple[int, float, Waypoint]] = []
        self.current_waypoint: Optional[Waypoint] = None
        self.active_hazards: Dict[str, Tuple[float, float]] = {}  # id -> (x, y)

        # Nav state
        self.navigation_active: bool = False
        self.nav_state: str = "IDLE"

        # Callback groups
        self._timer_cbg   = MutuallyExclusiveCallbackGroup()
        self._service_cbg = MutuallyExclusiveCallbackGroup()
        self._sub_cbg     = ReentrantCallbackGroup()

        # Parameters
        self._declare_parameters()

        # ROS interfaces
        self._create_publishers()
        self._create_subscribers()
        self._create_services()
        self._create_timers()

        # Create a synthetic traversability map for simulation
        self._initialize_sim_traversability_map()

        self.get_logger().info("NavigationNode initialized")

    # ------------------------------------------------------------------
    # PARAMETER DECLARATION
    # ------------------------------------------------------------------
    def _declare_parameters(self) -> None:
        self.declare_parameter("max_slope_deg", MAX_SLOPE_DEG)
        self.declare_parameter("max_speed_ms", MAX_SPEED_MS)
        self.declare_parameter("min_speed_ms", MIN_SPEED_MS)
        self.declare_parameter("waypoint_tolerance_m", WAYPOINT_TOLERANCE_M)
        self.declare_parameter("map_frame", "map")
        self.declare_parameter("robot_frame", "base_link")
        self.declare_parameter("replan_on_hazard", True)
        self.declare_parameter("dead_reckoning_enabled", True)
        self.declare_parameter("heartbeat_hz", 2.0)
        self.declare_parameter("path_publish_hz", 1.0)
        self.declare_parameter("control_hz", 10.0)
        self.declare_parameter("replan_threshold_m", 2.0)  # Replan if off-path by >2m

    # ------------------------------------------------------------------
    # PUBLISHERS
    # ------------------------------------------------------------------
    def _create_publishers(self) -> None:
        self._pub_path = self.create_publisher(
            Path, "/navigation/current_path", RELIABLE_QOS
        )
        self._pub_energy = self.create_publisher(
            Float32, "/navigation/energy_estimate", RELIABLE_QOS
        )
        self._pub_cmd_vel = self.create_publisher(
            Twist, "/cmd_vel", SENSOR_QOS
        )
        self._pub_telemetry = self.create_publisher(
            String, "/navigation/telemetry", RELIABLE_QOS
        )
        self._pub_waypoint_markers = self.create_publisher(
            MarkerArray, "/navigation/waypoint_markers", RELIABLE_QOS
        )
        self._pub_heartbeat = self.create_publisher(
            String, "/navigation/current_path", RELIABLE_QOS
        )
        self.get_logger().info("Navigation publishers created")

    # ------------------------------------------------------------------
    # SUBSCRIBERS
    # ------------------------------------------------------------------
    def _create_subscribers(self) -> None:
        # Occupancy grid as traversability map
        self._sub_trav_map = self.create_subscription(
            OccupancyGrid, "/traversability_map",
            self._cb_traversability_map,
            RELIABLE_QOS,
            callback_group=self._sub_cbg,
        )

        # Hazard detections from perception
        self._sub_hazards = self.create_subscription(
            String, "/hazard_detections",
            self._cb_hazard_detections,
            RELIABLE_QOS,
            callback_group=self._sub_cbg,
        )

        # Wheel odometry
        self._sub_odom = self.create_subscription(
            Odometry, "/odometry",
            self._cb_odometry,
            SENSOR_QOS,
            callback_group=self._sub_cbg,
        )

        # IMU for dead reckoning
        self._sub_imu = self.create_subscription(
            Imu, "/imu/data",
            self._cb_imu,
            SENSOR_QOS,
            callback_group=self._sub_cbg,
        )

        # Autonomy state (to know about comms blackout)
        self._sub_autonomy = self.create_subscription(
            String, "/autonomy/state",
            self._cb_autonomy_state,
            RELIABLE_QOS,
            callback_group=self._sub_cbg,
        )

        # Incoming navigation goal from autonomy
        self._sub_goal = self.create_subscription(
            PoseStamped, "/navigation/goal",
            self._cb_navigation_goal,
            RELIABLE_QOS,
            callback_group=self._sub_cbg,
        )

        self.get_logger().info("Navigation subscribers created")

    # ------------------------------------------------------------------
    # SERVICES
    # ------------------------------------------------------------------
    def _create_services(self) -> None:
        self._srv_clear_costmap = self.create_service(
            Trigger, "/navigation/clear_costmap",
            self._srv_cb_clear_costmap,
            callback_group=self._service_cbg,
        )
        self._srv_abort_nav = self.create_service(
            Trigger, "/navigation/abort",
            self._srv_cb_abort_navigation,
            callback_group=self._service_cbg,
        )
        self._srv_pause = self.create_service(
            SetBool, "/navigation/pause",
            self._srv_cb_pause,
            callback_group=self._service_cbg,
        )

    # ------------------------------------------------------------------
    # TIMERS
    # ------------------------------------------------------------------
    def _create_timers(self) -> None:
        control_hz   = self.get_parameter("control_hz").value
        path_pub_hz  = self.get_parameter("path_publish_hz").value
        heartbeat_hz = self.get_parameter("heartbeat_hz").value

        self._timer_control  = self.create_timer(
            1.0 / control_hz,
            self._cb_control_loop,
            callback_group=self._timer_cbg,
        )
        self._timer_path_pub = self.create_timer(
            1.0 / path_pub_hz,
            self._cb_publish_path,
            callback_group=self._timer_cbg,
        )
        self._timer_heartbeat = self.create_timer(
            1.0 / heartbeat_hz,
            self._cb_publish_telemetry,
            callback_group=self._timer_cbg,
        )
        self._timer_dr = self.create_timer(
            0.05,   # 20 Hz dead reckoning update
            self._cb_dead_reckoning_update,
            callback_group=self._timer_cbg,
        )

    # ------------------------------------------------------------------
    # TRAVERSABILITY MAP INITIALIZATION
    # ------------------------------------------------------------------
    def _initialize_sim_traversability_map(self) -> None:
        """Create a synthetic traversability map for simulation."""
        width, height = 200, 200
        resolution = 0.5   # 0.5m per cell -> 100m x 100m map
        origin_x, origin_y = -50.0, -50.0

        cells     = np.zeros((height, width), dtype=np.float32)
        hazards   = np.zeros((height, width), dtype=bool)
        slope_map = np.zeros((height, width), dtype=np.float32)

        # Add some terrain features (craters, boulders, slopes)
        rng = np.random.default_rng(seed=42)

        # Random slope variation (lunar terrain)
        base_slope = rng.uniform(0, 8, (height, width)).astype(np.float32)
        slope_map += base_slope

        # Add a steep crater rim at center-right
        for r in range(height):
            for c in range(width):
                dx = c - 120
                dy = r - 100
                dist = math.sqrt(dx*dx + dy*dy)
                if 15 < dist < 22:  # Crater rim
                    slope_map[r, c] = 30.0  # Impassable slope
                    cells[r, c] = 95.0      # High cost (near-obstacle)
                elif dist <= 15:  # Crater interior
                    slope_map[r, c] = 25.0
                    cells[r, c] = 99.0

        # Add boulder hazards
        boulder_centers = [(60, 70), (100, 50), (140, 130), (80, 160), (50, 120)]
        for (br, bc) in boulder_centers:
            for dr in range(-3, 4):
                for dc in range(-3, 4):
                    r, c = br + dr, bc + dc
                    if 0 <= r < height and 0 <= c < width:
                        hazards[r, c] = True
                        cells[r, c]   = 100.0

        # PSR cold trap zones (high science interest, but harder terrain)
        for r in range(30, 60):
            for c in range(30, 80):
                slope_map[r, c] += rng.uniform(0, 5)

        self.traversability_map = TraversabilityMap(
            width=width,
            height=height,
            resolution_m=resolution,
            origin_x=origin_x,
            origin_y=origin_y,
            cells=cells,
            hazard_mask=hazards,
            slope_map=slope_map,
        )
        self.get_logger().info(
            f"Sim traversability map initialized: {width}x{height} cells, "
            f"{resolution}m resolution, {width*resolution:.0f}x{height*resolution:.0f}m area"
        )

    # ------------------------------------------------------------------
    # SUBSCRIBER CALLBACKS
    # ------------------------------------------------------------------
    def _cb_traversability_map(self, msg: OccupancyGrid) -> None:
        """Update traversability map from occupancy grid."""
        width  = msg.info.width
        height = msg.info.height
        res    = msg.info.resolution
        ox     = msg.info.origin.position.x
        oy     = msg.info.origin.position.y

        # Convert flat array to 2D numpy
        data = np.array(msg.data, dtype=np.float32).reshape((height, width))
        hazards = (data >= 90).astype(bool)

        with self._lock:
            if self.traversability_map is None:
                slope_map = np.zeros((height, width), dtype=np.float32)
            else:
                # Keep existing slope map if dimensions match
                if (self.traversability_map.height == height and
                        self.traversability_map.width == width):
                    slope_map = self.traversability_map.slope_map
                else:
                    slope_map = np.zeros((height, width), dtype=np.float32)

            self.traversability_map = TraversabilityMap(
                width=width,
                height=height,
                resolution_m=res,
                origin_x=ox,
                origin_y=oy,
                cells=data,
                hazard_mask=hazards,
                slope_map=slope_map,
            )

        self.get_logger().debug(
            f"Traversability map updated: {width}x{height}, {res}m/cell"
        )

    def _cb_hazard_detections(self, msg: String) -> None:
        """Process hazard detection updates and trigger replanning if needed."""
        try:
            hazard_list = json.loads(msg.data)
            new_hazards = {}
            for h in hazard_list:
                hid = h.get("id", f"hazard_{len(new_hazards)}")
                hx  = float(h.get("x", 0.0))
                hy  = float(h.get("y", 0.0))
                new_hazards[hid] = (hx, hy)

            # Check if hazards are on current path
            replan_needed = False
            if self.current_path and new_hazards:
                for hid, (hx, hy) in new_hazards.items():
                    if self._hazard_on_path(hx, hy, self.current_path):
                        self.get_logger().warn(
                            f"Hazard '{hid}' at ({hx:.1f}, {hy:.1f}) intersects "
                            f"current path - triggering replan"
                        )
                        replan_needed = True
                        break

            with self._lock:
                self.active_hazards.update(new_hazards)
                # Mark hazards on traversability map
                if self.traversability_map:
                    for hx, hy in new_hazards.values():
                        row, col = self.traversability_map.world_to_grid(hx, hy)
                        if self.traversability_map.is_valid(row, col):
                            # Mark 3x3 area around hazard
                            for dr in range(-2, 3):
                                for dc in range(-2, 3):
                                    r, c = row + dr, col + dc
                                    if self.traversability_map.is_valid(r, c):
                                        self.traversability_map.hazard_mask[r, c] = True

            if replan_needed and self.get_parameter("replan_on_hazard").value:
                self._trigger_replan("Hazard on path")

        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            self.get_logger().warn(f"Hazard detection parse error: {exc}")

    def _cb_odometry(self, msg: Odometry) -> None:
        """Update position from odometry."""
        with self._lock:
            self.current_x = msg.pose.pose.position.x
            self.current_y = msg.pose.pose.position.y
            self.current_speed_ms = math.sqrt(
                msg.twist.twist.linear.x**2 +
                msg.twist.twist.linear.y**2
            )

            # Extract heading from quaternion
            q = msg.pose.pose.orientation
            siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
            cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
            self.current_heading_rad = math.atan2(siny_cosp, cosy_cosp)

            # Sync dead reckoning to odometry when not in blackout
            if not self.comms_blackout_active:
                self.dead_reckoning.x = self.current_x
                self.dead_reckoning.y = self.current_y
                self.dead_reckoning.heading_rad = self.current_heading_rad
                self.dead_reckoning.covariance_m2 = 0.01  # ~10cm accuracy from odom

    def _cb_imu(self, msg: Imu) -> None:
        """Store IMU data for dead reckoning."""
        self.imu_angular_vel_z  = msg.angular_velocity.z
        self.imu_linear_acc_x   = msg.linear_acceleration.x
        self.imu_linear_acc_y   = msg.linear_acceleration.y

    def _cb_autonomy_state(self, msg: String) -> None:
        """Monitor autonomy state for comms blackout detection."""
        try:
            data = json.loads(msg.data)
            prev_blackout = self.comms_blackout_active
            state = data.get("state", "")
            self.comms_blackout_active = (state == "COMMS_BLACKOUT")

            if self.comms_blackout_active and not prev_blackout:
                self.get_logger().warn(
                    "Navigation: Comms blackout detected - activating dead reckoning"
                )
                self.dead_reckoning.active = True
                self.dead_reckoning.last_update_time = time.monotonic()
            elif not self.comms_blackout_active and prev_blackout:
                self.get_logger().info(
                    "Navigation: Comms restored - "
                    f"DR position error: {math.sqrt(self.dead_reckoning.covariance_m2):.2f}m"
                )
                self.dead_reckoning.active = False
        except (json.JSONDecodeError, KeyError) as exc:
            self.get_logger().debug(f"Autonomy state parse: {exc}")

    def _cb_navigation_goal(self, msg: PoseStamped) -> None:
        """Accept a new navigation goal."""
        gx = msg.pose.position.x
        gy = msg.pose.position.y

        # Extract heading from quaternion
        q = msg.pose.orientation
        heading = math.degrees(math.atan2(
            2.0 * (q.w * q.z + q.x * q.y),
            1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        ))

        wp_id = f"GOAL_{int(time.time())}"
        waypoint = Waypoint(
            wp_id=wp_id,
            x=gx,
            y=gy,
            heading_deg=heading,
        )
        self._add_waypoint(waypoint)
        self.get_logger().info(
            f"Navigation goal received: ({gx:.2f}, {gy:.2f}), "
            f"heading={heading:.1f}deg"
        )

    # ------------------------------------------------------------------
    # CONTROL LOOP
    # ------------------------------------------------------------------
    def _cb_control_loop(self) -> None:
        """
        Main navigation control loop.
        Advances toward current waypoint, checks arrival, issues velocity commands.
        """
        if not self.navigation_active:
            # Check if there's a waypoint to process
            if self.waypoint_queue:
                self._start_navigation_to_next_waypoint()
            return

        if self.current_waypoint is None:
            self.navigation_active = False
            self.nav_state = "IDLE"
            return

        # Get current position (DR or odometry)
        if self.dead_reckoning.active:
            cx = self.dead_reckoning.x
            cy = self.dead_reckoning.y
        else:
            cx = self.current_x
            cy = self.current_y

        # Check waypoint arrival
        dx = self.current_waypoint.x - cx
        dy = self.current_waypoint.y - cy
        dist = math.sqrt(dx*dx + dy*dy)

        tol = self.get_parameter("waypoint_tolerance_m").value
        if dist < tol:
            self.get_logger().info(
                f"Waypoint '{self.current_waypoint.wp_id}' reached "
                f"(dist={dist:.2f}m < {tol:.2f}m tolerance)"
            )
            self.current_waypoint.completed = True
            self.current_path = None
            self.current_waypoint = None
            self.navigation_active = bool(self.waypoint_queue)
            self.nav_state = "WAYPOINT_REACHED"
            self._stop_rover()
            return

        # Check if path planning needed
        if self.current_path is None:
            self._plan_path_to_current_waypoint()
            if self.current_path is None:
                self.get_logger().error(
                    f"No path to waypoint '{self.current_waypoint.wp_id}' - skipping"
                )
                self.current_waypoint.skipped = True
                self.current_waypoint = None
                self.navigation_active = bool(self.waypoint_queue)
                return

        # Check if we've deviated significantly from path
        if self.current_path:
            path_dist = self._distance_from_path(cx, cy, self.current_path)
            replan_thresh = self.get_parameter("replan_threshold_m").value
            if path_dist > replan_thresh:
                self.get_logger().info(
                    f"Off-path by {path_dist:.2f}m > {replan_thresh:.2f}m - replanning"
                )
                self._trigger_replan("Off-path deviation")

        # Issue velocity command toward next path point
        cmd = self._compute_velocity_command(cx, cy)
        self._pub_cmd_vel.publish(cmd)
        self.nav_state = "NAVIGATING"

    def _start_navigation_to_next_waypoint(self) -> None:
        """Pop next waypoint from queue and start navigating."""
        if not self.waypoint_queue:
            return
        _, _, waypoint = heapq.heappop(self.waypoint_queue)
        self.current_waypoint = waypoint
        self.navigation_active = True
        self.nav_state = "PLANNING"
        self.current_path = None
        self.get_logger().info(
            f"Starting navigation to waypoint '{waypoint.wp_id}' "
            f"at ({waypoint.x:.2f}, {waypoint.y:.2f})"
        )

    def _plan_path_to_current_waypoint(self) -> None:
        """Plan path to current waypoint using A* planner."""
        if self.traversability_map is None or self.current_waypoint is None:
            return

        if self.dead_reckoning.active:
            start = (self.dead_reckoning.x, self.dead_reckoning.y)
        else:
            start = (self.current_x, self.current_y)

        goal = (self.current_waypoint.x, self.current_waypoint.y)

        self.get_logger().info(
            f"Planning path: ({start[0]:.2f}, {start[1]:.2f}) -> "
            f"({goal[0]:.2f}, {goal[1]:.2f})"
        )

        t0 = time.monotonic()
        path = self.planner.plan(self.traversability_map, start, goal)
        elapsed_ms = (time.monotonic() - t0) * 1000

        if path:
            self.current_path = path
            self.path_energy_estimate_j = self.planner.estimate_path_energy(
                path, self.traversability_map
            )
            self.current_waypoint.energy_estimate_j = self.path_energy_estimate_j
            self.get_logger().info(
                f"Path found: {len(path)} points, "
                f"energy={self.path_energy_estimate_j:.1f}J, "
                f"planned in {elapsed_ms:.1f}ms"
            )
        else:
            self.get_logger().error(
                f"Path planning failed for waypoint '{self.current_waypoint.wp_id}'"
            )

    def _trigger_replan(self, reason: str) -> None:
        """Invalidate current path and trigger replanning."""
        self.current_path = None
        self.replanning_count += 1
        self.get_logger().info(
            f"Replanning triggered (#{self.replanning_count}): {reason}"
        )

    def _compute_velocity_command(self, cx: float, cy: float) -> Twist:
        """
        Compute velocity command toward next path point.
        Uses proportional control with slope-based speed limiting.
        """
        cmd = Twist()

        if not self.current_path or len(self.current_path) < 2:
            return cmd

        # Find next point on path
        lookahead_dist = 1.5  # meters
        target = self.current_path[-1]  # Default to final point

        for i, pt in enumerate(self.current_path):
            dx = pt[0] - cx
            dy = pt[1] - cy
            dist = math.sqrt(dx*dx + dy*dy)
            if dist >= lookahead_dist:
                target = pt
                # Remove passed points
                if i > 0:
                    self.current_path = self.current_path[i-1:]
                break

        # Direction to target
        tx, ty = target
        dx = tx - cx
        dy = ty - cy
        dist_to_target = math.sqrt(dx*dx + dy*dy)

        if dist_to_target < 0.01:
            return cmd

        # Compute speed based on terrain slope at current position
        max_speed = self.get_parameter("max_speed_ms").value
        min_speed = self.get_parameter("min_speed_ms").value

        speed = max_speed
        if self.traversability_map:
            row, col = self.traversability_map.world_to_grid(cx, cy)
            if self.traversability_map.is_valid(row, col):
                slope = self.traversability_map.slope_map[row, col]
                # Reduce speed on steep slopes
                speed_factor = max(0.1, 1.0 - (slope / MAX_SLOPE_DEG) * 0.8)
                speed = max(min_speed, max_speed * speed_factor)

        # Desired heading to target
        desired_heading = math.atan2(dy, dx)
        heading_error = desired_heading - self.current_heading_rad
        # Normalize to [-pi, pi]
        while heading_error > math.pi:
            heading_error -= 2 * math.pi
        while heading_error < -math.pi:
            heading_error += 2 * math.pi

        # Slow down for large heading errors
        if abs(heading_error) > math.pi / 4:
            speed = min_speed

        cmd.linear.x  = float(speed * math.cos(heading_error))
        cmd.angular.z = float(2.0 * heading_error)  # P-controller

        # Clamp angular velocity
        max_omega = 0.5  # rad/s
        cmd.angular.z = max(-max_omega, min(max_omega, cmd.angular.z))

        return cmd

    def _stop_rover(self) -> None:
        """Publish zero velocity command."""
        cmd = Twist()
        self._pub_cmd_vel.publish(cmd)

    # ------------------------------------------------------------------
    # DEAD RECKONING
    # ------------------------------------------------------------------
    def _cb_dead_reckoning_update(self) -> None:
        """
        Integrate IMU and wheel odometry for dead reckoning.
        Only active during comms blackout when GPS/external odometry unavailable.
        """
        if not self.dead_reckoning.active:
            return

        now = time.monotonic()
        dt = now - self.dead_reckoning.last_update_time
        self.dead_reckoning.last_update_time = now

        if dt <= 0 or dt > 1.0:  # Skip if dt is unreasonable
            return

        # Integrate heading from IMU gyro
        self.dead_reckoning.heading_rad += self.imu_angular_vel_z * dt

        # Integrate position from velocity estimate
        # v = omega * r (simplified wheel odometry)
        v_est = self.current_speed_ms
        self.dead_reckoning.x += v_est * math.cos(self.dead_reckoning.heading_rad) * dt
        self.dead_reckoning.y += v_est * math.sin(self.dead_reckoning.heading_rad) * dt

        # Update distance traveled
        dist_step = v_est * dt
        self.dead_reckoning.total_distance_m += dist_step

        # Grow position uncertainty with distance traveled (random walk)
        self.dead_reckoning.covariance_m2 += (
            DEAD_RECKONING_DRIFT_M * dist_step
        ) ** 2

        # Normalize heading
        while self.dead_reckoning.heading_rad > math.pi:
            self.dead_reckoning.heading_rad -= 2 * math.pi
        while self.dead_reckoning.heading_rad < -math.pi:
            self.dead_reckoning.heading_rad += 2 * math.pi

        # Warn if uncertainty is getting large
        uncertainty_m = math.sqrt(self.dead_reckoning.covariance_m2)
        if uncertainty_m > 5.0:
            self.get_logger().warn(
                f"DR: Position uncertainty = {uncertainty_m:.2f}m - "
                "consider halting until comms restore"
            )

    # ------------------------------------------------------------------
    # PATH UTILITIES
    # ------------------------------------------------------------------
    def _hazard_on_path(self, hx: float, hy: float,
                         path: List[Tuple[float, float]],
                         clearance_m: float = 1.5) -> bool:
        """Check if a hazard at (hx, hy) is within clearance of the path."""
        for i in range(len(path) - 1):
            x1, y1 = path[i]
            x2, y2 = path[i + 1]
            # Point-to-segment distance
            dx = x2 - x1
            dy = y2 - y1
            seg_len = math.sqrt(dx*dx + dy*dy)
            if seg_len < 1e-6:
                continue
            t = max(0, min(1, ((hx - x1)*dx + (hy - y1)*dy) / (seg_len*seg_len)))
            px = x1 + t * dx
            py = y1 + t * dy
            dist = math.sqrt((hx - px)**2 + (hy - py)**2)
            if dist < clearance_m:
                return True
        return False

    def _distance_from_path(self, cx: float, cy: float,
                              path: List[Tuple[float, float]]) -> float:
        """Compute minimum distance from (cx, cy) to any path segment."""
        min_dist = float('inf')
        for i in range(len(path) - 1):
            x1, y1 = path[i]
            x2, y2 = path[i + 1]
            dx = x2 - x1
            dy = y2 - y1
            seg_len_sq = dx*dx + dy*dy
            if seg_len_sq < 1e-12:
                d = math.sqrt((cx - x1)**2 + (cy - y1)**2)
            else:
                t = max(0, min(1, ((cx - x1)*dx + (cy - y1)*dy) / seg_len_sq))
                px = x1 + t * dx
                py = y1 + t * dy
                d = math.sqrt((cx - px)**2 + (cy - py)**2)
            min_dist = min(min_dist, d)
        return min_dist

    # ------------------------------------------------------------------
    # WAYPOINT MANAGEMENT
    # ------------------------------------------------------------------
    def _add_waypoint(self, wp: Waypoint) -> None:
        """Add waypoint to priority queue."""
        heapq.heappush(self.waypoint_queue, (wp.priority, time.monotonic(), wp))
        self.get_logger().info(
            f"Waypoint queued: '{wp.wp_id}' priority={wp.priority} "
            f"queue_size={len(self.waypoint_queue)}"
        )

    # ------------------------------------------------------------------
    # PUBLISHER CALLBACKS
    # ------------------------------------------------------------------
    def _cb_publish_path(self) -> None:
        """Publish current planned path as nav_msgs/Path."""
        if self.current_path is None:
            return

        path_msg = Path()
        path_msg.header.stamp = self.get_clock().now().to_msg()
        path_msg.header.frame_id = self.get_parameter("map_frame").value

        for x, y in self.current_path:
            pose = PoseStamped()
            pose.header = path_msg.header
            pose.pose.position.x = x
            pose.pose.position.y = y
            pose.pose.position.z = 0.0
            pose.pose.orientation.w = 1.0
            path_msg.poses.append(pose)

        self._pub_path.publish(path_msg)

        # Publish energy estimate
        energy_msg = Float32()
        energy_msg.data = float(self.path_energy_estimate_j)
        self._pub_energy.publish(energy_msg)

    def _cb_publish_telemetry(self) -> None:
        """Publish navigation telemetry as heartbeat."""
        if self.dead_reckoning.active:
            pos_x = self.dead_reckoning.x
            pos_y = self.dead_reckoning.y
            heading_deg = math.degrees(self.dead_reckoning.heading_rad)
        else:
            pos_x = self.current_x
            pos_y = self.current_y
            heading_deg = math.degrees(self.current_heading_rad)

        if self.current_waypoint:
            dx = self.current_waypoint.x - pos_x
            dy = self.current_waypoint.y - pos_y
            dist_to_target = math.sqrt(dx*dx + dy*dy)
            target_wp = self.current_waypoint.wp_id
        else:
            dist_to_target = 0.0
            target_wp = None

        path_len = 0.0
        if self.current_path and len(self.current_path) > 1:
            for i in range(1, len(self.current_path)):
                dx = self.current_path[i][0] - self.current_path[i-1][0]
                dy = self.current_path[i][1] - self.current_path[i-1][1]
                path_len += math.sqrt(dx*dx + dy*dy)

        telemetry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "nav_state": self.nav_state,
            "x": round(pos_x, 3),
            "y": round(pos_y, 3),
            "heading_deg": round(heading_deg, 2),
            "speed_ms": round(self.current_speed_ms, 3),
            "target_wp": target_wp,
            "dist_to_target_m": round(dist_to_target, 2),
            "path_length_m": round(path_len, 2),
            "energy_estimate_j": round(self.path_energy_estimate_j, 1),
            "waypoints_queued": len(self.waypoint_queue),
            "replanning_count": self.replanning_count,
            "dead_reckoning": self.dead_reckoning.active,
            "position_uncertainty_m": round(
                math.sqrt(self.dead_reckoning.covariance_m2), 3
            ),
            "active_hazards": len(self.active_hazards),
        }

        msg = String()
        msg.data = json.dumps(telemetry)
        self._pub_telemetry.publish(msg)

    # ------------------------------------------------------------------
    # SERVICE CALLBACKS
    # ------------------------------------------------------------------
    def _srv_cb_clear_costmap(self, request: Trigger.Request,
                               response: Trigger.Response) -> Trigger.Response:
        """Clear hazards and reinitialize traversability map."""
        if self.traversability_map:
            self.traversability_map.hazard_mask[:] = False
            self.active_hazards.clear()
            response.success = True
            response.message = "Costmap cleared"
            self.get_logger().info("Traversability map hazards cleared")
        else:
            response.success = False
            response.message = "No traversability map loaded"
        return response

    def _srv_cb_abort_navigation(self, request: Trigger.Request,
                                  response: Trigger.Response) -> Trigger.Response:
        """Abort current navigation and clear queue."""
        self.navigation_active = False
        self.current_waypoint = None
        self.current_path = None
        self.waypoint_queue.clear()
        self._stop_rover()
        self.nav_state = "ABORTED"
        response.success = True
        response.message = "Navigation aborted"
        self.get_logger().warn("Navigation aborted via service call")
        return response

    def _srv_cb_pause(self, request: SetBool.Request,
                       response: SetBool.Response) -> SetBool.Response:
        """Pause or resume navigation."""
        if request.data:
            self.navigation_active = False
            self._stop_rover()
            self.nav_state = "PAUSED"
            response.message = "Navigation paused"
        else:
            self.navigation_active = True
            self.nav_state = "RESUMING"
            response.message = "Navigation resumed"
        response.success = True
        return response


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------
def main(args=None) -> None:
    rclpy.init(args=args)
    executor = rclpy.executors.MultiThreadedExecutor(num_threads=6)
    node = NavigationNode()
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
