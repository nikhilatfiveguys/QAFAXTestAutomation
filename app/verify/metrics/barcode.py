"""Simple barcode proxy that searches for known tokens."""
from __future__ import annotations

from typing import Iterable

from ..preprocess import DocumentData


KNOWN_TOKENS = {"QR", "BARCODE", "CODE128", "CODE39"}


def detect_tokens(doc: DocumentData) -> Iterable[str]:
    try:
        text = doc.content.decode("utf-8").upper()
    except UnicodeDecodeError:
        return []
    return [token for token in KNOWN_TOKENS if token in text]
