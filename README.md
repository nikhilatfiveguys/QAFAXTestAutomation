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
  optional SNMP snapshots, and FoIP/T.38 validation attempts
- Optional self-test tool that checks for optional dependencies and environment readiness

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
   - `--did` to log the dialed DID
   - `--pcfax-queue` to attempt an HP PC-Fax submission (Windows + PyWin32 required)
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
   - `provenance.json` — hashes, sizes, and ingest provenance for reproducibility
   - `telemetry.json` — structured telemetry emitted during execution

## Web Interface

The entire workflow is also available through a browser-based UI powered by FastAPI.

1. Install the optional dependencies:

   ```bash
   pip install fastapi uvicorn python-multipart
   ```

2. Launch the server:

   ```bash
   python -m app.web  # listens on http://127.0.0.1:8000
   ```

3. Open `http://127.0.0.1:8000` in a browser, upload reference and candidate
   documents, adjust options (iterations, profile, HP PC-Fax queue, SMB ingest,
   SNMP, FoIP), and start the run. The UI renders the per-iteration metrics and
   provides direct download links to the HTML/CSV/JSON/log artifacts, FoIP
   outputs, and telemetry.

The web form simply orchestrates the same execution pipeline used by the CLI, so
every feature—including SNMP snapshots, FoIP validation, HP PC-Fax submissions,
and ingest polling—can be initiated from the browser.

## Configuration

Device profiles live under `config/profiles/`, verification policies under
`config/verify_policy.*.json`, and FoIP samples in `config/foip.sample.json`. Each run
records the SHA-256 hash of the loaded profile and policy so operators can reproduce
results. Policies now include preprocessing preferences and optional metric gates that can
be tightened per site.

## Self-Test

Validate optional tooling and environment prerequisites with:

```bash
python -m app.tools.self_test
```

The tool writes `artifacts/self_test.json` with pass/fail results.

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
