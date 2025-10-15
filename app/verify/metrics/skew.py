"""Skew estimation heuristics for scanned documents."""
from __future__ import annotations

import math

from ..loaders import DocumentData

try:
    import numpy as _np  # type: ignore
except Exception:  # pragma: no cover - numpy optional
    _np = None  # type: ignore


def estimate_skew_degrees(document: DocumentData) -> float:
    """Return an approximate skew angle in degrees."""

    if document.page_count == 0 or _np is None:
        return 0.0

    angles = []
    for page in document.pages:
        if page.image is None:
            continue
        angles.append(_estimate_page_angle(page.image))
    if not angles:
        return 0.0
    return float(sum(angles) / len(angles))


def _estimate_page_angle(image: "_np.ndarray") -> float:
    assert _np is not None
    y, x = _np.indices(image.shape)
    image = image.astype(_np.float32)
    total = float(_np.sum(image))
    if total == 0:
        return 0.0
    x_mean = float(_np.sum(x * image) / total)
    y_mean = float(_np.sum(y * image) / total)
    mu11 = float(_np.sum((x - x_mean) * (y - y_mean) * image) / total)
    mu20 = float(_np.sum(((x - x_mean) ** 2) * image) / total)
    mu02 = float(_np.sum(((y - y_mean) ** 2) * image) / total)
    angle = 0.5 * math.atan2(2 * mu11, mu20 - mu02)
    return math.degrees(angle)
