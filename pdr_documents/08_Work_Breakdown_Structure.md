# LPAS Work Breakdown Structure
**Document No.:** LPAS-WBS-001
**Review Level:** PDR-A
**Project:** Lunar PSR Autonomy Scout (LPAS)
**Date:** 2026-05-24
**Status:** Released for PDR

---

## 1. WBS Tree (Level 1–3)

### 1.0 Project Management
- 1.1 Schedule Management
  - 1.1.1 Integrated Master Schedule (IMS)
  - 1.1.2 Schedule risk analysis (Monte Carlo)
  - 1.1.3 Milestone tracking and reporting
- 1.2 Cost Management
  - 1.2.1 Cost estimating (grass-roots + parametric)
  - 1.2.2 Earned value management (EVM)
  - 1.2.3 Budget baseline and control accounts
- 1.3 Reporting and Reviews
  - 1.3.1 Monthly status reports to NASA/CLPS
  - 1.3.2 Technical interchange meetings (TIMs)
  - 1.3.3 Formal milestone reviews (PDR, CDR, SIR, FRR)

### 2.0 Systems Engineering
- 2.1 Requirements Management
  - 2.1.1 Mission requirements (Level 1–2)
  - 2.1.2 System requirements specification (SRS, LPAS-SYS-003)
  - 2.1.3 Requirements traceability matrix (RTM)
- 2.2 Interface Control
  - 2.2.1 Interface control document (ICD, LPAS-ICD-001)
  - 2.2.2 Rover-lander mechanical ICD
  - 2.2.3 Rover-lander electrical ICD
  - 2.2.4 Software interface control (ROS2 topic/service registry)
- 2.3 Verification and Validation
  - 2.3.1 V&V plan (LPAS-VVP-001)
  - 2.3.2 Unit-level testing
  - 2.3.3 System-level testing (thermal vac, vibration, EMC)
  - 2.3.4 Operational readiness test (ORT)
- 2.4 Risk Management
  - 2.4.1 Risk register maintenance
  - 2.4.2 Risk mitigation planning
  - 2.4.3 Risk retirement tracking

### 3.0 Flight System
- 3.1 Chassis and Mobility
  - 3.1.1 Chassis structure (Al-7075-T651 primary; CFRP secondary)
  - 3.1.2 Rocker-bogie suspension assembly
  - 3.1.3 Wheels (6 × Ti-6Al-4V; r = 0.25 m; grousered)
  - 3.1.4 Drive and steering actuators (6 × 250 W brushless DC motors)
- 3.2 Power Subsystem
  - 3.2.1 Solar arrays (2-panel; 200 W EOL; triple-junction GaAs; 28% efficiency)
  - 3.2.2 Battery (150 Wh LFP; 4S4P; −40°C to +60°C operating)
  - 3.2.3 Power management and distribution (PMAD; 28.8 V regulated bus)
- 3.3 Thermal Control
  - 3.3.1 Multi-layer insulation (MLI; 20-layer Kapton/Al; OBC, battery)
  - 3.3.2 Heaters (resistance heaters; 60 W total; thermostatic control)
  - 3.3.3 Radiators (passive Al fin; 0.04 m²; avionics box)
- 3.4 Avionics and Flight Software
  - 3.4.1 On-board computer (OBC; Cobham GR712RC SPARC; radiation-hardened)
  - 3.4.2 ROS2 flight software (Humble; 22 lifecycle nodes; LPAS-FSW-v2.3.1)
  - 3.4.3 AI inference models (ONNX opset 17; TensorRT on Jetson AGX Orin)
  - 3.4.4 F Prime BSP (board support package; low-level drivers; FDIR)
- 3.5 Communications
  - 3.5.1 UHF transceiver (437.1 MHz; 250 kbps; LRO relay)
  - 3.5.2 HGA Ka-band (26 GHz; 0.5 m dish; 2 Mbps; DSN direct)
  - 3.5.3 LGA omni (8.4 GHz X-band; 128 kbps; emergency/commissioning)
- 3.6 Science Payload
  - 3.6.1 TRIDENT drill (1 m depth; rotary-percussive; 15 N·m torque limit)
  - 3.6.2 NIRVSS spectrometer (Near-Infrared Volatile Spectroscope; 1–5 µm; SNR > 100:1)
  - 3.6.3 Cameras (NavCam stereo 1024×1024; HazCam stereo; science camera 4K RGB)
- 3.7 Navigation
  - 3.7.1 IMU (Honeywell HG1900-class; 0.1°/hr bias; 6-DOF)
  - 3.7.2 SLAM (ROS2 slam_toolbox; lidar-inertial; 16-ch, 50 m range)
  - 3.7.3 Nav2 stack (costmap 2D/3D; DWA local planner; AMCL; 0.5 m/s max speed)

### 4.0 Ground Support Equipment (GSE)
- 4.1 Mechanical GSE (handling fixtures, transport container, ramp deployment stand)
- 4.2 Electrical GSE (EGSE; umbilical simulator; power supply rack; battery charger)
- 4.3 Software GSE (test harness; EGSE control software; data archive)

### 5.0 Mission Operations
- 5.1 Mission Operations Center (MOC) development and certification
- 5.2 Flight operations team (FOT) training and certification
- 5.3 DSN interface and scheduling
- 5.4 Operations documentation (procedures, constraints, FDPs)
- 5.5 Anomaly resolution process

### 6.0 Integration and Test (I&T)
- 6.1 Component-level testing (unit tests per WBS 3.x)
- 6.2 Subsystem integration testing
- 6.3 System-level I&T (thermal vac, vibration, EMC/EMI, functional)
- 6.4 Environmental qualification (random vibration per GEVS; thermal vac per LPAS-ENV-001)
- 6.5 Acceptance testing and delivery

### 7.0 Launch Campaign
- 7.1 Rover-to-lander integration at KSC
- 7.2 Pad operations and range safety
- 7.3 Launch and early orbit support (LEOPS)
- 7.4 End-to-end mission simulation (pre-launch)

---

## 2. WBS Element Details

| WBS | Element Name | TRL (current) | TRL (target at CDR) | Make/Buy | Responsible Org |
|---|---|---|---|---|---|
| 3.1.1 | Chassis structure | 5 | 6 | Make | Structures Team |
| 3.1.2 | Rocker-bogie suspension | 7 | 8 | Make | Mechanisms Team |
| 3.1.3 | Wheels (Ti-6Al-4V) | 6 | 7 | Make | Mechanisms Team |
| 3.1.4 | Drive actuators (250 W BLDC) | 7 | 8 | Buy (maxon EC) | Mechanisms Team |
| 3.2.1 | Solar arrays (GaAs triple-jxn) | 8 | 9 | Buy (Spectrolab) | Power Team |
| 3.2.2 | LFP battery (150 Wh) | 6 | 7 | Make (custom cells) | Power Team |
| 3.2.3 | PMAD (28.8 V bus) | 6 | 7 | Make | Power Team |
| 3.3.1 | MLI blankets | 9 | 9 | Buy | Thermal Team |
| 3.3.2 | Heater circuits | 8 | 9 | Make | Thermal Team |
| 3.3.3 | Radiator panels | 7 | 8 | Make | Thermal Team |
| 3.4.1 | OBC (GR712RC SPARC) | 9 | 9 | Buy (Cobham) | Avionics Team |
| 3.4.2 | ROS2 FSW | 4 | 6 | Make | Software Team |
| 3.4.3 | AI inference models (ONNX) | 4 | 6 | Make | Autonomy Team |
| 3.4.4 | F Prime BSP | 5 | 6 | Make | Software Team |
| 3.5.1 | UHF transceiver | 9 | 9 | Buy (SDL/JPL heritage) | Comms Team |
| 3.5.2 | Ka-band HGA | 7 | 8 | Buy (custom 0.5 m dish) | Comms Team |
| 3.5.3 | X-band LGA | 9 | 9 | Buy (heritage) | Comms Team |
| 3.6.1 | TRIDENT drill | 6 | 7 | Buy (NASA GSFC) | Science Team |
| 3.6.2 | NIRVSS spectrometer | 7 | 8 | Buy (NASA ARC) | Science Team |
| 3.6.3 | Cameras (NavCam/HazCam/Sci) | 7 | 8 | Buy (FLIR/custom) | Science Team |
| 3.7.1 | IMU (HG1900-class) | 9 | 9 | Buy (Honeywell) | Navigation Team |
| 3.7.2 | SLAM (slam_toolbox + lidar) | 4 | 6 | Make | Navigation Team |
| 3.7.3 | Nav2 stack | 5 | 6 | Make | Navigation Team |

---

## 3. Phase Schedule Assignments

| WBS | Element | Phase B PM (est.) | Phase C PM (est.) | Phase D PM (est.) |
|---|---|---|---|---|
| 1.0 | Project Management | 1.5 FTE | 1.5 FTE | 1.5 FTE |
| 2.0 | Systems Engineering | 3.0 FTE | 2.5 FTE | 2.0 FTE |
| 3.1 | Chassis & Mobility | 2.0 FTE | 2.5 FTE | 1.5 FTE |
| 3.2 | Power | 1.5 FTE | 2.0 FTE | 1.0 FTE |
| 3.3 | Thermal | 1.0 FTE | 1.5 FTE | 0.5 FTE |
| 3.4 | Avionics & FSW | 3.0 FTE | 4.0 FTE | 2.0 FTE |
| 3.5 | Communications | 1.5 FTE | 1.5 FTE | 1.0 FTE |
| 3.6 | Science Payload | 1.5 FTE | 2.0 FTE | 1.0 FTE |
| 3.7 | Navigation | 2.0 FTE | 2.5 FTE | 1.5 FTE |
| 4.0 | GSE | 1.0 FTE | 2.0 FTE | 1.0 FTE |
| 5.0 | Mission Ops | 0.5 FTE | 1.5 FTE | 4.0 FTE |
| 6.0 | I&T | 1.0 FTE | 3.0 FTE | 2.0 FTE |
| 7.0 | Launch Campaign | 0.0 FTE | 0.5 FTE | 2.0 FTE |

---

## 4. Deliverables by WBS Element

| WBS | Key Deliverables |
|---|---|
| 1.1 | Integrated Master Schedule (IMS); monthly IMS updates |
| 1.2 | Cost performance report (CPR); EVM data package |
| 1.3 | PDR package; CDR package; SIR package; FRR package |
| 2.1 | LPAS-SYS-003 System Requirements Specification; RTM |
| 2.2 | LPAS-ICD-001 Interface Control Document; ROS2 interface registry |
| 2.3 | LPAS-VVP-001 V&V Plan; test reports (unit, subsystem, system); ORT report |
| 2.4 | Risk register; risk mitigation plans; risk retirement reports |
| 3.1 | Chassis structural analysis report; mechanisms test report; wheel test report |
| 3.2 | Power budget (LPAS-PWR-001); solar array acceptance test report; battery test report |
| 3.3 | Thermal model (Thermal Desktop); thermal vac test report |
| 3.4 | FSW design document; code review reports; FDIR specification; AI model performance report |
| 3.5 | Link budget (LPAS-COM-001); antenna pattern measurements; comms test report |
| 3.6 | Science payload ICD; calibration reports; science data product specification |
| 3.7 | Navigation algorithm design document; SLAM accuracy test report; Nav2 configuration |
| 4.0 | GSE design drawings; EGSE test procedures; GSE acceptance test report |
| 5.0 | MOC design document; FOT training plan; ops procedures; constraint list |
| 6.0 | I&T plan; environmental test procedures; acceptance test report |
| 7.0 | Launch site operations plan; range safety approval; LEOPS plan |

---

## 5. Document Control

| Field | Value |
|---|---|
| Document Number | LPAS-WBS-001 |
| Revision | A |
| Review Level | PDR-A |
| Next Review | CDR |
| Parent Documents | LPAS-SYS-003 (SRS), LPAS-CON-001 (ConOps) |
