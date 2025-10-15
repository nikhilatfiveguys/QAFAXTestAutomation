"""Line-based comparison helpers for verification and fallbacks."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

from ..loaders import DocumentData


@dataclass
class LineComparison:
    total_lines: int
    matching_lines: int
    mismatched: List[Tuple[int, str, str]]

    @property
    def mismatch_count(self) -> int:
        return self.total_lines - self.matching_lines

    @property
    def match_ratio(self) -> float:
        if self.total_lines == 0:
            return 1.0
        return self.matching_lines / self.total_lines

    @property
    def mismatch_ratio(self) -> float:
        if self.total_lines == 0:
            return 0.0
        return self.mismatch_count / self.total_lines


def compare_lines(reference: DocumentData, candidate: DocumentData, max_mismatches: int = 10) -> LineComparison:
    return compare_sequences(reference.lines, candidate.lines, max_mismatches=max_mismatches)


def compare_sequences(
    reference_lines: Sequence[str], candidate_lines: Sequence[str], max_mismatches: int = 10
) -> LineComparison:
    total = max(len(reference_lines), len(candidate_lines))
    matching = 0
    mismatched: List[Tuple[int, str, str]] = []
    for index in range(total):
        ref_line = reference_lines[index] if index < len(reference_lines) else ""
        cand_line = candidate_lines[index] if index < len(candidate_lines) else ""
        if ref_line == cand_line:
            matching += 1
        elif len(mismatched) < max_mismatches:
            mismatched.append((index + 1, ref_line, cand_line))
    return LineComparison(total_lines=total, matching_lines=matching, mismatched=mismatched)
