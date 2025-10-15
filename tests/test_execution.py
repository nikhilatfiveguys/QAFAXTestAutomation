from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.core.execution import RunOptions, execute_run


class ExecuteRunTests(unittest.TestCase):
    def test_execute_run_writes_artifacts(self) -> None:
        reference = Path("docs/samples/control_reference.txt")
        candidate = Path("docs/samples/control_candidate.txt")
        with TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            options = RunOptions(
                reference=reference,
                candidate=candidate,
                iterations=1,
                seed=42,
                output_dir=output_dir,
                run_id="unit-test",
            )
            result = execute_run(options)

            self.assertTrue((result.run_dir / "summary.json").is_file())
            self.assertTrue((result.run_dir / "report.html").is_file())
            summary = json.loads((result.run_dir / "summary.json").read_text())
            self.assertEqual(summary["run"]["id"], "unit-test")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
