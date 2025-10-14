"""High level orchestration for running fax simulations and verification."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from .fax_simulation import FaxProfile, FaxSimulation, SimulationResult
from .telemetry import TelemetrySink
from ..verify.pipeline import VerificationPipeline, VerificationSummary


@dataclass
class IterationConfig:
    iterations: int
    rng_seed: int


@dataclass
class IterationResult:
    index: int
    simulation: SimulationResult
    verification: Optional[VerificationSummary]


class IterationController:
    """Runs a number of simulated fax iterations and collects results."""

    def __init__(
        self,
        profile: FaxProfile,
        verification_pipeline: VerificationPipeline,
        telemetry: Optional[TelemetrySink] = None,
    ) -> None:
        self.profile = profile
        self.pipeline = verification_pipeline
        self.telemetry = telemetry or TelemetrySink()

    def run(self, iteration_config: IterationConfig, reference: Path, candidate: Path) -> List[IterationResult]:
        results: List[IterationResult] = []
        seed = iteration_config.rng_seed
        for index in range(iteration_config.iterations):
            simulation = FaxSimulation(profile=self.profile, seed=seed + index).run()
            self.telemetry.emit(
                "simulation.completed",
                index=index,
                bitrate=simulation.final_bitrate,
                fallback_steps=simulation.fallback_steps,
            )
            summary = self.pipeline.verify_pair(reference, candidate, simulation)
            results.append(IterationResult(index=index, simulation=simulation, verification=summary))
        return results

    def iter_events(self) -> Iterable[dict]:
        for event in self.telemetry.as_list():
            yield event.to_json()
