"""NETDEFY — SOC Alert Query & Analyst Workflow Endpoints (Phase 6)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from netdefy.api.dependencies import get_db_session, verify_api_key
from netdefy.api.schemas import (
    AlertDetailResponse,
    AlertListResponse,
    AlertPatchRequest,
)
from netdefy.storage.alert_repository import AlertRepository

router = APIRouter(prefix="/alerts", tags=["SOC Alerts"])


@router.get("", response_model=AlertListResponse)
def list_alerts(
    status_filter: str | None = Query(default=None, alias="status"),
    severity_filter: str | None = Query(default=None, alias="severity"),
    destination_port: int | None = Query(default=None, alias="port"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db_session),
) -> AlertListResponse:
    """List SOC security alerts with severity, status, and port filtering."""
    repo = AlertRepository(session=db)
    records, total = repo.list_alerts(
        status=status_filter,
        severity=severity_filter,
        destination_port=destination_port,
        limit=limit,
        offset=offset,
    )

    return AlertListResponse(
        total_count=total,
        limit=limit,
        offset=offset,
        alerts=[r.to_dict() for r in records],
    )


@router.get("/{alert_id}", response_model=AlertDetailResponse)
def get_alert_detail(
    alert_id: str,
    db: Session = Depends(get_db_session),
) -> AlertDetailResponse:
    """Retrieve detailed alert context, model scores, and analyst audit trail."""
    repo = AlertRepository(session=db)
    record = repo.get_alert(alert_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with ID '{alert_id}' not found",
        )

    audit_records = repo.get_audit_trail(alert_id)
    alert_data = record.to_dict()
    alert_data["audit_history"] = [a.to_dict() for a in audit_records]

    return AlertDetailResponse(**alert_data)


@router.patch("/{alert_id}", response_model=AlertDetailResponse)
def update_alert_status(
    alert_id: str,
    patch_req: AlertPatchRequest,
    db: Session = Depends(get_db_session),
    _analyst_auth: str = Depends(verify_api_key),
) -> AlertDetailResponse:
    """Transition alert workflow status (e.g. ACKNOWLEDGED, RESOLVED, FALSE_POSITIVE)."""
    repo = AlertRepository(session=db)
    record = repo.update_status(
        alert_id=alert_id,
        new_status=patch_req.status,
        analyst_id=patch_req.analyst_id,
        notes=patch_req.notes,
    )
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with ID '{alert_id}' not found",
        )

    db.commit()
    audit_records = repo.get_audit_trail(alert_id)
    alert_data = record.to_dict()
    alert_data["audit_history"] = [a.to_dict() for a in audit_records]

    return AlertDetailResponse(**alert_data)
