"""Security audit log and SIEM export router for Avinya HMS.

Provides structured, queryable access and NDJSON streaming for security events,
access decisions, emergency overrides, data breaches, and retention operations.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, AsyncGenerator, Generator, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, HttpUrl
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.dependencies import RequirePermission
from backend.domains.identity.models import User
from backend.domains.audit.models import SecurityAuditExportRegister
from backend.domains.patients.models import BreakGlassGrant
from backend.domains.privacy.models import (
    PatientDataRightsRequest,
    PrivacyDataBreachIncident,
    PrivacyDecisionAudit,
    PrivacyRetentionRunLedger,
)

router = APIRouter(prefix="/api/audit", tags=["Security & SIEM Audit Export"])


class SiemEvent(BaseModel):
    event_id: str
    timestamp: datetime
    category: str
    severity: str
    action: str
    actor_user_id: Optional[int] = None
    target_patient_id: Optional[int] = None
    details: dict[str, Any]


class SiemExportResponse(BaseModel):
    total_events: int
    limit: int
    offset: int
    events: List[SiemEvent]


class SiemWebhookTestRequest(BaseModel):
    webhook_url: str
    auth_header: Optional[str] = None


AUDIT_EVENT_CATEGORIES = frozenset({
    "PRIVACY_CONSENT",
    "BREAK_GLASS",
    "DATA_BREACH",
    "RETENTION_PURGE",
})
AUDIT_EVENT_SEVERITIES = frozenset({"INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"})


def _validate_event_filters(
    from_time: Optional[datetime],
    to_time: Optional[datetime],
    category: Optional[str],
    severity: Optional[str] = None,
) -> tuple[Optional[str], Optional[str]]:
    if from_time and to_time and from_time > to_time:
        raise HTTPException(status_code=400, detail="from_time must not be later than to_time.")
    normalized_category = category.strip().upper() if category is not None else None
    normalized_severity = severity.strip().upper() if severity is not None else None
    if category is not None and not normalized_category:
        raise HTTPException(status_code=400, detail="Category filter must not be blank.")
    if severity is not None and not normalized_severity:
        raise HTTPException(status_code=400, detail="Severity filter must not be blank.")
    if normalized_category and normalized_category not in AUDIT_EVENT_CATEGORIES:
        raise HTTPException(status_code=400, detail="Unsupported security event category.")
    if normalized_severity and normalized_severity not in AUDIT_EVENT_SEVERITIES:
        raise HTTPException(status_code=400, detail="Unsupported security event severity.")
    return normalized_category, normalized_severity


def _collect_security_events(
    db: Session,
    *,
    from_time: Optional[datetime] = None,
    to_time: Optional[datetime] = None,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[int, list[SiemEvent]]:
    """Gathers and normalizes events across multiple security & governance ledgers."""
    events: list[SiemEvent] = []
    fetch_limit = limit + offset
    total = 0

    def count_rows(model, timestamp_column, extra_conditions=()):
        statement = select(func.count()).select_from(model)
        if from_time:
            statement = statement.where(timestamp_column >= from_time)
        if to_time:
            statement = statement.where(timestamp_column <= to_time)
        for condition in extra_conditions:
            statement = statement.where(condition)
        return int(db.execute(statement).scalar() or 0)

    # 1. Privacy Decision Audits
    if not category or category.upper() == "PRIVACY_CONSENT":
        privacy_conditions = []
        if severity:
            requested_severity = severity.upper()
            severity_results = {
                "MEDIUM": ("WOULD_DENY",),
                "HIGH": ("DENY",),
                "CRITICAL": ("BYPASS_ALLOWED", "EMERGENCY_OVERRIDE"),
            }
            if requested_severity == "INFO":
                privacy_conditions.append(
                    PrivacyDecisionAudit.result.notin_(
                        ("WOULD_DENY", "DENY", "BYPASS_ALLOWED", "EMERGENCY_OVERRIDE")
                    )
                )
            else:
                matching_results = severity_results.get(requested_severity, ())
                privacy_conditions.append(
                    PrivacyDecisionAudit.result.in_(matching_results)
                    if matching_results else PrivacyDecisionAudit.result == "__NO_MATCH__"
                )
        total += count_rows(
            PrivacyDecisionAudit, PrivacyDecisionAudit.occurred_at, privacy_conditions
        )
        q = select(PrivacyDecisionAudit)
        if privacy_conditions:
            q = q.where(*privacy_conditions)
        if from_time:
            q = q.where(PrivacyDecisionAudit.occurred_at >= from_time)
        if to_time:
            q = q.where(PrivacyDecisionAudit.occurred_at <= to_time)
        p_audits = db.execute(q.order_by(desc(PrivacyDecisionAudit.id)).limit(fetch_limit)).scalars().all()

        for pa in p_audits:
            sev = "INFO"
            if pa.result == "WOULD_DENY":
                sev = "MEDIUM"
            elif pa.result == "DENY":
                sev = "HIGH"
            elif pa.result in ("BYPASS_ALLOWED", "EMERGENCY_OVERRIDE"):
                sev = "CRITICAL"

            if not severity or severity.upper() == sev:
                events.append(
                    SiemEvent(
                        event_id=f"AUDIT-PRIV-{pa.id}",
                        timestamp=pa.occurred_at if pa.occurred_at.tzinfo else pa.occurred_at.replace(tzinfo=timezone.utc),
                        category="PRIVACY_CONSENT",
                        severity=sev,
                        action=f"DATA_USE_{pa.result}",
                        actor_user_id=pa.actor_user_id,
                        details={
                            "data_use_point": pa.data_use_point,
                            "mode": pa.mode,
                            "reason_code": pa.reason_code,
                            "purpose_code": pa.purpose_code,
                            "policy_revision_id": pa.policy_revision_id,
                        },
                    )
                )

    # 2. Break-Glass Emergency Overrides
    if not category or category.upper() == "BREAK_GLASS":
        if not severity or severity.upper() == "CRITICAL":
            total += count_rows(BreakGlassGrant, BreakGlassGrant.created_at)
        q_bg = select(BreakGlassGrant)
        if from_time:
            q_bg = q_bg.where(BreakGlassGrant.created_at >= from_time)
        if to_time:
            q_bg = q_bg.where(BreakGlassGrant.created_at <= to_time)
        bg_records = db.execute(q_bg.order_by(desc(BreakGlassGrant.id)).limit(fetch_limit)).scalars().all()

        for bg in bg_records:
            sev = "CRITICAL"
            if not severity or severity.upper() == sev:
                events.append(
                    SiemEvent(
                        event_id=f"AUDIT-BG-{bg.id}",
                        timestamp=bg.created_at if bg.created_at.tzinfo else bg.created_at.replace(tzinfo=timezone.utc),
                        category="BREAK_GLASS",
                        severity=sev,
                        action="EMERGENCY_OVERRIDE_ACTIVATED",
                        actor_user_id=bg.user_id,
                        target_patient_id=bg.patient_id,
                        details={
                            "reason": bg.reason,
                            "expires_at": bg.expires_at.isoformat() if bg.expires_at else None,
                            "review_outcome": bg.review_outcome,
                        },
                    )
                )

    # 3. Personal Data Breach Incidents
    if not category or category.upper() == "DATA_BREACH":
        breach_conditions = []
        if severity:
            breach_conditions.append(func.upper(PrivacyDataBreachIncident.severity) == severity.upper())
        total += count_rows(
            PrivacyDataBreachIncident, PrivacyDataBreachIncident.created_at, breach_conditions
        )
        q_br = select(PrivacyDataBreachIncident)
        if breach_conditions:
            q_br = q_br.where(*breach_conditions)
        if from_time:
            q_br = q_br.where(PrivacyDataBreachIncident.created_at >= from_time)
        if to_time:
            q_br = q_br.where(PrivacyDataBreachIncident.created_at <= to_time)
        breaches = db.execute(q_br.order_by(desc(PrivacyDataBreachIncident.id)).limit(fetch_limit)).scalars().all()

        for br in breaches:
            sev = br.severity.value if hasattr(br.severity, "value") else str(br.severity)
            if not severity or severity.upper() == sev.upper():
                events.append(
                    SiemEvent(
                        event_id=f"AUDIT-BREACH-{br.id}",
                        timestamp=br.created_at if br.created_at.tzinfo else br.created_at.replace(tzinfo=timezone.utc),
                        category="DATA_BREACH",
                        severity=sev.upper(),
                        action=f"BREACH_{br.status.value if hasattr(br.status, 'value') else str(br.status)}",
                        actor_user_id=br.reported_by_user_id,
                        details={
                            "incident_code": br.incident_code,
                            "title": br.title,
                            "affected_records_count": br.estimated_affected_subjects,
                            "certin_reported": br.reported_to_authority_at is not None,
                        },
                    )
                )

    # 4. Retention Purges
    if not category or category.upper() == "RETENTION_PURGE":
        retention_conditions = []
        if severity:
            if severity.upper() == "INFO":
                retention_conditions.append(PrivacyRetentionRunLedger.dry_run.is_(True))
            elif severity.upper() == "MEDIUM":
                retention_conditions.append(PrivacyRetentionRunLedger.dry_run.is_(False))
            else:
                retention_conditions.append(PrivacyRetentionRunLedger.dry_run.is_(None))
        total += count_rows(
            PrivacyRetentionRunLedger, PrivacyRetentionRunLedger.executed_at, retention_conditions
        )
        q_ret = select(PrivacyRetentionRunLedger)
        if retention_conditions:
            q_ret = q_ret.where(*retention_conditions)
        if from_time:
            q_ret = q_ret.where(PrivacyRetentionRunLedger.executed_at >= from_time)
        if to_time:
            q_ret = q_ret.where(PrivacyRetentionRunLedger.executed_at <= to_time)
        runs = db.execute(q_ret.order_by(desc(PrivacyRetentionRunLedger.id)).limit(fetch_limit)).scalars().all()

        for ret in runs:
            sev = "INFO" if ret.dry_run else "MEDIUM"
            if not severity or severity.upper() == sev:
                events.append(
                    SiemEvent(
                        event_id=f"AUDIT-RET-{ret.id}",
                        timestamp=ret.executed_at if ret.executed_at.tzinfo else ret.executed_at.replace(tzinfo=timezone.utc),
                        category="RETENTION_PURGE",
                        severity=sev,
                        action="RETENTION_DRY_RUN" if ret.dry_run else "RETENTION_EXECUTED",
                        actor_user_id=ret.executed_by_user_id,
                        details={
                            "action": ret.action,
                            "dry_run": ret.dry_run,
                            "categories": ret.categories,
                            "affected_count": ret.affected_count,
                            "held_count": ret.held_count,
                            "approval_reference": ret.approval_reference,
                        },
                    )
                )

    # Stable tie-breakers prevent records with identical timestamps moving between pages.
    events.sort(key=lambda e: (e.timestamp, e.category, e.event_id), reverse=True)
    paginated = events[offset : offset + limit]
    return total, paginated


@router.get(
    "/security-events",
    response_model=SiemExportResponse,
    summary="Query security audit events for SIEM/SOC review",
)
def get_security_events(
    from_time: Optional[datetime] = None,
    to_time: Optional[datetime] = None,
    category: Optional[str] = Query(None, description="Event category: PRIVACY_CONSENT, BREAK_GLASS, DATA_BREACH, RETENTION_PURGE"),
    severity: Optional[str] = Query(None, description="Severity: INFO, LOW, MEDIUM, HIGH, CRITICAL"),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0, le=10000),
    db: Session = Depends(get_db),
    actor: User = Depends(RequirePermission("privacy:read")),
):
    """Returns normalized security audit logs formatted for SOC/SIEM inspection."""
    category, severity = _validate_event_filters(from_time, to_time, category, severity)
    total, events = _collect_security_events(
        db,
        from_time=from_time,
        to_time=to_time,
        category=category,
        severity=severity,
        limit=limit,
        offset=offset,
    )
    return SiemExportResponse(
        total_events=total,
        limit=limit,
        offset=offset,
        events=events,
    )


@router.get(
    "/stream",
    summary="Stream security events as NDJSON for SIEM collectors (Splunk, Elastic, Wazuh)",
)
def stream_security_events(
    from_time: Optional[datetime] = None,
    to_time: Optional[datetime] = None,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = Query(1000, ge=1, le=10000),
    db: Session = Depends(get_db),
    actor: User = Depends(RequirePermission("privacy:read")),
):
    """Streams newline-delimited JSON (NDJSON) security logs for automated SIEM log shippers."""
    category, severity = _validate_event_filters(from_time, to_time, category, severity)

    _, events = _collect_security_events(
        db,
        from_time=from_time,
        to_time=to_time,
        category=category,
        severity=severity,
        limit=limit,
        offset=0,
    )

    # Materialize once so the persisted digest is for the exact bytes returned.
    payload = "".join(event.model_dump_json() + "\n" for event in events).encode("utf-8")
    def utc_iso(value: Optional[datetime]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
        return normalized.isoformat()

    criteria = {
        "from_time": utc_iso(from_time),
        "to_time": utc_iso(to_time),
        "category": category.strip().upper() if category else None,
        "severity": severity.strip().upper() if severity else None,
        "limit": limit,
    }
    criteria_json = json.dumps(criteria, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    record = SecurityAuditExportRegister(
        exported_at=datetime.now(timezone.utc),
        actor_user_id=actor.id,
        schema_version=1,
        category=criteria["category"],
        severity=criteria["severity"],
        from_time=from_time,
        to_time=to_time,
        event_count=len(events),
        byte_count=len(payload),
        criteria_json=criteria_json,
        payload_sha256=hashlib.sha256(payload).hexdigest(),
    )
    try:
        db.add(record)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Audit export could not be registered; export was not delivered.",
        ) from exc

    return Response(
        content=payload,
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": "attachment; filename=security-audit-events.ndjson",
            "X-Audit-Export-Id": str(record.id),
        },
    )


@router.get("/exports", summary="List security audit export register entries")
def list_security_audit_exports(
    before_id: Optional[int] = Query(None, ge=1),
    from_time: Optional[datetime] = None,
    to_time: Optional[datetime] = None,
    actor_user_id: Optional[int] = Query(None, ge=1),
    category: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    actor: User = Depends(RequirePermission("privacy:read")),
):
    category, _ = _validate_event_filters(from_time, to_time, category)
    stmt = select(SecurityAuditExportRegister)
    if before_id is not None:
        stmt = stmt.where(SecurityAuditExportRegister.id < before_id)
    if from_time:
        stmt = stmt.where(SecurityAuditExportRegister.exported_at >= from_time)
    if to_time:
        stmt = stmt.where(SecurityAuditExportRegister.exported_at <= to_time)
    if actor_user_id is not None:
        stmt = stmt.where(SecurityAuditExportRegister.actor_user_id == actor_user_id)
    if category:
        stmt = stmt.where(SecurityAuditExportRegister.category == category.strip().upper())
    rows = db.execute(
        stmt.order_by(desc(SecurityAuditExportRegister.id)).limit(limit)
    ).scalars().all()
    return {
        "items": [
            {
                "id": row.id,
                "exported_at": row.exported_at,
                "actor_user_id": row.actor_user_id,
                "schema_version": row.schema_version,
                "category": row.category,
                "severity": row.severity,
                "from_time": row.from_time,
                "to_time": row.to_time,
                "event_count": row.event_count,
                "byte_count": row.byte_count,
                "payload_sha256": row.payload_sha256,
            }
            for row in rows
        ],
        "limit": limit,
        "next_before_id": rows[-1].id if len(rows) == limit else None,
    }


@router.get("/exports/{export_id}", summary="Read security audit export register metadata")
def get_security_audit_export(
    export_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(RequirePermission("privacy:read")),
):
    row = db.get(SecurityAuditExportRegister, export_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Audit export register entry not found.")
    return {
        "id": row.id,
        "exported_at": row.exported_at,
        "actor_user_id": row.actor_user_id,
        "schema_version": row.schema_version,
        "category": row.category,
        "severity": row.severity,
        "from_time": row.from_time,
        "to_time": row.to_time,
        "event_count": row.event_count,
        "byte_count": row.byte_count,
        "criteria": json.loads(row.criteria_json),
        "payload_sha256": row.payload_sha256,
    }


@router.post(
    "/siem/webhook-test",
    summary="Test connectivity to configured SIEM forwarder or webhook",
)
def test_siem_webhook_connectivity(
    payload: SiemWebhookTestRequest,
    actor: User = Depends(RequirePermission("system:admin")),
):
    """Validates external SIEM ingestion pipeline connectivity with SSRF guards."""
    import ipaddress
    import socket
    from urllib.parse import urlparse
    import httpx

    parsed = urlparse(payload.webhook_url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook URL scheme. Only http/https supported.",
        )
    if not parsed.hostname:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook URL: missing hostname.",
        )

    # SSRF Guard: Disallow loopback, private, link-local, and cloud-metadata addresses
    hostname = parsed.hostname.strip().lower()
    if hostname in ("localhost", "127.0.0.1", "::1", "169.254.169.254", "metadata.google.internal"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SSRF Protection: Webhook destination resolves to a restricted loopback or internal address.",
        )

    try:
        addr_info = socket.getaddrinfo(hostname, None)
        for _, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            try:
                ip_obj = ipaddress.ip_address(ip_str)
                cgnat = ipaddress.ip_network("100.64.0.0/10")
                if (
                    not ip_obj.is_global
                    or ip_obj in cgnat
                    or ip_obj.is_private
                    or ip_obj.is_loopback
                    or ip_obj.is_link_local
                    or ip_obj.is_multicast
                    or ip_obj.is_reserved
                ):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="SSRF Protection: Webhook destination resolves to a restricted internal or link-local address.",
                    )
            except ValueError:
                pass
    except socket.gaierror:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot resolve webhook host '{hostname}'.",
        )

    test_payload = {
        "event": "SIEM_CONNECTIVITY_PROBE",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "Avinya HMS",
        "actor": actor.email,
        "status": "HEALTHY",
    }
    headers = {"Content-Type": "application/json"}
    if payload.auth_header:
        headers["Authorization"] = payload.auth_header

    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(payload.webhook_url, json=test_payload, headers=headers)
            return {
                "success": resp.is_success,
                "status_code": resp.status_code,
                "message": "Probe delivered successfully." if resp.is_success else "External SIEM returned error status.",
            }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"SIEM webhook probe failed: {exc}",
        ) from exc

