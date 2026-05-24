cmake_minimum_required(VERSION 3.8)
project(lunar_scout_wheel_control)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)

ament_python_install_package(${PROJECT_NAME})

install(PROGRAMS
  lunar_scout_wheel_control/wheel_control_node.py
  lunar_scout_wheel_control/slip_prediction_node.py
  DESTINATION lib/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
