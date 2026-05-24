cmake_minimum_required(VERSION 3.8)
project(lunar_scout_science_payload)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclpy REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(action_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "action/DrillSample.action"
  "action/RunSpectrometer.action"
  DEPENDENCIES action_msgs
)

ament_python_install_package(${PROJECT_NAME})

install(PROGRAMS
  lunar_scout_science_payload/science_payload_node.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
