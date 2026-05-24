# LPAS Preliminary Hazard Analysis (PHA)
**Document Number:** LPAS-SAFE-001 | **Revision:** PDR-A | **Date:** 2026-05-24
**Classification:** Unclassified / For Official Use Only
**Prepared By:** LPAS Safety Engineering Team
**Approved By:** LPAS Mission Systems Engineer
**Reference Documents:** NASA-STD-8739.8A (Software Safety Standard), NPR 8715.3C (NASA General Safety Program), MIL-STD-882E (System Safety)

---

## 1.0 Purpose and Scope

This Preliminary Hazard Analysis (PHA) identifies and assesses hazards associated with the Lunar PSR Autonomy Scout (LPAS) rover mission from launch through end-of-mission. The PHA covers all mission phases: pre-launch, trans-lunar cruise, landing, deployment, surface operations, PSR ingress, PSR interior science, and end-of-mission. The analysis addresses hardware, software, and operational hazards and establishes risk control measures to achieve acceptable residual risk levels.

This document is the primary safety input to the LPAS Preliminary Design Review (PDR) and is updated at each design review milestone.

---

## 2.0 Hazard Classification Scheme

### 2.1 Severity Definitions (per MIL-STD-882E)

| Severity Level | Category | Definition | LPAS Context |
|---|---|---|---|
| I | Catastrophic | Loss of mission AND potential for personnel hazard; irreversible mission failure | Total rover loss; lander destruction; crew hazard (Artemis proximity) |
| II | Critical | Loss of primary mission objectives; major system loss; no recovery path | Loss of PSR science capability; rover stranded; critical subsystem failure |
| III | Marginal | Partial mission objective loss; recoverable with mission impact | Reduced science return; constrained traverse; instrument failure |
| IV | Negligible | Minimal mission impact; recoverable without significant resource expenditure | Minor data gaps; single-measurement loss; recoverable anomaly |

### 2.2 Likelihood Definitions

| Likelihood Level | Category | Probability per Mission | Expected Occurrences |
|---|---|---|---|
| A | Frequent | P > 0.20 | Likely to occur multiple times during mission |
| B | Probable | 0.10 < P ≤ 0.20 | Will likely occur once during mission |
| C | Occasional | 0.01 < P ≤ 0.10 | May occur during mission |
| D | Remote | 0.001 < P ≤ 0.01 | Unlikely but possible |
| E | Improbable | P ≤ 0.001 | So unlikely, near zero occurrence expected |

### 2.3 Risk Level Matrix

```
              LIKELIHOOD
              A         B         C         D         E
            Frequent  Probable  Occasional  Remote  Improbable
          ┌─────────┬─────────┬──────────┬────────┬──────────┐
  I  Cat  │   1A    │   1B    │    1C    │   1D   │    1E    │
         │  HIGH   │  HIGH   │   HIGH   │  MED   │   LOW    │
         ├─────────┼─────────┼──────────┼────────┼──────────┤
  II Crit │   2A    │   2B    │    2C    │   2D   │    2E    │
         │  HIGH   │  HIGH   │   MED    │  MED   │   LOW    │
         ├─────────┼─────────┼──────────┼────────┼──────────┤
  III Mar │   3A    │   3B    │    3C    │   3D   │    3E    │
         │  MED    │  MED    │   LOW    │  LOW   │   LOW    │
         ├─────────┼─────────┼──────────┼────────┼──────────┤
  IV Neg  │   4A    │   4B    │    4C    │   4D   │    4E    │
         │  LOW    │  LOW    │   LOW    │  LOW   │   LOW    │
         └─────────┴─────────┴──────────┴────────┴──────────┘

RISK LEVELS:
  HIGH   = Unacceptable; requires redesign or program-level waiver
  MEDIUM = Acceptable with documented mitigation and tracking
  LOW    = Acceptable; monitor and document
```

### 2.4 Risk Acceptance Criteria

| Risk Level | Disposition |
|---|---|
| HIGH | Unacceptable — must reduce to MED or LOW before CDR; program director approval required for any waiver |
| MEDIUM | Acceptable with LPAS safety case documentation and risk tracking board entry |
| LOW | Acceptable; document in risk register; review at next milestone |

---

## 3.0 Preliminary Hazard Analysis Table

| Haz ID | Hazard Description | Primary Cause | Secondary Cause | Effect | Sev | Likelihood (Pre) | Risk (Pre) | Control Measures | Residual Likelihood | Residual Risk |
|---|---|---|---|---|---|---|---|---|---|---|
| HAZ-001 | Wheel motor seizure / jamming (single wheel) | Regolith ingestion into bearing race; thermal shock from PSR cold soak (-230°C) → room temp cycle; impact with hidden rock at ≥ 5 cm depth | Motor controller overcurrent trip without thermal recovery; bearing lubricant solidification below -50°C | Loss of wheel drive; reduced traverse speed (-30%); increased current draw on remaining 5 wheels; slope limit reduced from 25° to 18° | III | C | MED | (1) Titanium mesh wheel design minimizes regolith ingestion pathways; (2) motor current limit set at 8A (1.5× nominal) with thermal rollback; (3) pre-drive warm-up sequence: motor heaters 20 min before cold-start drive; (4) FDIR autonomously adjusts gait to 5-wheel mode; (5) wheel temperature sensors with 60 s polling | D | LOW |
| HAZ-002 | Slope rollover exceeding 30° longitudinal tilt | Rover traverses unseen slope steeper than terrain model resolution allows; terrain model based on 1 m/px LROC NAC data — boulders and micro-slopes unresolved | Active tilt sensor delayed response; hazard avoidance algorithm fails to classify forward terrain at 30 m/hr traverse speed | Catastrophic rover tip-over; structural damage; mission loss; rover may slide into PSR with no power recovery | I | D | MED | (1) Tilt sensor (±45° range, 0.1° resolution) with hardware-level safe stop at 25° (5° margin); (2) LiDAR terrain slope estimation lookahead ≥ 2 m at 2 Hz; (3) max commanded slope limit 20° (5° software margin below hardware limit); (4) traverse speed capped at 15 m/hr on slopes > 15°; (5) pre-drive path terrain analysis using DEM + stereo; (6) slope alarm at 18° triggers operator notification on next comm pass | E | LOW |
| HAZ-003 | Battery thermal runaway (LFP chemistry) | Overcharge above 3.65 V/cell due to PCDU voltage regulator failure; cell internal short from radiation-induced dendrite growth; mechanical puncture during landing shock | BMS single-point failure; simultaneous cell and BMS anomaly | Rapid exothermic reaction; localized heating > 200°C; potential structural damage; total loss of power system; mission loss | I | E | LOW | (1) LFP chemistry selected for inherent thermal stability — onset of thermal runaway > 270°C vs. 150°C for NCA; (2) dual independent cell voltage monitoring: BMS primary + PCDU secondary; hardware overvoltage cutoff at 3.70 V/cell; (3) battery enclosure isolated from electronics bay by 2 mm Al thermal shield; (4) landing shock loads verified ≤ 40 g_rms (GEVS-7000A vibration qualification); (5) charge rate limited to 0.5 C max (75 W) | E | LOW |
| HAZ-004 | Solar array physical damage | Rock strike during traverse; lander plume particle impact during landing; dust accumulation reducing output > 30% | Single-axis deployment mechanism over-extension; micrometeorite impact (flux: ~2×10⁻⁶ kg/m²/yr at lunar surface) | Partial array damage: reduced power output; total damage: mission-limiting power deficit; unable to charge for PSR operations | II | D | MED | (1) Array stowed flat during traverse (protects against rock strikes during driving); (2) array deployed only at charging halts (> 99% of traverse time in stowed config); (3) GaAs cells individually bypassed in series strings — single-cell loss < 3% output reduction; (4) array power monitoring: output compared to model prediction; 20% deviation triggers alert; (5) deployment mechanism stop-limit switches prevent over-rotation | D | LOW |
| HAZ-005 | Earth-to-rover communications LOS loss (> 72 hours) | LRO relay orbital geometry — LRO in maintenance mode or anomaly; DSN aperture scheduling conflict; rover antenna mispointing (terrain blockage) | PSR crater rim obstruction of LRO link; lander RF interference in initial 50 m operations; solar flare communications blackout | Extended ground blackout; no uplink capability; rover operating on stored command buffer; science data accumulation without downlink; possible mission drift from plan | II | C | MED | (1) LPAS stores 8-hour autonomous command buffer from last uplink — operates independently; (2) 16 GB onboard flash prevents data loss for up to 72 hours at full science ops data rate; (3) two independent relay paths: LRO UHF primary + DSN via lander Ka-band backup; (4) safe mode autonomously sun-points and enters beacon mode after 8 hours without uplink; (5) comm loss > 24 hr triggers autonomous return traverse toward last known LOS position | D | LOW |
| HAZ-006 | Electronics cold soak failure in PSR (< -40°C ebox) | Extended dwell in PSR without adequate thermal control; heater circuit failure (single-point); solar array unable to power heaters during deep PSR excursion | PSR floor temperature -230°C (regolith at depth); conduction through wheel struts to chassis; radiative environment ≈ 4 K | Electronics below operating limit: -40°C (per component specification); flight computer lock-up; memory bit errors; battery capacity collapse | I | C | HIGH | (1) Electronics bay passively insulated with 20-layer MLI (effective emissivity ε = 0.02); (2) internal RHU-equivalent resistive heaters: 3×20 W PTC heaters maintain ebox > -20°C at survival power (45 W min); (3) automatic safing: if ebox temp < -35°C → halt traverse → max heater power → exit PSR; (4) thermal model validated to PSR boundary; maximum PSR dwell time = 2.88 h at 52 W (battery-limited); (5) 4 independent ebox temperature sensors with hardware watchdog | D | MED |
| HAZ-007 | Watchdog timer timeout causing flight computer reboot during critical operation | Software hang in autonomy manager node; infinite loop in path planner; memory leak after extended uptime (> 168 hr) | ROS2 node crash; radiation-induced SEU causing bit flip in loop counter; power glitch resetting processor without clean shutdown | Unexpected reboot during PSR traverse: navigation solution lost; current waypoint lost; rover halts in PSR; depending on timing, may halt on slope | II | B | HIGH | (1) Hardware watchdog timer: 5-second timeout requiring heartbeat from flight computer (1 Hz); (2) watchdog trigger → controlled checkpoint save → reboot → state restore from NVM; (3) checkpoint saves every 30 s: position, battery SoC, active waypoint, science queue; (4) FDIR transitions to safe mode before full reboot; (5) dual-redundant flight computers (cold standby); switchover time < 2 s; (6) SEU-tolerant FPGA for watchdog logic; (7) weekly forced reboot in safe charging position planned | C | MED |
| HAZ-008 | Autonomy deadlock — planner unable to resolve path (no valid path found) | Dense boulder field exceeds LiDAR detection range; all paths scored unsafe by hazard detection CNN; goal waypoint inside no-go zone not caught in pre-mission planning | Stereo camera blind spot due to dust on lens; hazard detection false-positive rate > 20% in novel terrain type (pumice, mare basalt edge) | Rover halts indefinitely; no drive progress; battery drains to survival mode threshold; PSR science timeline missed | II | B | HIGH | (1) Maximum planner timeout = 30 s; if no path found → backtrack 5 m → retry; (2) after 3 failed replanning attempts → enter "minimal safe motion" mode → slow reverse 2 m → request ground team re-routing via next comm pass; (3) terrain segmentation model validated on LROC NAC images of Nobile region (training set includes 2,400 lunar south pole frames); (4) maximum false-positive rate spec: < 5% at mAP@0.5 ≥ 0.85; (5) ground-defined "abort corridor" pre-loaded for each PSR ingress — always passable path maintained | C | MED |
| HAZ-009 | Drill binding / TRIDENT seizure at depth | Encountering ice-cemented regolith layer (> 200 MPa compressive strength); drill torque exceeding motor rating (12 N·m peak); drill string entanglement | Unknown subsurface stratigraphy; mixed-composition regolith with > 40% ice fraction; temperature-induced ice refreezing around drill string | Motor burnout; drill mechanism inoperable; sample collection impossible at drilled site; science mission impact (lost drill site) | II | C | MED | (1) Drill torque monitoring: continuous 100 Hz measurement; if torque > 10 N·m for > 2 s → stop rotation → retract 5 mm → resume (anti-bind cycle); (2) TRIDENT drill uses percussive + rotary motion: percussion loosens compacted material ahead of bit; (3) pre-drill surface preparation: rotary brush clears top 2 cm; (4) two pre-qualified backup drill sites per PSR target selected from ground analysis; (5) drill string temperature measured; if > +60°C → pause drill 10 min | D | LOW |
| HAZ-010 | Science payload contamination (organic/volatile false positive) | Rover outgassing contaminates PITMS sample inlet; drill tailings from upwind traverse contaminate spectrometer inlet; hardware-introduced organic compounds from assembly | Solvent residues from PCB manufacturing; lubricant vapor from wheel motors (low vapor pressure at -50°C but possible in PSR); MLVOC from insulation materials | False measurement of volatile concentrations; incorrect WEH % reported; incorrect ice stratigraphy interpretation; LPAS-SCI-001 Level 1 science requirement compromised | II | C | MED | (1) PITMS inlet closed during traverse (dust cover); opens only during dedicated science dwell; (2) all materials < 1 m of PITMS inlet: space-qualified, low-outgassing per ASTM E595 (TML < 1.0%, CVCM < 0.1%); (3) background measurement cycle required at first sol before any regolith disturbance; (4) drill tailings protocol: PITMS inlet faces upwind (away from drill) during sample collection; (5) PITMS venting cycle: 3-minute pre-measurement pump-down to < 10⁻⁶ Torr before data capture | D | LOW |
| HAZ-011 | Lander egress ramp deployment failure | Ramp motor failure; deployment mechanism frozen at -50°C (launch environment); structural interference from landing dust deposition on ramp hinge | Latching mechanism fails to release (launch lock pyro issue); ramp contacts tilted lander body at unexpected angle | Rover trapped on lander; unable to reach lunar surface; mission complete failure | I | D | MED | (1) Ramp deployment motor heated to +20°C before actuation (2-hour pre-heat sequence); (2) dual-redundant deployment motor paths (primary + backup); (3) ramp deployment confirmed via lander camera telemetry before rover drive; (4) alternative egress path: if ramp fails, rover drives off lander deck edge (0.4 m drop — wheel mesh designed for 0.5 m drop per SR-003 shock requirement); (5) pre-deployment lander health check verifies tilt < 15° | D | LOW |
| HAZ-012 | Power system brown-out during peak demand (drill + traverse simultaneously) | Combined drill (60 W) + traverse (50 W motor) + compute (35 W) + heater (20 W) demand exceeds instantaneous battery discharge capacity at cold temperature | Cold battery (−10°C) reduces peak discharge rate to 1.5C vs. 2C at nominal; PCDU load shedding algorithm failure | Voltage sag below 24 V (28 V − 15%) causes flight computer undervoltage reset; FDIR triggers safe mode; drill operation interrupted; data corruption risk | II | C | MED | (1) Operational constraint: drill and traverse not simultaneous; drill operations only at stationary science halt; (2) pre-drill battery check: SoC ≥ 80% required before drill activation; (3) PCDU implements load priority: Level 1 = heaters + computers; Level 2 = comms; Level 3 = science; Level 4 = drive motors; (4) battery heater pre-conditions battery to −5°C before drill start (improves peak current capacity by 20%); (5) brownout detector: if 28 V bus < 25 V → immediate Level 4 load shed | D | LOW |
| HAZ-013 | Radiation-induced SEU causing navigation error or false hazard detection | Galactic cosmic ray heavy ions cause single-event upset in flight computer memory; solar energetic particle event (SEPE) during traverse | Soft errors in LiDAR point cloud buffer cause phantom obstacle; bit flip in waypoint coordinate register causes 10 m position jump | Rover makes incorrect hazard avoidance maneuver; navigates toward hazard instead of away; position estimate diverges from truth | II | C | MED | (1) Flight computer uses LEON4-FT (ERC32 heritage) with hardware triple-modular redundancy (TMR) on critical registers; (2) error-correcting code (ECC) RAM — single-bit correction, double-bit detection; (3) LiDAR point cloud consistency check: 3-frame median filter rejects single-frame anomalies; (4) navigation state vector validated against IMU dead reckoning every 10 m; divergence > 1 m triggers replanning pause and state review; (5) radiation monitor (RadFET dosimeter): SEPE alert if dose rate > 10 mrad/hr → pause traverse, wait for event to pass | D | LOW |
| HAZ-014 | Thermal hardware failure — motor heater open circuit in PSR | PTC heater element fails open due to thermal cycling stress fracture; heater harness connector corrosion (vacuum/thermal cycling) | -230°C regolith conduction through wheel spokes cools motor below -50°C operating limit | Wheel motor seizes (lubricant solidifies); drive capability lost for affected wheel(s); see HAZ-001 cascade | II | C | MED | (1) Two independent heater circuits per motor (primary 10 W + backup 10 W); heaters are redundant and cross-strapped; (2) Kapton-insulated heater elements rated for > 5000 thermal cycles to -230°C; (3) heater current monitoring detects open circuit < 1 s; automatic switchover to backup circuit; (4) motor temperature sensors used in closed-loop heater control (target: -10°C minimum motor case temperature); (5) pre-PSR heater validation test: all heaters verified functional before ingress authorization | D | LOW |
| HAZ-015 | LiDAR or stereo camera PSR performance degradation (darkness) | PSR interior absolute darkness: no solar illumination; stereo cameras unable to generate disparity map without texture gradient | Dust on LIDAR window attenuating return signal; LiDAR photodetector saturation from active LED illumination backscatter | Navigation solution degrades in PSR; obstacle detection range reduced; rover traverses into undetected obstacle > 0.3 m | II | B | HIGH | (1) LPAS equipped with 4 active LED illumination arrays (850 nm, 10 W each) for stereo camera use in PSR darkness; (2) LiDAR (Ouster OS0-32, 850 nm, 50 m range at reflectivity > 10%) operates independent of ambient illumination — verified operational at 0 lux; (3) PSR traverse speed limited to 5 m/hr (vs. 30 m/hr in sunlight) to allow 3× longer dwell for LiDAR return integration; (4) dust cover cleaning: deployment heater + piezoelectric actuator vibrates optical window to dislodge dust before each LiDAR startup; (5) dual-modality detection: hazard must be confirmed by BOTH LiDAR AND stereo before path clearance | C | MED |
| HAZ-016 | Structural failure of rocker-bogie differential linkage | Fatigue failure of differential bar after > 50,000 terrain undulation cycles; binding caused by regolith ingestion into pivot joint; asymmetric wheel loading on steep traverse | Al-alloy fatigue under thermal cycling -230°C to +120°C range; pivot bearing seizure | Loss of body roll compensation; chassis tilts up to 6° for each 12° terrain undulation; exceeds tilt sensor margin; stability degraded on slopes | II | D | MED | (1) Differential bar machined from Ti-6Al-4V (superior fatigue and cryogenic properties vs. Al); (2) FEA analysis: structural margin > 2.5 at 10⁶ cycles (per CDR target); (3) pivot joints use dry-film MoS₂ lubricant (space-qualified, stable to -200°C); (4) pivot seals designed to exclude particles > 0.1 mm from bearing races; (5) structural health monitoring: strain gauge on differential bar with alert at > 60% of yield strain | E | LOW |
| HAZ-017 | Solar array dust contamination exceeding 30% output loss | Accumulated regolith fines electrostatically deposited on solar array surface over 120-sol mission; no cleaning mechanism | South pole dust mobility in partial illumination zone (electrostatic levitation during day/night boundary crossing); lander plume initial contamination | Power deficit: if array output < 140 W (−30%), traverse operations curtailed; battery cycle rate increases; reduced science output | III | B | MED | (1) ITO anti-static coating on solar array coverglass to reduce electrostatic charging (reduces particle attraction by ~40%); (2) conservative power margin designed for 20% degradation at EOL (EOL efficiency 26.5% includes 5% dust factor); (3) power output monitoring: if output < 160 W at optimal angle → science operations prioritized over traverse to extend charge time; (4) periodic array tilt sweep: 10° oscillation at 0.1 Hz loosens deposited fines by inertia (15-minute passive dust mitigation cycle twice per sol) | C | LOW |

---

## 4.0 Risk Matrix — Pre- and Post-Mitigation Summary

### 4.1 Pre-Mitigation Risk Distribution

```
              LIKELIHOOD
              A         B         C         D         E
            Frequent  Probable  Occasional  Remote  Improbable
          ┌─────────┬─────────┬──────────┬────────┬──────────┐
  I  Cat  │         │         │  HAZ-006 │HAZ-002 │  HAZ-003 │
          │         │         │          │HAZ-011 │          │
          ├─────────┼─────────┼──────────┼────────┼──────────┤
  II Crit │         │ HAZ-007 │  HAZ-005 │HAZ-004 │          │
          │         │ HAZ-008 │  HAZ-009 │HAZ-012*│          │
          │         │ HAZ-015 │  HAZ-010 │HAZ-013 │          │
          │         │         │  HAZ-014 │HAZ-016 │          │
          ├─────────┼─────────┼──────────┼────────┼──────────┤
  III Mar │         │ HAZ-017 │  HAZ-001 │        │          │
          ├─────────┼─────────┼──────────┼────────┼──────────┤
  IV Neg  │         │         │          │        │          │
          └─────────┴─────────┴──────────┴────────┴──────────┘
  (* HAZ-012 reassigned II-C after analysis)

  HIGH RISK (pre-mitigation): HAZ-006, HAZ-007, HAZ-008, HAZ-015
  MED  RISK (pre-mitigation): HAZ-001..005, HAZ-009..014, HAZ-016, HAZ-017
```

### 4.2 Post-Mitigation Risk Distribution

```
              LIKELIHOOD
              A         B         C         D         E
            Frequent  Probable  Occasional  Remote  Improbable
          ┌─────────┬─────────┬──────────┬────────┬──────────┐
  I  Cat  │         │         │          │        │  HAZ-003 │
          │         │         │          │        │          │
          ├─────────┼─────────┼──────────┼────────┼──────────┤
  II Crit │         │         │  HAZ-006 │HAZ-002 │          │
          │         │         │  HAZ-007 │HAZ-004 │          │
          │         │         │  HAZ-008 │HAZ-005 │          │
          │         │         │  HAZ-015 │HAZ-011 │          │
          ├─────────┼─────────┼──────────┼────────┼──────────┤
  III Mar │         │         │          │HAZ-001 │          │
          │         │         │          │HAZ-009 │          │
          │         │         │          │HAZ-010 │          │
          │         │         │          │HAZ-012 │          │
          │         │         │          │HAZ-013 │          │
          │         │         │          │HAZ-014 │          │
          │         │         │          │HAZ-016 │          │
          │         │         │          │HAZ-017 │          │
          ├─────────┼─────────┼──────────┼────────┼──────────┤
  IV Neg  │         │         │          │        │          │
          └─────────┴─────────┴──────────┴────────┴──────────┘

  HIGH RISK (post-mitigation): NONE
  MED  RISK (post-mitigation): HAZ-006, HAZ-007, HAZ-008, HAZ-015
  LOW  RISK (post-mitigation): HAZ-001..005, HAZ-009..014, HAZ-016, HAZ-017
```

---

## 5.0 Key Mitigation Strategies by Category

### 5.1 Mobility Hazard Mitigations

The primary mobility risk driver is cold-temperature performance in the PSR environment. Key mitigations are:

- **Pre-traverse thermal conditioning:** All six wheel motors heated to ≥ -10°C before any cold-start drive. PTC heater elements draw 10 W per motor (60 W total for 20-minute pre-heat), consuming 20 Wh of battery — budgeted in the PSR entry power plan.
- **Speed-slope interlock:** Software enforces a dynamic speed limit: v_max = 30 − 1.5×(slope_deg) m/hr, capping traverse speed at 8 m/hr on 15° slopes and 0 on slopes > 20°.
- **Active tilt monitoring:** Hardware tilt interrupt at 25° triggers immediate motor brake (< 10 ms) and FDIR safe stop, independent of flight computer state.
- **5-wheel contingency gait:** FDIR autonomously executes modified 5-wheel gait if one wheel current exceeds 10 A for > 5 s — power redistributed across remaining motors.

### 5.2 Power System Hazard Mitigations

- **LFP chemistry selection:** LFP cells have a flat discharge curve (3.2 V nominal, 3.65 V max), eliminating the lithium plating regime that leads to thermal runaway in NCA/NMC chemistries. The LFP thermal stability onset temperature is 270°C, well above any achievable case temperature in the lunar environment.
- **Load priority hierarchy:** The PCDU enforces a non-overridable hardware load priority table. Level 1 loads (survival heaters, flight computers) cannot be shed by software command — only by hardware undervoltage cutoff (< 20 V bus).
- **Power budget discipline:** A 20% power margin is maintained on all nominal load cases (see LPAS-PWR-001). Peak loads (drill + heaters simultaneously) analyzed as worst-case single events; battery pre-conditioning protocol required before each such event.

### 5.3 Software and Autonomy Hazard Mitigations

- **Checkpoint and recovery architecture:** LPAS flight software saves a full navigation and mission state checkpoint to non-volatile memory every 30 seconds. On any reboot (watchdog-triggered or power cycle), the rover restores from the most recent checkpoint and enters a safe-hold state awaiting ground re-authorization.
- **Autonomy envelope bounding:** For AL-3 (PSR interior), the ground team uploads a defined operating polygon (max dimensions 300 m × 300 m for Phase 5 operations) and an explicit abort corridor before each PSR ingress. The planner cannot command motion outside this envelope.
- **Hazard detection model validation:** The terrain segmentation ONNX model is validated on 2,400 labeled frames from LROC NAC images of the Nobile region and analog terrain datasets. Acceptance criterion: mAP@0.5 ≥ 0.85 on held-out validation set (500 frames). False-positive budget: ≤ 5% (hazard detected where none exists) to prevent excessive path replanning.

### 5.4 Thermal Hazard Mitigations (PSR Cold Soak)

The electronics bay thermal design must survive the PSR deep cold environment:
- **Thermal environment:** PSR floor regolith at depth ≈ -230°C (43 K); effective sky temperature ≈ 4 K (deep space); no solar illumination.
- **Isolation strategy:** 20-layer MLI blanket on all chassis external surfaces; effective emissivity ε_eff = 0.02. Conduction from wheel struts to chassis minimized by Ti-6Al-4V rocker arms (lower conductivity than Al-7075: k = 7 vs. 173 W/m·K).
- **Active heating floor:** Three 20 W PTC heaters in electronics bay provide 60 W maximum heating; survival load analysis (LPAS-PWR-001, Case 4) establishes 2.88-hour maximum PSR dwell at 52 W survival load.
- **Maximum PSR dwell constraint:** Hard operational constraint: LPAS must not dwell in PSR interior for > 2.5 hours without returning to a pre-planned charging position or battery SoC drops below the 20% LFP minimum (see LPAS-PWR-001).

### 5.5 Science Payload Hazard Mitigations

- **PITMS contamination protocol:** Background mass spectrum acquired on first sol before any regolith disturbance. If post-mission background comparison shows VOC signatures above 10 ppb, instrument data flagged for ground review prior to publication.
- **Drill anti-bind active control:** TRIDENT torque measured at 100 Hz; adaptive percussive rate increases from 10 Hz to 30 Hz when torque exceeds 7 N·m, reducing the probability of bind-up before the 10 N·m hard limit is reached.
- **Contamination zone mapping:** Pre-mission analysis using lander plume models (NASA LADEE data for lunar surface contamination) defines a 15 m contamination exclusion zone around the lander. PITMS inlet closed until LPAS is confirmed > 15 m from lander.

---

## 6.0 Hazard Tracking and Closure Process

Each hazard in this PHA is entered into the LPAS Risk Tracking Database (RTD). Hazard status is reviewed at each design milestone (PDR, CDR, TRR) and updated with:
1. Control measure implementation status (Planned → In Work → Implemented → Verified)
2. Verification method (Analysis / Test / Inspection / Demonstration)
3. Residual risk re-assessment after control measure implementation verification

**Open Actions from this PHA:**
| Action ID | Hazard | Action | Owner | Due |
|---|---|---|---|---|
| PHA-ACT-001 | HAZ-006 | TVAC thermal model correlation test for PSR cold soak scenario | Thermal Lead | CDR-30 days |
| PHA-ACT-002 | HAZ-007 | Watchdog timer hardware qualification test at -40°C | Avionics Lead | CDR-60 days |
| PHA-ACT-003 | HAZ-008 | Terrain segmentation model validation on Nobile LROC NAC dataset (2400 frames) | AI/ML Lead | CDR-90 days |
| PHA-ACT-004 | HAZ-015 | LiDAR performance characterization in simulated PSR darkness (0 lux, -100°C) | Sensors Lead | CDR-60 days |
| PHA-ACT-005 | HAZ-002 | Slope terrain model resolution analysis — LROC stereo 1 m/px vs. onboard LiDAR | Navigation Lead | CDR-30 days |

---

*Document end. Next update at CDR based on detailed design verification testing.*
*Reference: LPAS-VVP-001 (V&V Plan) for verification method cross-reference; LPAS-RM-MB-05 for Risk Register.*
