"""Command line entry point for the Fax QA Automation MVP."""
from __future__ import annotations

from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path
from typing import List
import json

from .core.config_service import ConfigService, default_config_service
from .core.fax_simulation import FaxProfile
from .core.iteration_controller import IterationConfig, IterationController, IterationResult
from .core.run_context import RunContext
from .reports.reporter import ReportBuilder
from .verify.pipeline import VerificationPipeline


def _load_profile(config: ConfigService, profile_name: str) -> FaxProfile:
    loaded = config.load(f"profiles/{profile_name}.json")
    return FaxProfile.from_config(loaded.payload, loaded.sha256)


def _build_pipeline(
    config: ConfigService, policy_name: str, profile_hash: str | None
) -> tuple[VerificationPipeline, str]:
    loaded = config.load(f"verify_policy.{policy_name}.json")
    pipeline = VerificationPipeline(loaded.payload, loaded.sha256, profile_hash)
    return pipeline, loaded.sha256


def _build_context(
    run_id: str,
    profile: FaxProfile,
    policy_name: str,
    policy_hash: str,
    iterations: int,
    seed: int,
    reference: Path,
    candidate: Path,
    path_mode: str,
    did: str | None,
    pcfax_queue: str | None,
) -> RunContext:
    return RunContext(
        run_id=run_id,
        profile=profile,
        policy_name=policy_name,
        policy_hash=policy_hash,
        iterations=iterations,
        seed=seed,
        reference=reference,
        candidate=candidate,
        path_mode=path_mode,
        location="Local",
        did=did,
        pcfax_queue=pcfax_queue,
        started_at=datetime.utcnow(),
    )


def _persist_reports(
    report_builder: ReportBuilder,
    run_id: str,
    context: RunContext,
    iterations: List[IterationResult],
    telemetry: List[dict],
) -> Path:
    run_dir = report_builder.ensure_run_directory(run_id)
    report_builder.write_json(run_dir, context, iterations, telemetry)
    report_builder.write_csv(run_dir, context, iterations)
    report_builder.write_html(run_dir, context, iterations)
    report_builder.write_run_log(run_dir, context, iterations)
    telemetry_path = run_dir / "telemetry.json"
    telemetry_path.write_text(json.dumps(telemetry, indent=2))
    return run_dir


def run(argv: List[str] | None = None) -> None:
    parser = ArgumentParser(description="Fax QA Automation MVP")
    parser.add_argument("reference", type=Path, help="Reference document path")
    parser.add_argument("candidate", type=Path, help="Candidate document path")
    parser.add_argument("--profile", default="Brother_V34_33k6_ECM256", help="Profile name (without .json)")
    parser.add_argument("--policy", default="normal", help="Policy variant")
    parser.add_argument("--iterations", type=int, default=1, help="Number of iterations to run")
    parser.add_argument("--seed", type=int, default=1234, help="Seed for deterministic runs")
    parser.add_argument("--output", type=Path, default=Path("artifacts"), help="Base output directory for reports")
    parser.add_argument("--run-id", default="demo", help="Identifier used for artifact directories")
    parser.add_argument(
        "--path",
        choices=["digital", "print-scan"],
        default="digital",
        help="Test path used for the run",
    )
    parser.add_argument("--did", default=None, help="Dialed DID used for the run")
    parser.add_argument("--pcfax-queue", dest="pcfax_queue", default=None, help="HP PC-Fax queue identifier")
    args = parser.parse_args(argv)

    config = default_config_service()
    profile = _load_profile(config, args.profile)
    pipeline, policy_hash = _build_pipeline(config, args.policy, profile.config_sha256)
    controller = IterationController(profile=profile, verification_pipeline=pipeline)

    iteration_results = controller.run(
        IterationConfig(iterations=args.iterations, rng_seed=args.seed),
        reference=args.reference,
        candidate=args.candidate,
    )

    context = _build_context(
        run_id=args.run_id,
        profile=profile,
        policy_name=args.policy,
        policy_hash=policy_hash,
        iterations=args.iterations,
        seed=args.seed,
        reference=args.reference,
        candidate=args.candidate,
        path_mode=args.path,
        did=args.did,
        pcfax_queue=args.pcfax_queue,
    )

    report_builder = ReportBuilder(args.output)
    telemetry_events = list(controller.iter_events())
    run_dir = _persist_reports(
        report_builder,
        args.run_id,
        context,
        iteration_results,
        telemetry_events,
    )

    print(
        f"Run completed for profile {profile.name} with {len(iteration_results)} iteration(s). "
        f"Artifacts written to {run_dir}"
    )


if __name__ == "__main__":
    run()
