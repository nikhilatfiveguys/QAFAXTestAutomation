"""Page alignment helpers with deterministic fallbacks."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from .loaders import DocumentData, DocumentPage


@dataclass
class PagePair:
    index: int
    reference: DocumentPage
    candidate: DocumentPage
    confidence: float


def align_documents(reference: DocumentData, candidate: DocumentData) -> Tuple[List[PagePair], List[str]]:
    """Align pages using order-based heuristics with TODO for advanced matching."""

    pairs: List[PagePair] = []
    warnings: List[str] = []
    count = min(reference.page_count, candidate.page_count)
    for index in range(count):
        pairs.append(PagePair(index=index, reference=reference.pages[index], candidate=candidate.pages[index], confidence=1.0))
    if reference.page_count != candidate.page_count:
        warnings.append(
            f"Page count mismatch (ref={reference.page_count}, cand={candidate.page_count}); extra pages ignored."
        )
    return pairs, warnings
