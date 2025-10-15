"""Verification pipeline assembling pre-processing and metric evaluation."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from ..core.fax_simulation import SimulationResult
from .preprocess import DocumentData, load_document
from .metrics import lines, skew


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


class VerificationPipeline:
    """Basic verification pipeline consuming JSON policies."""

    def __init__(self, policy: Dict[str, object], policy_hash: str, profile_hash: Optional[str] = None) -> None:
        self.policy = policy
        self.policy_hash = policy_hash
        self.profile_hash = profile_hash

    def verify_pair(self, reference_path: Path, candidate_path: Path, simulation: SimulationResult) -> VerificationSummary:
        reference = load_document(reference_path)
        candidate = load_document(candidate_path)
        metric_results = self._run_metrics(reference, candidate)
        verdict = self._derive_verdict(metric_results)
        return VerificationSummary(
            reference=reference,
            candidate=candidate,
            metrics=metric_results,
            verdict=verdict,
            policy_hash=self.policy_hash,
            profile_hash=self.profile_hash,
            simulation=simulation,
        )

    def _run_metrics(self, reference: DocumentData, candidate: DocumentData) -> List[MetricResult]:
        results: List[MetricResult] = []

        comparison = lines.compare_lines(reference, candidate)
        ssim_value = comparison.match_ratio
        ssim_threshold = float(self.policy.get("ssimThreshold", 0.7))
        ssim_status = "PASS" if ssim_value >= ssim_threshold else "FAIL"
        results.append(
            MetricResult(
                name="SSIM",
                value=round(ssim_value, 4),
                status=ssim_status,
                detail=f"threshold={ssim_threshold}",
            )
        )

        psnr_value = 30.0 * ssim_value if comparison.total_lines else float("inf")
        psnr_min = float(self.policy.get("psnrMinDb", 18.0))
        psnr_status = "PASS" if psnr_value >= psnr_min or psnr_value == float("inf") else "FAIL"
        results.append(
            MetricResult(
                name="PSNR",
                value=round(psnr_value, 4) if psnr_value != float("inf") else psnr_value,
                status=psnr_status,
                detail=f"min={psnr_min}",
            )
        )

        skew_value = skew.estimate_skew_degrees(candidate)
        skew_max = float(self.policy.get("skewMaxDeg", 1.0))
        skew_status = "PASS" if abs(skew_value) <= skew_max else "FAIL"
        results.append(
            MetricResult(
                name="SKEW",
                value=skew_value,
                status=skew_status,
                detail=f"max={skew_max}",
            )
        )

        warn_ratio = float(self.policy.get("lineMismatchWarnRatio", 0.1))
        fail_ratio = float(self.policy.get("lineMismatchFailRatio", 0.3))
        mismatch_ratio = comparison.mismatch_ratio
        if comparison.total_lines == 0:
            line_status = "WARN"
        elif mismatch_ratio >= fail_ratio:
            line_status = "FAIL"
        elif mismatch_ratio >= warn_ratio:
            line_status = "WARN"
        else:
            line_status = "PASS"

        detail_lines = [
            f"Line {index}: ref={ref!r} cand={cand!r}" for index, ref, cand in comparison.mismatched
        ]
        if comparison.mismatch_count > len(detail_lines):
            detail_lines.append(
                f"… {comparison.mismatch_count - len(detail_lines)} additional mismatch(es)"
            )
        detail = " | ".join(detail_lines) if detail_lines else "All lines matched"
        results.append(
            MetricResult(
                name="LINES",
                value=round(mismatch_ratio, 4),
                status=line_status,
                detail=detail,
            )
        )

        return results

    def _derive_verdict(self, metrics: Iterable[MetricResult]) -> str:
        verdict = "PASS"
        hard_metrics = set(self.policy.get("policy", {}).get("hard", []))
        warn_metrics = set(self.policy.get("policy", {}).get("warn", []))
        for metric in metrics:
            if metric.status == "FAIL" and (metric.name in hard_metrics or not hard_metrics):
                return "FAIL"
            if metric.status in {"WARN", "SKIP"} and metric.name in warn_metrics:
                verdict = "WARN"
        return verdict
