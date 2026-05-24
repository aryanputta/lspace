# LPAS Project — Claude Code Notes

## Build Commands

```bash
# ROS2 workspace
cd ros2_ws && colcon build --symlink-install

# Python packages (autonomy models)
pip install -e autonomy_models/

# Terrain processing dependencies
pip install rasterio numpy scipy pillow astropy matplotlib

# AI model dependencies
pip install torch torchvision onnx onnxruntime opencv-python

# Run all tests
cd ros2_ws && colcon test
python -m pytest autonomy_models/ scripts/
```

## Lint / Format

```bash
# Python
ruff check .
black --check .

# ROS2 / ament
ament_flake8 ros2_ws/src/
ament_pep257 ros2_ws/src/
```

## Key Files

- `ros2_ws/src/lunar_scout_bringup/launch/lunar_scout_sim.launch.py` — main sim launcher
- `ros2_ws/src/lunar_scout_autonomy/lunar_scout_autonomy/autonomy_manager_node.py` — top-level state machine
- `autonomy_models/pytorch_models/terrain_segmentation/model.py` — terrain segmentation CNN
- `scripts/terrain_processing/process_dem_to_gazebo.py` — DEM → Gazebo pipeline
- `pdr_documents/` — full PDR package
- `mission_budget/` — mass, power, thermal, comms budgets

## Architecture Notes

- All ROS2 nodes use lifecycle management — must be activated before use
- Power management node must be running before science payload activates
- Autonomy manager is the top-level state machine — all mode changes go through it
- Nav2 is configured for slow lunar traverse (max 0.5 m/s)
- All AI models deployed as ONNX for cross-platform compatibility
- TensorRT engines generated separately for Jetson AGX Orin deployment

## NASA Data Sources

- LOLA DEM: https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/
- LROC NAC: https://pds-imaging.jpl.nasa.gov/volumes/lro.html
- JMARS: https://jmars.asu.edu/ (requires account)
- LRO PDS archive: https://pds-geosciences.wustl.edu/

## Coding Standards

- Python: PEP8, type hints required, rclpy lifecycle nodes
- ROS2: QoS profiles from rclpy.qos, no raw topic polling
- AI models: ONNX opset 17, dynamic batch axis
- No RTG references in power system (mission constraint)
- Mass margin: always maintain 15% CBE margin
