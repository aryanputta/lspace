#!/usr/bin/env bash
# =============================================================================
# LPAS Simulation Environment Setup — Ubuntu 22.04 / WSL2
# =============================================================================
# Run once inside WSL2 Ubuntu 22.04:
#   bash scripts/setup_wsl_sim.sh
#
# What this does:
#   1. Installs ROS 2 Humble (full desktop)
#   2. Installs Ignition Gazebo Fortress
#   3. Installs all LPAS ROS2 and Python dependencies
#   4. Builds the ros2_ws workspace
#   5. Prints the launch command
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROS_DISTRO="humble"
IGN_VERSION="fortress"

log() { echo -e "\033[1;34m[LPAS-SETUP]\033[0m $*"; }
ok()  { echo -e "\033[1;32m[OK]\033[0m $*"; }
err() { echo -e "\033[1;31m[ERR]\033[0m $*"; exit 1; }

# =============================================================================
# 1. System prerequisites
# =============================================================================
log "Updating apt and installing prerequisites..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    curl gnupg2 lsb-release software-properties-common \
    python3-pip python3-venv build-essential cmake git \
    libopencv-dev python3-opencv

# =============================================================================
# 2. ROS 2 Humble
# =============================================================================
if ! command -v ros2 &>/dev/null; then
    log "Installing ROS 2 Humble..."
    sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
        -o /usr/share/keyrings/ros-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
        http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo "$UBUNTU_CODENAME") main" \
        | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
    sudo apt-get update -qq
    sudo apt-get install -y -qq ros-${ROS_DISTRO}-desktop
    ok "ROS 2 Humble installed"
else
    ok "ROS 2 Humble already present"
fi

# Source ROS2 for the remainder of this script
source /opt/ros/${ROS_DISTRO}/setup.bash

# =============================================================================
# 3. Ignition Gazebo Fortress
# =============================================================================
if ! command -v ign &>/dev/null; then
    log "Installing Ignition Gazebo Fortress..."
    sudo curl -sSL https://packages.osrfoundation.org/gazebo.gpg \
        -o /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] \
        http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" \
        | sudo tee /etc/apt/sources.list.d/gazebo-stable.list > /dev/null
    sudo apt-get update -qq
    sudo apt-get install -y -qq ignition-${IGN_VERSION}
    ok "Ignition Gazebo Fortress installed"
else
    ok "Ignition Gazebo already present"
fi

# =============================================================================
# 4. ROS 2 + Gazebo integration packages
# =============================================================================
log "Installing ROS2 Nav2, SLAM, Gazebo bridge, and perception packages..."
sudo apt-get install -y -qq \
    ros-${ROS_DISTRO}-navigation2 \
    ros-${ROS_DISTRO}-nav2-bringup \
    ros-${ROS_DISTRO}-slam-toolbox \
    ros-${ROS_DISTRO}-ros-gz \
    ros-${ROS_DISTRO}-ros-gz-bridge \
    ros-${ROS_DISTRO}-ros-gz-sim \
    ros-${ROS_DISTRO}-robot-state-publisher \
    ros-${ROS_DISTRO}-joint-state-publisher \
    ros-${ROS_DISTRO}-xacro \
    ros-${ROS_DISTRO}-tf2-ros \
    ros-${ROS_DISTRO}-tf2-tools \
    ros-${ROS_DISTRO}-rviz2 \
    ros-${ROS_DISTRO}-diagnostic-updater \
    ros-${ROS_DISTRO}-diagnostic-aggregator \
    ros-${ROS_DISTRO}-diagnostic-msgs \
    ros-${ROS_DISTRO}-nav-msgs \
    ros-${ROS_DISTRO}-sensor-msgs \
    ros-${ROS_DISTRO}-geometry-msgs \
    ros-${ROS_DISTRO}-lifecycle-msgs \
    python3-colcon-common-extensions \
    python3-rosdep \
    python3-catkin-pkg

ok "ROS2 stack packages installed"

# =============================================================================
# 5. Python ML / AI dependencies
# =============================================================================
log "Installing Python packages (PyTorch, ONNX Runtime, OpenCV, etc.)..."
pip3 install --quiet --upgrade pip
pip3 install --quiet \
    torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    onnx \
    onnxruntime \
    opencv-python-headless \
    numpy \
    scipy \
    rasterio \
    pillow \
    astropy \
    matplotlib \
    py_trees \
    transforms3d

ok "Python packages installed"

# =============================================================================
# 6. rosdep init + update
# =============================================================================
log "Initialising rosdep..."
if [ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]; then
    sudo rosdep init
fi
rosdep update --quiet
ok "rosdep ready"

# =============================================================================
# 7. Install rosdep dependencies for the workspace
# =============================================================================
log "Resolving workspace rosdep dependencies..."
cd "${REPO_ROOT}/ros2_ws"
rosdep install --from-paths src --ignore-src -r -y --rosdistro "${ROS_DISTRO}" || true
ok "rosdep dependencies installed"

# =============================================================================
# 8. Build the workspace
# =============================================================================
log "Building ros2_ws with colcon (this may take 2-5 minutes)..."
cd "${REPO_ROOT}/ros2_ws"
source /opt/ros/${ROS_DISTRO}/setup.bash

colcon build \
    --symlink-install \
    --cmake-args -DCMAKE_BUILD_TYPE=RelWithDebInfo \
    --parallel-workers "$(nproc)" \
    2>&1 | tail -n 30

ok "Workspace built successfully"

# =============================================================================
# 9. Shell setup — append to .bashrc
# =============================================================================
BASHRC="${HOME}/.bashrc"
MARKER="# LPAS sim setup"

if ! grep -q "${MARKER}" "${BASHRC}" 2>/dev/null; then
    log "Adding ROS2 + workspace source to ~/.bashrc..."
    cat >> "${BASHRC}" <<EOF

${MARKER}
source /opt/ros/${ROS_DISTRO}/setup.bash
source ${REPO_ROOT}/ros2_ws/install/setup.bash
export IGN_GAZEBO_RESOURCE_PATH=${REPO_ROOT}/gazebo_worlds:${REPO_ROOT}/gazebo_worlds/models
export GZ_SIM_RESOURCE_PATH=\${IGN_GAZEBO_RESOURCE_PATH}
EOF
    ok "~/.bashrc updated"
fi

# =============================================================================
# 10. Done — print launch command
# =============================================================================
echo ""
echo "============================================================"
echo "  LPAS Sim environment ready!"
echo "============================================================"
echo ""
echo "  Source your shell (or open a new terminal), then run:"
echo ""
echo "    source ~/.bashrc"
echo "    cd ${REPO_ROOT}"
echo "    ros2 launch lunar_scout_bringup lunar_scout_sim.launch.py"
echo ""
echo "  For headless (no Gazebo GUI window):"
echo "    ros2 launch lunar_scout_bringup lunar_scout_sim.launch.py headless:=true"
echo ""
echo "  Gazebo GUI opens first (~5 s), then RViz2 (~8 s)."
echo "  Nav2 activates at ~15 s once odom TF is live."
echo "============================================================"
