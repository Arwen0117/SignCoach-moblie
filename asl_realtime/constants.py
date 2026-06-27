"""Shared landmark layout constants."""

from __future__ import annotations

SELECTED_TYPES = ("left_hand", "right_hand", "pose", "face")

LEFT_HAND_COUNT = 21
RIGHT_HAND_COUNT = 21
POSE_COUNT = 33

# A compact, commonly used MediaPipe lip contour subset.
LIP_LANDMARKS = [
    61,
    185,
    40,
    39,
    37,
    0,
    267,
    269,
    270,
    409,
    291,
    146,
    91,
    181,
    84,
    17,
    314,
    405,
    321,
    375,
    78,
    191,
    80,
    81,
    82,
    13,
    312,
    311,
    310,
    415,
    308,
    95,
    88,
    178,
    87,
    14,
    317,
    402,
    318,
    324,
]

FEATURE_LANDMARK_COUNT = LEFT_HAND_COUNT + RIGHT_HAND_COUNT + POSE_COUNT + len(LIP_LANDMARKS)
FEATURE_DIM = FEATURE_LANDMARK_COUNT * 3

