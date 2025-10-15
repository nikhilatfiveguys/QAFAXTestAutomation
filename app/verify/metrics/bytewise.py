"""Simplified byte-oriented metrics for placeholder verification."""
from __future__ import annotations

from dataclasses import dataclass
from math import log10
from typing import Tuple

from ..preprocess import DocumentData


@dataclass
class BytewiseComparison:
    mse: float
    psnr: float
    similarity: float


def compare(reference: DocumentData, candidate: DocumentData) -> BytewiseComparison:
    ref = reference.content
    cand = candidate.content
    length = max(len(ref), len(cand), 1)
    padded_ref, padded_cand = _pad(ref, cand, length)
    diff_sq = 0.0
    matches = 0
    for rb, cb in zip(padded_ref, padded_cand):
        if rb == cb:
            matches += 1
        diff_sq += (rb - cb) ** 2
    mse = diff_sq / length
    if mse == 0:
        psnr = float("inf")
    else:
        psnr = 20 * log10(255.0 / (mse ** 0.5))
    similarity = matches / length
    return BytewiseComparison(mse=mse, psnr=psnr, similarity=similarity)


def _pad(ref: bytes, cand: bytes, length: int) -> Tuple[bytes, bytes]:
    if len(ref) == len(cand) == length:
        return ref, cand
    padded_ref = ref.ljust(length, b"\x00")
    padded_cand = cand.ljust(length, b"\x00")
    return padded_ref, padded_cand
