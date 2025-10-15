# QAFAX Test Automation

This repository delivers the minimal viable Fax QA automation CLI described in the
engineering plan. It simulates deterministic fax negotiations, compares reference and
candidate documents line-by-line, and writes structured reports that can be shared with
operators and device vendors.

## Features

- Seeded T.30 negotiation simulator with V.34/V.17 metadata and fallback logging
- Lightweight verification pipeline with placeholder SSIM/PSNR/SKEW/LINES metrics
- JSON/CSV/HTML reports plus a plain-text run log under `artifacts/<run-id>/`
- Configurable device profiles and verification policies loaded from `config/`
- Metadata capture for DID and HP PC-Fax queues to support workflow handoffs

## Getting Started

1. Ensure Python 3.11 or newer is installed. No third-party packages are required for the
   CLI MVP.
2. Run the CLI with a reference and candidate document:

   ```bash
   python -m app.main docs/samples/control_reference.txt docs/samples/control_candidate.txt \
     --iterations 3 --seed 42 --run-id demo
   ```

   Optional flags:

   - `--profile` / `--policy` to load different configuration files
   - `--path {digital|print-scan}` to record the path chips in reports (default: `digital`)
   - `--did` to log the dialed DID
   - `--pcfax-queue` to record an HP PC-Fax queue name

3. Inspect the generated artifacts under `artifacts/<run-id>/`:

   - `summary.json` — full run metadata, per-iteration metrics, and telemetry
   - `summary.csv` — iteration summaries suitable for spreadsheets
   - `report.html` — human-friendly view with chips and negotiation logs
   - `run.log` — text log of Phase B→D events for every iteration
   - `telemetry.json` — structured telemetry emitted during execution

## Configuration

Device profiles live under `config/profiles/` and verification policies under
`config/verify_policy.*.json`. Each run records the SHA-256 hash of the loaded profile and
policy so operators can reproduce results.

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
