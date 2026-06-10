"""Escalation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.api.models import EscalationClose, EscalationCloseResponse, EscalationsListResponse
from src.api.services import close_escalation, list_escalations
from src.db.session import get_db


router = APIRouter(prefix="/escalations", tags=["escalations"])


@router.get("", response_model=EscalationsListResponse)
def fetch_escalations(
    status_filter: str = Query("pending", alias="status", pattern="^(pending|closed|all)$"),
    session: Session = Depends(get_db),
):
    escalations = list_escalations(session, status=status_filter)
    return {"escalations": escalations, "total": len(escalations)}


@router.patch("/{escalation_id}/close", response_model=EscalationCloseResponse)
def mark_escalation_closed(
    escalation_id: int,
    payload: EscalationClose,
    session: Session = Depends(get_db),
):
    try:
        return close_escalation(session, escalation_id, payload.closed_by)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

