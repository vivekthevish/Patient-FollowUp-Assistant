"""Patient endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.api.models import (
    ErrorResponse,
    OutcomeUpdateResponse,
    PatientCreate,
    PatientCreateResponse,
    PatientDetailResponse,
    PatientsListResponse,
    PatientOutcomeUpdate,
)
from src.api.services import create_patient, get_patient_detail, list_patients, update_patient_outcome
from src.db.session import get_db


router = APIRouter(prefix="/patients", tags=["patients"])


@router.post("", response_model=PatientCreateResponse, status_code=status.HTTP_201_CREATED)
def register_patient(payload: PatientCreate, session: Session = Depends(get_db)):
    try:
        return create_patient(session, payload)
    except ValueError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc), "error_code": "DUPLICATE_EMAIL"},
        )


@router.get("", response_model=PatientsListResponse)
def fetch_patients(
    followup_status: str = Query("all", pattern="^(pending|completed|all)$"),
    severity: str | None = Query(default=None, pattern="^(Critical|High|Moderate|Low)$"),
    search: str | None = Query(default=None),
    session: Session = Depends(get_db),
):
    patients = list_patients(session, followup_status=followup_status, severity=severity, search=search)
    return {"patients": patients, "total": len(patients)}


@router.get("/{patient_id}", response_model=PatientDetailResponse)
def fetch_patient(patient_id: str, session: Session = Depends(get_db)):
    try:
        return {"patient": get_patient_detail(session, patient_id)}
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/{patient_id}/outcome", response_model=OutcomeUpdateResponse)
def patch_outcome(patient_id: str, payload: PatientOutcomeUpdate, session: Session = Depends(get_db)):
    try:
        return update_patient_outcome(session, patient_id, payload.followup_status)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
