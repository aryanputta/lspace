// test_bekker_soil_model.cpp — unit tests for Bekker model
#include <gtest/gtest.h>
#include "lpas/bekker_soil_model.hpp"

using namespace lpas;

TEST(BekkerModel, NominalSinkageReasonable) {
    RegolithParams soil{};
    WheelParams    wheel{};
    auto result = compute_sinkage(soil, wheel);
    // Expect 15–40mm sinkage for nominal load
    EXPECT_GE(result.sinkage_m, 0.010);
    EXPECT_LE(result.sinkage_m, 0.060);
}

TEST(BekkerModel, HigherLoadGivesMoreSinkage) {
    RegolithParams soil{};
    WheelParams light_wheel{.radius_m=0.25, .width_m=0.175, .load_n=200.0};
    WheelParams heavy_wheel{.radius_m=0.25, .width_m=0.175, .load_n=500.0};
    auto r_light = compute_sinkage(soil, light_wheel);
    auto r_heavy = compute_sinkage(soil, heavy_wheel);
    EXPECT_GT(r_heavy.sinkage_m, r_light.sinkage_m);
}

TEST(BekkerModel, TractiveForcePositiveForPositiveSlip) {
    RegolithParams soil{};
    WheelParams    wheel{};
    auto sinkage = compute_sinkage(soil, wheel);
    double ft = tractive_force_with_slip(soil, wheel, sinkage, 0.15);
    EXPECT_GT(ft, 0.0);
}

TEST(BekkerModel, TractiveForceZeroAtZeroSlip) {
    RegolithParams soil{};
    WheelParams    wheel{};
    auto sinkage = compute_sinkage(soil, wheel);
    double ft = tractive_force_with_slip(soil, wheel, sinkage, 0.0);
    EXPECT_NEAR(ft, 0.0, 1e-6);
}

TEST(BekkerModel, NegativeSlipGivesNegativeForce) {
    RegolithParams soil{};
    WheelParams    wheel{};
    auto sinkage = compute_sinkage(soil, wheel);
    double ft = tractive_force_with_slip(soil, wheel, sinkage, -0.2);
    EXPECT_LT(ft, 0.0);
}

TEST(BekkerModel, SixWheelTotalTractionMeetsSlope25Deg) {
    RegolithParams soil{};
    WheelParams    wheel{};
    auto sinkage = compute_sinkage(soil, wheel);
    double ft_per_wheel = tractive_force_with_slip(soil, wheel, sinkage, 0.2);
    double total_traction = ft_per_wheel * 6.0;

    // Required: m * g_lunar * sin(25°)
    double mass_kg   = 202.0;
    double g_lunar   = 1.62;
    double required  = mass_kg * g_lunar * std::sin(25.0 * M_PI / 180.0);

    EXPECT_GT(total_traction, required)
        << "Total traction " << total_traction << " N must exceed "
        << required << " N for 25° slope";
}

int main(int argc, char** argv) {
    testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
