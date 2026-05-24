# LPAS System Requirements Review (SRR)
## Document Number: LPAS-SYS-003 | Revision: A | Date: 2026-05-24

---

**Mission:** Lunar PSR Autonomy Scout (LPAS)
**Prepared By:** LPAS Systems Engineering
**Approved By:** LPAS Mission Systems Engineer
**Reference:** NPR 7120.5E; NASA/SP-2016-6105; LPAS-OPS-002 (ConOps); LPAS-SCI-001 (STM)

---

## 1.0 Purpose and Scope

This System Requirements Review (SRR) document establishes the complete, traceable, and verifiable set of mission and system requirements for the LPAS rover. Requirements are organized in a two-tier hierarchy:

- **Mission Requirements (MR):** Derived from NASA/SMD programmatic direction, science objectives (STM), and Artemis precursor mission constraints
- **System Requirements (SR):** Derived from mission requirements; allocated to rover subsystems; form the basis for subsystem specifications

All requirements are formatted with: ID, Statement, Rationale, Verification Method, Parent Requirement, and Status.

**Verification Methods:**
- **(A)** Analysis — mathematical/simulation-based demonstration
- **(I)** Inspection — visual or dimensional check
- **(T)** Test — laboratory or environmental testing
- **(D)** Demonstration — functional demonstration in relevant environment

---

## 2.0 Mission Requirements (MR-001 through MR-015)

---

**MR-001**
**Statement:** The LPAS rover shall traverse a minimum cumulative distance of 5 km during the primary 120-sol mission.
**Rationale:** Science objectives require visits to ≥ 3 PSR sites separated by up to 2 km; transit from lander to PSR-A is ~3 km; return traverse required.
**Verification:** T — Drive distance accumulated via odometry + visual odometry correlation; validated in analog terrain test.
**Parent:** NASA SMD LDEP Science Requirement SR-WATER-01.
**Status:** Baseline

---

**MR-002**
**Statement:** The LPAS rover shall characterize water ice content (H₂O wt%) at ≥ 1 PSR site to threshold mission success, and ≥ 3 PSR sites to full mission success, as defined in LPAS-SCI-001.
**Rationale:** Directly drives STM Goal 1 and primary ISRU assessment objective.
**Verification:** D — Drill, sample handling, PITMS analysis demonstrated on analog regolith simulant; data product format verified.
**Parent:** STM SG-1, SO-1.1.
**Status:** Baseline

---

**MR-003**
**Statement:** The LPAS rover shall return a minimum of 500 MB of compressed science data to Earth for threshold mission success, and ≥ 5 GB for full mission success.
**Rationale:** Science teams require minimum data volumes for valid geophysical analyses; 500 MB represents ≥ 3 drill events + NS grid + terrain mapping.
**Verification:** A/T — Data volume calculated from instrument data rates × operational scenarios; comms link budget verified by analysis.
**Parent:** STM measurement requirements; LPAS-SYS-MB-04 (Comms Budget).
**Status:** Baseline

---

**MR-004**
**Statement:** The LPAS rover shall survive and operate on slopes up to 25° in any direction on the lunar surface.
**Rationale:** Nobile crater PSR ingress corridors include slopes up to 22° (LRO/LOLA DEM analysis); 3° margin applied.
**Verification:** T — Rover demonstrated on 25° slope (0.5 g equivalent or 1g slope test); tip-over analysis by A.
**Parent:** Landing site terrain analysis (LPAS-NAV-TERRAIN-001).
**Status:** Baseline

---

**MR-005**
**Statement:** The LPAS rover shall operate for a minimum of 120 sols from lunar surface touchdown.
**Rationale:** Full science program requires 120 sols; eclipse survival, component reliability, and margin must all support this duration.
**Verification:** A — Reliability analysis (FMEA); power budget margin analysis; component lifetime qualification data.
**Parent:** LPAS mission definition document.
**Status:** Baseline

---

**MR-006**
**Statement:** The LPAS rover total wet mass shall not exceed 250 kg, including all payload, propellant, and margin.
**Rationale:** CLPS lander IM-3 rover accommodation constraint limits rover mass to ≤ 250 kg to preserve lander landing margin.
**Verification:** I/T — Mass properties measurement at system-level ATP; mass budget maintained per LPAS-SYS-MB-01.
**Parent:** CLPS IM-3 ICD, Section 4.2.
**Status:** Baseline (current CBE: 202 kg; margin to requirement: 48 kg)

---

**MR-007**
**Statement:** The LPAS rover shall autonomously navigate and avoid obstacles without real-time ground interaction for periods of up to 8 continuous hours during PSR interior operations.
**Rationale:** PSR interior operations experience LRO relay blackouts of up to 4 hours; operations plan requires 8-hour autonomous windows for efficiency.
**Verification:** D — Autonomous traverse demonstrated on analog terrain without ground contact for ≥ 8 hr.
**Parent:** LPAS-OPS-002, Phase 5 PSR Operations; ConOps Autonomy Level AL-3.
**Status:** Baseline

---

**MR-008**
**Statement:** The LPAS rover shall survive a thermal environment ranging from -230°C (PSR surface contact) to +130°C (illuminated regolith peak) without damage to any flight-critical hardware.
**Rationale:** Nobile PSR surface temperatures reach ~40 K (-233°C); illuminated south polar regolith reaches ~120°C peak. Both environments are encountered during the nominal mission.
**Verification:** T — Thermal vacuum testing over component survival ranges; A — thermal model correlation.
**Parent:** LPAS-SYS-MB-03 (Thermal Budget).
**Status:** Baseline

---

**MR-009**
**Statement:** The LPAS rover shall maintain continuous uplink/downlink communication capability via LRO relay or equivalent, with a maximum data blackout period of 24 hours.
**Rationale:** Ground team must be able to intervene in anomaly situations within 24 hours; 24-hour buffer consistent with LRO orbital geometry and LRO relay reliability history.
**Verification:** A — LRO orbital coverage analysis; communications architecture link budget.
**Parent:** LPAS-OPS-002, Section 5.0.
**Status:** Baseline

---

**MR-010**
**Statement:** The LPAS rover shall deposit a sealed surface sample cache at a surveyed location within 100 m of the CLPS lander for potential retrieval by Artemis crew.
**Rationale:** Artemis program objective to enable crew sample retrieval; cache position must be survey-quality accurate.
**Verification:** D — Cache deployment mechanism demonstrated; position reporting accuracy verified.
**Parent:** NASA Artemis South Pole Precursor Science Plan, 2024.
**Status:** Baseline

---

**MR-011**
**Statement:** The LPAS rover shall complete all primary science operations with ≤ 15% probability of mission failure due to single-point failures in any non-redundant critical subsystem.
**Rationale:** Program risk posture; aligns with NASA Class C mission reliability targets.
**Verification:** A — FMEA; fault tree analysis; reliability block diagram.
**Parent:** NASA Class C mission reliability standard.
**Status:** Baseline

---

**MR-012**
**Statement:** The LPAS rover shall not contaminate PSR science measurement sites with Earth-origin volatile species at levels greater than 1% of the expected natural volatile signal.
**Rationale:** Volatile contamination of PSR measurements would invalidate science return and compromise orbital calibration objectives.
**Verification:** A/T — Outgassing analysis per ASTM E 595; material selection TML < 0.5%; contamination transport model.
**Parent:** STM Planetary Protection constraints; COSPAR Category IV.
**Status:** Baseline

---

**MR-013**
**Statement:** The LPAS rover shall provide real-time telemetry at a minimum rate of 1 packet per 60 seconds during all operational phases.
**Rationale:** Ground team requires minimum health visibility; 60-second cadence matches LRO relay data buffer timing.
**Verification:** T — Telemetry generation rate verified in ground integration testing.
**Parent:** LPAS-OPS-002, Section 5.0; MO team requirement.
**Status:** Baseline

---

**MR-014**
**Statement:** The LPAS rover design shall incorporate no single-point failure that would cause loss of mission capability without any indication to the ground team within 24 hours.
**Rationale:** Silent failure leading to total mission loss within undetectable time window is unacceptable for Class C mission.
**Verification:** A — Fault tree analysis; FMEA criticality analysis; FDIR architecture review.
**Parent:** MR-011; NPR 8715.3 fault tolerance requirements.
**Status:** Baseline

---

**MR-015**
**Statement:** The LPAS rover shall operate compatibly with the CLPS lander interface, including mechanical, electrical, RF, and thermal interfaces, as defined in LPAS-SYS-004 (ICD).
**Rationale:** CLPS lander is the delivery vehicle and initial power/comms relay; interface compatibility is mandatory for mission success.
**Verification:** I/T — Interface verification at lander integration; ICD compliance review.
**Parent:** CLPS Task Order ICD; LPAS-SYS-004.
**Status:** Baseline

---

## 3.0 System Requirements (SR-001 through SR-040)

### 3.1 Mobility Requirements

---

**SR-001**
**Statement:** The LPAS rover shall traverse a minimum of 100 m per sol during Phase 3 (survey) operations.
**Rationale:** 5 km over 50 traverse sols = 100 m/sol minimum; provides schedule margin for science stops.
**Verification:** T — Demonstrated on analog terrain simulating lunar regolith (GRC simulant BP-1 or JSC-1AF).
**Parent:** MR-001.
**Status:** Baseline

---

**SR-002**
**Statement:** The LPAS rover shall be capable of a nominal traverse speed of ≥ 30 m/hr on level terrain (slope ≤ 5°) with full autonomy enabled.
**Rationale:** 30 m/hr × 4 hr active traverse window = 120 m/sol; meets SR-001 with margin.
**Verification:** T — Measured drive speed on level analog terrain.
**Parent:** SR-001; MR-001.
**Status:** Baseline

---

**SR-003**
**Statement:** The LPAS rover mobility system shall maintain directional control on slopes up to 25° without exceeding a side-slip angle of 3° from intended heading.
**Rationale:** PSR ingress corridors have slopes up to 22°; heading accuracy required for terrain mapping correlation.
**Verification:** T — Slope traverse test at 25° on analog regolith; heading deviation measured by IMU.
**Parent:** MR-004.
**Status:** Baseline

---

**SR-004**
**Statement:** The LPAS rover shall be capable of traversing over surface rocks up to 0.25 m in height with all six wheels maintaining contact with the terrain.
**Rationale:** LOLA DEM data for Nobile crater shows rock exposure rates consistent with 1–5% of terrain covered by rocks ≥ 0.1 m; 0.25 m clearance provides 2× rock height margin.
**Verification:** T — Rock-climbing test over 0.25 m obstacle.
**Parent:** MR-004.
**Status:** Baseline

---

**SR-005**
**Statement:** The LPAS rover wheel diameter shall be ≥ 0.35 m and wheel width ≥ 0.12 m to provide adequate traction and floatation on loose regolith.
**Rationale:** Regolith simulant traction analysis (terramechanics): wheel diameter-to-radius ratio and contact patch area calculated for CPT-derived bearing capacity; floatation requirement for low-cohesion regolith (c = 0.1 kPa).
**Verification:** A — Terramechanics analysis (Bekker model); T — wheel slip vs. normal load on simulant.
**Parent:** SR-002; MR-004.
**Status:** Baseline

---

**SR-006**
**Statement:** The LPAS rover shall be capable of extricating itself from a soft-soil entrapment using wheel differential driving and rocking maneuvers without ground intervention.
**Rationale:** Rover entrapment in low-cohesion PSR regolith is a credible risk; autonomous extrication reduces mission impact.
**Verification:** T/D — Entrapment test in analog regolith; autonomous extrication maneuver demonstrated.
**Parent:** MR-007; MR-011.
**Status:** Baseline

---

**SR-007**
**Statement:** The LPAS rover rocker-bogie suspension shall limit body tilt angle to ≤ 35° under worst-case terrain with one wheel in a 0.30 m depression.
**Rationale:** Electronics bay has gravity-sensitive components; 35° limit prevents fluid/thermal management issues; inertial navigation accuracy degrades beyond 35° tilt.
**Verification:** A — Kinematics model; T — single-wheel drop test.
**Parent:** MR-004; MR-008.
**Status:** Baseline

---

### 3.2 Power Requirements

---

**SR-008**
**Statement:** The LPAS power system shall provide a minimum of 150 W solar-derived power during nominal operations at Nobile crater rim (85.2°S) during the primary mission window (Q4 2028 – Q1 2029).
**Rationale:** Total nominal operating load = 138 W; 150 W provides 9% charging margin to maintain battery SoC during traverse operations.
**Verification:** A — Solar irradiance model at south polar geometry; array output calculation at mission solar angles.
**Parent:** MR-005; MR-006.
**Status:** Baseline

---

**SR-009**
**Statement:** The LPAS solar array end-of-mission (EoM) power output shall be ≥ 130 W (accounting for UV degradation, micrometeorite pitting, and dust accumulation over 120 sols).
**Rationale:** Array degradation of 10–15% expected over mission life (Mars heritage data scaled to lunar environment); 130 W EoM still meets survival heater + comms loads.
**Verification:** A — Array degradation model; T — UV + particle radiation dose testing of solar cell coupon.
**Parent:** SR-008; MR-005.
**Status:** Baseline

---

**SR-010**
**Statement:** The LPAS battery system shall provide a minimum usable energy of 2.1 kWh (depth of discharge ≤ 20% for LFP chemistry) to sustain PSR interior operations for ≥ 6 continuous hours at nominal science operations load (45 W).
**Rationale:** 45 W × 6 hr = 0.27 kWh minimum ops energy; 2.1 kWh capacity allows for traverse energy (8.6 Wh/km × 2 km = 17.2 Wh), science ops, and return traverse margin.
**Verification:** T — Battery discharge test at 45 W load from 100% to 80% SoC.
**Parent:** MR-007; MR-008.
**Status:** Baseline

---

**SR-011**
**Statement:** The LPAS battery shall maintain operability (charge/discharge) across a temperature range of -20°C to +40°C.
**Rationale:** Battery bay temperature in PSR approach operations will fall to -20°C minimum (thermal analysis); +40°C maximum in high-power charge scenario.
**Verification:** T — Battery charge/discharge cycle test over -20°C to +40°C range; capacity retention ≥ 90%.
**Parent:** MR-008.
**Status:** Baseline

---

**SR-012**
**Statement:** The LPAS survival heater system shall maintain all electronics bay components above -40°C during PSR operations (no solar input, 6-hour duration).
**Rationale:** -40°C is the cold survival limit for flight computer, memory, and power electronics; PSR ambient radiative environment is < -200°C; MLI + RHU-equivalent heaters required.
**Verification:** A — Thermal analysis; T — thermal vacuum test at PSR thermal environment (< -100°C environment, 6-hr soak).
**Parent:** MR-008; SR-010.
**Status:** Baseline

---

**SR-013**
**Statement:** The LPAS power system shall provide uninterrupted 28 VDC ± 2 V regulated power to the flight computer under all load conditions from 0 to peak load (210 W total system load).
**Rationale:** Flight computer and navigation sensors require regulated power within ±7% of nominal; unregulated bus variation would cause CPU resets.
**Verification:** T — Power bus regulation test under full load transient (0 → 210 W step).
**Parent:** MR-011; MR-014.
**Status:** Baseline

---

**SR-014**
**Statement:** The LPAS power management and distribution unit (PMAD) shall provide independent over-current protection for each subsystem power branch.
**Rationale:** Single shorted component must not cause bus collapse; branch protection isolates faults without affecting other subsystems.
**Verification:** T — Short circuit test on each branch; verify main bus remains within ±5% during fault.
**Parent:** MR-011; MR-014.
**Status:** Baseline

---

### 3.3 Thermal Requirements

---

**SR-015**
**Statement:** The LPAS electronics bay shall maintain all internal components within their operating temperature range (-20°C to +50°C) during all mission phases, including 6-hour PSR interior operations.
**Rationale:** Component operating ranges define inner electronics bay requirement; FPGA and memory devices limit at -20°C (cold) and +70°C (hot); 50°C internal limit provides 20°C margin to component limits.
**Verification:** A — Thermal analysis (SINDA/Fluint or equivalent); T — Thermal vacuum test.
**Parent:** MR-008.
**Status:** Baseline

---

**SR-016**
**Statement:** The LPAS battery thermal management system shall maintain battery cells within -10°C to +35°C during charging and -20°C to +45°C during discharge.
**Rationale:** LFP battery chemistry charge rate severely degrades below -10°C; electrolyte damage occurs above +50°C; operating limits provide 10°C margin to damage limits.
**Verification:** T — Thermal vacuum test with battery charging and discharging at boundary temperatures.
**Parent:** SR-011; MR-008.
**Status:** Baseline

---

**SR-017**
**Statement:** The LPAS thermal design shall limit heat dissipation from the electronics bay radiator to ≤ 25 W at 0°C radiator temperature, using a radiator area of ≤ 0.3 m².
**Rationale:** Radiator sizing based on maximum steady-state dissipation from all operating electronics (25 W at 0°C on 0.3 m² provides margin for worst-hot case in full solar illumination at landing site).
**Verification:** A — Thermal analysis (radiator sizing); T — radiator performance measurement in thermal vacuum.
**Parent:** SR-015; MR-008.
**Status:** Baseline

---

**SR-018**
**Statement:** The LPAS MLI blanket system shall achieve an effective system emissivity of ≤ 0.03 for the electronics bay enclosure.
**Rationale:** 15-layer MLI with aluminized Mylar/Dacron spacers achieves ε_eff ≈ 0.02; requirement set at 0.03 to allow for MLI blanket seams, cutouts, and installation imperfections.
**Verification:** A — MLI effective emissivity calculation per standard multi-layer model; T — thermal conductance test on blanket sample.
**Parent:** SR-012; SR-015.
**Status:** Baseline

---

**SR-019**
**Statement:** The LPAS wheel/drive motor assemblies shall survive a thermal cycle from -120°C to +120°C without loss of functional capability.
**Rationale:** Wheel motors on lunar surface exposed to full solar illumination (≤ +120°C) and deep shadow/PSR environment (≤ -120°C); motors must restart after cold soak.
**Verification:** T — Motor thermal cycle test from -120°C to +120°C for 20 cycles; torque output measured before/after.
**Parent:** MR-008.
**Status:** Baseline

---

### 3.4 Communications Requirements

---

**SR-020**
**Statement:** The LPAS rover shall maintain a UHF link (400–437 MHz band) to LRO relay at a minimum data rate of 128 kbps during all LRO passes with an elevation angle > 5° above the local horizon.
**Rationale:** 128 kbps × 8 min pass = 61 MB/pass; minimum to maintain science data return within 24 hours; elevation > 5° ensures adequate link margin at all usable relay geometries.
**Verification:** A — Link budget analysis; T — RF performance test at 128 kbps with lab relay simulation.
**Parent:** MR-003; MR-009.
**Status:** Baseline

---

**SR-021**
**Statement:** The LPAS rover UHF system shall achieve ≥ 8 dB link margin when communicating with LRO at ranges up to 5 km at a data rate of 256 kbps.
**Rationale:** 8 dB margin consistent with NASA link design practice; accounts for pointing uncertainty, terrain obstruction margin, and relay hardware variation.
**Verification:** A — Link budget analysis per RF link budget document (LPAS-SYS-MB-04).
**Parent:** SR-020; MR-009.
**Status:** Baseline

---

**SR-022**
**Statement:** The LPAS rover shall store a minimum of 16 GB of uncompressed science and engineering data onboard, supporting ≥ 3 days of full science operations without downlink.
**Rationale:** 3-day comms blackout in PSR produces ~507 MB/day × 3 = 1.5 GB; 16 GB provides 10× margin and supports full extended-mission buffer.
**Verification:** I/T — Memory capacity verification; data volume model validation.
**Parent:** MR-003; MR-009.
**Status:** Baseline

---

**SR-023**
**Statement:** The LPAS rover uplink command receiver shall process and acknowledge command packets within 500 ms of receipt.
**Rationale:** Ground team uplink verification requires timely ACK; 500 ms command processing time adds < 5% to 2.5-second one-way light time for responsive commanding.
**Verification:** T — Command latency test (receive-to-ACK timing measured in integration test).
**Parent:** MR-013.
**Status:** Baseline

---

**SR-024**
**Statement:** The LPAS rover shall transmit a health beacon packet (containing minimum power, thermal, and fault status) at minimum once per 5 minutes in safe mode, using ≤ 1 W transmit power.
**Rationale:** Safe mode comms must conserve power; 1 W TX extends battery-only survival from 6 to > 8 hours; 5-minute beacon cadence allows ground detection of entry to safe mode within one LRO pass.
**Verification:** T — Safe mode beacon test: 1 W TX, 5-min interval, verified in RF test.
**Parent:** MR-009; MR-013; MR-014.
**Status:** Baseline

---

### 3.5 Science Payload Requirements

---

**SR-025**
**Statement:** The LPAS science payload total mass shall not exceed 22 kg, inclusive of all instruments, sample handling hardware, and associated mounting structures.
**Rationale:** 22 kg science payload allocation per mass budget (LPAS-SYS-MB-01); mass margin preserved for system-level growth.
**Verification:** I/T — Science payload mass measurement at PDR mass audit.
**Parent:** MR-006.
**Status:** Baseline

---

**SR-026**
**Statement:** The LPAS TRIDENT drill shall penetrate to a minimum depth of 50 cm in lunar regolith simulant with estimated compressive strength ≤ 10 MPa.
**Rationale:** STM SO-1.1 requires samples at 0–10, 10–30, 30–50 cm depth; 50 cm minimum drill depth.
**Verification:** T — Drill penetration test in high-density regolith simulant (compressive strength 5–10 MPa, density 1,600 kg/m³).
**Parent:** MR-002; STM SO-1.1.
**Status:** Baseline

---

**SR-027**
**Statement:** The LPAS PITMS volatile mass spectrometer shall achieve a lower detection limit of ≤ 0.1 wt% H₂O equivalent in regolith samples.
**Rationale:** STM requires H₂O measurement with ±2 wt% precision; detection limit must be well below expected minimum values; 0.1 wt% sensitivity consistent with VIPER PITMS qualification data.
**Verification:** T — PITMS sensitivity test with calibrated H₂O-doped simulant samples; detection verified at 0.1 wt% level.
**Parent:** MR-002; STM SO-1.1.
**Status:** Baseline

---

**SR-028**
**Statement:** The LPAS neutron spectrometer (LPAS-NS) shall achieve a statistical precision of ≤ 3% (1σ) in epithermal neutron count rate over a 300-second integration period in an environment equivalent to 5 wt% H₂O regolith.
**Rationale:** STM SO-1.3 traverse measurement precision; 3% statistical precision in 300 s provides adequate H₂O discrimination for mapping at ≥ 1 wt% changes per 50 m traverse step.
**Verification:** T — NS calibration test with calibrated H₂O regolith simulant; A — Monte Carlo N-Particle (MCNP) modeling of expected count rates.
**Parent:** MR-002; STM SO-1.3.
**Status:** Baseline

---

**SR-029**
**Statement:** The LPAS science camera (LPAS-MC) shall achieve a spatial resolution of ≤ 0.5 mrad/pixel in its highest-resolution imaging mode.
**Rationale:** 0.5 mrad/pixel at 5 m range = 2.5 mm/pixel; sufficient to identify sub-cm-scale regolith texture, ice crystal clumps, and color variation for geologic interpretation.
**Verification:** T — Camera resolution test using USAF 1951 chart; measured against ≤ 0.5 mrad/pixel specification.
**Parent:** MR-002; STM SO-4.1.
**Status:** Baseline

---

**SR-030**
**Statement:** The LPAS science payload shall collect at least two complete science "event packages" (drill + PITMS + NS + NIRS) per sol during peak science operations (Phase 5, Sol 71–100) when battery and thermal margins allow.
**Rationale:** 30-sol PSR phase with ≥ 3 drill sites requires efficient science cadence; 2 events/sol (at target sites) is achievable within battery and thermal constraints per ConOps analysis.
**Verification:** D — Science cadence demonstrated in operational rehearsal with real hardware.
**Parent:** MR-002; MR-007.
**Status:** Baseline

---

### 3.6 Reliability and Fault Tolerance Requirements

---

**SR-031**
**Statement:** The LPAS flight computer shall be implemented with dual-redundant (cold standby) CPUs with automatic failover within 30 seconds of primary CPU failure detection.
**Rationale:** Loss of flight computer = total mission loss; dual redundancy required per MR-014; 30 s failover time ensures FDIR remains timely.
**Verification:** T — CPU failover test: inject primary CPU fault; measure failover time; verify nominal operations on secondary.
**Parent:** MR-011; MR-014.
**Status:** Baseline

---

**SR-032**
**Statement:** The LPAS system shall tolerate any single-wheel failure without loss of traverse capability to within 50% of full traverse speed.
**Rationale:** 6-wheel rocker-bogie with independent wheel drives provides inherent single-wheel-loss tolerance; 50% speed reduction is acceptable per mission timeline margin.
**Verification:** A — Kinematics analysis with 1-of-6 wheel locked; T — drive test with one wheel disabled.
**Parent:** MR-011.
**Status:** Baseline

---

**SR-033**
**Statement:** The LPAS Mission-Critical software shall have a mean time between software-induced anomalies of ≥ 2,000 hours of operation.
**Rationale:** 120 sols = ~2,880 hours; target of ≥ 2,000 hours means < 1.44 expected software anomalies over mission; consistent with NASA Class C software reliability targets for autonomous systems.
**Verification:** A — Software fault rate analysis from unit/integration test defect density data; heritage software reliability models.
**Parent:** MR-011.
**Status:** Baseline

---

**SR-034**
**Statement:** The LPAS power system shall implement battery over-temperature protection with hardware cutoff at 60°C cell temperature, independent of flight software.
**Rationale:** Battery thermal runaway is a catastrophic failure mode; hardware protection required independent of software to prevent software fault masking battery over-temperature.
**Verification:** T — Battery over-temperature test: inject 60°C condition; verify hardware cutoff before software response.
**Parent:** MR-014; MR-011.
**Status:** Baseline

---

**SR-035**
**Statement:** The LPAS FDIR system shall detect a critical power system fault (bus voltage < 22 V) and initiate safe mode within 1 second.
**Rationale:** Battery discharge below 22 V indicates SoC < 5% (LFP discharge curve); immediate safe mode required to preserve remaining energy for comms and heaters; 1-second response is achievable in hardware-assisted FDIR.
**Verification:** T — Power bus undervoltage fault injection test; safe mode response timing measured.
**Parent:** MR-014; SR-024.
**Status:** Baseline

---

### 3.7 Autonomy Requirements

---

**SR-036**
**Statement:** The LPAS navigation system shall estimate rover position with an accuracy of ≤ 1.0 m (1σ) after 100 m of traverse, relative to a known starting position, using visual odometry and IMU dead reckoning.
**Rationale:** Science measurements must be spatially co-registered with LRO orbital map at ≤ 1 m accuracy; 100 m traverse without ground beacon or landmark update drives the onboard navigation accuracy requirement.
**Verification:** T — Navigation accuracy test on analog terrain; position error measured at 100 m intervals vs. surveyed ground truth.
**Parent:** MR-007; STM SO-4.1.
**Status:** Baseline

---

**SR-037**
**Statement:** The LPAS terrain assessment module (TAM) shall detect obstacles ≥ 0.20 m in height at a range of ≥ 3 m ahead of the rover's planned path, with a false negative rate of ≤ 2%.
**Rationale:** Minimum stopping distance at 30 m/hr ≈ 0.5 m; 3 m detection range provides 6× stopping distance margin; 0.20 m is ≈ 80% of the maximum traversable rock height (0.25 m), ensuring pre-detection.
**Verification:** T — Obstacle detection test at 3 m range; measured false-negative rate for 0.20 m obstacles on analog terrain.
**Parent:** MR-007; SR-004.
**Status:** Baseline

---

**SR-038**
**Statement:** The LPAS autonomy system shall replan a safe detour path around a detected obstacle within 15 seconds without ground intervention, maintaining traverse direction to within ±20° of the original heading.
**Rationale:** 15-second replanning with 30 m/hr traverse speed = < 0.125 m additional travel during replanning; ±20° heading tolerance maintains progress toward science target.
**Verification:** T — Replanning response time measured in simulation + hardware-in-the-loop test; timing and heading deviation measured.
**Parent:** MR-007; SR-037.
**Status:** Baseline

---

**SR-039**
**Statement:** The LPAS autonomy system shall execute all commanded safe-mode transitions within 5 seconds of fault detection, regardless of current autonomy level.
**Rationale:** 5-second response ensures all actuators can reach safe state before rover travels > 0.04 m at maximum speed; critical for avoiding terrain falls or thermal exceedances.
**Verification:** T — Fault injection test; safe mode transition timing measured from fault trigger to all-motors-stopped state.
**Parent:** MR-007; MR-014; SR-035.
**Status:** Baseline

---

**SR-040**
**Statement:** The LPAS mission manager software shall maintain a 120-sol mission execution timeline with ≤ 5% schedule deviation in science activity completion, accounting for unplanned replanning events up to 4× per traverse sol.
**Rationale:** Science timeline drives mission success; 5% deviation on 120 sols = 6 sols of slack; 4 replanning events per traverse sol is the 95th-percentile terrain complexity scenario from VIPER analog tests.
**Verification:** D — Mission manager demonstrated in operational simulation spanning 120 sols of simulated terrain data.
**Parent:** MR-007; MR-002.
**Status:** Baseline

---

## 4.0 Requirements Summary

| Category | Count | ID Range |
|----------|-------|----------|
| Mission Requirements | 15 | MR-001 – MR-015 |
| Mobility | 7 | SR-001 – SR-007 |
| Power | 7 | SR-008 – SR-014 |
| Thermal | 5 | SR-015 – SR-019 |
| Communications | 5 | SR-020 – SR-024 |
| Science Payload | 6 | SR-025 – SR-030 |
| Reliability | 5 | SR-031 – SR-035 |
| Autonomy | 5 | SR-036 – SR-040 |
| **TOTAL** | **55** | |

---

## 5.0 Requirements Traceability Summary

| System Requirement | Parent Mission Requirement(s) | STM Reference | Subsystem |
|-------------------|-------------------------------|---------------|-----------|
| SR-001 – SR-007 | MR-001, MR-004, MR-005, MR-006 | SO-4.1 | Mobility |
| SR-008 – SR-014 | MR-005, MR-006, MR-007, MR-011 | — | Power |
| SR-015 – SR-019 | MR-008 | — | Thermal |
| SR-020 – SR-024 | MR-003, MR-009, MR-013 | — | Comms |
| SR-025 – SR-030 | MR-002, MR-006 | SG-1, SG-2 | Science Payload |
| SR-031 – SR-035 | MR-011, MR-014 | — | Avionics / System |
| SR-036 – SR-040 | MR-007, MR-014 | SO-4.1 | Autonomy / FSW |

---

*Document end. Requirements baseline frozen at SRR. Changes controlled via NPR 7120.5E Configuration Management process.*
*All requirements exported to LPAS-SYS-RE-01 (requirements_database.csv).*
