"""Placeholder skew metric that assumes digital inputs."""
from __future__ import annotations

from ..preprocess import DocumentData


def estimate_skew_degrees(_: DocumentData) -> float:
    return 0.0
