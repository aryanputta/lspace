@echo off
:: LPAS Sim Launcher — run from Windows to open Gazebo + RViz2 in WSL2
:: Double-click this file or run from PowerShell/CMD.
:: GUI windows appear on Windows desktop via WSLg automatically.

echo ============================================================
echo   LPAS Simulation Launcher
echo   Gazebo + RViz2 will open as Windows desktop apps (WSLg)
echo ============================================================
echo.

:: Check WSL2 is available
wsl -d Ubuntu-22.04 echo "WSL2 OK" 2>nul
if %errorlevel% neq 0 (
    echo ERROR: WSL2 Ubuntu-22.04 not found.
    echo Install it: wsl --install -d Ubuntu-22.04
    pause
    exit /b 1
)

echo Launching LPAS sim in WSL2...
echo Gazebo window appears in ~10s, RViz2 in ~20s.
echo.
echo Press Ctrl+C in this window to stop the sim.
echo.

wsl -d Ubuntu-22.04 -e bash -c "set -e; source /opt/ros/humble/setup.bash 2>/dev/null; source /mnt/c/Users/aryan/Code/apps/lspace/ros2_ws/install/setup.bash 2>/dev/null; export IGN_GAZEBO_RESOURCE_PATH=/mnt/c/Users/aryan/Code/apps/lspace/gazebo_worlds:/mnt/c/Users/aryan/Code/apps/lspace/gazebo_worlds/models; export GZ_SIM_RESOURCE_PATH=$IGN_GAZEBO_RESOURCE_PATH; export LIBGL_ALWAYS_SOFTWARE=1; export GALLIUM_DRIVER=llvmpipe; export DISPLAY=:0; cd /mnt/c/Users/aryan/Code/apps/lspace; ros2 launch lunar_scout_bringup lunar_scout_sim.launch.py"

pause
