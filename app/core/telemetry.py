"""Lightweight telemetry collector for structured event logging."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List
import json


@dataclass
class TelemetryEvent:
    name: str
    timestamp: datetime
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "timestamp": self.timestamp.isoformat(timespec="milliseconds"),
            "payload": self.payload,
        }


class TelemetrySink:
    """In-memory collection with optional persistent flush."""

    def __init__(self) -> None:
        self._events: List[TelemetryEvent] = []

    def emit(self, name: str, **payload: Any) -> None:
        self._events.append(TelemetryEvent(name=name, timestamp=datetime.utcnow(), payload=payload))

    def extend(self, events: Iterable[TelemetryEvent]) -> None:
        self._events.extend(events)

    def as_list(self) -> List[TelemetryEvent]:
        return list(self._events)

    def flush_to_file(self, path: Path) -> None:
        data = [event.to_json() for event in self._events]
        path.write_text(json.dumps(data, indent=2))
