"""Noise index estimation based on simple gradient statistics."""
from __future__ import annotations

from ..loaders import DocumentData

try:
    import numpy as _np  # type: ignore
except Exception:  # pragma: no cover - numpy optional
    _np = None  # type: ignore


def noise_index(document: DocumentData) -> float:
    """Return a noise proxy value in the range [0, 1]."""

    if document.page_count == 0:
        return 0.0

    if _np is not None:
        return _image_noise(document)

    if document.size < 2:
        return 0.0
    transitions = 0
    last = document.content[0]
    for value in document.content[1:]:
        if value != last:
            transitions += 1
        last = value
    return transitions / max(1, document.size - 1)


def _image_noise(document: DocumentData) -> float:
    assert _np is not None
    values: list[float] = []
    for page in document.pages:
        if page.image is None:
            continue
        image = page.image.astype(_np.float32)
        vertical = _np.abs(_np.diff(image, axis=0))
        horizontal = _np.abs(_np.diff(image, axis=1))
        combined = _np.concatenate([vertical.flatten(), horizontal.flatten()])
        if combined.size == 0:
            continue
        values.append(float(_np.mean(_np.clip(combined / 255.0, 0.0, 1.0))))
    if not values:
        return 0.0
    return float(sum(values) / len(values))
