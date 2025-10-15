"""Entry point to launch the FastAPI web UI with uvicorn."""
from __future__ import annotations


def main() -> None:  # pragma: no cover - thin wrapper around uvicorn
    from . import create_app

    try:
        app = create_app()
    except RuntimeError as exc:
        raise SystemExit(str(exc))

    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise SystemExit("uvicorn is required to launch the web interface.") from exc

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":  # pragma: no cover
    main()
