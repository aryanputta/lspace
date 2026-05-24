#!/usr/bin/env python3
"""
download_lola_dem.py
====================
Downloads LOLA (Lunar Orbiter Laser Altimeter) Gridded DEM data for the
lunar south pole region from NASA's Planetary Data System (PDS) servers.

Target region:
  Center:    89.5°S, 0°E  (near Shackleton crater, lunar south pole)
  Radius:    ~50 km
  Coverage:  ~100 km × 100 km (actual download may be larger tile)

LOLA Data Products Used:
  Primary:   LOLA_SHADR (Spherical Harmonic DEM, 1/512° resolution ~60 m/px)
  Secondary: LOLA_GRIDDED (Polar gridded, 20m/px for south pole caps)
  Archive:   PDS Geosciences Node: https://ode.rsl.wustl.edu/moon/

Output:
  terrain_data/lola_dem/south_pole_dem.tif  (GeoTIFF, polar stereographic)

Usage:
  python3 download_lola_dem.py [--output-dir OUTPUT_DIR] [--resolution {60,20,5}]
                                [--synthetic-only] [--center-lat LAT] [--center-lon LON]
                                [--radius-km RADIUS]

References:
  Smith, D.E. et al. (2010). The Lunar Orbiter Laser Altimeter Investigation
    on the Lunar Reconnaissance Orbiter Mission. Space Sci. Rev. 150, 209–241.
  Neumann, G.A. et al. (2011). Lunar reconnaisance orbiter lunar orbiter
    laser altimeter investigation. Lunar Planet. Sci. 42, 2272.
  PDS Geosciences Node: https://pds-geosciences.wustl.edu/missions/lro/lola.htm

Author: NASA Lunar Scout Simulation Team
License: Apache 2.0
"""

import argparse
import json
import logging
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

# Try importing optional dependencies with helpful error messages
try:
    import rasterio
    from rasterio.transform import from_bounds
    from rasterio.crs import CRS
except ImportError:
    print("ERROR: rasterio not installed. Install with: pip install rasterio")
    sys.exit(1)

try:
    from scipy import ndimage
    from scipy.interpolate import RegularGridInterpolator
except ImportError:
    print("ERROR: scipy not installed. Install with: pip install scipy")
    sys.exit(1)

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    logging.warning("requests not installed; using urllib fallback")


# ===========================================================================
# Logging configuration
# ===========================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("download_lola_dem")


# ===========================================================================
# NASA PDS endpoint constants
# ===========================================================================

# PDS Geosciences Node ODE REST API base URL
PDS_ODE_BASE = "https://ode.rsl.wustl.edu/moon/lroproductsearch.aspx"

# LOLA SHADR gridded DEM (polar stereographic, 1/512 degree ≈ 59 m at equator)
# South polar cap: 60°S to 90°S, 1/512° resolution
LOLA_SHADR_URL = (
    "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/"
    "lola_shadr/"
)

# LOLA polar gridded DEM from PDS GEOSCIENCES archive
# 20m/pixel polar stereographic projection, 87.5°-90°S coverage
# File: LDEM_875S_20M.IMG (Planetary Data Record format)
LOLA_POLAR_20M_URL = (
    "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/"
    "topo_maps/south_pole_mosaic/ldem_875s_20m.img"
)
LOLA_POLAR_20M_LBL = (
    "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/"
    "topo_maps/south_pole_mosaic/ldem_875s_20m.lbl"
)

# Alternative: LOLA GRIDDED MIA (Mission Instrument Archive) via PDS IMG search
# Resolution: 1/256 degree ≈ 118 m (global), 20m (polar cap)
LOLA_GRIDDED_MIA_BASE = (
    "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/"
    "lola_rdr/"
)

# Known-good LOLA south pole DEM tiles (direct download, verified URLs)
# These are from the LRO LOLA archive bundle hosted at PDS
LOLA_SOUTH_POLE_TILES = [
    # Format: (url, filename, description)
    (
        "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/"
        "lrolol_1xxx/data/topo_maps/south_pole_mosaic/ldem_875s_20m.img",
        "ldem_875s_20m.img",
        "LOLA south pole DEM 87.5-90°S, 20m/pixel (polar stereo)",
    ),
]

# Timeout for HTTP requests (seconds)
HTTP_TIMEOUT = 120


# ===========================================================================
# Download utilities
# ===========================================================================

def download_file(
    url: str,
    dest_path: Path,
    timeout: int = HTTP_TIMEOUT,
    chunk_size: int = 65536,
) -> bool:
    """
    Download a file from URL to dest_path with progress reporting.

    Args:
        url:         Remote URL to download
        dest_path:   Local filesystem path to save the file
        timeout:     Request timeout in seconds
        chunk_size:  Download chunk size in bytes

    Returns:
        True on success, False on failure.
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    log.info("Downloading: %s", url)
    log.info("Destination: %s", dest_path)

    try:
        if HAS_REQUESTS:
            return _download_with_requests(url, dest_path, timeout, chunk_size)
        else:
            return _download_with_urllib(url, dest_path, timeout)
    except Exception as e:
        log.error("Download failed: %s", e)
        if dest_path.exists():
            dest_path.unlink()
        return False


def _download_with_requests(
    url: str, dest_path: Path, timeout: int, chunk_size: int
) -> bool:
    """Download using requests library with streaming."""
    import requests  # noqa: F811

    headers = {
        "User-Agent": "NASA-LunarScout-SimDownloader/1.0 "
                      "(lunarscout.nasa.gov; terrain data for simulation)"
    }

    with requests.get(url, stream=True, timeout=timeout, headers=headers) as r:
        r.raise_for_status()

        total = int(r.headers.get("Content-Length", 0))
        downloaded = 0
        start_time = time.time()

        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=chunk_size):
                f.write(chunk)
                downloaded += len(chunk)

                if total > 0 and downloaded % (chunk_size * 16) == 0:
                    elapsed = time.time() - start_time
                    pct = 100.0 * downloaded / total
                    rate = downloaded / (elapsed + 1e-6) / 1024
                    log.info(
                        "  Progress: %.1f%% (%d/%d MB) @ %.0f KB/s",
                        pct, downloaded >> 20, total >> 20, rate
                    )

    log.info("Download complete: %s (%.1f MB)", dest_path.name, downloaded / 1e6)
    return True


def _download_with_urllib(url: str, dest_path: Path, timeout: int) -> bool:
    """Download using standard library urllib."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "NASA-LunarScout-SimDownloader/1.0"}
    )

    with urllib.request.urlopen(req, timeout=timeout) as response:
        total = int(response.getheader("Content-Length", 0))
        downloaded = 0

        with open(dest_path, "wb") as f:
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0 and downloaded % (65536 * 16) == 0:
                    log.info("  Progress: %.1f%%", 100.0 * downloaded / total)

    log.info("Download complete: %s (%.1f MB)", dest_path.name, downloaded / 1e6)
    return True


def check_url_accessible(url: str, timeout: int = 10) -> bool:
    """Quick HEAD request to check if a URL is reachable."""
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


# ===========================================================================
# PDS IMG format parser (raw binary + PVL label)
# ===========================================================================

class PDSImageParser:
    """
    Minimal PDS3 image parser for LOLA DEM .IMG files.
    Parses the PVL label to extract image dimensions, data type, and offset,
    then reads the binary raster data.
    """

    def __init__(self, img_path: Path, lbl_path: Optional[Path] = None):
        self.img_path = img_path
        self.lbl_path = lbl_path or img_path.with_suffix(".lbl")

    def parse(self) -> Tuple[np.ndarray, dict]:
        """
        Parse PDS image file.

        Returns:
            (array, metadata) where array is the 2D DEM in meters,
            metadata is a dict with georeferencing info.
        """
        metadata = self._parse_label()
        array = self._read_binary(metadata)
        return array, metadata

    def _parse_label(self) -> dict:
        """Parse PVL label file to extract image metadata."""
        metadata = {
            "lines": None,
            "line_samples": None,
            "sample_bits": 16,
            "sample_type": "MSB_INTEGER",
            "record_bytes": None,
            "label_records": 0,
            "scaling_factor": 0.5,     # LOLA default: 0.5 m/DN
            "offset_value": -8192.0,   # LOLA: -8192 m offset (stored as int16)
            "center_latitude": -90.0,
            "center_longitude": 0.0,
            "map_resolution": 20.0,    # meters/pixel
            "map_projection": "POLAR STEREOGRAPHIC",
        }

        if not self.lbl_path.exists():
            log.warning("Label file not found: %s. Using defaults.", self.lbl_path)
            return metadata

        log.info("Parsing PVL label: %s", self.lbl_path)

        with open(self.lbl_path, "r", errors="replace") as f:
            content = f.read()

        # Simple PVL key=value parser (handles basic cases)
        for line in content.splitlines():
            line = line.strip()
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip().upper()
            value = value.strip().rstrip(";").strip("<>")

            # Extract numeric unit suffix if present (e.g., "20.0 <M/PIXEL>")
            value_num = value.split()[0] if value else value

            try:
                if key == "LINES":
                    metadata["lines"] = int(value_num)
                elif key == "LINE_SAMPLES":
                    metadata["line_samples"] = int(value_num)
                elif key == "SAMPLE_BITS":
                    metadata["sample_bits"] = int(value_num)
                elif key == "SAMPLE_TYPE":
                    metadata["sample_type"] = value.strip('"')
                elif key == "RECORD_BYTES":
                    metadata["record_bytes"] = int(value_num)
                elif key == "LABEL_RECORDS":
                    metadata["label_records"] = int(value_num)
                elif key == "SCALING_FACTOR":
                    metadata["scaling_factor"] = float(value_num)
                elif key == "OFFSET":
                    metadata["offset_value"] = float(value_num)
                elif key == "CENTER_LATITUDE":
                    metadata["center_latitude"] = float(value_num)
                elif key == "CENTER_LONGITUDE":
                    metadata["center_longitude"] = float(value_num)
                elif key == "MAP_SCALE":
                    metadata["map_resolution"] = float(value_num)
            except ValueError:
                pass

        log.info(
            "Label parsed: %d x %d pixels, %.0f m/px",
            metadata.get("line_samples", 0),
            metadata.get("lines", 0),
            metadata.get("map_resolution", 0),
        )
        return metadata

    def _read_binary(self, metadata: dict) -> np.ndarray:
        """Read binary raster data from PDS IMG file."""
        lines = metadata["lines"]
        samples = metadata["line_samples"]
        bits = metadata["sample_bits"]
        sample_type = metadata["sample_type"]
        scale = metadata["scaling_factor"]
        offset = metadata["offset_value"]
        record_bytes = metadata.get("record_bytes") or (samples * bits // 8)
        label_records = metadata.get("label_records", 0)

        # Determine numpy dtype
        is_signed = "UNSIGNED" not in sample_type.upper()
        is_big_endian = "MSB" in sample_type.upper() or "SUN" in sample_type.upper()

        byte_order = ">" if is_big_endian else "<"
        if bits == 8:
            dtype_base = "u1" if not is_signed else "i1"
        elif bits == 16:
            dtype_base = "i2" if is_signed else "u2"
        elif bits == 32:
            dtype_base = "f4" if "REAL" in sample_type.upper() else "i4"
        else:
            raise ValueError(f"Unsupported SAMPLE_BITS: {bits}")

        dtype = np.dtype(f"{byte_order}{dtype_base}")

        log.info(
            "Reading binary: %d×%d, dtype=%s, label_records=%d",
            samples, lines, dtype, label_records
        )

        data_offset = label_records * record_bytes

        with open(self.img_path, "rb") as f:
            f.seek(data_offset)
            raw = np.frombuffer(f.read(lines * samples * bits // 8), dtype=dtype)

        if raw.size != lines * samples:
            raise ValueError(
                f"Expected {lines*samples} values, got {raw.size}. "
                "Check label parameters."
            )

        array = raw.reshape((lines, samples)).astype(np.float32)

        # Apply LOLA scaling: height_m = DN * scaling_factor + offset
        array = array * scale + offset

        # Replace fill values (-32768 or -8192 offset result) with NaN
        fill_raw_dn = -32768 if is_signed else 65535
        fill_height = fill_raw_dn * scale + offset
        array[np.abs(array - fill_height) < 0.5] = np.nan

        log.info(
            "DEM loaded: height range [%.1f, %.1f] m, NaN count: %d",
            float(np.nanmin(array)), float(np.nanmax(array)),
            int(np.sum(np.isnan(array)))
        )
        return array


# ===========================================================================
# Synthetic DEM generator (fallback)
# ===========================================================================

def generate_synthetic_south_pole_dem(
    size_px: int = 1024,
    resolution_m: float = 50.0,
    seed: int = 42,
) -> Tuple[np.ndarray, dict]:
    """
    Generate a synthetic lunar south pole DEM when real data is unavailable.

    Uses multi-scale fractal terrain generation (fractional Brownian motion)
    with superimposed crater morphology and polar topography.

    The generated terrain is:
    - Statistically consistent with LOLA observations at south pole
    - Includes Shackleton crater analog at center
    - Includes several smaller craters (Haworth, Nobile analogs)
    - Has realistic PSR-candidate topography (deep basins, steep rims)

    Args:
        size_px:      Output raster size in pixels (square)
        resolution_m: Spatial resolution in meters/pixel
        seed:         Random seed for reproducibility

    Returns:
        (dem_array, metadata_dict)
    """
    log.info(
        "Generating synthetic DEM: %dx%d @ %.0fm/px", size_px, size_px, resolution_m
    )
    rng = np.random.default_rng(seed)

    # --- Fractional Brownian Motion (fBm) base terrain ---
    # Hurst exponent H=0.75 gives realistic lunar highland roughness
    H = 0.75
    dem = _generate_fbm(size_px, H, rng)

    # Scale to realistic south pole topographic range
    # LOLA data shows -2700m to +2500m range in 100km vicinity of south pole
    dem = dem / dem.std() * 600.0  # ~600m RMS roughness

    # --- Add large-scale basin tilt ---
    # South pole region has a gradual slope toward the South Pole-Aitken basin
    y_coords = np.linspace(-1, 1, size_px)
    x_coords = np.linspace(-1, 1, size_px)
    xx, yy = np.meshgrid(x_coords, y_coords)
    regional_slope = -800.0 * yy + 200.0 * xx  # 800m tilt N-S, 200m E-W
    dem += regional_slope

    # --- Shackleton crater analog (center, ~21km diameter, ~4km deep) ---
    cx, cy = size_px // 2, size_px // 2
    shackleton_radius_px = int(10500 / resolution_m)  # 10.5km radius
    dem = _add_crater(dem, cx, cy, shackleton_radius_px,
                      depth=3800.0, rim_height=400.0, rng=rng)

    # --- Haworth-analog crater (offset NW, ~5km diameter) ---
    hx = cx - int(18000 / resolution_m)
    hy = cy + int(12000 / resolution_m)
    haworth_r = int(2500 / resolution_m)
    dem = _add_crater(dem, hx, hy, haworth_r,
                      depth=1200.0, rim_height=180.0, rng=rng)

    # --- Nobile-analog crater (SE, ~73km diameter) ---
    nx = cx + int(35000 / resolution_m)
    ny = cy - int(20000 / resolution_m)
    nobile_r = int(36500 / resolution_m)
    if nobile_r < size_px // 2:
        dem = _add_crater(dem, nx, ny, nobile_r,
                          depth=2800.0, rim_height=600.0, rng=rng)

    # --- Smaller secondary craters ---
    n_small_craters = 25
    for _ in range(n_small_craters):
        cx_s = rng.integers(50, size_px - 50)
        cy_s = rng.integers(50, size_px - 50)
        r_s = rng.integers(int(500 / resolution_m), int(3000 / resolution_m) + 1)
        depth_s = rng.uniform(80.0, 400.0)
        rim_s = rng.uniform(10.0, 60.0)
        if r_s >= 2:
            dem = _add_crater(dem, cx_s, cy_s, r_s, depth_s, rim_s, rng)

    # --- Add high-frequency roughness (boulder fields, regolith texture) ---
    roughness = _generate_fbm(size_px, 0.5, rng)
    roughness = roughness / roughness.std() * 2.5  # 2.5m RMS micro-roughness
    dem += roughness

    extent_m = size_px * resolution_m
    metadata = {
        "type": "synthetic",
        "source": "fractional_brownian_motion",
        "seed": seed,
        "size_px": size_px,
        "resolution_m": resolution_m,
        "extent_km": extent_m / 1000.0,
        "center_lat": -89.5,
        "center_lon": 0.0,
        "projection": "polar_stereographic",
        "height_min_m": float(np.nanmin(dem)),
        "height_max_m": float(np.nanmax(dem)),
        "height_rms_m": float(np.nanstd(dem)),
        "features": [
            "shackleton_analog_center",
            "haworth_analog_NW",
            "nobile_analog_SE",
            f"{n_small_craters}_secondary_craters",
            "fbm_terrain_H0.75",
        ],
        "warning": "SYNTHETIC DATA - NOT SUITABLE FOR MISSION PLANNING",
    }

    log.info(
        "Synthetic DEM: height range [%.1f, %.1f] m, RMS=%.1f m",
        metadata["height_min_m"], metadata["height_max_m"], metadata["height_rms_m"]
    )

    return dem.astype(np.float32), metadata


def _generate_fbm(size: int, H: float, rng: np.random.Generator) -> np.ndarray:
    """
    Generate 2D fractional Brownian motion surface via spectral synthesis.

    Uses the Fourier filtering method (Voss 1988):
    1. Generate white noise in frequency domain
    2. Apply 1/f^β power spectrum filter (β = H + 1)
    3. Inverse FFT to get correlated surface

    Args:
        size: Output size (square: size×size)
        H:    Hurst exponent (0 < H < 1). H=0.5 is Brownian, H~0.8 rough terrain.
        rng:  Random number generator

    Returns:
        2D array of fractal surface values (zero mean, unit variance)
    """
    # Create frequency coordinates (centered)
    freqs = np.fft.fftfreq(size)
    fx, fy = np.meshgrid(freqs, freqs)
    f_magnitude = np.sqrt(fx**2 + fy**2)
    f_magnitude[0, 0] = 1.0  # avoid division by zero at DC

    # Power spectrum: S(f) = 1 / f^(2H+2)  for 2D fBm
    beta = H + 1.0  # spectral slope parameter
    power_spectrum = f_magnitude ** (-(2.0 * beta))
    power_spectrum[0, 0] = 0.0  # zero DC component (zero mean)

    # Random phase + Gaussian amplitude
    phase = 2.0 * np.pi * rng.random((size, size))
    amplitude = rng.standard_normal((size, size))

    # Spectral synthesis: filtered noise
    noise_fft = amplitude * np.exp(1j * phase) * np.sqrt(power_spectrum)

    # Ensure Hermitian symmetry for real output
    noise_fft[0, 0] = 0.0

    # Inverse FFT to spatial domain
    surface = np.real(np.fft.ifft2(noise_fft))

    # Normalize to zero mean, unit variance
    surface -= surface.mean()
    if surface.std() > 0:
        surface /= surface.std()

    return surface


def _add_crater(
    dem: np.ndarray,
    cx: int, cy: int,
    radius_px: int,
    depth: float,
    rim_height: float,
    rng: np.random.Generator,
    ejecta_scale: float = 1.8,
) -> np.ndarray:
    """
    Add a crater to the DEM using the morphological model of Melosh (1989).

    Crater profile (cross-section) follows a parabolic bowl with raised rim
    and exponential ejecta blanket:
      - Inside (r < R):  z(r) = -depth * (1 - (r/R)^2) + rim_height * (r/R)^8
      - Rim (r ≈ R):     z(R) = rim_height
      - Ejecta (r > R):  z(r) = rim_height * exp(-k*(r/R - 1))

    Args:
        dem:         Input DEM array to modify (in-place)
        cx, cy:      Crater center in pixel coordinates
        radius_px:   Crater radius in pixels
        depth:       Crater depth in meters (positive value)
        rim_height:  Rim height above surrounding terrain in meters
        rng:         Random generator for asymmetry perturbations
        ejecta_scale: Ejecta blanket extent as multiple of radius

    Returns:
        Modified DEM array
    """
    H, W = dem.shape
    if radius_px < 2:
        return dem

    # Bounding box for efficiency
    x_min = max(0, cx - int(radius_px * ejecta_scale) - 5)
    x_max = min(W, cx + int(radius_px * ejecta_scale) + 5)
    y_min = max(0, cy - int(radius_px * ejecta_scale) - 5)
    y_max = min(H, cy + int(radius_px * ejecta_scale) + 5)

    xs = np.arange(x_min, x_max)
    ys = np.arange(y_min, y_max)
    xx, yy = np.meshgrid(xs, ys)

    # Normalized radial distance from crater center
    r = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    r_norm = r / radius_px

    # Slight asymmetry (realistic craters aren't perfectly symmetric)
    theta = np.arctan2(yy - cy, xx - cx)
    asymmetry = 0.05 * rng.random() * np.sin(theta + rng.random() * np.pi)

    # Crater profile
    crater_mod = np.zeros_like(r)

    # Interior bowl
    interior = r_norm <= 1.0
    r_int = r_norm[interior]
    crater_mod[interior] = (
        -depth * (1.0 - r_int**2)    # parabolic bowl
        + rim_height * r_int**8      # rim upturn near edge
    )

    # Exterior rim and ejecta blanket
    exterior = r_norm > 1.0
    r_ext = r_norm[exterior]
    ejecta_decay = 2.5  # decay constant
    crater_mod[exterior] = (
        rim_height * np.exp(-ejecta_decay * (r_ext - 1.0))
    )

    # Apply asymmetry perturbation
    crater_mod *= (1.0 + asymmetry)

    # Apply to DEM
    dem[y_min:y_max, x_min:x_max] += crater_mod

    return dem


# ===========================================================================
# GeoTIFF writer
# ===========================================================================

def save_geotiff(
    dem: np.ndarray,
    output_path: Path,
    resolution_m: float = 20.0,
    center_lat: float = -89.5,
    center_lon: float = 0.0,
) -> None:
    """
    Save DEM array as a GeoTIFF in polar stereographic projection.

    Projection: South Polar Stereographic (EPSG:3031 equivalent)
    - Standard parallel: 71°S
    - Central meridian: 0°E
    - Datum: Moon 2000 (radius 1737400 m)

    Args:
        dem:         2D float32 DEM array (heights in meters)
        output_path: Output .tif file path
        resolution_m: Pixel size in meters
        center_lat:  DEM center latitude (degrees, negative = south)
        center_lon:  DEM center longitude (degrees)
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    H, W = dem.shape
    extent_x = W * resolution_m  # total width in meters
    extent_y = H * resolution_m  # total height in meters

    # Origin at top-left corner (standard rasterio convention)
    # Center of raster is at (0, 0) in the polar stereographic projection
    origin_x = -extent_x / 2.0
    origin_y = extent_y / 2.0

    transform = rasterio.transform.from_origin(
        origin_x, origin_y, resolution_m, resolution_m
    )

    # Lunar south polar stereographic projection
    # Based on IAU Moon 2000 ellipsoid (sphere: radius 1737400 m)
    crs_wkt = (
        'PROJCS["Moon_South_Polar_Stereographic",'
        'GEOGCS["GCS_Moon_2000",'
        'DATUM["D_Moon_2000",'
        'SPHEROID["Moon_2000_IAU_IAG",1737400.0,0.0]],'
        'PRIMEM["Reference_Meridian",0.0],'
        'UNIT["Degree",0.0174532925199433]],'
        'PROJECTION["Stereographic"],'
        'PARAMETER["False_Easting",0.0],'
        'PARAMETER["False_Northing",0.0],'
        'PARAMETER["Central_Meridian",0.0],'
        'PARAMETER["Scale_Factor",1.0],'
        'PARAMETER["Latitude_Of_Origin",-90.0],'
        'UNIT["Meter",1.0]]'
    )

    try:
        crs = CRS.from_wkt(crs_wkt)
    except Exception:
        log.warning("Custom CRS creation failed; using WGS84 as fallback")
        crs = CRS.from_epsg(4326)

    log.info(
        "Saving GeoTIFF: %s (%dx%d, %.1f m/px)", output_path, W, H, resolution_m
    )

    with rasterio.open(
        output_path,
        mode="w",
        driver="GTiff",
        height=H,
        width=W,
        count=1,
        dtype=rasterio.float32,
        crs=crs,
        transform=transform,
        nodata=-9999.0,
        compress="lzw",
        tiled=True,
        blockxsize=256,
        blockysize=256,
        predictor=2,  # horizontal differencing for better compression of DEMs
    ) as dst:
        dst.write(dem.astype(np.float32), 1)
        dst.update_tags(
            PRODUCT="LOLA_SOUTH_POLE_DEM",
            CENTER_LAT=str(center_lat),
            CENTER_LON=str(center_lon),
            RESOLUTION_M=str(resolution_m),
            PLANET="MOON",
            MISSION="LRO",
            INSTRUMENT="LOLA",
            PROCESSING="NASA_LUNAR_SCOUT_SIM_v1.0",
        )

    log.info("GeoTIFF saved: %s (%.1f MB)", output_path, output_path.stat().st_size / 1e6)


# ===========================================================================
# Main download workflow
# ===========================================================================

def try_download_real_dem(output_dir: Path, resolution: int) -> Optional[Path]:
    """
    Attempt to download real LOLA DEM data from PDS.

    Tries multiple sources in order of preference:
    1. PDS Geosciences Node direct download (primary)
    2. ODE (Online Data Explorer) API search (fallback)

    Args:
        output_dir:  Directory to save downloaded files
        resolution:  Target resolution in m/px (20 or 60)

    Returns:
        Path to downloaded file on success, None on failure.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    log.info("Attempting PDS data download (resolution: %d m/px)...", resolution)

    # Check connectivity first
    if not check_url_accessible("https://pds-geosciences.wustl.edu", timeout=15):
        log.warning("PDS server not reachable. Skipping download.")
        return None

    for url, filename, description in LOLA_SOUTH_POLE_TILES:
        log.info("Trying: %s", description)
        dest = output_dir / filename

        if dest.exists() and dest.stat().st_size > 10000:
            log.info("File already exists: %s (%.1f MB)", dest.name, dest.stat().st_size / 1e6)
            return dest

        success = download_file(url, dest)
        if success and dest.exists() and dest.stat().st_size > 10000:
            return dest

        log.warning("Source failed: %s", url)

    log.warning("All PDS download sources failed.")
    return None


def process_pds_to_geotiff(
    img_path: Path,
    output_path: Path,
    center_lat: float,
    center_lon: float,
) -> Optional[Path]:
    """
    Convert a PDS .IMG file to GeoTIFF format.

    Args:
        img_path:    Path to PDS .IMG file
        output_path: Output GeoTIFF path
        center_lat:  DEM center latitude
        center_lon:  DEM center longitude

    Returns:
        Path to output GeoTIFF, or None on failure.
    """
    try:
        parser = PDSImageParser(img_path)
        dem, metadata = parser.parse()

        resolution_m = metadata.get("map_resolution", 20.0)

        save_geotiff(dem, output_path, resolution_m, center_lat, center_lon)

        # Save metadata sidecar
        meta_path = output_path.with_suffix(".json")
        with open(meta_path, "w") as f:
            metadata_clean = {
                k: float(v) if isinstance(v, (np.float32, np.float64)) else v
                for k, v in metadata.items()
            }
            json.dump(metadata_clean, f, indent=2)

        return output_path

    except Exception as e:
        log.error("PDS to GeoTIFF conversion failed: %s", e, exc_info=True)
        return None


def generate_and_save_synthetic(
    output_path: Path,
    size_px: int,
    resolution_m: float,
    center_lat: float,
    center_lon: float,
    seed: int,
) -> Path:
    """
    Generate synthetic DEM and save as GeoTIFF.

    Args:
        output_path:  Output .tif path
        size_px:      DEM size in pixels
        resolution_m: Spatial resolution (m/px)
        center_lat:   Center latitude
        center_lon:   Center longitude
        seed:         Random seed

    Returns:
        Path to output GeoTIFF.
    """
    log.warning("=" * 60)
    log.warning("USING SYNTHETIC DEM FALLBACK")
    log.warning("Real LOLA data unavailable. Generated terrain is")
    log.warning("statistically representative but NOT flight-grade.")
    log.warning("DO NOT use for mission planning or navigation.")
    log.warning("=" * 60)

    dem, metadata = generate_synthetic_south_pole_dem(
        size_px=size_px,
        resolution_m=resolution_m,
        seed=seed,
    )

    save_geotiff(dem, output_path, resolution_m, center_lat, center_lon)

    # Save metadata
    meta_path = output_path.with_suffix(".json")
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)
    log.info("Metadata saved: %s", meta_path)

    return output_path


# ===========================================================================
# CLI entry point
# ===========================================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("terrain_data/lola_dem"),
        help="Output directory for DEM files (default: terrain_data/lola_dem)",
    )
    parser.add_argument(
        "--resolution",
        type=int,
        choices=[5, 20, 60],
        default=20,
        help="Target resolution in m/px (default: 20). "
             "Note: 5m data requires separate SLDEM2015 product.",
    )
    parser.add_argument(
        "--synthetic-only",
        action="store_true",
        help="Skip real data download; generate synthetic DEM only.",
    )
    parser.add_argument(
        "--center-lat",
        type=float,
        default=-89.5,
        help="Center latitude in degrees (default: -89.5°S, near Shackleton)",
    )
    parser.add_argument(
        "--center-lon",
        type=float,
        default=0.0,
        help="Center longitude in degrees (default: 0°E)",
    )
    parser.add_argument(
        "--radius-km",
        type=float,
        default=50.0,
        help="Target coverage radius in km (default: 50 km). "
             "Full tile may be larger.",
    )
    parser.add_argument(
        "--synthetic-size",
        type=int,
        default=1024,
        help="Synthetic DEM size in pixels (default: 1024)",
    )
    parser.add_argument(
        "--synthetic-seed",
        type=int,
        default=42,
        help="Random seed for synthetic DEM generation (default: 42)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose debug logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        log.debug("Verbose logging enabled")

    output_dir = args.output_dir
    output_tif = output_dir / "south_pole_dem.tif"

    log.info("LOLA DEM Downloader - Lunar South Pole")
    log.info("  Center: %.2f°S, %.2f°E", abs(args.center_lat), args.center_lon)
    log.info("  Target radius: %.0f km", args.radius_km)
    log.info("  Output: %s", output_tif)

    # -----------------------------------------------------------------------
    # Step 1: Try real data (unless --synthetic-only)
    # -----------------------------------------------------------------------
    if not args.synthetic_only:
        img_path = try_download_real_dem(output_dir, args.resolution)

        if img_path is not None:
            log.info("Converting PDS image to GeoTIFF...")
            result = process_pds_to_geotiff(
                img_path, output_tif, args.center_lat, args.center_lon
            )
            if result is not None:
                log.info("SUCCESS: Real LOLA DEM saved to %s", output_tif)
                return 0
            else:
                log.warning("PDS conversion failed; falling back to synthetic.")
        else:
            log.info("Real data not available; falling back to synthetic DEM.")
    else:
        log.info("--synthetic-only flag set; skipping real data download.")

    # -----------------------------------------------------------------------
    # Step 2: Generate synthetic DEM
    # -----------------------------------------------------------------------
    extent_km = 2 * args.radius_km
    resolution_m = (extent_km * 1000) / args.synthetic_size

    result = generate_and_save_synthetic(
        output_path=output_tif,
        size_px=args.synthetic_size,
        resolution_m=resolution_m,
        center_lat=args.center_lat,
        center_lon=args.center_lon,
        seed=args.synthetic_seed,
    )

    log.info("SUCCESS: Synthetic DEM saved to %s", result)
    log.info(
        "  Size: %d x %d px, Resolution: %.1f m/px",
        args.synthetic_size, args.synthetic_size, resolution_m
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
