# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification for the single-file QAFAX desktop executable.

This spec dynamically bundles optional dependencies (PySide6, Pillow, numpy,
pdf2image, pytesseract, pyzbar, pyserial, smbprotocol, and PyWin32 modules)
whenever they are available in the build environment so that the resulting
`QAFAXDesktop.exe` ships with the full feature set without requiring manual
installs on operator workstations. The build emits a *single* executable so
operators can download a lone ``.exe`` from GitHub without having to extract an
archive first.
"""

import importlib.util
from pathlib import Path
from typing import List, Sequence, Tuple

from PyInstaller.utils.hooks import collect_all, logger as hook_logger


project_root = Path(__file__).resolve().parent.parent


def _collect_optional_package(name: str) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]], List[str]]:
    """Return datas/binaries/hiddenimports for an optional package if installed."""

    if importlib.util.find_spec(name) is None:
        return [], [], []
    try:
        data, binaries, hidden = collect_all(name)
    except Exception as exc:  # pragma: no cover - defensive for missing hooks
        hook_logger.warning("Skipping optional package %s: %s", name, exc)
        return [], [], []
    return list(data), list(binaries), list(hidden)


def _collect_directory(source: Path, target_prefix: str) -> List[Tuple[str, str]]:
    """Collect every file under *source* so PyInstaller copies it into the bundle."""

    if not source.exists():
        return []
    entries: List[Tuple[str, str]] = []
    for path in source.rglob("*"):
        if path.is_file():
            relative = path.relative_to(source)
            destination = Path(target_prefix) / relative
            entries.append((str(path), str(destination)))
    return entries


datas: List[Tuple[str, str]] = []
binaries: List[Tuple[str, str]] = []
hiddenimports: List[str] = []


OPTIONAL_PACKAGES: Sequence[str] = (
    "PySide6",
    "numpy",
    "PIL",
    "pdf2image",
    "pytesseract",
    "pyzbar",
    "serial",
    "smbprotocol",
)

for package in OPTIONAL_PACKAGES:
    pkg_datas, pkg_binaries, pkg_hidden = _collect_optional_package(package)
    datas.extend(pkg_datas)
    binaries.extend(pkg_binaries)
    hiddenimports.extend(pkg_hidden)


OPTIONAL_MODULES: Sequence[str] = (
    "win32print",
    "win32timezone",
)

for module in OPTIONAL_MODULES:
    if importlib.util.find_spec(module) is not None:
        hiddenimports.append(module)


datas.extend(_collect_directory(project_root / "config", "config"))
datas.extend(_collect_directory(project_root / "docs", "docs"))


block_cipher = None


a = Analysis(
    [str(project_root / "app" / "ui" / "__main__.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)


pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)


exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="QAFAXDesktop",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

