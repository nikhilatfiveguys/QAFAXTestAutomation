# Fax QA Automation — End-to-End Engineering Plan

**Owner:** <you>  
**Version Roadmap:** v0.1 (MVP) → v0.2 (Remote) → v0.3 (Sweep/Analytics)

**Recommended Stack:** Python 3.11, PySide6/Qt, OpenCV, scikit-image, Pillow, pdf2image (Poppler), pyzbar, pytesseract (optional), Jinja2, FastAPI (Agent)  
**Target Platforms:** macOS 13+, Windows 10+ (Linux optional)  
**Transport Paths:** Simulator (default) with optional T.38 FoIP validation

---

## 1. Purpose & Goals

* Provide QA operators with tooling to simulate fax send-side flows, execute iterative test runs, ingest rescans or digital captures, and verify output quality.
* Support cross-brand V.34 (up to 33.6 kbps) and V.17 (up to 14.4 kbps) via configurable profiles that capture ECM behavior, timers, and fallback quirks.
* Enable remote execution through a secure Remote Agent with mTLS, RBAC, and audit logging.
* Deliver robustness features: seeded determinism, crash-safe resume, anti-brittle metrics policy, environment self-tests, and smooth UI complete with sea-wave animations.

## 2. Scope Overview

**Included (MVP):**
- Local and device library ingestion, simulation of upload plus keypad/start, iteration control.
- Verification pipeline (SSIM/PSNR/OCR/skew/noise/MTF/barcode) with HTML/CSV/JSON reports and reproducibility packs.
- Digital re-upload to devices, V.34/V.17 profiles with ECM 64/256, speed fallback logging.
- Animations, environment self-test, and privacy controls.

**Remote (v0.2):** Remote site management, on-site Agent, mTLS, resumable jobs.

**Analytics (v0.3):** Auto-sweep grid, baselines, trend analytics.

**Out of Scope:** Physical paper handling and vendor-proprietary administrative interfaces beyond documented endpoints.

## 3. UX Highlights

1. **Splash:** Sea-wave animation (QtLottie) with preloading.
2. **Library:** Unified view of local folders and device sources (SMB/FTP/API/Email) with thumbnails and metadata.
3. **Test Builder:** Document selection, DID input, iteration count, brand profile (V.34/V.17, ECM, speed cap), run target (Local/Remote Site).
4. **Run Console:** Progress ring, T.30 timeline logs, metadata chips (Brand • Standard • Speed • ECM • Path • Local/Remote).
5. **Results & Compare:** Drag-and-drop rescan/import, side-by-side viewer with diff overlay, verdict badges and override flow requiring comments.
6. **Reports:** Export to HTML/CSV/JSON plus Repro Pack bundling artifacts, logs, configs, hashes.
7. **Self-Test Wizard:** Environment checks with remediation guidance.

## 4. Architecture & Modules

```
/app
  /ui                      # PySide6 views, animations, compare viewer
  /core
    iteration_controller.py
    fax_simulation.py      # T.30 model, V.34/V.17, ECM, fallback, seeded RNG
    fax_transport.py       # transport: "sim" | "t38"
    worker_pool.py         # process pool for verification, crash-safe
    config_service.py
    telemetry.py
  /verify
    pipeline.py            # orchestrates preprocess->metrics->policy
    preprocess.py
    align.py               # content-hash pairing with manual override hooks
    metrics/
      ssim_psnr.py ocr.py skew.py noise.py mtf_proxy.py barcode_qr.py
    policy.py              # hard vs warn gates, overrides supported
  /connectors
    base.py smb.py ftp.py device_http.py imap.py twain_wia_ica.py
    pcfax.py ipp.py snmp.py
  /remote
    client.py              # mTLS RPC with resumable transfer
    agent/
      main.py adapters/ security.py audit.py
  /reports
    reporter.py templates/
  /privacy
    redaction.py           # ROI blur/hash-only storage
/config
  verify_policy.*.json     # Strict/Normal/Lenient
  profiles/                # brand/standard JSON files
  foip.json                # SIP/T.38 config (optional)
/tests /docs /scripts
```

## 5. Device Profiles

Representative schema:

```json
{
  "name": "Brother_V34_33k6_ECM256",
  "standard": "V34",
  "paperSize": "Letter",
  "dpi": 200,
  "maxBitrateBps": 33600,
  "minBitrateBps": 2400,
  "bitrateStepsBps": [33600,31200,28800,26400,24000,21600,19200,16800,14400,12000,9600,7200,4800,2400],
  "ecm": {"enabled": true, "blockBytes": 256, "maxRetries": 3, "timeoutMs": 2500},
  "v34": {"longTraining": false, "tcfDurationMs": 1500, "asymmetricAllowed": true},
  "v17": null,
  "t30TimersMs": {"T1": 35000, "T2": 6000, "T3": 10000},
  "phaseBNoiseChance": 0.02,
  "fallbackPolicy": "graceful",
  "brandQuirks": {"nsfVendorBytes": "62-52-4F", "retryPageWhenCFRLate": true, "preferECMOn": true},
  "transport": "sim"
}
```

Ship profiles for major brands across V.34 and V.17 variants with ECM block sizes of 64 and 256 bytes.

## 6. Simulation & Transport

* Implement full T.30 phase modeling including DIS/DCS exchange, V.8/V.21 handshakes, TCF/CFR, ECM block handling, and Phase D completions.
* Seeded RNG for determinism; log `rngSeed`, `profileHash`, and `policyHash` per run.
* Support fallback based on TCF margin, stepping down through configured bitrate ladders.
* Optional T.38 FoIP validation path for parity checks; annotate reports with `transport=t38`.
* Provide detailed negotiation CSV logs capturing phase events, fallbacks, and retransmissions.

## 7. Ingestion & Device Connectivity

* **Digital re-upload:** PC-Fax, IPP/LPR/RAW 9100, device mailbox uploads.
* **Pull scans:** SMB/FTP/Web/Email mailboxes; TWAIN/WIA/ICA capture.
* **Print-then-rescan:** Triggered via stored jobs when supported.
* Handle partial files via stable-size polling, ignore temporary extensions, compute SHA-256 after transfer.
* Record provenance metadata `{source, deviceId, siteId, jobId, sha256, timestamp}` for each asset.

## 8. Verification Pipeline

* Preprocess with grayscale conversion, DPI normalization, deskew, and denoise per configuration.
* Metrics: SSIM/PSNR, OCR accuracy (optional), skew angle, noise index, MTF50, barcode/QR detection across rotations/scales.
* Policy engine separates hard failures from warnings and supports operator overrides with required comments.
* Store raw and preprocessed images in Repro Pack subject to privacy settings.
* Alignment via content-hash pairing with manual re-pair UI for mismatched pages.

## 9. Remote Execution & Security

* **Direct mode:** Operates over VPN/zero-trust networks with exposed device services.
* **Agent mode:** FastAPI-based on-site agent offering mTLS, RBAC (Operator/Lead/Admin roles), audit logging, and resumable, chunked transfers.
* Implement certificate pinning, firewall allowlists, OS keychain secret storage, TLS1.2+, and reconnection resilience with buffered artifacts.
* UI highlights site and transport path, warning users when digital ingestion is attempted for print-quality templates.

## 10. Reporting & Repro Packs

* HTML reports featuring page tiles, diff overlays, verdict badges, negotiation timelines, and metadata chips.
* CSV/JSON exports with per-page metrics, device metadata, and configuration hashes.
* Repro Packs bundle logs, inputs/outputs (respecting privacy), and checksums for reproducibility.
* Capture operator notes and override rationale with timestamps and user identity.

## 11. Privacy, Retention, Compliance

* Redaction mode for ROI blurring before disk write and optional hash-only storage.
* Default retention policy purges raw images after 30 days while retaining metrics and hashes.
* Configurable privacy settings stored in JSON.

## 12. Animations & Smoothness

* Sea-wave splash screen with minimum display time.
* Skeleton loaders for large libraries and wave micro-loaders for verification/remote streaming states.
* Progress animations with easing and subtle completion effects.

## 13. Performance & Stability

* Lazy thumbnail generation capped at preview DPI ~110 and virtualized lists for large libraries.
* Verification executed in a process pool with per-iteration checkpoints for crash-safe resume.
* PDF ingestion via streaming conversion with cancellation support.

## 14. Packaging & Release

* macOS: PyInstaller-built `.app`, codesigned (hardened runtime) and notarized via `notarytool`; include first-run permission helper.
* Windows: Signed MSIX (preferred) or installer executable; document Defender exceptions if necessary.
* Ship docs (`README.md`, `ARCHITECTURE.md`, `QA_GUIDE.md`, `CONTROL_SHEET.pdf`, `CHANGELOG.md`, Self-Test Guide) and publish checksums.

## 15. Test Matrix

* Documents: control sheet (text/slanted edge/QR), dense text, halftone, barcode form.
* Standards & Speeds: V.34 (33.6→14.4) and V.17 (14.4→7.2).
* ECM: on (64), on (256), off.
* Brands: Brother, Canon, Ricoh, HP, Konica.
* Line profiles: clean, noise 0.02/0.05, late CFR quirk.
* Transport: simulator vs T.38 parity runs.

**Fix validation:**
- SMB partial files respected, hash logged.
- Crash-safe resume validated by mid-iteration kill/relaunch.
- OCR optional mode produces WARN when Tesseract unavailable if `ocr.required=false`.
- Strict vs Normal thresholds yield expected outcome differences.
- Seeded determinism reproduces timelines with identical seeds.
- Agent reconnection buffers artifacts and resumes job after network flap.

## 16. Acceptance Criteria

**v0.1 (MVP):** Library, simulation, iteration control, verification with overrides, report generation, profile coverage, self-test wizard, privacy features, UI responsiveness.

**v0.2 (Remote):** Remote site/agent with mTLS, RBAC, audit logging, remote ingestion, resumable jobs, reconnection handling.

**v0.3 (Analytics):** Auto-sweep, baselines, drift tracking, trend visualization, packaging/signing readiness.

## 17. Roadmap (7 Weeks)

1. **Week 1:** Repository scaffold, splash screen, library indexing, self-test wizard.
2. **Week 2:** Profile loader, fax simulation core, seeded RNG, negotiation logs.
3. **Week 3:** Verification core with SSIM/PSNR/skew/noise, policy enforcement, HTML/CSV reporting.
4. **Week 4:** OCR, MTF, barcode metrics, alignment tools, compare viewer, Repro Pack, privacy controls.
5. **Week 5:** Device connectors, crash-safe resume, process pool stabilization.
6. **Week 6:** Remote agent, security hardening, resumable transfers, direct mode polish.
7. **Week 7:** Analytics features, packaging/signing tasks.

## 18. Sample Interfaces

```python
result = VerificationPipeline("config/verify_policy.normal.json").verify_pair(
    ref_doc=source_doc,
    out_doc=rescanned_file,
    device_meta={
        "standard": "V34",
        "bitrate": 31200,
        "ecm": {"enabled": True, "blockBytes": 256},
        "retransmits": 0
    }
)
ReportBuilder().write_all(run_id, result)
```

```json
POST /jobs
{
  "profile": "Brother_V34_33k6_ECM256",
  "did": "18005551212",
  "iterations": 50,
  "mode": "digital",
  "documents": [{"name": "control.pdf", "bytes_b64": "..."}],
  "rngSeed": 123456789
}
```

```python
def wait_stable(path, polls=3, interval=2.0):
    last = -1
    stable = 0
    while stable < polls:
        size = stat_size(path)
        stable = stable + 1 if size == last else 0
        last = size
        time.sleep(interval)
```

## 19. Packaging Checklist

* Version bump and changelog update.
* Codesign and notarize macOS build; sign Windows installer/MSIX.
* Bundle control sheet PDF, sample profiles/policies, sample reports.
* Publish checksums and include diagnostics JSON from self-test.

## 20. Compliance & Governance Defaults

* RBAC roles: Operator (run), Lead (override/thresholds), Admin (sites/certs).
* Append-only audit log for job activity, configuration hashes, overrides.
* Data retention: default 30-day raw purge, metrics retained indefinitely, redaction enabled for configured ROIs.

---

This plan delivers a cross-brand V.34/V.17 fax QA automation platform with deterministic simulation, optional T.38 validation, resilient verification pipeline, secure remote automation, privacy safeguards, and packaged releases for macOS and Windows.
