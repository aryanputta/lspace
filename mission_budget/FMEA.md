# Failure Modes and Effects Analysis — LPAS-FMEA-001 | PDR-A

**Document Number:** LPAS-FMEA-001
**Revision:** A
**Review Level:** PDR
**Date:** 2026-05-24
**Author:** Systems Reliability Team
**Status:** Released
**Standard:** MIL-STD-1629A, NASA-SP-6105 (NASA Preferred Reliability Practices)

---

## 1. Scope and Ground Rules

This FMEA covers all LPAS subsystems during surface operations at the lunar south pole. Analysis boundary begins at landing/deployment and ends at planned end-of-mission. Each failure mode is analyzed at the lowest replaceable assembly (LRA) level. Severity, Occurrence, and Detection ratings follow the 1–10 scales defined in Section 2.

Single Point Failures (SPFs) are identified where a single failure causes loss of the primary mission objective with no redundant path. All SPFs are flagged in the table.

---

## 2. Rating Scales

### 2.1 Severity (S)
| Rating | Description |
|---|---|
| 9–10 | Loss of mission / crew safety (not applicable — no crew) |
| 7–8 | Loss of primary science objective or rover total loss |
| 5–6 | Significant degradation of science or mobility |
| 3–4 | Minor degradation, mission continues with workaround |
| 1–2 | No mission impact, cosmetic or telemetry-only effect |

### 2.2 Occurrence (O)
| Rating | Description |
|---|---|
| 9–10 | Failure probable during mission (>1 in 10) |
| 7–8 | Failure likely (1 in 10 to 1 in 100) |
| 5–6 | Occasional (1 in 100 to 1 in 1,000) |
| 3–4 | Remote (1 in 1,000 to 1 in 10,000) |
| 1–2 | Extremely unlikely (<1 in 10,000) |

### 2.3 Detection (D)
| Rating | Description |
|---|---|
| 9–10 | No detection method; failure not observable |
| 7–8 | Low probability of detection before effect propagates |
| 5–6 | Moderate detection via telemetry or indirect indicator |
| 3–4 | High probability of detection via direct sensor |
| 1–2 | Certain detection before mission impact |

**RPN = S × O × D.** Critical threshold: RPN > 100.

---

## 3. FMEA Table

> SPF = Single Point Failure (marked with ★)

| # | Item | Function | Failure Mode | Local Effect | System Effect | Detection Method | S | O | D | RPN | Recommended Action |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Wheel actuator FL ★ | Drive front-left wheel | Motor winding open circuit | FL wheel stops | Rover immobilized if 2+ wheels fail; asymmetric drag if 1 | Motor current telemetry, dead reckoning drift | 8 | 4 | 3 | **96** | Redundant H-bridge driver ICs; thermal fuse in series; FDIR auto-switch to 3-wheel crawl mode |
| 2 | Wheel actuator FL ★ | Drive front-left wheel | Encoder failure (Hall sensor) | Loss of FL velocity feedback | Nav2 wheel odometry degraded; potential runaway | Odometry vs. IMU divergence check | 6 | 4 | 4 | **96** | Dual Hall sensors per wheel; IMU backup odometry |
| 3 | Battery cell (any) ★ | Energy storage | Internal short circuit | Thermal runaway in affected cell | Battery fire/venting; total power loss | Cell voltage monitor, cell temperature >60 °C | 9 | 3 | 3 | **81**→ see note | BMS overcurrent trip <5 ms; cell-level fusing; cell group isolation relay; 15% capacity margin |
| 4 | Battery cell ★ | Energy storage | Lithium plating (cold charge) | Capacity fade, internal short risk | Premature end-of-mission | Impedance spectroscopy at each charge; temperature gate | 7 | 4 | 4 | **112** | Hardware block: charging prohibited below −20 °C (PTC-gated relay); charge rate limited to 0.5C below 0 °C |
| 5 | Battery BMS | Protect battery | BMS microcontroller hang | No overcurrent protection | Unprotected overcharge/overdischarge | BMS watchdog telemetry, voltage drift | 8 | 3 | 4 | **96** | Hardware backup overvoltage clamp (TVS array); BMS watchdog reset; redundant voltage comparator |
| 6 | Comms UHF antenna pointing ★ | Maintain LRO UHF link | Antenna gimbal jam | No antenna articulation | Comms loss; no downlink for telemetry or commands | Gimbal encoder stall, link margin drop | 8 | 4 | 3 | **96** | Fixed backup LGA (low-gain patch) at 0 dB gain; stored command sequences for autonomous ops |
| 7 | Comms UHF transceiver | Transmit/receive | Power amplifier burnout | No UHF TX | No uplink to LRO relay; mission data lost | TX power monitor; no ACK from LRO | 8 | 3 | 2 | **48** | Redundant PA stage; power limiter ahead of PA |
| 8 | AI inference (Jetson) ★ | Terrain classification | Inference timeout >500 ms | Hazard detection unavailable | Rover enters safe stop; no autonomous traverse | Watchdog timer (500 ms), ROS2 topic heartbeat | 7 | 5 | 2 | **70** | Watchdog recovery: FDIR reboots node; fallback to conservative 0.1 m/s safe-mode traverse; pre-loaded hazard map |
| 9 | AI model (terrain seg.) | Terrain labeling | Model outputs all-unknown class | Navigation degrades | Traverse halted; science objectives missed | Output entropy monitor; class distribution check | 5 | 4 | 3 | **60** | Fallback to slope-only navigation (DEM-derived); model retrain from ground not possible — pre-validated model set |
| 10 | Drill motor assembly ★ | Core sample extraction | Motor stall under high torque | Drill seized in regolith | Science objective A (soil sample) lost | Drill motor current spike, depth encoder stall | 8 | 5 | 3 | **120** ★ SPF | Manual retract spring (pre-loaded torsion return); FDIR auto-retract on 2A current threshold; 3 retry attempts |
| 11 | Drill motor assembly | Core sample extraction | Drill bit fracture | Bit debris in sample | Contaminated sample; re-drill required | Drill torque drop after fracture; depth mismatch | 6 | 3 | 5 | **90** | Spare drill bit in deployment mechanism; bit inspection image before each use |
| 12 | Solar array deployment (port) ★ | Generate power | Panel fails to deploy | 50% power loss | Below power budget for science mode | Deployment switch, current from panel | 8 | 2 | 2 | **32** | Dual pyro release + spring deployment; non-explosive actuator (NEA) backup; pre-mission deployment test |
| 13 | Solar array cell (any) | Power generation | Cell delamination | Local power loss (<5%) | Minor power reduction | Array IV curve monitoring, cell-level shunts | 3 | 3 | 4 | **36** | Cell bypass diodes; 25% power margin in array sizing |
| 14 | Voltage regulator (main 28V bus) ★ | Regulate main bus | Output overcurrent latch | Main bus shuts off | Total power loss | Bus voltage monitor; OCP flag in PDU | 9 | 2 | 2 | **36** | Hiccup-mode OCP with auto-restart; redundant 28V rail from secondary converter |
| 15 | IMU (primary) | Attitude/heading | Gyro bias drift >0.5°/hr | Heading error accumulates | Nav2 path deviation; potential hazard | IMU vs. wheel odometry cross-check | 5 | 4 | 3 | **60** | Dual IMU (Xsens MTi-300 + LORD 3DM-GX5); outlier rejection in EKF |
| 16 | IMU (primary) | Attitude/heading | Accelerometer saturation (shock) | Tilt estimate invalid | Rover tipping risk undetected | Data range flag; cross-check with other IMU | 7 | 3 | 4 | **84** | Tilt safety limit enforced in wheel controller; chassis tilt sensor backup (inclinometer) |
| 17 | Thermal heater H-01 ★ | Maintain Z01 > −20 °C | Heater element open circuit | No heating in electronics bay | Electronics below survival limit; total loss | Zone 01 RTD temperature drop; power current drop | 9 | 2 | 2 | **36** | Redundant heater H-02 at −5 °C colder setpoint; BMS heater channel monitoring |
| 18 | Thermal sensor (RTD) | Temperature telemetry | RTD open circuit | No temperature reading for zone | Undetected thermal excursion | Cross-compare adjacent zone RTDs | 5 | 3 | 5 | **75** | 4× RTDs per critical zone; median voter algorithm in thermal monitor node |
| 19 | Heat pipe (HP-01) ★ | Transport heat elec→radiator | Working fluid leak | HP-01 non-functional | Z01 temperature rises; thermal limit in 8 min | Z01 temperature gradient stall; radiator ΔT drop | 8 | 2 | 3 | **48** | HP-02 parallel path provides backup; FDIR reduces compute load to 15 W idle if Z01 > 55 °C |
| 20 | Wheel steering actuator (front) | Steer front wheels | Actuator jam in off-center | Rover can only drive straight | Science site access limited | Steering angle encoder stall | 5 | 3 | 4 | **60** | Differential wheel speed steering (skid steer fallback); actuator torque limit 2 Nm |
| 21 | LIDAR unit (primary) | 3D hazard map | Detector array failure | 3D map unavailable | Hazard detection relies on camera alone | LIDAR return count; range image blank | 7 | 3 | 4 | **84** | Stereo camera fallback hazard detection (reduced confidence); reduced traverse speed 0.1 m/s |
| 22 | Mass spectrometer vacuum pump | Maintain vacuum for MS | Pump motor seizure | MS analyzer offline | Science objective B (volatile detection) lost | Pump RPM telemetry; chamber pressure rise | 7 | 3 | 5 | **105** ★ SPF | Pump is not redundant — pre-mission qualification to 5,000 hr MTTF; getter pump backup maintains vacuum for 2 h |
| 23 | Flash memory (science data) | Store science data | Flash write failure | Science data lost for affected pass | Potential loss of unique measurements | Write-verify after each record; error count telemetry | 6 | 2 | 3 | **36** | RAID-1 mirrored NVMe; critical data compressed and relayed to LRO immediately |
| 24 | Regolith sampling scoop ★ | Collect bulk sample | Scoop actuator stripped gear | Scoop non-functional | Backup to drill only; sediment objectives at risk | Actuator position encoder no-change | 6 | 3 | 5 | **90** | Torque limit 0.8 Nm; gear tooth hardness HRC 58; spare scoop stowed in payload bay |
| 25 | OBC (main computer) ★ | Mission command and control | CPU hard fault / watchdog reset | Node reboot ~30 s | Traverse interrupted; state machine reset | Watchdog timeout; ROS2 lifecycle state change | 7 | 3 | 3 | **63** | FDIR auto-restart sequence; persistent state to flash before each maneuver; rad-hard COTS (Xilinx Zynq UltraScale+) |
| 26 | Power distribution relay (science) | Switch science payload on/off | Relay contact weld | Science payload cannot be powered off | Uncontrolled power draw; thermal risk | Relay state vs. commanded state mismatch | 5 | 2 | 4 | **40** | Solid-state relay with current cutoff; mechanical backup relay in series |
| 27 | Comms link (LRO relay) ★ | All ground communication | LRO orbital contact window missed | No data uplink/downlink for 113.5 min | Commands queue; autonomy must continue | Contact window timer; no ACK from LRO | 5 | 4 | 1 | **20** | On-board stored command sequences for 24 h autonomous ops; next-pass retry |
| 28 | Wheel traction (all 4) | Traverse regolith | All-wheel slip (slope >20°) | Rover unable to advance | Mission abort of traverse leg | IMU tilt + odometry/IMU divergence | 6 | 3 | 3 | **54** | Max slope limit 15° in autonomy planner; wheel slip controller (torque modulation); re-route command from ground |

---

## 4. Critical Items List (RPN > 100)

| # | Item | RPN | SPF? | Critical Risk |
|---|---|---|---|---|
| 1 | Drill motor assembly — stall/seize | 120 | Yes ★ | Loss of primary science sample objective |
| 2 | Battery cell — lithium plating / cold charge short | 112 | Yes ★ | Total power loss, end of mission |
| 3 | Mass spectrometer vacuum pump — motor seizure | 105 | Yes ★ | Loss of volatile detection science objective |

**Note on Battery Cell Short (item #3 in Section 3):** Initial RPN computed as 81 pre-mitigation; lithium plating mode (#4) gives RPN 112 and is the governing battery failure mode.

---

## 5. Single Point Failure (SPF) Summary

| SPF # | Item | Subsystem | Mitigation Status |
|---|---|---|---|
| SPF-01 | Wheel actuator FL (and each wheel) | Mobility | Redundant driver; 3-wheel crawl FDIR |
| SPF-02 | Battery cell (internal short) | Power | BMS cell-level isolation; PTC gate |
| SPF-03 | Comms UHF antenna gimbal | Comms | Fixed backup LGA patch antenna |
| SPF-04 | AI inference watchdog timeout | Autonomy Software | Watchdog + safe-mode traverse |
| SPF-05 | Drill motor stall | Science | Spring retract + FDIR current trip |
| SPF-06 | Main 28V voltage regulator | Power | Hiccup OCP; redundant secondary rail |
| SPF-07 | Heater H-01 (electronics bay) | Thermal | Redundant H-02 at backup setpoint |
| SPF-08 | Heat pipe HP-01 (main) | Thermal | HP-02 parallel path; FDIR power reduction |
| SPF-09 | Mass spectrometer vacuum pump | Science | Getter backup; 5,000 hr MTTF qual |
| SPF-10 | OBC main computer | Avionics | FDIR auto-restart; persistent state flash |

**Total SPFs identified: 10**

---

## 6. Mitigation Implementation Summary

### 6.1 Redundant Wheel Motor Drivers

Each wheel is driven by a dual H-bridge (DRV8873 × 2 per wheel) with independent current sensing. Primary and backup drivers share the motor winding via a changeover relay (Panasonic AHN, rated 3A continuous). FDIR on the FPGA monitors current waveform deviation and switches to the backup driver within 50 ms. Three-wheel crawl mode is implemented in the wheel controller node; max speed reduced to 0.05 m/s.

### 6.2 Battery Overcurrent Protection

The BMS (Texas Instruments BQ76952) provides cell-level voltage/temperature monitoring at 100 ms sample rate. Overcurrent protection trips within 5 ms of threshold detection. Each cell group (7S) has an inline self-resetting PTC fuse (TE Connectivity RXEF110). A hardware-only comparator (LM393) provides backup overvoltage disconnect independent of the BMS microcontroller.

### 6.3 Backup LGA Antenna

A fixed 4-element patch array (LGA) is mounted on the rover top deck at 0 dBi gain. It provides omnidirectional coverage in the upper hemisphere. Link budget analysis (LPAS-COMMS-003) confirms closure at LRO elevation > 15° with 3 dB margin at 9600 bps. Used when primary gimbal is inoperative.

### 6.4 Watchdog Timeout Recovery (AI Inference)

The Jetson AGX Orin runs a hardware watchdog (GPIO-tied to FPGA) with a 500 ms timeout. If the terrain_segmentation ROS2 node misses its 10 Hz publication, the watchdog fires and the FPGA commands: (1) rover halt, (2) Jetson node SIGKILL + restart via systemd service, (3) fallback to slope-only navigation from pre-loaded DEM-derived traversability map. Recovery time < 8 s.

### 6.5 Manual Drill Retract Spring

A pre-loaded torsion spring (k = 0.12 N·m/rad, stored energy 0.9 J) is held by a solenoid latch during drilling. On power loss or FDIR trigger (motor current > 2.0 A for >200 ms), the solenoid releases and the spring retracts the drill 15 mm — sufficient to break regolith grip. Tested to 1,000 retract cycles (LPAS-SCI-TEST-007).

---

## 7. Summary Statistics

| Metric | Value |
|---|---|
| Total failure modes analyzed | 28 |
| Single Point Failures (SPFs) | 10 |
| Critical items (RPN > 100) | 3 |
| Highest RPN (pre-mitigation) | 120 — Drill motor stall (FM-10) |
| Highest RPN (post-mitigation, estimated) | 72 — Drill motor stall (spring retract reduces D from 3 to 2) |
| Failure modes with no current mitigation | 0 |
| Open actions required before CDR | 4 (see Section 8) |

### 7.1 Critical Path Items

The following items represent the critical reliability path for primary mission success:

1. **Battery thermal control** (SPF-02) — must maintain >−20 °C during 2.88 h PSR dwell
2. **Drill motor stall** (SPF-05) — only path to science sample objective; spring retract is sole recovery
3. **Comms link** (SPF-03, SPF-07 combined) — all science data and commanding passes through LRO relay; LGA backup covers gimbal failure but not LRO orbital geometry gaps
4. **AI inference** (SPF-04) — autonomous traverse impossible without terrain classifier; watchdog recovery essential

---

## 8. Open Actions

| Action ID | Description | Owner | Due |
|---|---|---|---|
| FMEA-OA-001 | Quantify post-mitigation RPN for all 28 modes with updated occurrence rates from component test data | Reliability | CDR |
| FMEA-OA-002 | HP-01 leak rate test: confirm <1×10⁻⁸ std cc/s He at operating pressure | Thermal | CDR |
| FMEA-OA-003 | Drill retract spring 1,000-cycle test in thermal vacuum (−100 °C to +50 °C) | Science Payload | CDR |
| FMEA-OA-004 | Mass spectrometer pump MTTF verification — supplier qualification data required | Science Payload | CDR |

---

*End of LPAS-FMEA-001 Rev A*
