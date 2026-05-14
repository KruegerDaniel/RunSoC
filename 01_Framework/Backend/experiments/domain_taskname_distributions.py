
DOMAIN_DISTRIBUTIONS = [
    ("general_purpose", 0.45),
    ("safety", 0.22),
    ("sensor", 0.14),
    ("automotive_comms", 0.08),
    ("vision_or_accelerated", 0.08),
    ("security", 0.03),
]

TASK_NAME_PREFIXES_BY_DOMAIN = {
    "general_purpose": ["control", "fusion", "diagnostics", "planning"],
    "safety": ["brake_watch", "fault_reaction", "safety_monitor", "torque_guard"],
    "sensor": ["camera_input", "radar_input", "lidar_input", "imu_input"],
    "automotive_comms": ["navigation", "control", "safety", "telemetry"],
    "vision_or_accelerated": ["object_detect", "lane_detect", "feature_extract"],
    "security": ["auth_check", "message_verify", "secure_boot_check"],
}

def memory_usage_kb_by_domain(domain: str):
    """
    Synthetic per-runnable memory model.
    """
    if domain == "vision_or_accelerated":
        buckets = [
            ((64, 256), 0.45),
            ((257, 1024), 0.40),
            ((1025, 4096), 0.15),
        ]
    elif domain == "sensor":
        buckets = [
            ((8, 64), 0.50),
            ((65, 256), 0.35),
            ((257, 1024), 0.15),
        ]
    elif domain == "security":
        buckets = [
            ((4, 32), 0.50),
            ((33, 128), 0.35),
            ((129, 512), 0.15),
        ]
    else:
        buckets = [
            ((1, 16), 0.70),
            ((17, 64), 0.20),
            ((65, 256), 0.08),
            ((257, 1024), 0.02),
        ]
    return buckets