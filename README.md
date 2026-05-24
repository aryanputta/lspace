# Lunar PSR Autonomy Scout (LPAS)

**AI-Assisted Rover and Surface Relay Architecture for Artemis Lunar South Pole Operations**

---

## Mission Overview

The Lunar PSR Autonomy Scout is a NASA-inspired robotic precursor mission targeting the lunar south pole's Permanently Shadowed Regions (PSRs). Designed to support sustained Artemis-era human presence, LPAS autonomously characterizes water ice distribution, maps traversability, and validates surface infrastructure concepts under extreme cold and communication constraints.

| Parameter | Value |
|-----------|-------|
| Total System Mass | < 202 kg (250 kg requirement) |
| Mission Duration | 120 sols |
| Traverse Distance | > 10 km cumulative |
| Max Slope Capability | 25° |
| Peak Solar Power | 200 W |
| Battery Capacity | 150 Wh |
| Downlink Rate | 1 Mbps (Ka-band relay) |
| Autonomy Level | Hybrid (Level 2/3) |
| Primary Science Target | 3 PSR sites, water ice characterization |

---

## Repository Structure

```
lunar-psr-autonomy-scout/
├── cad/                          # CAD models and mechanical design
│   ├── nx_models/                # Siemens NX assemblies
│   ├── step_exports/             # STEP file exports
│   └── mass_properties/          # Mass budget calculations
│
├── ros2_ws/                      # ROS2 Humble workspace
│   └── src/
│       ├── lunar_scout_bringup/        # Launch files and configs
│       ├── lunar_scout_description/    # URDF/XACRO robot model
│       ├── lunar_scout_autonomy/       # Autonomy manager
│       ├── lunar_scout_navigation/     # Navigation stack integration
│       ├── lunar_scout_hazard_detection/ # AI hazard detection
│       ├── lunar_scout_power_management/ # Power system management
│       ├── lunar_scout_thermal_monitor/  # Thermal monitoring
│       ├── lunar_scout_comms/          # Communications management
│       ├── lunar_scout_science_payload/ # Science instruments
│       ├── lunar_scout_wheel_control/   # Wheel traction control
│       └── lunar_scout_fault_detection/ # FDIR system
│
├── gazebo_worlds/                # Gazebo Fortress simulation
│   ├── lunar_south_pole/         # Main south pole world
│   ├── psr_terrain/              # PSR interior world
│   ├── models/                   # SDF models
│   └── plugins/                  # Custom Gazebo plugins
│
├── isaac_sim/                    # NVIDIA Isaac Sim environments
│
├── terrain_data/                 # NASA terrain datasets
│   ├── lola_dem/                 # LOLA elevation maps
│   ├── lroc_imagery/             # LROC NAC imagery
│   ├── slope_maps/               # Computed slope maps
│   ├── illumination_maps/        # Solar illumination analysis
│   └── processed/                # Processed terrain products
│
├── autonomy_models/              # AI/ML models
│   ├── pytorch_models/
│   │   ├── terrain_segmentation/ # DeepLabV3+ terrain classifier
│   │   ├── hazard_detection/     # Real-time obstacle detector
│   │   ├── wheel_slip_prediction/ # Temporal slip predictor
│   │   ├── traversability/       # BEV traversability estimator
│   │   └── energy_prediction/    # Path energy predictor
│   ├── onnx_exports/             # Deployment models
│   ├── tensorrt_engines/         # TensorRT optimized
│   └── benchmarks/               # Benchmark suite
│
├── thermal_analysis/             # Thermal engineering
│   ├── matlab_models/            # MATLAB thermal networks
│   ├── nx_thermal/               # NX Thermal exports
│   └── radiator_sizing/          # Radiator trade analysis
│
├── stk_analysis/                 # Systems Tool Kit analysis
│   ├── scenarios/                # STK scenario configs
│   ├── coverage_reports/         # Coverage analysis
│   └── comm_windows/             # Communication window reports
│
├── system_engineering/           # MBSE artifacts
│   ├── sysml/                    # SysML diagrams
│   ├── requirements/             # Requirements database
│   ├── icds/                     # Interface Control Documents
│   └── fmea/                     # Failure Mode analysis
│
├── pdr_documents/                # Preliminary Design Review package
│   ├── 01_Science_Traceability_Matrix.md
│   ├── 02_ConOps.md
│   ├── 03_System_Requirements_Review.md
│   ├── 04_ICD_Interface_Control_Document.md
│   ├── 05_Verification_and_Validation_Plan.md
│   ├── 06_Hazard_Analysis.md
│   ├── 07_Mission_Operations_Timeline.md
│   ├── 08_Work_Breakdown_Structure.md
│   └── 09_Gantt_Schedule.md
│
├── trade_studies/                # Engineering trade studies
│   ├── Mobility_Architecture_Trade.md
│   ├── Power_Architecture_Trade.md
│   └── Autonomy_Level_Trade.md
│
├── mission_budget/               # Resource budgets
│   ├── Mass_Budget.md
│   ├── Power_Budget.md
│   ├── Thermal_Budget.md
│   ├── Comms_Budget.md
│   ├── Risk_Matrix.md
│   └── FMEA.md
│
├── simulation_results/           # Simulation output data
│   ├── mobility/                 # Wheel + terrain simulations
│   ├── autonomy/                 # AI benchmark results
│   ├── thermal/                  # Thermal analysis outputs
│   └── comms/                    # Communication link analysis
│
├── scripts/                      # Utility scripts
│   ├── terrain_processing/       # DEM download and processing
│   ├── data_pipeline/            # Data ingestion pipeline
│   └── benchmarks/               # Benchmark runners
│
└── docs/                         # References and papers
    ├── references/               # NASA/JPL reference documents
    └── papers/                   # Related research papers
```

---

## Software Stack

### Robotics & Simulation
| Tool | Version | Purpose |
|------|---------|---------|
| ROS2 | Humble Hawksbill | Robot middleware |
| Gazebo | Fortress | Physics simulation |
| NVIDIA Isaac Sim | 2023.1 | High-fidelity simulation |
| RViz2 | Latest | Visualization |
| Nav2 | Latest | Autonomous navigation |
| SLAM Toolbox | Latest | Mapping |

### AI & Autonomy
| Tool | Version | Purpose |
|------|---------|---------|
| PyTorch | 2.1+ | Model training |
| ONNX Runtime | 1.16+ | Deployment inference |
| TensorRT | 8.6+ | GPU-optimized inference |
| CUDA | 12.0+ | GPU acceleration |
| OpenCV | 4.8+ | Computer vision |

### Mission Analysis
| Tool | Purpose |
|------|---------|
| GMAT | Trajectory analysis |
| STK / Python sim | Communication windows |
| MATLAB | Thermal modeling |
| astropy | Orbital mechanics |

### Mechanical Design
| Tool | Purpose |
|------|---------|
| Siemens NX | Primary CAD |
| FreeCAD | Open-source cross-check |

---

## Quick Start

### 1. Build ROS2 Workspace
```bash
cd ros2_ws
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

### 2. Launch Simulation
```bash
ros2 launch lunar_scout_bringup lunar_scout_sim.launch.py
```

### 3. Process Terrain Data
```bash
cd scripts/terrain_processing
python download_lola_dem.py --output ../../terrain_data/lola_dem/
python process_dem_to_gazebo.py --input ../../terrain_data/lola_dem/south_pole_dem.tif
python generate_illumination_map.py
```

### 4. Train AI Models
```bash
cd autonomy_models/pytorch_models/terrain_segmentation
python train.py --epochs 100 --batch_size 8 --lr 1e-4 --data_dir ../../../terrain_data
```

### 5. Run Benchmarks
```bash
cd autonomy_models/benchmarks
python benchmark_suite.py --models_dir ../onnx_exports
```

---

## Mission Heritage & References

| Program | Reference |
|---------|-----------|
| VIPER | NASA VIPER rover architecture, TRIDENT drill system |
| Perseverance | JPL rocker-bogie mobility, AutoNav system |
| CLPS | Commercial Lunar Payload Services payload standards |
| Lunar Flashlight | JPL CubeSat PSR mapping mission |
| F Prime | JPL flight software framework |
| Artemis | NASA south pole human landing site planning |

---

## Engineering Standards

- **Systems Engineering**: NASA-STD-0007, NASA/SP-2016-6105 (SE Handbook)
- **Software**: NASA-STD-8739.8, JPL D-60411
- **Safety**: MIL-STD-882E, NASA-STD-8719.13
- **FMEA**: MIL-STD-1629A
- **Mass Margin**: 15% per NASA mass margin policy
- **Power Margin**: 25% per NASA power margin policy

---

## Career Framing

> "Designed a NASA-style lunar south pole robotic precursor mission focused on autonomous PSR exploration, volatile characterization, surface infrastructure readiness, and AI-assisted rover operations supporting sustained Artemis-era human presence."

**Target Roles:** NASA Pathways · JPL Robotics · SpaceX Starship Surface Systems · Blue Origin Lunar Systems · Lockheed Martin Space · Draper Lunar Navigation · RTX Space Systems · Astrobotic Robotics · NVIDIA Robotics & Autonomy

---

*Project Status: Preliminary Design Phase*
*Last Updated: 2026-05-24*
