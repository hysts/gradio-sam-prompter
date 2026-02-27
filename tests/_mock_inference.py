"""Shared mock inference helpers for test demo applications.

Provides circle-based mask generation used by ``_demo.py``,
``_demo_slow.py``, and ``_demo_clear.py``.
"""

import numpy as np

MOCK_MASK_RADIUS = 50


def apply_fg_points(mask: np.ndarray, obj: dict, h: int, w: int) -> bool:
    """Paint foreground-point circles onto *mask*.  Returns True if any pixel was set."""
    has_content = False
    for i, pt in enumerate(obj.get("points", [])):
        label = obj["labels"][i] if i < len(obj.get("labels", [])) else 1
        if label == 1:
            yy, xx = np.ogrid[:h, :w]
            dist = np.sqrt((xx - pt[0]) ** 2 + (yy - pt[1]) ** 2)
            mask[dist <= MOCK_MASK_RADIUS] = 1
            has_content = True
    return has_content


def apply_boxes(mask: np.ndarray, obj: dict, h: int, w: int) -> bool:
    """Fill box regions onto *mask*.  Returns True if any pixel was set."""
    has_content = False
    for box in obj.get("boxes", []):
        x1, y1, x2, y2 = box
        x1, x2 = max(0, min(x1, w)), max(0, min(x2, w))
        y1, y2 = max(0, min(y1, h)), max(0, min(y2, h))
        mask[int(y1) : int(y2), int(x1) : int(x2)] = 1
        has_content = True
    return has_content


def apply_bg_points(mask: np.ndarray, obj: dict, h: int, w: int) -> None:
    """Erase background-point circles from *mask*."""
    for i, pt in enumerate(obj.get("points", [])):
        label = obj["labels"][i] if i < len(obj.get("labels", [])) else 1
        if label == 0:
            yy, xx = np.ogrid[:h, :w]
            dist = np.sqrt((xx - pt[0]) ** 2 + (yy - pt[1]) ** 2)
            mask[dist <= MOCK_MASK_RADIUS] = 0
