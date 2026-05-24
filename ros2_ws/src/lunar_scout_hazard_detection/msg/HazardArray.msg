# HazardArray.msg
# Collection of all hazard detections for the current sensor frame,
# plus an aggregate emergency-stop decision.

std_msgs/Header header

# All detected hazards in this frame
HazardDetection[] hazards

# True if any hazard is within the emergency_stop_distance_m parameter
bool emergency_stop_required

# Human-readable reason for emergency stop (empty when not required)
string reason

# Aggregate statistics
uint32 total_detections
float32 closest_hazard_distance_m    # 0.0 if no detections
uint8   dominant_hazard_class        # class of the closest / highest-conf hazard

# Processing metadata
float32 inference_latency_ms
float32 depth_estimation_latency_ms
builtin_interfaces/Duration processing_time
