"""Unit tests for the SNMP connector helpers."""
from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

from app.connectors import snmp


class SNMPConnectorTestCase(unittest.TestCase):
    def test_missing_dependency_returns_error(self) -> None:
        with patch.dict(sys.modules, {"pysnmp": None}):
            snapshot = snmp.query_status("127.0.0.1", "public", ["1.3.6.1.2.1.1.1.0"])
        self.assertTrue(snapshot.errors)
        self.assertEqual(snapshot.values, {})

    def test_to_dict_structure(self) -> None:
        snapshot = snmp.SNMPSnapshot(
            target="printer", community="public", values={"oid": "value"}, errors=[], captured_at=snapshot_time()
        )
        payload = snapshot.to_dict()
        self.assertEqual(payload["target"], "printer")
        self.assertIn("capturedAt", payload)


def snapshot_time():
    from datetime import datetime

    return datetime.utcnow()


if __name__ == "__main__":
    unittest.main()
