# LPAS Mobility Architecture Trade Study
**Document:** LPAS-TRADE-MOB-001 | **Revision:** PDR-A | **Date:** 2026-05-24

---

## 1. Trade Space Definition

Four mobility architectures were evaluated for LPAS south pole traverse requirements: 25° slope capability, 2+ hour PSR dwell, rocky terrain up to 0.3m obstacle height.

| Option | Architecture | Heritage |
|--------|-------------|---------|
| A | 4-wheel skid-steer | Small planetary rovers |
| **B** | **6-wheel rocker-bogie** | **Curiosity, VIPER, Perseverance** |
| C | 8-wheel rocker-bogie | Proposed only |
| D | Tracked crawler | Terrestrial vehicles |

---

## 2. Evaluation Criteria

| Criterion | Weight | Rationale |
|-----------|--------|-----------|
| Slope capability (≥25°) | 25% | PSR crater walls can reach 35° |
| System mass (kg) | 20% | 250 kg total mass limit |
| Power consumption | 20% | 175W average budget |
| PSR navigation reliability | 15% | No recourse in PSR; fault = mission loss |
| Heritage TRL | 10% | PDR-phase; proven flight designs preferred |
| Reliability / MTBF | 10% | 90-day primary mission |

---

## 3. Scoring Matrix (1–5, 5 = best)

| Criterion | Weight | A | B | C | D |
|-----------|--------|---|---|---|---|
| Slope capability | 25% | 2 | 4 | 5 | 3 |
| System mass | 20% | 5 | 4 | 3 | 2 |
| Power consumption | 20% | 4 | 4 | 3 | 2 |
| PSR nav reliability | 15% | 2 | 5 | 5 | 3 |
| Heritage TRL | 10% | 3 | 5 | 3 | 2 |
| Reliability / MTBF | 10% | 3 | 5 | 4 | 3 |
| **Weighted Total** | | **3.15** | **4.35** | **3.75** | **2.50** |

**Selected: Option B — 6-wheel rocker-bogie**

---

## 4. Heritage Comparison

| Parameter | Curiosity | VIPER | Perseverance | **LPAS** |
|-----------|-----------|-------|-------------|---------|
| Wheel diameter | 500 mm | 280 mm | 526 mm | **500 mm** |
| Wheel width | 160 mm | 110 mm | 180 mm | **175 mm** |
| Wheelbase | 2.77 m | 1.5 m | 2.89 m | **0.95 m** |
| Track width | 2.30 m | 1.5 m | 2.26 m | **1.75 m** |
| Max slope (tested) | 30° | 25° | 30° | **25° (req)** |
| Rover mass | 900 kg | 430 kg | 1025 kg | **132 kg CBE** |
| Wheel material | Al machined | Al machined | Al machined | **Ti-6Al-4V mesh** |
| Motor per wheel | 2 (drive+steer) | 1 | 2 | **1 (drive only)** |

LPAS uses VIPER-heritage wheel sizing (scaled to 500mm for performance margin) with Ti mesh wheels for mass reduction. Rocker geometry from Curiosity (scaled for 132 kg rover mass).

---

## 5. Selected Design Parameters

| Parameter | Value | Heritage Source |
|-----------|-------|----------------|
| Wheel radius | 0.25 m | Curiosity/VIPER heritage |
| Wheel width | 0.175 m | VIPER heritage |
| Wheelbase | 0.95 m | Mass-scaled from Curiosity |
| Track width | 1.75 m | Mass-scaled from Curiosity |
| Rocker arm length | 0.95 m | Sized for 25° slope |
| Bogie arm length | 0.50 m | Two-wheel bogie |
| Max traverse speed | 0.5 m/s | Nav2 / power constraint |
| Min turn radius | 2.3 m | Kinematic model |
| Motor power | 250W × 6 | Slope + slip margin |
| Max slope | 25° | Requirement SR-005 |
| Max obstacle | 0.30 m | ≥0.6× wheel radius |

---

## 6. Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Wheel motor failure (1 of 6) | Medium | Rover continues on 5 wheels; reduced speed |
| Rocker arm binding | High | Ti-6Al-4V hard anodized; dust seal |
| Excessive slip in PSR regolith | Medium | Bekker soil model; slip prediction AI |
| Bogie arm crack (cold) | High | -196°C cryogenic test; FEA analysis at -230°C |
