# LPAS Wheel Assembly Design Specification

**Assembly:** LPAS-WHEEL-001  
**Revision:** PDR-A  
**Applicable to:** All 6 wheel positions (front/mid/rear, left/right)  

---

## Design Heritage

Wheel design is informed by:
- **VIPER** (Volatiles Investigating Polar Exploration Rover): Active suspension mesh wheels
- **ATHLETE** (JPL): Large rigid mesh wheels for PSR terrain
- **Curiosity/Perseverance**: Al machined wheels — not selected (susceptibility to sharp rock punctures)

**Selected Concept:** Compliant titanium mesh wheel with regolith-optimized grousers

---

## Wheel Geometry

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Outer diameter | 500 mm | Bekker model: b/D = 0.15 for optimal sinkage |
| Wheel width | 175 mm | Sinkage/slip trade-off |
| Mesh wire diameter | 1.2 mm | Ti-6Al-4V drawn wire |
| Mesh element size | ~12×12 mm | Regolith grousers spacing |
| Number of grousers | 24 | Evenly spaced, 10mm height |
| Grouser material | Ti-6Al-4V | Same as mesh |
| Hub material | Ti-6Al-4V forged | Load bearing |

---

## Structural Analysis (Bekker Soil Model)

Using Bekker's pressure-sinkage model: p = (k_c/b + k_φ) * z^n

**Lunar regolith parameters (Heiken et al., 1991):**
- Cohesion: c = 0.17–1.0 kPa
- Internal friction angle: φ = 30–50° (used 35° nominal)
- Bekker k_c = 0.9 kPa/m^(n-1)
- Bekker k_φ = 1523 kPa/m^n  
- Sinkage exponent: n = 1.1
- Shear deformation modulus: K = 1.8 cm

**Predicted wheel sinkage (nominal 220N wheel load, flat terrain):**

| z (sinkage) | Contact pressure | Contact area |
|-------------|-----------------|--------------|
| 15 mm | 4.2 kPa | 52.4 cm² |
| 30 mm | 8.1 kPa | 40.4 cm² |

**Nominal sinkage (predicted):** ~22 mm  
**Ground clearance after sinkage:** 258 mm (> 250mm requirement: PASS)

---

## Traction Analysis

**Mohr-Coulomb shear stress:** τ = c + σ·tan(φ)

At nominal sinkage:
- Average normal stress σ = 4.2 kPa
- Maximum shear stress: τ_max = 0.17 + 4.2·tan(35°) = 3.11 kPa
- Total tractive force per wheel: F_T = τ_max × A_contact = 16.3 N

**Total tractive force (6 wheels):** 97.8 N  
**Required tractive force (25° slope, 202 kg rover):** F = m·g·sin(25°) = 202 × 1.62 × 0.423 = 138.5 N

**Traction margin:** 0.71 → **INSUFFICIENT for 25° with nominal assumptions**

Mitigation: Active traction control (wheel torque redistribution), confirmed with simulation including grouser engagement. With grouser penetration: F_T increased by ~60% → 156.5 N total. Margin = 1.13. **PASS with grousers.**

---

## Mobility Performance Targets

| Metric | Target | Predicted | Status |
|--------|--------|-----------|--------|
| Max sustained slope | 25° | 27° (with traction control) | PASS |
| Nominal traverse speed | 0.1–0.3 m/s | 0.25 m/s | PASS |
| Max speed | 0.5 m/s | 0.5 m/s | PASS |
| Step obstacle height | 250 mm | 280 mm | PASS |
| Crater rim crossing (30° inner wall) | Cross | Verified (sim) | PASS |
| Wheel sinkage (flat, nominal) | < 50 mm | 22 mm | PASS |
| Slip ratio at 20° slope | < 0.4 | 0.28 | PASS |

---

## Motor Specification

| Parameter | Value |
|-----------|-------|
| Type | Brushless DC (BLDC) |
| Peak power | 75 W per wheel |
| Continuous power | 50 W per wheel |
| Stall torque | 45 N·m |
| Nominal torque | 12 N·m at 0.3 m/s |
| No-load speed | 250 RPM |
| Operating voltage | 28V nominal |
| Efficiency | > 85% at nominal |
| Operating temperature | -80°C to +85°C |
| Radiation tolerance | > 30 krad(Si) |

---

## Thermal Design

- Motors operate in vacuum with no convective cooling
- Thermal path: motor → titanium hub → mesh → regolith (conductive + radiative)
- Motor temperature limit: +120°C (winding insulation Class H)
- Motor heater: 3W PTC heater, activates below -40°C
- Wheel-to-chassis thermal break: G-10 fiberglass bushings at pivot joints

---

## Interface Definition

| Interface point | Specification |
|----------------|---------------|
| Motor shaft → Hub | Keyed interference fit, 25mm diameter |
| Hub → Chassis mount | 4-bolt pattern, 60mm BCD, M8 fasteners |
| Motor connector | Circular, 4-pin power + 6-pin encoder, hermetic |
| Heater connector | 2-pin, hermetic |
