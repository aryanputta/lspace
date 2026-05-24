cmake_minimum_required(VERSION 3.8)
project(lunar_scout_embedded CXX C)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Compiler hardening flags (NASA/JPL coding standard)
add_compile_options(
  -Wall -Wextra -Wpedantic
  -Werror=return-type
  -Werror=implicit-function-declaration
  -fstack-protector-strong
  -D_FORTIFY_SOURCE=2
)

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_lifecycle REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(diagnostic_msgs REQUIRED)

# Core embedded library
add_library(lpas_embedded STATIC
  src/power_monitor.cpp
  src/wheel_controller.cpp
  src/fault_manager.cpp
  src/thermal_controller.cpp
  src/bekker_soil_model.cpp
  src/rocker_bogie_kinematics.cpp
)
target_include_directories(lpas_embedded PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)
ament_target_dependencies(lpas_embedded rclcpp std_msgs geometry_msgs)

# ROS2 C++ node executables
add_executable(wheel_control_cpp_node
  src/nodes/wheel_control_cpp_node.cpp
)
target_link_libraries(wheel_control_cpp_node lpas_embedded)
ament_target_dependencies(wheel_control_cpp_node
  rclcpp rclcpp_lifecycle std_msgs geometry_msgs nav_msgs sensor_msgs
)

add_executable(power_management_cpp_node
  src/nodes/power_management_cpp_node.cpp
)
target_link_libraries(power_management_cpp_node lpas_embedded)
ament_target_dependencies(power_management_cpp_node
  rclcpp rclcpp_lifecycle std_msgs sensor_msgs diagnostic_msgs
)

add_executable(fault_detection_cpp_node
  src/nodes/fault_detection_cpp_node.cpp
)
target_link_libraries(fault_detection_cpp_node lpas_embedded)
ament_target_dependencies(fault_detection_cpp_node
  rclcpp rclcpp_lifecycle std_msgs diagnostic_msgs
)

install(TARGETS
  lpas_embedded
  wheel_control_cpp_node
  power_management_cpp_node
  fault_detection_cpp_node
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY include/
  DESTINATION include
)

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  ament_add_gtest(test_bekker test/test_bekker_soil_model.cpp)
  target_link_libraries(test_bekker lpas_embedded)

  ament_add_gtest(test_kinematics test/test_rocker_bogie_kinematics.cpp)
  target_link_libraries(test_kinematics lpas_embedded)

  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
