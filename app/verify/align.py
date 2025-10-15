"""Page alignment helpers with deterministic fallbacks."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple
import math
import os
import sys

from .loaders import DocumentData, DocumentPage
from .metrics import lines

try:  # Optional dependency used when available.
    import numpy as _np  # type: ignore
except Exception:  # pragma: no cover - NumPy is optional for tests.
    _np = None  # type: ignore


@dataclass
class PagePair:
    """Represents an aligned page pair with a confidence score."""

    index: int
    reference: DocumentPage
    candidate: DocumentPage
    confidence: float


def align_documents(
    reference: DocumentData,
    candidate: DocumentData,
    *,
    low_confidence_threshold: float = 0.6,
) -> Tuple[List[PagePair], List[str]]:
    """Align pages using lightweight similarity heuristics.

    The routine attempts to match each candidate page with the best scoring reference
    page. When similarity is high, the match is accepted automatically. If the score
    falls below ``low_confidence_threshold`` and the CLI is running interactively, a
    manual prompt is offered so operators can override the mapping. Non-interactive
    runs record warnings when low-confidence matches occur.
    """

    if not reference.pages or not candidate.pages:
        pairs, warnings = _pair_by_index(reference.pages, candidate.pages)
        if reference.page_count != candidate.page_count:
            warnings.append(
                f"Page count mismatch (ref={reference.page_count}, cand={candidate.page_count}); extra pages ignored."
            )
        return pairs, warnings

    similarity = _similarity_matrix(reference.pages, candidate.pages)
    unmatched_refs = set(range(len(reference.pages)))
    warnings: List[str] = []
    pairs: List[PagePair] = []

    for cand_index, cand_page in enumerate(candidate.pages):
        if not unmatched_refs:
            warnings.append(
                f"Candidate has extra page at index {cand_index}; no reference counterpart available."
            )
            break
        best_ref = max(unmatched_refs, key=lambda idx: similarity[idx][cand_index])
        best_score = similarity[best_ref][cand_index]
        chosen_ref = best_ref
        chosen_score = best_score

        if chosen_score < low_confidence_threshold:
            override = _prompt_manual_choice(
                cand_index,
                unmatched_refs,
                similarity,
            )
            if override is not None and override in unmatched_refs:
                chosen_ref = override
                chosen_score = similarity[chosen_ref][cand_index]
                warnings.append(
                    f"Manual alignment override: candidate page {cand_index} → reference page {chosen_ref}"
                )
            else:
                warnings.append(
                    f"Low alignment confidence for candidate page {cand_index} (score={best_score:.2f})."
                )

        pairs.append(
            PagePair(
                index=len(pairs),
                reference=reference.pages[chosen_ref],
                candidate=cand_page,
                confidence=chosen_score,
            )
        )
        unmatched_refs.remove(chosen_ref)

    if unmatched_refs:
        warnings.append(
            f"Reference has {len(unmatched_refs)} unmatched page(s): {sorted(unmatched_refs)}"
        )

    if reference.page_count != candidate.page_count:
        warnings.append(
            f"Page count mismatch (ref={reference.page_count}, cand={candidate.page_count}); alignment limited to {len(pairs)} pair(s)."
        )

    pairs.sort(key=lambda pair: pair.reference.index)
    for new_index, pair in enumerate(pairs):
        pair.index = new_index

    return pairs, warnings


def _pair_by_index(
    reference_pages: Sequence[DocumentPage], candidate_pages: Sequence[DocumentPage]
) -> Tuple[List[PagePair], List[str]]:
    count = min(len(reference_pages), len(candidate_pages))
    pairs = [
        PagePair(index=index, reference=reference_pages[index], candidate=candidate_pages[index], confidence=1.0)
        for index in range(count)
    ]
    warnings: List[str] = []
    return pairs, warnings


def _similarity_matrix(
    reference_pages: Sequence[DocumentPage], candidate_pages: Sequence[DocumentPage]
) -> List[List[float]]:
    matrix: List[List[float]] = []
    total_ref = len(reference_pages)
    total_cand = len(candidate_pages)
    for ref_index, ref_page in enumerate(reference_pages):
        row: List[float] = []
        for cand_index, cand_page in enumerate(candidate_pages):
            score = _page_similarity(ref_page, cand_page, ref_index, cand_index, total_ref, total_cand)
            row.append(score)
        matrix.append(row)
    return matrix


def _page_similarity(
    reference: DocumentPage,
    candidate: DocumentPage,
    ref_index: int,
    cand_index: int,
    total_ref: int,
    total_cand: int,
) -> float:
    scores: List[float] = []

    if reference.text_lines or candidate.text_lines:
        comparison = lines.compare_sequences(reference.text_lines, candidate.text_lines)
        scores.append(comparison.match_ratio)

    image_score = _image_similarity(reference, candidate)
    if image_score is not None:
        scores.append(image_score)

    if not scores:
        # When we have no textual or image data, default to a neutral score and rely on ordering.
        scores.append(0.5)

    order_penalty = abs(ref_index - cand_index) / max(total_ref, total_cand, 1)
    order_score = 1.0 - min(1.0, order_penalty)

    content_score = sum(scores) / len(scores)
    blended = (content_score * 0.8) + (order_score * 0.2)
    return max(0.0, min(1.0, blended))


def _image_similarity(reference: DocumentPage, candidate: DocumentPage) -> float | None:
    if _np is None or reference.image is None or candidate.image is None:
        return None

    ref_image = reference.image.astype(_np.float32)
    cand_image = candidate.image.astype(_np.float32)
    height = int(min(ref_image.shape[0], cand_image.shape[0]))
    width = int(min(ref_image.shape[1], cand_image.shape[1]))
    if height == 0 or width == 0:
        return None

    ref_crop = ref_image[:height, :width]
    cand_crop = cand_image[:height, :width]
    difference = _np.abs(ref_crop - cand_crop)
    mae = float(_np.mean(difference))
    if math.isfinite(mae):
        return max(0.0, min(1.0, 1.0 - (mae / 255.0)))
    return None


def _prompt_manual_choice(
    cand_index: int,
    unmatched_refs: Iterable[int],
    similarity: List[List[float]],
) -> int | None:
    if not _allow_manual_prompt():
        return None

    available = sorted(unmatched_refs)
    suggestions = sorted(
        available,
        key=lambda idx: similarity[idx][cand_index],
        reverse=True,
    )[:3]

    print(
        f"Low-confidence alignment for candidate page {cand_index}.",
        f"Suggested reference pages: {suggestions}",
        "(press Enter to accept highest score or type a reference index)",
        sep="\n",
        flush=True,
    )
    try:
        response = input("Reference page index> ").strip()
    except (EOFError, KeyboardInterrupt):  # pragma: no cover - defensive.
        return None

    if response == "":
        return suggestions[0] if suggestions else None

    try:
        choice = int(response)
    except ValueError:
        print("Invalid entry; keeping automatic alignment.")
        return None

    if choice not in available:
        print(f"Reference index {choice} not available; keeping automatic alignment.")
        return None
    return choice


def _allow_manual_prompt() -> bool:
    if os.environ.get("QAFAX_DISABLE_PROMPTS", "0") == "1":
        return False
    return sys.stdin.isatty() and sys.stdout.isatty()
