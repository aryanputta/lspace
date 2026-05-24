// power_monitor.hpp — real-time power system state tracking
#pragma once

#include <array>
#include <cmath>
#include <cstdint>
#include <limits>

namespace lpas {

// Load priority table (lower = higher priority, always powered)
enum class LoadPriority : uint8_t {
    SAFETY_CRITICAL = 0,  // fault detection, heaters
    MOBILITY        = 1,  // wheel motors
    AVIONICS        = 2,  // flight computer, IMU
    COMMS           = 3,  // UHF, HGA
    SCIENCE         = 4,  // drill, spectrometers
    IMAGING         = 5,  // cameras
    NON_ESSENTIAL   = 6,
};

struct LoadRecord {
    const char*   name;
    LoadPriority  priority;
    float         nominal_w;
    float         peak_w;
    bool          enabled;
};

// Battery state
struct BatteryState {
    float soc;            // 0.0–1.0
    float voltage_v;
    float current_a;      // positive = charging, negative = discharging
    float temperature_c;
    float capacity_wh;
    float remaining_wh;

    float time_to_empty_h() const noexcept {
        if (current_a >= 0.0f) return std::numeric_limits<float>::infinity();
        float power_w = -current_a * voltage_v;
        return (power_w > 0.01f) ? remaining_wh / power_w : 99.0f;
    }

    // LFP discharge curve: approximate OCV vs SOC
    float ocv_from_soc(float soc_frac) const noexcept {
        // LFP: flat ~3.2–3.3V from 20–90% SOC, drops at extremes
        if (soc_frac > 0.9f)  return 3.40f + (soc_frac - 0.9f) * 0.5f;
        if (soc_frac < 0.15f) return 2.80f + soc_frac * 2.67f;
        return 3.20f + (soc_frac - 0.15f) * 0.13f;  // flat plateau
    }

    // Temperature derating factor (LFP cold performance)
    float temp_derate() const noexcept {
        if (temperature_c >= 20.0f)  return 1.0f;
        if (temperature_c >= 0.0f)   return 1.0f - (20.0f - temperature_c) * 0.01f;
        if (temperature_c >= -10.0f) return 0.80f + (temperature_c + 10.0f) * 0.02f;
        return 0.60f;  // below -10°C: 60% capacity
    }
};

// Solar array state
struct SolarState {
    float irradiance_w_m2;  // W/m²
    float array_temp_c;
    float array_area_m2;
    float cell_efficiency;  // BOL efficiency

    float power_output_w() const noexcept {
        // Temperature coefficient: GaAs ≈ -0.2%/°C from 28°C reference
        float temp_coeff = 1.0f - 0.002f * (array_temp_c - 28.0f);
        return irradiance_w_m2 * array_area_m2 * cell_efficiency * temp_coeff;
    }
};

// Power system state machine
enum class PowerMode : uint8_t {
    FULL_POWER     = 0,   // All loads enabled
    REDUCED        = 1,   // Science payload shed
    SAFE_MINIMUM   = 2,   // Only avionics + heaters
    SURVIVAL       = 3,   // Battery critical, minimum draw
    CHARGING       = 4,   // Stationary, charging battery
};

class PowerMonitor {
public:
    static constexpr float BATTERY_CAPACITY_WH   = 150.0f;
    static constexpr float LOW_SOC_THRESHOLD      = 0.20f;
    static constexpr float CRITICAL_SOC_THRESHOLD = 0.10f;
    static constexpr float FULL_SOC_THRESHOLD     = 0.90f;

    explicit PowerMonitor() noexcept {
        battery_.capacity_wh  = BATTERY_CAPACITY_WH;
        battery_.remaining_wh = BATTERY_CAPACITY_WH * 0.8f;
        battery_.soc          = 0.8f;
        battery_.voltage_v    = 28.0f;
        battery_.temperature_c = 20.0f;
        solar_.array_area_m2   = 1.2f;
        solar_.cell_efficiency = 0.295f;
        solar_.irradiance_w_m2 = 0.0f;
    }

    void update(float solar_irr_w_m2, float total_load_w, float dt_s) noexcept {
        solar_.irradiance_w_m2 = solar_irr_w_m2;
        float solar_power = solar_.power_output_w();
        float net_power   = solar_power - total_load_w;  // + = charging

        // Integrate energy
        battery_.remaining_wh += (net_power / 3600.0f) * dt_s;
        battery_.remaining_wh = std::clamp(
            battery_.remaining_wh, 0.0f, BATTERY_CAPACITY_WH);

        battery_.soc     = battery_.remaining_wh / BATTERY_CAPACITY_WH
                           * battery_.temp_derate();
        battery_.current_a = net_power / battery_.voltage_v;

        update_mode();
    }

    PowerMode mode() const noexcept { return mode_; }
    const BatteryState& battery() const noexcept { return battery_; }
    const SolarState& solar() const noexcept { return solar_; }

    float available_power_w() const noexcept {
        return solar_.power_output_w()
               + (battery_.soc > CRITICAL_SOC_THRESHOLD
                  ? battery_.remaining_wh * 3600.0f / 3600.0f  // 1h discharge rate
                  : 0.0f);
    }

private:
    BatteryState battery_{};
    SolarState   solar_{};
    PowerMode    mode_{ PowerMode::FULL_POWER };

    void update_mode() noexcept {
        if (battery_.soc <= CRITICAL_SOC_THRESHOLD) {
            mode_ = PowerMode::SURVIVAL;
        } else if (battery_.soc <= LOW_SOC_THRESHOLD) {
            mode_ = PowerMode::SAFE_MINIMUM;
        } else if (battery_.soc >= FULL_SOC_THRESHOLD
                   && solar_.power_output_w() > 50.0f) {
            mode_ = PowerMode::FULL_POWER;
        } else if (mode_ == PowerMode::SURVIVAL && battery_.soc > 0.15f) {
            mode_ = PowerMode::REDUCED;
        }
    }
};

}  // namespace lpas
