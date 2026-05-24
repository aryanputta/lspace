# generate_illumination_map.py
# Computes lunar south pole solar illumination map using DEM ray-tracing.
# Sun position: max elevation 1.54 deg above horizon, azimuth sweeps 0-360 deg over lunar year.
# Integrates over N_SUN_POSITIONS=72 (every 5 deg azimuth).
# Outputs: illumination_fraction.png, psr_definitive_mask.png, illumination_metadata.json

import argparse
import json
import os
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import uniform_filter

PROJECT_ROOT = Path(__file__).resolve().parents[2]

N_SUN_POSITIONS: int = 72
SUN_ELEVATION_DEG: float = 1.54
RESOLUTION_M: float = 30.0
PSR_ILLUMINATION_THRESHOLD: float = 0.01


def load_dem(dem_path: str, resolution_m: float) -> tuple[np.ndarray, float]:
    img = Image.open(dem_path)
    arr = np.array(img, dtype=np.float32)
    if arr.ndim == 3:
        arr = arr[:, :, 0]
    return arr, resolution_m


def compute_sun_direction(azimuth_deg: float, elevation_deg: float) -> tuple[float, float, float]:
    az_rad = np.deg2rad(azimuth_deg)
    el_rad = np.deg2rad(elevation_deg)
    dx = np.cos(el_rad) * np.sin(az_rad)
    dy = np.cos(el_rad) * np.cos(az_rad)
    dz = np.sin(el_rad)
    return float(dx), float(dy), float(dz)


def ray_trace_shadow_mask(
    dem: np.ndarray,
    resolution_m: float,
    sun_dx: float,
    sun_dy: float,
    sun_dz: float,
    max_range_m: float = 50000.0,
) -> np.ndarray:
    rows, cols = dem.shape
    n_steps = int(max_range_m / resolution_m)
    shadow = np.zeros((rows, cols), dtype=np.bool_)

    row_indices = np.arange(rows, dtype=np.float32)
    col_indices = np.arange(cols, dtype=np.float32)
    grid_col, grid_row = np.meshgrid(col_indices, row_indices)

    for step in range(1, n_steps + 1):
        sample_row = grid_row - step * sun_dy
        sample_col = grid_col + step * sun_dx
        sample_elev_floor = dem + step * sun_dz * resolution_m

        valid = (
            (sample_row >= 0)
            & (sample_row < rows - 1)
            & (sample_col >= 0)
            & (sample_col < cols - 1)
        )

        r0 = np.clip(sample_row.astype(np.int32), 0, rows - 2)
        c0 = np.clip(sample_col.astype(np.int32), 0, cols - 2)
        r1 = r0 + 1
        c1 = c0 + 1

        fr = np.clip(sample_row - r0.astype(np.float32), 0.0, 1.0)
        fc = np.clip(sample_col - c0.astype(np.float32), 0.0, 1.0)

        terrain_at_sample = (
            dem[r0, c0] * (1 - fr) * (1 - fc)
            + dem[r1, c0] * fr * (1 - fc)
            + dem[r0, c1] * (1 - fr) * fc
            + dem[r1, c1] * fr * fc
        )

        newly_shadowed = valid & (terrain_at_sample > sample_elev_floor) & (~shadow)
        shadow |= newly_shadowed

        if not np.any(valid):
            break

    return shadow


def compute_illumination_map(
    dem: np.ndarray,
    resolution_m: float,
    n_sun_positions: int,
    sun_elevation_deg: float,
) -> np.ndarray:
    rows, cols = dem.shape
    illuminated_count = np.zeros((rows, cols), dtype=np.float32)

    azimuths = np.linspace(0.0, 360.0, n_sun_positions, endpoint=False)

    for i, az in enumerate(azimuths):
        dx, dy, dz = compute_sun_direction(az, sun_elevation_deg)
        shadow = ray_trace_shadow_mask(dem, resolution_m, dx, dy, dz)
        illuminated_count += (~shadow).astype(np.float32)

        if (i + 1) % 12 == 0:
            pct = (i + 1) / n_sun_positions * 100
            print(f"  Sun position {i+1}/{n_sun_positions} ({pct:.0f}%) -- azimuth {az:.1f} deg")

    illumination_fraction = illuminated_count / float(n_sun_positions)
    return illumination_fraction


def save_illumination_fraction_png(
    illumination_fraction: np.ndarray,
    output_path: str,
) -> None:
    scaled = np.clip(illumination_fraction * 255.0, 0, 255).astype(np.uint8)
    img = Image.fromarray(scaled, mode="L")
    img.save(output_path)
    print(f"  Saved illumination_fraction.png -> {output_path}")


def save_psr_mask_png(
    illumination_fraction: np.ndarray,
    output_path: str,
    threshold: float = PSR_ILLUMINATION_THRESHOLD,
) -> None:
    psr_mask = (illumination_fraction < threshold).astype(np.uint8) * 255
    img = Image.fromarray(psr_mask, mode="L")
    img.save(output_path)
    print(f"  Saved psr_definitive_mask.png -> {output_path}")


def compute_metadata(
    illumination_fraction: np.ndarray,
    dem: np.ndarray,
    resolution_m: float,
    n_sun_positions: int,
    sun_elevation_deg: float,
) -> dict:
    psr_mask = illumination_fraction < PSR_ILLUMINATION_THRESHOLD
    total_pixels = illumination_fraction.size
    psr_pixels = int(np.sum(psr_mask))
    psr_fraction = float(psr_pixels / total_pixels)
    mean_illumination = float(np.mean(illumination_fraction))

    pixel_area_km2 = (resolution_m / 1000.0) ** 2
    total_area_km2 = float(total_pixels * pixel_area_km2)
    psr_area_km2 = float(psr_pixels * pixel_area_km2)

    dx = np.gradient(dem, resolution_m, axis=1)
    dy = np.gradient(dem, resolution_m, axis=0)
    slope_rad = np.arctan(np.sqrt(dx**2 + dy**2))
    slope_deg = np.rad2deg(slope_rad)

    metadata: dict = {
        "dem_rows": int(dem.shape[0]),
        "dem_cols": int(dem.shape[1]),
        "resolution_m": resolution_m,
        "n_sun_positions": n_sun_positions,
        "sun_elevation_deg": sun_elevation_deg,
        "sun_azimuth_step_deg": 360.0 / n_sun_positions,
        "psr_threshold_illumination_fraction": PSR_ILLUMINATION_THRESHOLD,
        "psr_fraction": round(psr_fraction, 4),
        "psr_area_km2": round(psr_area_km2, 2),
        "total_area_km2": round(total_area_km2, 2),
        "mean_illumination": round(mean_illumination, 4),
        "max_illumination": round(float(np.max(illumination_fraction)), 4),
        "min_illumination": round(float(np.min(illumination_fraction)), 4),
        "dem_min_m": round(float(np.min(dem)), 2),
        "dem_max_m": round(float(np.max(dem)), 2),
        "dem_mean_m": round(float(np.mean(dem)), 2),
        "mean_slope_deg": round(float(np.mean(slope_deg)), 2),
        "max_slope_deg": round(float(np.max(slope_deg)), 2),
        "traversable_fraction_15deg": round(float(np.mean(slope_deg < 15.0)), 4),
        "psr_pixel_count": psr_pixels,
        "total_pixel_count": total_pixels,
    }
    return metadata


def generate_synthetic_dem(rows: int, cols: int, resolution_m: float) -> np.ndarray:
    dem = np.zeros((rows, cols), dtype=np.float32)
    center_row = rows // 2
    center_col = cols // 2

    rr, cc = np.mgrid[0:rows, 0:cols]
    dist = np.sqrt((rr - center_row) ** 2 + (cc - center_col) ** 2) * resolution_m

    crater_radius_m = 10500.0
    crater_depth_m = 4000.0
    rim_height_m = 2850.0

    rim_falloff = np.exp(-((dist - crater_radius_m) ** 2) / (2 * (crater_radius_m * 0.15) ** 2))
    dem += rim_height_m * rim_falloff

    inside_crater = dist <= crater_radius_m
    floor_profile = -crater_depth_m * (1.0 - (dist[inside_crater] / crater_radius_m) ** 2)
    dem[inside_crater] = floor_profile

    noise = np.random.default_rng(seed=42).normal(0, 15.0, (rows, cols)).astype(np.float32)
    noise = uniform_filter(noise, size=3)
    dem += noise

    return dem


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate lunar south pole solar illumination map from DEM."
    )
    parser.add_argument(
        "--dem_path",
        type=str,
        default=None,
        help=(
            "Path to input DEM (GeoTIFF or 16-bit PNG). "
            "If omitted, a synthetic Shackleton-like DEM is generated."
        ),
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default=str(PROJECT_ROOT / "terrain_data" / "processed"),
        help="Output directory for illumination products.",
    )
    parser.add_argument(
        "--resolution_m",
        type=float,
        default=RESOLUTION_M,
        help=f"DEM spatial resolution in meters per pixel (default: {RESOLUTION_M}).",
    )
    parser.add_argument(
        "--n_sun_positions",
        type=int,
        default=N_SUN_POSITIONS,
        help=(
            f"Number of sun azimuth positions to sample over 360 deg "
            f"(default: {N_SUN_POSITIONS})."
        ),
    )
    parser.add_argument(
        "--sun_elevation_deg",
        type=float,
        default=SUN_ELEVATION_DEG,
        help=(
            f"Sun elevation angle above horizon in degrees "
            f"(default: {SUN_ELEVATION_DEG}, max at lunar south pole)."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=== LPAS Illumination Map Generator ===")
    print(f"  Output directory : {output_dir.resolve()}")
    print(f"  Resolution       : {args.resolution_m} m/px")
    print(
        f"  Sun positions    : {args.n_sun_positions} "
        f"(every {360.0/args.n_sun_positions:.1f} deg azimuth)"
    )
    print(f"  Sun elevation    : {args.sun_elevation_deg} deg above horizon")

    if args.dem_path is not None and os.path.isfile(args.dem_path):
        print(f"\n[1/4] Loading DEM from {args.dem_path}")
        dem, resolution_m = load_dem(args.dem_path, args.resolution_m)
    else:
        if args.dem_path is not None:
            print(
                f"\n[1/4] WARNING: DEM file not found at '{args.dem_path}' "
                f"-- using synthetic DEM."
            )
        else:
            print(
                "\n[1/4] No DEM path provided -- generating synthetic Shackleton crater DEM."
            )
        dem = generate_synthetic_dem(257, 257, args.resolution_m)
        resolution_m = args.resolution_m

    print(f"  DEM shape    : {dem.shape[0]} x {dem.shape[1]} pixels")
    print(f"  Elev range   : {dem.min():.1f} m to {dem.max():.1f} m")
    print(
        f"  Coverage     : {dem.shape[0]*resolution_m/1000:.1f} km x "
        f"{dem.shape[1]*resolution_m/1000:.1f} km"
    )

    print(
        f"\n[2/4] Ray-tracing illumination for {args.n_sun_positions} sun positions..."
    )
    illumination_fraction = compute_illumination_map(
        dem,
        resolution_m,
        args.n_sun_positions,
        args.sun_elevation_deg,
    )

    print("\n[3/4] Saving output products...")
    illum_png_path = str(output_dir / "illumination_fraction.png")
    psr_png_path = str(output_dir / "psr_definitive_mask.png")

    save_illumination_fraction_png(illumination_fraction, illum_png_path)
    save_psr_mask_png(illumination_fraction, psr_png_path)

    print("\n[4/4] Computing and saving metadata...")
    metadata = compute_metadata(
        illumination_fraction,
        dem,
        resolution_m,
        args.n_sun_positions,
        args.sun_elevation_deg,
    )

    metadata_path = str(output_dir / "illumination_metadata.json")
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"  Saved illumination_metadata.json -> {metadata_path}")

    print("\n=== Results ===")
    print(f"  PSR fraction         : {metadata['psr_fraction']*100:.2f}%")
    print(f"  PSR area             : {metadata['psr_area_km2']:.1f} km2")
    print(f"  Mean illumination    : {metadata['mean_illumination']*100:.1f}%")
    print(f"  Mean slope           : {metadata['mean_slope_deg']:.1f} deg")
    print(
        f"  Traversable fraction : {metadata['traversable_fraction_15deg']*100:.1f}% "
        f"(slope < 15 deg)"
    )
    print(
        f"  DEM elevation range  : {metadata['dem_min_m']:.0f} m to "
        f"{metadata['dem_max_m']:.0f} m"
    )
    print("\nDone.")


if __name__ == "__main__":
    main()
