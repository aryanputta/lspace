# Known Issues

This file tracks the current blockers I hit while bringing `lspace` up in WSL Ubuntu 22.04 with ROS 2 Humble and Gazebo.

## 1. `lunar_south_pole.world` fails to load in `ign gazebo`
- File: `gazebo_worlds/lunar_south_pole/lunar_south_pole.world`
- Symptom: Gazebo reports an invalid `<diffuse>` value and aborts world loading.
- Impact: The sim cannot stay up long enough to spawn the rover and establish `odom`.
- Next fix: Clamp the world light color values to valid SDF ranges and rerun the launch.

## 2. Autonomy startup still depends on lifecycle sequencing
- File: `ros2_ws/src/lunar_scout_autonomy/lunar_scout_autonomy/autonomy_manager_node.py`
- Symptom: The node previously self-configured and self-activated in `main()`, which conflicted with the lifecycle manager.
- Impact: Lifecycle bringup crashes or stalls when the manager and node both try to own transitions.
- Next fix: Keep lifecycle control in the bringup layer and make the node passive at startup.

## 3. Nav2 waits forever when `odom` never appears
- Files: `ros2_ws/src/lunar_scout_bringup/launch/lunar_scout_sim.launch.py`, Nav2 config files
- Symptom: `controller_server` times out waiting for `base_link -> odom`.
- Impact: Navigation never fully activates.
- Next fix: Make sure Gazebo loads, the rover spawns, and the odom publisher is alive before Nav2 activation.

## 4. QoS mismatches still exist between custom nodes
- Topics involved: `/traversability_map`, `/cmd_vel`, `/hazard_detections`
- Symptom: ROS warns that publishers and subscribers are using incompatible QoS profiles.
- Impact: Some messages are dropped even when the nodes are otherwise running.
- Next fix: Standardize QoS policy per topic and make the publisher/subscriber contracts explicit.

## 5. Hazard detection still needs a stable inference path
- File: `ros2_ws/src/lunar_scout_hazard_detection/lunar_scout_hazard_detection/hazard_detection_node.py`
- Symptom: The node can fall back to heuristic mode when ONNX is absent or inconsistent.
- Impact: The sim can run without ML inference, but the intended detection pipeline is not fully green.
- Next fix: Lock the ONNX export format and validate the runtime input/output contract.

## 6. Science payload is not part of the working sim subset yet
- File: `ros2_ws/src/lunar_scout_science_payload/`
- Symptom: This package is still not cleanly integrated into the launch path.
- Impact: The main rover demo does not depend on it, but the full mission stack is incomplete.
- Next fix: Treat it as a separate bringup target after the core sim is stable.

## 7. `lunar_scout_embedded` is still placeholder-heavy
- File: `ros2_ws/src/lunar_scout_embedded/`
- Symptom: The package has missing source files and is not buildable as a full native control stack.
- Impact: It cannot be treated as a production-ready simulation dependency.
- Next fix: Either add the missing sources or exclude it from the simulation release path.

## 8. Mixed Windows and WSL execution is fragile
- Environment: Windows host + WSL Ubuntu 22.04
- Symptom: Python launch scripts and GUI tools can break on line endings, display forwarding, or path assumptions.
- Impact: Launches work only after careful environment-specific fixes.
- Next fix: Normalize line endings, keep WSL-only runtime paths inside WSL, and avoid Windows path assumptions in ROS launch files.

## Current Status
- ROS workspace builds for the simulation subset.
- The repo is closer to a working demo, but the Gazebo world file still blocks a clean live launch.
- Fixing the world file is the next high-value step.
