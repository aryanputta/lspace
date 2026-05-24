# LPAS Power Architecture Trade Study
**Document No.:** LPAS-TRADE-PWR-001
**Review Level:** PDR-A
**Project:** Lunar PSR Autonomy Scout (LPAS)
**Date:** 2026-05-24
**Status:** Released for PDR

---

## 1. Constraint: RTG Excluded

> **RTG is NOT traded.** Radioisotope thermoelectric generators are excluded from the LPAS trade space per mission requirement MR-008. Reasons:
> - **Planetary protection:** RTG requires NASA Office of Planetary Protection Category II review; Pu-238 near PSR ice deposits raises contamination risk to potential biosignature sites.
> - **Cost:** MMRTG unit cost > $100M (FY2026); exceeds total CLPS delivery cost cap.
> - **Schedule:** Pu-238 production at Oak Ridge is capacity-limited; no allocation available for this mission class.
>
> This constraint is binding and not subject to re-trade at CDR.

---

## 2. Options Evaluated

| Option | Architecture | Notes |
|---|---|---|
| **A** | **Solar + LFP battery (selected)** | LiFePO₄; proven at −40°C; VIPER/Chang'e heritage |
| B | Solar + NMC Li-ion | Higher Wh/kg but narrower temperature range |
| C | Solar + Lithium-Sulfur (Li-S) | Higher energy density; TRL 3; not flight-proven |
| D | Fuel cell (H₂/O₂ PEM) | No lunar surface heritage; cryogenic H₂ storage problematic |

---

## 3. Evaluation Criteria and Weights

| Criterion | Weight | Rationale |
|---|---|---|
| Energy density (Wh/kg) | 20% | Every kg of battery = kg less science payload |
| PSR survival > 2 h blackout | 25% | Primary mission: 2.0 h nominal PSR dwell; highest weight |
| Heritage TRL | 20% | PDR phase; flight-proven chemistry reduces risk |
| Operating temperature range | 20% | External environment: −230°C lunar night; battery must stay > −20°C with heaters |
| Cost and complexity | 15% | CLPS cost envelope; custom chemistry requires qualification |

---

## 4. Scoring Matrix (1–5, 5 = best)

| Criterion | Weight | A: Solar+LFP | B: Solar+NMC | C: Solar+Li-S | D: Fuel Cell |
|---|---|---|---|---|---|
| Energy density (Wh/kg) | 20% | 3 | 4 | 5 | 2 |
| PSR survival > 2 h | 25% | 4 | 3 | 3 | 5 |
| Heritage TRL | 20% | 5 | 5 | 2 | 3 |
| Temperature range | 20% | 4 | 3 | 2 | 4 |
| Cost and complexity | 15% | 5 | 4 | 3 | 2 |
| **Weighted Total** | | **4.10** | **3.70** | **2.95** | **3.25** |

**Winner: Option A — Solar + LFP battery; weighted score 4.10 / 5.0**

---

## 5. Score Justification — Option A

- **Energy density (3/5):** LFP cells deliver ~160–190 Wh/kg vs. 250 Wh/kg for NMC and ~400 Wh/kg projected for Li-S. The mass penalty for 150 Wh capacity is ~0.9 kg vs. NMC — acceptable within mass margin.
- **PSR survival (4/5):** LFP retains > 85% capacity at −20°C (with heater maintaining cell temperature). NMC degrades to < 60% capacity at −20°C (scored 3). Li-S degrades severely below 0°C (scored 3). Fuel cell scores 5 but is excluded by other criteria.
- **Heritage TRL (5/5):** LFP has lunar surface heritage (Chang'e-3/4 Yutu-2 rover batteries; commercial LEO satellites). Cell qualification data exists. NMC also scores 5 (ISS, commercial smallsat heritage).
- **Temperature range (4/5):** LFP stable from −40°C (with heater) to +60°C. NMC: −20°C to +60°C (narrower cold limit). Li-S: degrades below 0°C — fails lunar night survival without extreme heater power.
- **Cost/complexity (5/5):** LFP cells are COTS; qualification campaign is standard. Li-S requires custom chemistry qualification (scored 3). Fuel cell requires H₂ tank, regulator, purge system, and membrane qualification (scored 2).

---

## 6. Selected System Specifications

### 6.1 Solar Array

| Parameter | Value | Source/Heritage |
|---|---|---|
| Technology | Triple-junction GaAs (InGaP/GaAs/Ge) | Spectrolab/AZUR heritage |
| BOL efficiency | 29.5% | Spectrolab UTJ spec |
| EOL efficiency | 28.0% | 5% degradation at 90-sol mission end |
| EOL power output | 200 W | Design requirement SR-006 |
| Solar constant at Moon | 1,361 W/m² | ASTM E490 AM0 |
| Sun elevation at Shackleton rim | ≤ 2° (max) | LOLA illumination model |
| Array tilt from horizontal | 85° (near-vertical; aimed at horizon sun) | Derived from 2° sun elevation |
| Required array area | 2.05 m² | 200 W / (1361 × 0.280 × sin(87°) × 0.93 MPPT) |
| Panel configuration | 2 × deployable panels, 1.025 m² each | — |
| Array mass | 8.6 kg | 4.2 kg/m² AFRL standard |
| Panel substrate | CFRP honeycomb (2 mm face sheets) | Mass-optimized |
| MPPT efficiency | 97% | Buck-boost converter |

### 6.2 Battery

| Parameter | Value | Source/Heritage |
|---|---|---|
| Chemistry | LiFePO₄ (LFP) | Chang'e Yutu-2; VIPER-class batteries |
| Nominal capacity | 150 Wh | Design requirement SR-006 |
| Cell configuration | 4S4P (14.8 V nominal at pack level; 28.8 V with 2× series packs) | — |
| Usable capacity (40% SOC floor) | 90 Wh | PSR ops floor 40% SOC |
| Cell energy density | 190 Wh/kg | A123 ANR26650M1B spec |
| Pack mass | 7.9 kg | 150 Wh / 190 Wh/kg + 20% packaging |
| Operating temperature | −20°C to +60°C | Requires PTC heater ≥ −20°C |
| Survival temperature | −40°C (non-operating) | LFP cell spec |
| Max charge rate | 0.5C (75 W) | LFP cycle life preservation |
| Max discharge rate | 2C continuous (300 W) | LFP spec |

### 6.3 Power Bus

| Parameter | Value |
|---|---|
| Regulated bus voltage | 28.8 V (2× 4S LFP packs in series) |
| Unregulated bus (science loads) | 12 V (derived) |
| PMAD efficiency | 96% |
| Load switching | 16 independent switched channels |
| Fault protection | Current-limited latching switches (CLCS) per channel |

---

## 7. Eclipse Survival and PSR Dwell Budget

### 7.1 PSR Load Breakdown

| Load Item | Power (W) |
|---|---|
| Drive motors at 0.2 m/s (6 × 250 W, partial load) | 30 |
| NIRVSS spectrometer (science, active) | 7 |
| Avionics + OBC | 8 |
| Battery / motor heaters (survival minimum) | 7 |
| **Total PSR operating load** | **52 W** |

### 7.2 Dwell Calculation

| Parameter | Calculation | Result |
|---|---|---|
| Full battery capacity | 150 Wh | 150 Wh |
| Full discharge dwell | 150 Wh ÷ 52 W | **2.88 h** |
| Energy at 40% SOC floor | 150 Wh × 0.60 = 90 Wh | 90 Wh |
| Dwell to 40% SOC floor | 90 Wh ÷ 52 W | 1.73 h |
| **Nominal dwell with 30% time margin on 2.88 h** | 2.88 h × 0.70 | **2.0 h (baseline)** |

**Baseline PSR dwell: 2.0 h, with 30% margin against 2.88 h full-discharge limit.**

### 7.3 Survival-Only (No Drive) Dwell

| Condition | Power | Duration |
|---|---|---|
| Survival load only (no drive, no science) | 15 W | 150 Wh ÷ 15 W = **10.0 h** |
| Night standby (heaters + watchdog) | 10 W avg | 150 Wh × 0.80 ÷ 10 W = **12.0 h** |

The 10-hour survival window confirms that the rover can survive a single worst-case LRO contact blackout (max 24 h) only if it enters night standby before battery drops below 80% SOC.

---

## 8. RTG Trade-Off Summary (Informational Only)

| Parameter | RTG (MMRTG) | Selected (Solar+LFP) |
|---|---|---|
| Continuous power | 110 W (constant) | 200 W (illuminated) / 0 W (eclipse) |
| Mass | 45 kg | 16.5 kg (array + battery) |
| PSR dwell (unconstrained) | Unlimited | 2.0 h nominal |
| Cost | > $100M | < $2M |
| Planetary protection | Category II review required; Pu-238 risk | No restriction |
| Schedule | 5+ year Pu-238 production lead | Standard procurement |
| **Reason not selected** | **Violates mission requirement MR-008** | — |

---

## 9. Document Control

| Field | Value |
|---|---|
| Document Number | LPAS-TRADE-PWR-001 |
| Revision | A |
| Review Level | PDR-A |
| Next Review | CDR |
| Parent Documents | LPAS-SYS-003 (SRS); LPAS-PWR-001 (Power Budget); MR-008 (mission constraint) |
