# Lunar PSR Autonomy Scout (LPAS)

**A fully simulated NASA-inspired lunar rover mission — ROS2 Humble · Gazebo Fortress · Nav2 · PyTorch AI stack**

---

## What this is

LPAS is a complete systems-engineering simulation of a robotic precursor mission targeting the lunar south pole's Permanently Shadowed Regions (PSRs). The idea came from wanting to build something that goes deeper than a generic rover demo — a project with real mission design documents behind it, a working autonomy stack, and a simulation you can actually launch and watch drive.

The rover is designed to autonomously characterize water ice distribution in PSRs to support sustained Artemis-era human operations. That mission context drives every design decision: why the power system is solar-only (no RTG), why the rover has a rocker-bogie suspension, why Nav2 is tuned for 0.5 m/s lunar traverse, and why the QoS profiles on every ROS topic are explicit.

**What's running now:**
- Gazebo Fortress opens a photorealistic lunar south pole world with crater terrain and PSR shadows
- The rover spawns with a 6-wheel rocker-bogie suspension, deployable solar panels, stereo cameras, LiDAR, and a science drill
- Full ROS2 lifecycle node stack: wheel control, hazard detection, terrain segmentation, power management, thermal monitor, fault detection, comms, and autonomy manager
- Nav2 + SLAM Toolbox activate 15 seconds after launch (once odometry TF is live)
- RViz2 shows the robot model, TF tree, laser scan, and odometry

---

## Mission Design

| Parameter | Value |
|-----------|-------|
| Target | Nobile Crater, 85.2°S — primary PSR site |
| Mission Duration | 120 sols (primary) |
| Traverse Distance | ≥ 10 km cumulative |
| Science Goals | Water ice mapping, regolith mechanics, PSR radiation environment |
| Autonomy Level | Hybrid AL-2/AL-3 (supervised traverse → full PSR autonomy) |
| Power | 200 W peak solar, 150 Wh Li-Ion (no RTG) |
| Mass | < 202 kg (meets 250 kg requirement with 15% margin) |
| Comms | UHF → LRO relay → DSN, 1 Mbps Ka-band |

The full Concept of Operations, Science Traceability Matrix, ICD, FMEA, and 9-document PDR package are in `pdr_documents/`. These aren't boilerplate — they trace directly to the simulation design.

---

## Repository Structure

```
lspace/
├── ros2_ws/src/
│   ├── lunar_scout_bringup/        # Launch files, Nav2/SLAM configs, RViz2
│   ├── lunar_scout_description/    # URDF/XACRO + STL meshes from NX
│   ├── lunar_scout_autonomy/       # Behavior-tree autonomy manager (lifecycle)
│   ├── lunar_scout_navigation/     # Nav2 parameter tuning for lunar terrain
│   ├── lunar_scout_hazard_detection/ # ONNX terrain segmentation + hazard detection
│   ├── lunar_scout_power_management/ # Solar/battery power model
│   ├── lunar_scout_thermal_monitor/  # Electronics bay thermal limits
│   ├── lunar_scout_comms/          # Link budget + comms window manager
│   ├── lunar_scout_wheel_control/  # Rocker-bogie kinematics + odom TF
│   └── lunar_scout_fault_detection/ # FDIR state machine
│
├── gazebo_worlds/
│   ├── lunar_south_pole/           # Main sim world (SDF 1.9)
│   └── models/                     # Terrain heightmap, rock fields, lander
│
├── cad/
│   ├── nx_models/                  # Siemens NX assembly tree + FEA setup
│   ├── nx_models/mesh_exports/     # STL exports → also in description/meshes/
│   └── mass_properties/            # CBE mass budget (JSON + CSV)
│
├── autonomy_models/pytorch_models/ # DeepLabV3+ terrain seg, hazard ONNX models
├── terrain_data/                   # LOLA DEM tiles (downloaded separately)
├── pdr_documents/                  # Full PDR package (9 documents)
├── mission_budget/                 # Mass, power, thermal, comms budgets
├── system_engineering/             # SysML, RTM, ICD, FMEA
├── stk_analysis/                   # STK coverage + comm window analysis
└── scripts/
    └── setup_wsl_sim.sh            # One-command WSL2 install + build
```

---

## Running the Simulation

### Prerequisites
WSL2 with Ubuntu 22.04 on Windows, or native Ubuntu 22.04.

### One-time setup (~10 min)
```bash
# In WSL2 terminal:
cd /mnt/c/Users/<you>/Code/apps/lspace    # adjust path
bash scripts/setup_wsl_sim.sh
```

This installs ROS2 Humble, Ignition Gazebo Fortress, Nav2, SLAM Toolbox, all Python packages, builds the workspace, and configures `~/.bashrc`.

### Launch
```bash
source ~/.bashrc
ros2 launch lunar_scout_bringup lunar_scout_sim.launch.py
```

**What you'll see:**
| Time | Event |
|------|-------|
| t = 0 s | Gazebo opens with lunar south pole world |
| t = 5 s | Rover spawns at origin (gold chassis + blue solar panels) |
| t = 8 s | RViz2 opens — robot model, TF tree, sensor displays |
| t = 15 s | Nav2 + SLAM Toolbox activate |

**Headless (no GUI window):**
```bash
ros2 launch lunar_scout_bringup lunar_scout_sim.launch.py headless:=true
```

### Verification
```bash
# Check TF chain
ros2 run tf2_tools view_frames

# Watch odometry
ros2 topic echo /lpas/wheel_control/odometry

# Confirm Nav2 is active
ros2 action list    # should show /navigate_to_pose
```

---

## Software Stack

### Robotics
| Component | Purpose |
|-----------|---------|
| ROS2 Humble | Robot middleware + lifecycle management |
| Ignition Gazebo Fortress | Physics sim with lunar regolith terrain |
| Nav2 | Autonomous navigation (tuned: max 0.5 m/s, cost functions for rough terrain) |
| SLAM Toolbox | LiDAR-based online mapping |
| ros_gz_bridge | Gazebo ↔ ROS2 topic bridge (`/clock`, sensors) |

### Autonomy & AI
| Component | Purpose |
|-----------|---------|
| PyTorch (CPU) | Terrain segmentation training (DeepLabV3+) |
| ONNX Runtime | Deployed inference — hazard detection, traversability |
| OpenCV | Stereo vision, image preprocessing |
| py_trees | Behavior tree for mission management |

### Mechanical (CAD)
The rover body is designed in Siemens NX with an Al-7075 honeycomb chassis, Ti-6Al-4V wheel mounts, and rocker-bogie kinematics matching JPL heritage geometry. All STL meshes are exported to `ros2_ws/src/lunar_scout_description/meshes/` and visible in the URDF. Structural analysis uses NX Nastran with 10g axial / 6g lateral launch loads.

---

## Autonomy Architecture

The autonomy manager is a ROS2 lifecycle node running a behavior tree with five states: `STANDBY → SURVEY → APPROACH_PSR → PSR_OPS → EMERGENCY_SAFE`.

The AI pipeline:
1. Stereo hazcam images → ONNX hazard detection → obstacle costmap
2. LiDAR + stereo → traversability estimation → Nav2 costmap layer
3. Terrain segmentation (regolith class, rock density, slope) → path safety score
4. ONNX wheel slip predictor → traction control feedback to Nav2 planner

All models fall back to heuristic-only mode when no ONNX file is present (default in sim).

---

## Engineering Standards

This project follows:
- **Systems Engineering:** NASA-STD-0007, NASA/SP-2016-6105
- **Software:** NASA-STD-8739.8, ROS2 lifecycle node contracts
- **Safety:** MIL-STD-882E, FDIR three-level hierarchy
- **FMEA:** MIL-STD-1629A
- **Mass margin:** 15% CBE maintained throughout
- **Power margin:** 25% maintained; no RTG (solar-only constraint)

---

## What's Next

- [ ] PSR interior world (`gazebo_worlds/psr_terrain/`) with thermal simulation
- [ ] ONNX model training pipeline on LOLA DEM synthetic imagery
- [ ] Science payload re-integration (drill actuation in Gazebo)
- [ ] Rocker-bogie joint state feedback → real suspension animation
- [ ] NVIDIA Isaac Sim environment (high-fidelity lighting/shadow for PSR)
- [ ] Science autonomy module: onboard NS data interpretation + target scoring

---

## Project Context.

The mission design draws from VIPER, Perseverance AutoNav, LCROSS, and Artemis south pole planning. The PSR water ice targets (Nobile, Shackleton, Haworth) are the same sites NASA is actively studying for ISRU.

---

*Branch: `claude/lunar-psr-autonomy-scout-ba8EX` | Last Updated: 2026-05-24*
