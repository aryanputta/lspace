"""
LPAS DEM → Gazebo Heightmap Processor

Converts LOLA GeoTIFF DEM to Gazebo-compatible heightmap PNG
and generates derived products: slope map, roughness index, PSR mask.

Usage:
  python process_dem_to_gazebo.py \
    --input terrain_data/lola_dem/south_pole_dem.tif \
    --output_size 512 \
    --terrain_scale 50.0
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

log = logging.getLogger("lpas.terrain")

PROJECT_ROOT = Path(__file__).parent.parent.parent
TERRAIN_DATA  = PROJECT_ROOT / "terrain_data"
GAZEBO_WORLDS = PROJECT_ROOT / "gazebo_worlds" / "lunar_south_pole"


def load_dem(path: Path) -> tuple[np.ndarray, dict]:
    try:
        import rasterio
        with rasterio.open(path) as src:
            dem = src.read(1).astype(np.float32)
            meta = {
                "crs": str(src.crs),
                "transform": list(src.transform),
                "nodata": src.nodata,
                "width": src.width,
                "height": src.height,
                "source": str(path),
            }
            if src.nodata is not None:
                dem = np.where(dem == src.nodata, np.nan, dem)
        return dem, meta
    except ImportError:
        log.warning("rasterio not available — loading numpy fallback")
        npy_path = path.with_suffix(".npy")
        if npy_path.exists():
            dem = np.load(npy_path).astype(np.float32)
            meta = {"source": str(npy_path), "fallback": True}
            return dem, meta
        raise FileNotFoundError(f"Cannot load DEM: {path}")


def resample_dem(dem: np.ndarray, target_size: int) -> np.ndarray:
    from scipy.ndimage import zoom
    if dem.shape[0] == target_size and dem.shape[1] == target_size:
        return dem
    # Power-of-2 sizing for Gazebo heightmap
    actual_size = 1
    while actual_size < target_size:
        actual_size *= 2
    sy = actual_size / dem.shape[0]
    sx = actual_size / dem.shape[1]
    resampled = zoom(dem, (sy, sx), order=3)
    return resampled.astype(np.float32)


def fill_nodata(dem: np.ndarray) -> np.ndarray:
    from scipy.ndimage import uniform_filter
    mask = np.isnan(dem)
    if not mask.any():
        return dem
    filled = dem.copy()
    filled[mask] = np.nanmedian(dem)
    # Smooth filled regions
    blurred = uniform_filter(filled, size=5)
    filled[mask] = blurred[mask]
    return filled


def dem_to_gazebo_png(
    dem: np.ndarray, output_path: Path, bits: int = 16
) -> tuple[float, float]:
    dem_min = float(np.nanmin(dem))
    dem_max = float(np.nanmax(dem))
    dem_range = dem_max - dem_min

    if bits == 16:
        scale = 65535.0 / dem_range
        normalized = ((dem - dem_min) * scale).clip(0, 65535).astype(np.uint16)
        Image.fromarray(normalized, mode="I;16").save(output_path)
    else:
        scale = 255.0 / dem_range
        normalized = ((dem - dem_min) * scale).clip(0, 255).astype(np.uint8)
        Image.fromarray(normalized, mode="L").save(output_path)

    log.info(f"Gazebo heightmap: {output_path} ({dem.shape[1]}×{dem.shape[0]}, {bits}-bit)")
    return dem_min, dem_max


def compute_slope_map(dem: np.ndarray, pixel_size_m: float) -> np.ndarray:
    # Central difference gradient
    dy, dx = np.gradient(dem, pixel_size_m)
    slope = np.degrees(np.arctan(np.sqrt(dx**2 + dy**2)))
    return slope.astype(np.float32)


def compute_roughness_map(dem: np.ndarray, window: int = 5) -> np.ndarray:
    from scipy.ndimage import uniform_filter
    smoothed = uniform_filter(dem.astype(np.float64), size=window)
    roughness = np.abs(dem - smoothed).astype(np.float32)
    return roughness


def compute_psr_mask(slope_map: np.ndarray, lat_center_deg: float = -89.5) -> np.ndarray:
    """
    Approximate PSR mask: regions permanently in shadow.
    Simplified: PSR = areas where slope > critical angle from sun
    Sun elevation at south pole: max ~2° above horizon
    Shadow criterion: terrain slope toward sun > sun elevation angle
    """
    sun_elevation_deg = 2.0  # max solar elevation at south pole
    size = slope_map.shape[0]
    cy, cx = size / 2.0, size / 2.0
    y_idx, x_idx = np.ogrid[:size, :size]
    # Direction toward sun (simplified: poleward-facing slopes)
    dist = np.sqrt((x_idx - cx)**2 + (y_idx - cy)**2)
    # Approximate: PSR where slope > sun_elevation AND in crater interior
    psr_mask = (slope_map > sun_elevation_deg + 10.0).astype(np.uint8)
    # PSR centers more likely at large crater bowls (high dist from center → crater rims)
    return psr_mask


def save_png_8bit(arr: np.ndarray, path: Path, invert: bool = False) -> None:
    a_min, a_max = arr.min(), arr.max()
    if a_max > a_min:
        normalized = ((arr - a_min) / (a_max - a_min) * 255).astype(np.uint8)
    else:
        normalized = np.zeros_like(arr, dtype=np.uint8)
    if invert:
        normalized = 255 - normalized
    Image.fromarray(normalized, mode="L").save(path)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    parser = argparse.ArgumentParser(description="DEM → Gazebo heightmap converter")
    parser.add_argument("--input", type=Path,
                        default=TERRAIN_DATA / "lola_dem" / "south_pole_dem.tif")
    parser.add_argument("--output_size", type=int, default=512)
    parser.add_argument("--terrain_scale_m", type=float, default=50.0,
                        help="Meters per pixel in output heightmap")
    parser.add_argument("--lat_center", type=float, default=-89.5)
    args = parser.parse_args()

    GAZEBO_WORLDS.mkdir(parents=True, exist_ok=True)
    processed = TERRAIN_DATA / "processed"
    processed.mkdir(parents=True, exist_ok=True)

    # Load DEM
    log.info(f"Loading DEM: {args.input}")
    if args.input.exists():
        dem, meta = load_dem(args.input)
    else:
        log.warning("DEM not found — generating synthetic terrain")
        sys.path.insert(0, str(Path(__file__).parent.parent / "data_pipeline"))
        from ingest_nasa_data import generate_synthetic_south_pole_dem, save_dem_geotiff
        size = args.output_size
        extent_km = size * args.terrain_scale_m / 1000.0
        dem, meta = generate_synthetic_south_pole_dem(
            size=size, lat_center=args.lat_center, extent_km=extent_km
        )
        save_dem_geotiff(dem, meta, args.input)

    # Fill NoData and resample
    dem = fill_nodata(dem)
    dem = resample_dem(dem, args.output_size)

    # Gazebo heightmap
    hm_path = GAZEBO_WORLDS / "lunar_south_pole_dem.png"
    dem_min, dem_max = dem_to_gazebo_png(dem, hm_path, bits=16)

    # Derived products
    pixel_m = args.terrain_scale_m
    slope = compute_slope_map(dem, pixel_m)
    roughness = compute_roughness_map(dem)
    psr_mask = compute_psr_mask(slope, args.lat_center)

    save_png_8bit(slope, processed / "slope_map.png")
    save_png_8bit(roughness, processed / "roughness_map.png")
    Image.fromarray(psr_mask * 255, mode="L").save(processed / "psr_mask.png")

    # Traversability map (composite: low slope + low roughness = high traversability)
    trav = np.clip(1.0 - (slope / 30.0) - (roughness / 5.0), 0.0, 1.0)
    save_png_8bit(trav, processed / "traversability_map.png")

    metadata = {
        "source": str(args.input),
        "output_size_px": args.output_size,
        "terrain_scale_m_per_px": pixel_m,
        "elevation_min_m": float(dem_min),
        "elevation_max_m": float(dem_max),
        "slope_max_deg": float(slope.max()),
        "slope_mean_deg": float(slope.mean()),
        "psr_fraction": float(psr_mask.mean()),
        "traversable_fraction": float((trav > 0.5).mean()),
        "gazebo_heightmap": str(hm_path),
        "gazebo_world_size_m": args.output_size * pixel_m,
    }
    with open(processed / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    log.info(f"Terrain stats: slope max={slope.max():.1f}°, PSR={psr_mask.mean()*100:.1f}%")
    log.info(f"Gazebo world size: {metadata['gazebo_world_size_m']:.0f} × {metadata['gazebo_world_size_m']:.0f} m")
    log.info(f"All terrain products saved to {processed}")


if __name__ == "__main__":
    main()
