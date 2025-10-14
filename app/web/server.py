"""FastAPI server exposing a browser-based front end for QA runs."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, List, Optional

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..core.config_service import default_config_service
from ..core.fax_simulation import FaxProfile
from ..core.iteration_controller import IterationConfig, IterationController, IterationResult
from ..reports.reporter import ReportBuilder
from ..verify.pipeline import VerificationPipeline
from . import __doc__  # noqa: F401  # ensure package is discovered

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
PROFILES_DIR = CONFIG_DIR / "profiles"
POLICY_PREFIX = "verify_policy."
ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "web"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Fax QA Automation UI")
app.mount("/artifacts", StaticFiles(directory=str(ARTIFACTS_DIR)), name="artifacts")

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


def _available_profiles() -> List[str]:
    return sorted(path.stem for path in PROFILES_DIR.glob("*.json"))


def _available_policies() -> List[str]:
    policies: List[str] = []
    for path in CONFIG_DIR.glob(f"{POLICY_PREFIX}*.json"):
        suffix = path.stem[len(POLICY_PREFIX) :]
        policies.append(suffix)
    return sorted(policies)


def _load_profile(name: str) -> FaxProfile:
    config = default_config_service()
    loaded = config.load(str(Path("profiles") / f"{name}.json"))
    return FaxProfile.from_config(loaded.payload)


def _build_pipeline(policy_name: str, profile_hash: Optional[str]) -> VerificationPipeline:
    config = default_config_service()
    loaded = config.load(f"{POLICY_PREFIX}{policy_name}.json")
    return VerificationPipeline(loaded.payload, loaded.sha256, profile_hash=profile_hash)


def _serialize_results(results: List[IterationResult]) -> List[Dict[str, object]]:
    serialized: List[Dict[str, object]] = []
    for result in results:
        verification = result.verification
        metrics: List[Dict[str, object]] = []
        if verification:
            for metric in verification.metrics:
                metrics.append(
                    {
                        "name": metric.name,
                        "status": metric.status,
                        "value": None if metric.value is None else round(float(metric.value), 4),
                        "detail": metric.detail,
                    }
                )
        events = [
            {
                "timestamp": f"{event.timestamp:.3f}",
                "phase": event.phase,
                "event": event.event,
                "detail": event.detail,
            }
            for event in result.simulation.events
        ]
        serialized.append(
            {
                "index": result.index,
                "simulation": {
                    "bitrate": result.simulation.final_bitrate,
                    "fallback_steps": result.simulation.fallback_steps,
                    "profile": result.simulation.profile.name,
                    "rng_seed": result.simulation.rng_seed,
                    "events": events,
                },
                "verification": None
                if verification is None
                else {
                    "verdict": verification.verdict,
                    "policy_hash": verification.policy_hash,
                    "profile_hash": verification.profile_hash,
                    "metrics": metrics,
                },
            }
        )
    return serialized


def _default_context(request: Request) -> Dict[str, object]:
    profiles = _available_profiles()
    policies = _available_policies()
    return {
        "request": request,
        "profiles": profiles,
        "policies": policies,
        "form_values": {
            "iterations": 1,
            "seed": 1234,
            "profile": profiles[0] if profiles else None,
            "policy": policies[0] if policies else None,
        },
        "result": None,
        "error": None,
    }


@app.get("/", response_class=HTMLResponse, name="index")
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", _default_context(request))


async def _persist_upload(upload: UploadFile, target: Path) -> Path:
    data = await upload.read()
    target.write_bytes(data)
    return target


@app.post("/", response_class=HTMLResponse)
async def run_job(
    request: Request,
    reference: UploadFile = File(...),
    candidate: UploadFile = File(...),
    profile: str = Form(...),
    policy: str = Form("normal"),
    iterations: int = Form(1),
    seed: int = Form(1234),
) -> HTMLResponse:
    context = _default_context(request)
    context["form_values"] = {
        "profile": profile,
        "policy": policy,
        "iterations": iterations,
        "seed": seed,
    }

    run_id = f"web-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

    try:
        profile_model = _load_profile(profile)
        pipeline = _build_pipeline(policy, profile_hash=profile_model.name)
        controller = IterationController(profile=profile_model, verification_pipeline=pipeline)

        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            reference_path = tmp_path / (reference.filename or "reference.bin")
            candidate_path = tmp_path / (candidate.filename or "candidate.bin")
            await _persist_upload(reference, reference_path)
            await _persist_upload(candidate, candidate_path)

            results = controller.run(
                IterationConfig(iterations=max(1, iterations), rng_seed=seed),
                reference=reference_path,
                candidate=candidate_path,
            )

        report_builder = ReportBuilder(ARTIFACTS_DIR)
        html_path = report_builder.write_html(run_id, results)
        json_path = report_builder.write_json(run_id, results)
        csv_path = report_builder.write_csv(run_id, results)

        context["result"] = {
            "run_id": run_id,
            "iterations": _serialize_results(results),
            "reports": {
                "html": html_path.name,
                "json": json_path.name,
                "csv": csv_path.name,
            },
        }
    except Exception as exc:  # pylint: disable=broad-except
        context["error"] = str(exc)

    return templates.TemplateResponse("index.html", context)


__all__ = ["app"]
