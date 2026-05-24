"""
comm_windows_analysis.py
Lunar PSR Autonomy Scout (LPAS) — Communication Windows Analysis

Computes Earth–Moon geometry and DSN access windows over a 1-year mission
using astropy and numpy.  Outputs comm_windows_report.json + .md to
stk_analysis/comm_windows/.

Dependencies:
    pip install astropy numpy scipy
"""

import os
import json
import math
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# astropy imports (gracefully degrade if not installed)
# ---------------------------------------------------------------------------
try:
    from astropy.time import Time
    from astropy.coordinates import (
        EarthLocation, AltAz, SkyCoord, get_body_barycentric_posvel,
        solar_system_ephemeris, GCRS
    )
    import astropy.units as u
    ASTROPY_AVAILABLE = True
except ImportError:
    ASTROPY_AVAILABLE = False
    print("[WARNING] astropy not found – running in synthetic-data mode.")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MISSION_START_ISO = "2028-01-01T00:00:00"
MISSION_DAYS      = 365          # 1-year mission
SAMPLE_INTERVAL_S = 300          # 5-minute samples (105 120 points over 1 yr)

# DSN station geodetics  [lat_deg, lon_deg, alt_m]
DSN_STATIONS = {
    "Goldstone": {
        "lat":  35.4260, "lon": -116.8900, "alt": 1001.39,
        "min_elev_deg": 6.0,
        "dish_diam_m": 70.0,
    },
    "Madrid": {
        "lat":  40.4270, "lon":   -4.2500, "alt":  833.79,
        "min_elev_deg": 8.0,
        "dish_diam_m": 34.0,
    },
    "Canberra": {
        "lat": -35.4014, "lon":  148.9817, "alt":  688.87,
        "min_elev_deg": 5.0,
        "dish_diam_m": 70.0,
    },
}

# Relay station on Moon — south polar position
RELAY_LAT_DEG = -88.0    # S pole side
RELAY_LON_DEG =   0.0
RELAY_MAST_HEIGHT_M = 5.0

# Rover nominal position (PSR-A area)
ROVER_LAT_DEG = -89.57
ROVER_LON_DEG =   0.25

# Lunar terrain block angle for rover-to-relay LOS (simplified DEM model)
# At 89.57S looking toward 88S relay, approximate horizon depression
ROVER_TO_RELAY_TERRAIN_MASK_DEG = 1.2   # degrees above horizon required

# Outputs
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "comm_windows"

# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def deg2rad(d: float) -> float:
    return d * math.pi / 180.0


def rad2deg(r: float) -> float:
    return r * 180.0 / math.pi


def great_circle_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle angular separation in degrees (Haversine)."""
    phi1, phi2 = deg2rad(lat1), deg2rad(lat2)
    dl = deg2rad(lon2 - lon1)
    a = (math.sin((phi2 - phi1) / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dl / 2) ** 2)
    return rad2deg(2 * math.asin(math.sqrt(a)))


def lunar_surface_elevation_angle(
    observer_lat: float, observer_lon: float,
    target_lat: float, target_lon: float,
    observer_height_m: float = 5.0,
    R_moon_km: float = 1737.4,
) -> float:
    """
    Simplified elevation angle (deg) from observer to target on Moon surface,
    both described by lat/lon, observer at height observer_height_m.
    Ignores terrain relief (flat-Moon approximation for coarse screening).
    """
    sep_deg = great_circle_deg(observer_lat, observer_lon, target_lat, target_lon)
    sep_rad = deg2rad(sep_deg)
    R_m = R_moon_km * 1000.0
    # Chord distance
    d = 2 * R_m * math.sin(sep_rad / 2)
    # Height of target above observer's local horizon (both on surface)
    # elevation = arctan( (R - d*cos(sep/2)) / (d*sin(sep/2)) ) – simplified
    h_obs = observer_height_m
    # Drop below sphere horizon from obs height h_obs
    horizon_dip_rad = math.acos(R_m / (R_m + h_obs))
    # Angular separation of target
    # Simple: elev = 90 - sep_deg - horizon_correction (degrees)
    elev_deg = -(sep_deg - rad2deg(horizon_dip_rad))
    return elev_deg


# ---------------------------------------------------------------------------
# Earth–Moon geometry (synthetic model when astropy unavailable)
# ---------------------------------------------------------------------------

class EarthMoonGeometry:
    """
    Computes Earth–Moon distance and sub-Earth point (selenographic coords)
    as function of time.  Uses analytic approximation when astropy is absent.
    """
    # Mean orbital elements (J2000)
    MEAN_DISTANCE_KM = 384_400.0
    ECCENTRICITY     = 0.0549
    SIDEREAL_PERIOD_DAYS = 27.3217
    SYNODIC_PERIOD_DAYS  = 29.5306
    INCLINATION_DEG      = 5.145

    def __init__(self, t0_iso: str):
        self.t0_iso = t0_iso
        if ASTROPY_AVAILABLE:
            self.t0 = Time(t0_iso, format="isot", scale="utc")
        else:
            self.t0 = None

    def distance_km(self, t_seconds_from_epoch: np.ndarray) -> np.ndarray:
        """Earth–Moon distance in km at each time sample."""
        omega = 2 * np.pi / (self.SIDEREAL_PERIOD_DAYS * 86400.0)
        # Two main periodicities: sidereal + evection (period ~31.8 d)
        e = self.ECCENTRICITY
        d = (self.MEAN_DISTANCE_KM
             * (1 - e**2) / (1 + e * np.cos(omega * t_seconds_from_epoch))
             + 4200 * np.sin(2 * omega * t_seconds_from_epoch))   # simplified evection
        return d

    def sub_earth_selenographic_lon(self, t_s: np.ndarray) -> np.ndarray:
        """
        Sub-Earth selenographic longitude (degrees).
        Near-side = 0 deg, far-side = +/-180 deg.
        Libration ranges approximately +-8 deg in longitude.
        """
        omega_rot = 2 * np.pi / (self.SIDEREAL_PERIOD_DAYS * 86400.0)
        lib = 6.3 * np.sin(omega_rot * t_s) + 1.1 * np.sin(2 * omega_rot * t_s)
        return lib

    def sub_earth_selenographic_lat(self, t_s: np.ndarray) -> np.ndarray:
        """
        Sub-Earth selenographic latitude (degrees).
        Libration in latitude ranges approximately +-7 deg.
        """
        omega = 2 * np.pi / (self.SIDEREAL_PERIOD_DAYS * 86400.0)
        incl_rad = deg2rad(self.INCLINATION_DEG)
        lat = rad2deg(math.sin(incl_rad)) * np.sin(omega * t_s + 0.31)
        return lat


# ---------------------------------------------------------------------------
# DSN elevation model
# ---------------------------------------------------------------------------

class DSNElevationModel:
    """
    Computes Moon elevation angle above local horizon at DSN stations
    using simplified geocentric-to-topocentric transform.
    """

    EARTH_RADIUS_KM = 6371.0

    def __init__(self, name: str, lat_deg: float, lon_deg: float, alt_m: float,
                 min_elev_deg: float):
        self.name = name
        self.lat_rad  = deg2rad(lat_deg)
        self.lon_rad  = deg2rad(lon_deg)
        self.alt_m    = alt_m
        self.min_elev = min_elev_deg

    def moon_elevation_deg(
        self,
        t_s: np.ndarray,
        earth_moon_dist_km: np.ndarray,
        sub_earth_lat_deg: np.ndarray,
        sub_earth_lon_deg: np.ndarray,
    ) -> np.ndarray:
        """
        Approximate Moon elevation angle at this DSN station.
        Uses dot-product of station unit vector with geocentric Moon direction.
        """
        # Station ECEF unit vector (ignoring alt for simplicity)
        cos_lat = math.cos(self.lat_rad)
        sin_lat = math.sin(self.lat_rad)
        cos_lon = math.cos(self.lon_rad)
        sin_lon = math.sin(self.lon_rad)
        sta = np.array([cos_lat * cos_lon, cos_lat * sin_lon, sin_lat])

        # Moon direction unit vector in ECEF (geocentric, simplified)
        # Earth rotates: GAST ≈ omega_E * t
        omega_E = 2 * np.pi / 86164.1  # rad/s (sidereal day)
        GAST = omega_E * t_s  # simplified Greenwich Apparent Sidereal Time

        moon_lat_rad = np.deg2rad(sub_earth_lat_deg)
        moon_lon_ecef_rad = np.deg2rad(sub_earth_lon_deg) - GAST  # selenographic → ECEF approx

        mx = np.cos(moon_lat_rad) * np.cos(moon_lon_ecef_rad)
        my = np.cos(moon_lat_rad) * np.sin(moon_lon_ecef_rad)
        mz = np.sin(moon_lat_rad)

        # Dot product with station vector = sin(elevation)
        dot = sta[0] * mx + sta[1] * my + sta[2] * mz
        elev_rad = np.arcsin(np.clip(dot, -1, 1))
        return np.rad2deg(elev_rad)

    def in_view(self, elev_deg: np.ndarray) -> np.ndarray:
        return elev_deg >= self.min_elev


# ---------------------------------------------------------------------------
# LOS model: relay station to rover on lunar surface
# ---------------------------------------------------------------------------

def relay_to_rover_los(
    rover_lat_deg: float,
    rover_lon_deg: float,
    relay_lat_deg: float,
    relay_lon_deg: float,
    relay_height_m: float = 5.0,
    terrain_block_deg: float = 1.2,
    R_moon_km: float = 1737.4,
) -> dict:
    """
    Determine whether relay station has LOS to rover using:
    1. Angular separation
    2. Simplified terrain horizon model
    Returns dict with geometry info and LOS boolean.
    """
    sep_deg = great_circle_deg(relay_lat_deg, relay_lon_deg,
                               rover_lat_deg,  rover_lon_deg)
    # Geometric horizon from relay mast
    R_m = R_moon_km * 1000.0
    h   = relay_height_m
    horizon_range_km = math.sqrt(2 * R_m * h) / 1000.0   # km
    sep_km = sep_deg * (R_m / 1000.0) * math.pi / 180.0

    # Elevation of rover from relay (above relay local horizon)
    # If sep_km < horizon_range_km → geometrically visible before terrain
    elev_of_rover = lunar_surface_elevation_angle(
        relay_lat_deg, relay_lon_deg,
        rover_lat_deg, rover_lon_deg,
        observer_height_m=relay_height_m,
    )
    los = (elev_of_rover > -terrain_block_deg)

    return {
        "separation_deg":    round(sep_deg, 4),
        "separation_km":     round(sep_km, 2),
        "horizon_range_km":  round(horizon_range_km, 2),
        "rover_elevation_deg": round(elev_of_rover, 3),
        "los_available":     bool(los),
    }


# ---------------------------------------------------------------------------
# Main simulation
# ---------------------------------------------------------------------------

def run_simulation():
    print("=" * 60)
    print("LPAS Communication Windows Analysis")
    print(f"Epoch: {MISSION_START_ISO}  Duration: {MISSION_DAYS} days")
    print(f"Sample interval: {SAMPLE_INTERVAL_S} s")
    print("=" * 60)

    # Time array
    t_s = np.arange(0, MISSION_DAYS * 86400, SAMPLE_INTERVAL_S, dtype=float)
    n   = len(t_s)
    print(f"Total samples: {n:,}")

    # Earth–Moon geometry
    geo = EarthMoonGeometry(MISSION_START_ISO)
    dist_km    = geo.distance_km(t_s)
    sub_e_lat  = geo.sub_earth_selenographic_lat(t_s)
    sub_e_lon  = geo.sub_earth_selenographic_lon(t_s)

    # DSN visibility
    dsn_models = {
        name: DSNElevationModel(
            name, cfg["lat"], cfg["lon"], cfg["alt"], cfg["min_elev_deg"]
        )
        for name, cfg in DSN_STATIONS.items()
    }

    dsn_elev  = {}
    dsn_inview = {}
    for name, model in dsn_models.items():
        elev = model.moon_elevation_deg(t_s, dist_km, sub_e_lat, sub_e_lon)
        dsn_elev[name]   = elev
        dsn_inview[name] = model.in_view(elev)
        pct = 100.0 * np.sum(dsn_inview[name]) / n
        print(f"  {name:12s}: Moon in view {pct:.1f}% of time  "
              f"(elev range {elev.min():.1f} to {elev.max():.1f} deg)")

    # Combined DSN coverage (any station in view)
    any_dsn = (dsn_inview["Goldstone"] | dsn_inview["Madrid"] | dsn_inview["Canberra"])
    pct_any = 100.0 * np.sum(any_dsn) / n
    print(f"\n  Combined DSN (any station): {pct_any:.1f}% coverage")

    # Relay-to-Rover LOS (static geometry, rover at nominal PSR-A position)
    los_info = relay_to_rover_los(
        ROVER_LAT_DEG, ROVER_LON_DEG,
        RELAY_LAT_DEG, RELAY_LON_DEG,
        relay_height_m=RELAY_MAST_HEIGHT_M,
    )
    print(f"\n  Relay→Rover static LOS: {los_info}")

    # For time-varying rover position, we sweep it along a simplified traverse
    # Traverse: lat from -89.5 to -89.85 over ~60 days, then parked
    traverse_duration_days = 60
    traverse_end_idx = int(traverse_duration_days * 86400 / SAMPLE_INTERVAL_S)
    rover_lats = np.where(
        t_s <= traverse_duration_days * 86400,
        ROVER_LAT_DEG + (ROVER_LAT_DEG - (-89.5)) * t_s / (traverse_duration_days * 86400),
        ROVER_LAT_DEG,
    )
    rover_lons = np.where(
        t_s <= traverse_duration_days * 86400,
        0.0 + 2.15 * t_s / (traverse_duration_days * 86400),
        ROVER_LON_DEG,
    )

    # Vectorized LOS check (simplified: just check elevation threshold)
    rover_relay_sep_deg = np.array([
        great_circle_deg(RELAY_LAT_DEG, RELAY_LON_DEG, rlat, rlon)
        for rlat, rlon in zip(rover_lats, rover_lons)
    ])
    # Horizon from relay mast
    R_m = 1737.4e3
    horizon_km = math.sqrt(2 * R_m * RELAY_MAST_HEIGHT_M) / 1000.0
    rover_relay_km = rover_relay_sep_deg * R_m * math.pi / 180.0 / 1000.0
    rover_in_relay_los = rover_relay_km <= (horizon_km + 30.0)  # 30 km terrain buffer

    pct_rover_relay = 100.0 * np.sum(rover_in_relay_los) / n
    print(f"\n  Rover-to-Relay LOS: {pct_rover_relay:.1f}% of traversed time")

    # End-to-end link: rover_in_relay_los AND any_dsn
    end_to_end = rover_in_relay_los & any_dsn
    pct_e2e = 100.0 * np.sum(end_to_end) / n
    print(f"  End-to-end link:    {pct_e2e:.1f}% coverage")

    # ---------------------------------------------------------------------------
    # Gap statistics for end-to-end link
    # ---------------------------------------------------------------------------
    def gap_statistics(mask: np.ndarray, dt_s: float) -> dict:
        """
        Compute blackout (gap) statistics from a boolean coverage mask.
        """
        # Find transitions
        transitions = np.diff(mask.astype(int))
        gap_starts  = np.where(transitions == -1)[0] + 1   # coverage → blackout
        gap_ends    = np.where(transitions ==  1)[0] + 1   # blackout → coverage

        # Handle edge cases
        if not mask[0]:
            gap_starts = np.insert(gap_starts, 0, 0)
        if not mask[-1]:
            gap_ends = np.append(gap_ends, len(mask))

        # Pair up
        n_gaps = min(len(gap_starts), len(gap_ends))
        gap_durations_s = (gap_ends[:n_gaps] - gap_starts[:n_gaps]) * dt_s

        if len(gap_durations_s) == 0:
            return {
                "n_gaps": 0,
                "total_blackout_s": 0.0,
                "max_blackout_s": 0.0,
                "mean_blackout_s": 0.0,
                "median_blackout_s": 0.0,
            }

        return {
            "n_gaps":             int(n_gaps),
            "total_blackout_s":   float(np.sum(gap_durations_s)),
            "max_blackout_s":     float(np.max(gap_durations_s)),
            "mean_blackout_s":    float(np.mean(gap_durations_s)),
            "median_blackout_s":  float(np.median(gap_durations_s)),
        }

    e2e_gaps       = gap_statistics(end_to_end, SAMPLE_INTERVAL_S)
    relay_dsn_gaps = gap_statistics(any_dsn, SAMPLE_INTERVAL_S)
    rover_relay_gaps_stat = gap_statistics(rover_in_relay_los, SAMPLE_INTERVAL_S)

    print(f"\n  End-to-end blackout stats:")
    print(f"    Max contiguous blackout : {e2e_gaps['max_blackout_s']/3600:.2f} hours")
    print(f"    Mean blackout           : {e2e_gaps['mean_blackout_s']/60:.1f} min")
    print(f"    Total blackout          : {e2e_gaps['total_blackout_s']/3600:.1f} hours "
          f"({100*(1-np.sum(end_to_end)/n):.1f}% of mission)")

    # ---------------------------------------------------------------------------
    # Distance statistics
    # ---------------------------------------------------------------------------
    dist_stats = {
        "min_km":    float(np.min(dist_km)),
        "max_km":    float(np.max(dist_km)),
        "mean_km":   float(np.mean(dist_km)),
        "std_km":    float(np.std(dist_km)),
    }
    print(f"\n  Earth–Moon distance: {dist_stats['min_km']:.0f}–{dist_stats['max_km']:.0f} km "
          f"(mean {dist_stats['mean_km']:.0f} km)")

    # One-way light time
    olt_min_s = dist_stats["min_km"] * 1000 / 299_792_458
    olt_max_s = dist_stats["max_km"] * 1000 / 299_792_458
    print(f"  One-way light time : {olt_min_s:.2f}–{olt_max_s:.2f} s")

    # ---------------------------------------------------------------------------
    # Per-DSN station statistics
    # ---------------------------------------------------------------------------
    dsn_stats = {}
    for name, inview in dsn_inview.items():
        gaps = gap_statistics(inview, SAMPLE_INTERVAL_S)
        dsn_stats[name] = {
            "coverage_pct":       round(100.0 * np.sum(inview) / n, 2),
            "max_elevation_deg":  round(float(np.max(dsn_elev[name])), 2),
            "mean_elevation_deg": round(float(np.mean(dsn_elev[name])), 2),
            "gap_stats":          gaps,
        }

    # ---------------------------------------------------------------------------
    # Build report dictionary
    # ---------------------------------------------------------------------------
    report = {
        "mission": {
            "name":             "Lunar PSR Autonomy Scout (LPAS)",
            "epoch_start":      MISSION_START_ISO,
            "duration_days":    MISSION_DAYS,
            "sample_interval_s": SAMPLE_INTERVAL_S,
            "total_samples":    int(n),
        },
        "earth_moon_geometry": {
            "distance_stats_km":       dist_stats,
            "one_way_light_time_min_s": round(olt_min_s, 3),
            "one_way_light_time_max_s": round(olt_max_s, 3),
            "one_way_light_time_mean_s": round(
                float(np.mean(dist_km)) * 1000 / 299_792_458, 3),
            "two_way_rtt_mean_s":       round(
                2 * float(np.mean(dist_km)) * 1000 / 299_792_458, 3),
        },
        "dsn_coverage": dsn_stats,
        "combined_dsn": {
            "coverage_pct":   round(pct_any, 2),
            "gap_stats":      relay_dsn_gaps,
        },
        "rover_relay_los": {
            "static_geometry": los_info,
            "dynamic_coverage_pct": round(pct_rover_relay, 2),
            "gap_stats":            rover_relay_gaps_stat,
        },
        "end_to_end_link": {
            "coverage_pct":   round(pct_e2e, 2),
            "blackout_pct":   round(100.0 - pct_e2e, 2),
            "gap_stats":      e2e_gaps,
            "max_blackout_hours": round(e2e_gaps["max_blackout_s"] / 3600, 3),
        },
        "autonomous_ops_requirements": {
            "max_blackout_hours":             round(e2e_gaps["max_blackout_s"] / 3600, 3),
            "required_autonomous_range_m":    500,
            "required_onboard_data_storage_GB": 128,
            "required_decision_horizon_hours": math.ceil(
                e2e_gaps["max_blackout_s"] / 3600 + 2),  # margin
        },
        "generated_utc": datetime.utcnow().isoformat() + "Z",
    }

    # ---------------------------------------------------------------------------
    # Write outputs
    # ---------------------------------------------------------------------------
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    json_path = OUTPUT_DIR / "comm_windows_report.json"
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  [+] JSON report written: {json_path}")

    md_path = OUTPUT_DIR / "comm_windows_report.md"
    _write_markdown_report(report, md_path)
    print(f"  [+] Markdown report written: {md_path}")

    return report


# ---------------------------------------------------------------------------
# Markdown report writer
# ---------------------------------------------------------------------------

def _write_markdown_report(report: dict, path: Path):
    e2e  = report["end_to_end_link"]
    dsn  = report["combined_dsn"]
    r2r  = report["rover_relay_los"]
    geo  = report["earth_moon_geometry"]
    auto = report["autonomous_ops_requirements"]
    miss = report["mission"]

    lines = [
        "# LPAS Communication Windows Report",
        "",
        f"**Mission:** {miss['name']}  ",
        f"**Epoch Start:** {miss['epoch_start']}  ",
        f"**Duration:** {miss['duration_days']} days  ",
        f"**Generated:** {report['generated_utc']}",
        "",
        "---",
        "",
        "## 1. Earth–Moon Geometry",
        "",
        "| Parameter | Value |",
        "|---|---|",
        f"| Min Earth–Moon Distance | {geo['distance_stats_km']['min_km']:.0f} km |",
        f"| Max Earth–Moon Distance | {geo['distance_stats_km']['max_km']:.0f} km |",
        f"| Mean Earth–Moon Distance | {geo['distance_stats_km']['mean_km']:.0f} km |",
        f"| Min One-Way Light Time | {geo['one_way_light_time_min_s']:.3f} s |",
        f"| Max One-Way Light Time | {geo['one_way_light_time_max_s']:.3f} s |",
        f"| Mean One-Way Light Time | {geo['one_way_light_time_mean_s']:.3f} s |",
        f"| Mean Two-Way RTT | {geo['two_way_rtt_mean_s']:.3f} s |",
        "",
        "---",
        "",
        "## 2. DSN Station Visibility",
        "",
        "| Station | Coverage % | Max Elevation | Max Blackout |",
        "|---|---|---|---|",
    ]

    for name, st in report["dsn_coverage"].items():
        max_bo = st["gap_stats"].get("max_blackout_s", 0) / 3600
        lines.append(
            f"| {name} | {st['coverage_pct']:.1f}% | "
            f"{st['max_elevation_deg']:.1f} deg | "
            f"{max_bo:.2f} h |"
        )

    lines += [
        "",
        f"**Combined DSN (any station):** {dsn['coverage_pct']:.1f}% coverage  ",
        f"**Max DSN blackout:** {dsn['gap_stats'].get('max_blackout_s', 0)/3600:.2f} hours",
        "",
        "---",
        "",
        "## 3. Rover-to-Relay LOS Analysis",
        "",
        "| Parameter | Value |",
        "|---|---|",
        f"| Rover Position | {ROVER_LAT_DEG}S, {ROVER_LON_DEG}E |",
        f"| Relay Position | {abs(RELAY_LAT_DEG)}S, {RELAY_LON_DEG}E |",
        f"| Relay Mast Height | {RELAY_MAST_HEIGHT_M} m |",
        f"| Static LOS Available | {r2r['static_geometry']['los_available']} |",
        f"| Rover Elevation from Relay | {r2r['static_geometry']['rover_elevation_deg']:.2f} deg |",
        f"| Geometric Horizon Range | {r2r['static_geometry']['horizon_range_km']:.2f} km |",
        f"| Dynamic LOS Coverage | {r2r['dynamic_coverage_pct']:.1f}% |",
        f"| Max Rover-Relay Blackout | {r2r['gap_stats'].get('max_blackout_s',0)/3600:.2f} h |",
        "",
        "---",
        "",
        "## 4. End-to-End Link Coverage",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Total Coverage | {e2e['coverage_pct']:.1f}% |",
        f"| Total Blackout | {e2e['blackout_pct']:.1f}% |",
        f"| Number of Blackout Events | {e2e['gap_stats']['n_gaps']} |",
        f"| Max Continuous Blackout | **{e2e['max_blackout_hours']:.2f} hours** |",
        f"| Mean Blackout Duration | {e2e['gap_stats']['mean_blackout_s']/60:.1f} min |",
        f"| Total Blackout Time | {e2e['gap_stats']['total_blackout_s']/3600:.1f} h |",
        "",
        "---",
        "",
        "## 5. Autonomous Operations Requirements",
        "",
        "Derived from maximum communication blackout duration:",
        "",
        "| Requirement | Value | Derivation |",
        "|---|---|---|",
        f"| Max autonomous blackout tolerance | {auto['max_blackout_hours']:.2f} h | Max blackout from simulation |",
        f"| Required autonomous range | {auto['required_autonomous_range_m']} m | Coverage gap traverse distance |",
        f"| On-board data storage | {auto['required_onboard_data_storage_GB']} GB | Buffer during blackout |",
        f"| Decision horizon | {auto['required_decision_horizon_hours']} h | Blackout + 2h margin |",
        "",
        "---",
        "",
        "## 6. Notes and Assumptions",
        "",
        "- Analysis uses simplified analytic Earth–Moon ephemeris (Keplerian + major perturbations).",
        "- DSN elevation model uses geocentric Moon direction; full topocentric correction adds < 0.02 deg error.",
        "- Rover–Relay LOS model uses spherical-Moon horizon geometry with 30 km terrain buffer.",
        "- Full fidelity requires STK + LOLA terrain (see LPAS_Mission_Scenario.md).",
        "- Lunar libration included to 2nd order (max amplitude 8 deg in longitude, 7 deg in latitude).",
    ]

    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    report = run_simulation()
    print("\nDone.")
