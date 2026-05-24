cmake_minimum_required(VERSION 3.8)
project(lunar_scout_science_payload)

find_package(ament_cmake REQUIRED)
find_package(rclpy REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "action/DrillSample.action"
  "action/RunSpectrometer.action"
)

install(PROGRAMS
  lunar_scout_science_payload/science_payload_node.py
  DESTINATION lib/${PROJECT_NAME}
)
install(DIRECTORY lunar_scout_science_payload
  DESTINATION lib/${PROJECT_NAME})

ament_package()
