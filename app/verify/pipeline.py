"""Verification pipeline assembling preprocessing, alignment, and metrics."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional

from ..core.fax_simulation import SimulationResult
from . import align
from .loaders import DocumentData, load_document
from .metrics import barcode, lines, mtf_proxy, noise, ocr, skew, ssim_psnr
from .preprocess import PreprocessOptions, apply_preprocess


@dataclass
class MetricResult:
    name: str
    value: Optional[float]
    status: str
    detail: str = ""


@dataclass
class VerificationSummary:
    reference: DocumentData
    candidate: DocumentData
    metrics: List[MetricResult]
    verdict: str
    policy_hash: str
    profile_hash: Optional[str]
    simulation: SimulationResult
    notes: List[str] = field(default_factory=list)


class VerificationPipeline:
    """Verification pipeline that adapts to available tooling."""

    def __init__(self, policy: dict, policy_hash: str, profile_hash: Optional[str] = None) -> None:
        self.policy = policy
        self.policy_hash = policy_hash
        self.profile_hash = profile_hash
        self.preprocess_options = PreprocessOptions.from_policy(policy)
        self.hard_metrics = set(policy.get("policy", {}).get("hard", []))
        self.warn_metrics = set(policy.get("policy", {}).get("warn", []))

    def verify_pair(self, reference_path: Path, candidate_path: Path, simulation: SimulationResult) -> VerificationSummary:
        reference_raw = load_document(reference_path)
        candidate_raw = load_document(candidate_path)
        reference, ref_report = apply_preprocess(reference_raw, self.preprocess_options)
        candidate, cand_report = apply_preprocess(candidate_raw, self.preprocess_options)
        page_pairs, alignment_warnings = align.align_documents(reference, candidate)
        if page_pairs:
            aligned_reference = DocumentData(
                path=reference.path,
                content=reference.content,
                sha256=reference.sha256,
                pages=[pair.reference for pair in page_pairs],
                warnings=list(reference.warnings),
            )
            aligned_candidate = DocumentData(
                path=candidate.path,
                content=candidate.content,
                sha256=candidate.sha256,
                pages=[pair.candidate for pair in page_pairs],
                warnings=list(candidate.warnings),
            )
            reference = aligned_reference
            candidate = aligned_candidate
        line_comparison = lines.compare_lines(reference, candidate)
        metrics = self._run_metrics(reference, candidate, line_comparison, alignment_warnings)
        verdict = self._derive_verdict(metrics)
        notes = []
        if ref_report.warnings:
            notes.append("reference:" + ", ".join(ref_report.warnings))
        if cand_report.warnings:
            notes.append("candidate:" + ", ".join(cand_report.warnings))
        if alignment_warnings:
            notes.extend(alignment_warnings)
        return VerificationSummary(
            reference=reference,
            candidate=candidate,
            metrics=metrics,
            verdict=verdict,
            policy_hash=self.policy_hash,
            profile_hash=self.profile_hash,
            simulation=simulation,
            notes=notes,
        )

    def _run_metrics(
        self,
        reference: DocumentData,
        candidate: DocumentData,
        line_comparison: lines.LineComparison,
        alignment_warnings: List[str],
    ) -> List[MetricResult]:
        results: List[MetricResult] = []

        ssim_result = ssim_psnr.compute(reference, candidate)
        ssim_threshold = float(self.policy.get("ssimThreshold", 0.7))
        ssim_status = self._numeric_status("SSIM", ssim_result.ssim, lambda v: v >= ssim_threshold)
        detail = f"threshold={ssim_threshold} method={ssim_result.method}"
        if ssim_result.notes:
            detail += " | " + " | ".join(ssim_result.notes)
        results.append(MetricResult(name="SSIM", value=_round_or_none(ssim_result.ssim), status=ssim_status, detail=detail))

        psnr_min = float(self.policy.get("psnrMinDb", 18.0))
        psnr_status = self._numeric_status("PSNR", ssim_result.psnr, lambda v: v >= psnr_min)
        psnr_value = None if ssim_result.psnr is None else (_round_or_none(ssim_result.psnr))
        results.append(MetricResult(name="PSNR", value=psnr_value, status=psnr_status, detail=f"min={psnr_min}"))

        skew_value = skew.estimate_skew_degrees(candidate)
        skew_max = float(self.policy.get("skewMaxDeg", 1.0))
        skew_status = self._numeric_status("SKEW", abs(skew_value), lambda v: v <= skew_max)
        results.append(MetricResult(name="SKEW", value=_round_or_none(skew_value), status=skew_status, detail=f"max={skew_max}"))

        noise_value = noise.noise_index(candidate)
        noise_warn = float(self.policy.get("noiseWarn", 0.12))
        if noise_value >= noise_warn:
            noise_status = "WARN" if "NOISE" in self.warn_metrics else "FAIL"
        else:
            noise_status = "PASS"
        results.append(MetricResult(name="NOISE", value=_round_or_none(noise_value), status=noise_status, detail=f"warn>={noise_warn}"))

        mtf_threshold = float(self.policy.get("mtf", {}).get("mtf50Min", 0.25))
        mtf_value = mtf_proxy.mtf50_proxy(candidate)
        mtf_status = self._numeric_status("MTF", mtf_value, lambda v: v >= mtf_threshold)
        results.append(MetricResult(name="MTF", value=_round_or_none(mtf_value), status=mtf_status, detail=f"min={mtf_threshold}"))

        mismatch_ratio = line_comparison.mismatch_ratio
        warn_ratio = float(self.policy.get("lineMismatchWarnRatio", 0.1))
        fail_ratio = float(self.policy.get("lineMismatchFailRatio", 0.3))
        if line_comparison.total_lines == 0:
            line_status = "WARN"
        elif mismatch_ratio >= fail_ratio:
            line_status = "FAIL"
        elif mismatch_ratio >= warn_ratio:
            line_status = "WARN"
        else:
            line_status = "PASS"
        detail_lines = [
            f"Line {index}: ref={ref!r} cand={cand!r}" for index, ref, cand in line_comparison.mismatched
        ]
        if line_comparison.mismatch_count > len(detail_lines):
            detail_lines.append(f"… {line_comparison.mismatch_count - len(detail_lines)} additional mismatch(es)")
        detail = " | ".join(detail_lines) if detail_lines else "All lines matched"
        results.append(
            MetricResult(
                name="LINES",
                value=_round_or_none(mismatch_ratio),
                status=line_status,
                detail=detail,
            )
        )

        ocr_cfg = self.policy.get("ocr", {})
        require_ocr = bool(ocr_cfg.get("required", False))
        min_accuracy = float(ocr_cfg.get("minAccuracy", 0.95))
        ocr_value, alpha, total = ocr.ocr_accuracy(candidate)
        if total == 0 and not require_ocr:
            ocr_status = "SKIP"
        elif ocr_value >= min_accuracy or (ocr_value == 0 and not require_ocr):
            ocr_status = "PASS"
        else:
            ocr_status = "FAIL" if require_ocr else "WARN"
        ocr_detail = f"alpha={alpha} total={total} min={min_accuracy}" if total else "no text"
        results.append(MetricResult(name="OCR", value=_round_or_none(ocr_value), status=ocr_status, detail=ocr_detail))

        barcode_cfg = self.policy.get("barcode", {})
        required_barcode = bool(barcode_cfg.get("required", False))
        tokens = list(barcode.detect_tokens(candidate))
        if tokens:
            barcode_status = "PASS"
            barcode_detail = ", ".join(tokens)
        else:
            barcode_status = "FAIL" if required_barcode else "WARN"
            barcode_detail = "no tokens detected"
        results.append(MetricResult(name="BARCODE", value=len(tokens), status=barcode_status, detail=barcode_detail))

        if alignment_warnings:
            results.append(
                MetricResult(
                    name="ALIGNMENT",
                    value=None,
                    status="WARN",
                    detail=" | ".join(alignment_warnings),
                )
            )
        return results

    def _derive_verdict(self, metrics: Iterable[MetricResult]) -> str:
        verdict = "PASS"
        for metric in metrics:
            if metric.status == "FAIL" and (not self.hard_metrics or metric.name in self.hard_metrics):
                return "FAIL"
            if metric.status in {"WARN", "SKIP"} and metric.name in self.warn_metrics:
                verdict = "WARN"
        return verdict

    def _numeric_status(self, name: str, value: Optional[float], comparator) -> str:
        if value is None:
            return "WARN" if name in self.warn_metrics else "SKIP"
        return "PASS" if comparator(value) else "FAIL"


def _round_or_none(value: Optional[float]) -> Optional[float]:
    if value is None or value == float("inf"):
        return value
    return round(value, 4)
