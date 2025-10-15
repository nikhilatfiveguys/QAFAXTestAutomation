from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.fax_simulation import FaxProfile, SimulationResult
from app.verify.pipeline import VerificationPipeline
from app.verify.loaders import DocumentData, DocumentPage
from app.verify.preprocess import PreprocessReport


class VerificationPipelineAlignmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self._prev_disable = os.environ.get("QAFAX_DISABLE_PROMPTS")
        os.environ["QAFAX_DISABLE_PROMPTS"] = "1"

    def tearDown(self) -> None:
        if self._prev_disable is None:
            os.environ.pop("QAFAX_DISABLE_PROMPTS", None)
        else:
            os.environ["QAFAX_DISABLE_PROMPTS"] = self._prev_disable

    def _document(self, name: str, pages: list[list[str]]) -> DocumentData:
        document_pages = [
            DocumentPage(index=i, text_lines=lines, image=None, dpi=None) for i, lines in enumerate(pages)
        ]
        return DocumentData(path=Path(name), content=b"", sha256=f"{name}-sha", pages=document_pages)

    def _simulation(self) -> SimulationResult:
        profile = FaxProfile(
            name="TestProfile",
            standard="V34",
            max_bitrate=33600,
            bitrate_steps=[33600, 31200, 28800],
            ecm_enabled=True,
            ecm_block_bytes=256,
            fallback_policy="graceful",
            config_sha256="hash",
        )
        return SimulationResult(profile=profile, events=[], final_bitrate=33600, fallback_steps=0, rng_seed=42)

    def test_alignment_reorders_pages_before_metrics(self) -> None:
        reference = self._document("ref", [["alpha"], ["beta"]])
        candidate = self._document("cand", [["beta"], ["alpha"]])

        pipeline = VerificationPipeline(
            {
                "policy": {"hard": [], "warn": []},
                "ssimThreshold": 0.0,
                "psnrMinDb": 0.0,
                "skewMaxDeg": 180.0,
                "noiseWarn": 1.0,
                "lineMismatchWarnRatio": 1.0,
                "lineMismatchFailRatio": 1.0,
                "mtf": {"mtf50Min": 0.0},
                "ocr": {"required": False},
                "barcode": {"required": False},
            },
            policy_hash="hash",
            profile_hash="profile",
        )

        with patch("app.verify.pipeline.load_document", side_effect=[reference, candidate]), patch(
            "app.verify.pipeline.apply_preprocess",
            side_effect=[(reference, PreprocessReport()), (candidate, PreprocessReport())],
        ):
            summary = pipeline.verify_pair(Path("ref"), Path("cand"), self._simulation())

        mismatch_metric = next(metric for metric in summary.metrics if metric.name == "LINES")
        self.assertEqual(mismatch_metric.value, 0.0)
        self.assertEqual(summary.verdict, "PASS")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
