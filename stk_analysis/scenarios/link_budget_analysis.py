"""
link_budget_analysis.py
Lunar PSR Autonomy Scout (LPAS) — RF Link Budget Calculator

Computes:
  1. UHF rover-to-relay link budget (437.525 MHz, BPSK 128 kbps)
  2. Ka-band relay-to-Earth link budget (26 GHz, DSN 70-m dish)

Outputs:
  - Printed formatted table
  - stk_analysis/comm_windows/link_budget_report.json

Usage:
    python link_budget_analysis.py

Dependencies: numpy (optional; all math is standard-library-compatible)
"""

import math
import json
import os
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "comm_windows"

# Physical constants
SPEED_OF_LIGHT_MPS = 299_792_458.0   # m/s
BOLTZMANN_DB        = -228.6          # 10*log10(k_B) dBW/K/Hz  (k_B = 1.380649e-23)
KELVIN_0_C          = 273.15


def db(x: float) -> float:
    """Linear to dB."""
    return 10.0 * math.log10(x)


def from_db(x_db: float) -> float:
    """dB to linear."""
    return 10.0 ** (x_db / 10.0)


def fspl_db(distance_m: float, freq_hz: float) -> float:
    """
    Free-space path loss (dB).
    FSPL = 20*log10(4 * pi * d * f / c)
    """
    return 20.0 * math.log10(4 * math.pi * distance_m * freq_hz / SPEED_OF_LIGHT_MPS)


def noise_power_db(T_sys_K: float, bandwidth_hz: float) -> float:
    """
    Thermal noise power in dBW.
    N = k_B * T_sys * B
    """
    return BOLTZMANN_DB + db(T_sys_K) + db(bandwidth_hz)


def noise_figure_to_noise_temp_K(nf_db: float, T_ref_K: float = 290.0) -> float:
    """Convert noise figure (dB) to equivalent noise temperature (K)."""
    nf_lin = from_db(nf_db)
    return T_ref_K * (nf_lin - 1.0)


def parabolic_dish_gain_dbi(diameter_m: float, freq_hz: float,
                             efficiency: float = 0.60) -> float:
    """
    Parabolic dish on-axis gain (dBi).
    G = eta * (pi * D / lambda)^2
    """
    wavelength_m = SPEED_OF_LIGHT_MPS / freq_hz
    G_lin = efficiency * (math.pi * diameter_m / wavelength_m) ** 2
    return db(G_lin)


def required_Eb_N0_bpsk_db(ber: float = 1e-5) -> float:
    """
    Required Eb/N0 for coherent BPSK to achieve target BER.
    BER = 0.5 * erfc(sqrt(Eb/N0))  →  Eb/N0 = (erfc_inv(2*BER))^2
    For BER=1e-5: Eb/N0 ~ 9.59 dB  (tabulated, matches standard refs)
    """
    # Table lookup (standard BPSK waterfall):
    table = {
        1e-3: 6.79,
        1e-4: 8.40,
        1e-5: 9.59,
        1e-6: 10.53,
    }
    return table.get(ber, 9.59)


# ===========================================================================
# LINK 1: UHF Rover → Relay Station
# ===========================================================================

def compute_uhf_link(
    tx_power_W: float     = 5.0,
    tx_gain_dBi: float    = 5.0,
    rx_gain_dBi: float    = 8.0,
    freq_MHz: float       = 437.525,
    data_rate_bps: float  = 128_000,
    fec_rate: float       = 0.5,        # rate-1/2 Turbo code
    T_sys_K: float        = 300.0,
    req_ber: float        = 1e-5,
    required_margin_dB: float = 3.0,
    distances_m: list     = None,
) -> dict:
    """
    Compute UHF rover-to-relay link budget at multiple range values.

    Parameters
    ----------
    distances_m : list of floats
        Rover-to-relay ranges to evaluate [m].  Default: [100, 250, 500, 1000, 2000, 5000].
    """
    if distances_m is None:
        distances_m = [100, 250, 500, 1000, 2000, 5000]

    freq_hz = freq_MHz * 1e6
    wavelength_m = SPEED_OF_LIGHT_MPS / freq_hz

    # Transmitter
    tx_power_dBW   = db(tx_power_W)
    eirp_dBW       = tx_power_dBW + tx_gain_dBi

    # Receiver noise
    N0_dBW_Hz = BOLTZMANN_DB + db(T_sys_K)                # noise spectral density

    # Bandwidth
    symbol_rate_bps = data_rate_bps / fec_rate             # 256 ksps after FEC overhead
    noise_bw_hz     = symbol_rate_bps * 1.25               # 25% excess (Nyquist shaping)

    # Required Eb/N0
    req_EbN0_dB = required_Eb_N0_bpsk_db(req_ber)         # 9.59 dB

    # Required C/N0  = Eb/N0 + 10*log10(data_rate)
    req_CN0_dB = req_EbN0_dB + db(data_rate_bps)          # dBHz

    print("\n" + "=" * 70)
    print("UHF ROVER-TO-RELAY LINK BUDGET  (437.525 MHz, BPSK, 128 kbps)")
    print("=" * 70)
    print(f"  TX Power        : {tx_power_W:.1f} W = {tx_power_dBW:+.2f} dBW")
    print(f"  TX Antenna Gain : {tx_gain_dBi:+.1f} dBi  (stub helix)")
    print(f"  EIRP            : {eirp_dBW:+.2f} dBW")
    print(f"  Frequency       : {freq_MHz:.3f} MHz")
    print(f"  Wavelength      : {wavelength_m*100:.1f} cm")
    print(f"  RX Antenna Gain : {rx_gain_dBi:+.1f} dBi  (Yagi-Uda, 5 el.)")
    print(f"  System Noise T  : {T_sys_K:.0f} K")
    print(f"  G/T             : {rx_gain_dBi - db(T_sys_K):+.2f} dB/K")
    print(f"  N0              : {N0_dBW_Hz:+.2f} dBW/Hz")
    print(f"  Data Rate       : {data_rate_bps/1000:.0f} kbps")
    print(f"  FEC Rate        : 1/{int(1/fec_rate)}")
    print(f"  Req. Eb/N0      : {req_EbN0_dB:.2f} dB  (BPSK, BER {req_ber:.0e})")
    print(f"  Req. C/N0       : {req_CN0_dB:.2f} dBHz")
    print(f"  Required Margin : {required_margin_dB:.1f} dB")
    print()
    print(f"  {'Range (m)':>12}  {'FSPL (dB)':>10}  {'Rx Power (dBW)':>16}  "
          f"{'C/N0 (dBHz)':>12}  {'Eb/N0 (dB)':>12}  {'Margin (dB)':>12}  {'Status':>8}")
    print("  " + "-" * 90)

    results = []
    for d in distances_m:
        fspl   = fspl_db(d, freq_hz)
        rx_pwr = eirp_dBW - fspl + rx_gain_dBi          # dBW (free space)
        cn0    = rx_pwr - N0_dBW_Hz                      # dBHz
        ebn0   = cn0 - db(data_rate_bps)                 # dB
        margin = ebn0 - req_EbN0_dB - required_margin_dB
        status = "PASS" if margin >= 0 else "FAIL"

        print(f"  {d:>12.0f}  {fspl:>10.2f}  {rx_pwr:>+16.2f}  "
              f"{cn0:>12.2f}  {ebn0:>12.2f}  {margin:>+12.2f}  {status:>8}")

        results.append({
            "range_m":        d,
            "fspl_dB":        round(fspl, 2),
            "rx_power_dBW":   round(rx_pwr, 2),
            "cn0_dBHz":       round(cn0, 2),
            "ebn0_dB":        round(ebn0, 2),
            "link_margin_dB": round(margin, 2),
            "status":         status,
        })

    max_range_m = next(
        (r["range_m"] for r in reversed(results) if r["status"] == "PASS"),
        0
    )
    print(f"\n  Maximum range for {required_margin_dB} dB margin: {max_range_m:.0f} m")
    print("=" * 70)

    return {
        "link_name":          "UHF Rover-to-Relay",
        "frequency_MHz":      freq_MHz,
        "modulation":         "BPSK",
        "data_rate_kbps":     data_rate_bps / 1000,
        "fec":                f"Turbo rate-1/{int(1/fec_rate)}",
        "tx_power_W":         tx_power_W,
        "tx_power_dBW":       round(tx_power_dBW, 2),
        "tx_gain_dBi":        tx_gain_dBi,
        "eirp_dBW":           round(eirp_dBW, 2),
        "rx_gain_dBi":        rx_gain_dBi,
        "system_noise_temp_K": T_sys_K,
        "G_over_T_dBK":       round(rx_gain_dBi - db(T_sys_K), 2),
        "N0_dBW_Hz":          round(N0_dBW_Hz, 2),
        "req_EbN0_dB":        round(req_EbN0_dB, 2),
        "req_margin_dB":      required_margin_dB,
        "max_range_m":        max_range_m,
        "range_sweep":        results,
    }


# ===========================================================================
# LINK 2: Ka-Band Relay → Earth (DSN 70-m Goldstone)
# ===========================================================================

def compute_ka_link(
    tx_power_W: float        = 20.0,
    tx_dish_diam_m: float    = 0.5,
    tx_dish_efficiency: float = 0.60,
    freq_GHz: float          = 26.0,
    rx_gain_dBi: float       = 74.2,    # DSN 70-m at 26 GHz
    T_sys_K: float           = 25.0,    # DSN 70-m system temp
    rx_noise_fig_dB: float   = 1.5,     # includes feed + LNA
    atm_loss_dB: float       = 0.5,
    req_snr_dB: float        = 12.0,
    required_margin_dB: float = 3.0,
    ranges_km: list          = None,
) -> dict:
    """
    Compute Ka-band relay-to-Earth (DSN) link budget.
    """
    if ranges_km is None:
        ranges_km = [356_400, 384_400, 405_500, 350_000, 400_000, 406_700]

    freq_hz = freq_GHz * 1e9
    tx_power_dBW = db(tx_power_W)

    # Transmit dish gain
    tx_gain_dBi = parabolic_dish_gain_dbi(tx_dish_diam_m, freq_hz, tx_dish_efficiency)
    eirp_dBW    = tx_power_dBW + tx_gain_dBi

    # DSN receiver
    # Noise temperature: combine sky (3K) + atm (~20K @ low elev) + LNA
    T_rx_K = noise_figure_to_noise_temp_K(rx_noise_fig_dB, T_ref_K=290.0)
    # total system temp (feedlines, sky, etc. already in the given T_sys_K)
    G_over_T_dB = rx_gain_dBi - db(T_sys_K)

    # Noise bandwidth — assume 1 MHz symbol rate downlink
    symbol_rate_hz = 1_024_000   # 1.024 Msps (1 Mbps BPSK after FEC)
    noise_bw_hz    = symbol_rate_hz * 1.2

    N_dBW  = BOLTZMANN_DB + db(T_sys_K) + db(noise_bw_hz)   # total noise power

    print("\n" + "=" * 70)
    print(f"Ka-BAND RELAY-TO-EARTH LINK BUDGET  ({freq_GHz:.1f} GHz, DSN Goldstone 70 m)")
    print("=" * 70)
    print(f"  TX Power         : {tx_power_W:.1f} W = {tx_power_dBW:+.2f} dBW")
    print(f"  TX Dish Diameter : {tx_dish_diam_m:.2f} m")
    print(f"  TX Dish Gain     : {tx_gain_dBi:+.2f} dBi  (eta={tx_dish_efficiency:.2f})")
    print(f"  EIRP             : {eirp_dBW:+.2f} dBW")
    print(f"  Frequency        : {freq_GHz:.1f} GHz")
    print(f"  Wavelength       : {1000*SPEED_OF_LIGHT_MPS/(freq_hz):.2f} mm")
    print(f"  Atmospheric Loss : {atm_loss_dB:.1f} dB")
    print(f"  RX Dish Gain     : {rx_gain_dBi:+.1f} dBi  (DSN 70-m)")
    print(f"  System Temp      : {T_sys_K:.0f} K")
    print(f"  G/T              : {G_over_T_dB:+.2f} dB/K")
    print(f"  RX Noise Fig     : {rx_noise_fig_dB:.1f} dB")
    print(f"  Symbol Rate      : {symbol_rate_hz/1e3:.0f} ksps")
    print(f"  Noise BW         : {noise_bw_hz/1e3:.0f} kHz")
    print(f"  Req. SNR         : {req_snr_dB:.1f} dB")
    print(f"  Required Margin  : {required_margin_dB:.1f} dB")
    print()
    print(f"  {'Range (km)':>12}  {'FSPL (dB)':>10}  {'Rx Signal (dBW)':>16}  "
          f"{'SNR (dB)':>10}  {'Margin (dB)':>12}  {'Status':>8}")
    print("  " + "-" * 75)

    results = []
    for d_km in sorted(set(ranges_km)):
        d_m    = d_km * 1000.0
        fspl   = fspl_db(d_m, freq_hz)
        rx_sig = eirp_dBW - fspl - atm_loss_dB + rx_gain_dBi   # dBW
        snr    = rx_sig - N_dBW
        margin = snr - req_snr_dB - required_margin_dB
        status = "PASS" if margin >= 0 else "FAIL"

        print(f"  {d_km:>12,.0f}  {fspl:>10.2f}  {rx_sig:>+16.2f}  "
              f"{snr:>10.2f}  {margin:>+12.2f}  {status:>8}")

        results.append({
            "range_km":        d_km,
            "fspl_dB":         round(fspl, 2),
            "rx_signal_dBW":   round(rx_sig, 2),
            "snr_dB":          round(snr, 2),
            "link_margin_dB":  round(margin, 2),
            "status":          status,
        })

    # Nominal (384,400 km) margin
    nom = next((r for r in results if r["range_km"] == 384_400), results[0])
    print(f"\n  Nominal range (384,400 km) SNR  : {nom['snr_dB']:.2f} dB")
    print(f"  Nominal range link margin       : {nom['link_margin_dB']:+.2f} dB")
    print("=" * 70)

    return {
        "link_name":             "Ka-Band Relay-to-Earth",
        "frequency_GHz":         freq_GHz,
        "modulation":            "BPSK",
        "symbol_rate_ksps":      symbol_rate_hz / 1000,
        "tx_power_W":            tx_power_W,
        "tx_power_dBW":          round(tx_power_dBW, 2),
        "tx_dish_diameter_m":    tx_dish_diam_m,
        "tx_dish_gain_dBi":      round(tx_gain_dBi, 2),
        "eirp_dBW":              round(eirp_dBW, 2),
        "atmospheric_loss_dB":   atm_loss_dB,
        "rx_gain_dBi":           rx_gain_dBi,
        "system_temp_K":         T_sys_K,
        "G_over_T_dBK":          round(G_over_T_dB, 2),
        "rx_noise_fig_dB":       rx_noise_fig_dB,
        "req_snr_dB":            req_snr_dB,
        "req_margin_dB":         required_margin_dB,
        "nominal_snr_dB":        nom["snr_dB"],
        "nominal_margin_dB":     nom["link_margin_dB"],
        "range_sweep":           results,
    }


# ===========================================================================
# Summary and JSON output
# ===========================================================================

def main():
    print("\nLPAS RF Link Budget Analysis")
    print("Lunar PSR Autonomy Scout — Communications Subsystem")
    print()

    # --- UHF Link ---
    uhf = compute_uhf_link(
        tx_power_W     = 5.0,
        tx_gain_dBi    = 5.0,
        rx_gain_dBi    = 8.0,
        freq_MHz       = 437.525,
        data_rate_bps  = 128_000,
        fec_rate       = 0.5,
        T_sys_K        = 300.0,
        req_ber        = 1e-5,
        required_margin_dB = 3.0,
        distances_m    = [50, 100, 250, 500, 1000, 2000, 3000, 5000, 10_000],
    )

    # --- Ka-Band Link ---
    ka = compute_ka_link(
        tx_power_W         = 20.0,
        tx_dish_diam_m     = 0.5,
        tx_dish_efficiency = 0.60,
        freq_GHz           = 26.0,
        rx_gain_dBi        = 74.2,
        T_sys_K            = 25.0,
        rx_noise_fig_dB    = 1.5,
        atm_loss_dB        = 0.5,
        req_snr_dB         = 12.0,
        required_margin_dB = 3.0,
        ranges_km          = [350_000, 356_400, 384_400, 400_000, 405_500, 406_700],
    )

    # --- Verification checks ---
    print("\n" + "=" * 70)
    print("LINK BUDGET SUMMARY")
    print("=" * 70)

    uhf_nom = next(r for r in uhf["range_sweep"] if r["range_m"] == 500)
    print(f"\n  UHF Link @ 500 m nominal range:")
    print(f"    Eb/N0        = {uhf_nom['ebn0_dB']:.2f} dB")
    print(f"    Link Margin  = {uhf_nom['link_margin_dB']:+.2f} dB  (req >= 0 dB)")
    print(f"    Status       = {uhf_nom['status']}")

    ka_nom = next(r for r in ka["range_sweep"] if r["range_km"] == 384_400)
    print(f"\n  Ka-Band Link @ 384,400 km nominal range:")
    print(f"    SNR          = {ka_nom['snr_dB']:.2f} dB")
    print(f"    Link Margin  = {ka_nom['link_margin_dB']:+.2f} dB  (req >= 0 dB)")
    print(f"    Status       = {ka_nom['status']}")
    print("=" * 70)

    # --- Write JSON report ---
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "mission": "Lunar PSR Autonomy Scout (LPAS)",
        "document": "RF Link Budget Analysis",
        "links": [uhf, ka],
    }
    out_path = OUTPUT_DIR / "link_budget_report.json"
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  [+] JSON report written: {out_path}")


if __name__ == "__main__":
    main()
