"""Pre-processing helpers preparing document pages for metrics."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

from .loaders import DocumentData, DocumentPage

try:  # Optional dependency used for numeric operations when available.
    import numpy as _np  # type: ignore
except Exception:  # pragma: no cover - numpy is optional
    _np = None  # type: ignore


@dataclass
class PreprocessOptions:
    dpi: int
    grayscale: bool
    deskew: bool
    denoise: bool

    @classmethod
    def from_policy(cls, policy: dict) -> "PreprocessOptions":
        settings = policy.get("preprocess", {})
        return cls(
            dpi=int(settings.get("dpi", 300)),
            grayscale=bool(settings.get("grayscale", True)),
            deskew=bool(settings.get("deskew", True)),
            denoise=bool(settings.get("denoise", True)),
        )


@dataclass
class PreprocessReport:
    applied: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def apply_preprocess(document: DocumentData, options: PreprocessOptions) -> Tuple[DocumentData, PreprocessReport]:
    """Apply lightweight preprocessing to each page when tooling is available."""

    report = PreprocessReport()
    if not document.pages:
        return document, report

    if _np is None:
        report.warnings.append("NumPy unavailable; image preprocessing skipped.")
        return document, report

    for page in document.pages:
        if page.image is None:
            continue
        if options.grayscale and page.image.ndim == 3 and page.image.shape[-1] == 3:
            page.image = _np.mean(page.image, axis=2).astype(_np.uint8)
            report.applied.append(f"page {page.index}: grayscale")
        if options.deskew:
            page.warnings.append("deskew-not-implemented")
        if options.denoise:
            # Simple median filter substitute using rolling window average.
            kernel = _np.ones((3, 3), dtype=_np.float32) / 9.0
            padded = _np.pad(page.image, 1, mode="edge")
            filtered = _convolve2d(padded, kernel)
            page.image = filtered.astype(_np.uint8)
            report.applied.append(f"page {page.index}: denoise")
        if page.dpi is None:
            page.dpi = options.dpi
    return document, report


def _convolve2d(image: "_np.ndarray", kernel: "_np.ndarray") -> "_np.ndarray":
    """A minimal 2D convolution implementation used for denoising."""

    assert _np is not None
    kh, kw = kernel.shape
    ih, iw = image.shape
    output = _np.zeros((ih - kh + 1, iw - kw + 1), dtype=_np.float32)
    for y in range(output.shape[0]):
        for x in range(output.shape[1]):
            region = image[y : y + kh, x : x + kw]
            output[y, x] = _np.sum(region * kernel)
    return output
