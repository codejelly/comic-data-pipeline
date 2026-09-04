# Publisher classifications
MAJOR_PUBLISHERS: set[str] = {
    "marvel comics",
    "dc comics",
    "image comics",
}

# 3-Day Pull Count Velocity Thresholds
PULL_THRESHOLDS: dict[str, int] = {
    "MAJOR": 25,
    "DEFAULT": 10,
    "MID_SERIES_DELTA": 15,
    "MID_SERIES_MANUAL": 20,
}

# Acceleration Filter Requirements
ACCELERATION_CONFIG = {
    "MIN_DELTA_3D": 10,
    "MIN_ACCELERATION": 5,
}
