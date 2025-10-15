"""Document loading helpers for verification workflows."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
import hashlib

try:  # Optional dependencies used when available.
    from pdf2image import convert_from_path  # type: ignore
except Exception:  # pragma: no cover - pdf2image is optional in tests.
    convert_from_path = None  # type: ignore

try:
    from PIL import Image  # type: ignore
except Exception:  # pragma: no cover - Pillow is optional in tests.
    Image = None  # type: ignore

try:
    import numpy as _np  # type: ignore
except Exception:  # pragma: no cover - NumPy is optional in tests.
    _np = None  # type: ignore


ArrayLike = "_np.ndarray"  # Forward reference for type checkers.


@dataclass
class DocumentPage:
    """Represents a single logical page that may contain pixels and text."""

    index: int
    text_lines: List[str]
    image: Optional[ArrayLike]
    dpi: Optional[int]
    warnings: List[str] = field(default_factory=list)


@dataclass
class DocumentData:
    """Loaded document containing one or more logical pages."""

    path: Path
    content: bytes
    sha256: str
    pages: List[DocumentPage]
    warnings: List[str] = field(default_factory=list)

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def lines(self) -> List[str]:
        all_lines: List[str] = []
        for page in self.pages:
            all_lines.extend(page.text_lines)
        return all_lines

    @property
    def size(self) -> int:
        return len(self.content)


def load_document(path: Path) -> DocumentData:
    """Load a document from disk and decode pixels when tooling is available."""

    content = path.read_bytes()
    sha256 = hashlib.sha256(content).hexdigest()
    suffix = path.suffix.lower()
    warnings: List[str] = []

    if suffix in {".txt", ".log", ".csv", ".json"}:
        text_lines = _decode_lines(content)
        pages = [DocumentPage(index=0, text_lines=text_lines, image=None, dpi=None)]
        return DocumentData(path=path, content=content, sha256=sha256, pages=pages)

    if suffix in {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"} and Image is not None:
        image_page = _load_image_page(path, warnings)
        return DocumentData(path=path, content=content, sha256=sha256, pages=[image_page], warnings=warnings)

    if suffix == ".pdf" and convert_from_path is not None:
        pages = _load_pdf_pages(path, warnings)
        return DocumentData(path=path, content=content, sha256=sha256, pages=pages, warnings=warnings)

    warnings.append("Binary loader unavailable; falling back to text decode.")
    text_lines = _decode_lines(content)
    pages = [DocumentPage(index=0, text_lines=text_lines, image=None, dpi=None, warnings=["text-fallback"])]
    return DocumentData(path=path, content=content, sha256=sha256, pages=pages, warnings=warnings)


def _decode_lines(content: bytes) -> List[str]:
    text = content.decode("utf-8", errors="replace")
    return text.splitlines()


def _load_image_page(path: Path, warnings: List[str]) -> DocumentPage:
    assert Image is not None
    index = 0
    with Image.open(path) as handle:  # type: ignore[call-arg]
        dpi = None
        if isinstance(handle.info.get("dpi"), tuple):
            dpi_tuple = handle.info["dpi"]
            if len(dpi_tuple) >= 1 and isinstance(dpi_tuple[0], (int, float)):
                dpi = int(round(dpi_tuple[0]))
        gray = handle.convert("L")
        image_array = _to_numpy(gray)
        text_lines: List[str] = []
    return DocumentPage(index=index, text_lines=text_lines, image=image_array, dpi=dpi)


def _load_pdf_pages(path: Path, warnings: List[str]) -> List[DocumentPage]:
    assert convert_from_path is not None
    pil_pages = convert_from_path(str(path), dpi=300)  # type: ignore[arg-type]
    pages: List[DocumentPage] = []
    for index, page in enumerate(pil_pages):
        dpi = getattr(page, "info", {}).get("dpi")
        page_dpi: Optional[int] = None
        if isinstance(dpi, tuple) and dpi:
            page_dpi = int(round(dpi[0]))
        image_array = _to_numpy(page.convert("L"))
        pages.append(DocumentPage(index=index, text_lines=[], image=image_array, dpi=page_dpi))
    if not pages:
        warnings.append("PDF loader returned no pages.")
    return pages


def _to_numpy(image: "Image.Image") -> Optional[ArrayLike]:  # type: ignore[name-defined]
    if _np is None:
        return None
    try:
        return _np.asarray(image, dtype=_np.uint8)
    except Exception:  # pragma: no cover - rare Pillow/numpy interop issues.
        return None
