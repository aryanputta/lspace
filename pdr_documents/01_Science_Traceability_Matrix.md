# LPAS Science Traceability Matrix (STM)
## Document Number: LPAS-SCI-001 | Revision: A | Date: 2026-05-24

---

**Mission:** Lunar PSR Autonomy Scout (LPAS)
**Prepared By:** LPAS Science Team / Systems Engineering
**Approved By:** LPAS Principal Investigator
**Reference:** NASA SMD Lunar Discovery and Exploration Program Goals; LEAG Lunar Exploration Roadmap 2023

---

## 1.0 Purpose and Scope

This Science Traceability Matrix (STM) establishes the linkage between the top-level science goals of the LPAS mission and the specific measurements, instruments, and success criteria that operationalize those goals. The STM serves as the master driver for science requirements flow-down and is the authoritative reference for payload selection, instrument performance specifications, and mission success evaluation.

The STM is structured in five levels of increasing specificity:
1. **Science Goal** — Top-level programmatic scientific objective
2. **Science Objective** — Specific, testable scientific question
3. **Investigation** — Experimental approach or observational strategy
4. **Measurement** — Quantified parameter, precision, and spatial/temporal coverage
5. **Instrument** — Hardware implementation
6. **Success Criterion** — Threshold and baseline criteria for mission success evaluation

---

## 2.0 Science Context

### 2.1 Programmatic Justification

Permanently Shadowed Regions (PSRs) at the lunar south pole are thermally stable cold traps (surface temperatures < 40 K in deepest regions) that may have accumulated volatile species over billions of years via cometary impacts, asteroid delivery, solar wind implantation, and volcanic outgassing. Orbital data from LCROSS, LRO/LAMP, LRO/Mini-RF, Chandrayaan-1/M3, and SOFIA indicate elevated hydrogen and water-ice-equivalent signals in several south polar PSRs. However, ground-truth measurements of volatile abundance, vertical distribution, physical state (crystalline vs. amorphous ice), and regolith mixing ratio are absent.

LPAS directly addresses the highest-priority science questions identified in:
- National Academies of Sciences, Engineering, and Medicine (NASEM) 2023 *Origins, Worlds, and Life* Decadal Survey
- LEAG Lunar Exploration Roadmap, Theme I: "Understanding the Lunar Environment"
- NASA Moon to Mars Science Objectives (2020): "Resource Potential Assessment" objectives RP-1 through RP-4

### 2.2 Target Sites

| Site ID | Name | PSR Area (km²) | Est. Water Ice Signal (LEND H-epithermal) | Priority |
|---------|------|-----------------|-------------------------------------------|----------|
| PSR-A | Nobile Crater Floor | 1,340 | +18% suppression vs. average | Primary |
| PSR-B | Shackleton Inner Wall | 28 | +12% suppression | Secondary |
| PSR-C | Haworth NW Lobe | 640 | +9% suppression | Tertiary |

---

## 3.0 Science Traceability Matrix

### 3.1 Goal 1: Characterize Water Ice Distribution and Abundance in PSRs

| STM Row | Science Goal | Science Objective | Investigation | Measurement | Instrument | Success Criterion |
|---------|-------------|-------------------|---------------|-------------|------------|-------------------|
| 1.1 | **SG-1:** Characterize water ice distribution, abundance, and vertical stratigraphy within lunar south polar PSRs to support ISRU resource assessment and Artemis site selection | SO-1.1: Map bulk H₂O abundance vs. depth at ≥ 3 PSR sites spanning the Nobile/Haworth region | Percussive drill core extraction at 3 sites; neutron spectrometer orbital-to-ground calibration at each site | H₂O wt% at 0–10 cm, 10–30 cm, and 30–50 cm depth intervals; spatial resolution ≤ 5 m; measurement precision ±2 wt% | TRIDENT-heritage percussive drill (50 cm depth); PITMS volatile mass spectrometer; MONS-equivalent thermal neutron spectrometer (LPAS-NS) | **Threshold:** ≥ 1 site fully drilled to 50 cm with all 3 depth intervals sampled; **Baseline:** ≥ 3 sites with full vertical profile; data return ≥ 90% |
| 1.2 | **SG-1** (cont.) | SO-1.2: Determine physical state of water ice (crystalline vs. amorphous, pure vs. regolith-mixed) and ice grain size distribution at ≥ 2 sites | Near-infrared reflectance spectroscopy of drill tailings; mass spectrometric isotopic analysis; particle size sieve analysis from drill sample | NIR spectral reflectance 1.0–3.5 µm; H₂O band depth at 1.50, 2.02, 3.1 µm ±0.5% band depth; D/H isotope ratio ±50‰; grain size bins: <75, 75–250, 250–1000 µm | VIPER-NIRVSS-heritage near-infrared reflectance spectrometer (LPAS-NIRS); PITMS; drill sample sieve assembly | **Threshold:** 1 site with NIR spectra + isotopic measurement; **Baseline:** 2 sites with complete physical characterization suite |
| 1.3 | **SG-1** (cont.) | SO-1.3: Constrain the lateral heterogeneity of H₂O concentration at ≤ 500 m spatial scale across a PSR traverse of ≥ 1 km | Repeated neutron spectrometer measurements at 50-m intervals along traverse transect; surface temperature correlation via calibrated thermometry | Epithermal neutron count rate at ≥ 20 measurement stations per transect; sensitivity to ≥ 1 wt% H₂O change; measurement dwell time ≥ 300 s per station | LPAS-NS neutron spectrometer; LPAS-TC thermocouple array (surface contact); stereo navigation cameras (context imaging) | **Threshold:** ≥ 10 stations along 500 m transect in PSR-A; **Baseline:** ≥ 20 stations along 1 km transect at PSR-A + partial transect at PSR-B |

---

### 3.2 Goal 2: Characterize Regolith Mechanical and Physical Properties for ISRU

| STM Row | Science Goal | Science Objective | Investigation | Measurement | Instrument | Success Criterion |
|---------|-------------|-------------------|---------------|-------------|------------|-------------------|
| 2.1 | **SG-2:** Measure mechanical, physical, and thermal properties of PSR regolith to bound excavation energy requirements and engineering risk for ISRU operations | SO-2.1: Determine bearing capacity, cohesion, and internal friction angle of the top 50 cm of regolith at ≥ 2 PSR sites | Wheel slip telemetry analysis (WCA) during traverse; percussive drill specific energy measurement; cone penetrometer tip resistance vs. depth | Wheel slip ratio ≥ 1% resolution; drill specific energy (J/cm³) ±10%; cone tip resistance (qc) at 2 cm depth intervals ±5 kPa; derived friction angle ±3°; derived cohesion ±1 kPa | LPAS rover wheel encoders + IMU (traction analysis); TRIDENT drill with strain gauge bit force measurement; LPAS-CPT cone penetrometer tool | **Threshold:** WCA at ≥ 5 traverse segments + 1 CPT at PSR-A; **Baseline:** CPT at ≥ 2 sites + WCA throughout traverse |
| 2.2 | **SG-2** (cont.) | SO-2.2: Measure bulk density and particle size distribution of surface and subsurface regolith at ≥ 2 depth intervals | In-situ density measurements from drill core volume and mass; grain size analysis from sieve assembly in PITMS sample inlet | Bulk density ±50 kg/m³ at surface (0–5 cm) and 10–20 cm depth; grain size distribution in 6 bins (< 20, 20–75, 75–250, 250–1000, 1000–5000 µm, > 5 mm); cumulative size fraction ±5% | LPAS-CPT bulk density module; TRIDENT drill sample mass sensor (±0.1 g resolution); PITMS sample-prep sieve assembly | **Threshold:** Surface density at ≥ 1 PSR site; **Baseline:** Two-depth density profile + full grain size distribution at PSR-A and PSR-B |
| 2.3 | **SG-2** (cont.) | SO-2.3: Determine regolith thermal conductivity and specific heat capacity at the top 30 cm at ≥ 1 PSR site | Thermal needle probe insertion with controlled heating pulse; diurnal thermal cycling measurement at fixed location (72-hour soak) | Thermal conductivity k = 0.001–0.02 W/(m·K) ±20%; specific heat cp ±15%; thermal diffusivity ±20%; measurements at 5, 15, and 30 cm depth | LPAS-HFP heat flow probe (heritage: LunaH-Map); LPAS-TC thermocouple string; time-domain temperature acquisition at 0.1 K resolution | **Threshold:** Single depth (15 cm) thermal conductivity at PSR-A; **Baseline:** 3-depth profile + 72-hour time series at PSR-A |

---

### 3.3 Goal 3: Characterize the Radiation and Plasma Environment Within PSRs

| STM Row | Science Goal | Science Objective | Investigation | Measurement | Instrument | Success Criterion |
|---------|-------------|-------------------|---------------|-------------|------------|-------------------|
| 3.1 | **SG-3:** Measure the charged particle, photon, and neutron radiation environment within and at the boundary of PSRs to support crew radiation dose assessments and ISRU hardware qualification | SO-3.1: Quantify galactic cosmic ray (GCR) and solar energetic particle (SEP) dose rate inside a PSR vs. the adjacent illuminated surface | Simultaneous dosimetry measurements at the PSR boundary and ≥ 50 m interior; comparison with LRO/CRaTER orbital baseline | Absorbed dose rate (µGy/hr) at 0.1 µGy/hr resolution; dose equivalent (µSv/hr); linear energy transfer (LET) spectrum 0.2–10,000 MeV·cm²/g; temporal resolution 60 s; measurement pairs inside vs. outside PSR | LPAS-RAD silicon detector stack (heritage: MSL/RAD, BIRD architecture); 8-detector stack with Al shielding window | **Threshold:** ≥ 24 hours continuous dosimetry at PSR-A boundary; **Baseline:** ≥ 48 hours inside + outside paired measurements at PSR-A |
| 3.2 | **SG-3** (cont.) | SO-3.2: Measure thermal and epithermal neutron flux variation between illuminated regolith and PSR interior to calibrate orbital neutron spectrometer data | Neutron flux measurements on 50-m traverse grid entering PSR; simultaneous LRO/LEND orbital overpass coordination | Thermal neutron count rate (≤ 0.5 eV) ±3% statistical; epithermal neutron count rate (0.5 eV – 500 keV) ±3%; spatial sampling every 25 m traverse; minimum dwell 300 s/station | LPAS-NS thermal neutron spectrometer (He-3 and Li-6 detector channels, 200 cm² effective area) | **Threshold:** 10-station profile crossing PSR boundary at PSR-A; **Baseline:** 20-station grid at PSR-A + 10-station at PSR-B |
| 3.3 | **SG-3** (cont.) | SO-3.3: Measure plasma density, ion composition, and electric field at the PSR boundary to characterize electrostatic dust lofting environment | Langmuir probe sweep during traverse from illuminated to shadowed terrain; ion mass spectrometer sampling | Electron density ne: 10–10⁵ cm⁻³ ±20%; electron temperature Te: 0.1–10 eV ±15%; ion composition: Na⁺, K⁺, Ca⁺, Ar⁺, H₂O⁺ with 10⁴ dynamic range; electrostatic field Ez ±50 mV/m | LPAS-LP Langmuir probe (swept-bias, 2 probes deployed on 1 m booms); PITMS ion channel | **Threshold:** Langmuir probe data through PSR boundary crossing; **Baseline:** Full ion composition at ≥ 3 points across boundary + interior |

---

### 3.4 Goal 4: Characterize the Topographic and Geologic Context of PSR Margins

| STM Row | Science Goal | Science Objective | Investigation | Measurement | Instrument | Success Criterion |
|---------|-------------|-------------------|---------------|-------------|------------|-------------------|
| 4.1 | **SG-4:** Produce high-resolution topographic maps and geologic characterizations of PSR margins and interiors to support future crewed landing and EVA route planning | SO-4.1: Generate ≥ 1:500-scale topographic map of PSR ingress corridor(s) with slope, roughness, and hazard characterization | Stereo photogrammetry from rover-mounted cameras during traverse; LiDAR point cloud at key waypoints; ground-truth correlation with LRO/LOLA 1-m DEM | Terrain elevation accuracy ±0.05 m; slope accuracy ±0.5°; surface roughness RMS ±0.02 m over 1 m baseline; spatial coverage ≥ 1 km² at PSR-A; point cloud density ≥ 100 pts/m² | LPAS stereo hazard avoidance cameras (1024×1024 px, 120° FOV, 40 cm baseline); LPAS-LiDAR (rotating 2D, 905 nm, 30 m range, 0.1° angular resolution) | **Threshold:** Topographic strip ≥ 200 m × 20 m along ingress corridor at PSR-A; **Baseline:** ≥ 1 km² PSR-A ingress zone mapped to ±5 cm vertical accuracy |
| 4.2 | **SG-4** (cont.) | SO-4.2: Characterize surface albedo and spectral reflectance of PSR floor and illuminated rim to distinguish ice-rich vs. ice-poor surface units | Multispectral imaging at ≥ 6 wavelengths across illuminated/shadowed boundary; photometric normalization to standard geometry | Reflectance factor (REFF) at 440, 540, 650, 750, 900, 1000 nm ±2% calibrated accuracy; spatial resolution ≤ 0.5 mrad/pixel at nadir; coverage ≥ 0.5 km² | LPAS-MC multispectral science camera (Bayer + 2 NIR-pass filters, 2048×2048 px, f/8); active LED calibration target | **Threshold:** ≥ 3 spectral bands at PSR-A boundary (50 m swath); **Baseline:** Full 6-band mosaic of PSR-A ingress zone + 3-band PSR-B |
| 4.3 | **SG-4** (cont.) | SO-4.3: Document boulder distribution, impact crater size-frequency, and regolith surface age constraints at PSR margin and interior | Systematic imaging transects; crater counting on orthorectified mosaics; in-situ micrometeorite flux measurement | Boulder count ≥ 0.3 m diameter; crater diameter range 0.1–50 m; size-frequency distribution relative age ±30%; transect spacing ≤ 10 m; micrometeorite flux detector exposure ≥ 30 days | LPAS stereo navigation cameras (context imaging at 0.2 mrad/pixel); LPAS-MC (science imaging); passive dust/micrometeorite impact sensor array (piezoelectric film, 0.1 m² area) | **Threshold:** Boulder/crater survey along 500 m traverse at PSR-A; **Baseline:** ≥ 2 km total transect across PSR-A margin + 30-day micrometeorite flux record |

---

## 4.0 Instrument Summary

| Instrument ID | Instrument Name | Heritage | Mass (kg) | Power (W) | Key Measurement |
|---------------|----------------|----------|-----------|-----------|-----------------|
| TRIDENT | Percussive rotary drill, 50 cm depth | TRIDENT (VIPER) | 5.2 | 65 (peak) | Drill cores, sample delivery |
| PITMS | Portable Isotope and Thermal Mass Spectrometer | PITMS (VIPER) | 2.1 | 14 | Volatile species, isotopes |
| LPAS-NS | Neutron Spectrometer (He-3 + Li-6) | LEND/LRO heritage | 2.8 | 4 | H abundance mapping |
| LPAS-NIRS | Near-Infrared Reflectance Spectrometer 1.0–3.5 µm | NIRVSS (VIPER) | 1.4 | 6 | Ice physical state |
| LPAS-CPT | Cone Penetrometer + Bulk Density Tool | MoonRaker (concept) | 1.6 | 8 (actuator) | Regolith mechanical props |
| LPAS-HFP | Heat Flow Probe (thermal needle, 30 cm) | HP³ (InSight) heritage | 0.9 | 3 (heater) | Thermal conductivity |
| LPAS-RAD | Radiation Detector Stack (Si, 8 layers) | MSL/RAD | 1.5 | 4 | Dose rate, LET spectrum |
| LPAS-LP | Langmuir Probe (dual, 1 m boom) | MAVEN/LP heritage | 0.6 | 1.5 | Plasma density, Te |
| LPAS-LiDAR | 2D Rotating LiDAR, 905 nm | Velodyne VLP-16 heritage | 1.8 | 8 | Terrain elevation |
| LPAS-MC | Multispectral Science Camera, 2048 px | Mastcam-Z (MSL) heritage | 1.7 | 5 | Spectral reflectance |
| LPAS-TC | Thermocouple Array (8-pt surface contact) | Various | 0.4 | 0.5 | Surface temperature |
| **TOTAL** | | | **20.0** | **119 (peak)** | |
| Drill Sample Handling + Sieve | Mechanical sample routing | VIPER SAMPLE | 2.0 | 12 | Sample prep |
| **TOTAL WITH HANDLING** | | | **22.0** | **131 (peak)** | |

---

## 5.0 Measurement Priority Matrix

| Measurement | Priority | Required for Threshold? | Required for Baseline? | Notes |
|-------------|----------|------------------------|----------------------|-------|
| H₂O wt% depth profile (drill core) | 1 | Yes | Yes | Highest ISRU value |
| Regolith mechanical properties (CPT) | 2 | Yes | Yes | Engineering-critical |
| NIR ice physical state | 3 | No | Yes | Science value add |
| Radiation dose rate (inside/outside PSR) | 4 | Yes | Yes | Crew safety critical |
| Thermal conductivity | 5 | No | Yes | ISRU thermal modeling |
| Neutron spectrometer traverse grid | 6 | Yes | Yes | Orbital cal required |
| Topographic mapping (stereo/LiDAR) | 7 | Yes | Yes | Navigation + planning |
| Plasma/Langmuir probe | 8 | No | No | Bonus science |
| Multispectral surface mapping | 9 | No | Yes | Context + science |
| Micrometeorite flux | 10 | No | No | Long-duration bonus |

---

## 6.0 Data Volume Requirements

| Science Product | Raw Data Rate | Compression Ratio | Compressed Volume/Sol | Priority |
|----------------|--------------|-------------------|-----------------------|---------|
| Drill core images (4× per drill) | 12 MB/event | 5:1 lossless | 9.6 MB/drill sol | 1 |
| PITMS mass spectra | 2 MB/sample | 3:1 | 2.7 MB/drill sol | 1 |
| LPAS-NS neutron counts | 0.1 MB/hr | 2:1 | 1.2 MB/day | 2 |
| LPAS-NIRS spectra (16 per sol) | 0.5 MB/spectrum | 3:1 | 2.7 MB/day | 2 |
| Navigation stereo images | 3 MB/pair | 4:1 | 75 MB/traverse sol | 3 |
| LiDAR point clouds | 20 MB/scan | 8:1 | 50 MB/day | 3 |
| LPAS-MC multispectral mosaics | 8 MB/image | 6:1 | 26 MB/day | 4 |
| LPAS-RAD dosimetry | 0.02 MB/hr | 2:1 | 0.24 MB/day | 2 |
| Housekeeping telemetry | 5 MB/day | 4:1 | 1.25 MB/day | 1 |
| **TOTAL (peak traverse + science sol)** | | | **~169 MB/day** | |
| **TOTAL (science ops sol only)** | | | **~90 MB/day** | |
| **Allocated downlink budget** | | | **500 MB/day** | See Comms Budget |

---

*Document end. Revision history tracked in LPAS DOORS database, baseline LPAS-SCI-001-REV-A.*
