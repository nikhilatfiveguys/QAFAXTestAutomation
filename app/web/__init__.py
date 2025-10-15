"""FastAPI application that exposes the fax QA workflow through a browser."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional
import html
import uuid

from ..connectors.snmp import SNMPSnapshot
from ..core.config_service import default_config_service
from ..core.execution import DEFAULT_SNMP_OIDS, RunOptions, RunResult, execute_run
from ..core.iteration_controller import IterationResult
from ..core.foip import FoipResult


def create_app():  # type: ignore[override]
    """Build the FastAPI application for the web UI."""

    try:
        from fastapi import FastAPI, File, Form, UploadFile
        from fastapi.concurrency import run_in_threadpool
        from fastapi.responses import HTMLResponse
        from fastapi.staticfiles import StaticFiles
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "FastAPI (and python-multipart) is required to use the web interface."
        ) from exc

    app = FastAPI(title="QAFAX Web UI", description="Run fax QA workflows from the browser")
    config_service = default_config_service()
    artifacts_dir = Path("artifacts")
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/artifacts", StaticFiles(directory=str(artifacts_dir)), name="artifacts")

    profiles = _list_profiles(config_service.base_path / "profiles") or ["Brother_V34_33k6_ECM256"]
    policies = _list_policies(config_service.base_path)

    def _default_values() -> Dict[str, object]:
        return {
            "profile": profiles[0] if profiles else "Brother_V34_33k6_ECM256",
            "policy": policies[0] if policies else "normal",
            "run_id": "web-run",
            "iterations": 1,
            "seed": 1234,
            "path_mode": "digital",
            "did": "",
            "pcfax_queue": "",
            "ingest_dir": "",
            "ingest_pattern": "*",
            "ingest_timeout": 0.0,
            "ingest_interval": 1.0,
            "snmp_target": "",
            "snmp_community": "public",
            "snmp_oids": ",".join(DEFAULT_SNMP_OIDS),
            "require_ocr": False,
            "require_barcode": False,
        }

    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        values = _default_values()
        html_content = _render_page(
            profiles,
            policies,
            values,
            result=None,
            message=None,
            artifacts_root=artifacts_dir,
        )
        return HTMLResponse(html_content)

    @app.post("/run", response_class=HTMLResponse)
    async def run_workflow(
        reference_file: UploadFile = File(...),
        candidate_file: UploadFile = File(...),
        profile: str = Form(...),
        policy: str = Form(...),
        run_id: str = Form("web-run"),
        iterations: int = Form(1),
        seed: int = Form(1234),
        path_mode: str = Form("digital"),
        did: str = Form(""),
        pcfax_queue: str = Form(""),
        ingest_dir: str = Form(""),
        ingest_pattern: str = Form("*"),
        ingest_timeout: float = Form(0.0),
        ingest_interval: float = Form(1.0),
        snmp_target: str = Form(""),
        snmp_community: str = Form("public"),
        snmp_oids: str = Form(",".join(DEFAULT_SNMP_OIDS)),
        require_ocr: Optional[str] = Form(None),
        require_barcode: Optional[str] = Form(None),
        foip_config_file: UploadFile | None = File(None),
    ) -> HTMLResponse:
        values = _default_values()
        values.update(
            {
                "profile": profile,
                "policy": policy,
                "run_id": run_id,
                "iterations": iterations,
                "seed": seed,
                "path_mode": path_mode,
                "did": did,
                "pcfax_queue": pcfax_queue,
                "ingest_dir": ingest_dir,
                "ingest_pattern": ingest_pattern,
                "ingest_timeout": ingest_timeout,
                "ingest_interval": ingest_interval,
                "snmp_target": snmp_target,
                "snmp_community": snmp_community,
                "snmp_oids": snmp_oids,
                "require_ocr": require_ocr is not None,
                "require_barcode": require_barcode is not None,
            }
        )

        upload_dir = artifacts_dir / "uploads" / _timestamped_slug(run_id)
        upload_dir.mkdir(parents=True, exist_ok=True)

        reference_path = _persist_upload(reference_file, upload_dir, prefix="reference")
        candidate_path = _persist_upload(candidate_file, upload_dir, prefix="candidate")
        foip_path = None
        if foip_config_file is not None and foip_config_file.filename:
            foip_path = _persist_upload(foip_config_file, upload_dir, prefix="foip")

        snmp_list = [oid.strip() for oid in snmp_oids.split(",") if oid.strip()]
        options = RunOptions(
            reference=reference_path,
            candidate=candidate_path,
            profile=profile,
            policy=policy,
            iterations=iterations,
            seed=seed,
            output_dir=artifacts_dir,
            run_id=run_id,
            path_mode=path_mode,
            did=did or None,
            pcfax_queue=pcfax_queue or None,
            ingest_dir=ingest_dir or None,
            ingest_pattern=ingest_pattern or "*",
            ingest_timeout=ingest_timeout,
            ingest_interval=ingest_interval,
            require_ocr=require_ocr is not None,
            require_barcode=require_barcode is not None,
            snmp_target=snmp_target or None,
            snmp_community=snmp_community or "public",
            snmp_oids=snmp_list,
            foip_config=foip_path,
        )

        try:
            result = await run_in_threadpool(execute_run, options)
        except Exception as exc:  # pragma: no cover - defensive guard
            html_content = _render_page(
                profiles,
                policies,
                values,
                result=None,
                message=f"Run failed: {html.escape(str(exc))}",
                artifacts_root=artifacts_dir,
            )
            return HTMLResponse(html_content, status_code=500)

        html_content = _render_page(
            profiles,
            policies,
            values,
            result=result,
            message="Run completed successfully.",
            artifacts_root=artifacts_dir,
        )
        return HTMLResponse(html_content)

    return app


def _list_profiles(root: Path) -> List[str]:
    return sorted(path.stem for path in root.glob("*.json"))


def _list_policies(config_root: Path) -> List[str]:
    results: List[str] = []
    for path in config_root.glob("verify_policy.*.json"):
        name = path.stem.split("verify_policy.")[-1]
        results.append(name)
    return sorted(results) or ["normal"]


def _timestamped_slug(run_id: str) -> str:
    safe_id = "".join(ch for ch in run_id if ch.isalnum() or ch in {"-", "_"}) or "run"
    suffix = uuid.uuid4().hex[:6]
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    return f"{safe_id}-{stamp}-{suffix}"


def _persist_upload(upload: "UploadFile", directory: Path, prefix: str) -> Path:
    filename = Path(upload.filename or f"{prefix}.bin").name
    path = directory / f"{prefix}-{filename}"
    upload.file.seek(0)
    data = upload.file.read()
    path.write_bytes(data)
    upload.file.close()
    return path


def _render_page(
    profiles: Iterable[str],
    policies: Iterable[str],
    values: Dict[str, object],
    *,
    result: RunResult | None,
    message: Optional[str],
    artifacts_root: Path,
) -> str:
    profile_options = "".join(
        _option_html(option, option == values.get("profile", "")) for option in profiles
    )
    policy_options = "".join(
        _option_html(option, option == values.get("policy", "")) for option in policies
    )
    message_html = f"<div class='message'>{html.escape(message)}</div>" if message else ""
    result_html = (
        _render_result(result, artifacts_root) if result is not None else ""
    )
    return """
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>QAFAX Web UI</title>
    <style>
      body { font-family: Arial, sans-serif; margin: 2rem; color: #0f172a; }
      h1 { margin-bottom: 0.5rem; }
      form { background: #f8fafc; padding: 1.5rem; border-radius: 12px; box-shadow: 0 4px 12px rgba(15, 23, 42, 0.1); }
      fieldset { border: none; margin: 0; padding: 0; }
      .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; margin-top: 1rem; }
      label { display: flex; flex-direction: column; font-size: 0.9rem; color: #1e293b; }
      input[type="text"], input[type="number"], input[type="file"], select { margin-top: 0.25rem; padding: 0.5rem; border: 1px solid #cbd5f5; border-radius: 8px; font-size: 0.95rem; }
      .checkbox { display: flex; align-items: center; gap: 0.5rem; }
      button { margin-top: 1.5rem; padding: 0.75rem 1.5rem; background: #0284c7; color: white; border: none; border-radius: 999px; font-size: 1rem; cursor: pointer; }
      button:hover { background: #0369a1; }
      .message { margin: 1rem 0; padding: 0.75rem 1rem; background: #e0f2fe; color: #075985; border-radius: 8px; }
      .results { margin-top: 2rem; }
      .chips { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 1rem; }
      .chip { background: #e0f2fe; color: #0c4a6e; padding: 0.25rem 0.75rem; border-radius: 999px; font-size: 0.85rem; }
      table { width: 100%; border-collapse: collapse; margin-bottom: 1.5rem; }
      th, td { border: 1px solid #cbd5f5; padding: 0.5rem; text-align: left; font-size: 0.9rem; }
      th { background: #f1f5f9; }
      .PASS { color: #166534; }
      .WARN { color: #b45309; }
      .FAIL { color: #b91c1c; }
      .artifacts a { color: #0369a1; text-decoration: none; }
      .artifacts a:hover { text-decoration: underline; }
    </style>
  </head>
  <body>
    <h1>QAFAX Web UI</h1>
    <p>Upload reference and candidate documents, adjust options, and run the verification pipeline from your browser.</p>
    {message_html}
    <form method="post" action="/run" enctype="multipart/form-data">
      <fieldset class="grid">
        <label>Reference Document<input type="file" name="reference_file" required /></label>
        <label>Candidate Document<input type="file" name="candidate_file" required /></label>
        <label>Profile<select name="profile">{profile_options}</select></label>
        <label>Policy<select name="policy">{policy_options}</select></label>
        <label>Run ID<input type="text" name="run_id" value="{run_id}" required /></label>
        <label>Iterations<input type="number" min="1" name="iterations" value="{iterations}" /></label>
        <label>Seed<input type="number" name="seed" value="{seed}" /></label>
        <label>Path<select name="path_mode">{path_options}</select></label>
        <label>DID<input type="text" name="did" value="{did}" /></label>
        <label>HP PC-Fax Queue<input type="text" name="pcfax_queue" value="{pcfax_queue}" /></label>
        <label>Ingest Directory<input type="text" name="ingest_dir" value="{ingest_dir}" /></label>
        <label>Ingest Pattern<input type="text" name="ingest_pattern" value="{ingest_pattern}" /></label>
        <label>Ingest Timeout (s)<input type="number" step="0.1" name="ingest_timeout" value="{ingest_timeout}" /></label>
        <label>Ingest Interval (s)<input type="number" step="0.1" name="ingest_interval" value="{ingest_interval}" /></label>
        <label>SNMP Target<input type="text" name="snmp_target" value="{snmp_target}" /></label>
        <label>SNMP Community<input type="text" name="snmp_community" value="{snmp_community}" /></label>
        <label>SNMP OIDs<input type="text" name="snmp_oids" value="{snmp_oids}" /></label>
        <label>FoIP Config<input type="file" name="foip_config_file" /></label>
      </fieldset>
      <div class="grid" style="margin-top:1rem;">
        <label class="checkbox"><input type="checkbox" name="require_ocr" {require_ocr_checked} />Require OCR</label>
        <label class="checkbox"><input type="checkbox" name="require_barcode" {require_barcode_checked} />Require Barcode</label>
      </div>
      <button type="submit">Run Verification</button>
    </form>
    <div class="results">{result_html}</div>
  </body>
</html>
""".strip().format(
        message_html=message_html,
        profile_options=profile_options,
        policy_options=policy_options,
        run_id=html.escape(str(values.get("run_id", ""))),
        iterations=html.escape(str(values.get("iterations", 1))),
        seed=html.escape(str(values.get("seed", 1234))),
        path_options=_path_options(str(values.get("path_mode", "digital"))),
        did=html.escape(str(values.get("did", ""))),
        pcfax_queue=html.escape(str(values.get("pcfax_queue", ""))),
        ingest_dir=html.escape(str(values.get("ingest_dir", ""))),
        ingest_pattern=html.escape(str(values.get("ingest_pattern", "*"))),
        ingest_timeout=html.escape(str(values.get("ingest_timeout", 0.0))),
        ingest_interval=html.escape(str(values.get("ingest_interval", 1.0))),
        snmp_target=html.escape(str(values.get("snmp_target", ""))),
        snmp_community=html.escape(str(values.get("snmp_community", "public"))),
        snmp_oids=html.escape(str(values.get("snmp_oids", ",".join(DEFAULT_SNMP_OIDS)))),
        require_ocr_checked="checked" if values.get("require_ocr") else "",
        require_barcode_checked="checked" if values.get("require_barcode") else "",
        result_html=result_html,
    )


def _option_html(value: str, selected: bool) -> str:
    escaped = html.escape(value)
    return f"<option value='{escaped}' {'selected' if selected else ''}>{escaped}</option>"


def _path_options(selected: str) -> str:
    options = []
    for value, label in (("digital", "Digital"), ("print-scan", "Print-Scan")):
        escaped = html.escape(value)
        choice = "selected" if value == selected else ""
        options.append(f"<option value='{escaped}' {choice}>{label}</option>")
    return "".join(options)


def _render_result(result: RunResult, artifacts_root: Path) -> str:
    context = result.context
    chips = _render_chips(context)
    artifact_links = _render_artifact_links(result.generated_files, artifacts_root)
    iterations = "".join(_render_iteration(iteration) for iteration in result.iterations)
    ingest_section = _render_ingest_section(result.ingest_artifacts)
    snmp_section = _render_snmp_section(result.snmp_snapshot)
    foip_section = _render_foip_section(result.foip_result)
    return f"""
    <section>
      <h2>Run Summary — {html.escape(context.run_id)}</h2>
      <div class="chips">{chips}</div>
      <div class="artifacts">{artifact_links}</div>
      {snmp_section}
      {foip_section}
      {ingest_section}
      {iterations}
    </section>
    """.strip()


def _render_chips(context) -> str:
    chips = [
        context.profile.brand,
        f"Standard {context.profile.standard}",
        context.bitrate_label,
        context.ecm_label,
        context.path_label,
        context.location,
    ]
    if context.did:
        chips.append(f"DID {context.did}")
    if context.pcfax_queue:
        chips.append(f"HP PC-Fax: {context.pcfax_queue}")
    if context.pcfax_detail:
        chips.append(context.pcfax_detail)
    ingest_label = context.ingest_label
    if ingest_label:
        chips.append(ingest_label)
    foip_label = context.foip_label
    if foip_label:
        chips.append(foip_label)
    snmp_label = context.snmp_label
    if snmp_label:
        chips.append(snmp_label)
    return "".join(f"<span class='chip'>{html.escape(chip)}</span>" for chip in chips)


def _render_artifact_links(files: Dict[str, Path], artifacts_root: Path) -> str:
    links: List[str] = []
    for label, key in (
        ("HTML Report", "report_html"),
        ("Summary JSON", "summary_json"),
        ("Summary CSV", "summary_csv"),
        ("Run Log", "run_log"),
        ("Provenance", "provenance_json"),
        ("Telemetry", "telemetry_json"),
    ):
        path = files.get(key)
        if not path:
            continue
        url = _artifact_url(path, artifacts_root)
        links.append(f"<a href='{url}' target='_blank'>{html.escape(label)}</a>")
    if not links:
        return ""
    return " | ".join(links)


def _artifact_url(path: Path, artifacts_root: Path) -> str:
    try:
        relative = path.resolve().relative_to(artifacts_root.resolve())
    except ValueError:
        return "#"
    return f"/artifacts/{relative.as_posix()}"


def _render_iteration(iteration: IterationResult) -> str:
    verification = iteration.verification
    if verification is None:
        return "<section><h3>Iteration {}</h3><p>No verification result.</p></section>".format(iteration.index)
    metrics_rows = "".join(
        f"<tr><td>{html.escape(metric.name)}</td><td>{html.escape(_format_value(metric.value))}</td>"
        f"<td class='{html.escape(metric.status)}'>{html.escape(metric.status)}</td>"
        f"<td>{html.escape(metric.detail)}</td></tr>"
        for metric in verification.metrics
    )
    notes = "".join(f"<li>{html.escape(note)}</li>" for note in verification.notes)
    notes_section = f"<ul>{notes}</ul>" if notes else ""
    return f"""
    <section class="iteration">
      <h3>Iteration {html.escape(str(iteration.index))} — {html.escape(verification.verdict)}</h3>
      <p>Bitrate: {html.escape(str(verification.simulation.final_bitrate))} • Fallback steps: {html.escape(str(verification.simulation.fallback_steps))}</p>
      <table>
        <thead><tr><th>Metric</th><th>Value</th><th>Status</th><th>Detail</th></tr></thead>
        <tbody>{metrics_rows}</tbody>
      </table>
      {notes_section}
    </section>
    """.strip()


def _format_value(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{value:.3f}" if isinstance(value, float) else str(value)


def _render_ingest_section(artifacts: Iterable[Dict[str, object]]) -> str:
    artifacts = list(artifacts)
    if not artifacts:
        return ""
    rows = "".join(
        f"<tr><td>{html.escape(str(item.get('path', '')))}</td>"
        f"<td>{html.escape(str(item.get('size', '')))}</td>"
        f"<td>{html.escape(str(item.get('sha256', '')))}</td>"
        f"<td>{html.escape(str(item.get('capturedAt', '')))}</td></tr>"
        for item in artifacts
    )
    return """
    <section>
      <h3>Ingested Artifacts</h3>
      <table>
        <thead><tr><th>Path</th><th>Size</th><th>SHA-256</th><th>Captured</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </section>
    """.strip()


def _render_snmp_section(snapshot: Optional[SNMPSnapshot]) -> str:
    if snapshot is None:
        return ""
    rows = "".join(
        f"<tr><td>{html.escape(oid)}</td><td>{html.escape(str(value))}</td></tr>"
        for oid, value in snapshot.values.items()
    )
    errors = "".join(f"<li>{html.escape(error)}</li>" for error in snapshot.errors)
    errors_section = f"<ul>{errors}</ul>" if snapshot.errors else ""
    return f"""
    <section>
      <h3>SNMP Snapshot — {html.escape(snapshot.target)}</h3>
      <table>
        <thead><tr><th>OID</th><th>Value</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
      {errors_section}
    </section>
    """.strip()


def _render_foip_section(result: Optional[FoipResult]) -> str:
    if result is None:
        return ""
    artifacts = "".join(
        f"<tr><td>{html.escape(str(artifact.path))}</td>"
        f"<td>{artifact.size}</td><td>{html.escape(artifact.sha256)}</td></tr>"
        for artifact in result.artifacts
    )
    artifact_section = (
        """
        <table>
          <thead><tr><th>Artifact</th><th>Size</th><th>SHA-256</th></tr></thead>
          <tbody>{}</tbody>
        </table>
        """.format(artifacts)
        if artifacts
        else ""
    )
    errors = "".join(f"<li>{html.escape(error)}</li>" for error in result.errors)
    errors_section = f"<ul>{errors}</ul>" if result.errors else ""
    command = f"<p>Command: {' '.join(result.command) if result.command else 'n/a'}</p>"
    return f"""
    <section>
      <h3>FoIP Validation — {'Executed' if result.executed else 'Dry Run'}</h3>
      <p>{html.escape(result.detail)}</p>
      {command}
      {artifact_section}
      {errors_section}
    </section>
    """.strip()


try:  # pragma: no cover - module level convenience for ASGI servers
    app = create_app()
except RuntimeError:  # FastAPI not installed; defer error until explicitly requested
    app = None  # type: ignore


__all__ = ["create_app", "app"]

