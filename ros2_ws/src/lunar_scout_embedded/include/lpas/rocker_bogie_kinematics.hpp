// rocker_bogie_kinematics.hpp — 6-wheel rocker-bogie inverse kinematics
#pragma once

#include <array>
#include <cmath>
#include <stdexcept>

namespace lpas {

// Rover geometry constants
struct RoverGeometry {
    double wheel_radius_m    = 0.25;
    double track_width_m     = 1.75;   // left-to-right center distance
    double wheelbase_m       = 0.95;   // front-to-rear axle distance
    double rocker_length_m   = 0.70;
    double bogie_length_m    = 0.50;
    double bogie_pivot_x_m   = 0.20;  // bogie pivot offset from mid-wheel
};

// 6-wheel velocity commands [FL, ML, RL, FR, MR, RR] (rad/s)
using WheelVelocities = std::array<double, 6>;

// Indices
constexpr int FL = 0, ML = 1, RL = 2;
constexpr int FR = 3, MR = 4, RR = 5;

struct TwistCmd {
    double linear_x;   // m/s
    double angular_z;  // rad/s
};

// Kinematic limits
constexpr double MAX_WHEEL_SPEED_RAD_S = 2.0;
constexpr double MAX_LINEAR_MPS        = 0.5;
constexpr double MAX_ANGULAR_RADPS     = 0.3;

// Differential drive → 6-wheel velocities
// Outer wheels turn faster; inner wheels turn slower
// Mid-wheel velocity = average of front/rear to minimize scrub
inline WheelVelocities compute_wheel_velocities(
    const TwistCmd& cmd, const RoverGeometry& geo)
{
    // Saturate command
    double lin = std::clamp(cmd.linear_x,  -MAX_LINEAR_MPS,    MAX_LINEAR_MPS);
    double ang = std::clamp(cmd.angular_z, -MAX_ANGULAR_RADPS, MAX_ANGULAR_RADPS);

    double v_left  = lin - ang * geo.track_width_m * 0.5;
    double v_right = lin + ang * geo.track_width_m * 0.5;

    double omega_left  = v_left  / geo.wheel_radius_m;
    double omega_right = v_right / geo.wheel_radius_m;

    // Clamp per-wheel
    auto sat = [](double v) noexcept -> double {
        return std::clamp(v, -MAX_WHEEL_SPEED_RAD_S, MAX_WHEEL_SPEED_RAD_S);
    };

    WheelVelocities w{};
    w[FL] = sat(omega_left);
    w[ML] = sat(omega_left);   // rocker-bogie: all same side same speed
    w[RL] = sat(omega_left);
    w[FR] = sat(omega_right);
    w[MR] = sat(omega_right);
    w[RR] = sat(omega_right);

    return w;
}

// Forward kinematics: wheel speeds → body twist (dead reckoning)
inline TwistCmd wheel_velocities_to_twist(
    const WheelVelocities& w, const RoverGeometry& geo)
{
    double omega_left  = (w[FL] + w[ML] + w[RL]) / 3.0;
    double omega_right = (w[FR] + w[MR] + w[RR]) / 3.0;

    double v_left  = omega_left  * geo.wheel_radius_m;
    double v_right = omega_right * geo.wheel_radius_m;

    return TwistCmd{
        .linear_x  = (v_left + v_right) * 0.5,
        .angular_z = (v_right - v_left) / geo.track_width_m,
    };
}

// Compute chassis roll from rocker angle differential (left vs right rocker)
// Provides attitude estimate on rough terrain
inline double estimate_chassis_roll(
    double rocker_left_angle_rad,
    double rocker_right_angle_rad,
    const RoverGeometry& geo)
{
    double delta_height = (std::sin(rocker_left_angle_rad)
                           - std::sin(rocker_right_angle_rad))
                          * geo.rocker_length_m * 0.5;
    return std::atan2(delta_height, geo.track_width_m);
}

// Per-wheel slip ratio: (v_wheel_body - v_actual) / max(|v_wheel_body|, ε)
inline double compute_slip_ratio(
    double wheel_omega_rad_s,
    double body_speed_m_s,
    double wheel_radius_m) noexcept
{
    constexpr double eps = 0.01;
    double v_wheel = wheel_omega_rad_s * wheel_radius_m;
    double denom = std::max(std::abs(v_wheel), eps);
    return (v_wheel - body_speed_m_s) / denom;
}

// Traction control: reduce wheel speed if slip exceeds limit
inline WheelVelocities traction_control(
    const WheelVelocities& commanded,
    const std::array<double, 6>& slip_ratios,
    double slip_limit = 0.35) noexcept
{
    WheelVelocities corrected = commanded;
    for (int i = 0; i < 6; ++i) {
        double s = std::abs(slip_ratios[i]);
        if (s > slip_limit) {
            double scale = slip_limit / s;
            corrected[i] *= scale;
        }
    }
    return corrected;
}

}  // namespace lpas
