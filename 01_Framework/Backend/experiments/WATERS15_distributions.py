######################
# WATERS15 Distributions as per https://rtn.ecrts.org/forum/download/WATERS15_Real_World_Automotive_Benchmark_For_Free.pdf
######################
import math
import random

PERIOD_DISTRIBUTION = [
    (1, 0.03),
    (2, 0.02),
    (5, 0.02),
    (10, 0.25),
    (20, 0.25),
    (50, 0.03),
    (100, 0.20),
    (200, 0.01),
    (1000, 0.04),
    ("event_angle_sync", 0.15),
]

# WATERS15 runnable ACET table, in microseconds.
# For event/angle-synchronous tasks, use the angle-sync row.
ACET_US_BY_PERIOD = {
    1: {"min": 0.34, "avg": 5.00, "max": 30.11},
    2: {"min": 0.32, "avg": 4.20, "max": 40.69},
    5: {"min": 0.36, "avg": 11.04, "max": 83.38},
    10: {"min": 0.21, "avg": 10.09, "max": 309.87},
    20: {"min": 0.25, "avg": 8.74, "max": 291.42},
    50: {"min": 0.29, "avg": 17.56, "max": 92.98},
    100: {"min": 0.21, "avg": 10.53, "max": 420.43},
    200: {"min": 0.22, "avg": 2.56, "max": 21.95},
    1000: {"min": 0.37, "avg": 0.43, "max": 0.46},
    "event_angle_sync": {"min": 0.45, "avg": 6.52, "max": 88.58},
}

CHAIN_LENGTH_DISTRIBUTION = [
    (2, 0.30),
    (3, 0.40),
    (4, 0.20),
    (5, 0.10),
]

ACTIVATION_PATTERN_DISTRIBUTION = [
    (1, 0.70),
    (2, 0.20),
    (3, 0.10),
]


def sample_weibull_us(period) -> float:
    stats = ACET_US_BY_PERIOD[period]
    min_us = stats["min"]
    avg_us = stats["avg"]
    max_us = stats["max"]

    shape = 0.85
    scale = avg_us / math.gamma(1.0 + 1.0 / shape)

    for _ in range(100):
        sample = random.weibullvariate(scale, shape)
        if min_us <= sample <= max_us:
            return sample

    return min(max(sample, min_us), max_us)
