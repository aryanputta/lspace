"""
LPAS Full Simulation Launch File

Launches:
  1. Gazebo Fortress with lunar south pole world
  2. Robot state publisher (URDF → TF)
  3. All LPAS ROS2 lifecycle nodes
  4. Nav2 navigation stack
  5. SLAM Toolbox
  6. RViz2 with LPAS config
  7. Lifecycle manager (auto-activates all nodes)
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
from launch_ros.substitutions import FindPackageShare

BRINGUP_PKG = get_package_share_directory("lunar_scout_bringup")
DESC_PKG = get_package_share_directory("lunar_scout_description")

GAZEBO_WORLDS = Path(__file__).parent.parent.parent.parent.parent.parent / \
    "gazebo_worlds" / "lunar_south_pole"


def generate_launch_description() -> LaunchDescription:
    # ── Arguments ─────────────────────────────────────────────────────────────
    use_sim_time = LaunchConfiguration("use_sim_time", default="true")
    headless = LaunchConfiguration("headless", default="false")
    use_rviz = LaunchConfiguration("use_rviz", default="true")
    log_level = LaunchConfiguration("log_level", default="info")
    world_file = LaunchConfiguration(
        "world_file",
        default=str(GAZEBO_WORLDS / "lunar_south_pole.world"),
    )

    declare_use_sim_time = DeclareLaunchArgument("use_sim_time", default_value="true")
    declare_headless = DeclareLaunchArgument("headless", default_value="false")
    declare_use_rviz = DeclareLaunchArgument("use_rviz", default_value="true")
    declare_log_level = DeclareLaunchArgument("log_level", default_value="info")
    declare_world = DeclareLaunchArgument("world_file")

    # ── Gazebo ─────────────────────────────────────────────────────────────────
    gazebo = ExecuteProcess(
        cmd=[
            "gz", "sim", "-r",
            world_file,
            "--headless-rendering",
        ],
        condition=IfCondition(headless),
        output="screen",
    )
    gazebo_gui = ExecuteProcess(
        cmd=["gz", "sim", "-r", world_file],
        condition=UnlessCondition(headless),
        output="screen",
    )

    # ── Robot Description ──────────────────────────────────────────────────────
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
            "robot_description": robot_description,
            "use_sim_time": use_sim_time,
            "publish_frequency": 50.0,
        }],
    )

    # ── Spawn rover in Gazebo ──────────────────────────────────────────────────
    spawn_rover = Node(
        package="ros_gz_sim",
        executable="create",
        name="spawn_lpas_rover",
        arguments=[
            "-topic", "robot_description",
            "-name", "lpas_rover",
            "-x", "0.0", "-y", "0.0", "-z", "0.5",
            "-R", "0.0", "-P", "0.0", "-Y", "0.0",
        ],
        output="screen",
    )

    # ── LPAS Lifecycle Nodes ───────────────────────────────────────────────────
    fault_detection_node = LifecycleNode(
        package="lunar_scout_fault_detection",
        executable="fault_detection_node.py",
        name="fault_detection_node",
        namespace="lpas",
        output="screen",
        parameters=[{"use_sim_time": use_sim_time}],
        arguments=["--ros-args", "--log-level", log_level],
    )

    power_management_node = LifecycleNode(
        package="lunar_scout_power_management",
        executable="power_management_node.py",
        name="power_management_node",
        namespace="lpas",
        output="screen",
        parameters=[{"use_sim_time": use_sim_time}],
    )

    thermal_monitor_node = LifecycleNode(
        package="lunar_scout_thermal_monitor",
        executable="thermal_monitor_node.py",
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
        name="comms_node",
        namespace="lpas",
        output="screen",
        parameters=[{"use_sim_time": use_sim_time}],
    )

    hazard_detection_node = LifecycleNode(
        package="lunar_scout_hazard_detection",
        executable="hazard_detection_node.py",
        name="hazard_detection_node",
        namespace="lpas",
        output="screen",
        parameters=[{
            "use_sim_time": use_sim_time,
            "detection_confidence_threshold": 0.75,
            "emergency_stop_distance_m": 2.0,
            "onnx_model_path": str(
                Path(DESC_PKG).parent.parent.parent.parent /
                "autonomy_models" / "onnx_exports" / "hazard_detection.onnx"
            ),
        }],
    )

    terrain_segmentation_node = LifecycleNode(
        package="lunar_scout_hazard_detection",
        executable="terrain_segmentation_node.py",
        name="terrain_segmentation_node",
        namespace="lpas",
        output="screen",
        parameters=[{"use_sim_time": use_sim_time}],
    )

    wheel_control_node = LifecycleNode(
        package="lunar_scout_wheel_control",
        executable="wheel_control_node.py",
        name="wheel_control_node",
        namespace="lpas",
        output="screen",
        parameters=[{
            "use_sim_time": use_sim_time,
            "max_linear_speed_m_s": 0.5,
            "max_angular_speed_rad_s": 0.3,
        }],
    )

    autonomy_manager_node = LifecycleNode(
        package="lunar_scout_autonomy",
        executable="autonomy_manager_node.py",
        name="autonomy_manager_node",
        namespace="lpas",
        output="screen",
        parameters=[{"use_sim_time": use_sim_time}],
    )

    navigation_node = LifecycleNode(
        package="lunar_scout_navigation",
        executable="navigation_node.py",
        name="navigation_node",
        namespace="lpas",
        output="screen",
        parameters=[{
            "use_sim_time": use_sim_time,
            "max_slope_deg": 20.0,
        }],
    )

    # ── Nav2 Stack ─────────────────────────────────────────────────────────────
    nav2_launch = IncludeLaunchDescription(
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
    )

    # ── SLAM Toolbox ───────────────────────────────────────────────────────────
    slam_toolbox = Node(
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
    )

    # ── Lifecycle Manager ──────────────────────────────────────────────────────
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
                "lpas/power_management_node",
                "lpas/thermal_monitor_node",
                "lpas/comms_node",
                "lpas/wheel_control_node",
                "lpas/terrain_segmentation_node",
                "lpas/hazard_detection_node",
                "lpas/navigation_node",
                "lpas/autonomy_manager_node",
            ],
            "bond_timeout": 4.0,
            "attempt_respawn_reconnection": True,
        }],
    )

    # ── RViz2 ─────────────────────────────────────────────────────────────────
    rviz_node = Node(
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
    )

    # ── Diagnostics Aggregator ─────────────────────────────────────────────────
    diagnostic_aggregator = Node(
        package="diagnostic_aggregator",
        executable="aggregator_node",
        name="diagnostic_aggregator",
        parameters=[{
            "use_sim_time": use_sim_time,
            "analyzers": {
                "power": {"type": "diagnostic_aggregator/GenericAnalyzer",
                          "path": "Power", "contains": ["power"]},
                "thermal": {"type": "diagnostic_aggregator/GenericAnalyzer",
                            "path": "Thermal", "contains": ["thermal"]},
                "comms": {"type": "diagnostic_aggregator/GenericAnalyzer",
                          "path": "Comms", "contains": ["comms"]},
            },
        }],
    )

    return LaunchDescription([
        declare_use_sim_time,
        declare_headless,
        declare_use_rviz,
        declare_log_level,
        declare_world,
        # Simulation
        gazebo,
        gazebo_gui,
        robot_state_publisher,
        spawn_rover,
        # Safety-critical nodes first
        fault_detection_node,
        power_management_node,
        thermal_monitor_node,
        comms_node,
        # Mobility
        wheel_control_node,
        # Perception
        terrain_segmentation_node,
        hazard_detection_node,
        # Navigation
        slam_toolbox,
        nav2_launch,
        navigation_node,
        # Top-level
        autonomy_manager_node,
        # Management
        lifecycle_manager,
        diagnostic_aggregator,
        # Visualization
        rviz_node,
    ])
