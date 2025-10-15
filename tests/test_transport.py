from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.core.fax_encode import FaxPage
from app.transport.modem.runner import ModemRunner
from app.transport.t38.runner import T38Runner


class TransportRunnerTests(unittest.TestCase):
    def _sample_page(self, directory: Path) -> FaxPage:
        page_path = directory / "page_001.tiff"
        page_path.write_bytes(b"fake tiff data")
        return FaxPage(
            source_index=0,
            tiff_path=page_path,
            width=1728,
            height=2200,
            x_dpi=204,
            y_dpi=196,
            compression="group4",
        )

    def test_t38_runner_handles_missing_tools(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            config = {
                "sip": {"user": "1001", "password": "secret", "domain": "sip.example.com"},
                "tools": {"ua": "pjsua", "uaPath": "no-such-ua", "t38Path": "no-such-t38"},
            }
            config_path = tmp_path / "t38.json"
            config_path.write_text(json.dumps(config))
            runner = T38Runner(config_path)
            page = self._sample_page(tmp_path)
            result = runner.send([page], tmp_path, did="18005551212")
            self.assertFalse(result.executed)
            self.assertEqual(result.transport, "t38")
            self.assertTrue(result.errors)
            self.assertTrue(result.artifacts)

    def test_modem_runner_dry_run_without_pyserial(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            config_path = tmp_path / "modem.json"
            config_path.write_text(json.dumps({"port": "COM3"}))
            runner = ModemRunner(config_path)
            page = self._sample_page(tmp_path)
            with patch("app.transport.modem.runner.serial", None):
                result = runner.send([page], tmp_path, did="18005551212")
            self.assertEqual(result.transport, "modem")
            self.assertFalse(result.executed)
            self.assertTrue(result.errors)
            self.assertTrue(result.artifacts)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
