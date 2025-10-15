"""Command line entry point for the Fax QA Automation MVP."""
from __future__ import annotations

from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence
import json

from .connectors.smb_ingest import SMBIngestor
from .connectors.snmp import SNMPSnapshot, query_status
from .core.config_service import ConfigService, default_config_service
from .core.fax_simulation import FaxProfile
from .core.foip import FoipResult, FoipValidator
from .core.iteration_controller import IterationConfig, IterationController, IterationResult
from .core.run_context import RunContext
from .core.send_pcfax import submit_to_queue
from .reports.reporter import ReportBuilder
from .verify.pipeline import VerificationPipeline


def _load_profile(config: ConfigService, profile_name: str) -> FaxProfile:
    loaded = config.load(f"profiles/{profile_name}.json")
    return FaxProfile.from_config(loaded.payload, loaded.sha256)


def _build_pipeline(
    config: ConfigService,
    policy_name: str,
    profile_hash: str | None,
    require_ocr: bool,
    require_barcode: bool,
) -> tuple[VerificationPipeline, str]:
    loaded = config.load(f"verify_policy.{policy_name}.json")
    policy = dict(loaded.payload)
    ocr_cfg = dict(policy.get("ocr", {}))
    if require_ocr:
        ocr_cfg["required"] = True
    policy["ocr"] = ocr_cfg
    barcode_cfg = dict(policy.get("barcode", {}))
    if require_barcode:
        barcode_cfg["required"] = True
    policy["barcode"] = barcode_cfg
    pipeline = VerificationPipeline(policy, loaded.sha256, profile_hash)
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
    pcfax_detail: str | None,
    ingest_dir: Optional[str],
    ingest_pattern: Optional[str],
    snmp_snapshot: SNMPSnapshot | None,
    foip_result: FoipResult | None,
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
        ingest_dir=ingest_dir,
        ingest_pattern=ingest_pattern,
        pcfax_detail=pcfax_detail,
        snmp_snapshot=snmp_snapshot,
        foip_result=foip_result,
    )


def _persist_reports(
    report_builder: ReportBuilder,
    run_id: str,
    context: RunContext,
    iterations: List[IterationResult],
    telemetry: List[dict],
    ingest_artifacts: Sequence[Dict[str, object]],
    snmp_snapshot: SNMPSnapshot | None,
    foip_result: FoipResult | None,
) -> Path:
    run_dir = report_builder.ensure_run_directory(run_id)
    report_builder.write_json(
        run_dir,
        context,
        iterations,
        telemetry,
        ingest_artifacts,
        snmp_snapshot=snmp_snapshot,
        foip_result=foip_result,
    )
    report_builder.write_csv(run_dir, context, iterations)
    report_builder.write_html(run_dir, context, iterations)
    report_builder.write_run_log(run_dir, context, iterations)
    if iterations:
        reference_doc, candidate_doc = _first_verified_documents(iterations)
        if reference_doc and candidate_doc:
            report_builder.write_provenance(
                run_dir,
                reference_doc,
                candidate_doc,
                ingest_artifacts,
                snmp_snapshot=snmp_snapshot,
                foip_result=foip_result,
            )
    telemetry_path = run_dir / "telemetry.json"
    telemetry_path.write_text(json.dumps(telemetry, indent=2))
    return run_dir


def _first_verified_documents(iterations: Iterable[IterationResult]):
    for result in iterations:
        if result.verification:
            return result.verification.reference, result.verification.candidate
    return None, None


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
    parser.add_argument("--ingest-dir", dest="ingest_dir", default=None, help="Directory to monitor for ingested scans")
    parser.add_argument(
        "--ingest-pattern",
        dest="ingest_pattern",
        default="*",
        help="Glob pattern used when scanning ingest directory",
    )
    parser.add_argument(
        "--ingest-timeout",
        dest="ingest_timeout",
        type=float,
        default=0.0,
        help="Seconds to wait for new ingest files after the run",
    )
    parser.add_argument(
        "--ingest-interval",
        dest="ingest_interval",
        type=float,
        default=1.0,
        help="Polling interval in seconds for ingest stability checks",
    )
    parser.add_argument("--require-ocr", action="store_true", help="Force OCR metric to be required")
    parser.add_argument("--require-barcode", action="store_true", help="Force barcode metric to be required")
    parser.add_argument("--snmp-target", default=None, help="SNMP target hostname or IP")
    parser.add_argument("--snmp-community", default="public", help="SNMP community string")
    parser.add_argument(
        "--snmp-oids",
        default="1.3.6.1.2.1.43.10.2.1.4.1.1,1.3.6.1.2.1.43.16.5.1.2.1.1",
        help="Comma-separated list of SNMP OIDs to query",
    )
    parser.add_argument(
        "--foip-config",
        type=Path,
        default=None,
        help="Path to FoIP/T.38 validation configuration JSON",
    )
    args = parser.parse_args(argv)

    config = default_config_service()
    profile = _load_profile(config, args.profile)
    pipeline, policy_hash = _build_pipeline(
        config,
        args.policy,
        profile.config_sha256,
        require_ocr=args.require_ocr,
        require_barcode=args.require_barcode,
    )
    controller = IterationController(profile=profile, verification_pipeline=pipeline)

    pcfax_detail: Optional[str] = None
    if args.pcfax_queue:
        result = submit_to_queue(args.candidate, args.pcfax_queue, args.did)
        controller.telemetry_sink.emit(
            "pcfax.submission",
            queue=args.pcfax_queue,
            submitted=result.submitted,
            detail=result.detail,
        )
        pcfax_detail = result.detail

    snmp_snapshot: Optional[SNMPSnapshot] = None
    if args.snmp_target:
        oids = [oid.strip() for oid in args.snmp_oids.split(",") if oid.strip()]
        snmp_snapshot = query_status(args.snmp_target, args.snmp_community, oids)
        controller.telemetry_sink.emit(
            "snmp.snapshot",
            target=args.snmp_target,
            community=args.snmp_community,
            values=snmp_snapshot.values,
            errors=snmp_snapshot.errors,
        )

    foip_result: Optional[FoipResult] = None
    if args.foip_config:
        try:
            validator = FoipValidator(args.foip_config)
        except (OSError, json.JSONDecodeError) as exc:
            foip_result = FoipResult(
                executed=False,
                detail="FoIP configuration error",
                artifacts=[],
                errors=[str(exc)],
                command=None,
            )
        else:
            foip_result = validator.run()
        controller.telemetry_sink.emit(
            "foip.validation",
            executed=foip_result.executed,
            detail=foip_result.detail,
            artifacts=len(foip_result.artifacts),
            errors=foip_result.errors,
        )

    ingest_artifacts: List[Dict[str, object]] = []
    ingestor: Optional[SMBIngestor] = None
    baseline: Dict[Path, int] = {}
    if args.ingest_dir:
        ingestor = SMBIngestor(Path(args.ingest_dir), pattern=args.ingest_pattern, interval=args.ingest_interval)
        baseline = ingestor.snapshot()

    iteration_results = controller.run(
        IterationConfig(iterations=args.iterations, rng_seed=args.seed),
        reference=args.reference,
        candidate=args.candidate,
    )

    if ingestor is not None:
        artifacts = ingestor.detect_new(baseline, timeout=args.ingest_timeout)
        ingest_artifacts = [
            {
                "path": str(artifact.path),
                "size": artifact.size,
                "sha256": artifact.sha256,
                "capturedAt": artifact.captured_at,
            }
            for artifact in artifacts
        ]

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
        pcfax_detail=pcfax_detail,
        ingest_dir=args.ingest_dir,
        ingest_pattern=args.ingest_pattern if args.ingest_dir else None,
        snmp_snapshot=snmp_snapshot,
        foip_result=foip_result,
    )

    report_builder = ReportBuilder(args.output)
    telemetry_events = list(controller.iter_events())
    run_dir = _persist_reports(
        report_builder,
        args.run_id,
        context,
        iteration_results,
        telemetry_events,
        ingest_artifacts,
        snmp_snapshot,
        foip_result,
    )

    print(
        f"Run completed for profile {profile.name} with {len(iteration_results)} iteration(s). "
        f"Artifacts written to {run_dir}"
    )


if __name__ == "__main__":
    run()
