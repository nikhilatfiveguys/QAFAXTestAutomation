"""Simple MTF50 proxy metric using gradient energy."""
from __future__ import annotations

from ..loaders import DocumentData

try:
    import numpy as _np  # type: ignore
except Exception:  # pragma: no cover - numpy optional
    _np = None  # type: ignore


def mtf50_proxy(document: DocumentData) -> float | None:
    """Return an approximate MTF50 proxy value or None if unavailable."""

    if _np is None:
        return None

    gradients = []
    for page in document.pages:
        if page.image is None:
            continue
        image = page.image.astype(_np.float32)
        sobel_x = _np.abs(_np.diff(image, axis=1))
        sobel_y = _np.abs(_np.diff(image, axis=0))
        energy = float(_np.mean(sobel_x) + _np.mean(sobel_y)) / 2.0
        gradients.append(energy)
    if not gradients:
        return None
    return float(sum(gradients) / len(gradients)) / 255.0
