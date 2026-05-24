// rocker_bogie_kinematics.cpp — implementation (logic in header-only)
#include "lpas/rocker_bogie_kinematics.hpp"

namespace lpas {
static_assert(sizeof(WheelVelocities) == 6 * sizeof(double));
}
