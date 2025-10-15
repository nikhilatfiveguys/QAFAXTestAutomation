"""Utilities for converting documents into fax-friendly TIFF pages."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence
import logging

try:  # pragma: no cover - optional dependency detection
    from PIL import Image, ImageOps
except ImportError:  # pragma: no cover - fallback is handled at runtime
    Image = None  # type: ignore[assignment]
    ImageOps = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

FAX_FINE_X_DPI = 204
FAX_FINE_Y_DPI = 196
SUPPORTED_EXTENSIONS = {".pdf", ".tif", ".tiff", ".png", ".jpg", ".jpeg", ".bmp"}


@dataclass
class FaxPage:
    """Metadata describing an encoded fax page."""

    source_index: int
    tiff_path: Path
    width: int
    height: int
    x_dpi: int
    y_dpi: int
    compression: str


class FaxEncodingError(RuntimeError):
    """Raised when a document cannot be converted into fax pages."""


def encode_to_fax_tiff(
    source: Path,
    output_dir: Path,
    *,
    compression: str = "group4",
    target_dpi: tuple[int, int] = (FAX_FINE_X_DPI, FAX_FINE_Y_DPI),
) -> List[FaxPage]:
    """Convert the provided document into fax TIFF pages.

    Parameters
    ----------
    source:
        Document path to convert.
    output_dir:
        Directory where generated TIFF files should be written.
    compression:
        TIFF compression mode. "group4" (MMR) is recommended.
    target_dpi:
        Desired X/Y DPI tuple for generated pages.
    """

    if Image is None:  # pragma: no cover - executed when Pillow missing
        raise FaxEncodingError(
            "Pillow is required to encode documents to fax TIFF. Install pillow to proceed."
        )

    if source.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise FaxEncodingError(f"Unsupported document type: {source.suffix}")

    output_dir.mkdir(parents=True, exist_ok=True)

    frames = list(_load_frames(source))
    if not frames:
        raise FaxEncodingError("No frames decoded from source document")

    encoded_pages: List[FaxPage] = []
    for index, frame in enumerate(frames):
        image = frame.convert("L")
        image = ImageOps.autocontrast(image)
        image = _normalize_resolution(image, target_dpi)
        bw = image.point(lambda value: 0 if value < 128 else 255, mode="1")
        tiff_path = output_dir / f"page_{index + 1:03d}.tiff"
        bw.save(tiff_path, format="TIFF", compression=compression, dpi=target_dpi)
        encoded_pages.append(
            FaxPage(
                source_index=index,
                tiff_path=tiff_path,
                width=bw.width,
                height=bw.height,
                x_dpi=target_dpi[0],
                y_dpi=target_dpi[1],
                compression=compression,
            )
        )
        logger.debug("Encoded fax page %s to %s", index, tiff_path)
    return encoded_pages


def _load_frames(source: Path) -> Iterable["Image.Image"]:
    suffix = source.suffix.lower()
    if suffix == ".pdf":
        yield from _load_pdf_frames(source)
    else:
        yield from _load_image_frames(source)


def _load_pdf_frames(source: Path) -> Iterable["Image.Image"]:
    try:
        from pdf2image import convert_from_path  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise FaxEncodingError("pdf2image is required to convert PDF documents") from exc

    for page in convert_from_path(str(source), dpi=FAX_FINE_Y_DPI):
        yield page


def _load_image_frames(source: Path) -> Iterable["Image.Image"]:
    assert Image is not None
    image = Image.open(source)
    index = 0
    while True:
        try:
            image.seek(index)
        except EOFError:
            break
        yield image.copy()
        index += 1


def _normalize_resolution(image: "Image.Image", target_dpi: Sequence[int]) -> "Image.Image":
    info = image.info or {}
    current_dpi = info.get("dpi")
    if not current_dpi:
        return image
    x_dpi, y_dpi = current_dpi
    if int(x_dpi) == target_dpi[0] and int(y_dpi) == target_dpi[1]:
        return image
    scale_x = target_dpi[0] / x_dpi
    scale_y = target_dpi[1] / y_dpi
    new_width = max(1, int(image.width * scale_x))
    new_height = max(1, int(image.height * scale_y))
    return image.resize((new_width, new_height))
