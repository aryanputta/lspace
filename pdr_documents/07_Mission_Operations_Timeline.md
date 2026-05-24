# LPAS Mission Operations Timeline
**Document No.:** LPAS-OPS-001
**Review Level:** PDR-A
**Project:** Lunar PSR Autonomy Scout (LPAS)
**Date:** 2026-05-24
**Status:** Released for PDR

---

## 1. Scope

End-to-end operations timeline from pre-launch through primary science operations at Shackleton Crater rim. Times are relative to launch (L±) and touchdown (T+). All durations are worst-case unless noted.

---

## 2. Pre-Launch Operations (T-7d through T-0)

**Launch Vehicle:** Falcon 9 Block 5 (primary) or Vulcan Centaur VC2S (backup)
- Falcon 9: 5,500 kg net payload to TLI; LC-39A, Kennedy Space Center
- Vulcan Centaur: 6,000 kg to TLI; SLC-41, Cape Canaveral

| Time | Event | Duration | Responsible | Success Criterion |
|---|---|---|---|---|
| T-7d | Final functional test at integration facility; all subsystems on GSE power | 4h | SE + Avionics | All 22 ROS2 nodes nominal; no FDIR flags |
| T-7d | Battery charge to 60% SOC (flight storage level); 72 Wh at 3A (0.2C) | 6h | Power Lead | BMS confirms 60% SOC; cell balance < 15 mV |
| T-7d | Science payload calibration: NIRVSS dark + flatfield; TRIDENT dry-fire | 4h | Science Lead | NIRVSS SNR > 100:1 at 2.1 µm; drill torque 8.5 N·m |
| T-7d | FSW final load: LPAS-FSW-v2.3.1; all ROS2 node checksums verified | 2h | Software Lead | CRC64 matches golden image |
| T-7d | Solar array final deploy/stow cycle; 195 W confirmed on GSE solar sim | 1h | Mechanisms | Deploy and stow < 4 min each; no binding |
| T-5d | Rover-to-CLPS lander integration; umbilical mate (48-pin, +28 VDC) | 3h | Integration | 48/48 pins nominal; rover draws < 5 W (heater only) |
| T-5d | Integrated comms test: UHF loopback via lander relay | 1h | Comms | > 240 kbps downlink confirmed; command uplink verified |
| T-5d | Launch simulation test (LST): full countdown readiness | 3h | FOT | All Go criteria met; FRR complete |
| T-5d | DSN contact verification: Goldstone 34 m session | 30 min | DSN Coord | Link margin ≥ 6 dB; frame sync confirmed |
| T-2d | Final Go/No-Go poll: all 8 subsystem leads | 2h | Mission Director | All leads: Go |
| T-2d | Sol 0 command sequence loaded to flight computer buffer | 1h | Software Lead | Buffer CRC verified; no corruption |
| T-1d | DSN stations briefed: Goldstone 34 m + Canberra 26 m on standby | — | DSN Coord | Schedule confirmed for first 72h post-launch |
| T-12h | MOC 24-hour staffing begins (3 shifts) | — | MOC Lead | All display systems nominal; voice net up |
| T-6h | Propellant load complete; pad cleared | — | Launch Director | — |
| T-4h | Lander terminal countdown autonomy activated; rover heater-only mode | — | FOT | Rover: survival heater 3 W; battery 60% SOC |
| T-30min | Final Go/No-Go; Launch Director concurrence | — | Mission Director | Launch commit issued |
| T-0 | **LAUNCH** | — | — | Falcon 9 lifts off LC-39A; rover in powered-off state |

---

## 3. Trans-Lunar Cruise (L+0 to L+4.5 Days)

| MET | Event | LPAS State | Battery SOC | Notes |
|---|---|---|---|---|
| L+0h | Liftoff and first-stage sep | Off; heater 3 W | 60% | Accelerometer logs launch shock |
| L+0h 08m | Fairing separation | Passive | 60% | Confirmed via lander telemetry |
| L+0h 30m | TLI burn complete; C3 = −2.0 km²/s² | Passive | 60% | Lunar arrival NET L+108h |
| L+24h | Health check 1: housekeeping poll, 10-min session | 5 W | 59% | IMU gyro bias < 0.01°/hr in microgravity |
| L+48h | Health check 2: drive motor heater pulse (5 s); motor response confirmed | 5 W | 58% | — |
| L+72h | Health check 3: flight computer memory ECC scrub | 5 W | 57% | Expect 0–2 corrected single-bit errors |
| L+96h | Health check 4: command buffer re-verified for landing sequence | 5 W | 56% | All health checks nominal → lander LOI go/no-go |
| L+100h | Landing site confirmation (ground-only): 89.9°S, 0.0°E (Shackleton rim) | Ground | — | Final landing ellipse ±0.3° lat, ±0.5° lon |
| L+102h | Lander LOI burn; 900 m/s retrograde; 100 km circular orbit | Passive | 56% | LPAS accelerometer archives structural data |
| L+104h | Descent orbit insertion: 100 km → 18 km | Passive | 56% | — |
| L+106h | PDI T-120 min: LPAS battery charging begins (lander provides 15 W) | Charging | Rising to 70% | IMU activated; navigation initialized |
| L+107h 45m | Navigation solution converges using lander star tracker alignment | IMU active | 68% | Attitude knowledge < 0.1° |
| L+108h | Powered descent final approach: 100 m/s | Charging | 68% | All LPAS loads off except IMU + OBC |
| L+108h 15m | **TOUCHDOWN** at Shackleton rim | Battery-only; IMU running | 70% | Touchdown shock < 1.5 g; tilt < 15° |

**Attitude control during cruise:**
- Lander: sun sensor + star tracker
- Rover in standby: thermostat-controlled heaters only; 3 W survival load

---

## 4. Landing and Deployment: First 2 Hours Post-Touchdown

**Reference:** T+ = minutes after confirmed touchdown at Shackleton rim (89.9°S, 0.0°E)

| T+ | Event | LPAS State | Power | Battery SOC | Notes |
|---|---|---|---|---|---|
| T+0:00 | **TOUCHDOWN — CLPS lander at Shackleton rim** | Standby; IMU running | 8 W | 70% | Accelerometer confirms landing shock < 1.5 g; tilt 2.1° |
| T+1:00 | Lander stability assessment: tilt < 15° confirmed | Standby | 8 W | 70% | 4-point contact verified by load sensors |
| T+2:00 | Dust settling interval begins (ballistic plume, ~10 min) | Standby | 8 W | 70% | Lander cameras monitor; no LPAS commanding |
| T+5:00 | **Rover egress ramp deploy command uplinked** | Pre-deploy | 8 W | 70% | Ground command: EGRESS_RAMP_DEPLOY_CMD; 1.28s one-way delay |
| T+5:30 | Ramp pyro bolt fires; hinge released | Deploy active | 60 W | 69% | Pyro current: 12 A for 50 ms; confirmed |
| T+6:00 | Ramp motor drives to 18° below horizontal | Deploying | 65 W | 69% | Motor current 2.8 A nominal |
| T+7:30 | Ramp fully deployed; latch closed; potentiometer confirms angle | Deploy complete | 30 W | 68% | Lander camera image confirms; ramp clear |
| T+8:00 | Wheel un-braked; drive motor drivers enabled; hazard cameras ON at 2 fps | Egress ready | 35 W | 68% | FSW: STATE → EGRESS_READY |
| T+10:00 | Solar array deployment: SOLAR_ARRAY_DEPLOY_CMD | Array deploy | +148 W input | 68%↑ | Array at sun-pointing; output 148 W (angle-limited at 5° sun elev.) |
| T+15:00 | **Rover drives off lander; first photos uplinked** | Driving | 166 W total | 70% | Speed 0.3 m/s; 45 s to clear ramp; 2.2 m displacement confirmed |
| T+15:30 | First stereo HazCam panorama captured (3 × 1024×1024 JPEG) | Imaging | 55 W | 70% | 22 MB raw → 3.2 MB compressed; uplinked via UHF next pass |
| T+20:00 | Rover 5 m clear of lander plume zone; stops for IMU calibration | IMU cal | 45 W | 71% | 8-point static rotation; 4 min; gyro bias logged |
| T+30:00 | Lander shadow cleared; solar irradiance > 1,360 W/m² confirmed | Charging | Net +110 W | 73% | Heater setpoints: survival −20°C → operational 0°C |
| T+45:00 | **Solar array fully optimized; 194 W output; first power positive** | Power nominal | Net +144 W | 77% | POWER_STATE → NOMINAL; epoch logged |
| T+60:00 | UHF transceiver (437 MHz) link verified: 6 dB margin | Comms check | 55 W | 80% | DSN contact: 8-min pass; 100 kbps; 4.8 MB engineering TLM downlinked |
| T+60:00 | HGA Ka-band (26 GHz) deployed; initial Earth pointing | HGA active | — | 80% | 2 Mbps downlink confirmed; 3.5 dB margin |
| T+75:00 | NavCam stereo pair (1024×1024, 60° FOV, 0.12 m baseline) calibrated | Nav checkout | 50 W | 83% | IMU (HG1900-class, 0.1°/hr bias) calibration complete |
| T+75:00 | Lidar (16-ch, 10 Hz, 50 m range) spinning; 360° scan acquired | Sensor check | — | 83% | 10 m × 10 m terrain map generated; SLAM initialized |
| T+90:00 | **Autonomy system boot; first autonomous navigation step** | Autonomous | 165 W | 86% | All 22 ROS2 lifecycle nodes: UNCONFIGURED → ACTIVE |
| T+90:30 | Nav2 online; costmap built from lidar; first waypoint: 3 m north | Navigating | 165 W | 86% | Hazard detection: 25 ms/frame; terrain seg: 18 ms/frame |
| T+91:05 | First autonomous waypoint reached (3 m in 35 s); no anomalies | Nominal | 45 W | 86% | AUTONOMY_READY telemetry packet transmitted |
| T+105:00 | All systems nominal; battery charging to 100% SOC | Standby | 45 W | 90% | Autonomy manager: INIT → COMMISSIONING |
| T+120:00 | **Deployment complete; Sol 0 success declared** | Nominal ops | 45 W | 94% | First science team status report transmitted |

---

## 5. First 7-Sol Commissioning Sequence

*One sol = one 24-hour Earth-day planning cycle. Shackleton rim receives ~89% illumination; sols here are Earth-day intervals during the lit mission phase.*

### Sol 1 — System Checkout and Sensor Calibration

| LMST | Activity | Duration | Pass Criterion |
|---|---|---|---|
| 05:00 | Morning charge complete (100% SOC) | — | SOC ≥ 100% |
| 06:00 | IMU in-situ calibration: Allan variance; 30-min static log | 30 min | Gyro bias < 0.08°/hr |
| 07:00 | Camera calibration: stereo intrinsic/extrinsic update from ground test chart | 45 min | Reprojection error < 1.5 px |
| 08:00 | Lidar boresight alignment vs. known lander position | 30 min | Range error < 3 cm at 2 m |
| 09:00 | Drive system checkout: all 6 wheels commanded; motor current verified | 30 min | All motors 1.8–3.2 A nominal |
| 10:00 | Nav2 costmap test: 10 m round-trip with obstacle avoidance | 30 min | Return error < 0.05 m |
| 11:00 | Science payload power-on (no operations) | 15 min | All payloads boot without fault |
| 13:00 | DSN Ka-band downlink | 60 min | 400 MB calibration data delivered |
| 17:00 | End Sol 1 ops | — | Battery ≥ 82% SOC |

### Sol 2–3 — First 50 m Traverse Test

| Parameter | Target | Achieved (planned) |
|---|---|---|
| Total traverse distance | 50 m (25 m/sol) | — |
| Nominal traverse speed | 0.3 m/s | — |
| Hazard zone speed | 0.1 m/s | — |
| SLAM position error at 50 m | < 0.5 m | — |
| Slip ratio limit | < 0.4 (stop threshold) | — |
| Waypoints | 10 total, 5 m spacing | — |
| Terrain classes covered | Flat regolith, rocky outcrop, < 10° slope | — |
| Data collected | 6,000 lidar frames, 2,400 stereo images, full IMU log | — |

### Sol 4–5 — Science Payload Checkout

| Payload | Activity | Pass Criterion |
|---|---|---|
| TRIDENT Drill (1 m depth) | Deploy bit; 10 cm drill test | Torque < 15 N·m; no stall; 2.9 cm/min penetration |
| NIRVSS Spectrometer (1–5 µm) | Dark, flatfield, wavelength calibration | SNR > 100:1 at 2.1 µm; wavelength cal ±2 nm |
| HazCam stereo pair | 3D point cloud accuracy vs. surveyed targets | Z error < 2 cm at 3 m |
| NavCam stereo pair | Map vs. lander CAD geometry | Reprojection error < 1.5 px |
| Science camera (4K RGB) | Dark, flatfield, focus test | MTF > 0.4 at Nyquist |

### Sol 6–7 — First PSR Approach

| Step | Activity | Key Metric |
|---|---|---|
| Sol 6 morning | Drive to PSR boundary (120 m from touchdown site) | Speed 0.3 m/s; 7 min traverse |
| Sol 6 midday | Charge to 100% SOC | 2h charge at 194 W; battery full |
| Sol 6 afternoon | PSR boundary mapping: lidar scan at 5 m standoff | 50 m swath; 5 cm resolution |
| Sol 7 morning | PSR entry rehearsal: 10 m inside; 5 min dwell; exit | Battery SOC drop ≤ 5% |
| Sol 7 afternoon | Data review; FSW parameter update if required | All telemetry nominal |
| Sol 7 evening | DSN debrief downlink | 800 MB PSR characterization data |

---

## 6. Nominal Traverse Day (Hour-by-Hour)

| LMST | Phase | Duration | Activities | Power State | Battery SOC |
|---|---|---|---|---|---|
| 05:00–07:00 | **Morning Charge Phase** | 2h | Solar charging at 194 W; FSW health check; uplink next-sol ops plan via LRO morning pass | Net +144 W | 78% → 100% |
| 07:00–11:00 | **Navigation Phase** | 4h | Autonomous traverse at 0.3 m/s; Nav2 path planning active; terrain segmentation + hazard detection every frame; SLAM map updates every 10 m; target: 100 m/sol maximum | 166 W total | 100% → 91% |
| 11:00–13:00 | **Science Operations Phase** | 2h | Rover stationary; NIRVSS 4-spectrum scan (5 min each); TRIDENT drill if warranted; science team decisions arrive in uplink | 50 W; net +144 W solar → charging | 91% → 97% |
| 13:00–14:00 | **Uplink/Downlink Phase** | 1h | LRO UHF pass 1 (~8 min, 250 kbps): telemetry burst ~15 MB; DSN Ka-band (~45 min, 2 Mbps): 300 MB sol data downlink; uplink: next-sol plan | 55 W | 97% → 99% |
| 14:00–16:00 | **Afternoon Charge/Standby** | 2h | Top-off battery; thermal management; non-critical subsystems power down | Net +148 W | 99% → 100% |
| 16:00–17:00 | **Second Comms Pass** | 1h | LRO UHF pass 2 (~8 min): housekeeping telemetry | 50 W | 100% → 99% |
| 17:00–05:00 | **Night Standby** | 12h | Heaters maintain electronics > −40°C; watchdog timer 10-min heartbeat; wakeup at 05:00 | 10 W avg | 99% → 78% |

**Daily data volume:** ~1.2 GB raw; compressed to ~400 MB; ~300 MB downlinked per sol.

---

## 7. PSR Entry Protocol — Detailed Autonomy Sequence

### 7.1 Pre-Entry Conditions (All Required Before Entry)

| Parameter | Requirement | Nominal Value |
|---|---|---|
| Battery SOC | ≥ 100% | 100% (150 Wh) |
| Battery temperature | −10°C to +50°C | +15°C |
| Electronics bay temperature | −20°C to +60°C | +20°C |
| Drive motor temperature | > −30°C all 6 motors | +10°C |
| IMU health | No faults; bias < 0.1°/hr | 0.05°/hr |
| SLAM position uncertainty | < 0.3 m (1σ) | 0.15 m |
| Last Earth contact | < 24h ago | — |
| AI inference engines | All nominal; latency < 30 ms | terrain 18 ms, hazard 25 ms, slip 12 ms |

**Thermal pre-heating:** Drive motor heaters active T−30 min; OBC heaters maintain +20°C minimum.

### 7.2 Entry Phase

| Step | Time | Action |
|---|---|---|
| Entry authorization | T=0 | Ground command OR autonomous trigger after pre-entry check pass |
| Speed reduction | T+0:30 | Ramp 0.3 m/s → 0.2 m/s over 30 s |
| PSR boundary confirmed | T+1:00 | NavCam irradiance < 50 W/m² — PSR boundary crossed |
| All AI models active | T+1:00 | Terrain seg 18 ms, hazard det 25 ms, slip prediction (TCN) 12 ms |
| 30 s hazard check cycle | T+1:00 onward | Full-sensor hazard check every 30 s; stop if hazard score > 0.7 |
| Thermal logging | T+1:00 onward | Every 60 s; alert if any node < −35°C |
| SLAM anchor update | Every 10 m traveled | New keyframe; path tracked for return egress |

### 7.3 Inside PSR Operations

| Parameter | Limit | Auto-Abort Trigger |
|---|---|---|
| Maximum dwell time | 2.88 h | Abort at 2.88 h regardless of state |
| **Nominal dwell (30% margin)** | **2.0 h** | — |
| Battery SOC floor | 40% | Abort if SOC < 40% |
| Slip ratio | < 0.4 | Abort if slip > 0.4 for > 10 s |
| SLAM position uncertainty | < 1.0 m (1σ) | Abort if uncertainty > 2.0 m |
| Drive motor current | < 8 A/wheel | Abort if any wheel stalls > 5 s |
| Speed limit | 0.2 m/s | Hard-coded in FSW for PSR mode |

**Autonomous abort triggers — any one sufficient:**
1. SOC < 40%
2. Elapsed PSR time > 2.88 h
3. Slip ratio > 0.4 sustained 10 s
4. SLAM uncertainty > 2.0 m
5. Any motor current > 8 A for > 5 s
6. Electronics temperature < −40°C
7. Terrain segmentation: > 30% hazard pixels in forward view

### 7.4 PSR Dwell Budget Derivation

| Load Item | Power |
|---|---|
| Drive motors at 0.2 m/s (6 × 250 W motors, partial load) | 30 W |
| NIRVSS spectrometer (science ops) | 7 W |
| Avionics + survival heaters | 15 W |
| **Total PSR load** | **52 W** |
| Full discharge dwell: 150 Wh / 52 W | **2.88 h** |
| Available at 40% SOC floor: 90 Wh / 52 W | 1.73 h |
| **Nominal dwell with 30% time margin** | **2.0 h** |

### 7.5 Exit Phase

| Step | Action |
|---|---|
| Exit trigger | Auto-abort or planned exit at 2.0 h |
| Path selection | Backtrack on inbound SLAM path (primary); computed alternate (secondary) |
| Exit speed | 0.2 m/s; increase to 0.3 m/s once irradiance > 200 W/m² |
| Recharge waypoint | Pre-planned illuminated terrain ≤ 50 m from PSR boundary |
| Post-exit charge | Charge to 90% SOC before further traverse |
| Post-exit data | Full telemetry burst in next comms window |

---

## 8. Earth Contact Windows

### LRO UHF Relay

| Parameter | Value |
|---|---|
| Frequency | 437.1 MHz UHF (downlink) / 401 MHz (uplink) |
| Downlink rate | 250 kbps nominal; 2 Mbps burst |
| Uplink rate | 1 kbps |
| Pass duration | ~8 min per pass |
| Passes per sol (usable) | 2 primary scheduled |
| Volume per pass | ~15 MB downlink |
| LRO orbit | 50 km polar; 118-min period |
| PSR interior coverage | Reduced by crater rim; 4–6 min passes from 100 m depth |

### DSN Ka-Band Direct-to-Earth (via HGA)

| Parameter | Value |
|---|---|
| Frequency | 26.0 GHz Ka-band |
| Data rate | 2 Mbps (LDPC coded) |
| Link margin | 3.5 dB (0.5 m HGA, 34 m DSN station) |
| Contact frequency | 1 per day (DSN scheduling permitting) |
| Contact duration | 45–60 min |
| Volume per contact | ~720 MB |
| Stations | Goldstone, Madrid, Canberra |

**Earth visibility from Shackleton rim (89.9°S):** Earth is permanently above local horizon at 1–5° elevation; communication blackout < 2 h/day (LRO geometry gaps only).

### Maximum Communication Blackout

- Nominal operations: < 2 h/day
- PSR interior: up to 14 days without guaranteed contact if LRO geometry fails (all science pre-authorized by ground)

---

## 9. Emergency Timeline

| Event | Trigger | Automatic Response | Ground Response |
|---|---|---|---|
| Hardware fault (any) | Node fault flag | Autonomy manager → SAFE_MODE; non-essential loads shed | Engineers assess next LRO pass |
| Watchdog timeout | FSW heartbeat missed > 10 min | OBC hardware reset; FSW reload from flash | Fault review; recovery command |
| Safe mode entry | Any critical fault | UHF beacon every 60 s; HGA slewed to Earth; 15 W survival only | Flight Director recovery poll |
| PSR auto-abort | Any abort trigger (§7.3) | Immediate backtrack on SLAM path; UHF burst on exit | Acknowledge; next-sol plan |
| Battery critical (< 20% SOC) | SOC monitor | All loads shed except UHF beacon + heaters | Recovery plan within 24h |
| Thermal critical (< −45°C) | Temperature monitor | Drive stopped; maximum heater power; safe mode | Thermal assessment |
| Recovery from safe mode | Fault cleared | — | Ground command: EXIT_SAFE_MODE + checkout sequence |

**Watchdog → safe mode → ground contact max timeline: 24 h** (bounded by LRO pass schedule).

---

## 10. PSR Entry Sequence Diagram

```mermaid
sequenceDiagram
    participant G as Ground Control
    participant LRO as LRO Relay
    participant AM as Autonomy Manager
    participant NAV as Nav2 / SLAM
    participant AI as AI Inference Engine
    participant PWR as Power Management
    participant SCI as Science Payload (NIRVSS)

    G->>LRO: PSR_ENTRY_AUTH_CMD (uplink)
    LRO->>AM: Forward command (1.28s one-way delay)

    AM->>PWR: Check pre-entry conditions
    PWR-->>AM: SOC=100%, motors +10°C, ebox +20°C — OK

    AM->>NAV: Check SLAM health
    NAV-->>AM: Uncertainty=0.15 m — OK

    AM->>AI: Enable all inference engines
    AI-->>AM: terrain_seg=18ms, hazard_det=25ms, slip_pred=12ms — OK

    AM->>NAV: SET_SPEED(0.2 m/s)
    AM->>AM: STATE → PSR_ENTRY

    AM->>LRO: Pre-ingress health packet (2 MB)
    LRO->>G: Forward telemetry; Flight Director logs GO

    loop Every 30s during PSR traverse
        AI->>AM: Hazard score (threshold 0.7)
        NAV->>AM: Slip ratio update (threshold 0.4)
        PWR->>AM: SOC update (floor 40%)
        AM->>AM: Evaluate abort conditions

        alt Abort condition triggered
            AM->>NAV: BACKTRACK_CMD (inbound SLAM path)
            AM->>SCI: PAYLOAD_SAFE_MODE
            AM->>LRO: ABORT telemetry burst (next pass)
        end
    end

    AM->>SCI: Begin NIRVSS science dwell at WP-PSR-01 (T+15min, 50m depth)
    SCI-->>AM: Science data packaged (0.12 MB)

    alt LRO in view from PSR interior
        AM->>LRO: Transmit science + health (6 MB)
        LRO->>G: Relay data
        G->>LRO: CONTINUE_AUTHORIZED
        LRO->>AM: Forward authorization
    else LRO occluded by crater rim
        AM->>AM: Cache data; continue on pre-authorized plan
    end

    AM->>NAV: Continue traverse to WP-PSR-02 (100m), then WP-PSR-DRILL (200m)

    alt Planned exit at T+2.0h
        AM->>SCI: SCIENCE_WRAP_CMD
        AM->>NAV: BACKTRACK_CMD (inbound path)
    end

    NAV->>AM: PSR boundary crossed (irradiance > 200 W/m²)
    AM->>NAV: SET_SPEED(0.3 m/s)
    AM->>PWR: Charge to 90% SOC at illuminated waypoint
    AM->>LRO: PSR_COMPLETE telemetry (next pass)
    LRO->>G: Forward completion report
    AM->>AM: STATE → NOMINAL_OPS
```

---

## 11. Document Control

| Field | Value |
|---|---|
| Document Number | LPAS-OPS-001 |
| Revision | A |
| Review Level | PDR-A |
| Next Review | CDR |
| Parent Documents | LPAS-CON-001 (ConOps), LPAS-PWR-001 (Power Budget), LPAS-HAZ-001 (Hazard Analysis) |
