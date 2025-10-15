"""SMB/Share ingest helpers with stable-size polling."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List
import fnmatch
import hashlib
import os
import time


@dataclass
class IngestedArtifact:
    path: Path
    size: int
    sha256: str
    captured_at: float


class SMBIngestor:
    """Poll a directory for new files that stabilise in size."""

    def __init__(
        self,
        root: Path,
        pattern: str = "*",
        stable_polls: int = 3,
        interval: float = 1.0,
    ) -> None:
        self.root = root
        self.pattern = pattern
        self.stable_polls = stable_polls
        self.interval = interval

    def snapshot(self) -> Dict[Path, int]:
        return {path: path.stat().st_size for path in self._iter_matching()}

    def detect_new(self, baseline: Dict[Path, int], timeout: float = 0.0) -> List[IngestedArtifact]:
        deadline = time.time() + timeout
        seen = dict(baseline)
        artifacts: List[IngestedArtifact] = []
        while True:
            for path in self._iter_matching():
                try:
                    size = path.stat().st_size
                except FileNotFoundError:
                    continue
                if path in seen and seen[path] == size:
                    continue
                if not self._is_stable(path, size):
                    continue
                sha = _sha256(path)
                artifacts.append(IngestedArtifact(path=path, size=size, sha256=sha, captured_at=time.time()))
                seen[path] = size
            if artifacts or time.time() >= deadline:
                return artifacts
            time.sleep(self.interval)

    def _is_stable(self, path: Path, initial_size: int) -> bool:
        size = initial_size
        consecutive = 0
        for _ in range(self.stable_polls):
            time.sleep(self.interval)
            try:
                current = path.stat().st_size
            except FileNotFoundError:
                return False
            if current == size:
                consecutive += 1
            else:
                consecutive = 0
                size = current
            if consecutive >= self.stable_polls - 1:
                return True
        return False

    def _iter_matching(self) -> Iterable[Path]:
        if not self.root.exists():
            return []
        return [
            Path(entry.path)
            for entry in os.scandir(self.root)
            if entry.is_file()
            and fnmatch.fnmatch(entry.name, self.pattern)
            and not entry.name.lower().endswith((".tmp", ".partial"))
        ]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
