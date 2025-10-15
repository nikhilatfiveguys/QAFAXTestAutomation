"""FoIP/T.38 validation helpers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence
import glob
import hashlib
import json
import subprocess


@dataclass
class FoipArtifact:
    path: Path
    size: int
    sha256: str
    captured_at: datetime

    def to_dict(self) -> Dict[str, object]:
        return {
            "path": str(self.path),
            "size": self.size,
            "sha256": self.sha256,
            "capturedAt": self.captured_at.isoformat(),
        }


@dataclass
class FoipResult:
    executed: bool
    detail: str
    artifacts: List[FoipArtifact]
    errors: List[str]
    command: Optional[Sequence[str]] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "executed": self.executed,
            "detail": self.detail,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "errors": list(self.errors),
            "command": list(self.command) if self.command else None,
        }


class FoipValidator:
    """Execute FoIP validation according to a JSON configuration file."""

    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        with config_path.open("r", encoding="utf-8") as handle:
            self.config = json.load(handle)

    def run(self) -> FoipResult:
        command = self._command()
        detail = self.config.get("description", "FoIP validation")
        errors: List[str] = []
        executed = False

        if command:
            timeout = float(self.config.get("timeout", 60.0))
            try:
                completed = subprocess.run(
                    command,
                    cwd=self._working_directory(),
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False,
                )
                executed = True
                if completed.returncode != 0:
                    errors.append(
                        f"Command exited with {completed.returncode}: {completed.stderr.strip()}"
                    )
                detail = completed.stdout.strip() or detail
            except FileNotFoundError:
                errors.append("FoIP command not found; ensure dependencies are installed")
            except subprocess.TimeoutExpired:
                errors.append(f"FoIP command timed out after {timeout} seconds")
        else:
            errors.append("No FoIP command provided; run recorded as dry-run")

        artifacts = self._collect_artifacts()
        if not artifacts:
            errors.append("No FoIP artifacts discovered")

        return FoipResult(
            executed=executed,
            detail=detail,
            artifacts=artifacts,
            errors=errors,
            command=command,
        )

    def _command(self) -> Optional[Sequence[str]]:
        command = self.config.get("command")
        if isinstance(command, list) and all(isinstance(item, str) for item in command):
            return command
        return None

    def _working_directory(self) -> Optional[str]:
        work_dir = self.config.get("workingDirectory")
        if isinstance(work_dir, str) and work_dir:
            return work_dir
        return None

    def _collect_artifacts(self) -> List[FoipArtifact]:
        pattern = self.config.get("artifactPattern")
        root = self.config.get("artifactDirectory")
        if not pattern or not root:
            return []
        paths = sorted(Path(path) for path in glob.glob(str(Path(root) / pattern)))
        artifacts: List[FoipArtifact] = []
        for path in paths:
            if not path.exists():
                continue
            try:
                size = path.stat().st_size
                sha = _sha256(path)
                artifacts.append(
                    FoipArtifact(
                        path=path,
                        size=size,
                        sha256=sha,
                        captured_at=datetime.utcnow(),
                    )
                )
            except OSError:
                # Surface the issue but continue so callers can inspect partial results.
                artifacts.append(
                    FoipArtifact(
                        path=path,
                        size=0,
                        sha256="",
                        captured_at=datetime.utcnow(),
                    )
                )
        return artifacts


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
