# analyze_comm_visibility.py
# Analyzes LRO satellite communication windows for LPAS at the lunar south pole.
# LRO orbital parameters: altitude 50 km, inclination 90 deg, period 113.5 min.
# Computes elevation angle from LPAS ground position to LRO.
# Contact windows defined by elevation > 5 deg threshold.
# Earth direct visibility: Earth never rises above horizon at south pole -- DSN via LRO relay only.
# Outputs: daily_contact_windows.json, contact_statistics.md in stk_analysis/coverage_reports/

import argparse
import json
import math
from pathlib import Path
from typing import NamedTuple


LRO_ALTITUDE_KM: float = 50.0
LRO_INCLINATION_DEG: float = 90.0
LRO_PERIOD_MIN: float = 113.5
MOON_RADIUS_KM: float = 1737.4
LRO_ORBIT_RADIUS_KM: float = MOON_RADIUS_KM + LRO_ALTITUDE_KM

LPAS_LAT_DEG: float = -89.9
LPAS_LON_DEG: float = 0.0

MIN_ELEVATION_DEG: float = 5.0
SIMULATION_DT_MIN: float = 0.25

EARTH_DIRECT_AVAILABLE: bool = False

UHF_FREQ_MHZ: float = 437.55
UHF_TX_POWER_W: float = 5.0
UHF_ANTENNA_GAIN_ROVER_DBI: float = 2.0
UHF_ANTENNA_GAIN_LRO_DBI: float = 0.0
UHF_DATARATE_BPS: int = 256_000
UHF_MAX_RANGE_KM: float = 200.0

PROJECT_ROOT: Path = Path(__file__).parent.parent.parent
DEFAULT_OUTPUT_DIR: Path = PROJECT_ROOT / "stk_analysis" / "coverage_reports"


class ContactWindow(NamedTuple):
    start_min: float
    end_min: float
    duration_s: float
    max_elevation_deg: float
    max_elev_time_min: float
    mean_elevation_deg: float
    slant_range_km_at_max: float
    data_volume_mb: float


def lro_position_at_time(t_min: float) -> tuple[float, float, float]:
    orbital_period_min = LRO_PERIOD_MIN
    phase_rad = 2.0 * math.pi * (t_min / orbital_period_min)

    incl_rad = math.radians(LRO_INCLINATION_DEG)

    lro_lat_rad = math.asin(math.sin(incl_rad) * math.sin(phase_rad))
    lro_lat_deg = math.degrees(lro_lat_rad)

    cos_lat = math.cos(lro_lat_rad)
    if abs(cos_lat) > 1e-9:
        lro_lon_offset_rad = math.atan2(
            math.cos(incl_rad) * math.sin(phase_rad),
            math.cos(phase_rad),
        )
    else:
        lro_lon_offset_rad = 0.0

    nodal_precession_deg_per_orbit = 0.0
    orbit_number = t_min / orbital_period_min
    node_deg = nodal_precession_deg_per_orbit * orbit_number

    lro_lon_deg = math.degrees(lro_lon_offset_rad) + node_deg

    lro_lon_deg = (lro_lon_deg + 180.0) % 360.0 - 180.0

    return lro_lat_deg, lro_lon_deg, LRO_ALTITUDE_KM


def compute_elevation_angle(
    obs_lat_deg: float,
    obs_lon_deg: float,
    sat_lat_deg: float,
    sat_lon_deg: float,
    sat_alt_km: float,
) -> tuple[float, float]:
    obs_lat_r = math.radians(obs_lat_deg)
    obs_lon_r = math.radians(obs_lon_deg)
    sat_lat_r = math.radians(sat_lat_deg)
    sat_lon_r = math.radians(sat_lon_deg)

    cos_central_angle = math.sin(obs_lat_r) * math.sin(sat_lat_r) + math.cos(
        obs_lat_r
    ) * math.cos(sat_lat_r) * math.cos(obs_lon_r - sat_lon_r)
    cos_central_angle = max(-1.0, min(1.0, cos_central_angle))
    central_angle_rad = math.acos(cos_central_angle)

    r_moon = MOON_RADIUS_KM
    r_sat = r_moon + sat_alt_km

    sin_elev = (r_sat * math.cos(central_angle_rad) - r_moon) / math.sqrt(
        r_sat**2 + r_moon**2 - 2.0 * r_sat * r_moon * math.cos(central_angle_rad)
    )
    sin_elev = max(-1.0, min(1.0, sin_elev))
    elevation_deg = math.degrees(math.asin(sin_elev))

    slant_range_km = math.sqrt(
        r_sat**2 + r_moon**2 - 2.0 * r_sat * r_moon * math.cos(central_angle_rad)
    )

    return elevation_deg, slant_range_km


def compute_link_margin_db(
    slant_range_km: float,
    freq_mhz: float,
    tx_power_w: float,
    tx_gain_dbi: float,
    rx_gain_dbi: float,
    data_rate_bps: int,
    noise_figure_db: float = 3.0,
    required_eb_n0_db: float = 9.6,
    line_loss_db: float = 1.5,
) -> float:
    eirp_dbw = 10.0 * math.log10(tx_power_w) + tx_gain_dbi - line_loss_db
    fspl_db = (
        20.0 * math.log10(slant_range_km * 1000.0)
        + 20.0 * math.log10(freq_mhz * 1e6)
        - 147.55
    )
    received_power_dbw = eirp_dbw - fspl_db + rx_gain_dbi
    k_boltzmann_dbw_hz_k = -228.6
    system_noise_temp_k = 290.0 * (10.0 ** (noise_figure_db / 10.0) - 1.0) + 50.0
    noise_density_dbw_hz = k_boltzmann_dbw_hz_k + 10.0 * math.log10(system_noise_temp_k)
    noise_power_dbw = noise_density_dbw_hz + 10.0 * math.log10(float(data_rate_bps))
    eb_n0_db = received_power_dbw - noise_power_dbw
    margin_db = eb_n0_db - required_eb_n0_db
    return margin_db


def simulate_lro_passes(
    sim_duration_min: float = 1440.0,
    dt_min: float = SIMULATION_DT_MIN,
) -> list[ContactWindow]:
    windows: list[ContactWindow] = []
    in_contact: bool = False
    contact_start: float = 0.0
    max_elev: float = 0.0
    max_elev_time: float = 0.0
    elev_samples: list[float] = []
    slant_at_max: float = LRO_ALTITUDE_KM

    t = 0.0
    while t <= sim_duration_min:
        sat_lat, sat_lon, sat_alt = lro_position_at_time(t)
        elev, slant = compute_elevation_angle(
            LPAS_LAT_DEG, LPAS_LON_DEG, sat_lat, sat_lon, sat_alt
        )

        if elev >= MIN_ELEVATION_DEG:
            if not in_contact:
                in_contact = True
                contact_start = t
                max_elev = elev
                max_elev_time = t
                elev_samples = [elev]
                slant_at_max = slant
            else:
                elev_samples.append(elev)
                if elev > max_elev:
                    max_elev = elev
                    max_elev_time = t
                    slant_at_max = slant
        else:
            if in_contact:
                duration_s = (t - contact_start) * 60.0
                mean_elev = float(sum(elev_samples) / len(elev_samples)) if elev_samples else 0.0
                margin_db = compute_link_margin_db(
                    slant_at_max,
                    UHF_FREQ_MHZ,
                    UHF_TX_POWER_W,
                    UHF_ANTENNA_GAIN_ROVER_DBI,
                    UHF_ANTENNA_GAIN_LRO_DBI,
                    UHF_DATARATE_BPS,
                )
                data_volume_mb = (
                    UHF_DATARATE_BPS * duration_s / 8.0 / 1e6
                    if margin_db > 0.0
                    else 0.0
                )
                windows.append(
                    ContactWindow(
                        start_min=contact_start,
                        end_min=t,
                        duration_s=duration_s,
                        max_elevation_deg=round(max_elev, 2),
                        max_elev_time_min=round(max_elev_time, 2),
                        mean_elevation_deg=round(mean_elev, 2),
                        slant_range_km_at_max=round(slant_at_max, 1),
                        data_volume_mb=round(data_volume_mb, 2),
                    )
                )
                in_contact = False
                max_elev = 0.0
                elev_samples = []

        t += dt_min

    return windows


def build_elevation_timeseries(
    sim_duration_min: float = 1440.0,
    dt_min: float = 2.0,
) -> list[dict]:
    series: list[dict] = []
    t = 0.0
    while t <= sim_duration_min:
        sat_lat, sat_lon, sat_alt = lro_position_at_time(t)
        elev, slant = compute_elevation_angle(
            LPAS_LAT_DEG, LPAS_LON_DEG, sat_lat, sat_lon, sat_alt
        )
        series.append(
            {
                "t_min": round(t, 2),
                "elevation_deg": round(elev, 2),
                "slant_range_km": round(slant, 1),
                "lro_lat_deg": round(sat_lat, 2),
                "lro_lon_deg": round(sat_lon, 2),
                "in_contact": elev >= MIN_ELEVATION_DEG,
            }
        )
        t += dt_min
    return series


def compute_statistics(windows: list[ContactWindow], sim_duration_min: float) -> dict:
    if not windows:
        return {"error": "no_contact_windows_found"}

    durations_s = [w.duration_s for w in windows]
    data_volumes_mb = [w.data_volume_mb for w in windows]
    total_contact_s = sum(durations_s)
    n_passes = len(windows)
    passes_per_day = n_passes * 1440.0 / sim_duration_min

    margin_at_max = compute_link_margin_db(
        LRO_ALTITUDE_KM,
        UHF_FREQ_MHZ,
        UHF_TX_POWER_W,
        UHF_ANTENNA_GAIN_ROVER_DBI,
        UHF_ANTENNA_GAIN_LRO_DBI,
        UHF_DATARATE_BPS,
    )
    margin_at_edge = compute_link_margin_db(
        math.sqrt(LRO_ORBIT_RADIUS_KM**2 - MOON_RADIUS_KM**2),
        UHF_FREQ_MHZ,
        UHF_TX_POWER_W,
        UHF_ANTENNA_GAIN_ROVER_DBI,
        UHF_ANTENNA_GAIN_LRO_DBI,
        UHF_DATARATE_BPS,
    )

    dur_histogram: dict[str, int] = {
        "0-300s": 0,
        "300-600s": 0,
        "600-900s": 0,
        "900-1200s": 0,
        ">1200s": 0,
    }
    for d in durations_s:
        if d < 300:
            dur_histogram["0-300s"] += 1
        elif d < 600:
            dur_histogram["300-600s"] += 1
        elif d < 900:
            dur_histogram["600-900s"] += 1
        elif d < 1200:
            dur_histogram["900-1200s"] += 1
        else:
            dur_histogram[">1200s"] += 1

    return {
        "simulation_duration_min": sim_duration_min,
        "n_passes_total": n_passes,
        "passes_per_day": round(passes_per_day, 1),
        "total_contact_s": round(total_contact_s, 1),
        "total_contact_min_per_day": round(total_contact_s / 60.0 * 1440.0 / sim_duration_min, 2),
        "contact_fraction_pct": round(total_contact_s / (sim_duration_min * 60.0) * 100.0, 3),
        "mean_pass_duration_s": round(total_contact_s / n_passes, 1),
        "max_pass_duration_s": round(max(durations_s), 1),
        "min_pass_duration_s": round(min(durations_s), 1),
        "mean_max_elevation_deg": round(
            sum(w.max_elevation_deg for w in windows) / n_passes, 2
        ),
        "max_elevation_seen_deg": round(max(w.max_elevation_deg for w in windows), 2),
        "total_data_volume_mb": round(sum(data_volumes_mb), 1),
        "mean_data_per_pass_mb": round(sum(data_volumes_mb) / n_passes, 2),
        "link_margin_db_at_nadir": round(margin_at_max, 1),
        "link_margin_db_at_5deg_elev": round(margin_at_edge, 1),
        "uhf_freq_mhz": UHF_FREQ_MHZ,
        "uhf_datarate_bps": UHF_DATARATE_BPS,
        "duration_histogram": dur_histogram,
        "lro_orbital_params": {
            "altitude_km": LRO_ALTITUDE_KM,
            "inclination_deg": LRO_INCLINATION_DEG,
            "period_min": LRO_PERIOD_MIN,
            "orbit_radius_km": LRO_ORBIT_RADIUS_KM,
        },
        "lpas_ground_station": {
            "name": "LPAS Rover",
            "lat_deg": LPAS_LAT_DEG,
            "lon_deg": LPAS_LON_DEG,
            "elevation_threshold_deg": MIN_ELEVATION_DEG,
        },
        "earth_direct_link": {
            "available": EARTH_DIRECT_AVAILABLE,
            "geometric_reason": (
                "Earth subtends elevation ~ 0 deg as seen from lunar south pole. "
                "Earth declination (geocentric) = 0 deg +/- 1.54 deg (libration only). "
                "At observer latitude -89.9 deg, Earth is permanently at or below horizon. "
                "No direct DSN contact possible at any time during mission."
            ),
            "dsn_link_path": "LPAS UHF -> LRO UHF -> LRO Ka-band -> DSN 34m dish",
            "dsn_stations_used": ["DSS-24 Goldstone", "DSS-54 Madrid", "DSS-43 Tidbinbilla"],
        },
        "contact_windows": [
            {
                "pass_number": i + 1,
                "start_min": round(w.start_min, 2),
                "end_min": round(w.end_min, 2),
                "duration_s": round(w.duration_s, 1),
                "max_elevation_deg": w.max_elevation_deg,
                "max_elev_time_min": w.max_elev_time_min,
                "mean_elevation_deg": w.mean_elevation_deg,
                "slant_range_km_at_max_elev": w.slant_range_km_at_max,
                "data_volume_mb_at_256kbps": w.data_volume_mb,
            }
            for i, w in enumerate(windows)
        ],
    }


def render_ascii_elevation_plot(
    windows: list[ContactWindow],
    sim_duration_min: float,
    width: int = 80,
    height: int = 20,
) -> str:
    passes_per_day = len(windows) * 1440.0 / sim_duration_min
    total_contact_min = sum(w.duration_s for w in windows) / 60.0 * 1440.0 / sim_duration_min
    max_elev = max((w.max_elevation_deg for w in windows), default=0.0)

    lines: list[str] = []
    lines.append("LRO Elevation vs Time (first 1440 min = 1 Earth day)")
    lines.append(f"  Passes/day: {passes_per_day:.1f}  |  Contact: {total_contact_min:.1f} min/day  |  Max elev: {max_elev:.1f} deg")
    lines.append(f"  Min elevation threshold: {MIN_ELEVATION_DEG} deg  |  LRO orbit: {LRO_ALTITUDE_KM} km / {LRO_PERIOD_MIN} min")
    lines.append("")

    day_windows = [w for w in windows if w.start_min < 1440.0]
    if not day_windows:
        lines.append("  (no contact windows in first day)")
        return "\n".join(lines)

    timeline = [" "] * width
    for w in day_windows:
        start_col = int(w.start_min / 1440.0 * width)
        end_col = int(w.end_min / 1440.0 * width)
        start_col = min(start_col, width - 1)
        end_col = min(end_col, width - 1)
        for c in range(start_col, end_col + 1):
            timeline[c] = "#"

    lines.append("  Contact timeline (# = in contact with LRO):")
    lines.append("  0h" + " " * (width - 6) + "24h")
    lines.append("  |" + "".join(timeline) + "|")
    lines.append("")

    lines.append("  Pass durations (s):")
    dur_bins = [0, 300, 600, 900, 1200, 9999]
    dur_labels = ["  0-300s ", "300-600s", "600-900s", "900-1200", " >1200s "]
    bar_width = 40
    all_durations = [w.duration_s for w in windows]
    for label, lo, hi in zip(dur_labels, dur_bins[:-1], dur_bins[1:]):
        count = sum(1 for d in all_durations if lo <= d < hi)
        bar_len = int(count / max(len(all_durations), 1) * bar_width)
        lines.append(f"  {label} | {'|' * bar_len:<{bar_width}} {count}")

    lines.append("")
    lines.append("  Note: Earth is permanently below horizon at lunar south pole.")
    lines.append("  All commanding and downlink must use LRO UHF relay -> DSN.")

    return "\n".join(lines)


def write_contact_statistics_md(
    stats: dict,
    windows: list[ContactWindow],
    output_path: Path,
) -> None:
    lines: list[str] = []
    lines.append("# LPAS LRO Contact Window Analysis")
    lines.append("")
    lines.append(f"**LPAS Ground Station:** {LPAS_LAT_DEG} deg S, {LPAS_LON_DEG} deg E  ")
    lines.append(f"**LRO Orbit:** {LRO_ALTITUDE_KM} km altitude, {LRO_INCLINATION_DEG} deg inclination, {LRO_PERIOD_MIN} min period  ")
    lines.append(f"**Contact Threshold:** Elevation > {MIN_ELEVATION_DEG} deg  ")
    lines.append(f"**UHF Frequency:** {UHF_FREQ_MHZ} MHz  ")
    lines.append(f"**UHF Data Rate:** {UHF_DATARATE_BPS/1000:.0f} kbps  ")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Earth Direct Link Visibility")
    lines.append("")
    lines.append("> **Earth is NOT directly visible from the lunar south pole.**")
    lines.append(">")
    lines.append("> **Geometric basis:** Earth's declination as seen from the Moon is approximately")
    lines.append("> 0 deg +/- 1.54 deg (due to lunar libration only). At observer latitude -89.9 deg S,")
    lines.append("> the horizon elevation of Earth is:")
    lines.append(">")
    lines.append(">   Elev_Earth = 90 deg - (90 deg - observer_lat) - Earth_declination_max")
    lines.append(">             = 90 - 90.1 - 1.54 = -1.64 deg (below horizon)")
    lines.append(">")
    lines.append("> Earth never rises above the horizon at any point during the mission.")
    lines.append("> **All ground communications use the LRO UHF relay -> DSN link.**")
    lines.append("> DSN stations: Goldstone (DSS-24), Madrid (DSS-54), Canberra (DSS-43).")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## LRO UHF Relay Statistics")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Passes per day (normalized) | {stats.get('passes_per_day', 'N/A')} |")
    lines.append(f"| Total contact per day | {stats.get('total_contact_min_per_day', 0):.1f} min |")
    lines.append(f"| Contact fraction | {stats.get('contact_fraction_pct', 0):.3f}% |")
    lines.append(f"| Mean pass duration | {stats.get('mean_pass_duration_s', 0):.0f} s |")
    lines.append(f"| Max pass duration | {stats.get('max_pass_duration_s', 0):.0f} s |")
    lines.append(f"| Min pass duration | {stats.get('min_pass_duration_s', 0):.0f} s |")
    lines.append(f"| Mean max elevation | {stats.get('mean_max_elevation_deg', 0):.1f} deg |")
    lines.append(f"| Max elevation observed | {stats.get('max_elevation_seen_deg', 0):.1f} deg |")
    lines.append(f"| Total data volume (sim period) | {stats.get('total_data_volume_mb', 0):.1f} MB |")
    lines.append(f"| Mean data per pass | {stats.get('mean_data_per_pass_mb', 0):.1f} MB |")
    lines.append(f"| Link margin at nadir | {stats.get('link_margin_db_at_nadir', 0):.1f} dB |")
    lines.append(f"| Link margin at 5 deg elev | {stats.get('link_margin_db_at_5deg_elev', 0):.1f} dB |")
    lines.append("")
    lines.append("## Pass Duration Histogram")
    lines.append("")
    lines.append("| Duration Bin | Count | Bar |")
    lines.append("|---|---|---|")
    hist = stats.get("duration_histogram", {})
    for bin_label, count in hist.items():
        bar = "|" * min(count * 3, 40)
        lines.append(f"| {bin_label} | {count} | {bar} |")
    lines.append("")
    lines.append("## Contact Windows Table (first 20 passes)")
    lines.append("")
    lines.append("| Pass | Start (min) | End (min) | Duration (s) | Max Elev (deg) | Slant Range (km) | Data (MB) |")
    lines.append("|---|---|---|---|---|---|---|")
    for w_dict in stats.get("contact_windows", [])[:20]:
        lines.append(
            f"| {w_dict['pass_number']} "
            f"| {w_dict['start_min']:.1f} "
            f"| {w_dict['end_min']:.1f} "
            f"| {w_dict['duration_s']:.0f} "
            f"| {w_dict['max_elevation_deg']:.1f} "
            f"| {w_dict['slant_range_km_at_max_elev']:.0f} "
            f"| {w_dict['data_volume_mb_at_256kbps']:.1f} |"
        )
    lines.append("")
    lines.append("## Link Budget Summary")
    lines.append("")
    lines.append("| Parameter | Value |")
    lines.append("|---|---|")
    lines.append(f"| UHF frequency | {UHF_FREQ_MHZ} MHz |")
    lines.append(f"| TX power (rover) | {UHF_TX_POWER_W} W |")
    lines.append(f"| Rover antenna gain | {UHF_ANTENNA_GAIN_ROVER_DBI} dBi |")
    lines.append(f"| LRO antenna gain | {UHF_ANTENNA_GAIN_LRO_DBI} dBi |")
    lines.append(f"| Data rate | {UHF_DATARATE_BPS//1000} kbps |")
    lines.append(f"| Max usable range | {UHF_MAX_RANGE_KM} km |")
    lines.append(f"| Link margin at nadir ({LRO_ALTITUDE_KM} km) | {stats.get('link_margin_db_at_nadir', 0):.1f} dB |")
    lines.append(f"| Link margin at 5 deg elevation | {stats.get('link_margin_db_at_5deg_elev', 0):.1f} dB |")
    lines.append("| DSN relay path | LPAS UHF -> LRO UHF -> LRO Ka-band -> DSN 34m |")

    output_path.write_text("\n".join(lines))
    print(f"  Saved contact_statistics.md -> {output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze LRO communication windows for LPAS at the lunar south pole."
    )
    parser.add_argument(
        "--sim_days",
        type=float,
        default=1.0,
        help="Simulation duration in Earth days (default: 1.0).",
    )
    parser.add_argument(
        "--dt_min",
        type=float,
        default=SIMULATION_DT_MIN,
        help=f"Time step in minutes (default: {SIMULATION_DT_MIN}).",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Output directory for contact reports (default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--elevation_threshold_deg",
        type=float,
        default=MIN_ELEVATION_DEG,
        help=f"Minimum LRO elevation angle for contact in degrees (default: {MIN_ELEVATION_DEG}).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    sim_duration_min = args.sim_days * 1440.0

    print("=== LPAS LRO Comm Visibility Analysis ===")
    print(f"  LPAS position        : {LPAS_LAT_DEG} deg S, {LPAS_LON_DEG} deg E (Shackleton rim)")
    print(f"  LRO orbit            : {LRO_ALTITUDE_KM} km alt / {LRO_INCLINATION_DEG} deg incl / {LRO_PERIOD_MIN} min period")
    print(f"  Elevation threshold  : {MIN_ELEVATION_DEG} deg")
    print(f"  Simulation duration  : {args.sim_days:.1f} days ({sim_duration_min:.0f} min)")
    print(f"  Time step            : {args.dt_min} min")
    print(f"  Earth direct link    : NOT AVAILABLE (permanently below horizon)")

    print("\n[1/4] Simulating LRO passes...")
    windows = simulate_lro_passes(sim_duration_min, args.dt_min)
    print(f"  Found {len(windows)} contact windows in {args.sim_days:.1f} day(s).")

    print("\n[2/4] Computing statistics...")
    stats = compute_statistics(windows, sim_duration_min)

    print("\n[3/4] Saving daily_contact_windows.json...")
    json_path = output_dir / "daily_contact_windows.json"
    with open(json_path, "w") as f:
        json.dump(stats, f, indent=2)
    print(f"  Saved -> {json_path}")

    print("\n[4/4] Writing contact_statistics.md...")
    md_path = output_dir / "contact_statistics.md"
    write_contact_statistics_md(stats, windows, md_path)

    ascii_plot = render_ascii_elevation_plot(windows, sim_duration_min)
    print("\n" + ascii_plot)

    print("\n=== Summary ===")
    print(f"  Passes per day            : {stats['passes_per_day']}")
    print(f"  Contact time per day      : {stats['total_contact_min_per_day']:.1f} min")
    print(f"  Contact fraction          : {stats['contact_fraction_pct']:.3f}%")
    print(f"  Mean pass duration        : {stats['mean_pass_duration_s']:.0f} s")
    print(f"  Max pass duration         : {stats['max_pass_duration_s']:.0f} s")
    print(f"  Mean max elevation        : {stats['mean_max_elevation_deg']:.1f} deg")
    print(f"  Total data volume         : {stats['total_data_volume_mb']:.1f} MB")
    print(f"  Link margin (nadir)       : {stats['link_margin_db_at_nadir']:.1f} dB")
    print(f"  Link margin (5 deg elev)  : {stats['link_margin_db_at_5deg_elev']:.1f} dB")
    print(f"  Earth direct link         : {EARTH_DIRECT_AVAILABLE} (relay-only via LRO -> DSN)")
    print("\nDone.")


if __name__ == "__main__":
    main()
