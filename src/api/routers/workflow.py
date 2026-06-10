"""Workflow endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.models import WorkflowRunResponse, WorkflowStatusResponse
from src.api.services import get_workflow_status, start_workflow_job
from src.db.session import get_db


router = APIRouter(prefix="/workflow", tags=["workflow"])


@router.post("/run", response_model=WorkflowRunResponse, status_code=status.HTTP_202_ACCEPTED)
def run_workflow(session: Session = Depends(get_db)):
    record = start_workflow_job(session)
    return {
        "job_id": record["job_id"],
        "reminder_patients": record["reminder_patients"],
        "escalation_patients": record["escalation_patients"],
        "skipped_patients": record["skipped_patients"],
        "status": record["status"],
        "message": (
            f"Workflow started. {len(record['reminder_patients'])} reminders, "
            f"{len(record['escalation_patients'])} escalations, "
            f"{len(record['skipped_patients'])} skipped."
        ),
    }


@router.get("/status/{job_id}", response_model=WorkflowStatusResponse)
def workflow_status(job_id: str):
    try:
        return get_workflow_status(job_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

