"""
LPAS Full Simulation Launch File

Startup sequence:
  1. Gazebo Fortress + lunar south pole world
  2. Robot state publisher (URDF → TF)
  3. ros_gz_bridge (/clock + sensor topics)
  4. Rover spawn in Gazebo
  5. Safety / power nodes (immediate)
  6. Wheel control, hazard detection, navigation (immediate)
  7. Autonomy manager + lifecycle manager (immediate)
  8. Nav2 + SLAM Toolbox (delayed 15 s — wait for Gazebo + odom TF)
  9. RViz2
"""
from __future__ import annotations

import os
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    IncludeLaunchDescription,
    RegisterEventHandler,
    TimerAction,
)
from launch.conditions import IfCondition, UnlessCondition
from launch.event_handlers import OnProcessExit, OnShutdown
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    Command,
    FindExecutable,
    LaunchConfiguration,
    PathJoinSubstitution,
)
from launch_ros.actions import LifecycleNode, Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare

BRINGUP_PKG  = get_package_share_directory("lunar_scout_bringup")
DESC_PKG     = get_package_share_directory("lunar_scout_description")

# Resolve workspace root: share/lunar_scout_bringup is 4 levels deep inside install/
GAZEBO_WORLDS = Path(BRINGUP_PKG).parents[3] / "src" / "gazebo_worlds" / "lunar_south_pole"
# Fallback: repo root relative to the description package install location
if not GAZEBO_WORLDS.exists():
    GAZEBO_WORLDS = Path(BRINGUP_PKG).parents[4] / "gazebo_worlds" / "lunar_south_pole"

ONNX_MODEL_PATH = str(
    Path(DESC_PKG).parents[3] / "src" / "autonomy_models" / "onnx_exports" / "hazard_detection.onnx"
)


def generate_launch_description() -> LaunchDescription:
    # ── Launch arguments ──────────────────────────────────────────────────────
    use_sim_time = LaunchConfiguration("use_sim_time", default="true")
    headless     = LaunchConfiguration("headless",     default="false")
    use_rviz     = LaunchConfiguration("use_rviz",     default="true")
    log_level    = LaunchConfiguration("log_level",    default="info")
    world_file   = LaunchConfiguration(
        "world_file",
        default=str(GAZEBO_WORLDS / "lunar_south_pole.world"),
    )

    declare_use_sim_time = DeclareLaunchArgument("use_sim_time", default_value="true")
    declare_headless     = DeclareLaunchArgument("headless",     default_value="false")
    declare_use_rviz     = DeclareLaunchArgument("use_rviz",     default_value="true")
    declare_log_level    = DeclareLaunchArgument("log_level",    default_value="info")
    declare_world        = DeclareLaunchArgument(
        "world_file",
        default_value=str(GAZEBO_WORLDS / "lunar_south_pole.world"),
    )

    # ── Gazebo ────────────────────────────────────────────────────────────────
    # Headless mode: server only (no GUI), useful for CI or remote machines
    gazebo_headless = ExecuteProcess(
        cmd=["ign", "gazebo", "-r", "-s", world_file, "--headless-rendering"],
        condition=IfCondition(headless),
        output="screen",
    )
    # GUI mode: full Gazebo window
    gazebo_gui = ExecuteProcess(
        cmd=["ign", "gazebo", "-r", world_file],
        condition=UnlessCondition(headless),
        output="screen",
        additional_env={"IGN_GAZEBO_RESOURCE_PATH": str(GAZEBO_WORLDS.parent)},
    )

    # ── ros_gz_bridge — /clock + sensor bridges ───────────────────────────────
    # The /clock bridge is required for use_sim_time to work in all ROS2 nodes.
    ros_gz_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="ros_gz_bridge",
        output="screen",
        parameters=[{"use_sim_time": use_sim_time}],
        arguments=[
            "/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock",
            "/scan@sensor_msgs/msg/LaserScan[ignition.msgs.LaserScan",
            "/stereo/left/image_raw@sensor_msgs/msg/Image[ignition.msgs.Image",
            "/stereo/right/image_raw@sensor_msgs/msg/Image[ignition.msgs.Image",
            "/imu/data@sensor_msgs/msg/Imu[ignition.msgs.IMU",
        ],
    )

    # ── Robot description ─────────────────────────────────────────────────────
    robot_description = Command([
        FindExecutable(name="xacro"), " ",
        PathJoinSubstitution([
            FindPackageShare("lunar_scout_description"),
            "urdf", "lunar_scout.urdf.xacro",
        ]),
        " use_sim_time:=", use_sim_time,
    ])

    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        output="screen",
        parameters=[{
            "robot_description": ParameterValue(robot_description, value_type=str),
            "use_sim_time": use_sim_time,
            "publish_frequency": 50.0,
        }],
    )

    # ── Spawn rover in Gazebo ─────────────────────────────────────────────────
    # Delayed 5 s to ensure Gazebo is ready before spawn
    spawn_rover = TimerAction(
        period=5.0,
        actions=[
            Node(
                package="ros_gz_sim",
                executable="create",
                name="spawn_lpas_rover",
                arguments=[
                    "-topic", "robot_description",
                    "-name",  "lpas_rover",
                    "-x", "0.0", "-y", "0.0", "-z", "0.5",
                    "-R", "0.0", "-P", "0.0", "-Y", "0.0",
                ],
                output="screen",
            ),
        ],
    )

    # ── LPAS Safety-critical nodes (start immediately) ────────────────────────
    fault_detection_node = LifecycleNode(
        package="lunar_scout_fault_detection",
        executable="fault_detection_node.py",
        prefix="python3",
        name="fault_detection_node",
        namespace="lpas",
        output="screen",
        parameters=[{"use_sim_time": use_sim_time}],
        arguments=["--ros-args", "--log-level", log_level],
    )

    # Regular Node (not lifecycle) — starts publishing power state immediately
    power_management_node = Node(
        package="lunar_scout_power_management",
        executable="power_management_node.py",
        prefix="python3",
        name="power_management_node",
        namespace="lpas",
        output="screen",
        parameters=[{"use_sim_time": use_sim_time}],
    )

    thermal_monitor_node = LifecycleNode(
        package="lunar_scout_thermal_monitor",
        executable="thermal_monitor_node.py",
        prefix="python3",
        name="thermal_monitor_node",
        namespace="lpas",
        output="screen",
        parameters=[{
            "use_sim_time": use_sim_time,
            "psr_environment_temp_c": -230.0,
        }],
    )

    comms_node = LifecycleNode(
        package="lunar_scout_comms",
        executable="comms_node.py",
        prefix="python3",
        name="comms_node",
        namespace="lpas",
        output="screen",
        parameters=[{"use_sim_time": use_sim_time}],
    )

    # ── Mobility ──────────────────────────────────────────────────────────────
    wheel_control_node = LifecycleNode(
        package="lunar_scout_wheel_control",
        executable="wheel_control_node.py",
        prefix="python3",
        name="wheel_control_node",
        namespace="lpas",
        output="screen",
        parameters=[{
            "use_sim_time": use_sim_time,
            "max_linear_speed_m_s": 0.5,
            "max_angular_speed_rad_s": 0.3,
        }],
    )

    # ── Perception ────────────────────────────────────────────────────────────
    terrain_segmentation_node = Node(
        package="lunar_scout_hazard_detection",
        executable="terrain_segmentation_node.py",
        prefix="python3",
        name="terrain_segmentation_node",
        namespace="lpas",
        output="screen",
        parameters=[{"use_sim_time": use_sim_time}],
    )

    hazard_detection_node = LifecycleNode(
        package="lunar_scout_hazard_detection",
        executable="hazard_detection_node.py",
        prefix="python3",
        name="hazard_detection_node",
        namespace="lpas",
        output="screen",
        parameters=[{
            "use_sim_time": use_sim_time,
            "detection_confidence_threshold": 0.75,
            "emergency_stop_distance_m": 2.0,
            # Parameter name must match what the node declares: "model_path"
            "model_path": ONNX_MODEL_PATH,
        }],
    )

    # ── Navigation proxy node ─────────────────────────────────────────────────
    navigation_node = Node(
        package="lunar_scout_navigation",
        executable="navigation_node.py",
        prefix="python3",
        name="navigation_node",
        namespace="lpas",
        output="screen",
        parameters=[{
            "use_sim_time": use_sim_time,
            "max_slope_deg": 20.0,
        }],
    )

    # ── Top-level autonomy ────────────────────────────────────────────────────
    autonomy_manager_node = LifecycleNode(
        package="lunar_scout_autonomy",
        executable="autonomy_manager_node.py",
        prefix="python3",
        name="autonomy_manager_node",
        namespace="lpas",
        output="screen",
        parameters=[{"use_sim_time": use_sim_time}],
    )

    # ── Lifecycle manager — configures and activates all lifecycle nodes ───────
    # bond_timeout increased to 8 s to handle ONNX model loading latency.
    lifecycle_manager = Node(
        package="nav2_lifecycle_manager",
        executable="lifecycle_manager",
        name="lifecycle_manager_lpas",
        output="screen",
        parameters=[{
            "use_sim_time": use_sim_time,
            "autostart": True,
            "node_names": [
                "lpas/fault_detection_node",
                "lpas/thermal_monitor_node",
                "lpas/comms_node",
                "lpas/wheel_control_node",
                "lpas/hazard_detection_node",
                "lpas/autonomy_manager_node",
            ],
            "bond_timeout": 8.0,
            "attempt_respawn_reconnection": True,
        }],
    )

    # ── Nav2 + SLAM — delayed 15 s to ensure odom TF is live ─────────────────
    nav2_launch = TimerAction(
        period=15.0,
        actions=[
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource([
                    PathJoinSubstitution([
                        FindPackageShare("nav2_bringup"),
                        "launch",
                        "navigation_launch.py",
                    ])
                ]),
                launch_arguments={
                    "use_sim_time": use_sim_time,
                    "params_file": PathJoinSubstitution([
                        FindPackageShare("lunar_scout_bringup"),
                        "config", "nav2_params.yaml",
                    ]),
                }.items(),
            ),
        ],
    )

    slam_toolbox = TimerAction(
        period=15.0,
        actions=[
            Node(
                package="slam_toolbox",
                executable="async_slam_toolbox_node",
                name="slam_toolbox",
                output="screen",
                parameters=[{
                    "use_sim_time": use_sim_time,
                    "solver_plugin": "solver_plugins::CeresSolver",
                    "ceres_linear_solver": "SPARSE_NORMAL_CHOLESKY",
                    "ceres_preconditioner": "SCHUR_JACOBI",
                    "transform_publish_period": 0.02,
                    "map_update_interval": 5.0,
                    "resolution": 0.05,
                    "max_laser_range": 30.0,
                }],
            ),
        ],
    )

    # ── Diagnostics aggregator ────────────────────────────────────────────────
    diagnostic_aggregator = Node(
        package="diagnostic_aggregator",
        executable="aggregator_node",
        name="diagnostic_aggregator",
        parameters=[{
            "use_sim_time": use_sim_time,
            "analyzers": {
                "power":   {"type": "diagnostic_aggregator/GenericAnalyzer",
                            "path": "Power",   "contains": ["power"]},
                "thermal": {"type": "diagnostic_aggregator/GenericAnalyzer",
                            "path": "Thermal", "contains": ["thermal"]},
                "comms":   {"type": "diagnostic_aggregator/GenericAnalyzer",
                            "path": "Comms",   "contains": ["comms"]},
            },
        }],
    )

    # ── RViz2 — delayed slightly to let robot model come up ───────────────────
    rviz_node = TimerAction(
        period=8.0,
        actions=[
            Node(
                package="rviz2",
                executable="rviz2",
                name="rviz2",
                condition=IfCondition(use_rviz),
                arguments=[
                    "-d",
                    PathJoinSubstitution([
                        FindPackageShare("lunar_scout_bringup"),
                        "config", "lpas_rviz.rviz",
                    ]),
                ],
                parameters=[{"use_sim_time": use_sim_time}],
                output="screen",
            ),
        ],
    )

    return LaunchDescription([
        # Arguments
        declare_use_sim_time,
        declare_headless,
        declare_use_rviz,
        declare_log_level,
        declare_world,
        # Simulation infrastructure
        gazebo_headless,
        gazebo_gui,
        ros_gz_bridge,
        robot_state_publisher,
        spawn_rover,
        # Safety-critical (start immediately)
        fault_detection_node,
        power_management_node,
        thermal_monitor_node,
        comms_node,
        # Mobility
        wheel_control_node,
        # Perception
        terrain_segmentation_node,
        hazard_detection_node,
        # Navigation proxy
        navigation_node,
        # Top-level
        autonomy_manager_node,
        # Lifecycle management
        lifecycle_manager,
        # Diagnostics
        diagnostic_aggregator,
        # Nav2 + SLAM (delayed — wait for odom TF to be live)
        nav2_launch,
        slam_toolbox,
        # Visualization (delayed — wait for robot model)
        rviz_node,
    ])
