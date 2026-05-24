# Thermal Budget — LPAS-THERM-001 | PDR-A

**Document Number:** LPAS-THERM-001
**Revision:** A
**Review Level:** PDR
**Date:** 2026-05-24
**Author:** Thermal Systems Team
**Status:** Released

---

## 1. Scope

This document establishes the thermal budget for the Lunar PSR Autonomy Scout (LPAS) rover. It covers the 16-zone lumped-parameter thermal model, heat dissipation accounting, survival heater sizing for eclipse/PSR dwell, radiator and MLI specifications, battery thermal control, and heat pipe routing architecture. All values are Current Best Estimates (CBE) with 20% margin applied at subsystem level.

---

## 2. Mission Thermal Environment

| Parameter | Value | Notes |
|---|---|---|
| Lunar south pole solar flux | 1361 × sin(2°) = 47.5 W/m² | Max solar elevation 2° |
| PSR floor temperature (external) | −230 °C (43 K) | Shackleton crater interior |
| Illuminated regolith temperature | +120 °C (393 K) | Solar noon surface, avoided |
| Deep space sink | −270 °C (3 K) | Zenith view |
| Lunar IR surface emission | 5.67×10⁻⁸ × 0.95 × 43⁴ ≈ 0.02 W/m² | Inside PSR |
| Maximum PSR dwell duration | 2.88 h | Per eclipse traverse segment |
| Eclipse survival heater budget | 52 W | Battery-constrained, heaters only |

---

## 3. 16-Zone Lumped Parameter Thermal Model

Each zone represents a thermally distinct node in the LPAS lumped-capacitance network. Conductance links (W/K) and radiative couplings (m²) are defined in the NX Thermal model `thermal_analysis/nx_thermal/lpas_16node.sim`.

| Zone # | Zone Name | Primary Material | Node Mass (kg) | Operating Range (°C) | Survival Range (°C) |
|---|---|---|---|---|---|
| Z01 | Electronics Bay (primary) | Al 6061-T6 enclosure | 4.2 | −20 to +60 | −40 to +70 |
| Z02 | Compute Board (Jetson AGX Orin) | PCB + copper spreader | 0.6 | 0 to +55 | −20 to +65 |
| Z03 | Battery Pack | Li-ion NMC cells, Al housing | 2.1 | −20 to +45 | −30 to +60 |
| Z04 | Power Distribution Unit (PDU) | Al chassis, copper busbars | 0.8 | −30 to +70 | −40 to +80 |
| Z05 | Solar Array Panel (port) | CFRP substrate, coverglass | 1.1 | −150 to +80 | −170 to +100 |
| Z06 | Solar Array Panel (starboard) | CFRP substrate, coverglass | 1.1 | −150 to +80 | −170 to +100 |
| Z07 | Mobility Chassis (front) | Al 7075-T73 weldment | 3.8 | −80 to +80 | −100 to +100 |
| Z08 | Mobility Chassis (rear) | Al 7075-T73 weldment | 3.2 | −80 to +80 | −100 to +100 |
| Z09 | Wheel Assembly FL | Ti-6Al-4V spokes, Al rim | 0.4 | −120 to +90 | −150 to +110 |
| Z10 | Wheel Assembly FR | Ti-6Al-4V spokes, Al rim | 0.4 | −120 to +90 | −150 to +110 |
| Z11 | Wheel Assembly RL | Ti-6Al-4V spokes, Al rim | 0.4 | −120 to +90 | −150 to +110 |
| Z12 | Wheel Assembly RR | Ti-6Al-4V spokes, Al rim | 0.4 | −120 to +90 | −150 to +110 |
| Z13 | Science Payload Bay | Al 6061-T6, kapton-lined | 1.9 | −40 to +50 | −55 to +65 |
| Z14 | Comms Antenna Assembly | Al + Invar mount | 0.7 | −80 to +80 | −100 to +100 |
| Z15 | Radiator Panel | Al 6061-T6, Ag-Teflon OSR | 0.9 | −30 to +65 | −50 to +80 |
| Z16 | Regolith Contact Feet | Ti-6Al-4V, Aerogel isolator | 0.3 | −150 to +80 | −200 to +100 |

**Total modeled mass:** 22.3 kg (thermal zones only; excludes structural closeout)

---

## 4. Heat Dissipation Budget

All values in watts. CBE = measured/predicted from component datasheets and analysis. Margin = 20% applied to CBE. Total = CBE + Margin.

| Subsystem | Component | Operating Mode | CBE (W) | Margin (W) | Total with Margin (W) |
|---|---|---|---|---|---|
| Compute | Jetson AGX Orin (AI inference) | Science mode | 25.0 | 5.0 | 30.0 |
| Compute | Jetson AGX Orin (standby) | Traverse mode | 10.0 | 2.0 | 12.0 |
| Compute | Flight computer (OBC) | All modes | 4.0 | 0.8 | 4.8 |
| Compute | FPGA (wheel/sensor I/O) | All modes | 3.5 | 0.7 | 4.2 |
| Power | Battery charging electronics | Charge mode | 8.0 | 1.6 | 9.6 |
| Power | PDU switching losses | All modes | 2.5 | 0.5 | 3.0 |
| Power | Solar array regulator | Illuminated | 3.0 | 0.6 | 3.6 |
| Mobility | 4× wheel motor drivers (per wheel 3W) | Traverse | 12.0 | 2.4 | 14.4 |
| Mobility | Steering actuators (2× active) | Turning | 4.0 | 0.8 | 4.8 |
| Science | Drill motor assembly | Drilling | 18.0 | 3.6 | 21.6 |
| Science | Mass spectrometer ion pump | Science mode | 6.0 | 1.2 | 7.2 |
| Science | Camera illumination LEDs | Imaging | 3.0 | 0.6 | 3.6 |
| Comms | UHF transceiver (TX) | Uplink/downlink | 8.0 | 1.6 | 9.6 |
| Comms | UHF transceiver (RX idle) | Standby | 1.5 | 0.3 | 1.8 |
| Comms | LGA antenna LNA | Receive only | 0.5 | 0.1 | 0.6 |
| Thermal | Survival heater bank A | Eclipse/PSR | 26.0 | — | 26.0 |
| Thermal | Survival heater bank B | Eclipse/PSR | 26.0 | — | 26.0 |

### 4.1 Mode Power Summary

| Operational Mode | Total Dissipation CBE (W) | Total with Margin (W) |
|---|---|---|
| Traverse (nominal) | 36.5 | 43.8 |
| Science (drilling + AI) | 67.5 | 81.0 |
| Eclipse survival (heaters only) | 52.0 | 52.0 |
| Charge + standby | 29.5 | 35.4 |
| Peak instantaneous | 72.0 | 86.4 |

---

## 5. Survival Power: Eclipse / PSR Thermal Analysis

### 5.1 Heater Budget

During eclipse and PSR cold-soak traverses, solar input drops to near zero. The entire 52 W heater budget is dedicated to maintaining electronics bay and battery above survival limits.

| Heater | Zone Protected | Power (W) | Setpoint (°C) | Thermostat Type |
|---|---|---|---|---|
| H-01 Electronics Bay primary | Z01 | 15.0 | −15 °C on / −5 °C off | Mechanical bimetallic |
| H-02 Electronics Bay backup | Z01 | 10.0 | −20 °C on / −10 °C off | PTC thermistor-switched |
| H-03 Battery PTC heater | Z03 | 15.0 | −18 °C on / −8 °C off | PTC self-regulating |
| H-04 PDU keep-alive | Z04 | 5.0 | −25 °C on / −15 °C off | Mechanical bimetallic |
| H-05 Science bay survival | Z13 | 7.0 | −50 °C on / −40 °C off | Mechanical bimetallic |
| **Total** | | **52.0 W** | | |

### 5.2 PSR Cold Soak Analysis

**Governing equation:** Q_heater = Q_loss_conducted + Q_loss_radiated

Assumptions:
- External boundary: 43 K (−230 °C) PSR floor, ε_regolith = 0.95
- Electronics bay internal wall: T_wall = T_set − 5 °C buffer
- Conduction to chassis: k_Al = 167 W/(m·K), path length 0.3 m, area 0.004 m²
- Radiation from electronics bay to chassis interior: ε_eff = 0.03 (MLI), A_rad = 0.12 m²
- Chassis to regolith conduction through Aerogel feet: k_aero = 0.015 W/(m·K), area 0.008 m², path 0.02 m

| Loss Path | Conductance (W/K) | ΔT at PSR (K) | Heat Loss (W) |
|---|---|---|---|
| Al chassis to regolith feet | 0.006 | 243 | 1.46 |
| Radiator panel to PSR sky | 0.68 (εσA/T³) | variable | 3.2 |
| Electronics bay MLI to chassis | 0.05 | 30 | 1.5 |
| Wiring harness conduction | 0.03 | 50 | 1.5 |
| **Total estimated loss** | | | **~7.7 W** |

**Available heater margin at 52 W:** 52 − 7.7 = **44.3 W** (positive — survival confirmed)

**Maximum dwell time at 52 W budget before battery depletion:**
- Battery capacity: 540 Wh (usable 80% = 432 Wh)
- At 52 W heater load + 12 W compute standby = 64 W total eclipse draw
- Max eclipse duration: 432 / 64 = **6.75 h** battery limited
- Mission constraint: 2.88 h max PSR dwell — **margin = 4.0× (thermal OK)**

---

## 6. Radiator Sizing

### 6.1 Design Parameters

| Parameter | Value |
|---|---|
| Radiator area | 0.12 m² |
| Surface coating | Ag-Teflon OSR (Optical Solar Reflector) |
| Coating absorptivity (α) | 0.08 |
| Coating emissivity (ε) | 0.88 |
| Max electronics temperature | +65 °C (338 K) |
| Radiator mounting | Port side panel, nadir-facing (away from regolith) |
| View factor to deep space | 0.72 |
| View factor to lunar surface | 0.18 |
| View factor to solar panels | 0.10 |

### 6.2 Rejection Capacity

Maximum heat rejection at T_electronics = 65 °C:

Q_reject = ε × σ × A × F_space × (T_elec⁴ − T_space⁴)
         = 0.88 × 5.67×10⁻⁸ × 0.12 × 0.72 × (338⁴ − 3⁴)
         = **63.1 W**

Solar input absorbed by radiator (worst case, low-angle illumination):
Q_solar_in = α × G_solar_pole × A_proj = 0.08 × 47.5 × 0.012 = **0.046 W** (negligible)

Net rejection at peak science mode (81 W total dissipation, routing 60 W to radiator via heat pipes):
Q_net = 63.1 − 0.046 = **63.1 W available** vs. 60 W required → **margin: 5.2%**

Action: radiator area is minimum compliant. Increase to 0.14 m² at CDR if science mode power grows.

---

## 7. MLI Blanket Specifications

| Parameter | Specification |
|---|---|
| Number of layers | 20 |
| Layer material | Double-aluminized Mylar (DAM), 6 µm |
| Spacer material | Dacron net, 0.127 mm |
| Effective emissivity (ε_eff) | 0.03 |
| Coverage zones | Electronics bay (Z01), battery (Z03), science bay (Z13) |
| Blanket total area | 1.8 m² |
| Seam overlap | 25 mm minimum, crinkle-fold at penetrations |
| Penetrations | Sealed with Beta cloth tape, ε ≈ 0.84 at penetration rings |
| Installation standard | GSFC-STD-7000B Section 5 |

**MLI thermal conductance across 20-layer stack:**
k_eff = ε_eff × σ × (T_hot² + T_cold²) × (T_hot + T_cold) × A
At T_hot = 20 °C, T_cold = −40 °C: Q_MLI = 0.03 × 5.67×10⁻⁸ × (293² + 233²)(293 + 233) × 1.8 = **0.91 W**

---

## 8. Battery Thermal Control

| Parameter | Value |
|---|---|
| Battery chemistry | Li-ion NMC (LG MJ1 cells, 18650 format) |
| Cell count | 7S12P (84 cells total) |
| Total capacity | 540 Wh |
| Minimum operating temperature | −20 °C (charging); −30 °C (discharge only) |
| Maximum operating temperature | +45 °C |
| Heater type | PTC (positive temperature coefficient) self-regulating |
| PTC heater nominal power | 15 W at −20 °C |
| PTC saturation power | 3 W at +25 °C (self-limits) |
| Thermostat setpoint (ON) | −18 °C |
| Thermostat setpoint (OFF) | −8 °C |
| Insulation | 20-layer MLI + 10 mm Aerogel panel on regolith-facing face |
| Temperature sensors | 4× PT100 RTD, 2× redundant per cell group |
| Over-temperature protection | Hardware cutoff at +50 °C via BMS relay |

**Battery thermal time constant** (cooling in PSR):
τ = m × Cp / (UA) = 2.1 × 1005 / (0.05 + 0.02) = **30,150 s = 8.4 h**

At 43 K boundary, time to reach −20 °C from +20 °C = τ × ln((293 − 43)/(253 − 43)) = 30150 × ln(1.19) = **5,270 s = 1.46 h** without heater. PTC heater maintains temperature well within the 2.88 h dwell constraint.

---

## 9. Heat Pipe Routing

### 9.1 Architecture

Ammonia heat pipes transport waste heat from the electronics bay (Z01, Z02) to the radiator panel (Z15). Two parallel pipes provide single-fault tolerance.

| Pipe ID | Route | Length (m) | Pipe OD (mm) | Working Fluid | Max Q (W) | Operating Temp Range (°C) |
|---|---|---|---|---|---|---|
| HP-01 | Z01 (OBC evap) → Z15 (radiator cond) | 0.45 | 9.5 | Ammonia | 40 | −40 to +80 |
| HP-02 | Z02 (Jetson evap) → Z15 (radiator cond) | 0.38 | 9.5 | Ammonia | 50 | −40 to +80 |
| HP-03 | Z03 (battery, bypass/warm) → Z01 | 0.22 | 6.4 | Ammonia | 20 | −30 to +55 |

### 9.2 Installation Notes

- HP-01 and HP-02 are sintered copper wick, 200 mesh
- All pipes mounted with low-conductance standoffs (PEEK bushings) to chassis
- Evaporator saddles bonded to PCB cold plates with Bergquist GP3000 thermal interface material (TIM), k = 3.0 W/(m·K), bond thickness 0.25 mm
- Condenser section brazed directly to radiator panel face sheet
- HP-03 reversible: during charging in illumination, pipes heat from electronics to battery; during eclipse, bidirectional flow arrested by gravity assist angle (pipes tilted 2° toward evaporator)
- Leak test per ASTM E493 at 1.5× MAWP

### 9.3 Heat Pipe Thermal Resistance Budget

| Segment | Resistance (K/W) |
|---|---|
| Evaporator wall to wick | 0.04 |
| Wick to vapor | 0.02 |
| Vapor transport (adiabatic) | 0.01 |
| Condenser vapor to wick | 0.02 |
| Condenser wick to wall | 0.03 |
| TIM (evaporator saddle) | 0.05 |
| TIM (condenser to radiator) | 0.04 |
| **Total HP-02 (worst case)** | **0.21 K/W** |

At 30 W Jetson dissipation: ΔT = 0.21 × 30 = **6.3 °C** — well within budget.

---

## 10. Thermal Budget Summary

| Budget Item | Requirement | CBE | Margin |
|---|---|---|---|
| Radiator area | ≥ 0.10 m² | 0.12 m² | +20% |
| Heater power (eclipse) | ≤ 52 W | 52.0 W | 0% — constrained |
| MLI effective emissivity | ≤ 0.05 | 0.03 | +40% |
| Battery min temperature | > −20 °C (op) | −15 °C (analysis) | +5 °C |
| Electronics max temperature | < +65 °C | +58 °C (analysis) | +7 °C |
| PSR dwell margin | > 0 h margin | +4.0× on battery | OK |
| Heat pipe capacity margin | > 20% | 25% | OK |

**Open items at PDR-A:**
1. Radiator area to be confirmed at CDR pending science mode power growth trade.
2. HP-03 directionality analysis to be validated with full thermal model run in NX Thermal.
3. Regolith contact conductance measurement required for Z16 nodes (test coupon campaign).

---

*End of LPAS-THERM-001 Rev A*
