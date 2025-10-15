"""Entry point for launching the QAFAX desktop UI."""
from __future__ import annotations

from .gui import launch


def main() -> None:
    """Launch the PySide6 desktop UI."""

    launch()


if __name__ == "__main__":  # pragma: no cover
    main()
