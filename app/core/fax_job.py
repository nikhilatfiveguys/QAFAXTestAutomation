"""Fax job orchestration for built-in transports."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .fax_encode import FaxPage, encode_to_fax_tiff
from ..transport.base import FaxTransportResult


@dataclass
class TransportOptions:
    """Transport selection and configuration for a fax job."""

    mode: str
    did: Optional[str]
    t38_config: Optional[Path] = None
    modem_config: Optional[Path] = None


@dataclass
class FaxJobResult:
    """Outcome of preparing pages and optionally running a transport."""

    pages: List[FaxPage]
    transport_result: Optional[FaxTransportResult]


class FaxJob:
    """Prepare fax pages and execute transports based on configuration."""

    def __init__(self, source: Path, run_dir: Path) -> None:
        self.source = source
        self.run_dir = run_dir
        self.pages_dir = run_dir / "transport" / "pages"
        self.logs_dir = run_dir / "transport" / "logs"
        self.pages_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def execute(self, options: TransportOptions) -> FaxJobResult:
        pages = encode_to_fax_tiff(self.source, self.pages_dir)
        transport_result: Optional[FaxTransportResult] = None
        if options.mode == "t38":
            transport_result = _run_t38(pages, self.logs_dir, options)
        elif options.mode == "modem":
            transport_result = _run_modem(pages, self.logs_dir, options)
        return FaxJobResult(pages=pages, transport_result=transport_result)


def _run_t38(pages: List[FaxPage], logs_dir: Path, options: TransportOptions) -> FaxTransportResult:
    from ..transport.t38.runner import T38Runner

    if options.t38_config is None:
        return FaxTransportResult(
            executed=False,
            transport="t38",
            detail="Missing T.38 configuration",
            timeline=[],
            artifacts=[],
            errors=["t38_config not provided"],
        )

    runner = T38Runner(options.t38_config)
    return runner.send(pages, logs_dir, did=options.did)


def _run_modem(pages: List[FaxPage], logs_dir: Path, options: TransportOptions) -> FaxTransportResult:
    from ..transport.modem.runner import ModemRunner

    if options.modem_config is None:
        return FaxTransportResult(
            executed=False,
            transport="modem",
            detail="Missing modem configuration",
            timeline=[],
            artifacts=[],
            errors=["modem_config not provided"],
        )

    runner = ModemRunner(options.modem_config)
    return runner.send(pages, logs_dir, did=options.did)
