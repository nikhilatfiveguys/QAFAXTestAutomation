# QAFAX Test Automation

This repository delivers the minimal viable Fax QA automation CLI described in the
engineering plan. It now includes image-ready verification scaffolding, HP PC-Fax queue
submission hooks, ingest polling for print-scan workflows, and reproducible reporting
artifacts suitable for QA review packages.

## Features

- Seeded T.30 negotiation simulator with V.34/V.17 metadata and fallback logging
- Verification pipeline that loads text or images, applies optional preprocessing, and
  reports SSIM/PSNR/SKEW/NOISE/MTF/OCR/BARCODE/LINES metrics with policy-driven verdicts
- Content-aware page alignment that automatically reorders scans and offers a manual
  override prompt when confidence is low
- JSON/CSV/HTML reports, a plain-text run log, telemetry export, and a provenance manifest
  under `artifacts/<run-id>/`
- Configurable device profiles and verification policies loaded from `config/`
- Metadata capture for DID, HP PC-Fax queue submissions, ingest directory monitoring,
  optional SNMP snapshots, FoIP/T.38 validation attempts, and built-in T.38/USB modem
  transport timelines
- Optional self-test tool that checks for optional dependencies and environment readiness
- Optional PySide6 desktop UI for running the entire workflow without a browser

## First-Time Setup (Summary)

For the full walkthrough, see the [User Guide](docs/USER_GUIDE.md). The condensed steps
below help you run the CLI quickly:

1. Install Python 3.11 or newer and clone this repository. Optional dependencies (NumPy,
   Pillow, pdf2image, OpenCV, scikit-image, PyWin32, pytesseract, pyzbar) unlock additional
   metrics and connectors but are not required for basic runs.
2. Create a virtual environment and install whichever optional packages you need:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install --upgrade pip
   pip install numpy Pillow pdf2image opencv-python scikit-image pywin32 pytesseract pyzbar
   ```

3. Validate your environment with the self-test utility:

   ```bash
   python -m app.tools.self_test
   ```

4. Run the CLI with a reference and candidate document:

   ```bash
   python -m app.main docs/samples/control_reference.txt docs/samples/control_candidate.txt \
     --iterations 3 --seed 42 --run-id demo
   ```

   Optional flags:

   - `--profile` / `--policy` to load different configuration files
   - `--path {digital|print-scan}` to record the path chips in reports (default: `digital`)
   - `--transport {sim|t38|modem}` to run the built-in transport encoder + timeline capture
   - `--did` to log the dialed DID
   - `--pcfax-queue` to attempt an HP PC-Fax submission (Windows + PyWin32 required)
   - `--t38-config` / `--modem-config` to point at driverless fax configuration JSON files
   - `--ingest-dir` / `--ingest-pattern` / `--ingest-timeout` / `--ingest-interval` to poll a
     scan folder for new artifacts after each run
   - `--snmp-target` / `--snmp-community` / `--snmp-oids` to collect printer counters via SNMP
   - `--foip-config` to execute a FoIP/T.38 validation workflow defined by a JSON config
   - `--require-ocr` and `--require-barcode` to promote optional metrics to hard gates

5. Inspect the generated artifacts under `artifacts/<run-id>/`:

   - `summary.json` — full run metadata, per-iteration metrics, optional ingest manifest,
     SNMP snapshots, FoIP results, and telemetry
   - `summary.csv` — iteration summaries suitable for spreadsheets
   - `report.html` — human-friendly view with chips and negotiation logs
   - `run.log` — text log of Phase B→D events for every iteration
   - `transport_timeline.csv` — optional timeline of built-in T.38/modem transport events
   - `provenance.json` — hashes, sizes, and ingest provenance for reproducibility
   - `telemetry.json` — structured telemetry emitted during execution

## Desktop GUI

Operators who prefer a Windows desktop experience can install `PySide6` when running
from source or use the packaged executable described below. To run the GUI directly
from Python:

```bash
pip install PySide6
python -m app.ui  # opens the QAFAX Desktop window
```

The desktop UI exposes the same options as the CLI: choose reference/candidate
documents, pick profiles and policies, configure transport (simulation, built-in
T.38, USB modem), toggle HP PC-Fax submission, ingest polling, SNMP snapshots,
and FoIP validation. Execution happens in a background thread so progress logs and
artifacts appear in the window without blocking the interface.

## Download Prebuilt Windows Executable

Every push to the `main` branch and any published GitHub release triggers the
**Build QAFAX Desktop Executable** workflow. The automation installs the
optional feature libraries, runs the unit test suite, builds the packaged GUI
via `pyinstaller`, and publishes a `QAFAXDesktop.zip` artifact. You can obtain
the self-contained executable in two ways:

1. Navigate to **Actions → Build QAFAX Desktop Executable → latest successful
   run** and download the `QAFAXDesktop.zip` artifact. The archive contains the
   bundled `QAFAXDesktop.exe`, configuration files, and documentation.
2. When tagging a release, the workflow automatically uploads the same archive
   to the release assets so operators can fetch it directly from the release
   page.

The packaged build embeds PySide6, optional verification dependencies, and the
`config/` + `docs/` trees, so Windows users can launch the desktop app without
installing Python or extra wheels.

## Windows Executable Build

To distribute the desktop UI without requiring Python or manual dependency installs,
bundle it into a standalone `.exe` using PyInstaller. Build the executable from a
Windows environment where the optional feature libraries are installed (for example
`pip install PySide6 Pillow numpy pdf2image pytesseract pyzbar pyserial smbprotocol pywin32`).

```powershell
pip install pyinstaller
powershell -ExecutionPolicy Bypass -File scripts/build_windows_exe.ps1
```

The PowerShell helper invokes `PyInstaller` with `scripts/qafax_desktop.spec`, which
automatically collects the optional packages when present and embeds `config/` and
`docs/` so `dist/QAFAXDesktop/QAFAXDesktop.exe` runs on clean operator workstations
without additional downloads. Sign the resulting binary according to your deployment
policies before distribution.

## Configuration

Device profiles live under `config/profiles/`, verification policies under
`config/verify_policy.*.json`, FoIP samples in `config/foip.sample.json`, and
driverless fax transport templates in `config/fax/`. Each run records the
SHA-256 hash of the loaded profile and policy so operators can reproduce
results. Policies now include preprocessing preferences and optional metric
gates that can be tightened per site.

## Self-Test

Validate optional tooling and environment prerequisites with:

```bash
python -m app.tools.self_test
```

The tool writes `artifacts/self_test.json` with pass/fail results, including
checks for optional Python packages, HP PC-Fax queues, and FoIP/transport tools
(`t38modem`, `pjsua`).

## Testing

Basic unit tests cover configuration loading, simulation determinism, and report writers.
Run them with:

```bash
python -m unittest
```

## Roadmap

The CLI codebase is structured to grow into the full desktop application described in
`docs/ENGINEERING_PLAN.md`. Stub packages (e.g., connectors, privacy, remote) remain in the
repository for future expansion.
