"""Report and log writers for the Fax QA automation CLI MVP."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Dict, Iterable, List
import csv
import json

from ..core.iteration_controller import IterationResult
from ..core.run_context import RunContext


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
    ) -> Path:
        path = run_dir / "summary.json"
        payload = {
            "run": self._run_metadata(context),
            "iterations": [self._iteration_dict(result) for result in iterations],
            "telemetry": list(telemetry),
        }
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
                    ]
                )
        return path

    def write_html(
        self, run_dir: Path, context: RunContext, iterations: Iterable[IterationResult]
    ) -> Path:
        path = run_dir / "report.html"
        chips = self._chips(context)
        iteration_sections = "\n".join(self._html_iteration_section(result) for result in iterations)
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
            "reference": str(context.reference),
            "candidate": str(context.candidate),
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


def _find_metric_value(metrics: Iterable[object], name: str) -> float | None:
    for metric in metrics:
        if getattr(metric, "name", None) == name:
            return getattr(metric, "value", None)
    return None
