"""HP PC-Fax queue connector stubs for future expansion."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class PCFaxJob:
    """Placeholder representation of a queued HP PC-Fax job."""

    queue_name: str
    document_path: str
    did: Optional[str] = None


def submit_job(job: PCFaxJob) -> None:
    """Stub submission routine.

    The MVP does not integrate with the real HP PC-Fax pipeline. This function exists so
    callers can be wired up later without changing imports.
    """

    raise NotImplementedError("HP PC-Fax integration will be implemented in a future release")
