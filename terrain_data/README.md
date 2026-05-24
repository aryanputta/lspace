# LPAS Terrain Data — Lunar South Pole

**Project:** Lunar PSR Autonomy Scout (LPAS)
**Data Region:** Lunar south pole, 88°S–90°S
**Primary Reference Site:** Shackleton crater, 89.9°S, 0°E

---

## 1. Data Sources

### 1.1 LOLA DEM (Lunar Orbiter Laser Altimeter)

| Parameter | Value |
|---|---|
| Instrument | LOLA aboard Lunar Reconnaissance Orbiter (LRO) |
| PDS Archive | https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/ |
| Data product | LOLA RDR gridded DEM, PDS label format |
| Horizontal resolution | 30 m/pixel (at equator; ~28 m/pixel at 89°S due to projection) |
| Vertical accuracy | ±1 m radial (±0.1 m vertical relative) |
| Coordinate system | IAU Moon 2000 (NAIF body code 301), spheroid a=1737400 m, f=0 |
| Datum | Mean lunar radius 1737.4 km |
| Projection (south pole product) | Polar stereographic, true-scale latitude 90°S, standard parallel 89°S |
| Horizontal datum | Selenographic coordinates (LRO laser ranging, 1-sigma 10 m absolute) |
| Elevation encoding | IEEE 32-bit float, meters above mean lunar radius |
| PDS data set ID | LRO-L-LOLA-3-RDR-V1.0 |
| Applicable PDS volume | LROLOL_1001–LROLOL_1007 |
| Recommended file | LDEM_87S_90S_60MPP_SLP.IMG (slope) / LDEM_87S_90S_60MPP.IMG (elevation) |

### 1.2 LROC NAC Imagery (Lunar Reconnaissance Orbiter Camera — Narrow Angle Camera)

| Parameter | Value |
|---|---|
| Instrument | LROC NAC (two cameras: NAC-L, NAC-R) |
| PDS Archive | https://pds-imaging.jpl.nasa.gov/volumes/lro.html |
| Data set ID | LRO-L-LROC-2-EDR-V1.0 |
| Ground sampling distance | ~0.5 m/pixel at 50 km orbital altitude |
| Imaging mode | Panchromatic (400–760 nm bandpass) |
| Pixel format | 12-bit DN, delivered as 8-bit scaled or 16-bit TIFF |
| Swath width | ~2.5 km per NAC strip at 50 km altitude |
| Shackleton coverage | Multiple NAC strips available: M1187148736LE, M1166945717LE (confirm via LROC QuickMap) |
| Geometric correction | SPICE-corrected, registered to LOLA DEM horizontal datum |
| Photometric normalization | Hapke photometric model, incidence angle corrected |

### 1.3 JMARS (Java Mission-planning and Analysis for Remote Sensing)

| Parameter | Value |
|---|---|
| Provider | Arizona State University |
| URL | https://jmars.asu.edu/ |
| Access | Requires free account registration |
| Relevant layers | LOLA DEM color-hillshade, LROC WAC mosaic, PSR mask (Hayne et al. 2015), DIVINER bolometric temperature |
| Export format | GeoTIFF (WGS84 or stereographic), PNG, FITS |
| Use case | Visual inspection, PSR boundary reference, slope context |

---

## 2. Shackleton Crater Reference Parameters

| Parameter | Value | Source |
|---|---|---|
| Center latitude | 89.9°S | USGS Gazetteer of Planetary Nomenclature |
| Center longitude | 0.0°E | USGS Gazetteer of Planetary Nomenclature |
| Rim-to-rim diameter | 21.0 km | LOLA DEM measurement |
| Crater depth (rim to floor) | 4.0 km | Zuber et al. 2012, Science 339 |
| Rim elevation above datum | +2850 m | LOLA DEM |
| Floor elevation | −1150 m | LOLA DEM |
| PSR fraction of floor | ~95% | Hayne et al. 2015, JGR Planets |
| Estimated floor temperature | 43–93 K | Paige et al. 2010, Science 330 |
| Confirmed water ice evidence | Yes (M3 spectral, LCROSS plume) | Colaprete et al. 2010, Science 330 |
| LPAS primary landing ellipse center | 89.85°S, 0.0°E | Mission design baseline |
| Landing ellipse semi-major axis | 5.0 km | 3-sigma, 99.7% landing probability |

---

## 3. Data Download Procedures

### 3.1 LOLA DEM Download Script

```bash
# Download LOLA 30 m/px south pole DEM from NASA PDS
# Requires wget or curl; no authentication needed

PDS_BASE="https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/ldem_87s"

# Elevation grid (30 m/px, 88-90 deg S band)
wget -P terrain_data/lola_dem/ \
  "${PDS_BASE}/ldem_87s_30mpp.img" \
  "${PDS_BASE}/ldem_87s_30mpp.lbl"

# Slope grid
wget -P terrain_data/lola_dem/ \
  "${PDS_BASE}/ldem_87s_30mpp_slp.img" \
  "${PDS_BASE}/ldem_87s_30mpp_slp.lbl"

# Convert PDS IMG to GeoTIFF using GDAL (requires gdal >= 3.4)
gdal_translate \
  -of GTiff \
  -a_srs '+proj=stere +lat_0=-90 +lon_0=0 +k=1 +x_0=0 +y_0=0 +a=1737400 +b=1737400 +units=m +no_defs' \
  terrain_data/lola_dem/ldem_87s_30mpp.img \
  terrain_data/lola_dem/ldem_87s_30mpp.tif
```

### 3.2 JMARS Interface Procedure

1. Log into https://jmars.asu.edu with your ASU/NASA credentials.
2. Open the "Moon" body context.
3. Navigate to Layer Manager > Add Layer > LOLA DEM (Color-Hillshade).
4. Add PSR mask layer: Layer Manager > Add Layer > PSR (Hayne 2015).
5. Zoom to 89.9°S, 0°E.
6. Export region: File > Export View > GeoTIFF, 30 m/px, polar stereographic.
7. Place exported file in `terrain_data/lola_dem/jmars_export.tif`.

### 3.3 LROC NAC Download

Use the LROC QuickMap at https://quickmap.lroc.asu.edu to identify NAC strip IDs covering the landing ellipse, then download from the PDS via:

```bash
# Example for one NAC strip
wget "https://pds-imaging.jpl.nasa.gov/data/lro/camera/data/2023/M1187148736LE.IMG" \
  -P terrain_data/lroc_imagery/
```

---

## 4. Processed Data Products

All processed products are generated by the pipeline scripts in `scripts/terrain_processing/` and written to `terrain_data/processed/`.

| Filename | Description | Resolution | Format | Script |
|---|---|---|---|---|
| `slope_map.png` | Terrain slope in degrees, 0–45° range | 30 m/px | 8-bit PNG, colormap viridis | `process_dem_to_gazebo.py` |
| `roughness_map.png` | RMS height deviation in 3×3 window (m) | 30 m/px | 8-bit PNG, 0–0.5 m range | `process_dem_to_gazebo.py` |
| `psr_mask.png` | Binary PSR mask: 255 = PSR, 0 = illuminated | 30 m/px | 8-bit PNG | `generate_illumination_map.py` |
| `traversability_map.png` | Composite score 0–1 (1 = fully traversable) | 30 m/px | 8-bit PNG | `process_dem_to_gazebo.py` |
| `illumination_fraction.png` | Mean annual illumination fraction 0–1 | 30 m/px | 8-bit PNG, 16-bit TIFF | `generate_illumination_map.py` |
| `psr_definitive_mask.png` | Definitive PSR mask from ray-tracing (72 positions) | 30 m/px | 8-bit PNG | `generate_illumination_map.py` |
| `heightmap_gazebo_16bit.png` | Gazebo-compatible heightmap, elevation encoded | 129×129 px | 16-bit PNG | `process_dem_to_gazebo.py` |
| `illumination_metadata.json` | Statistics: psr_fraction, mean_illumination, etc. | N/A | JSON | `generate_illumination_map.py` |

---

## 5. Coordinate Reference System

All LPAS terrain data products use the following CRS unless noted otherwise:

```
PROJCS["Moon_South_Pole_Stereographic",
    GEOGCS["GCS_Moon_2000",
        DATUM["D_Moon_2000",
            SPHEROID["Moon_2000_IAU_IAG",1737400.0,0.0]],
        PRIMEM["Reference_Meridian",0.0],
        UNIT["Degree",0.0174532925199433]],
    PROJECTION["Stereographic"],
    PARAMETER["False_Easting",0.0],
    PARAMETER["False_Northing",0.0],
    PARAMETER["Central_Meridian",0.0],
    PARAMETER["Scale_Factor",1.0],
    PARAMETER["Latitude_Of_Origin",-90.0],
    UNIT["Meter",1.0]]
```

EPSG equivalent: IAU 30135 (Moon 2015 — South Pole Stereographic). Use `+proj=stere +lat_0=-90 +lon_0=0 +a=1737400 +b=1737400 +units=m` in PROJ/GDAL.

**Origin (0, 0 in map coordinates):** South pole, 89.9°S 0°E maps to approximately (0, 1850) m in stereographic projection.

---

## 6. Gazebo Heightmap File Format Specifications

The Gazebo physics simulator requires heightmaps in a specific format for the `DEM` terrain plugin:

| Parameter | Specification |
|---|---|
| File format | 16-bit grayscale PNG |
| Dimensions | Must be 2^n + 1 pixels square (e.g., 129×129, 257×257, 513×513) |
| Recommended size | 129×129 (covers ~3.8 km × 3.8 km at 30 m/px) |
| Elevation encoding | Linear map: pixel value 0 = min elevation, 65535 = max elevation |
| Min elevation stored | Stored in `illumination_metadata.json` key `dem_min_m` |
| Max elevation stored | Stored in `illumination_metadata.json` key `dem_max_m` |
| SDF reference | `<uri>file://terrain_data/processed/heightmap_gazebo_16bit.png</uri>` |
| SDF size element | `<size>3870 3870 2000</size>` (X Y Z in meters, Z = max_m - min_m) |
| Byte order | Big-endian (PNG standard) |
| Color space | Grayscale, no alpha channel |

**Usage in Gazebo SDF:**
```xml
<heightmap>
  <uri>model://lpas_terrain/materials/textures/heightmap_gazebo_16bit.png</uri>
  <size>3870 3870 2000</size>
  <pos>0 0 -1150</pos>
  <texture>
    <diffuse>model://lpas_terrain/materials/textures/lunar_surface.png</diffuse>
    <normal>model://lpas_terrain/materials/textures/flat_normal.png</normal>
    <size>10</size>
  </texture>
</heightmap>
```

---

## 7. Directory Structure

```
terrain_data/
├── README.md                          # This file
├── lola_dem/                          # Raw LOLA DEM files (PDS format)
│   ├── ldem_87s_30mpp.img             # Elevation grid PDS image
│   ├── ldem_87s_30mpp.lbl             # PDS label file
│   └── ldem_87s_30mpp.tif             # GDAL-converted GeoTIFF
├── lroc_imagery/                      # Raw LROC NAC strips (PDS format)
│   └── M1187148736LE.IMG              # Example NAC strip
├── lroc_nac/                          # LROC NAC processed tiles
├── illumination_maps/                 # Illumination fraction products
│   ├── illumination_fraction.png
│   └── psr_definitive_mask.png
├── slope_maps/                        # Slope and roughness products
│   ├── slope_map.png
│   └── roughness_map.png
└── processed/                         # Pipeline-ready products
    ├── traversability_map.png
    ├── psr_mask.png
    ├── heightmap_gazebo_16bit.png
    └── illumination_metadata.json
```

## 8. PSR Statistics (Shackleton Rim Area)

Based on LOLA DEM and ray-traced illumination model (`generate_illumination_map.py`, 72 sun positions):

| Metric | Value |
|---|---|
| Total area covered (DEM tile) | ~655 km² |
| PSR fraction (ray-traced) | ~8.2% |
| Mean slope (overall) | 6.3° |
| Max slope (crater wall interior) | 38.7° |
| Traversable fraction (slope < 15°) | ~68% |
| Expected water ice regions | PSR craters > 5 km diameter, floor T < 110 K |
| Shackleton floor temperature (DIVINER) | 43–93 K |

## 9. Data License

LOLA DEM: NASA Open Data, public domain (NASA Open Source Agreement)
LROC imagery: NASA Open Data, public domain
Processed derivatives: MIT License (this project)
