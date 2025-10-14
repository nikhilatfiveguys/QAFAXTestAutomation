"""Approximate noise metric using byte transitions."""
from __future__ import annotations

from ..preprocess import DocumentData


def noise_index(doc: DocumentData) -> float:
    if doc.size < 2:
        return 0.0
    transitions = 0
    last = doc.content[0]
    for value in doc.content[1:]:
        if value != last:
            transitions += 1
        last = value
    return transitions / (doc.size - 1)
