// test_rocker_bogie_kinematics.cpp — unit tests for rocker-bogie kinematics
#include <gtest/gtest.h>
#include "lpas/rocker_bogie_kinematics.hpp"

using namespace lpas;

TEST(RockerBogie, ZeroCommandGivesZeroVelocities) {
    TwistCmd cmd{0.0, 0.0};
    RoverGeometry geo{};
    auto v = compute_wheel_velocities(cmd, geo);
    for (auto vi : v) EXPECT_NEAR(vi, 0.0, 1e-9);
}

TEST(RockerBogie, PureForwardGivesEqualSideSpeeds) {
    TwistCmd cmd{0.3, 0.0};
    RoverGeometry geo{};
    auto v = compute_wheel_velocities(cmd, geo);
    // Left and right should be equal for straight-line
    EXPECT_NEAR(v[FL], v[FR], 1e-9);
    EXPECT_NEAR(v[ML], v[MR], 1e-9);
    EXPECT_NEAR(v[RL], v[RR], 1e-9);
    // All left-side wheels same speed
    EXPECT_NEAR(v[FL], v[ML], 1e-9);
    EXPECT_NEAR(v[ML], v[RL], 1e-9);
}

TEST(RockerBogie, LeftTurnInnerWheelsSlower) {
    TwistCmd cmd{0.3, 0.2};  // turn right → right wheels faster
    RoverGeometry geo{};
    auto v = compute_wheel_velocities(cmd, geo);
    EXPECT_GT(v[FR], v[FL]);
    EXPECT_GT(v[MR], v[ML]);
}

TEST(RockerBogie, SpeedClamped) {
    TwistCmd cmd{10.0, 0.0};  // grossly over limit
    RoverGeometry geo{};
    auto v = compute_wheel_velocities(cmd, geo);
    for (auto vi : v) {
        EXPECT_LE(std::abs(vi), MAX_WHEEL_SPEED_RAD_S + 1e-9);
    }
}

TEST(RockerBogie, ForwardKinematicsRoundTrip) {
    RoverGeometry geo{};
    TwistCmd cmd{0.25, 0.0};
    auto v = compute_wheel_velocities(cmd, geo);
    v[FL] = v[ML] = v[RL] = v[FR] = v[MR] = v[RR];  // ideal (no slip)
    auto recovered = wheel_velocities_to_twist(v, geo);
    EXPECT_NEAR(recovered.linear_x, 0.25, 1e-6);
    EXPECT_NEAR(recovered.angular_z, 0.0, 1e-9);
}

TEST(RockerBogie, SlipRatioZeroAtMatchingSpeed) {
    double omega = 1.0;
    double v_body = omega * 0.25;  // omega * wheel_radius
    double slip = compute_slip_ratio(omega, v_body, 0.25);
    EXPECT_NEAR(slip, 0.0, 1e-6);
}

TEST(RockerBogie, TractionControlReducesHighSlip) {
    WheelVelocities cmd{};
    cmd.fill(2.0);
    std::array<double,6> slips{};
    slips.fill(0.5);  // all wheels 50% slip
    auto corrected = traction_control(cmd, slips, 0.35);
    for (auto vi : corrected) {
        EXPECT_LT(std::abs(vi), 2.0);
    }
}

int main(int argc, char** argv) {
    testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
