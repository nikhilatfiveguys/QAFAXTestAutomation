"""Shared execution utilities for CLI and web workflows."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
import json

from ..connectors.smb_ingest import SMBIngestor
from ..connectors.snmp import SNMPSnapshot, query_status
from ..core.fax_simulation import FaxProfile
from ..core.foip import FoipResult, FoipValidator
from ..core.iteration_controller import (
    IterationConfig,
    IterationController,
    IterationResult,
)
from ..core.run_context import RunContext
from ..core.send_pcfax import submit_to_queue
from ..reports.reporter import ReportBuilder
from ..verify.pipeline import VerificationPipeline
from .config_service import ConfigService, default_config_service


DEFAULT_SNMP_OIDS: Tuple[str, ...] = (
    "1.3.6.1.2.1.43.10.2.1.4.1.1",
    "1.3.6.1.2.1.43.16.5.1.2.1.1",
)


@dataclass
class RunOptions:
    """Parameters required to execute a fax QA run."""

    reference: Path
    candidate: Path
    profile: str = "Brother_V34_33k6_ECM256"
    policy: str = "normal"
    iterations: int = 1
    seed: int = 1234
    output_dir: Path = field(default_factory=lambda: Path("artifacts"))
    run_id: str = "demo"
    path_mode: str = "digital"
    did: Optional[str] = None
    pcfax_queue: Optional[str] = None
    ingest_dir: Optional[str] = None
    ingest_pattern: str = "*"
    ingest_timeout: float = 0.0
    ingest_interval: float = 1.0
    require_ocr: bool = False
    require_barcode: bool = False
    snmp_target: Optional[str] = None
    snmp_community: str = "public"
    snmp_oids: Sequence[str] = field(default_factory=lambda: DEFAULT_SNMP_OIDS)
    foip_config: Optional[Path] = None


@dataclass
class RunResult:
    """Artifacts produced by an execution."""

    context: RunContext
    iterations: List[IterationResult]
    telemetry: List[dict]
    ingest_artifacts: List[Dict[str, object]]
    snmp_snapshot: Optional[SNMPSnapshot]
    foip_result: Optional[FoipResult]
    run_dir: Path
    generated_files: Dict[str, Path]


def execute_run(options: RunOptions, config_service: ConfigService | None = None) -> RunResult:
    """Execute a fax QA run and persist reports using the provided options."""

    config = config_service or default_config_service()
    profile = _load_profile(config, options.profile)
    pipeline, policy_hash = _build_pipeline(
        config,
        options.policy,
        profile.config_sha256,
        require_ocr=options.require_ocr,
        require_barcode=options.require_barcode,
    )
    controller = IterationController(profile=profile, verification_pipeline=pipeline)

    pcfax_detail: Optional[str] = None
    if options.pcfax_queue:
        result = submit_to_queue(options.candidate, options.pcfax_queue, options.did)
        controller.telemetry_sink.emit(
            "pcfax.submission",
            queue=options.pcfax_queue,
            submitted=result.submitted,
            detail=result.detail,
        )
        pcfax_detail = result.detail

    snmp_snapshot: Optional[SNMPSnapshot] = None
    if options.snmp_target:
        oids = [oid for oid in options.snmp_oids if oid]
        snmp_snapshot = query_status(options.snmp_target, options.snmp_community, oids)
        controller.telemetry_sink.emit(
            "snmp.snapshot",
            target=options.snmp_target,
            community=options.snmp_community,
            values=snmp_snapshot.values,
            errors=snmp_snapshot.errors,
        )

    foip_result: Optional[FoipResult] = None
    if options.foip_config:
        try:
            validator = FoipValidator(options.foip_config)
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
    if options.ingest_dir:
        ingestor = SMBIngestor(
            Path(options.ingest_dir),
            pattern=options.ingest_pattern,
            interval=options.ingest_interval,
        )
        baseline = ingestor.snapshot()

    iteration_results = controller.run(
        IterationConfig(iterations=options.iterations, rng_seed=options.seed),
        reference=options.reference,
        candidate=options.candidate,
    )

    if ingestor is not None:
        artifacts = ingestor.detect_new(baseline, timeout=options.ingest_timeout)
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
        run_id=options.run_id,
        profile=profile,
        policy_name=options.policy,
        policy_hash=policy_hash,
        iterations=options.iterations,
        seed=options.seed,
        reference=options.reference,
        candidate=options.candidate,
        path_mode=options.path_mode,
        did=options.did,
        pcfax_queue=options.pcfax_queue,
        pcfax_detail=pcfax_detail,
        ingest_dir=options.ingest_dir,
        ingest_pattern=options.ingest_pattern if options.ingest_dir else None,
        snmp_snapshot=snmp_snapshot,
        foip_result=foip_result,
    )

    report_builder = ReportBuilder(options.output_dir)
    telemetry_events = list(controller.iter_events())
    run_dir, generated = _persist_reports(
        report_builder,
        options.run_id,
        context,
        iteration_results,
        telemetry_events,
        ingest_artifacts,
        snmp_snapshot,
        foip_result,
    )

    return RunResult(
        context=context,
        iterations=iteration_results,
        telemetry=telemetry_events,
        ingest_artifacts=ingest_artifacts,
        snmp_snapshot=snmp_snapshot,
        foip_result=foip_result,
        run_dir=run_dir,
        generated_files=generated,
    )


def _load_profile(config: ConfigService, profile_name: str) -> FaxProfile:
    loaded = config.load(f"profiles/{profile_name}.json")
    return FaxProfile.from_config(loaded.payload, loaded.sha256)


def _build_pipeline(
    config: ConfigService,
    policy_name: str,
    profile_hash: Optional[str],
    *,
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
    *,
    run_id: str,
    profile: FaxProfile,
    policy_name: str,
    policy_hash: str,
    iterations: int,
    seed: int,
    reference: Path,
    candidate: Path,
    path_mode: str,
    did: Optional[str],
    pcfax_queue: Optional[str],
    pcfax_detail: Optional[str],
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
) -> tuple[Path, Dict[str, Path]]:
    run_dir = report_builder.ensure_run_directory(run_id)
    generated: Dict[str, Path] = {}
    generated["summary_json"] = report_builder.write_json(
        run_dir,
        context,
        iterations,
        telemetry,
        ingest_artifacts,
        snmp_snapshot=snmp_snapshot,
        foip_result=foip_result,
    )
    generated["summary_csv"] = report_builder.write_csv(run_dir, context, iterations)
    generated["report_html"] = report_builder.write_html(run_dir, context, iterations)
    generated["run_log"] = report_builder.write_run_log(run_dir, context, iterations)
    reference_doc, candidate_doc = _first_verified_documents(iterations)
    if reference_doc and candidate_doc:
        generated["provenance_json"] = report_builder.write_provenance(
            run_dir,
            reference_doc,
            candidate_doc,
            ingest_artifacts,
            snmp_snapshot=snmp_snapshot,
            foip_result=foip_result,
        )
    telemetry_path = run_dir / "telemetry.json"
    telemetry_path.write_text(json.dumps(telemetry, indent=2))
    generated["telemetry_json"] = telemetry_path
    return run_dir, generated


def _first_verified_documents(iterations: Iterable[IterationResult]):
    for result in iterations:
        if result.verification:
            return result.verification.reference, result.verification.candidate
    return None, None

