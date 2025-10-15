"""Shared transport dataclasses for fax sending implementations."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional
import hashlib


@dataclass
class ArtifactRecord:
    """Represents a file generated during transport execution."""

    path: Path
    size: int
    sha256: str

    @classmethod
    def from_path(cls, path: Path) -> "ArtifactRecord":
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        return cls(path=path, size=len(data), sha256=digest)

    def to_dict(self) -> dict:
        return {"path": str(self.path), "size": self.size, "sha256": self.sha256}


@dataclass
class TransportEvent:
    """Structured negotiation event emitted by transports."""

    timestamp: float
    phase: str
    event: str
    detail: str


@dataclass
class FaxTransportResult:
    """Outcome from running a fax transport implementation."""

    executed: bool
    transport: str
    detail: str
    timeline: List[TransportEvent]
    artifacts: List[ArtifactRecord]
    errors: List[str]
    command: Optional[List[str]] = None
    return_code: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "executed": self.executed,
            "transport": self.transport,
            "detail": self.detail,
            "timeline": [
                {
                    "timestamp": event.timestamp,
                    "phase": event.phase,
                    "event": event.event,
                    "detail": event.detail,
                }
                for event in self.timeline
            ],
            "artifacts": [record.to_dict() for record in self.artifacts],
            "errors": list(self.errors),
            "command": self.command,
            "returnCode": self.return_code,
        }


def record_artifacts(paths: Iterable[Path]) -> List[ArtifactRecord]:
    """Convert a list of paths to artifact records while filtering missing files."""

    records: List[ArtifactRecord] = []
    for path in paths:
        if path.exists():
            records.append(ArtifactRecord.from_path(path))
    return records
