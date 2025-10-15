"""Environment self-test covering optional dependencies and resources."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List
import json
import os
import platform


OPTIONAL_MODULES = [
    "numpy",
    "PIL.Image",
    "pdf2image",
    "skimage.metrics",
    "pytesseract",
    "pyzbar",
]


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


def run_self_test(ingest_dir: str | None = None, pcfax_queue: str | None = None) -> Dict[str, object]:
    results: List[CheckResult] = []
    for module_name in OPTIONAL_MODULES:
        results.append(_check_import(module_name))
    if ingest_dir:
        results.append(_check_ingest_directory(Path(ingest_dir)))
    if pcfax_queue:
        results.append(_check_printer_queue(pcfax_queue))
    payload = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "checks": [result.__dict__ for result in results],
    }
    return payload


def _check_import(module: str) -> CheckResult:
    try:
        __import__(module)
        return CheckResult(name=f"import:{module}", passed=True, detail="available")
    except Exception as exc:  # pragma: no cover - depends on host packages
        return CheckResult(name=f"import:{module}", passed=False, detail=str(exc))


def _check_ingest_directory(path: Path) -> CheckResult:
    if path.exists() and path.is_dir():
        return CheckResult(name=f"ingest:{path}", passed=True, detail="reachable")
    return CheckResult(name=f"ingest:{path}", passed=False, detail="directory not found")


def _check_printer_queue(queue_name: str) -> CheckResult:
    if os.name != "nt":
        return CheckResult(name=f"pcfax:{queue_name}", passed=False, detail="Windows-only feature")
    try:
        import win32print  # type: ignore

        printers = [info[2] for info in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL)]
        if queue_name in printers:
            return CheckResult(name=f"pcfax:{queue_name}", passed=True, detail="queue available")
        return CheckResult(name=f"pcfax:{queue_name}", passed=False, detail="queue not found")
    except Exception as exc:  # pragma: no cover - depends on host packages
        return CheckResult(name=f"pcfax:{queue_name}", passed=False, detail=str(exc))


def main() -> None:
    payload = run_self_test()
    output_dir = Path("artifacts")
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "self_test.json"
    path.write_text(json.dumps(payload, indent=2))
    print(f"Self-test results written to {path}")


if __name__ == "__main__":
    main()
