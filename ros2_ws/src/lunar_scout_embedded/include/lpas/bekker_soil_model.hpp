// bekker_soil_model.hpp — Bekker pressure-sinkage model for lunar regolith
#pragma once

#include <cmath>
#include <array>
#include <stdexcept>

namespace lpas {

// Lunar regolith parameters (Heiken et al. 1991 / Carrier et al. 1991)
struct RegolithParams {
    double cohesion_kpa       = 0.17;   // c  [kPa]
    double friction_angle_deg = 35.0;   // φ  [deg]
    double kc_kpa             = 0.9;    // Bekker k_c
    double kphi_kpa           = 1523.0; // Bekker k_φ
    double n_exponent         = 1.1;    // sinkage exponent
    double shear_deform_m     = 0.018;  // K  [m]
    double density_kg_m3      = 1500.0; // bulk density
};

struct WheelParams {
    double radius_m   = 0.25;
    double width_m    = 0.175;
    double load_n     = 360.0;  // Per wheel: (202 kg * 1.62 m/s²) / 6
};

struct SinkageResult {
    double sinkage_m;        // wheel sinkage [m]
    double contact_area_m2;  // contact patch area
    double contact_pressure_kpa;
    double tractive_force_n; // Mohr-Coulomb max traction
    double slip_critical;    // slip ratio at traction limit
};

// Bekker pressure-sinkage: p = (kc/b + kφ) * z^n
inline double bekker_pressure(
    const RegolithParams& soil, double width_m, double sinkage_m) noexcept
{
    return (soil.kc_kpa / width_m + soil.kphi_kpa)
           * std::pow(sinkage_m, soil.n_exponent);
}

// Iterative sinkage solver (Newton-Raphson, 20 iterations max)
inline double solve_sinkage(
    const RegolithParams& soil,
    const WheelParams& wheel,
    double tol = 1e-6)
{
    // Contact area approximation for cylindrical wheel:
    // A ≈ b * sqrt(2 * r * z)  (Hertz contact approximation)
    double z = 0.02;  // initial guess 2cm
    for (int i = 0; i < 20; ++i) {
        double b = wheel.width_m;
        double r = wheel.radius_m;
        double contact_len = std::sqrt(2.0 * r * z);
        double area = b * contact_len;
        double p_avg = bekker_pressure(soil, b, z);
        double f_calc = p_avg * area * 1000.0;  // kPa → Pa, then × m² = N
        double err = f_calc - wheel.load_n;
        if (std::abs(err) < tol * wheel.load_n) break;
        // Derivative approximation
        double dz = z * 0.001;
        double df = (bekker_pressure(soil, b, z + dz)
                     * b * std::sqrt(2.0 * r * (z + dz)) * 1000.0
                     - f_calc) / dz;
        if (std::abs(df) < 1e-12) break;
        z -= err / df;
        if (z < 1e-6) z = 1e-6;
        if (z > wheel.radius_m) z = wheel.radius_m * 0.8;
    }
    return z;
}

inline SinkageResult compute_sinkage(
    const RegolithParams& soil, const WheelParams& wheel)
{
    SinkageResult result{};
    result.sinkage_m = solve_sinkage(soil, wheel);

    double b = wheel.width_m;
    double r = wheel.radius_m;
    double z = result.sinkage_m;

    result.contact_area_m2 = b * std::sqrt(2.0 * r * z);
    result.contact_pressure_kpa = bekker_pressure(soil, b, z);

    // Mohr-Coulomb shear strength: τ = c + σ·tan(φ)
    double phi_rad = soil.friction_angle_deg * M_PI / 180.0;
    double tau_max = (soil.cohesion_kpa
                      + result.contact_pressure_kpa * std::tan(phi_rad));
    result.tractive_force_n = tau_max * result.contact_area_m2 * 1000.0;

    // Critical slip ratio from Janosi-Hanamoto shear model
    result.slip_critical = soil.shear_deform_m / (r * std::acos(1.0 - z / r));

    return result;
}

// Wong-Reece tractive force with slip: F_t = (c·A + W·tan(φ)) * (1 - K/(j) * (1 - exp(-j/K)))
// j = slip displacement = r * θ * slip_ratio
inline double tractive_force_with_slip(
    const RegolithParams& soil,
    const WheelParams& wheel,
    const SinkageResult& sinkage,
    double slip_ratio)
{
    double phi_rad = soil.friction_angle_deg * M_PI / 180.0;
    double A = sinkage.contact_area_m2;
    double W = wheel.load_n;
    double K = soil.shear_deform_m;

    // Contact angle
    double theta = std::acos(1.0 - sinkage.sinkage_m / wheel.radius_m);
    double j = wheel.radius_m * theta * std::abs(slip_ratio);
    if (j < 1e-9) return 0.0;

    double F_max = (soil.cohesion_kpa * 1000.0 * A + W * std::tan(phi_rad));
    double F_t = F_max * (1.0 - (K / j) * (1.0 - std::exp(-j / K)));
    return std::copysign(F_t, slip_ratio);
}

}  // namespace lpas
