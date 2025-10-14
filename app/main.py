"""Command line entry point for the Fax QA Automation MVP."""
from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
from typing import List

from .core.config_service import ConfigService, default_config_service
from .core.fax_simulation import FaxProfile
from .core.iteration_controller import IterationConfig, IterationController
from .reports.reporter import ReportBuilder
from .verify.pipeline import VerificationPipeline


def _load_profile(config: ConfigService, profile_name: str) -> FaxProfile:
    profile_path = Path("profiles") / f"{profile_name}.json"
    payload = config.load(str(profile_path))
    return FaxProfile.from_config(payload.payload)


def _build_pipeline(config: ConfigService, policy_name: str, profile_hash: str | None) -> VerificationPipeline:
    loaded = config.load(f"verify_policy.{policy_name}.json")
    return VerificationPipeline(loaded.payload, loaded.sha256, profile_hash)


def run(argv: List[str] | None = None) -> None:
    parser = ArgumentParser(description="Fax QA Automation MVP")
    parser.add_argument("reference", type=Path, help="Reference document path")
    parser.add_argument("candidate", type=Path, help="Candidate document path")
    parser.add_argument("--profile", default="Brother_V34_33k6_ECM256", help="Profile name (without .json)")
    parser.add_argument("--policy", default="normal", help="Policy variant")
    parser.add_argument("--iterations", type=int, default=1, help="Number of iterations to run")
    parser.add_argument("--seed", type=int, default=1234, help="Seed for deterministic runs")
    parser.add_argument("--output", type=Path, default=Path("artifacts"), help="Output directory for reports")
    parser.add_argument("--run-id", default="demo", help="Identifier used for report filenames")
    args = parser.parse_args(argv)

    config = default_config_service()
    profile = _load_profile(config, args.profile)
    policy = config.load(f"verify_policy.{args.policy}.json")
    pipeline = VerificationPipeline(policy.payload, policy.sha256, profile_hash=profile.name)
    controller = IterationController(profile=profile, verification_pipeline=pipeline)
    iteration_results = controller.run(
        IterationConfig(iterations=args.iterations, rng_seed=args.seed),
        reference=args.reference,
        candidate=args.candidate,
    )
    report_builder = ReportBuilder(args.output)
    report_builder.write_json(args.run_id, iteration_results)
    report_builder.write_csv(args.run_id, iteration_results)
    report_builder.write_html(args.run_id, iteration_results)
    print(f"Run completed for profile {profile.name} with {len(iteration_results)} iteration(s).")
    for event in controller.iter_events():
        print(event)


if __name__ == "__main__":
    run()
