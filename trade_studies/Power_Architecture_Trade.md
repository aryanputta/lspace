# LPAS Power Architecture Trade Study
**Document:** LPAS-TRADE-PWR-001 | **Revision:** PDR-A | **Date:** 2026-05-24

---

## 1. Constraint

> **RTG is NOT traded.** Radioisotope thermoelectric generators are excluded from trade space per mission constraint (planetary protection protocol + cost >$100M MMRTG). See MR-008.

---

## 2. Trade Space

| Option | Architecture | Notes |
|--------|-------------|-------|
| **A** | **Solar + LFP battery** | **Selected** |
| B | Solar + NMC Li-ion | Higher energy density, narrower temp range |
| C | Solar + Li-S | Emerging tech, TRL 3 |
| D | Fuel cell (H₂/O₂) | No heritage for lunar surface; cryo storage issues |

---

## 3. Evaluation Criteria

| Criterion | Weight | Rationale |
|-----------|--------|-----------|
| Energy density (Wh/kg) | 20% | 250 kg mass limit |
| PSR survival (>2h blackout) | 25% | Core mission requirement |
| Heritage TRL | 20% | PDR-phase, flight-proven preferred |
| Operating temperature range | 20% | -230°C external, battery must stay >-20°C |
| Cost & complexity | 15% | CLPS cost cap ~$50M |

---

## 4. Scoring Matrix

| Criterion | Weight | A | B | C | D |
|-----------|--------|---|---|---|---|
| Energy density | 20% | 3 | 4 | 5 | 2 |
| PSR survival >2h | 25% | 4 | 3 | 3 | 5 |
| Heritage TRL | 20% | 5 | 5 | 2 | 3 |
| Temperature range | 20% | 4 | 3 | 2 | 4 |
| Cost & complexity | 15% | 5 | 4 | 3 | 2 |
| **Weighted Total** | | **4.10** | **3.70** | **3.00** | **3.30** |

**Selected: Option A — Solar + LFP Battery**

---

## 5. Solar Array Sizing

| Parameter | Value | Source |
|-----------|-------|--------|
| Required average power | 175W traverse, 52W survival | Power Budget |
| Solar cell technology | Triple-junction GaAs | Perseverance / VIPER heritage |
| BOL efficiency | 29.5% | InGaP/GaAs/Ge cell |
| EOL efficiency | 28.1% | 5% degradation after 90 days |
| Solar flux at Moon | 1361 W/m² | ASTM E490 |
| Illumination angle (south pole) | max 2° elevation | LOLA/LROC analysis |
| Cos(angle) factor | 0.035 | sin(2°) — grazing incidence |
| Array area required | 2.0 m² | 175W / (1361×0.281×0.035×0.93) |
| Panel count | 2 deployable panels | 1.0 m² each |
| Array mass | 8.4 kg | 4.2 kg/m² (AFRL standard) |
| Panel structure | CFRP honeycomb substrate | Mass-optimized |

> Note: South pole illumination is always at grazing incidence (max 2° sun elevation). Arrays are tilted 85° from horizontal to maximize flux capture from near-horizon sun.

---

## 6. Battery Sizing

| Parameter | Value | Source |
|-----------|-------|--------|
| Chemistry | LFP (LiFePO₄) | Trade selection |
| Nominal capacity | 150 Wh | Power Budget |
| Usable capacity (80% DOD) | 120 Wh | Battery spec |
| Survival load | 52W | Power Budget (heaters only) |
| Max PSR dwell | 120 Wh / 52W = 2.31 h | Calculation |
| PSR dwell with 20% margin | 1.85 h → **use 1.5h ops** | Mission planning |
| Cell count | 4S4P (14.8V nom) | COTS LFP 18650 |
| Cell energy density | 190 Wh/kg | A123 ANR26650 spec |
| Battery mass | 7.9 kg | |
| Charge rate (C) | 0.5C max | LFP spec |
| Discharge rate (C) | 2C max continuous | LFP spec |
| Min operating temp | -20°C | PTC heater required |
| Survival temp | -40°C | LFP cell spec |

---

## 7. Eclipse Survival Analysis

```
Survival load: 52W = 15W battery heater + 10W OBC + 12W comms (standby) + 15W misc heaters
Available energy: 120 Wh (usable at -20°C)
PSR dwell budget: 120 Wh ÷ 52W = 2.31 h
With 20% margin: 1.85 h (plan to 1.5h with abort trigger at 50% SOC)
```

| Load | Power |
|------|-------|
| Battery PTC heater | 15W |
| Avionics (minimal) | 10W |
| Comms (UHF standby) | 12W |
| Electronics bay heaters | 10W |
| Sensor survival heaters | 5W |
| **Total survival** | **52W** |

---

## 8. MPPT Design

Maximum Power Point Tracking required due to:
- Variable illumination angle (0°–2° sun elevation)
- Temperature-dependent Voc: -0.2%/°C (GaAs cells)
- Bus voltage: 28V regulated (MIL-STD-1553 standard)
- MPPT efficiency: >97%
