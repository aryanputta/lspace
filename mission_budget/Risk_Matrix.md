# LPAS Risk Matrix
**Document:** LPAS-RISK-001 | **Revision:** PDR-A | **Date:** 2026-05-24

Risk scoring: **Likelihood** (1=Rare → 5=Almost Certain) × **Consequence** (1=Negligible → 5=Mission Loss)

| Risk Score | Level | Color |
|-----------|-------|-------|
| ≤ 4 | Low | 🟢 |
| 5–9 | Medium | 🟡 |
| 10–15 | High | 🟠 |
| ≥ 16 | Critical | 🔴 |

---

## Risk Register

| ID | Category | Description | L | C | Score | Mitigation | Residual |
|----|----------|-------------|---|---|-------|------------|---------|
| R-01 | Technical | **Wheel mesh failure** — Ti mesh puncture by sharp regolith fragment; loss of mobility | 2 | 4 | 🟡 8 | Compliant mesh design; 20% traction margin; 3-wheel degraded mode | 🟢 4 |
| R-02 | Technical | **Power shortfall in PSR** — grazing solar angle lower than expected; battery depleted before recharging | 3 | 4 | 🟠 12 | Planned hibernation; energy-aware path planning; conservative traverse budget | 🟡 6 |
| R-03 | Technical | **Thermal exceedance (cold)** — longer-than-planned PSR traverse; battery below -20°C | 3 | 3 | 🟡 9 | Survival heaters (45W); thermal limit on PSR dwell time; temperature watchdog | 🟢 4 |
| R-04 | Technical | **Navigation localization loss** — SLAM divergence in featureless PSR crater floor | 3 | 3 | 🟡 9 | IMU dead-reckoning backup; star tracker; visual odometry; manual intervention | 🟡 6 |
| R-05 | Technical | **AI model false negative** — hazard detector misses boulder in low light; collision | 2 | 4 | 🟡 8 | LIDAR fusion (independent of lighting); conservative speed in low light; redundant HazCam | 🟢 4 |
| R-06 | Technical | **Communications blackout > 6h** — deeper PSR than mapped; relay LOS blocked | 3 | 3 | 🟡 9 | 8h autonomous operation capability; store-and-forward; UHF + HGA redundancy | 🟡 6 |
| R-07 | Technical | **Drill mechanism jam** — hard rock layer at shallow depth; drill stuck | 3 | 2 | 🟡 6 | Torque/force limits; auto-retract on overload; multiple site attempts | 🟢 4 |
| R-08 | Technical | **Flight computer single-event upset** — cosmic ray bit flip; software fault | 3 | 3 | 🟡 9 | Redundant computers; TMR logic for critical registers; watchdog reboot | 🟡 6 |
| R-09 | Technical | **Dust contamination** — electrostatic dust adhesion to solar arrays; power reduction | 4 | 2 | 🟡 8 | Sloped array orientation; dust-mitigating coating; operational power margins | 🟡 6 |
| R-10 | Mission | **Lander deployment failure** — rover egress ramp malfunction; rover stranded on lander | 2 | 5 | 🟠 10 | Heritage egress mechanism; deployment test; backup release actuator | 🟡 6 |
| R-11 | Mission | **Science site inaccessibility** — target PSR slopes too steep for rover entry | 2 | 3 | 🟡 6 | Multiple target sites (3 PSRs); slope analysis pre-mission with LOLA | 🟢 4 |
| R-12 | Mission | **Reduced mission data return** — limited contact windows, downlink congestion | 3 | 2 | 🟡 6 | Data compression; priority science data first; 3× downlink margin | 🟢 4 |
| R-13 | Schedule | **AI model accuracy insufficient for flight** — testing reveals mIoU < 0.80 threshold | 2 | 3 | 🟡 6 | Traditional path planning fallback; conservative AI threshold; additional training data | 🟢 4 |
| R-14 | Schedule | **Integration & test schedule slip** — hardware delivery delays push TRR past CDR+12mo | 3 | 3 | 🟡 9 | Parallel software/hardware development; simulation-based early testing; schedule reserves | 🟡 6 |
| R-15 | Cost | **Mass budget overrun** — subsystem CBE growth exceeds 15% MGA | 2 | 3 | 🟡 6 | Monthly mass tracking; 60kg margin to 250kg cap; design-to-mass culture | 🟢 4 |

---

## Top Risks for PDR Action

1. **R-02 Power Shortfall (🟠 12)** — Derive energy-aware traverse planning requirement. Validate solar angle model with LOLA terrain illumination data.
2. **R-08 SEU / Flight Computer (🟡 9)** — Select radiation-hardened processor by CDR. Define FDIR response for memory errors.
3. **R-06 Extended Blackout (🟡 9)** — Implement and test 8-hour autonomous mission execution in simulation before CDR.
4. **R-14 Schedule (🟡 9)** — Review delivery schedule for drill mechanism and spectrometer at PDR+3mo checkpoint.

---

## Risk Burn-Down Plan

| Phase | Target Risk Count | High+ |
|-------|------------------|-------|
| PDR | 15 total | 1 🔴, 4 🟠 |
| CDR | 12 total | 0 🔴, 2 🟠 |
| TRR | 8 total | 0 🔴, 1 🟠 |
| Launch | 5 total | 0 🔴, 0 🟠 |
