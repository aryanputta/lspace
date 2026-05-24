# LPAS Mobility Architecture Trade Study
**Document No.:** LPAS-TRADE-MOB-001
**Review Level:** PDR-A
**Project:** Lunar PSR Autonomy Scout (LPAS)
**Date:** 2026-05-24
**Status:** Released for PDR

---

## 1. Trade Objective

Select the mobility architecture for LPAS that satisfies: 25° slope capability on Shackleton rim, > 2 h PSR dwell with full traverse, rocky terrain with obstacles up to 0.30 m, and total rover mass < 150 kg CBE (15% margin target).

---

## 2. Options Evaluated

| Option | Architecture | Heritage |
|---|---|---|
| A | 4-wheel skid-steer | Small planetary rovers, MER-class precursors |
| **B** | **6-wheel rocker-bogie (selected)** | **Curiosity, Perseverance, VIPER, MER Spirit/Opportunity** |
| C | 8-wheel rocker-bogie | Proposed only; no flight heritage |
| D | Tracked crawler | Terrestrial mining/military; no lunar flight heritage |

---

## 3. Evaluation Criteria and Weights

| Criterion | Weight | Rationale |
|---|---|---|
| Slope capability (max sustained) | 25% | PSR crater walls reach 35°; requirement: 25° sustained |
| System mass | 20% | Total rover mass budget 150 kg CBE; every kg matters |
| Electrical power (drive load) | 20% | 200 W solar; drive must not exceed 120 W avg traverse |
| PSR navigation reliability | 15% | Failure inside PSR = mission loss; no rescue |
| Heritage TRL | 10% | PDR phase: flight-proven designs reduce schedule risk |
| Reliability / MTBF | 10% | 90-sol primary mission; no in-situ repair |

---

## 4. Scoring Matrix (1–5, 5 = best)

| Criterion | Weight | A: 4-wheel skid | B: 6-wheel RB | C: 8-wheel RB | D: Tracked |
|---|---|---|---|---|---|
| Slope capability | 25% | 2 | 4 | 5 | 3 |
| System mass | 20% | 5 | 4 | 3 | 2 |
| Electrical power | 20% | 4 | 4 | 3 | 2 |
| PSR nav reliability | 15% | 2 | 5 | 5 | 3 |
| Heritage TRL | 10% | 3 | 5 | 3 | 2 |
| Reliability / MTBF | 10% | 3 | 5 | 4 | 3 |
| **Weighted Total** | | **3.15** | **4.35** | **3.75** | **2.50** |

**Winner: Option B — 6-wheel rocker-bogie; weighted score 4.35 / 5.0**

---

## 5. Score Justification — Option B

- **Slope (4/5):** Rocker-bogie geometry passively accommodates 30°+ slopes (Curiosity demonstrated 32° in Gale Crater). Scored 4 rather than 5 because pure passive suspension is less predictive than active systems on novel terrain.
- **Mass (4/5):** Six wheels and rocker-bogie hardware add ~8 kg over a 4-wheel skid steer, but eliminate the steering actuator mass and reduce power electronics (no differential steering). Net mass penalty vs. Option A is < 5 kg at rover scale.
- **Power (4/5):** All 6 motors driven at partial load (20–50 W each, 120–300 W peak) at 0.3 m/s. Same score as Option A because drive power is dominated by motor count, not steering architecture.
- **PSR reliability (5/5):** Rocker-bogie provides ground clearance and wheel independence: any single wheel can be lifted 0.30 m without the chassis tilting > 15°. In PSR darkness where terrain cannot be fully pre-mapped, passive adaptation is critical.
- **Heritage (5/5):** Rocker-bogie is the highest-heritage lunar/Mars rover mobility system. VIPER used this architecture for similar polar operations; Curiosity and Perseverance validated the design at mass scales from 175 kg to 1,025 kg.
- **Reliability (5/5):** No single-point failures in passive rocker-bogie: any 5-of-6 motors operational allows mission completion at reduced speed. No steering motors eliminates a failure mode present in Options A and C.

---

## 6. Heritage Comparison Table

| Parameter | Curiosity (MSL) | Perseverance (M2020) | VIPER (lunar) | **LPAS (this work)** |
|---|---|---|---|---|
| Wheel diameter (mm) | 500 | 526 | 280 | **500** |
| Wheel width (mm) | 160 | 180 | 110 | **175** |
| Wheel material | Al 7050 machined | Al 7050 machined | Al machined | **Ti-6Al-4V mesh** |
| Wheelbase (m) | 2.77 | 2.89 | 1.50 | **0.95** |
| Track width (m) | 2.30 | 2.26 | 1.50 | **1.75** |
| Max slope tested (deg) | 30 | 30 | 25 | **25 (requirement)** |
| Rover mass (kg) | 900 | 1,025 | 430 | **132 CBE** |
| Motors per wheel | 2 (drive + steer) | 2 (drive + steer) | 1 | **1 (drive only)** |
| Motor power (W) | 250 | 250 | 100 | **250** |
| Speed nominal (m/s) | 0.04 | 0.04 | 0.30 | **0.30** |

*LPAS uses VIPER speed class with Curiosity/Perseverance motor power and wheel diameter. Ti-6Al-4V mesh wheels reduce wheel mass by ~40% vs. machined Al at equivalent stiffness.*

---

## 7. Selected Design Parameters

| Parameter | Value | Heritage/Rationale |
|---|---|---|
| Wheel radius | 0.25 m | Curiosity/Perseverance heritage; ≥ 0.60× max obstacle |
| Wheel width | 0.175 m | VIPER heritage; optimized for loose regolith |
| Wheelbase | 0.95 m | Mass-scaled from Curiosity for 132 kg rover |
| Track width | 1.75 m | Stability at 25° slope; tip-over margin > 2× |
| Rocker arm length | 0.95 m | Sized by 25° slope + 0.30 m obstacle clearance |
| Bogie arm length | 0.50 m | Two-wheel bogie (front + mid per side) |
| Max traverse speed | 0.50 m/s | Nav2 hard limit; power constraint |
| PSR traverse speed | 0.20 m/s | Hazard detection reaction margin |
| Min turn radius | 2.3 m | Kinematic model (no in-situ steering) |
| Drive motor (× 6) | 250 W brushless DC (maxon EC-i class) | Curiosity/Perseverance heritage |
| Max slope (sustained) | 25° | Requirement SR-005 |
| Max obstacle height | 0.30 m (0.60× wheel radius) | Standard rocker-bogie design rule |

---

## 8. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Single wheel motor failure | Low | Low | 5-of-6 wheel mode; reduced speed; mission continues |
| Rocker joint binding (cold) | Low | High | Ti-6Al-4V hard-anodized joints; −196°C tested; dust seal |
| Excessive regolith slip (PSR) | Medium | Medium | Bekker-Wong soil model in Nav2; slip prediction AI abort trigger |
| Bogie fracture (−230°C thermal cycling) | Very Low | High | FEA at −230°C; cryogenic coupon test at CDR |
| Wheel mesh clogging (regolith ingress) | Low | Low | Open-cell mesh tolerates fill; no bearing-contact risk |

---

## 9. Document Control

| Field | Value |
|---|---|
| Document Number | LPAS-TRADE-MOB-001 |
| Revision | A |
| Review Level | PDR-A |
| Next Review | CDR |
| Parent Documents | LPAS-SYS-003 (SRS), LPAS-PWR-001 (Power Budget) |
