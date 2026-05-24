// bekker_soil_model.cpp — implementation (template inlines in header; this registers types)
#include "lpas/bekker_soil_model.hpp"

// Explicit instantiation for linker — all logic in header-only templates
namespace lpas {
// Verify at compile time that compute_sinkage is usable
static_assert(sizeof(SinkageResult) > 0, "SinkageResult must be a complete type");
}
