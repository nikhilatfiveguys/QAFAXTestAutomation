"""Tests for the FoIP/T.38 validation helpers."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.core.foip import FoipValidator


class FoipValidatorTestCase(unittest.TestCase):
    def test_collects_artifacts_without_command(self) -> None:
        with TemporaryDirectory() as tmpdir:
            artifact_path = Path(tmpdir) / "received.tiff"
            artifact_path.write_bytes(b"test")
            config_path = Path(tmpdir) / "foip.json"
            config = {
                "description": "Test FoIP run",
                "artifactDirectory": tmpdir,
                "artifactPattern": "*.tiff",
            }
            config_path.write_text(json.dumps(config))

            result = FoipValidator(config_path).run()

            self.assertFalse(result.executed)
            self.assertEqual(len(result.artifacts), 1)
            self.assertTrue(any("dry-run" in error for error in result.errors))


if __name__ == "__main__":
    unittest.main()
