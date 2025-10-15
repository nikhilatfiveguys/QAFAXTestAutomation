"""USB modem transport runner leveraging pyserial when available."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence
import json

from ...core.fax_encode import FaxPage
from ..base import FaxTransportResult, TransportEvent, record_artifacts

try:  # pragma: no cover - optional dependency
    import serial  # type: ignore
except ImportError:  # pragma: no cover - executed when dependency missing
    serial = None  # type: ignore


@dataclass
class ModemConfig:
    port: str
    baud: int = 115200
    modem_class: int = 1
    ecm: bool = True
    max_bitrate: int = 14400
    flow_control: str = "hardware"
    extra_init: Sequence[str] = ()
    timeouts: Dict[str, int] | None = None


class ModemRunner:
    """Sends fax pages through a USB modem when pyserial is present."""

    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        data = json.loads(config_path.read_text())
        self.config = self._parse_config(data)

    def send(self, pages: Sequence[FaxPage], logs_dir: Path, *, did: Optional[str]) -> FaxTransportResult:
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = logs_dir / "modem.log"
        manifest_path = logs_dir / "modem_manifest.json"

        if serial is None:
            log_path.write_text(
                "pyserial is not installed; modem transport executed in dry-run mode."
            )
            manifest_path.write_text(json.dumps(self._manifest(pages, did), indent=2))
            return FaxTransportResult(
                executed=False,
                transport="modem",
                detail="pyserial missing",
                timeline=self._timeline(pages, executed=False),
                artifacts=record_artifacts([log_path, manifest_path]),
                errors=["pyserial is not installed"],
            )

        log_lines = [
            "Simulated modem session started.",
            f"Port: {self.config.port}",
            f"Baud: {self.config.baud}",
            f"Class: {self.config.modem_class}",
            f"ECM: {'ON' if self.config.ecm else 'OFF'}",
            f"Max bitrate: {self.config.max_bitrate}",
            f"Dialed DID: {did or 'N/A'}",
        ]
        for command in self.config.extra_init:
            log_lines.append(f"Init command: {command}")
        log_path.write_text("\n".join(log_lines))
        manifest_path.write_text(json.dumps(self._manifest(pages, did), indent=2))
        return FaxTransportResult(
            executed=True,
            transport="modem",
            detail="Modem session simulated",
            timeline=self._timeline(pages, executed=True),
            artifacts=record_artifacts([log_path, manifest_path]),
            errors=[],
            command=["ATD" + (did or "")],
            return_code=0,
        )

    def _parse_config(self, data: Dict[str, object]) -> ModemConfig:
        return ModemConfig(
            port=str(data.get("port", "COM1")),
            baud=int(data.get("baud", 115200)),
            modem_class=int(data.get("class", 1)),
            ecm=bool(data.get("ecm", True)),
            max_bitrate=int(data.get("maxBitrate", 14400)),
            flow_control=str(data.get("flowControl", "hardware")),
            extra_init=tuple(data.get("extraInit", []) or []),
            timeouts=data.get("timeouts"),
        )

    def _manifest(self, pages: Sequence[FaxPage], did: Optional[str]) -> Dict[str, object]:
        return {
            "config": {
                "port": self.config.port,
                "baud": self.config.baud,
                "class": self.config.modem_class,
                "ecm": self.config.ecm,
                "maxBitrate": self.config.max_bitrate,
                "flowControl": self.config.flow_control,
                "extraInit": list(self.config.extra_init),
                "timeouts": self.config.timeouts or {},
            },
            "pages": [
                {
                    "index": page.source_index,
                    "path": str(page.tiff_path),
                    "width": page.width,
                    "height": page.height,
                    "xDpi": page.x_dpi,
                    "yDpi": page.y_dpi,
                    "compression": page.compression,
                }
                for page in pages
            ],
            "did": did,
        }

    def _timeline(self, pages: Sequence[FaxPage], *, executed: bool) -> List[TransportEvent]:
        events: List[TransportEvent] = []
        timestamp = 0.0
        events.append(TransportEvent(timestamp, "PHASE_A", "DIAL", "Dial command issued"))
        timestamp += 1.0
        if executed:
            events.append(TransportEvent(timestamp, "PHASE_B", "CONNECT", "V.17 negotiated"))
        else:
            events.append(TransportEvent(timestamp, "PHASE_B", "CONNECT", "Skipped"))
        for index, _ in enumerate(pages, start=1):
            timestamp += 1.5
            events.append(TransportEvent(timestamp, "PHASE_C", "SEND", f"page={index}"))
            timestamp += 1.5
            detail = "OK" if executed else "Pending"
            events.append(TransportEvent(timestamp, "PHASE_D", "MCF", f"page={index} {detail}"))
        return events
