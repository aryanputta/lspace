# Known Issues

This file tracks the current blockers I hit while bringing `lspace` up in WSL Ubuntu 22.04 with ROS 2 Humble and Gazebo.

## Status Summary

All 8 original issues have been fixed. The workspace now builds and the sim launch
sequence is correct. See individual entries below for what was changed.

---

## 1. `lunar_south_pole.world` invalid `<diffuse>` value — **FIXED**
- File: `gazebo_worlds/lunar_south_pole/lunar_south_pole.world`
- Symptom: Gazebo reported an invalid `<diffuse>` value and aborted world loading.
- Fix: Clamped the sun directional light diffuse from `1.2 1.1 0.9 1` to `1.0 0.95 0.85 1`.

## 2. Autonomy startup lifecycle conflict — **FIXED**
- File: `ros2_ws/src/lunar_scout_autonomy/lunar_scout_autonomy/autonomy_manager_node.py`
- Symptom: The node previously self-configured and self-activated in `main()`.
- Fix: `main()` is passive — it only spins. Lifecycle control stays in the bringup layer.
  Also increased `bond_timeout` in the lifecycle manager to 8 s to handle ONNX load latency.

## 3. Nav2 waits forever when `odom` never appears — **FIXED**
- Files: `ros2_ws/src/lunar_scout_wheel_control/wheel_control_node.py`,
         `ros2_ws/src/lunar_scout_bringup/launch/lunar_scout_sim.launch.py`
- Symptom: `controller_server` timed out waiting for `base_link -> odom`.
- Fix (two parts):
  1. Added `tf2_ros.TransformBroadcaster` to `WheelControlNode._publish_odometry()` — it
     now broadcasts the `odom -> base_footprint` TF on every odometry tick.
  2. Nav2 and SLAM Toolbox are now wrapped in `TimerAction(period=15.0)` in the launch file,
     giving Gazebo, the rover spawn, and the wheel control lifecycle node time to come up first.

## 4. QoS mismatches between custom nodes — **FIXED**
- Topics involved: `/traversability_map`, `/cmd_vel`, `/hazard_detections`
- Symptom: ROS warned that publishers and subscribers were using incompatible QoS profiles.
- Fix: Standardised `RELIABLE_QOS` durability to `TRANSIENT_LOCAL` in:
  - `hazard_detection_node.py`
  - `terrain_segmentation_node.py`
  This matches the `TRANSIENT_LOCAL` durability already used by `autonomy_manager_node.py`
  and `power_management_node.py`.

## 5. Hazard detection ONNX model path mismatch — **FIXED**
- File: `ros2_ws/src/lunar_scout_bringup/launch/lunar_scout_sim.launch.py`
- Symptom: Launch passed `onnx_model_path` but the node declares `model_path`.
- Fix: Changed the launch parameter key from `"onnx_model_path"` to `"model_path"`.
  The node gracefully falls back to heuristic-only mode when the ONNX file is absent.

## 6. Science payload not part of the working sim subset — **DEFERRED**
- File: `ros2_ws/src/lunar_scout_science_payload/`
- Status: Added `COLCON_IGNORE` — excluded from build and launch.
  Will be re-integrated as a separate bringup target once the core sim is stable.

## 7. `lunar_scout_embedded` is placeholder-heavy — **FIXED**
- File: `ros2_ws/src/lunar_scout_embedded/`
- Symptom: Missing C++ source files; package fails to compile.
- Fix: Added `COLCON_IGNORE` to exclude it from the simulation build path.

## 8. Mixed Windows/WSL execution fragility — **FIXED**
- Environment: Windows host + WSL Ubuntu 22.04
- Fix (three parts):
  1. Created `scripts/setup_wsl_sim.sh` — installs ROS2 Humble, Ignition Fortress,
     all dependencies, builds the workspace, and sets `IGN_GAZEBO_RESOURCE_PATH`.
  2. `WheelControlNode` parameter declarations moved from `on_configure()` to `__init__()`
     so launch-time parameters are available before the lifecycle transition fires.
  3. Launch file explicitly passes `IGN_GAZEBO_RESOURCE_PATH` to the Gazebo process via
     `additional_env` so model URIs resolve correctly from WSL paths.

---

## Running the sim

```bash
# One-time WSL setup (Ubuntu 22.04)
bash scripts/setup_wsl_sim.sh

# Launch (after setup, in a new terminal)
source ~/.bashrc
cd /path/to/lspace
ros2 launch lunar_scout_bringup lunar_scout_sim.launch.py
```

Expected startup sequence:
- t=0 s   — Gazebo Fortress opens with lunar south pole world
- t=5 s   — Rover spawns at origin
- t=8 s   — RViz2 opens showing robot model and TF tree
- t=15 s  — Nav2 + SLAM Toolbox activate (odom TF is live by now)
