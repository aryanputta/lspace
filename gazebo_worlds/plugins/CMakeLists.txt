cmake_minimum_required(VERSION 3.14)
project(lunar_sim_plugins VERSION 1.0.0 LANGUAGES CXX)

# =============================================================================
# Build configuration
# =============================================================================
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Release build by default; override with -DCMAKE_BUILD_TYPE=Debug
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

message(STATUS "Build type: ${CMAKE_BUILD_TYPE}")
message(STATUS "Compiler: ${CMAKE_CXX_COMPILER_ID} ${CMAKE_CXX_COMPILER_VERSION}")

# Optimization and warning flags
set(CMAKE_CXX_FLAGS_RELEASE "-O3 -march=native -DNDEBUG")
set(CMAKE_CXX_FLAGS_DEBUG   "-O0 -g3 -fsanitize=address,undefined")

add_compile_options(
  -Wall
  -Wextra
  -Wpedantic
  -Wno-unused-parameter  # Gazebo callbacks often have unused _info params
)

# =============================================================================
# Find Gazebo Fortress (Ignition Gazebo 6 / gz-sim 6)
# =============================================================================
# Supports both "ignition" (legacy) and "gz" (new) naming conventions.
# Gazebo Fortress uses gz-sim6 / ignition-gazebo6 package names.

# Try new gz naming first (gz-sim 7+), fall back to ignition naming (Fortress)
find_package(gz-cmake3 QUIET)
if(gz-cmake3_FOUND)
  # gz-garden or newer
  find_package(gz-sim7 REQUIRED)
  find_package(gz-plugin2 REQUIRED COMPONENTS register)
  find_package(gz-math7 REQUIRED)
  find_package(gz-msgs9 REQUIRED)
  set(GZ_SIM_TARGET gz-sim7::gz-sim7)
  set(GZ_PLUGIN_TARGET gz-plugin2::register)
  set(GZ_MATH_TARGET gz-math7::gz-math7)
  set(GZ_MSGS_TARGET gz-msgs9::gz-msgs9)
  message(STATUS "Found gz-sim 7 (Garden+)")
else()
  # Gazebo Fortress: ignition-gazebo6
  find_package(ignition-cmake2 REQUIRED)
  find_package(ignition-gazebo6 REQUIRED)
  find_package(ignition-plugin1 REQUIRED COMPONENTS register)
  find_package(ignition-math6 REQUIRED)
  find_package(ignition-msgs8 REQUIRED)
  set(GZ_SIM_TARGET ignition-gazebo6::ignition-gazebo6)
  set(GZ_PLUGIN_TARGET ignition-plugin1::register)
  set(GZ_MATH_TARGET ignition-math6::ignition-math6)
  set(GZ_MSGS_TARGET ignition-msgs8::ignition-msgs8)
  message(STATUS "Found ignition-gazebo 6 (Fortress)")
endif()

# Find Protobuf (needed for gz::msgs)
find_package(Protobuf REQUIRED)

# =============================================================================
# Optional: find Python3 for test scripts
# =============================================================================
find_package(Python3 COMPONENTS Interpreter QUIET)

# =============================================================================
# PLUGIN 1: Lunar Gravity Plugin
# =============================================================================
add_library(lunargravity_plugin SHARED lunar_gravity_plugin.cc)

target_include_directories(lunargravity_plugin PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}
)

target_link_libraries(lunargravity_plugin
  PUBLIC
    ${GZ_SIM_TARGET}
    ${GZ_PLUGIN_TARGET}
    ${GZ_MATH_TARGET}
)

set_target_properties(lunargravity_plugin PROPERTIES
  # Standard Gazebo naming: lib<plugin_name>.so
  OUTPUT_NAME "lunargravity_plugin"
  # Shared library versioning
  VERSION ${PROJECT_VERSION}
  SOVERSION 1
  # Position-independent code (required for shared libraries)
  POSITION_INDEPENDENT_CODE ON
  # C++ visibility: hide by default, explicit export only
  CXX_VISIBILITY_PRESET hidden
  VISIBILITY_INLINES_HIDDEN ON
)

# =============================================================================
# PLUGIN 2: Regolith Terrain Plugin (Bekker soil model)
# =============================================================================
add_library(regolith_terrain_plugin SHARED regolith_terrain_plugin.cc)

target_include_directories(regolith_terrain_plugin PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}
  ${Protobuf_INCLUDE_DIRS}
)

target_link_libraries(regolith_terrain_plugin
  PUBLIC
    ${GZ_SIM_TARGET}
    ${GZ_PLUGIN_TARGET}
    ${GZ_MATH_TARGET}
    ${GZ_MSGS_TARGET}
    ${Protobuf_LIBRARIES}
)

set_target_properties(regolith_terrain_plugin PROPERTIES
  OUTPUT_NAME "regolith_terrain_plugin"
  VERSION ${PROJECT_VERSION}
  SOVERSION 1
  POSITION_INDEPENDENT_CODE ON
  CXX_VISIBILITY_PRESET hidden
  VISIBILITY_INLINES_HIDDEN ON
)

# Math library
target_link_libraries(regolith_terrain_plugin PUBLIC m)

# =============================================================================
# OPTIONAL PLUGIN: PSR Temperature Plugin (stub - extend as needed)
# =============================================================================
# Uncomment and implement psr_temperature_plugin.cc when ready
# add_library(psr_temperature_plugin SHARED psr_temperature_plugin.cc)
# target_link_libraries(psr_temperature_plugin PUBLIC ${GZ_SIM_TARGET} ${GZ_PLUGIN_TARGET})

# =============================================================================
# Installation
# =============================================================================

# Install plugin shared libraries to Gazebo's plugin path
# Default: /usr/lib/x86_64-linux-gnu/ign-gazebo-6/plugins/ (Fortress)
#          or IGN_GAZEBO_SYSTEM_PLUGIN_PATH / GZ_SIM_SYSTEM_PLUGIN_PATH

include(GNUInstallDirs)

# Plugin install directory
set(GAZEBO_PLUGIN_INSTALL_DIR
  "${CMAKE_INSTALL_LIBDIR}/ign-gazebo-6/plugins"
  CACHE PATH "Gazebo plugin installation directory")

install(TARGETS
  lunargravity_plugin
  regolith_terrain_plugin
  LIBRARY DESTINATION ${GAZEBO_PLUGIN_INSTALL_DIR}
  ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
  RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)

# Install world files
install(DIRECTORY ${CMAKE_SOURCE_DIR}/../lunar_south_pole/
  DESTINATION share/lunar_sim/worlds/lunar_south_pole
  FILES_MATCHING PATTERN "*.world" PATTERN "*.sdf")

install(DIRECTORY ${CMAKE_SOURCE_DIR}/../psr_terrain/
  DESTINATION share/lunar_sim/worlds/psr_terrain
  FILES_MATCHING PATTERN "*.world" PATTERN "*.sdf")

# Install model files
install(DIRECTORY ${CMAKE_SOURCE_DIR}/../models/
  DESTINATION share/lunar_sim/models
  FILES_MATCHING
    PATTERN "*.sdf"
    PATTERN "*.config"
    PATTERN "*.dae"
    PATTERN "*.png"
    PATTERN "*.jpg")

# =============================================================================
# Tests (optional: requires Google Test)
# =============================================================================
option(BUILD_TESTS "Build unit tests" OFF)

if(BUILD_TESTS)
  find_package(GTest QUIET)
  if(GTest_FOUND)
    enable_testing()

    add_executable(test_bekker_model
      tests/test_bekker_model.cc
    )
    target_link_libraries(test_bekker_model
      PRIVATE
        regolith_terrain_plugin
        GTest::GTest
        GTest::Main
    )
    add_test(NAME BekkerModelTests COMMAND test_bekker_model)

    add_executable(test_gravity_plugin
      tests/test_gravity_plugin.cc
    )
    target_link_libraries(test_gravity_plugin
      PRIVATE
        lunargravity_plugin
        GTest::GTest
        GTest::Main
    )
    add_test(NAME GravityPluginTests COMMAND test_gravity_plugin)

    message(STATUS "Tests enabled")
  else()
    message(WARNING "GTest not found; tests disabled")
  endif()
endif()

# =============================================================================
# Configuration summary
# =============================================================================
message(STATUS "")
message(STATUS "=== lunar_sim_plugins build configuration ===")
message(STATUS "  Plugins to build:")
message(STATUS "    liblunargravity_plugin.so")
message(STATUS "    libregolith_terrain_plugin.so")
message(STATUS "  Install path: ${GAZEBO_PLUGIN_INSTALL_DIR}")
message(STATUS "  Tests:        ${BUILD_TESTS}")
message(STATUS "")
message(STATUS "  Build with:")
message(STATUS "    mkdir build && cd build")
message(STATUS "    cmake .. -DCMAKE_BUILD_TYPE=Release")
message(STATUS "    make -j$(nproc)")
message(STATUS "    sudo make install")
message(STATUS "")
message(STATUS "  Or set GZ_SIM_SYSTEM_PLUGIN_PATH to the build dir:")
message(STATUS "    export GZ_SIM_SYSTEM_PLUGIN_PATH=\$(pwd)/build")
message(STATUS "    gz sim ../lunar_south_pole/lunar_south_pole.world")
message(STATUS "==============================================")
message(STATUS "")
