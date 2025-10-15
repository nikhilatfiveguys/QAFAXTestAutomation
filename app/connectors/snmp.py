"""SNMP helpers for collecting printer counters and status."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List


@dataclass
class SNMPSnapshot:
    """Results returned from a snapshot of SNMP OIDs."""

    target: str
    community: str
    values: Dict[str, str]
    captured_at: datetime
    errors: List[str]

    def to_dict(self) -> Dict[str, object]:
        return {
            "target": self.target,
            "community": self.community,
            "capturedAt": self.captured_at.isoformat(),
            "values": dict(self.values),
            "errors": list(self.errors),
        }


class SNMPQueryError(RuntimeError):
    """Raised when a fatal SNMP error occurs."""


def query_status(
    target: str,
    community: str,
    oids: Iterable[str],
    *,
    port: int = 161,
    timeout: float = 2.0,
    retries: int = 1,
) -> SNMPSnapshot:
    """Query a set of OIDs and return a structured snapshot.

    The implementation prefers :mod:`pysnmp` when available and degrades to a
    best-effort stub that records missing-dependency errors when the library is
    not installed. This keeps the CLI runnable in minimal environments while
    still surfacing actionable diagnostics to operators.
    """

    values: Dict[str, str] = {}
    errors: List[str] = []

    try:
        from pysnmp.hlapi import (  # type: ignore
            CommunityData,
            ContextData,
            ObjectIdentity,
            ObjectType,
            SnmpEngine,
            UdpTransportTarget,
            getCmd,
        )
    except Exception as exc:  # pragma: no cover - executed in minimal envs
        errors.append(
            f"pysnmp not available ({exc}); install pysnmp to enable SNMP polling"
        )
        return SNMPSnapshot(
            target=target,
            community=community,
            values=values,
            captured_at=datetime.utcnow(),
            errors=errors,
        )

    engine = SnmpEngine()
    community_data = CommunityData(community, mpModel=1)
    transport = UdpTransportTarget((target, port), timeout=timeout, retries=retries)

    for oid in oids:
        iterator = getCmd(
            engine,
            community_data,
            transport,
            ContextData(),
            ObjectType(ObjectIdentity(oid)),
        )
        try:
            error_indication, error_status, error_index, var_binds = next(iterator)
        except StopIteration as exc:  # pragma: no cover - defensive guard
            raise SNMPQueryError(f"SNMP iterator exhausted for OID {oid}") from exc

        if error_indication:
            errors.append(f"{oid}: {error_indication}")
            continue
        if error_status:
            errors.append(
                f"{oid}: {error_status.prettyPrint()} at index {int(error_index)}"
            )
            continue
        for var_bind in var_binds:
            values[oid] = " = ".join(x.prettyPrint() for x in var_bind)

    return SNMPSnapshot(
        target=target,
        community=community,
        values=values,
        captured_at=datetime.utcnow(),
        errors=errors,
    )
