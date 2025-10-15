"""Run context metadata passed to report writers and logs."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from .fax_simulation import FaxProfile


@dataclass
class RunContext:
    run_id: str
    profile: FaxProfile
    policy_name: str
    policy_hash: str
    iterations: int
    seed: int
    reference: Path
    candidate: Path
    path_mode: str
    location: str
    did: Optional[str]
    pcfax_queue: Optional[str]
    started_at: datetime
    ingest_dir: Optional[str] = None
    ingest_pattern: Optional[str] = None
    pcfax_detail: Optional[str] = None

    @property
    def path_label(self) -> str:
        return "Path: Digital" if self.path_mode == "digital" else "Path: Print-Scan"

    @property
    def ecm_label(self) -> str:
        state = "ON" if self.profile.ecm_enabled else "OFF"
        return f"ECM {state} {self.profile.ecm_block_bytes}B"

    @property
    def bitrate_label(self) -> str:
        return f"Max {self.profile.max_bitrate // 1000} kbps"

    @property
    def ingest_label(self) -> Optional[str]:
        if self.ingest_dir:
            return f"Ingest: {self.ingest_dir} ({self.ingest_pattern or '*'})"
        return None
