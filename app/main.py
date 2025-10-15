"""Command line entry point for the Fax QA Automation application."""
from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
from typing import List, Sequence

from .core.execution import DEFAULT_SNMP_OIDS, RunOptions, execute_run


def _parse_args(argv: List[str] | None) -> RunOptions:
    parser = ArgumentParser(description="Fax QA Automation")
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
    parser.add_argument(
        "--transport",
        choices=["sim", "t38", "modem"],
        default="sim",
        help="Transport path to use before verification",
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
        default=",".join(DEFAULT_SNMP_OIDS),
        help="Comma-separated list of SNMP OIDs to query",
    )
    parser.add_argument(
        "--foip-config",
        type=Path,
        default=None,
        help="Path to FoIP/T.38 validation configuration JSON",
    )
    parser.add_argument(
        "--t38-config",
        type=Path,
        default=None,
        help="Path to built-in T.38 transport configuration JSON",
    )
    parser.add_argument(
        "--modem-config",
        type=Path,
        default=None,
        help="Path to USB modem transport configuration JSON",
    )
    args = parser.parse_args(argv)

    snmp_oids: Sequence[str] = [oid.strip() for oid in args.snmp_oids.split(",") if oid.strip()]

    return RunOptions(
        reference=args.reference,
        candidate=args.candidate,
        profile=args.profile,
        policy=args.policy,
        iterations=args.iterations,
        seed=args.seed,
        output_dir=args.output,
        run_id=args.run_id,
        path_mode=args.path,
        transport=args.transport,
        did=args.did,
        pcfax_queue=args.pcfax_queue,
        ingest_dir=args.ingest_dir,
        ingest_pattern=args.ingest_pattern,
        ingest_timeout=args.ingest_timeout,
        ingest_interval=args.ingest_interval,
        require_ocr=args.require_ocr,
        require_barcode=args.require_barcode,
        snmp_target=args.snmp_target,
        snmp_community=args.snmp_community,
        snmp_oids=snmp_oids,
        foip_config=args.foip_config,
        t38_config=args.t38_config,
        modem_config=args.modem_config,
    )


def run(argv: List[str] | None = None) -> None:
    options = _parse_args(argv)
    result = execute_run(options)
    print(
        f"Run completed for profile {result.context.profile.name} with {len(result.iterations)} iteration(s). "
        f"Artifacts written to {result.run_dir}"
    )


if __name__ == "__main__":  # pragma: no cover
    run()
