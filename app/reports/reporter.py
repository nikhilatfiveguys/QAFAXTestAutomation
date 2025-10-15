"""Report and log writers for the Fax QA automation CLI MVP."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence
import csv
import json

from ..connectors.snmp import SNMPSnapshot
from ..core.foip import FoipResult
from ..core.iteration_controller import IterationResult
from ..core.run_context import RunContext
from ..verify.loaders import DocumentData


class ReportBuilder:
    """Generate JSON/CSV/HTML summaries and a textual run log."""

    def __init__(self, base_output_dir: Path) -> None:
        self.base_output_dir = base_output_dir
        self.base_output_dir.mkdir(parents=True, exist_ok=True)

    def ensure_run_directory(self, run_id: str) -> Path:
        run_dir = self.base_output_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def write_json(
        self,
        run_dir: Path,
        context: RunContext,
        iterations: Iterable[IterationResult],
        telemetry: Iterable[Dict[str, object]],
        ingest_artifacts: Sequence[Dict[str, object]] | None = None,
        *,
        snmp_snapshot: SNMPSnapshot | None = None,
        foip_result: FoipResult | None = None,
    ) -> Path:
        path = run_dir / "summary.json"
        payload = {
            "run": self._run_metadata(context),
            "iterations": [self._iteration_dict(result) for result in iterations],
            "telemetry": list(telemetry),
        }
        if ingest_artifacts is not None:
            payload["ingestArtifacts"] = list(ingest_artifacts)
        if snmp_snapshot is not None:
            payload["snmp"] = snmp_snapshot.to_dict()
        if foip_result is not None:
            payload["foip"] = foip_result.to_dict()
        path.write_text(json.dumps(payload, indent=2))
        return path

    def write_csv(
        self, run_dir: Path, context: RunContext, iterations: Iterable[IterationResult]
    ) -> Path:
        path = run_dir / "summary.csv"
        with path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "iteration",
                    "verdict",
                    "bitrate",
                    "fallback_steps",
                    "policy_hash",
                    "profile_hash",
                    "mismatch_ratio",
                    "path_mode",
                    "did",
                    "pcfax_queue",
                    "pcfax_detail",
                ]
            )
            for result in iterations:
                verification = result.verification
                mismatch_ratio = _find_metric_value(verification.metrics if verification else [], "LINES")
                writer.writerow(
                    [
                        result.index,
                        verification.verdict if verification else "UNKNOWN",
                        result.simulation.final_bitrate,
                        result.simulation.fallback_steps,
                        verification.policy_hash if verification else "",
                        verification.profile_hash if verification else "",
                        mismatch_ratio if mismatch_ratio is not None else "",
                        context.path_mode,
                        context.did or "",
                        context.pcfax_queue or "",
                        context.pcfax_detail or "",
                    ]
                )
        return path

    def write_html(
        self, run_dir: Path, context: RunContext, iterations: Iterable[IterationResult]
    ) -> Path:
        path = run_dir / "report.html"
        chips = self._chips(context)
        iteration_sections = "\n".join(self._html_iteration_section(result) for result in iterations)
        extra_sections = self._html_snmp_section(context) + self._html_foip_section(context)
        html = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Fax QA Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; color: #0f172a; }}
    h1 {{ margin-bottom: 0.25rem; }}
    .chips {{ margin: 0 0 1rem 0; display: flex; flex-wrap: wrap; gap: 0.5rem; }}
    .chip {{ background: #e0f2fe; color: #0c4a6e; padding: 0.25rem 0.75rem; border-radius: 999px; font-size: 0.9rem; }}
    .meta {{ margin-bottom: 1rem; font-size: 0.9rem; color: #475569; }}
    .meta span {{ display: inline-block; margin-right: 1rem; }}
    .iteration {{ border-top: 1px solid #cbd5f5; padding-top: 1rem; margin-top: 1rem; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 1rem; }}
    th, td {{ border: 1px solid #cbd5f5; padding: 0.5rem; text-align: left; }}
    th {{ background: #f1f5f9; }}
    .PASS {{ color: #166534; }}
    .WARN {{ color: #b45309; }}
    .FAIL {{ color: #b91c1c; }}
    .events td {{ font-family: "Fira Mono", monospace; font-size: 0.85rem; }}
  </style>
</head>
<body>
  <h1>Fax QA Report — {run_id}</h1>
  <div class="chips">{chips}</div>
  <div class="meta">
    <span>Profile: {profile}</span>
    <span>Policy: {policy}</span>
    <span>Iterations: {iterations}</span>
    <span>Seed: {seed}</span>
    <span>Reference: {reference}</span>
    <span>Candidate: {candidate}</span>
  </div>
  {extra_sections}
  {iteration_sections}
</body>
</html>
""".strip().format(
            run_id=context.run_id,
            chips="".join(f"<span class='chip'>{chip}</span>" for chip in chips),
            profile=f"{context.profile.name} ({context.profile.config_sha256[:8]})",
            policy=f"{context.policy_name} ({context.policy_hash[:8]})",
            iterations=context.iterations,
            seed=context.seed,
            reference=context.reference,
            candidate=context.candidate,
            extra_sections=extra_sections,
            iteration_sections=iteration_sections,
        )
        path.write_text(html)
        return path

    def write_run_log(
        self, run_dir: Path, context: RunContext, iterations: Iterable[IterationResult]
    ) -> Path:
        path = run_dir / "run.log"
        lines = [
            f"Run ID: {context.run_id}",
            f"Started: {context.started_at.isoformat(timespec='seconds')}",
            f"Profile: {context.profile.name} (brand={context.profile.brand})",
            f"Policy: {context.policy_name}",
            f"Iterations: {context.iterations}",
            f"Seed: {context.seed}",
            f"Path Mode: {context.path_mode}",
            f"Location: {context.location}",
        ]
        if context.did:
            lines.append(f"DID: {context.did}")
        if context.pcfax_queue:
            lines.append(f"HP PC-Fax Queue: {context.pcfax_queue}")
        if context.pcfax_detail:
            lines.append(f"HP PC-Fax Detail: {context.pcfax_detail}")
        if context.ingest_dir:
            lines.append(f"Ingest Directory: {context.ingest_dir} pattern={context.ingest_pattern or '*'}")
        if context.foip_result:
            lines.append(
                f"FoIP validation executed={context.foip_result.executed} detail={context.foip_result.detail}"
            )
            for error in context.foip_result.errors:
                lines.append(f"FoIP error: {error}")
            for artifact in context.foip_result.artifacts:
                lines.append(
                    f"FoIP artifact: {artifact.path} size={artifact.size} sha256={artifact.sha256}"
                )
        if context.snmp_snapshot:
            lines.append(f"SNMP target: {context.snmp_snapshot.target}")
            for error in context.snmp_snapshot.errors:
                lines.append(f"SNMP error: {error}")
            for oid, value in context.snmp_snapshot.values.items():
                lines.append(f"SNMP {oid}: {value}")
        lines.append("")
        for result in iterations:
            verification = result.verification
            verdict = verification.verdict if verification else "UNKNOWN"
            lines.append(f"Iteration {result.index}: verdict={verdict} bitrate={result.simulation.final_bitrate}")
            for event in result.simulation.events:
                lines.append(
                    f"  [{event.timestamp:0.3f}] {event.phase} {event.event} :: {event.detail}"
                )
            lines.append("")
        path.write_text("\n".join(lines).strip() + "\n")
        return path

    def write_provenance(
        self,
        run_dir: Path,
        reference: DocumentData,
        candidate: DocumentData,
        ingest_artifacts: Sequence[Dict[str, object]],
        *,
        snmp_snapshot: SNMPSnapshot | None = None,
        foip_result: FoipResult | None = None,
    ) -> Path:
        payload = {
            "reference": {
                "path": str(reference.path),
                "sha256": reference.sha256,
                "size": reference.size,
                "pages": reference.page_count,
            },
            "candidate": {
                "path": str(candidate.path),
                "sha256": candidate.sha256,
                "size": candidate.size,
                "pages": candidate.page_count,
            },
            "ingest": list(ingest_artifacts),
        }
        if snmp_snapshot is not None:
            payload["snmp"] = snmp_snapshot.to_dict()
        if foip_result is not None:
            payload["foip"] = foip_result.to_dict()
        path = run_dir / "provenance.json"
        path.write_text(json.dumps(payload, indent=2))
        return path

    def _chips(self, context: RunContext) -> List[str]:
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
        return chips

    def _run_metadata(self, context: RunContext) -> Dict[str, object]:
        return {
            "id": context.run_id,
            "startedAt": context.started_at.isoformat(),
            "profile": {
                "name": context.profile.name,
                "brand": context.profile.brand,
                "hash": context.profile.config_sha256,
                "standard": context.profile.standard,
                "maxBitrate": context.profile.max_bitrate,
                "ecm": {
                    "enabled": context.profile.ecm_enabled,
                    "blockBytes": context.profile.ecm_block_bytes,
                },
            },
            "policy": {"name": context.policy_name, "hash": context.policy_hash},
            "iterations": context.iterations,
            "seed": context.seed,
            "pathMode": context.path_mode,
            "location": context.location,
            "did": context.did,
            "pcfaxQueue": context.pcfax_queue,
            "pcfaxDetail": context.pcfax_detail,
            "ingestDir": context.ingest_dir,
            "ingestPattern": context.ingest_pattern,
            "reference": str(context.reference),
            "candidate": str(context.candidate),
            "snmp": context.snmp_snapshot.to_dict() if context.snmp_snapshot else None,
            "foip": context.foip_result.to_dict() if context.foip_result else None,
        }

    def _iteration_dict(self, result: IterationResult) -> Dict[str, object]:
        verification = result.verification
        metrics = [asdict(metric) for metric in verification.metrics] if verification else []
        return {
            "iteration": result.index,
            "simulation": {
                "bitrate": result.simulation.final_bitrate,
                "fallback_steps": result.simulation.fallback_steps,
                "rng_seed": result.simulation.rng_seed,
                "events": [
                    {
                        "timestamp": event.timestamp,
                        "phase": event.phase,
                        "event": event.event,
                        "detail": event.detail,
                    }
                    for event in result.simulation.events
                ],
            },
            "verification": {
                "verdict": verification.verdict if verification else None,
                "policy_hash": verification.policy_hash if verification else None,
                "profile_hash": verification.profile_hash if verification else None,
                "metrics": metrics,
            },
        }

    def _html_iteration_section(self, result: IterationResult) -> str:
        verification = result.verification
        verdict = verification.verdict if verification else "UNKNOWN"
        metrics_rows = "".join(
            "<tr><td>{name}</td><td>{value}</td><td class='{status}'>{status}</td><td>{detail}</td></tr>".format(
                name=metric.name,
                value=metric.value if metric.value is not None else "",
                status=metric.status,
                detail=metric.detail,
            )
            for metric in (verification.metrics if verification else [])
        )
        if not metrics_rows:
            metrics_rows = "<tr><td colspan='4'>No verification metrics recorded.</td></tr>"
        events_rows = "".join(
            "<tr><td>{timestamp:0.3f}</td><td>{phase}</td><td>{event}</td><td>{detail}</td></tr>".format(
                timestamp=event.timestamp,
                phase=event.phase,
                event=event.event,
                detail=event.detail,
            )
            for event in result.simulation.events
        )
        return """
  <section class="iteration">
    <h2>Iteration {index} — <span class="{verdict}">{verdict}</span></h2>
    <p>Fallback steps: {fallback} • RNG seed: {seed}</p>
    <h3>Verification Metrics</h3>
    <table class="metrics">
      <thead><tr><th>Name</th><th>Value</th><th>Status</th><th>Detail</th></tr></thead>
      <tbody>{metrics_rows}</tbody>
    </table>
    <h3>Negotiation Log</h3>
    <table class="events">
      <thead><tr><th>Timestamp</th><th>Phase</th><th>Event</th><th>Detail</th></tr></thead>
      <tbody>{events_rows}</tbody>
    </table>
  </section>
""".format(
            index=result.index,
            verdict=verdict,
            fallback=result.simulation.fallback_steps,
            seed=result.simulation.rng_seed,
            metrics_rows=metrics_rows,
            events_rows=events_rows or "<tr><td colspan='4'>No events recorded.</td></tr>",
        )

    def _html_snmp_section(self, context: RunContext) -> str:
        snapshot = context.snmp_snapshot
        if not snapshot:
            return ""
        values_rows = "".join(
            f"<tr><td>{oid}</td><td>{value}</td></tr>" for oid, value in snapshot.values.items()
        )
        if not values_rows:
            values_rows = "<tr><td colspan='2'>No values returned.</td></tr>"
        errors = "".join(f"<li>{error}</li>" for error in snapshot.errors)
        error_block = f"<ul>{errors}</ul>" if errors else "<p>No SNMP errors reported.</p>"
        return """
  <section class="iteration">
    <h2>SNMP Snapshot — {target}</h2>
    <p>Community: {community} • Captured: {captured}</p>
    <table class="metrics"><thead><tr><th>OID</th><th>Value</th></tr></thead><tbody>{rows}</tbody></table>
    <div class="meta">{error_block}</div>
  </section>
""".format(
            target=snapshot.target,
            community=snapshot.community,
            captured=snapshot.captured_at.isoformat(timespec="seconds"),
            rows=values_rows,
            error_block=error_block,
        )

    def _html_foip_section(self, context: RunContext) -> str:
        result = context.foip_result
        if not result:
            return ""
        artifact_rows = "".join(
            f"<tr><td>{artifact.path}</td><td>{artifact.size}</td><td>{artifact.sha256}</td></tr>"
            for artifact in result.artifacts
        )
        if not artifact_rows:
            artifact_rows = "<tr><td colspan='3'>No FoIP artifacts captured.</td></tr>"
        errors = "".join(f"<li>{error}</li>" for error in result.errors)
        error_block = f"<ul>{errors}</ul>" if errors else "<p>No FoIP errors reported.</p>"
        command = " ".join(result.command) if result.command else "(none)"
        return """
  <section class="iteration">
    <h2>FoIP Validation</h2>
    <p>Executed: {executed} • Detail: {detail} • Command: {command}</p>
    <table class="metrics"><thead><tr><th>Artifact</th><th>Size</th><th>SHA-256</th></tr></thead><tbody>{rows}</tbody></table>
    <div class="meta">{error_block}</div>
  </section>
""".format(
            executed="Yes" if result.executed else "No",
            detail=result.detail,
            command=command,
            rows=artifact_rows,
            error_block=error_block,
        )


def _find_metric_value(metrics: Iterable[object], name: str) -> float | None:
    for metric in metrics:
        if getattr(metric, "name", None) == name:
            return getattr(metric, "value", None)
    return None
