"""
LPAS NASA Data Ingestion Pipeline
Downloads and processes real NASA datasets for LPAS terrain analysis.

Data sources:
  - LOLA: Lunar Orbiter Laser Altimeter (LRO)
  - LROC: Lunar Reconnaissance Orbiter Camera
  - DIVINER: LRO Diviner Radiometer (thermal)

Usage:
    python ingest_nasa_data.py --target south_pole --radius_km 50
    python ingest_nasa_data.py --product lola_dem --lat -89.5 --lon 0.0
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("lpas.data_pipeline")

# NASA PDS archive base URLs (real endpoints)
PDS_BASE = "https://pds-geosciences.wustl.edu"
LOLA_BASE = f"{PDS_BASE}/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_rdr"
LROC_BASE = "https://pds-imaging.jpl.nasa.gov/data/lro/camera"

# LOLA South Pole gridded product
# LDEM_512 = 512 pixels/degree = 59m/pixel at equator, ~2m/pixel at 89°S
LOLA_SOUTH_POLE_URL = (
    "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/"
    "lrolol_1xxx/data/lola_rdr/cylindrical/img/"
    "ldem_512_south.img"
)
LOLA_SOUTH_POLE_LBL = (
    "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/"
    "lrolol_1xxx/data/lola_rdr/cylindrical/img/"
    "ldem_512_south.lbl"
)

OUTPUT_DIR = Path(__file__).parent.parent.parent / "terrain_data"


@dataclass
class LOLAProduct:
    """LOLA DEM product metadata."""
    name: str
    url: str
    label_url: str
    local_path: Path
    resolution_deg: float  # degrees per pixel
    coverage_lat_min: float
    coverage_lat_max: float
    description: str


@dataclass
class DownloadResult:
    success: bool
    product: str
    path: Optional[Path]
    size_bytes: int
    checksum_sha256: Optional[str]
    error: Optional[str] = None
    elapsed_s: float = 0.0


LOLA_PRODUCTS: dict[str, LOLAProduct] = {
    "ldem_512_south": LOLAProduct(
        name="LDEM_512_South",
        url=LOLA_SOUTH_POLE_URL,
        label_url=LOLA_SOUTH_POLE_LBL,
        local_path=OUTPUT_DIR / "lola_dem" / "ldem_512_south.img",
        resolution_deg=1.0 / 512.0,  # ~59m/pixel
        coverage_lat_min=-90.0,
        coverage_lat_max=-60.0,
        description="LOLA 512 pixels/degree DEM, southern hemisphere",
    ),
}


def download_with_retry(
    url: str,
    dest: Path,
    retries: int = 3,
    timeout_s: int = 60,
) -> DownloadResult:
    """Download a file with retry logic and progress reporting."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    t_start = time.monotonic()

    for attempt in range(1, retries + 1):
        try:
            log.info(f"Downloading (attempt {attempt}/{retries}): {url}")
            req = urllib.request.Request(url, headers={"User-Agent": "LPAS-DataPipeline/1.0"})
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                sha = hashlib.sha256()

                with open(dest, "wb") as f:
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
                        sha.update(chunk)
                        downloaded += len(chunk)
                        if total > 0 and downloaded % (1024 * 1024) == 0:
                            pct = 100 * downloaded / total
                            log.info(f"  {downloaded/1e6:.1f} MB / {total/1e6:.1f} MB ({pct:.0f}%)")

            elapsed = time.monotonic() - t_start
            log.info(f"Download complete: {dest} ({downloaded/1e6:.2f} MB in {elapsed:.1f}s)")
            return DownloadResult(
                success=True,
                product=url.split("/")[-1],
                path=dest,
                size_bytes=downloaded,
                checksum_sha256=sha.hexdigest(),
                elapsed_s=elapsed,
            )

        except urllib.error.HTTPError as e:
            log.warning(f"HTTP {e.code} for {url}: {e.reason}")
            if attempt == retries:
                return DownloadResult(
                    success=False, product=url, path=None, size_bytes=0,
                    checksum_sha256=None, error=f"HTTP {e.code}: {e.reason}",
                )
        except urllib.error.URLError as e:
            log.warning(f"URL error (attempt {attempt}): {e.reason}")
            if attempt < retries:
                wait = 2 ** attempt
                log.info(f"Retrying in {wait}s...")
                time.sleep(wait)
            else:
                return DownloadResult(
                    success=False, product=url, path=None, size_bytes=0,
                    checksum_sha256=None, error=str(e.reason),
                )
        except Exception as e:
            log.error(f"Unexpected error: {e}")
            return DownloadResult(
                success=False, product=url, path=None, size_bytes=0,
                checksum_sha256=None, error=str(e),
            )

    # Should not reach here
    return DownloadResult(
        success=False, product=url, path=None, size_bytes=0,
        checksum_sha256=None, error="Max retries exceeded",
    )


def parse_pds_label(label_path: Path) -> dict:
    """Parse PDS3 label file into key-value dict."""
    label = {}
    if not label_path.exists():
        return label

    with open(label_path, "r", encoding="latin-1") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("/*"):
                key, _, val = line.partition("=")
                label[key.strip()] = val.strip().strip('"')

    return label


def generate_synthetic_south_pole_dem(
    size: int = 512,
    lat_center: float = -89.5,
    lon_center: float = 0.0,
    extent_km: float = 50.0,
    seed: int = 0,
) -> tuple[np.ndarray, dict]:
    """
    Generate a synthetic lunar south pole DEM when NASA data is unavailable.
    Uses fractal terrain with realistic crater density and PSR geometry.

    Returns:
        dem_array: (size, size) float32 array in meters
        metadata: dict with georeferencing info
    """
    log.info(f"Generating synthetic DEM: {size}×{size}, centered at ({lat_center}°, {lon_center}°)")
    rng = np.random.default_rng(seed)

    # Base terrain: fractal brownian motion
    dem = np.zeros((size, size), dtype=np.float32)
    for octave in range(7):
        freq = 2 ** octave
        amplitude = 200.0 / freq  # base amplitude 200m, halving per octave
        nx = max(size // freq, 2)
        raw = rng.normal(0, amplitude, (nx, nx))
        from scipy.ndimage import zoom, gaussian_filter
        upsampled = zoom(raw, size / nx, order=3)[:size, :size]
        dem += upsampled

    # Shift so mean elevation ≈ 0
    dem -= dem.mean()

    # Add polar bowl: south pole is slightly elevated due to ancient impactors
    cy, cx = size / 2, size / 2
    y_idx, x_idx = np.ogrid[:size, :size]
    dist_from_center = np.sqrt((x_idx - cx) ** 2 + (y_idx - cy) ** 2)
    # Gentle elevation increase toward pole center
    dem += 50.0 * np.exp(-(dist_from_center ** 2) / (2 * (size * 0.3) ** 2))

    # Add craters (Shackleton-like + smaller craters)
    craters = [
        # (cy, cx, radius_px, depth_m) — representative south pole craters
        (size * 0.5,  size * 0.5,  size * 0.18, 4200),   # Shackleton-like: 21km diam, 4.2km deep
        (size * 0.35, size * 0.55, size * 0.08, 1800),   # Mid-size crater
        (size * 0.65, size * 0.40, size * 0.06, 1200),   # Medium crater
        (size * 0.45, size * 0.70, size * 0.04, 600),    # Small crater
        (size * 0.75, size * 0.55, size * 0.03, 400),    # Small crater
        (size * 0.30, size * 0.30, size * 0.05, 900),    # Small crater
    ]

    for (cr_y, cr_x, cr_r, cr_depth) in craters:
        dist_c = np.sqrt((x_idx - cr_x) ** 2 + (y_idx - cr_y) ** 2)
        # Rim: Gaussian ring at r = cr_r
        rim = np.exp(-((dist_c - cr_r) ** 2) / (2 * (cr_r * 0.12) ** 2))
        # Bowl: paraboloid inside crater
        bowl = np.where(dist_c < cr_r, (1 - (dist_c / cr_r) ** 2), 0.0)
        dem += rim * cr_depth * 0.12   # Rim raised
        dem -= bowl * cr_depth          # Interior lowered

    # Clip to realistic lunar south pole range
    dem = np.clip(dem, -5000, 3000)

    pixel_size_km = extent_km / size
    pixel_size_deg = pixel_size_km / 111.0  # Approximate km/deg at south pole

    metadata = {
        "source": "synthetic_fbm_with_craters",
        "size_px": size,
        "center_lat_deg": lat_center,
        "center_lon_deg": lon_center,
        "extent_km": extent_km,
        "pixel_size_km": pixel_size_km,
        "pixel_size_deg": pixel_size_deg,
        "elevation_min_m": float(dem.min()),
        "elevation_max_m": float(dem.max()),
        "elevation_mean_m": float(dem.mean()),
        "crs": "IAU2015:30100",  # Moon sphere, radius 1737.4 km
        "generation_seed": seed,
        "note": "Synthetic fallback — replace with real LOLA data for mission use",
    }

    log.info(
        f"Synthetic DEM generated: elevation range "
        f"[{metadata['elevation_min_m']:.0f}, {metadata['elevation_max_m']:.0f}] m"
    )
    return dem, metadata


def save_dem_geotiff(dem: np.ndarray, metadata: dict, output_path: Path) -> None:
    """Save DEM as GeoTIFF with georeferencing."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import rasterio
        from rasterio.transform import from_bounds
        from rasterio.crs import CRS

        lat_c = metadata["center_lat_deg"]
        lon_c = metadata["center_lon_deg"]
        ext_deg = metadata["extent_km"] / 111.0

        transform = from_bounds(
            lon_c - ext_deg / 2,
            lat_c - ext_deg / 2,
            lon_c + ext_deg / 2,
            lat_c + ext_deg / 2,
            dem.shape[1],
            dem.shape[0],
        )

        with rasterio.open(
            output_path,
            "w",
            driver="GTiff",
            height=dem.shape[0],
            width=dem.shape[1],
            count=1,
            dtype=dem.dtype,
            crs="EPSG:4326",  # Geographic, Moon sphere not supported in EPSG — note in metadata
            transform=transform,
            compress="lzw",
        ) as dst:
            dst.write(dem, 1)
            dst.update_tags(**{k: str(v) for k, v in metadata.items()})

        log.info(f"Saved GeoTIFF: {output_path} ({output_path.stat().st_size / 1e3:.1f} KB)")

    except ImportError:
        log.warning("rasterio not available — saving as numpy binary instead")
        np.save(output_path.with_suffix(".npy"), dem)
        with open(output_path.with_suffix(".json"), "w") as f:
            json.dump(metadata, f, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="LPAS NASA Data Ingestion Pipeline")
    parser.add_argument("--product", choices=list(LOLA_PRODUCTS.keys()) + ["synthetic"],
                        default="synthetic", help="Data product to download")
    parser.add_argument("--lat", type=float, default=-89.5, help="Center latitude (deg)")
    parser.add_argument("--lon", type=float, default=0.0, help="Center longitude (deg)")
    parser.add_argument("--radius_km", type=float, default=50.0, help="Coverage radius (km)")
    parser.add_argument("--output_dir", type=Path, default=OUTPUT_DIR / "lola_dem")
    parser.add_argument("--force_synthetic", action="store_true",
                        help="Generate synthetic DEM even if download succeeds")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    results = []

    if args.product == "synthetic" or args.force_synthetic:
        log.info("Generating synthetic south pole DEM")
        dem, metadata = generate_synthetic_south_pole_dem(
            size=512, lat_center=args.lat, lon_center=args.lon,
            extent_km=args.radius_km * 2,
        )
        out_tif = args.output_dir / "south_pole_dem.tif"
        save_dem_geotiff(dem, metadata, out_tif)
        meta_path = args.output_dir / "south_pole_dem_metadata.json"
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)
        log.info(f"Synthetic DEM saved: {out_tif}")

    else:
        product = LOLA_PRODUCTS[args.product]
        log.info(f"Downloading LOLA product: {product.name}")

        result = download_with_retry(product.url, product.local_path)
        results.append(asdict(result))

        if result.success:
            lbl_result = download_with_retry(product.label_url, product.local_path.with_suffix(".lbl"))
            results.append(asdict(lbl_result))
            label = parse_pds_label(product.local_path.with_suffix(".lbl"))
            log.info(f"PDS label parsed: {len(label)} fields")
        else:
            log.warning(f"Download failed: {result.error}")
            log.info("Falling back to synthetic DEM generation")
            dem, metadata = generate_synthetic_south_pole_dem(
                lat_center=args.lat, lon_center=args.lon, extent_km=args.radius_km * 2
            )
            save_dem_geotiff(dem, metadata, args.output_dir / "south_pole_dem.tif")

    # Save pipeline run report
    report = {
        "pipeline": "LPAS NASA Data Ingestion",
        "version": "1.0.0",
        "args": vars(args),
        "results": results,
        "output_dir": str(args.output_dir),
    }
    report_path = args.output_dir / "ingestion_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    log.info(f"Pipeline report: {report_path}")


if __name__ == "__main__":
    main()
