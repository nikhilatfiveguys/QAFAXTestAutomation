"""Lightweight T.30 negotiation simulator used by the CLI MVP."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from random import Random
from typing import Dict, Iterable, List


class Transport(str, Enum):
    SIMULATOR = "sim"
    T38 = "t38"


@dataclass
class FaxProfile:
    """Profile metadata loaded from configuration files."""

    name: str
    standard: str
    max_bitrate: int
    bitrate_steps: List[int]
    ecm_enabled: bool
    ecm_block_bytes: int
    fallback_policy: str
    config_sha256: str
    transport: Transport = Transport.SIMULATOR

    @classmethod
    def from_config(cls, payload: Dict[str, object], sha256: str) -> "FaxProfile":
        return cls(
            name=str(payload["name"]),
            standard=str(payload["standard"]),
            max_bitrate=int(payload.get("maxBitrateBps", 33600)),
            bitrate_steps=[int(value) for value in payload.get("bitrateStepsBps", [33600, 31200, 28800, 26400, 24000])],
            ecm_enabled=bool(payload.get("ecm", {}).get("enabled", True)),
            ecm_block_bytes=int(payload.get("ecm", {}).get("blockBytes", 256)),
            fallback_policy=str(payload.get("fallbackPolicy", "graceful")),
            config_sha256=sha256,
            transport=Transport(str(payload.get("transport", "sim"))),
        )

    @property
    def brand(self) -> str:
        """Best-effort brand extraction from the profile name."""

        return self.name.split("_", 1)[0]


@dataclass
class NegotiationEvent:
    timestamp: float
    phase: str
    event: str
    detail: str


@dataclass
class SimulationResult:
    profile: FaxProfile
    events: List[NegotiationEvent]
    final_bitrate: int
    fallback_steps: int
    rng_seed: int


class FaxSimulation:
    """Produces deterministic negotiation logs based on seeded randomness."""

    CFR_THRESHOLD_DB = -2.5

    def __init__(self, profile: FaxProfile, seed: int) -> None:
        self.profile = profile
        self.seed = seed
        self._random = Random(seed)

    def _generate_phase_b_events(self) -> Iterable[NegotiationEvent]:
        yield NegotiationEvent(0.000, "PHASE_B", "DIS", self._dis_detail())

    def _dis_detail(self) -> str:
        ecm = "ON" if self.profile.ecm_enabled else "OFF"
        return f"STD:{self.profile.standard}, ECM:{ecm}, MAX:{self.profile.max_bitrate}bps"

    def _simulate_margin(self, bitrate: int) -> float:
        base_margin = 3.0 - (bitrate / max(self.profile.bitrate_steps)) * 3.0
        noise = self._random.uniform(-2.0, 2.0)
        return base_margin + noise

    def run(self) -> SimulationResult:
        events: List[NegotiationEvent] = list(self._generate_phase_b_events())
        current_bitrate = self.profile.max_bitrate
        steps = 0
        timestamp = 0.420

        for bitrate in self.profile.bitrate_steps:
            timestamp += 0.100
            margin = self._simulate_margin(bitrate)
            events.append(NegotiationEvent(timestamp, self.profile.standard, "TCF", f"margin={margin:.2f}dB @ {bitrate}"))
            if margin >= self.CFR_THRESHOLD_DB:
                events.append(NegotiationEvent(timestamp + 0.5, "PHASE_B", "CFR", "ok"))
                current_bitrate = bitrate
                break
            steps += 1
            events.append(
                NegotiationEvent(
                    timestamp + 0.01,
                    self.profile.standard,
                    "FALLBACK",
                    f"{bitrate}→{self._next_bitrate(bitrate)} bps",
                )
            )
        else:
            current_bitrate = self.profile.bitrate_steps[-1]
            events.append(NegotiationEvent(timestamp + 0.5, "PHASE_B", "CFR", "forced accept"))

        events.append(
            NegotiationEvent(timestamp + 1.0, "PHASE_C", "START", f"ecm={self.profile.ecm_block_bytes}B")
        )
        events.append(NegotiationEvent(timestamp + 3.0, "PHASE_D", "MCF", "retransmits=0"))
        return SimulationResult(
            profile=self.profile,
            events=events,
            final_bitrate=current_bitrate,
            fallback_steps=steps,
            rng_seed=self.seed,
        )

    def _next_bitrate(self, bitrate: int) -> int:
        try:
            idx = self.profile.bitrate_steps.index(bitrate)
        except ValueError:
            return bitrate
        if idx + 1 < len(self.profile.bitrate_steps):
            return self.profile.bitrate_steps[idx + 1]
        return bitrate
