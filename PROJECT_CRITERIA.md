# Project Criteria

This file captures the working criteria for `lspace` and the constraints the repo is trying to satisfy.

## Mission Criteria
- The rover sim should launch locally and visibly in WSL Ubuntu 22.04.
- ROS 2 Humble should build the simulation subset of the workspace cleanly.
- Gazebo / Ignition should load the lunar south pole world without parse errors.
- The rover should spawn into the world and produce a valid `odom -> base_link` transform.
- Nav2 should activate without lifecycle deadlocks.
- Core autonomy, hazard detection, power, thermal, comms, and wheel control nodes should start in the intended lifecycle order.

## Engineering Criteria
- Keep the repo buildable from source.
- Prefer deterministic local simulation over mock success.
- Fix real launch and runtime failures instead of papering over them.
- Keep Python ROS nodes executable in WSL without Windows-only assumptions.
- Keep topic QoS contracts explicit and consistent.
- Keep the code style readable and maintainable; remove placeholder or brittle wiring when it blocks execution.

## Mission Constraints
- Do not rely on RTG assumptions in the power system.
- Maintain mission mass margin and power budget discipline.
- Treat lifecycle ownership as a real contract, not a loose convention.
- Keep the autonomy stack compatible with slow lunar comms and PSR conditions.
- Keep the AI models ONNX-compatible for deployment.

## Reference Files
- [README.md](C:\Users\aryan\Code\apps\lspace\README.md)
- [CLAUDE.md](C:\Users\aryan\Code\apps\lspace\CLAUDE.md)
- [KNOWN_ISSUES.md](C:\Users\aryan\Code\apps\lspace\KNOWN_ISSUES.md)
- [lunar_scout_sim.launch.py](C:\Users\aryan\Code\apps\lspace\ros2_ws\src\lunar_scout_bringup\launch\lunar_scout_sim.launch.py)
- [autonomy_manager_node.py](C:\Users\aryan\Code\apps\lspace\ros2_ws\src\lunar_scout_autonomy\lunar_scout_autonomy\autonomy_manager_node.py)

## Practical Acceptance Test
The repo is “working” when:
1. `colcon build --symlink-install` succeeds for the simulation subset.
2. `ros2 launch lunar_scout_bringup lunar_scout_sim.launch.py` starts without immediate fatal errors.
3. The world loads in Gazebo.
4. The rover spawns and publishes transforms.
5. Nav2 and the custom ROS nodes stay up long enough to support a live demo.
