# LPAS Mission Scenario — STK Setup Guide

## Scenario Overview

| Parameter | Value |
|---|---|
| Mission Name | Lunar PSR Autonomy Scout (LPAS) |
| Epoch Start | 1 Jan 2028 00:00:00.000 UTCG |
| Epoch Stop | 1 Jan 2029 00:00:00.000 UTCG |
| Duration | 365.25 days |
| Time Step | 60 seconds (propagation), 10 s (access computation) |
| Central Body | Moon |
| Reference Frame | Moon Fixed (IAU MOON) |

---

## 1. STK Version and Module Requirements

- STK 12.x or later
- Modules required: STK Pro, Coverage, Communications, Terrain, SOLIS (or equivalent lunar surface vehicle propagator)
- Python integration: AGSpy / STK Engine for Python (optional, for scripting)
- SPICE kernels: NAIF/JPL DE440 ephemeris, PCK lunar orientation

---

## 2. Central Body Configuration

### 2.1 Moon Central Body

```
Object Type : CentralBody
Name        : Moon
Ephemeris   : DE440 (NAIF kernel de440.bsp)
Orientation : IAU Working Group Report 2015 (PCK)
Shape       : Oblate spheroid, R_eq = 1737.4 km, f = 0.00125
Gravity     : GRGM900C (truncated 70x70)
```

**Terrain Model — LOLA DEM**

```
Source      : NASA LOLA (Lunar Orbiter Laser Altimeter)
Product     : SLDEM2015 (512 ppd, ~59 m/post at equator)
Coverage    : Global, 87.5S–87.5N
File Format : GeoTIFF (.tif) or STK .pdtt terrain tile set
Resolution  : 118 m/post at south polar region (60–90S at 512 ppd)
Datum       : Lunar reference sphere, R = 1737.4 km
STK Path    : <STK_data>/Terrain/Moon/SLDEM2015_512ppd_87S_87N_000_360.pdtt
Polar patch : Supplementary 256 ppd global tile set for areas > 87.5S
```

**LOLA Terrain Import Steps in STK**

1. Open STK scenario → Insert → New Object → CentralBody → Moon
2. Right-click Moon → Properties → Terrain
3. Click "Add" → Navigate to SLDEM2015 tile set
4. Set interpolation: Bicubic
5. Enable "Use terrain for line-of-sight calculations": Yes
6. Enable "Use terrain for access calculations": Yes

---

## 3. Object Definitions

### 3.1 LPAS Rover (Surface Vehicle)

```
Object Type     : GroundVehicle (Surface Vehicle)
Name            : LPAS_Rover
Central Body    : Moon
Initial Position: 89.5S latitude, 0.000E longitude
Altitude        : Terrain (terrain-following enabled)
Propagator      : Great Arc (lunar surface)
```

**Rover Properties**

```
Body Dimensions : 1.2 m (L) x 0.9 m (W) x 0.75 m (H)
Wheel Track     : 0.85 m
Wheel Base      : 1.0 m
Max Speed       : 0.15 m/s nominal, 0.05 m/s in PSR
Terrain Model   : SLDEM2015 (terrain-following)
Altitude Method : AGL 0.35 m (wheel center height)
```

**Sensor Definitions on Rover**

```
[Sensor 1 — UHF Relay Antenna]
  Type            : Half-Power Half-Angle (conical)
  Half Angle      : 80 deg (near-omnidirectional)
  Pointing        : Body-fixed +Z (zenith)
  Frequency       : 437.525 MHz
  EIRP            : 12 dBW

[Sensor 2 — Hazard Camera (Hazcam)]
  Type            : Rectangular
  Horizontal FOV  : 120 deg
  Vertical FOV    : 90 deg
  Pointing        : Body-fixed +X (forward)
  Range           : 0–15 m effective hazard range

[Sensor 3 — Neutron Spectrometer Science FOV]
  Type            : Conical
  Half Angle      : 60 deg
  Pointing        : Body-fixed -Z (nadir)
  Science Range   : 0.5 m radius footprint at 0.35 m AGL
```

**Traverse Path Definition**

Waypoints are defined as a route file (GroundVehicle_Route.csv):

```
Waypoint, Latitude (S), Longitude (E), Speed (m/s), Notes
WP-00,    89.500,       0.000,         0.00,        Initial deployment
WP-01,    89.520,       0.050,         0.08,        Egress from lander
WP-02,    89.540,       0.120,         0.10,        Traverse to PSR-A entry
WP-03,    89.570,       0.180,         0.05,        PSR-A science stop #1
WP-04,    89.590,       0.250,         0.05,        PSR-A science stop #2
WP-05,    89.610,       0.310,         0.08,        Exit PSR-A
WP-06,    89.550,       1.200,         0.10,        Inter-site transit
WP-07,    89.720,       1.350,         0.05,        PSR-B science stop #1
WP-08,    89.750,       1.420,         0.05,        PSR-B science stop #2
WP-09,    89.800,       2.000,         0.08,        Transit to PSR-C
WP-10,    89.850,       2.150,         0.05,        PSR-C science stop #1
```

---

### 3.2 Relay Station (Fixed Facility)

```
Object Type     : Facility
Name            : LPAS_Relay_Station
Central Body    : Moon
Latitude        : 88.000S
Longitude       : 0.000E
Altitude        : Terrain + 5.0 m (mast height above terrain)
Terrain Model   : SLDEM2015
```

**Relay Station Properties**

```
Platform        : Lander-mounted relay mast
Mast Height     : 5.0 m above lander deck (8.5 m above local terrain)
```

**Relay Station Sensors / Transceivers**

```
[Transceiver 1 — UHF Rover Link]
  Frequency       : 437.525 MHz
  Antenna Type    : Yagi-Uda, 5 elements
  Gain            : 8 dBi
  Beamwidth       : 60 deg 3-dB half-angle (broad for rover tracking)
  RX Noise Fig    : 2.0 dB
  TX Power        : 2 W (relay downlink to rover)

[Transceiver 2 — Ka-Band Earth Link]
  Frequency       : 26.0 GHz (TX), 18.0 GHz (RX)
  Antenna Type    : Parabolic dish, 0.5 m diameter
  TX Gain         : 46.0 dBi (computed)
  RX Gain         : 42.5 dBi at 18 GHz
  EIRP            : 59 dBW
  Pointing        : Two-axis gimbal, Earth-pointed
```

---

### 3.3 DSN Ground Stations

#### Goldstone (DSS-14, 70-m dish)

```
Object Type     : Facility
Name            : DSN_Goldstone
Central Body    : Earth
Latitude        : 35.4260N
Longitude       : 116.8900W  (243.110E)
Altitude        : 1001.39 m MSL
```

```
[Antenna — 70-m BWG Dish]
  Frequency       : 26.0 GHz (Ka receive), 34.0 GHz (Ka transmit)
  RX Gain         : 74.2 dBi at 26 GHz
  System Temp     : 25 K (G/T = 59.3 dB/K)
  Beamwidth       : 0.048 deg at 26 GHz (3-dB)
  Min Elevation   : 6.0 deg (masking constraint)
  Azimuth Range   : 0–360 deg (continuous rotation)
```

#### Madrid (DSS-65, 34-m BWG)

```
Object Type     : Facility
Name            : DSN_Madrid
Central Body    : Earth
Latitude        : 40.4270N
Longitude       : 355.7500E  (4.250W)
Altitude        : 833.79 m MSL
```

```
[Antenna — 34-m BWG Dish]
  Frequency       : 26.0 GHz Ka-band
  RX Gain         : 68.1 dBi at 26 GHz
  System Temp     : 32 K (G/T = 53.1 dB/K)
  Beamwidth       : 0.095 deg at 26 GHz
  Min Elevation   : 8.0 deg
```

#### Canberra (DSS-43, 70-m dish)

```
Object Type     : Facility
Name            : DSN_Canberra
Central Body    : Earth
Latitude        : 35.4014S
Longitude       : 148.9817E
Altitude        : 688.87 m MSL
```

```
[Antenna — 70-m dish]
  Frequency       : 26.0 GHz Ka-band
  RX Gain         : 74.2 dBi at 26 GHz
  System Temp     : 26 K (G/T = 59.1 dB/K)
  Beamwidth       : 0.048 deg at 26 GHz
  Min Elevation   : 5.0 deg
```

---

## 4. Analysis Chain: Rover to Relay to Earth

### 4.1 Link Chain Configuration

```
Chain Name  : LPAS_Full_Link_Chain
Strand 1    : LPAS_Rover → LPAS_Relay_Station   (UHF, 437.525 MHz)
Strand 2    : LPAS_Relay_Station → DSN_Goldstone (Ka-band, 26 GHz)
Strand 3    : LPAS_Relay_Station → DSN_Madrid    (Ka-band, 26 GHz)
Strand 4    : LPAS_Relay_Station → DSN_Canberra  (Ka-band, 26 GHz)

Chain Access: in-access when Strand 1 AND (Strand 2 OR Strand 3 OR Strand 4) are simultaneously satisfied.
```

**STK Chain Setup**

1. Analysis → New Chain
2. Name: `LPAS_Full_Link_Chain`
3. Objects: Add LPAS_Rover, LPAS_Relay_Station, DSN_Goldstone (repeat for Madrid, Canberra as separate chains then Union)
4. Strand Type: Link (for RF analysis) or Line of Sight (for geometric only)
5. Access Constraint: Propagation time < 1.5 s (light-time corrected)
6. Enable: "Use CentralBody terrain for occlusion"

---

## 5. Coverage Analysis Configuration

### 5.1 Coverage Definition

```
Coverage Name   : PSR_Comm_Coverage
Coverage Type   : Point Coverage (on Moon surface)
Grid Type       : Custom latitude/longitude bounds
Lat Range       : 89.0S to 90.0S
Lon Range       : 0E to 360E
Grid Spacing    : 0.05 deg latitude x 0.1 deg longitude
Altitude        : Terrain surface
Asset           : LPAS_Relay_Station (access FROM relay)
Min Elevation   : 0.5 deg (above lunar horizon)
Terrain Masking : Enabled (SLDEM2015)
```

**Figure of Merit (FOM) Settings**

```
FOM 1 — Percent Coverage
  Type        : Percent of Time With Coverage
  Threshold   : 1 access (1 or more simultaneous)

FOM 2 — Coverage Gap
  Type        : Maximum Gap Duration
  Report      : Maximum blackout interval (seconds)

FOM 3 — Access Duration
  Type        : Simple Coverage (total time in access)
  Report      : Cumulative access time over mission duration
```

### 5.2 PSR Target Site Definitions

```
Site    Lat (S)    Lon (E)    PSR Diameter (km)   Notes
PSR-A   89.57      0.25       3.2                 Haworth Crater floor
PSR-B   89.73      1.42       4.8                 Shackleton adjacent
PSR-C   89.85      2.15       2.1                 Nobile Crater rim shadow
```

For each site, create a STK Area Target:
```
Object Type : AreaTarget
Name        : PSR_A_Target
Central Body: Moon
Shape       : Ellipse
Semi-Major  : 1.6 km
Semi-Minor  : 1.6 km
Latitude    : 89.57S
Longitude   : 0.25E
Orientation : 0 deg (north-aligned)
```

---

## 6. Access Reports Configuration

### 6.1 Rover-to-Relay Access Report

```
Report Name : LPAS_Rover_Relay_Access
Object 1    : LPAS_Rover
Object 2    : LPAS_Relay_Station
Type        : Access
Interval    : Full mission epoch (1 Jan 2028 – 1 Jan 2029)
Constraint  : LOS (terrain-blocked accesses excluded)
```

**Report Fields**

| Field | Units | Description |
|---|---|---|
| Access Number | — | Sequential access interval index |
| Start Time | UTCG | Access start epoch |
| Stop Time | UTCG | Access end epoch |
| Duration | seconds | Length of access window |
| Max Elevation Angle | degrees | Peak elevation angle at relay |
| Min Range | km | Minimum rover-relay range |
| Max Range | km | Maximum rover-relay range |

### 6.2 Relay-to-DSN Access Reports

```
Report Name : LPAS_Relay_DSN_Access
Objects     : LPAS_Relay_Station vs. DSN_Goldstone / DSN_Madrid / DSN_Canberra
Fields      : Same as above + Doppler shift, light-time delay, one-way range rate
```

### 6.3 End-to-End Chain Access Report

```
Report Name : LPAS_End_to_End_Chain
Chain       : LPAS_Full_Link_Chain
Fields      :
  - Access start/stop/duration
  - Total accessible time (%)
  - Blackout start/stop/duration
  - Max blackout duration
  - Active DSN station during each access
```

---

## 7. RF Communications Analysis Setup

### 7.1 Transmitter / Receiver Objects

**Rover UHF Transmitter**

```
Name            : LPAS_Rover_UHF_TX
Frequency       : 437.525 MHz
Power           : 5.0 W (7.0 dBW)
Modulation      : BPSK
Data Rate       : 128 kbps
FEC             : Turbo code, rate 1/2, K=7
Effective Rate  : 64 kbps (after FEC)
Antenna Gain    : 5.0 dBi (stub helix)
EIRP            : 12.0 dBW
```

**Relay Station UHF Receiver**

```
Name            : LPAS_Relay_UHF_RX
Frequency       : 437.525 MHz
Antenna Gain    : 8.0 dBi
Noise Figure    : 2.0 dB
System Noise Temp: 300 K
Bandwidth       : 256 kHz (matched to data rate)
```

### 7.2 Link Budget Constraints in STK

```
Access Constraint — UHF Link:
  Required Eb/N0  : 9.6 dB (BPSK, BER 1e-5)
  Margin Required : 3.0 dB
  Min Link Margin : 0 dB (constraint for access determination)

Access Constraint — Ka Link:
  Required SNR    : 12.0 dB
  Margin Required : 3.0 dB
```

---

## 8. Scenario Execution Checklist

```
[ ] 1. Create new STK scenario with epoch 1 Jan 2028 – 1 Jan 2029
[ ] 2. Set central body to Moon, import SLDEM2015 terrain
[ ] 3. Insert LPAS_Rover surface vehicle at 89.5S, 0E
[ ] 4. Import waypoint route file (LPAS_Traverse_Route.csv)
[ ] 5. Insert LPAS_Relay_Station facility at 88S, 0E with 5m mast offset
[ ] 6. Insert DSN facilities: Goldstone, Madrid, Canberra
[ ] 7. Define sensors and transceivers on all objects
[ ] 8. Create Chain: Rover to Relay to DSN (3 chains, one per DSN station)
[ ] 9. Define Coverage object for PSR region
[ ] 10. Define Area Targets for PSR-A, PSR-B, PSR-C
[ ] 11. Configure FOM objects (Percent Coverage, Max Gap, Access Duration)
[ ] 12. Run propagation (Great Arc, 60-s step)
[ ] 13. Compute access reports for all link pairs
[ ] 14. Export reports to CSV: Rover-Relay, Relay-DSN, End-to-End
[ ] 15. Run Coverage analysis, export FOM grid as .csv
[ ] 16. Save scenario as LPAS_Mission_v1.sc
```

---

## 9. Expected Results Summary (Pre-Analysis Estimates)

| Metric | Estimate | Basis |
|---|---|---|
| Relay–DSN total coverage | ~88% of mission duration | 3-station DSN geometry |
| Rover–Relay LOS coverage | ~72% of traversed positions | LOLA terrain shadow analysis |
| Max blackout (Rover–Relay) | ~4.2 hours | Crater rim occultation |
| Max blackout (Relay–DSN) | ~1.8 hours | Earth rotation / geometry |
| End-to-end uptime | ~65% | Combined chain efficiency |
| Ka-band link margin (nom.) | 8.4 dB | Link budget (see analysis) |
| UHF link margin (500m range) | 14.7 dB | Link budget (see analysis) |

---

## 10. File References

| File | Description |
|---|---|
| `comm_windows_analysis.py` | Python simulation of communication windows |
| `link_budget_analysis.py` | RF link budget calculator |
| `coverage_analysis.md` | Coverage results and PSR site analysis |
| `LPAS_Traverse_Route.csv` | Rover waypoint route file |
| `stk_analysis/comm_windows/comm_windows_report.json` | Machine-readable comm window results |
