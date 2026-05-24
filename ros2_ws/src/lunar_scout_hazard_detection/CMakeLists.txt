cmake_minimum_required(VERSION 3.8)
project(lunar_scout_hazard_detection)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Find dependencies
find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclpy REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(nav2_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(std_srvs REQUIRED)
find_package(tf2_ros REQUIRED)
find_package(tf2_geometry_msgs REQUIRED)
find_package(rosidl_default_generators REQUIRED)

# Generate custom messages
rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/HazardDetection.msg"
  "msg/HazardArray.msg"
  DEPENDENCIES
    std_msgs
    geometry_msgs
    sensor_msgs
)

# Install Python package
ament_python_install_package(${PROJECT_NAME})

# Install Python executables
install(PROGRAMS
  lunar_scout_hazard_detection/hazard_detection_node.py
  lunar_scout_hazard_detection/terrain_segmentation_node.py
  DESTINATION lib/${PROJECT_NAME}
)

# Install launch files, config, and models
install(DIRECTORY
  launch/
  DESTINATION share/${PROJECT_NAME}/launch
  OPTIONAL
)

install(DIRECTORY
  config/
  DESTINATION share/${PROJECT_NAME}/config
  OPTIONAL
)

install(DIRECTORY
  models/
  DESTINATION share/${PROJECT_NAME}/models
  OPTIONAL
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()

  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(test_hazard_detection test/test_hazard_detection.py)
endif()

ament_export_dependencies(rosidl_default_runtime)
ament_package()
