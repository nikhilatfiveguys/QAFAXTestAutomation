"""Preprocessing helpers used by the verification pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib


@dataclass
class DocumentData:
    path: Path
    content: bytes
    sha256: str

    @property
    def size(self) -> int:
        return len(self.content)


def load_document(path: Path) -> DocumentData:
    content = path.read_bytes()
    sha256 = hashlib.sha256(content).hexdigest()
    return DocumentData(path=path, content=content, sha256=sha256)
