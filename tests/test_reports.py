"""Tests for the report builder."""
from __future__ import annotations

import json
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from app.core.config_service import default_config_service
from app.core.fax_simulation import FaxProfile
from app.core.iteration_controller import IterationConfig, IterationController
from app.core.run_context import RunContext
from app.reports.reporter import ReportBuilder
from app.verify.pipeline import VerificationPipeline


class ReportBuilderTestCase(unittest.TestCase):
    def setUp(self) -> None:
        service = default_config_service()
        loaded_profile = service.load("profiles/Brother_V34_33k6_ECM256.json")
        self.profile = FaxProfile.from_config(loaded_profile.payload, loaded_profile.sha256)
        self.policy = service.load("verify_policy.normal.json")
        self.pipeline = VerificationPipeline(self.policy.payload, self.policy.sha256, self.profile.config_sha256)
        self.reference = Path("docs/samples/control_reference.txt")
        self.candidate = Path("docs/samples/control_candidate.txt")

    def test_writes_expected_files(self) -> None:
        controller = IterationController(profile=self.profile, verification_pipeline=self.pipeline)
        results = controller.run(
            IterationConfig(iterations=1, rng_seed=42),
            reference=self.reference,
            candidate=self.candidate,
        )
        context = RunContext(
            run_id="test",
            profile=self.profile,
            policy_name="normal",
            policy_hash=self.policy.sha256,
            iterations=1,
            seed=42,
            reference=self.reference,
            candidate=self.candidate,
            path_mode="digital",
            location="Local",
            did=None,
            pcfax_queue=None,
            started_at=datetime.utcnow(),
            ingest_dir=None,
            ingest_pattern=None,
            pcfax_detail=None,
        )
        telemetry = list(controller.iter_events())

        with TemporaryDirectory() as tmpdir:
            builder = ReportBuilder(Path(tmpdir))
            run_dir = builder.ensure_run_directory(context.run_id)
            builder.write_json(run_dir, context, results, telemetry, [])
            builder.write_csv(run_dir, context, results)
            builder.write_html(run_dir, context, results)
            builder.write_run_log(run_dir, context, results)
            reference_doc = results[0].verification.reference  # type: ignore[union-attr]
            candidate_doc = results[0].verification.candidate  # type: ignore[union-attr]
            builder.write_provenance(run_dir, reference_doc, candidate_doc, [])

            self.assertTrue((run_dir / "summary.json").is_file())
            self.assertTrue((run_dir / "summary.csv").is_file())
            self.assertTrue((run_dir / "report.html").is_file())
            self.assertTrue((run_dir / "run.log").is_file())
            self.assertTrue((run_dir / "provenance.json").is_file())

            summary = json.loads((run_dir / "summary.json").read_text())
            self.assertEqual(summary["run"]["id"], "test")
            self.assertEqual(len(summary["iterations"]), 1)


if __name__ == "__main__":
    unittest.main()
