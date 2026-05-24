# LPAS Work Breakdown Structure
**Document:** LPAS-WBS-001 | **Revision:** PDR-A | **Date:** 2026-05-24

---

## WBS Tree (Level 1–3)

```
1.0  Project Management
  1.1  Schedule Management
  1.2  Cost Management & EVM
  1.3  Reporting & Reviews (MCR, SRR, PDR, CDR, TRR, LRR)
  1.4  Configuration Management
  1.5  Risk Management

2.0  Systems Engineering
  2.1  Requirements Development & Management
  2.2  Interface Control Documents (ICDs)
  2.3  Verification & Validation Plan
  2.4  Systems Analysis & Trades
  2.5  MBSE / SysML Models
  2.6  Reliability & FMEA

3.0  Flight System
  3.1  Chassis & Mobility
    3.1.1  Structural Chassis (Al-7075 weldment)
    3.1.2  Rocker-Bogie Suspension Arms
    3.1.3  Wheel Assemblies (×6, Ti-6Al-4V mesh)
    3.1.4  Wheel Actuator Motors (×6 + drivers)
    3.1.5  Differential Drive Linkage
  3.2  Power System
    3.2.1  Solar Array Panels (triple-junction GaAs, 2 panels)
    3.2.2  Battery Assembly (LFP, 150 Wh)
    3.2.3  PMAD Electronics (PDU, relay, bus protection)
    3.2.4  Solar Array Drive Actuators
  3.3  Thermal Control System
    3.3.1  MLI Blankets (20 layers, ε_eff=0.03)
    3.3.2  PTC Heaters (battery 15W, electronics 10W)
    3.3.3  Radiator Panel (Al honeycomb, 0.12 m²)
    3.3.4  Heat Pipes (electronics bay to radiator)
    3.3.5  Temperature Sensors (16 PT100 RTDs)
  3.4  Avionics & Flight Software
    3.4.1  Onboard Computer (Jetson AGX Orin, 32 GB)
    3.4.2  ROS2 Humble Flight Software (11 lifecycle nodes)
    3.4.3  AI Autonomy Models (ONNX, TensorRT)
    3.4.4  JPL F Prime BSP (fault detection, sequencing)
    3.4.5  IMU (Xsens MTi-670)
    3.4.6  NAND Flash Storage (64 GB science data)
  3.5  Communications
    3.5.1  UHF Radio (437.5 MHz, 5W, LRO relay)
    3.5.2  Ka-band HGA System (26 GHz, 0.5m dish, 20W)
    3.5.3  LGA Emergency Antenna (hemispherical UHF)
    3.5.4  HGA Pointing Mechanism (2-axis gimbal)
  3.6  Science Payload
    3.6.1  TRIDENT Drill (0–500 mm depth, 10W)
    3.6.2  NIRVSS Spectrometer (400–2500 nm, VNIR)
    3.6.3  NavCam Stereo Pair (1280×960, 15 Hz)
    3.6.4  HazCam Wide-Angle (120° FOV, 30 Hz)
    3.6.5  LiDAR (360°×16-ch, VLP-16 heritage)
  3.7  Navigation & Autonomy Integration
    3.7.1  SLAM Toolbox Integration
    3.7.2  Nav2 Configuration & Tuning
    3.7.3  Autonomy State Machine
    3.7.4  Terrain Processing Pipeline

4.0  Ground Support Equipment
  4.1  EGSE (Electrical Ground Support)
  4.2  Mechanical GSE (MGSE, transport fixtures)
  4.3  Test Software & Simulators

5.0  Mission Operations
  5.1  Mission Operations Center (MOC) Systems
  5.2  Ground Control Software (ROS2 + DSN)
  5.3  Mission Operations Procedures (MOPs)
  5.4  Operator Training

6.0  Integration & Test
  6.1  Component-Level Testing (TRL 6)
  6.2  Subsystem Integration & Test
  6.3  System Integration & Test (SIT)
  6.4  Environmental Test (TVAC, vibration, EMI)
  6.5  Field Test (analog terrain, JPL Mars Yard)

7.0  Launch Campaign
  7.1  Lander Integration (Astrobotic Griffin)
  7.2  Launch Vehicle Accommodation (Falcon 9 / Vulcan Centaur)
  7.3  Range Operations
  7.4  Pre-Ship Review
```

---

## WBS Element Details

| WBS | Element | TRL | Make/Buy | Org | Phase B PM | Phase C PM | Phase D PM |
|-----|---------|-----|----------|-----|-----------|-----------|-----------|
| 3.1.1 | Structural Chassis | 4 | Make | Structures | 4 | 8 | 4 |
| 3.1.2 | Rocker-Bogie Arms | 4 | Make | Structures | 3 | 6 | 3 |
| 3.1.3 | Wheel Assemblies | 5 | Make | Mech | 4 | 8 | 4 |
| 3.1.4 | Wheel Actuators | 6 | Buy | Motors | 2 | 4 | 2 |
| 3.2.1 | Solar Panels | 7 | Buy | Power | 3 | 4 | 2 |
| 3.2.2 | Battery Assembly | 6 | Make | Power | 4 | 6 | 3 |
| 3.2.3 | PMAD Electronics | 5 | Make | Power | 6 | 8 | 4 |
| 3.3.1 | MLI Blankets | 9 | Buy | Thermal | 1 | 3 | 2 |
| 3.3.2 | PTC Heaters | 9 | Buy | Thermal | 1 | 2 | 1 |
| 3.3.3 | Radiator Panel | 7 | Make | Thermal | 2 | 4 | 2 |
| 3.4.1 | Onboard Computer | 6 | Buy | Avionics | 2 | 4 | 2 |
| 3.4.2 | ROS2 FSW | 4 | Make | Software | 14 | 18 | 8 |
| 3.4.3 | AI Models | 4 | Make | AI/ML | 10 | 12 | 6 |
| 3.4.4 | F Prime BSP | 5 | Make | Software | 6 | 8 | 4 |
| 3.5.1 | UHF Radio | 8 | Buy | Comms | 2 | 3 | 2 |
| 3.5.2 | Ka-band HGA | 6 | Make | Comms | 6 | 10 | 4 |
| 3.6.1 | TRIDENT Drill | 6 | Buy | Sci | 3 | 6 | 3 |
| 3.6.2 | NIRVSS | 6 | Buy | Sci | 3 | 6 | 3 |
| 3.6.3 | NavCam Stereo | 7 | Buy | Sci | 2 | 3 | 2 |
| 3.7.2 | Nav2 Integration | 4 | Make | Software | 6 | 8 | 4 |

---

## Level-of-Effort by Phase (Person-Months)

| WBS | Element | Phase A | Phase B | Phase C | Phase D | Total |
|-----|---------|---------|---------|---------|---------|-------|
| 1.0 | Project Mgmt | 6 | 12 | 12 | 8 | **38** |
| 2.0 | Systems Eng | 8 | 18 | 15 | 6 | **47** |
| 3.1 | Chassis & Mobility | 4 | 16 | 20 | 12 | **52** |
| 3.2 | Power System | 3 | 12 | 16 | 8 | **39** |
| 3.3 | Thermal Control | 3 | 10 | 14 | 6 | **33** |
| 3.4 | Avionics & FSW | 6 | 24 | 28 | 14 | **72** |
| 3.5 | Communications | 3 | 10 | 12 | 6 | **31** |
| 3.6 | Science Payload | 5 | 14 | 18 | 10 | **47** |
| 3.7 | Navigation | 2 | 8 | 10 | 4 | **24** |
| 4.0 | GSE | 0 | 4 | 6 | 8 | **18** |
| 5.0 | Mission Ops | 0 | 4 | 8 | 16 | **28** |
| 6.0 | I&T | 0 | 4 | 8 | 24 | **36** |
| 7.0 | Launch Campaign | 0 | 0 | 2 | 10 | **12** |
| | **TOTAL** | **40** | **136** | **169** | **132** | **477 PM** |

---

## Key Deliverables by WBS

| WBS | Deliverable | Due |
|-----|------------|-----|
| 2.1 | Requirements Database (DOORS/CSV) | PDR |
| 2.2 | ICD-Rover-Lander, ICD-Software | PDR |
| 2.3 | V&V Plan | PDR |
| 2.4 | Trade Study Reports (3) | PDR |
| 3.1 | CAD Assembly (NX/STEP), URDF | PDR |
| 3.2 | Power Budget, Cell Test Data | PDR |
| 3.3 | Thermal Model, Radiator Sizing | PDR |
| 3.4 | FSW Architecture, Node ICD | PDR |
| 3.5 | Link Budget, Antenna Patterns | PDR |
| 3.6 | Payload ICD, Science Data Plan | PDR |
| 3.7 | Nav Architecture, SLAM Config | PDR |
| All | PDR Package (20 documents) | Jun 2026 |
| 3.1 | Structural Analysis (FEA) | CDR |
| 3.4 | AI Model Validation Report | CDR |
| 6.4 | TVAC Test Report | TRR |
| All | Acceptance Test Procedure | TRR |
