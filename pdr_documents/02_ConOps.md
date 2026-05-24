# LPAS Concept of Operations (ConOps)
## Document Number: LPAS-OPS-002 | Revision: A | Date: 2026-05-24

---

**Mission:** Lunar PSR Autonomy Scout (LPAS)
**Prepared By:** LPAS Mission Operations Team
**Approved By:** LPAS Mission Director
**Reference:** NPR 7120.5E; LPAS-SYS-003 (SRR); Artemis South Pole ConOps Framework Rev A

---

## 1.0 Purpose and Scope

This Concept of Operations (ConOps) describes the operational approach for the Lunar PSR Autonomy Scout mission from launch through end-of-mission. It defines mission phases, stakeholder roles, communication architecture, autonomy levels, fault response procedures, and a representative day-in-the-life scenario. The ConOps is the primary operations planning document and serves as input to the Mission Operations Timeline (LPAS-OPS-007).

---

## 2.0 Mission Overview

LPAS will be delivered to the lunar south polar region aboard a Commercial Lunar Payload Services (CLPS) Task Order lander (IM-3 class or equivalent). Following lander touchdown at Nobile Crater rim (85.2°S, 32.0°E ±500 m), LPAS deploys via a motorized egress ramp and begins a 120-sol surface mission. The rover traverses from the illuminated rim toward PSR targets, conducting geophysical surveys, percussive drilling, and volatile characterization at up to three PSR sites.

**Key Parameters:**
| Parameter | Value |
|-----------|-------|
| Launch Vehicle | Falcon 9 Block 5 (CLPS secondary payload) |
| Trans-Lunar Cruise Duration | 4–6 days |
| Landing Site | Nobile Crater, 85.2°S, 32.0°E |
| Lander | IM-3 / Nova-C Block 2 (estimated) |
| Mission Duration | 120 sols (primary); extended to 180 sols if power permits |
| Total Traverse Distance (Baseline) | ≥ 5 km |
| Relay Asset | LRO (primary) + Lunar Gateway (if commissioned) |
| One-Way Light Time | 1.28 s (minimum) – 1.44 s (maximum) |

---

## 3.0 Mission Phases

### Phase 0: Launch and Trans-Lunar Injection (L-Day to L+6 Days)

**Duration:** ~6 days
**Rover State:** Powered off; survival heaters active via lander power; IMU in standby

**Key Activities:**
- Launch aboard CLPS lander; LPAS in stowed, launch-locked configuration
- LPAS receives lander-provided power (+28 VDC regulated); battery maintained at 60% SoC
- LPAS flight computer remains in cold standby; watchdog timer armed
- No rover commanding during ascent and TLI burn
- 24 hours post-TLI: LPAS health check via lander telemetry relay; confirm battery SoC, thermal state, and IMU bias stability
- DSN coverage: 8 hr/day tracking through lander RF system (UHF relay to X-band lander downlink)

**Constraints:**
- LPAS must not draw > 5W from lander during ascent (launch power budget constraint)
- Rover bay temperature must remain > -30°C (lander thermal control responsibility)
- No pyro events prior to lunar surface operations

**Success Criteria:** LPAS received on lander; battery SoC ≥ 55% at lunar arrival; no anomalies in health check

---

### Phase 1: Lander Descent and Touchdown (Lunar Arrival Day = Sol 0)

**Duration:** ~2 hours (powered descent + touchdown)
**Rover State:** Battery charging mode; all non-essential loads off

**Key Activities:**
- LPAS flight computer powers on ~4 hours before powered descent initiation (PDI)
- IMU alignment and navigation solution initialized using lander star tracker data
- Post-touchdown: lander stability assessment (tilt angle < 15°); LPAS nominal if tilt < 10°, limited operations 10–15°
- Lander transmits touchdown confirmation to DSN; ground team verifies LPAS health
- Rover bay depressurization (vents to lunar vacuum) — no mechanism needed, passive
- Deployment ramp actuator heaters enabled (+2 hours post-touchdown)

**Constraints:**
- LPAS commanding delayed ≥ 1 hour post-touchdown to allow lander settling and dust clearance
- Dust contamination mitigation: keep science cameras stowed until lander thruster contamination zone is confirmed clear (> 2 m)
- Lander must achieve tilt < 15° for nominal rover egress (ramp deployment constraint)

**Success Criteria:** Lander stable; LPAS battery SoC ≥ 70% after charging; flight computer nominal; deployment ramp heaters responsive

---

### Phase 2: Deployment and Egress (Sol 0–Sol 2)

**Duration:** 2 sols
**Rover State:** Transition from lander power to autonomous solar charging

**Key Activities:**
- Sol 0 (L+4 hr): Ground team reviews touchdown imagery and authorizes deployment
- Sol 0 (L+5 hr): Deployment ramp motor commanded; ramp deploys in 8 minutes; confirmation via lander cameras
- Sol 0 (L+6 hr): Wheel articulation to drive-ready position; solar array deployment (fold-flat to drive configuration, +34° cant angle)
- Sol 0 (L+7 hr): First roll: egress from lander to lunar surface; 2 m driven; stop and take first surface panorama (HAZCAMs + NavCAMs)
- Sol 1: IMU calibration drive (10 m N-S traverse, 10 m E-W traverse); attitude determination validation; solar array power verification (expected: 185 ± 15 W at sol 1 sun angle, β = 5°)
- Sol 2: 50 m checkout drive toward south (toward PSR direction); telemetry collection and science camera commissioning; LiDAR boresight calibration vs. known lander position

**Constraints:**
- Egress must occur within daylight window (solar elevation > 1° at landing site, ≥ 18 hr continuous for Nobile rim)
- Solar array power must be verified before cutting lander power umbilical
- Science instruments remain stowed/capped during egress (contamination protection)

**Autonomy Level:** Level 1 (fully ground-commanded); all drive commands uplinked and executed with ground approval

**Success Criteria:** All wheels on lunar surface; solar charging verified > 150 W; stereo cameras nominal; IMU drift < 0.1°/hr

---

### Phase 3: South Pole Survey — Illuminated Zone Transects (Sol 3–Sol 60)

**Duration:** 57 sols
**Rover State:** Nominal operations; daily traverse + science

**Key Activities:**
- Sol 3–7: Instrument commissioning; TRIDENT drill dry run (no sample); LPAS-NS background count verification; LPAS-RAD calibration
- Sol 8–30: Primary survey transect: 3 km traverse from lander toward Nobile PSR-A boundary; average 100 m/sol traverse; neutron spectrometer measurements every 50 m (20-min dwell per station); LiDAR terrain mapping continuously during traverse
- Sol 31–45: Secondary transect north-south across crater rim; slope characterization and boulder survey; CPT measurements at 3 pre-selected locations on illuminated terrain (engineering calibration)
- Sol 46–60: Approach to PSR-A boundary; detailed terrain mapping of ingress corridor; 50-m resolution topographic strip mapped via stereo cameras + LiDAR; pre-PSR entry thermal characterization (thermocouple surface measurements at ≥ 5 stations); science team deliberation on ingress target

**Daily Operations Pattern (Traverse Sol):**
| Time (LMST) | Activity | Duration |
|-------------|----------|----------|
| 05:00–07:00 | Wake + battery charge (solar) | 2 hr |
| 07:00–07:30 | Downlink playback of previous sol data via LRO pass | 30 min |
| 07:30–08:00 | Upload command sequence for current sol | 30 min |
| 08:00–12:00 | Traverse (Level 2 autonomy, 30 m/hr average) | 4 hr |
| 12:00–13:00 | Mid-sol stop: NS station dwell (20 min) + image capture | 1 hr |
| 13:00–17:00 | Continue traverse | 4 hr |
| 17:00–18:00 | Science instrument measurements at final waypoint | 1 hr |
| 18:00–19:00 | Telemetry compression and packetization | 1 hr |
| 19:00–20:00 | LRO evening pass — downlink science and telemetry | 1 hr |
| 20:00–05:00 | Low-power standby (battery trickle charge) | 9 hr |

**Power State:** Nominal (solar primary, battery buffer for peaks)
**Comms Windows:** 2× LRO passes/day (~8 min each); 1× direct DSN pass every 3 days (backup)
**Autonomy Level:** Level 2 (autonomous traverse on planned paths; human approval for new path segments > 50 m)

**Success Criteria:** ≥ 2.5 km traverse completed; ≥ 30 NS measurement stations; terrain map generated for PSR-A ingress corridor

---

### Phase 4: PSR Ingress Preparation (Sol 61–Sol 70)

**Duration:** 10 sols
**Rover State:** Reduced thermal margin (approaching shadow boundary)

**Key Activities:**
- Sol 61–63: Science team and navigation team joint review of terrain map; selection of ingress waypoint (slope < 12°, cleared of boulders > 0.3 m diameter in 2 m wheel path width)
- Sol 64–66: Thermal model update for expected PSR environment (-230°C surface at depth; ~-100°C ambient regolith at surface); heater power budget verification; RHU equivalent thermal load analysis
- Sol 67: Transition to "PSR approach" power mode: battery charged to 95% SoC; non-essential loads shed; science instruments set to survive mode
- Sol 68–69: Slow approach traverse across shadow boundary at 10 m/hr; thermal telemetry monitoring every 60 s; automatic safing if electronics bay temperature drops below -35°C (3 hr no-sun scenario)
- Sol 70: Confirm full PSR entry; report first interior observations; establish PSR operational baseline

**Constraints:**
- Solar arrays receive minimal power once > 30 m inside PSR boundary (solar elevation < 0.5°); battery-only operations
- Worst-case battery endurance in PSR: 14 hours at 45 W science ops load (2.1 kWh usable)
- No more than 8 hr continuous operations without return to charging zone (Sol 68–69 boundary transits only)
- Ground team must explicitly authorize each PSR ingress step (Level 1 commanding for ingress waypoints)

**Autonomy Level:** Level 1 for ingress route; Level 2 for hazard avoidance within approved corridor

**Success Criteria:** LPAS crosses PSR boundary to ≥ 50 m interior depth; all subsystems nominal; thermal margins maintained

---

### Phase 5: PSR Science Operations (Sol 71–Sol 100)

**Duration:** 30 sols
**Rover State:** Battery-constrained; PSR interior operations

**Key Activities:**
- Sol 71–75: Initial PSR-A characterization; NS grid survey (5×5 stations, 25 m spacing); surface temperature array deployment; LiDAR terrain scan of 200 m × 200 m zone
- Sol 76–80: First drill site selection and preparation; TRIDENT drill Site 1 (PSR-A); 50 cm drill to bedrock or maximum depth; sample delivery to PITMS; NIR spectral analysis of drill tailings
- Sol 81–85: Traverse to Site 2 within PSR-A (200 m west); repeat NS survey + TRIDENT drill; CPT measurement at Site 2; heat flow probe deployment and 72-hr soak
- Sol 86–90: Return to PSR boundary for battery recharge and data downlink; science team data review and Site 3 selection
- Sol 91–95: Re-entry to PSR-B (Shackleton approach, if terrain accessible); 5-station NS transect; 1 drill attempt
- Sol 96–100: Return traverse from PSR; consolidate science data; sample cache preparation for potential Artemis retrieval; radiation detector 120-hr continuous soak

**Battery Management (PSR Interior):**
- Operations limited to 6-hour active sessions per recharge cycle
- Minimum battery departure SoC: 85% (ensures return traverse power)
- During active science ops: 45 W total load; 8.6 Wh/km traverse energy; 2.1 kWh usable PSR battery reserve at departure
- Depth of discharge limit: 20% (LFP chemistry, cycle life preservation)

**Comms Windows (PSR Interior):**
- LRO pass: 2× per day, ~6 min usable per pass (geometry-dependent); relay store-and-forward for asynchronous commanding
- Gateway relay (if available): continuous coverage, 100 kbps uplink/downlink
- Ground contact during battery-constrained ops: Uplink command buffer loaded before each PSR ingress; rover executes autonomously for up to 6 hours

**Autonomy Level:** Level 3 (full autonomous traverse within PSR; replanning based on terrain hazards detected by LiDAR and stereo; science target selection advisory from onboard science autonomy module; all drill operations require ground confirmation via stored command sequences)

**Success Criteria:** ≥ 2 drill sites sampled; ≥ 1 PSR site fully characterized (PITMS + NS + NIR + CPT); ≥ 500 MB science data acquired

---

### Phase 6: Sample Cache Delivery and End-of-Mission (Sol 101–Sol 120)

**Duration:** 20 sols
**Rover State:** Degraded (end-of-life power; reduced battery capacity assumed)

**Key Activities:**
- Sol 101–105: Return traverse to vicinity of lander (~3 km); cache sample container deposited at pre-surveyed surface waypoint within 100 m of lander; GPS-quality position fix via LiDAR landmark matching
- Sol 106–110: Science data consolidation; all raw data confirmed downlinked; instrument calibration target observations for post-mission data processing
- Sol 111–115: Extended mission bonus activities (if power sufficient): additional NS transect; meteorite flux sensor extended exposure; Langmuir probe electric field survey
- Sol 116–119: Power system state-of-health report; battery capacity fade characterization; documentation of operational lessons learned for heritage to Artemis rovers
- Sol 120: End-of-Mission commanding; safe park position (solar array facing sun, antenna pointed toward LRO relay corridor); all data confirmed at DSN; mission declared complete

**Success Criteria:** All primary science products downlinked and verified at LPAS Science Operations Center; sample cache deposited and position recorded; final telemetry archived

---

## 4.0 Stakeholder Roles and Responsibilities

### 4.1 Organization Chart

```
LPAS Mission Director (NASA SMD)
├── Mission Systems Engineer (MSE)
├── Flight Operations Team (FOT)
│   ├── Flight Director
│   ├── Rover Driver (RD) — 2x per shift
│   ├── Systems Controller (SYSCON) — power, thermal, comms
│   └── Anomaly Response Team (ART)
├── Science Team
│   ├── Principal Investigator (PI)
│   ├── Science Operations Lead
│   ├── Instrument PIs (per instrument)
│   └── Science Uplink Leads (4x, one per instrument suite)
├── Navigation Team
│   ├── Navigation Lead
│   ├── Terrain Analyst
│   └── Autonomous Systems Operator (ASO)
└── Ground System Team
    ├── DSN Coordinator
    ├── Mission Planning Lead
    └── Data Management
```

### 4.2 Role Descriptions

| Role | Responsibility | Authority |
|------|---------------|-----------|
| Mission Director | Mission go/no-go decisions; stakeholder interface | Final authority on all mission phases |
| Flight Director | Real-time operations; anomaly response; shift oversight | All real-time rover commanding |
| Rover Driver | Path planning; drive command authoring; terrain assessment | Drive operations within Flight Director authority |
| SYSCON | Power, thermal, comm budget monitoring; load shedding decisions | Subsystem commanding within flight rules |
| PI | Science priorities; target selection; data quality assessment | Science operations planning |
| Science Ops Lead | Sol-by-sol science planning; STM margin tracking | Science uplink sequence approval |
| Navigation Lead | Pose estimation; map updates; traverse plan generation | Navigation product delivery |
| ASO | Autonomy level transitions; behavior parameter updates; fault autonomy monitoring | Autonomy configuration changes |

---

## 5.0 Communication Architecture and Ground Contact Schedule

### 5.1 RF Architecture

```
LPAS Rover ←→ LRO Relay Orbiter ←→ DSN Ground Station ←→ LPAS SOC (JPL/GSFC)
     UHF 400 MHz                Ka-band 26 GHz           Internet/NISN
     5W TX, 5 dBi               20W TX, 0.5m dish
     5 km range                 384,400 km
     ~6 Mbps peak data          1 Mbps downlink
```

**Relay Characteristics:**
| Parameter | UHF Rover–LRO | Ka-band LRO–Earth |
|-----------|--------------|-------------------|
| Frequency | 401 MHz (uplink) / 437 MHz (downlink) | 25.9 GHz (down) / 26.1 GHz (up) |
| TX Power | 5 W rover / 15 W LRO | 20 W LRO |
| Antenna Gain | 5 dBi rover (patch array) | 30 dBi (0.5 m dish) |
| Free Space Path Loss | 101 dB (5 km, 400 MHz) | 210 dB (384,400 km, 26 GHz) |
| Data Rate | 256 kbps nominal (2 Mbps peak) | 1 Mbps nominal |
| Session Duration | 6–12 min per LRO pass | 15 min per DSN contact |
| Link Margin | 8 dB (UHF) | 6 dB (Ka) |

### 5.2 Ground Contact Schedule

| Contact Type | Frequency | Duration | Data Volume | Purpose |
|-------------|-----------|----------|-------------|---------|
| LRO morning pass | Daily | 6–10 min | 120 MB down / 5 MB up | Primary science downlink |
| LRO evening pass | Daily | 6–10 min | 120 MB down / 5 MB up | Telemetry + command uplink |
| DSN direct (X-band) | 2× per week | 60 min | 500 MB down (via lander) | Emergency; backup command |
| Gateway relay (if available) | Continuous | 24 hr/day | 100 kbps continuous | Preferred if operational |
| Emergency uplink | As needed | 30 min minimum | Command-only | Anomaly response |

### 5.3 Communication Blackout Periods

- **PSR Interior Operations:** Signal shadowing by crater rim geometry causes periodic LRO link outage of up to 4 hours per orbit (LRO orbital period 118 min; ~40% occultation from PSR floor of Nobile)
- **Lander Obstruction:** During initial operations, lander body may block UHF LOS for azimuths 180°–220° from rover. Rover must be > 50 m from lander for unobstructed sky access
- **DSN Scheduling Gaps:** DSN 34 m aperture availability not guaranteed; 48 hr scheduling lead time required; backup 26 m aperture at Goldstone on standby

**Blackout Mitigation:** LPAS autonomy system operates without ground contact for up to 8 hours (command buffer stored from last uplink). Science data buffered onboard with 16 GB flash storage capacity.

---

## 6.0 Fault Response Decision Tree

### 6.1 Fault Detection, Isolation, and Recovery (FDIR) Architecture

**Three-level FDIR hierarchy:**

```
Level 1 — Component-Level (< 1 s response)
   Hardware watchdog timers, voltage/current trip limits, thermal switches
   Action: Power cycle component; switch to redundant (if available); raise fault flag

Level 2 — Subsystem-Level (1–30 s response)
   Flight computer monitors subsystem health; compares against limits table
   Action: Safe subsystem; issue alert to ground; hold traverse; continue mission if possible

Level 3 — System-Level (30 s – 15 min response)
   Mission manager assesses overall system state; trajectory toward survival or end-of-mission
   Action: Enter safe mode; face sun; antenna toward Earth/relay; wait for ground contact
```

### 6.2 Fault Response Decision Tree

```
FAULT DETECTED
│
├── Is fault life-critical (thermal runaway, total power loss, structural)?
│   YES → EMERGENCY SAFE MODE
│         - All non-essential loads off immediately
│         - Solar array align to sun (drive if needed)
│         - UHF beacon mode (1 min ping every 5 min)
│         - Wait for ground contact (up to 24 hr autonomy)
│   NO → Continue to next decision
│
├── Is fault a single subsystem failure with available backup?
│   YES → ISOLATE AND SWITCH REDUNDANCY
│         - Power off failed unit
│         - Switch to redundant unit
│         - Log fault; uplink alert on next pass
│         - Continue operations at reduced capability
│   NO → Continue
│
├── Is fault a transient (soft error, bit flip, watchdog reset)?
│   YES → RESET AND RETRY
│         - Power cycle affected unit
│         - Re-run initialization sequence
│         - If recurs > 3 times → escalate to subsystem fault
│   NO → Continue
│
├── Is fault science instrument failure (non-life-critical)?
│   YES → INSTRUMENT SAFE MODE
│         - Power off instrument
│         - Continue rover traverse operations
│         - Ground team notified on next pass
│         - Science team evaluates mission impact (mission success re-assessed vs. STM)
│   NO → Continue
│
└── All other faults → CONDITIONAL SAFE MODE
      - Suspend autonomous traverse
      - Hold position
      - Continue health monitoring and data collection
      - Uplink detailed fault report on next pass
      - Await ground team diagnosis and recovery commanding
```

### 6.3 Safe Mode Definition

In Safe Mode, LPAS maintains the following minimum functions:
| Function | State |
|----------|-------|
| Flight computers | Primary only; secondary in cold standby |
| Solar arrays | Sun-pointing (use rover drive to align if necessary) |
| Battery | Charging; discharge limited to comms and heaters |
| UHF comms | Beacon + receive only (5 W TX) |
| Thermal | All survival heaters enabled (45 W total) |
| Science instruments | All powered off |
| Navigation | IMU running; cameras off |
| Safe Mode Duration | Self-sustaining indefinitely while sun-pointing |

---

## 7.0 Day-in-the-Life Operation Scenario — Traverse + Science Sol (Sol 42)

**Context:** Sol 42; LPAS is at survey waypoint WP-42 (3.2 km from lander, 1.1 km from PSR-A boundary); nominal traverse + NS science sol; Level 2 autonomy active.

### 7.1 Timeline

| LMST | Event | System State | Notes |
|------|-------|-------------|-------|
| 05:00 | Auto-wake from overnight low-power standby | Flight computer boot complete; battery SoC 91% | Solar elevation = 4.2°; charging rate = 85 W |
| 05:05 | Power-on sequence: IMU, NavCam, HAZCAM, LPAS-NS | All nominal; IMU warm-up 15 min | SYSCON monitors boot telemetry |
| 05:20 | IMU navigation solution converged; pose uncertainty < 0.5 m | Navigation nominal | Star camera not used during travel (daylight operations) |
| 05:30 | Solar charging rate peaks: 185 W; battery charging at 18 W | Battery SoC rises to 93% | Sun elevation = 5.1° |
| 06:00 | LRO morning pass begins (06:02 – 06:10 LMST) | UHF link established; 247 kbps throughput | 8 min pass; 14.8 MB uplinked (command sequence) |
| 06:02 | Flight Director approves day's command sequence upload | Drive path WP-42 → WP-43 authorized (120 m heading 174°T) | Science stop at WP-42B (60 m mark) for NS dwell |
| 06:10 | LRO pass ends; command sequence stored in flight computer | All commands verified; checksums match | 6 hr autonomous operations window begins |
| 07:00 | Drive sequence initiates: depart WP-42 heading south | Speed 30 m/hr; HAZCAM running at 2 Hz; LiDAR active | Level 2: autonomous hazard avoidance enabled |
| 07:45 | HAZCAM detects rock ~0.28 m height at bearing 178°, 3.2 m ahead | Onboard SLAM updates local obstacle map | Replanning triggered; 0.8 m lateral detour; total path deviation +1.2 m |
| 07:52 | Obstacle cleared; resume nominal heading 174°T | Speed restored to 30 m/hr | Replanning response time: 7 s (meets SR-039 ≤ 15 s requirement) |
| 09:15 | WP-42B reached (60 m mark); NS dwell station begins | Rover stops; all motion locked | LPAS-NS measurement commences |
| 09:15–09:35 | LPAS-NS 20-min dwell: 21,450 epithermal counts recorded; 187 thermal counts | NS power: 4 W; measurement quality nominal | HAZCAM passive monitoring for terrain changes during dwell |
| 09:35 | NS measurement complete; data packaged and checksummed | 0.12 MB NS data generated | Stereo panoramic image taken (4× 1024×1024 pairs) — 15 MB |
| 09:40 | Drive resumes toward WP-43 (remaining 60 m) | Speed 30 m/hr | |
| 10:55 | WP-43 reached; arrival position 119.8 m from WP-42 (nav accuracy: 0.2 m) | Traverse complete; drive motors standby | End-of-traverse panorama: 8× image pairs = 30 MB |
| 11:00 | Science ops begin: LPAS-NIRS NIR surface scan (5 min integration) | NIRS power: 6 W; detector temp: -50°C (nominal) | 4 spectra acquired (nadir, 30°N, 30°S, 30°E pointing) |
| 11:30 | LPAS-TC thermocouple array deployed: surface temp = -57°C measured | TC data: 0.1 MB | Consistent with model prediction ±8°C |
| 12:00 | Midday standby: all instruments in low-power hold | Solar charging 175 W; battery topping to 97% SoC | Flight computer running health monitor only |
| 13:30 | Science instrument measurements complete; data compression begins | PITMS not needed on this sol (traverse-only sol) | Total science data generated: ~52 MB compressed |
| 14:00 | LRO afternoon pass (14:04 – 14:13 LMST) | UHF link: 231 kbps; 9 min pass | 31.5 MB downlinked: 30 MB science + 1.5 MB telemetry |
| 14:13 | LRO pass ends; remaining 21 MB queued for evening pass | Data buffer 21 MB remaining | |
| 16:00 | Housekeeping: power bus health check; battery discharge cycle monitoring | All limits nominal; no faults | Wheel motor temperature: -23°C (nominal for traversed terrain) |
| 17:30 | LRO evening pass (17:32 – 17:42 LMST) | 10 min pass; 36 MB downlink capacity | Full remaining 21 MB downlinked + 15 MB telemetry |
| 18:00 | Uplink window confirmation: all data received; command verification for Sol 43 | FOT confirms data integrity | Ground team has full sol products within 4 hours of generation |
| 19:00 | Low-power standby mode initiated | Battery SoC 98%; solar charging 40 W (sun elevation 2.1°) | Survival heaters active: 12 W total |
| 20:00–05:00 | Overnight standby | Battery SoC: 98% → 94% overnight (heater drain) | Auto-wake at 05:00 Sol 43 |

**Sol 42 Summary:**
- Distance traversed: 119.8 m
- Science data generated: 52 MB compressed
- Science data downlinked: 52 MB (100% return rate)
- Power consumed: 1.8 kWh (traverse) + 0.4 kWh (science) + 0.3 kWh (comms) = 2.5 kWh total
- Power generated: 2.8 kWh (solar) — positive energy balance: +0.3 kWh net
- All fault flags: nominal (zero faults)

---

## 8.0 Autonomy Levels

### 8.1 Autonomy Level Definitions

| Level | Name | Description | Ground Interaction | When Used |
|-------|------|-------------|-------------------|-----------|
| **AL-1** | Ground-Commanded | All rover actions result from explicit ground commands; no onboard initiative beyond basic fault protection | Ground team approves every action; 2.5 s minimum command latency | Deployment, ingress, drill operations, anomaly recovery |
| **AL-2** | Supervised Autonomy | Rover executes ground-approved plan autonomously; onboard hazard avoidance permitted; replanning within ±10 m of planned path allowed without ground approval | Ground approves path segments; rover executes and adapts locally | Standard traverse operations (Phase 3) |
| **AL-3** | Full Autonomy | Rover self-selects waypoints, traverses, and science observations within a ground-defined science zone; reports decisions to ground asynchronously; human override always possible via stored abort command | Ground defines operating envelope; rover operates independently for up to 8 hr | PSR interior operations (Phase 5), emergency traverse to charging zone |

### 8.2 Autonomy System Architecture

**Key Software Components:**
1. **ROS2 Autonomy Stack:** Nav2 navigation; behavior trees for mission management; SLAM for localization
2. **Terrain Assessment Module (TAM):** LiDAR + stereo fusion; slope/roughness/step-height analysis; path safety scoring
3. **Science Autonomy Module (SAM):** Onboard NS/NIRS data interpretation; target prioritization scoring; "go/no-go" for science dwell
4. **FDIR Manager:** Real-time fault monitoring; level 1/2/3 responses; safe mode sequencer
5. **Mission Manager:** Orchestrates all modules; tracks sol-by-sol plan execution; manages command buffers

### 8.3 Autonomy Level Transition Rules

| Transition | Trigger | Authorization |
|-----------|---------|---------------|
| AL-1 → AL-2 | Post-checkout verification complete (Sol 7); ground command | Flight Director |
| AL-2 → AL-3 | PSR interior entry confirmed; ground command issued | Mission Director + Flight Director joint approval |
| AL-3 → AL-2 | PSR egress completed; automatic after departure from PSR boundary | Automatic |
| Any → AL-1 | Fault detected OR explicit ground command | Automatic (fault) or Flight Director (command) |
| Any → Safe Mode | Critical fault; power < 10%; temp limit exceeded | Automatic (hardware + software) |

---

## 9.0 Contingency Operations

### 9.1 Wheel Failure Contingency

**Single Wheel Failure (1 of 6):** Rover continues at reduced stability; traverse speed reduced by 30%; slope limit reduced from 25° to 18°; mission continues.
**Two-Wheel Failure (same side):** Traverse capability severely degraded; return traverse to lander vicinity; mission enters reduced operations mode; PSR science limited to boundary approach.
**Two-Wheel Failure (opposite sides):** Rover motion still possible with modified gait; reduced to 40% speed; mission continues at degraded capability.

### 9.2 Communication Loss Contingency

**Duration < 8 hr:** Execute stored command buffer autonomously; wait for next LRO pass.
**Duration 8–24 hr:** Hold current position; sun-pointing for battery charge; beacon mode UHF; wait.
**Duration 24–72 hr:** Execute "communications loss protocol" — retravel to last known good communications position; attempt DSN direct link via lander if within range.
**Duration > 72 hr:** Emergency safe mode; maintain battery charge; transmit health beacon every 5 min; ground team attempts recovery via alternate relay (Gateway, KPLO, Chandrayaan-3 relay, if available).

### 9.3 Permanent Eclipse (Power Loss) Contingency

In the event of unexpectedly long eclipse (lander shadow block, terrain feature, array degradation):
- Automatic transition to survival heater mode only at SoC < 15%
- Minimal telemetry beacon transmitted every 30 min
- All science and drive operations suspended
- Expected survival time at -20°C ambient: 120 hours (5 days) on survival heaters alone at minimum heater power (15 W) with battery reserve

---

*Document end. See LPAS-OPS-007 for detailed sol-by-sol timeline and LPAS-SYS-003 for system requirements that drive these operational constraints.*
