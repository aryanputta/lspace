# HazardDetection.msg
# Single hazard detection result from camera + LIDAR fusion.
#
# hazard_class values:
#   0 = boulder        (rock obstacle)
#   1 = deep_crater    (drop hazard)
#   2 = steep_slope    (angle hazard)
#   3 = comms_shadow   (blocked comms zone)

std_msgs/Header header

# Classification
uint8 hazard_class
string class_name

# Detection confidence [0.0, 1.0]
float32 confidence

# 3-D position in robot body frame (x=right, y=up, z=forward)
geometry_msgs/Point position_body_frame

# Straight-line distance from rover to hazard centroid (metres)
float32 distance_m

# 2-D bounding box in the left camera image (pixels)
# centre_x, centre_y: box centre; size_x, size_y: full width/height
geometry_msgs/BoundingBox2D image_bbox

# Detection source bitmask: 1=camera, 2=lidar, 3=fused
uint8 detection_source

# Estimated hazard physical dimensions (metres, 0 if unknown)
float32 estimated_width_m
float32 estimated_height_m
