"""SSIM/PSNR estimation with graceful fallbacks."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from ..loaders import DocumentData
from . import lines

try:
    import numpy as _np  # type: ignore
except Exception:  # pragma: no cover - numpy optional
    _np = None  # type: ignore


@dataclass
class SSIMPSNRResult:
    ssim: float | None
    psnr: float | None
    method: str
    notes: List[str]


def compute(reference: DocumentData, candidate: DocumentData) -> SSIMPSNRResult:
    """Compute average SSIM/PSNR metrics across aligned pages."""

    if reference.page_count == 0 or candidate.page_count == 0:
        return SSIMPSNRResult(ssim=None, psnr=None, method="empty", notes=["No pages available."])

    if _np is None:
        comparison = lines.compare_lines(reference, candidate)
        detail = f"text-fallback (match={comparison.match_ratio:.4f})"
        value = comparison.match_ratio
        psnr = float("inf") if comparison.match_ratio == 1.0 else 0.0
        return SSIMPSNRResult(ssim=value, psnr=psnr, method="text", notes=[detail])

    values: List[float] = []
    psnr_values: List[float] = []
    notes: List[str] = []
    page_pairs = zip(reference.pages, candidate.pages)
    processed = 0
    for ref_page, cand_page in page_pairs:
        if ref_page.image is None or cand_page.image is None:
            notes.append(f"page {ref_page.index}: missing image data; fallback to text")
            comparison = lines.compare_sequences(ref_page.text_lines, cand_page.text_lines)
            values.append(comparison.match_ratio)
            psnr_values.append(float("inf") if comparison.match_ratio == 1.0 else 0.0)
            processed += 1
            continue
        ssim = _simple_ssim(ref_page.image.astype(_np.float32), cand_page.image.astype(_np.float32))
        psnr = _psnr(ref_page.image.astype(_np.float32), cand_page.image.astype(_np.float32))
        values.append(float(ssim))
        psnr_values.append(float(psnr))
        processed += 1
    if processed == 0:
        comparison = lines.compare_lines(reference, candidate)
        detail = f"text-fallback (match={comparison.match_ratio:.4f})"
        return SSIMPSNRResult(ssim=comparison.match_ratio, psnr=float("inf"), method="text", notes=[detail])

    ssim_avg = sum(values) / processed if processed else None
    psnr_avg = sum(psnr_values) / processed if processed else None
    return SSIMPSNRResult(ssim=ssim_avg, psnr=psnr_avg, method="image" if _np is not None else "text", notes=notes)


def _simple_ssim(img_a: "_np.ndarray", img_b: "_np.ndarray") -> float:
    assert _np is not None
    L = 255.0
    c1 = (0.01 * L) ** 2
    c2 = (0.03 * L) ** 2
    mu_x = float(_np.mean(img_a))
    mu_y = float(_np.mean(img_b))
    sigma_x = float(_np.var(img_a))
    sigma_y = float(_np.var(img_b))
    sigma_xy = float(_np.mean((img_a - mu_x) * (img_b - mu_y)))
    numerator = (2 * mu_x * mu_y + c1) * (2 * sigma_xy + c2)
    denominator = (mu_x ** 2 + mu_y ** 2 + c1) * (sigma_x + sigma_y + c2)
    if denominator == 0:
        return 1.0
    return max(min(numerator / denominator, 1.0), -1.0)


def _psnr(img_a: "_np.ndarray", img_b: "_np.ndarray") -> float:
    assert _np is not None
    mse = float(_np.mean((img_a - img_b) ** 2))
    if mse == 0:
        return float("inf")
    max_pixel = 255.0
    return 20 * _np.log10(max_pixel / _np.sqrt(mse))
