# LPAS Mass Budget
**Document:** LPAS-MECH-MASS-001  
**Revision:** PDR-A  
**Date:** 2026-05-24  
**Status:** Preliminary Design  

---

## Mass Budget Summary

| Subsystem | CBE (kg) | Margin (%) | MEV (kg) | Notes |
|-----------|----------|------------|----------|-------|
| Chassis & Structure | 45.0 | 11.6 | 50.2 | Al-7075 honeycomb, Ti mounts |
| Mobility System | 18.0 | 10.9 | 20.0 | 6-wheel mesh, motors, encoders |
| Power System | 26.0 | 11.5 | 29.0 | Solar + LFP battery + PCDU |
| Thermal Control | 6.0 | 11.7 | 6.7 | MLI, radiators, heaters, straps |
| Avionics | 5.0 | 11.3 | 5.6 | Flight computer, IMU, harness |
| Communications | 5.0 | 11.4 | 5.6 | UHF + Ka-band HGA |
| Navigation Sensors | 3.0 | 11.0 | 3.3 | Stereo cams, LIDAR, thermal IR |
| Science Payload | 22.0 | 13.4 | 24.9 | Drill, spectrometer, cameras |
| Miscellaneous | 2.0 | 16.7 | 2.3 | Dust covers, calibration targets |
| **TOTAL DRY MASS** | **132.0** | **11.9** | **147.7** | |
| System Margin (15%) | 19.8 | — | 22.2 | Per NASA mass margin policy |
| **TOTAL WITH MARGIN** | **151.8** | — | **169.9** | |

**Requirement: < 250 kg TOTAL** ✅ — 80 kg margin remaining

---

## Detailed Breakdown

### 1. Chassis & Structure (45.0 kg CBE)

| Item | Qty | Unit (kg) | Total CBE (kg) | Margin (%) | MEV (kg) |
|------|-----|-----------|----------------|------------|----------|
| Upper deck panel (Al-7075 HC, 20mm) | 1 | 4.2 | 4.2 | 12 | 4.7 |
| Lower deck panel | 1 | 3.8 | 3.8 | 12 | 4.3 |
| Side panels (×2) | 2 | 2.8 | 5.6 | 12 | 6.3 |
| Fore/aft bulkheads (×2) | 2 | 1.8 | 3.6 | 12 | 4.0 |
| Corner longerons (×4) | 4 | 0.8 | 3.2 | 10 | 3.5 |
| Electronics bay housing | 1 | 6.4 | 6.4 | 10 | 7.0 |
| Titanium wheel mounts (×6) | 6 | 0.7 | 4.2 | 10 | 4.6 |
| Rocker arms (×2) | 2 | 2.8 | 5.6 | 12 | 6.3 |
| Bogie arms (×2) | 2 | 1.6 | 3.2 | 12 | 3.6 |
| Differential bar | 1 | 1.8 | 1.8 | 12 | 2.0 |
| Fasteners and inserts | — | — | 2.1 | 15 | 2.4 |
| Lander interface hardware | 1 | 1.3 | 1.3 | 15 | 1.5 |
| **Subtotal** | | | **45.0** | **11.6** | **50.2** |

### 2. Mobility System (18.0 kg CBE)

| Item | Qty | Unit (kg) | Total CBE (kg) | Margin (%) | MEV (kg) |
|------|-----|-----------|----------------|------------|----------|
| Ti mesh wheel (r=250mm, w=175mm) | 6 | 0.95 | 5.7 | 12 | 6.4 |
| Wheel hub assembly | 6 | 0.42 | 2.5 | 10 | 2.8 |
| BLDC motor (75W peak) | 6 | 0.55 | 3.3 | 10 | 3.6 |
| Motor controller (integrated) | 6 | 0.18 | 1.1 | 10 | 1.2 |
| Optical wheel encoder | 6 | 0.04 | 0.24 | 10 | 0.3 |
| Bearing assemblies | 12 | 0.15 | 1.8 | 10 | 2.0 |
| Wheel harness | 1 | — | 0.8 | 15 | 0.9 |
| Motor heaters (×6) | 6 | 0.05 | 0.3 | 10 | 0.33 |
| Grouser attachment hardware | — | — | 0.86 | 10 | 0.95 |
| Wheel debris guards | 6 | 0.06 | 0.36 | 15 | 0.4 |
| Miscellaneous hardware | — | — | 1.84 | 12 | 2.1 |
| **Subtotal** | | | **18.0** | **10.9** | **20.0** |

### 3. Power System (26.0 kg CBE)

| Item | Qty | Unit (kg) | Total CBE (kg) | Margin (%) | MEV (kg) |
|------|-----|-----------|----------------|------------|----------|
| GaAs solar array panel (1m × 0.6m) | 2 | 2.8 | 5.6 | 12 | 6.3 |
| Solar array substrate/structure | 2 | 1.0 | 2.0 | 12 | 2.2 |
| Single-axis deployment mechanism | 2 | 1.1 | 2.2 | 15 | 2.5 |
| LFP battery pack (150 Wh, 4S3P) | 1 | 9.8 | 9.8 | 10 | 10.8 |
| Battery management system (BMS) | 1 | 0.4 | 0.4 | 10 | 0.4 |
| Power Control Distribution Unit | 1 | 2.8 | 2.8 | 12 | 3.1 |
| DC-DC converters (28V→5V, 3.3V) | 2 | 0.3 | 0.6 | 10 | 0.7 |
| Battery heaters (PTC, 20W) | 3 | 0.05 | 0.15 | 10 | 0.2 |
| Power harness | 1 | — | 1.2 | 15 | 1.4 |
| Solar array harness | 1 | — | 0.6 | 15 | 0.7 |
| Shunts, fuses, connectors | — | — | 0.65 | 10 | 0.7 |
| **Subtotal** | | | **26.0** | **11.5** | **29.0** |

---

## Mass Margin Policy

Per **NASA/SP-2016-6105 Rev2, Section 6.5.4** and mission-specific constraint:

| Design Maturity Level | Required Margin |
|-----------------------|-----------------|
| Conceptual (Phase A) | 30% |
| Preliminary Design (Phase B/PDR) | 20% |
| Critical Design (Phase C/CDR) | 15% |
| Manufacturing (Phase D) | 5% |

**Current status: PDR — 20% required, 60.6% maintained** ✅

---

## Mass Growth Allowance (MGA) Tracking

| Review | CBE Target | Actual CBE | Status |
|--------|-----------|------------|--------|
| MCR | < 300 kg | — | Planned |
| SRR | < 250 kg | — | Planned |
| **PDR** | **< 200 kg** | **132.0 kg** | ✅ PASS |
| CDR | < 180 kg | TBD | Planned |
| TRR | < 175 kg | TBD | Planned |

---

## Heritage Mass References

| Heritage Vehicle | Total Mass | Scale Factor |
|-----------------|-----------|--------------|
| VIPER Rover | 430 kg | LPAS smaller: science-focused |
| Yutu-2 (Chang'e-4) | 140 kg | Similar class |
| ATHLETE (concept) | 900 kg | Heavy mobility test platform |
| Mars Perseverance | 1,025 kg | Much larger Mars mission |

LPAS at 132 kg CBE is appropriately sized for CLPS-class lander delivery (max 200 kg payload).
