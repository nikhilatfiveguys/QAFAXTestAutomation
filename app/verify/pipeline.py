"""Verification pipeline assembling pre-processing and metric evaluation."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from ..core.fax_simulation import SimulationResult
from .preprocess import DocumentData, load_document
from .metrics import barcode, bytewise, noise, ocr, skew


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
        comparison = bytewise.compare(reference, candidate)
        ssim_threshold = float(self.policy.get("ssimThreshold", 0.7))
        ssim_status = "PASS" if comparison.similarity >= ssim_threshold else "FAIL"
        results.append(
            MetricResult(
                name="SSIM",
                value=comparison.similarity,
                status=ssim_status,
                detail=f"threshold={ssim_threshold}",
            )
        )
        psnr_min = float(self.policy.get("psnrMinDb", 18.0))
        psnr_status = "PASS" if comparison.psnr >= psnr_min or comparison.psnr == float("inf") else "FAIL"
        results.append(
            MetricResult(
                name="PSNR",
                value=comparison.psnr,
                status=psnr_status,
                detail=f"min={psnr_min}",
            )
        )
        noise_value = noise.noise_index(candidate)
        noise_max = float(self.policy.get("noiseMax", 0.8))
        noise_status = "PASS" if noise_value <= noise_max else "WARN"
        results.append(
            MetricResult(
                name="NOISE",
                value=noise_value,
                status=noise_status,
                detail=f"max={noise_max}",
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
        ocr_config = self.policy.get("ocr", {})
        ocr_required = bool(ocr_config.get("required", False))
        accuracy, detected, total = ocr.ocr_accuracy(candidate)
        if total == 0:
            status = "WARN" if ocr_required else "SKIP"
        else:
            min_accuracy = float(ocr_config.get("minAccuracy", 0.95))
            status = "PASS" if accuracy >= min_accuracy else ("FAIL" if ocr_required else "WARN")
        results.append(
            MetricResult(
                name="OCR",
                value=accuracy if total else None,
                status=status,
                detail=f"detected={detected} total={total}",
            )
        )
        barcode_config = self.policy.get("barcode", {})
        required = bool(barcode_config.get("requiredOnControlOnly", False))
        tokens = list(barcode.detect_tokens(candidate))
        if required:
            status = "PASS" if tokens else "FAIL"
        else:
            status = "PASS" if tokens else "SKIP"
        results.append(
            MetricResult(
                name="BARCODE",
                value=float(len(tokens)) if tokens else None,
                status=status,
                detail=", ".join(tokens) if tokens else "",
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
