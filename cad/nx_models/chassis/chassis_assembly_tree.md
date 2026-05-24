# LPAS Chassis Assembly — NX Assembly Tree

**Assembly:** LPAS-CHASSIS-001  
**Revision:** PDR-A  
**Mass (CBE):** 45.0 kg  
**Material Baseline:** Al-7075-T73 honeycomb panels, Al-6061-T6 structural members  

---

## NX Assembly Hierarchy

```
LPAS-CHASSIS-001 (Top-Level Assembly)
│
├── LPAS-STRUCT-010  Primary Structure Subassembly
│   ├── LPAS-STRUCT-011  Upper deck panel (Al honeycomb 20mm core)
│   │   ├── Part: upper_deck_panel.prt  [620mm × 480mm × 30mm]
│   │   └── Part: pcdu_mount_bracket.prt  [4x M8 interface]
│   ├── LPAS-STRUCT-012  Lower deck panel (Al honeycomb 20mm core)
│   │   └── Part: lower_deck_panel.prt  [620mm × 480mm × 30mm]
│   ├── LPAS-STRUCT-013  Side panel assembly (×2, mirrored)
│   │   ├── Part: side_panel_left.prt
│   │   └── Part: side_panel_right.prt  [mirrored instance]
│   ├── LPAS-STRUCT-014  Fore bulkhead
│   │   └── Part: fore_bulkhead.prt  [Al-7075 solid, 4mm]
│   ├── LPAS-STRUCT-015  Aft bulkhead
│   │   └── Part: aft_bulkhead.prt  [Al-7075 solid, 4mm]
│   └── LPAS-STRUCT-016  Corner longeron assembly (×4)
│       └── Part: longeron.prt  [Al-6061 extrusion, 40×40×3mm]
│
├── LPAS-WHEEL-MOUNT-020  Wheel Mount Subassembly (×6)
│   ├── LPAS-WHEEL-MOUNT-021  Front wheel mount — left
│   │   ├── Part: wheel_mount_housing.prt  [Ti-6Al-4V]
│   │   ├── Part: motor_interface_flange.prt
│   │   └── Part: bearing_race_assembly.prt
│   ├── LPAS-WHEEL-MOUNT-022  Mid wheel mount — left [mirrored from 021]
│   ├── LPAS-WHEEL-MOUNT-023  Rear wheel mount — left [mirrored from 021]
│   ├── LPAS-WHEEL-MOUNT-024  Front wheel mount — right [mirrored from 021]
│   ├── LPAS-WHEEL-MOUNT-025  Mid wheel mount — right
│   └── LPAS-WHEEL-MOUNT-026  Rear wheel mount — right
│
├── LPAS-SUSPENSION-030  Rocker-Bogie Suspension
│   ├── LPAS-SUSPENSION-031  Left rocker arm
│   │   ├── Part: rocker_arm_left.prt  [Al-6061, hollow tube 50×50×3mm]
│   │   ├── Part: rocker_pivot_bearing.prt
│   │   └── Part: rocker_bogie_joint.prt
│   ├── LPAS-SUSPENSION-032  Right rocker arm [mirrored]
│   ├── LPAS-SUSPENSION-033  Left bogie arm
│   │   ├── Part: bogie_arm_left.prt  [Al-6061, 40×40×3mm]
│   │   └── Part: bogie_pivot_bearing.prt
│   ├── LPAS-SUSPENSION-034  Right bogie arm [mirrored]
│   └── LPAS-SUSPENSION-035  Differential bar
│       └── Part: diff_bar.prt  [Al-6061, connects left/right rocker]
│
├── LPAS-EBOX-040  Electronics Bay Enclosure
│   ├── Part: ebox_housing.prt  [Al-6061, 400×300×200mm]
│   ├── Part: ebox_lid.prt  [removable, captive fasteners]
│   ├── Part: ebox_thermal_gasket.prt  [Indium thermal interface]
│   ├── Part: internal_card_cage.prt  [PCB mounting rails]
│   └── Part: ebox_connector_panel.prt  [D-sub and circular connectors]
│
└── LPAS-INTERFACE-050  External Interface Hardware
    ├── Part: lander_egress_ramp_attach.prt  [2x bolt pattern, shear pins]
    ├── Part: hga_mast_base.prt  [deployed from aft deck]
    ├── Part: solar_array_hinge_assy.prt  [×2, symmetric]
    └── Part: science_bay_panel.prt  [removable access door]
```

---

## Key Dimensions

| Parameter | Value |
|-----------|-------|
| Chassis length | 1,400 mm |
| Chassis width (body) | 620 mm |
| Chassis height (body) | 480 mm |
| Overall width (wheels deployed) | 1,750 mm |
| Overall height (antennas stowed) | 1,100 mm |
| Ground clearance | 280 mm |
| Wheelbase (front-rear) | 950 mm |
| Track width | 1,750 mm |

---

## Material Specifications

| Component | Material | Alloy | Temper | Notes |
|-----------|----------|-------|--------|-------|
| Honeycomb panels | Aluminum | 7075 | T73 | 20mm core, 0.5mm face |
| Structural members | Aluminum | 6061 | T6 | Extrusions |
| Wheel mounts | Titanium | Ti-6Al-4V | STA | Forged |
| Fasteners | Stainless | A286 | H1100 | Locking inserts |
| Electronics bay | Aluminum | 6061 | T651 | Machined |

---

## Interfaces to Other Assemblies

| Interface | Assembly | Interface Type | Specification |
|-----------|----------|----------------|---------------|
| Wheel mount → Wheel | LPAS-WHEEL-001 | Mechanical | 4-bolt pattern, 60mm BCD |
| Chassis → Lander | CLPS-LANDER | Mechanical | 4-point attach, quick-release |
| E-box → Power | LPAS-POWER-001 | Electrical | 28V input, 60A max |
| E-box → Harness | LPAS-HARNESS | Electrical | Circular MIL-spec connectors |

---

## NX Analysis Settings

- **Solver:** NX Nastran
- **Mesh type:** 10-node tetrahedral (CTETRA10) for complex parts
- **Shell elements:** CQUAD4 for panels
- **Load cases:**
  - Launch (quasi-static): 10g axial, 6g lateral
  - Landing impact: 3g axial, peak 8g (50ms pulse)
  - Thermal cycling: -230°C to +120°C
- **Margin of Safety target:** MS > 0.25 (conservative for PDR)
