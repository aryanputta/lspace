# LPAS Interface Control Document
**Document:** LPAS-ICD-001 | **Revision:** PDR-A | **Date:** 2026-05-24

---

## 1. Rover ↔ Lander Interface

### 1.1 Mechanical Interface

| Interface | Specification |
|-----------|---------------|
| Attachment points | 4× kinematic mount, titanium shear pins + clevis brackets |
| Deployment method | Egress ramp, 3-section telescoping, motor actuated |
| Ramp angle | 15° maximum (CLPS lander deck height ~0.6m) |
| Release mechanism | Pyro bolt (primary) + motorized backup |
| Launch load path | 4-point attach transmits 10g axial, 6g lateral to lander |
| Separation interface | ESPA-ring compatible bolt pattern |
| Alignment pins | 2× datum pins for repeatable install |

### 1.2 Electrical Interface (Umbilical)

| Signal | Specification | Connector |
|--------|---------------|-----------|
| 28V power from lander | 28V ±2V, 10A max, fused | MIL-C-26482 circular |
| Data (uplink mission plan) | RS-422, 1 Mbps | MIL-C-26482 |
| Heater enable | Discrete 28V logic | |
| Deployment complete signal | Discrete 28V | |
| Umbilical disconnect | Pull-to-release, 5N force | |

### 1.3 Thermal Interface

| Interface | Specification |
|-----------|---------------|
| Conductive coupling | G-10 fiberglass isolation bushings at mounts |
| Max heat transfer to lander | < 5W |
| Pre-deployment heater power from lander | 20W max, 28V |

---

## 2. ROS2 Software Interfaces

### 2.1 Topic Definitions

| Topic | Message Type | QoS | Rate | Direction |
|-------|-------------|-----|------|-----------|
| `/cmd_vel` | `geometry_msgs/Twist` | RELIABLE, depth=10 | On demand | Ground → Rover |
| `/wheel_control/odometry` | `nav_msgs/Odometry` | RELIABLE, depth=10 | 50 Hz | Rover → Nav |
| `/wheel_velocities` | `std_msgs/Float64MultiArray` | BEST_EFFORT, depth=5 | 20 Hz | WheelCtrl → Motors |
| `/wheel_slip_predictions` | `std_msgs/Float64MultiArray` | BEST_EFFORT, depth=5 | 20 Hz | SlipAI → WheelCtrl |
| `/imu/data` | `sensor_msgs/Imu` | BEST_EFFORT, depth=5 | 100 Hz | IMU → Nav |
| `/scan` | `sensor_msgs/LaserScan` | BEST_EFFORT, depth=5 | 10 Hz | LIDAR → Hazard |
| `/stereo/left/image_raw` | `sensor_msgs/Image` | BEST_EFFORT, depth=3 | 15 Hz | NavCam → AI |
| `/stereo/right/image_raw` | `sensor_msgs/Image` | BEST_EFFORT, depth=3 | 15 Hz | NavCam → AI |
| `/thermal/image_raw` | `sensor_msgs/Image` | BEST_EFFORT, depth=3 | 5 Hz | ThermalCam → AI |
| `/terrain_segmentation` | `std_msgs/String` (JSON) | BEST_EFFORT, depth=3 | 10 Hz | TerrainAI → Nav |
| `/traversability_map` | `nav_msgs/OccupancyGrid` | RELIABLE, depth=1 | 2 Hz | TerrainAI → Nav2 |
| `/hazard_detections` | `HazardArray` (custom) | RELIABLE, depth=10 | 10 Hz | HazardAI → Nav |
| `/hazard_visualization` | `sensor_msgs/Image` | BEST_EFFORT, depth=3 | 10 Hz | HazardAI → RViz |
| `/power/state` | `std_msgs/String` (JSON) | RELIABLE, T_LOCAL | 1 Hz | PowerMgmt → All |
| `/power/budget_report` | `std_msgs/String` (JSON) | RELIABLE, T_LOCAL | 0.1 Hz | PowerMgmt → GS |
| `/thermal/sensor_array` | `std_msgs/Float64MultiArray` | BEST_EFFORT, depth=5 | 5 Hz | ThermalMon → All |
| `/thermal/state` | `std_msgs/String` (JSON) | RELIABLE, T_LOCAL | 1 Hz | ThermalMon → All |
| `/comms/link_state` | `std_msgs/String` (JSON) | RELIABLE, T_LOCAL | 1 Hz | Comms → All |
| `/comms/bandwidth_bps` | `std_msgs/Float64` | BEST_EFFORT, depth=5 | 1 Hz | Comms → Nav |
| `/comms/blackout` | `std_msgs/Bool` | RELIABLE, T_LOCAL | 1 Hz | Comms → Autonomy |
| `/faults/active` | `std_msgs/String` (JSON) | RELIABLE, T_LOCAL | 1 Hz | FDIR → All |
| `/faults/safe_mode_request` | `std_msgs/Bool` | RELIABLE, T_LOCAL | On event | FDIR → Autonomy |
| `/autonomy/state` | `std_msgs/String` (JSON) | RELIABLE, T_LOCAL | 2 Hz | Autonomy → All |
| `/autonomy/mission_progress` | `std_msgs/String` (JSON) | RELIABLE, T_LOCAL | 0.2 Hz | Autonomy → GS |
| `/navigation/current_path` | `nav_msgs/Path` | RELIABLE, depth=1 | 1 Hz | Nav → RViz |
| `/navigation/energy_estimate` | `std_msgs/Float64` | RELIABLE, depth=5 | 1 Hz | Nav → PowerMgmt |
| `/science/drill_status` | `DrillStatus` (custom) | RELIABLE, T_LOCAL | 5 Hz | Science → All |
| `/science/spectrometer_data` | `SpectrometerData` (custom) | RELIABLE, T_LOCAL | On complete | Science → GS |
| `/diagnostics` | `diagnostic_msgs/DiagnosticArray` | RELIABLE, depth=10 | 1 Hz | All → Aggregator |
| `/joint_states` | `sensor_msgs/JointState` | BEST_EFFORT, depth=5 | 50 Hz | WheelCtrl → RViz |
| `/tf` | `tf2_msgs/TFMessage` | BEST_EFFORT, depth=100 | 50 Hz | RSP → All |

### 2.2 Service Definitions

| Service | Type | Server | Description |
|---------|------|--------|-------------|
| `/hazard_detection/emergency_stop` | `std_srvs/Trigger` | HazardDetect | Immediately zero wheel velocities |
| `/power/shed_load` | `std_srvs/SetBool` | PowerMgmt | Enable/disable non-essential loads |
| `/autonomy/change_mode` | Custom `ChangeMode` | Autonomy | Request mode transition |
| `/science/enable_payload` | `std_srvs/SetBool` | Science | Power on/off science instruments |
| `/comms/clear_queue` | `std_srvs/Trigger` | Comms | Flush store-and-forward queue |

### 2.3 Action Definitions

| Action | Type | Server | Goal / Feedback / Result |
|--------|------|--------|--------------------------|
| `/science/drill_operation` | Custom `DrillOp` | Science | Goal: depth_cm, site_id / FB: depth, force / Result: success, mass_g |
| `/science/spectrometer_scan` | Custom `SpectScan` | Science | Goal: duration_s / FB: progress / Result: spectrum, WEH% |
| `/navigate_to_pose` | `nav2_msgs/NavigateToPose` | Nav2 | Goal: pose / FB: distance_remaining / Result: success |
| `/navigate_through_poses` | `nav2_msgs/NavigateThroughPoses` | Nav2 | Goal: poses[] / FB: current_pose / Result: success |

---

## 3. RF Interface

### 3.1 UHF (Rover ↔ Relay Station)

| Parameter | Specification |
|-----------|---------------|
| Frequency | 437.5 MHz (amateur satellite band, regulatory clearance needed) |
| Protocol | CCSDS AOS (Advanced Orbiting Systems) |
| Modulation | BPSK |
| Data rate (nominal) | 128 kbps downlink, 9.6 kbps uplink |
| TX power (rover) | 5W |
| Antenna (rover) | 4-element patch array, 5 dBi |
| Polarization | RHCP |
| Frame format | CCSDS TM Transfer Frame, 1115 bytes |

### 3.2 Ka-Band (Relay ↔ Earth)

| Parameter | Specification |
|-----------|---------------|
| Frequency (downlink) | 26.0 GHz |
| Frequency (uplink) | 25.5 GHz |
| Protocol | CCSDS High Rate Data Link |
| Modulation | QPSK + Turbo (rate 1/2) |
| Data rate | 1 Mbps downlink, 128 kbps uplink |
| Relay dish | 0.5m parabolic, 45.8 dBi |
| DSN compatibility | 34m HEF (High Efficiency) Stations |

---

## 4. Science Data Interface

| Product | Format | Size | Delivery |
|---------|--------|------|----------|
| Drill core sample images | JPEG + raw TIFF | 10 MB/site | Post-operation |
| Mass spectrometer spectrum | HDF5 | 50 MB/site | Post-operation |
| Neutron spectrometer data | CSV + binary | 5 MB/traverse | Per 100m traverse |
| Stereo navigation images | JPEG pairs | 1 MB/image | Real-time (compressed) |
| Thermal IR maps | TIFF | 20 MB/sol | End of sol |
| SLAM map | ROS2 bag | 200 MB/sol | End of sol |
