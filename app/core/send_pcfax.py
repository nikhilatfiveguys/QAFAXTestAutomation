"""HP PC-Fax queue submission helpers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import os


@dataclass
class PCFaxJobResult:
    submitted: bool
    queue: Optional[str]
    detail: str


def submit_to_queue(document: Path, queue_name: str, did: Optional[str] = None) -> PCFaxJobResult:
    """Submit a document to an HP PC-Fax queue when the OS supports it."""

    if os.name != "nt":
        return PCFaxJobResult(submitted=False, queue=queue_name, detail="PC-Fax supported on Windows only.")

    try:
        import win32print  # type: ignore
    except Exception:  # pragma: no cover - pywin32 optional
        return PCFaxJobResult(submitted=False, queue=queue_name, detail="pywin32 not available; dry-run only.")

    handle = win32print.OpenPrinter(queue_name)
    try:
        job = (document.name, None, "RAW")
        job_id = win32print.StartDocPrinter(handle, 1, job)
        win32print.StartPagePrinter(handle)
        with open(document, "rb") as handle_file:
            data = handle_file.read()
            win32print.WritePrinter(handle, data)
        win32print.EndPagePrinter(handle)
        win32print.EndDocPrinter(handle)
        return PCFaxJobResult(submitted=True, queue=queue_name, detail=f"job_id={job_id} did={did or 'n/a'}")
    except Exception as exc:  # pragma: no cover - depends on OS behaviour
        return PCFaxJobResult(submitted=False, queue=queue_name, detail=f"submission failed: {exc}")
    finally:
        try:
            win32print.ClosePrinter(handle)
        except Exception:  # pragma: no cover - best effort cleanup
            pass
