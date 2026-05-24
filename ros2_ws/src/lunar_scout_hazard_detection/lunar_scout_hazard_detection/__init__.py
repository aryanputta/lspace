"""
Lunar Scout Hazard Detection Package.

Provides real-time hazard detection for NASA Lunar Scout rover using
stereo vision, LIDAR sensor fusion, and ONNX deep learning inference.

Nodes:
    hazard_detection_node: Lifecycle node for multi-modal hazard detection
    terrain_segmentation_node: Per-pixel terrain classification node

Hazard Classes:
    0 - boulder: Rock obstacle requiring avoidance
    1 - deep_crater: Crater with significant depth drop
    2 - steep_slope: Slope exceeding safe traversal angle
    3 - comms_shadow: Area with blocked Earth/relay communications
"""

__version__ = "1.0.0"
__author__ = "Lunar Scout Team"
__email__ = "rover-team@nasa.gov"

HAZARD_CLASSES = {
    0: "boulder",
    1: "deep_crater",
    2: "steep_slope",
    3: "comms_shadow",
}

HAZARD_COLORS_BGR = {
    0: (0, 0, 255),    # Red for boulder
    1: (0, 165, 255),  # Orange for deep crater
    2: (0, 255, 255),  # Yellow for steep slope
    3: (255, 0, 255),  # Magenta for comms shadow
}

TERRAIN_CLASSES = {
    0: "unknown",
    1: "regolith_flat",
    2: "regolith_rough",
    3: "rock_field",
    4: "crater_floor",
    5: "crater_rim",
    6: "bedrock",
    7: "shadow",
}

TERRAIN_COLORS_BGR = {
    0: (128, 128, 128),  # Gray - unknown
    1: (200, 180, 140),  # Tan - flat regolith
    2: (160, 130, 90),   # Dark tan - rough regolith
    3: (80, 80, 80),     # Dark gray - rock field
    4: (60, 100, 160),   # Blue-gray - crater floor
    5: (100, 80, 60),    # Brown - crater rim
    6: (40, 40, 40),     # Very dark - bedrock
    7: (0, 0, 0),        # Black - shadow
}

TRAVERSABILITY_COST = {
    0: 50,   # unknown - moderate cost
    1: 0,    # flat regolith - free
    2: 25,   # rough regolith - low cost
    3: 60,   # rock field - high cost
    4: 80,   # crater floor - very high cost
    5: 70,   # crater rim - high cost
    6: 40,   # bedrock - moderate cost
    7: 90,   # shadow - near-impassable (thermal risk)
}
