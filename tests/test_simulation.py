"""Tests for the deterministic fax negotiation simulator."""
from __future__ import annotations

import unittest

from app.core.config_service import default_config_service
from app.core.fax_simulation import FaxProfile, FaxSimulation


class FaxSimulationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        service = default_config_service()
        loaded = service.load("profiles/Brother_V34_33k6_ECM256.json")
        self.profile = FaxProfile.from_config(loaded.payload, loaded.sha256)

    def test_deterministic_results(self) -> None:
        first = FaxSimulation(self.profile, seed=42).run()
        second = FaxSimulation(self.profile, seed=42).run()
        self.assertEqual(first.final_bitrate, second.final_bitrate)
        self.assertEqual(first.fallback_steps, second.fallback_steps)
        self.assertEqual([event.detail for event in first.events], [event.detail for event in second.events])

    def test_seed_changes_results(self) -> None:
        first = FaxSimulation(self.profile, seed=1).run()
        second = FaxSimulation(self.profile, seed=2).run()
        self.assertNotEqual(
            [event.detail for event in first.events],
            [event.detail for event in second.events],
        )


if __name__ == "__main__":
    unittest.main()
