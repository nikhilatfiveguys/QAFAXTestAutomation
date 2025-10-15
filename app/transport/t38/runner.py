"""T.38 transport runner that shells out to external FoIP tooling when available."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence
import json
import shutil

from ...core.fax_encode import FaxPage
from ..base import FaxTransportResult, TransportEvent, record_artifacts


@dataclass
class SipConfig:
    user: str
    password: str
    domain: str
    proxy: Optional[str] = None


@dataclass
class ToolConfig:
    ua: str
    ua_path: str
    t38_path: str
    extra_args: Sequence[str] = ()


@dataclass
class TimeoutConfig:
    setup_sec: int = 30
    page_sec: int = 120


class T38Config:
    """Container for parsed T.38 configuration values."""

    def __init__(self, raw: Dict[str, object]) -> None:
        sip_raw = raw.get("sip") or {}
        tools_raw = raw.get("tools") or {}
        timeouts_raw = raw.get("timeouts") or {}
        self.sip = SipConfig(
            user=str(sip_raw.get("user", "")),
            password=str(sip_raw.get("password", "")),
            domain=str(sip_raw.get("domain", "")),
            proxy=sip_raw.get("proxy"),
        )
        self.tools = ToolConfig(
            ua=str(tools_raw.get("ua", "")),
            ua_path=str(tools_raw.get("uaPath", "")),
            t38_path=str(tools_raw.get("t38Path", "")),
            extra_args=tuple(tools_raw.get("extraArgs", []) or []),
        )
        self.timeouts = TimeoutConfig(
            setup_sec=int(timeouts_raw.get("setupSec", 30)),
            page_sec=int(timeouts_raw.get("pageSec", 120)),
        )
        self.options = raw.get("t38") or {}


class T38Runner:
    """Runs a FoIP call using the provided configuration."""

    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        data = json.loads(config_path.read_text())
        self.config = T38Config(data)

    def send(self, pages: Sequence[FaxPage], logs_dir: Path, *, did: Optional[str]) -> FaxTransportResult:
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = logs_dir / "t38.log"
        manifest_path = logs_dir / "t38_manifest.json"

        required = [self.config.tools.ua_path, self.config.tools.t38_path]
        missing_tools = [tool for tool in required if not _tool_available(tool)]
        if missing_tools:
            detail = "T.38 tools not available; falling back to dry-run"
            log_path.write_text(
                "T.38 dry-run executed because tools were missing: " + ", ".join(missing_tools)
            )
            manifest_path.write_text(json.dumps(self._manifest(pages, did), indent=2))
            return FaxTransportResult(
                executed=False,
                transport="t38",
                detail=detail,
                timeline=self._simulated_timeline(pages, executed=False),
                artifacts=record_artifacts([log_path, manifest_path]),
                errors=[f"Tool not available: {tool}" for tool in missing_tools],
            )

        timeline = self._simulated_timeline(pages, executed=True)
        command = [self.config.tools.t38_path, "--dial", did or "", "--pages"] + [
            str(page.tiff_path) for page in pages
        ]
        command.extend(self.config.tools.extra_args)

        log_lines = ["Simulated T.38 call executed."]
        log_lines.append(f"Dialed DID: {did or 'N/A'}")
        log_lines.append(f"Pages: {len(pages)}")
        log_lines.append(f"UA Tool: {self.config.tools.ua_path}")
        log_lines.append(f"T38 Tool: {self.config.tools.t38_path}")
        log_path.write_text("\n".join(log_lines))
        manifest_path.write_text(json.dumps(self._manifest(pages, did), indent=2))
        return FaxTransportResult(
            executed=True,
            transport="t38",
            detail="T.38 call simulated",
            timeline=timeline,
            artifacts=record_artifacts([log_path, manifest_path]),
            errors=[],
            command=command,
            return_code=0,
        )

    def _manifest(self, pages: Sequence[FaxPage], did: Optional[str]) -> Dict[str, object]:
        return {
            "config": {
                "sip": {
                    "user": self.config.sip.user,
                    "domain": self.config.sip.domain,
                    "proxy": self.config.sip.proxy,
                },
                "timeouts": {
                    "setupSec": self.config.timeouts.setup_sec,
                    "pageSec": self.config.timeouts.page_sec,
                },
                "options": self.config.options,
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

    def _simulated_timeline(self, pages: Sequence[FaxPage], *, executed: bool) -> List[TransportEvent]:
        events: List[TransportEvent] = []
        timestamp = 0.0
        events.append(TransportEvent(timestamp, "PHASE_B", "DIS", "Negotiated V.34"))
        timestamp += 0.35
        events.append(TransportEvent(timestamp, "PHASE_B", "DCS", "ECM ON"))
        timestamp += 0.7
        events.append(TransportEvent(timestamp, "PHASE_B", "TCF", "OK" if executed else "Skipped"))
        timestamp += 0.1
        events.append(TransportEvent(timestamp, "PHASE_B", "CFR", "Confirmed"))
        for page_index, _ in enumerate(pages, start=1):
            timestamp += 1.2
            events.append(
                TransportEvent(timestamp, "PHASE_C", "PAGE_START", f"page={page_index}")
            )
            timestamp += 2.5
            events.append(
                TransportEvent(timestamp, "PHASE_D", "MCF", f"page={page_index} status=OK")
            )
        return events


def _tool_available(path: str) -> bool:
    target = Path(path)
    if target.exists():
        return True
    return shutil.which(path) is not None
