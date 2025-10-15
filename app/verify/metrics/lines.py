"""Line-based comparison helpers for placeholder verification results."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from ..preprocess import DocumentData


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
    total = max(len(reference.lines), len(candidate.lines))
    matching = 0
    mismatched: List[Tuple[int, str, str]] = []
    for index in range(total):
        ref_line = reference.lines[index] if index < len(reference.lines) else ""
        cand_line = candidate.lines[index] if index < len(candidate.lines) else ""
        if ref_line == cand_line:
            matching += 1
        elif len(mismatched) < max_mismatches:
            mismatched.append((index + 1, ref_line, cand_line))
    return LineComparison(total_lines=total, matching_lines=matching, mismatched=mismatched)
