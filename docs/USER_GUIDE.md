# QAFAX Test Automation — User Guide

This guide explains how to prepare your workstation, run the CLI, and exercise every feature that ships with the QAFAX Test Automation MVP. Follow the sections in order the first time you use the tool, then jump to individual features as needed.

---

## 1. First-Time Setup

### 1.1 Prerequisites

| Component | Purpose | Notes |
| --- | --- | --- |
| Python 3.11+ | Required runtime | Install from python.org or Windows Store. Ensure `python` is available on `PATH`. |
| Git | Optional for updates | Lets you pull future revisions. |
| Poppler (`pdftoppm`) | Optional | Enables PDF rasterization for image metrics. On Windows install the Poppler binaries and add `bin/` to `PATH`. |
| Tesseract OCR | Optional | Required if you enable OCR gates (`--require-ocr`). Install language packs needed for your documents. |
| ZBar / `pyzbar` | Optional | Required if you enable barcode gates (`--require-barcode`). |
| PyWin32 | Optional (Windows) | Needed for silent HP PC-Fax submissions. Install with `pip install pywin32`. |
| PySerial | Optional | Required for USB modem transport support. Install with `pip install pyserial`. |
| FastAPI + Uvicorn | Optional | Required for the browser UI. Install with `pip install fastapi uvicorn python-multipart`. |
| SMB share access | Optional | Configure a network share for device scans if you plan to ingest print/scan artifacts. |
| SIP/T.38 tooling | Optional | Needed for FoIP validation and the built-in T.38 transport. Provide CLI tools such as `t38modem` and `pjsua` referenced in `config/fax/t38.sample.json`. |

> The CLI runs without optional dependencies. Missing tooling downgrades optional metrics to WARN unless explicitly required.

### 1.2 Clone and Install

```bash
cd /path/to/workspace
git clone <repository-url>
cd QAFAXTestAutomation
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements-optional.txt  # create from optional deps, or install piecemeal
```

A `requirements-optional.txt` file is not mandatory; install only the packages you need (`numpy`, `Pillow`, `pdf2image`, `opencv-python`, `scikit-image`, `pywin32`, `pytesseract`, `pyzbar`, `smbprotocol`, etc.).

### 1.3 Environment Validation

Run the built-in self-test to confirm your machine is ready:

```bash
python -m app.tools.self_test
```

Review `artifacts/self_test.json` for pass/fail results and remediation hints.

### 1.4 Configure Devices

* **HP PC-Fax Queue (Windows):**
  1. Install HP Fax drivers and open *Printing Preferences*.
  2. Disable cover pages and interactive prompts (set to “Use last settings”).
  3. Note the exact queue name (e.g., `HP LaserJet Fax`).

* **Scan-to-Folder Share:**
  1. Create a dedicated folder on a reachable SMB host.
  2. Grant the scanning device read/write access.
  3. Verify that partial uploads use temporary extensions (the ingestor ignores `.tmp`/`.partial` files by default).

* **SNMP Access:**
  1. Confirm the device exposes read-only SNMP on the expected community or v3 credentials.
  2. Collect the OIDs you want to poll (e.g., counters for jams, page counts).

* **FoIP/T.38 Tooling & Driverless Fax Transports:**
  1. Provision SIP credentials and CLI scripts capable of originating/terminating fax calls.
  2. Install command-line tools such as `t38modem` and `pjsua` for the built-in T.38 transport.
  3. Copy `config/foip.sample.json` (FoIP validation) and `config/fax/t38.sample.json` (driverless transport) to local files and update credentials, tool paths, and timeouts.
  4. For USB modem workflows, connect a Class 1/2 modem and install `pyserial`. Copy `config/fax/modem.sample.json` and set the COM port and initialization strings required by your hardware.

---

## 2. Core Workflow

### 2.1 Basic Run

```bash
python -m app.main docs/samples/control_reference.txt docs/samples/control_candidate.txt \
  --iterations 3 --seed 42 --run-id demo
```

This command:

1. Loads the default device profile (`Brother_V34_33k6_ECM256`) and policy (`verify_policy.normal`).
2. Seeds the negotiation simulator, ensuring deterministic fallbacks across iterations.
3. Runs the verification pipeline on the reference/candidate pair for each iteration.
4. Writes reports, logs, and provenance to `artifacts/demo/`.

### 2.2 Selecting Profiles and Policies

* Use `--profile Canon_V17_14k4_ECM64` to load `config/profiles/Canon_V17_14k4_ECM64.json`.
* Use `--policy verify_policy.strict` to load `config/verify_policy.strict.json` (if present).
* The SHA-256 hash of each config is stored in the artifacts for reproducibility.

### 2.3 Path & Transport Metadata

* `--path digital` (default) records that the candidate was a direct digital ingest.
* `--path print-scan` marks runs expecting physical print + scan workflows.
* `--transport sim` (default) records that only the simulator ran before verification.
* `--transport t38 --t38-config config/fax/t38.local.json` encodes the candidate into fax-ready TIFF pages and executes the driverless T.38 flow (dry-run if tooling is missing).
* `--transport modem --modem-config config/fax/modem.local.json` uses the USB modem path.
* `--location RemoteSite` can be set in `RunContext` when remote mode is added (TODO).

---

## 3. Feature Playbooks

Each subsection lists the steps to exercise the feature, expected outputs, and troubleshooting hints.

### 3.1 Verification Pipeline (Images + Text)

1. Provide a reference and candidate document (TXT, PDF, TIFF, or image formats).
2. The loader normalizes each page into grayscale arrays (using pdf2image/Pillow when available).
3. Preprocessing honors the policy: DPI normalization, deskew, and denoise when enabled.
4. Metrics computed per page include:
   * `SSIM` and `PSNR` from `skimage.metrics` (fallback placeholders if libs missing).
   * `SKEW`, `NOISE`, and `MTF` via heuristics in `app/verify/metrics/`.
   * Optional `OCR` and `BARCODE` metrics when dependencies exist or required.
5. Policy gates (hard vs warn) evaluate each metric and produce PASS/WARN/FAIL verdicts.
6. Review per-page tables in `artifacts/<run-id>/report.html`.

**Troubleshooting:** If metrics show `None`, install optional dependencies or relax policy thresholds.

### 3.2 Page Alignment & Manual Overrides

1. When candidate scans arrive out of order, the CLI computes text-based similarity and
   lightweight image heuristics to map each page back to its reference counterpart.
2. High-confidence matches automatically reorder the candidate document before metrics
   are calculated, so SSIM/LINES comparisons behave as expected.
3. If a page scores below the confidence threshold (0.6 by default) and the CLI is
   running interactively, you will be prompted to choose the correct reference index.
   Press **Enter** to accept the suggested page, or type a zero-based page number.
4. Non-interactive runs (e.g., CI pipelines) skip the prompt and record a warning in the
   artifacts; the `ALIGNMENT` metric in `report.html` captures these low-confidence cases.
   You can also set `QAFAX_DISABLE_PROMPTS=1` to force no prompts in automation.
5. Extra or missing pages are reported as warnings so you can investigate device
   settings or rescan as needed.

**Troubleshooting:** If pages are consistently misaligned, ensure the reference deck has
unique textual content per page or add control-sheet fiducials before rescanning.

### 3.3 HP PC-Fax Submission

1. Ensure Windows, PyWin32, and the HP Fax queue are configured (§1.4).
2. Run the CLI with `--pcfax-queue "HP LaserJet Fax" --did 18005551212`.
3. The CLI attempts a silent submission using `app/core/send_pcfax.py`.
4. Success/failure details appear in the console, `artifacts/<run-id>/run.log`, and JSON summaries.
5. If silent submission is unsupported, the tool records a WARN and continues.

### 3.4 SMB Ingest (Print-Scan)

1. Launch the CLI with `--path print-scan --ingest-dir \\LAB-SRV\Scans\QAFAX --ingest-pattern *.pdf`.
2. After each iteration, the ingestor polls the share until a new stable file appears.
3. Once stable size is observed across `stablePolls` (default 3), the file is hashed and copied locally.
4. Metadata is appended to `provenance.json` and the HTML report.
5. If the timeout is reached (`--ingest-timeout`), a WARN is recorded and the run continues.

### 3.5 SNMP Snapshot

1. Supply `--snmp-target 192.0.2.10 --snmp-community public --snmp-oids hrPrinterStatus,1.3.6.1.2.1.43.16.5.1.2.1.1`.
2. The CLI queries each OID and records results.
3. Values and errors are visible in `summary.json`, `run.log`, and `report.html` (SNMP section).
4. Missing SNMP libraries result in a WARN with diagnostic text.

### 3.6 FoIP / T.38 Validation

1. Prepare a FoIP config by copying `config/foip.sample.json` and editing:
   * `placeCommand` / `receiveCommand` templates.
   * Timeout values and output directories.
2. Invoke the CLI with `--foip-config config/foip.local.json`.
3. The validator executes the configured commands before the run starts, hashing produced artifacts.
4. Results appear in logs, JSON, HTML, and provenance files.
5. Failures (non-zero exit codes, missing files) are captured in the error list.

### 3.7 Driverless Fax Transport (T.38 / USB Modem)

1. Choose the transport path using `--transport t38` or `--transport modem`.
2. Provide the corresponding configuration file with `--t38-config` or `--modem-config`.
3. The CLI converts the candidate document into fax TIFF pages (requires Pillow/pdf2image).
4. For T.38, the tool checks for the presence of `t38modem`/`pjsua` and records a dry-run timeline if unavailable. When present, the simulated command line is logged for auditing.
5. For USB modems, the tool checks for `pyserial` and logs AT command sequences and configuration details.
6. Transport artifacts (`transport_timeline.csv`, manifest/log files) and status chips appear in `report.html`, the JSON summary, and the browser UI.

**Troubleshooting:** Missing dependencies fall back to dry-run mode with WARN telemetry. Ensure TIFF pages exist in `artifacts/<run-id>/transport/pages/` if encoding succeeds.

### 3.8 Deterministic Simulation & Iterations

1. Use `--iterations N --seed S` to replay negotiation sequences predictably.
2. Simulation logs include Phase B–D events, fallback steps, and bitrates per iteration.
3. View the negotiation timeline in the HTML report and `run.log`.

### 3.9 Reporting Artifacts

After each run, inspect the following files under `artifacts/<run-id>/`:

| File | Purpose |
| --- | --- |
| `summary.json` | Full run metadata, per-iteration metrics, telemetry, SNMP, FoIP, ingest manifests. |
| `summary.csv` | Spreadsheet-friendly iteration summaries. |
| `report.html` | Browser-ready view with chips, per-page tables, SNMP/FoIP sections, and negotiation logs. |
| `run.log` | Plain-text log of events and connector output. |
| `provenance.json` | Hashes, sizes, and provenance entries for reference/candidate/ingested files plus transport metadata. |
| `telemetry.json` | Structured telemetry events emitted during execution. |
| `transport_timeline.csv` | Negotiation timeline from the built-in T.38 or modem transport (if executed). |

### 3.10 Report Consumption

1. Open `artifacts/<run-id>/report.html` in any modern browser.
2. Chips summarize Brand, Standard, Speed, ECM, Path, Location, Queue, and DID.
3. SNMP and FoIP sections render above the per-iteration tables when data is present.
4. Share the HTML file along with accompanying artifacts for remote reviews.

### 3.11 Self-Test Utility

1. Run `python -m app.tools.self_test` whenever dependencies change.
2. The tool enumerates optional checks (Poppler, Tesseract, SMB reachability, printers, T.38 tooling, pyserial).
3. Review suggested fixes in the generated JSON file.

### 3.12 Desktop GUI Workflow

1. Install `PySide6` inside the project environment (`pip install PySide6`).
2. Launch the desktop application with `python -m app.ui`.
3. Use the file pickers to select the reference and candidate documents, then adjust
   iterations, profiles, policies, transport options, HP PC-Fax queues, ingest folders,
   SNMP targets, and FoIP validation as needed.
4. Click **Run QA** to execute the pipeline in the background. Progress messages appear
   in the log panel and the **Open artifacts folder** button opens the results directory
   once complete.
5. All artifacts are written under `artifacts/<run-id>/`, matching the CLI output.

### 3.13 Windows Executable Workflow

1. Install PyInstaller (`pip install pyinstaller`) and the optional runtime libraries you
   plan to ship (for example `pip install PySide6 Pillow numpy pdf2image pytesseract
   pyzbar pyserial smbprotocol pywin32`).
2. Run `powershell -ExecutionPolicy Bypass -File scripts/build_windows_exe.ps1` from a
   Developer PowerShell prompt.
3. After the build finishes, navigate to `dist/QAFAXDesktop/` and launch
   `QAFAXDesktop.exe`. The packaged application embeds the GUI, configuration files, and
   any installed optional dependencies so QA operators can run it without extra
   downloads.

---

## 4. Maintenance

* **Updating configs:** Edit files under `config/` and commit hashes are recorded automatically.
* **Adding profiles:** Place JSON files under `config/profiles/` and reference via `--profile`.
* **Extending policies:** Clone `config/verify_policy.normal.json`, adjust thresholds, and load with `--policy`.
* **Cleaning artifacts:** Delete old run directories from `artifacts/` after retention requirements are met.

---

## 5. Support Checklist

Before sharing a run externally, ensure:

- [ ] `summary.json`, `summary.csv`, `report.html`, and `provenance.json` are present.
- [ ] Optional metrics are populated or justified (self-test results attached if missing).
- [ ] SNMP snapshots and FoIP outputs are included when enabled.
- [ ] Run log shows expected profile, policy, and fallback behavior.
- [ ] Seed and profile/policy hashes are recorded for reproducibility.

For additional architectural details, reference `docs/ENGINEERING_PLAN.md`.
