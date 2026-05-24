@echo off
:: LPAS ROS2 Shell — opens a WSL2 terminal pre-sourced with ROS2 Humble + LPAS workspace
:: Double-click or run from PowerShell/CMD.
:: Use this to run: ros2 topic list, ros2 topic echo /scan, ros2 run tf2_tools view_frames, etc.

echo ============================================================
echo   LPAS ROS2 Shell
echo   ROS2 Humble + LPAS workspace pre-sourced
echo ============================================================
echo.

wsl -d Ubuntu-22.04 bash --rcfile /mnt/c/Users/aryan/Code/apps/lspace/scripts/lpas_env.sh

pause
