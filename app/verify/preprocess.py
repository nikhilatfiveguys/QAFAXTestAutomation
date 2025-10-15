"""Preprocessing helpers used by the verification pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List
import hashlib


@dataclass
class DocumentData:
    """Container for loaded document bytes and decoded text lines."""

    path: Path
    content: bytes
    sha256: str
    lines: List[str]

    @property
    def size(self) -> int:
        return len(self.content)


def load_document(path: Path) -> DocumentData:
    """Load a document from disk and decode its text content."""

    content = path.read_bytes()
    sha256 = hashlib.sha256(content).hexdigest()
    text = content.decode("utf-8", errors="replace")
    lines = text.splitlines()
    return DocumentData(path=path, content=content, sha256=sha256, lines=lines)
