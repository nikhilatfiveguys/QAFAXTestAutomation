"""Very small OCR proxy that counts alphanumeric coverage in text documents."""
from __future__ import annotations

from typing import Tuple

from ..preprocess import DocumentData


def ocr_accuracy(doc: DocumentData) -> Tuple[float, int, int]:
    try:
        text = doc.content.decode("utf-8")
    except UnicodeDecodeError:
        return 0.0, 0, doc.size
    alpha = sum(1 for ch in text if ch.isalnum())
    total = len(text)
    if total == 0:
        return 1.0, alpha, total
    return alpha / total, alpha, total
