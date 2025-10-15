"""Tests for configuration loading helpers."""
from __future__ import annotations

import unittest

from app.core.config_service import default_config_service


class ConfigServiceTestCase(unittest.TestCase):
    def test_load_profile(self) -> None:
        service = default_config_service()
        loaded = service.load("profiles/Brother_V34_33k6_ECM256.json")
        self.assertEqual(loaded.payload["name"], "Brother_V34_33k6_ECM256")
        self.assertEqual(len(loaded.sha256), 64)


if __name__ == "__main__":
    unittest.main()
