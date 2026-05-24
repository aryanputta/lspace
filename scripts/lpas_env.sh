#!/bin/bash
# LPAS ROS2 environment — sourced by ros2_shell.cmd
source /opt/ros/humble/setup.bash 2>/dev/null
source /mnt/c/Users/aryan/Code/apps/lspace/ros2_ws/install/setup.bash 2>/dev/null
export IGN_GAZEBO_RESOURCE_PATH=/mnt/c/Users/aryan/Code/apps/lspace/gazebo_worlds:/mnt/c/Users/aryan/Code/apps/lspace/gazebo_worlds/models
export GZ_SIM_RESOURCE_PATH=$IGN_GAZEBO_RESOURCE_PATH
export LIBGL_ALWAYS_SOFTWARE=1
export GALLIUM_DRIVER=llvmpipe
export DISPLAY=:0
PS1='[LPAS ros2] \w\$ '

echo ""
echo "LPAS ROS2 environment ready. Try:"
echo "  ros2 topic list"
echo "  ros2 topic echo /wheel_control/odometry"
echo "  ros2 run tf2_tools view_frames"
echo "  ros2 node list"
echo ""
