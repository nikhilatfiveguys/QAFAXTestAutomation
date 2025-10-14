"""Report writers for the Fax QA automation MVP."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable
import csv
import json

from ..core.iteration_controller import IterationResult


class ReportBuilder:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_json(self, run_id: str, iterations: Iterable[IterationResult]) -> Path:
        path = self.output_dir / f"{run_id}.json"
        payload = [self._iteration_dict(result) for result in iterations]
        path.write_text(json.dumps(payload, indent=2))
        return path

    def write_csv(self, run_id: str, iterations: Iterable[IterationResult]) -> Path:
        path = self.output_dir / f"{run_id}.csv"
        with path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow([
                "iteration",
                "verdict",
                "bitrate",
                "fallback_steps",
                "policy_hash",
                "profile_hash",
            ])
            for result in iterations:
                verification = result.verification
                writer.writerow(
                    [
                        result.index,
                        verification.verdict if verification else "UNKNOWN",
                        result.simulation.final_bitrate,
                        result.simulation.fallback_steps,
                        verification.policy_hash if verification else "",
                        verification.profile_hash if verification else "",
                    ]
                )
        return path

    def write_html(self, run_id: str, iterations: Iterable[IterationResult]) -> Path:
        path = self.output_dir / f"{run_id}.html"
        rows = [self._html_row(result) for result in iterations]
        html = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Fax QA Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ccc; padding: 0.5rem; text-align: left; }}
    th {{ background: #f0f4f8; }}
    .PASS {{ color: #1b5e20; }}
    .WARN {{ color: #f57f17; }}
    .FAIL {{ color: #b71c1c; }}
  </style>
</head>
<body>
  <h1>Fax QA Report: {run_id}</h1>
  <table>
    <thead>
      <tr>
        <th>Iteration</th>
        <th>Verdict</th>
        <th>Bitrate</th>
        <th>Fallback Steps</th>
        <th>Policy Hash</th>
        <th>Profile Hash</th>
      </tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>
</body>
</html>
""".strip().format(run_id=run_id, rows="\n".join(rows))
        path.write_text(html)
        return path

    def _iteration_dict(self, result: IterationResult) -> dict:
        verification = result.verification
        metrics = [metric.__dict__ for metric in verification.metrics] if verification else []
        return {
            "iteration": result.index,
            "simulation": {
                "profile": result.simulation.profile.name,
                "bitrate": result.simulation.final_bitrate,
                "fallback_steps": result.simulation.fallback_steps,
                "rng_seed": result.simulation.rng_seed,
            },
            "verification": {
                "verdict": verification.verdict if verification else None,
                "policy_hash": verification.policy_hash if verification else None,
                "profile_hash": verification.profile_hash if verification else None,
                "metrics": metrics,
            },
        }

    def _html_row(self, result: IterationResult) -> str:
        verification = result.verification
        verdict = verification.verdict if verification else "UNKNOWN"
        policy_hash = verification.policy_hash if verification else ""
        profile_hash = verification.profile_hash if verification else ""
        return (
            "<tr>"
            f"<td>{result.index}</td>"
            f"<td class='{verdict}'>{verdict}</td>"
            f"<td>{result.simulation.final_bitrate}</td>"
            f"<td>{result.simulation.fallback_steps}</td>"
            f"<td>{policy_hash}</td>"
            f"<td>{profile_hash}</td>"
            "</tr>"
        )
