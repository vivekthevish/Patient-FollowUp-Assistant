"""Pydantic schemas for the FastAPI API."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


Severity = Literal["Critical", "High", "Moderate", "Low"]
FollowupStatus = Literal["pending", "completed", "all"]
EscalationStatus = Literal["pending", "closed", "all"]


class PatientCreate(BaseModel):
    patient_name: str = Field(..., min_length=2)
    age: int = Field(..., ge=18, le=85)
    gender: Literal["Male", "Female", "Other"]
    email: EmailStr
    phone: Optional[str] = None
    diagnosis: str
    follow_up_date: date
    doctor_notes: str = Field(..., min_length=10)
    attending_doctor: str
    severity: Severity


class PatientOutcomeUpdate(BaseModel):
    followup_status: Literal["completed", "pending"]
    updated_by: str


class EscalationClose(BaseModel):
    closed_by: str


class ReminderSummary(BaseModel):
    reminder_id: int
    reminder_text: str
    rag_context_json: Optional[str] = None
    reminder_sent_dates: str
    email_status: str
    email_sent_at: Optional[datetime] = None


class PatientQueueItem(BaseModel):
    patient_id: str
    patient_name: str
    diagnosis: str
    severity: Severity
    follow_up_date: date
    patient_summary: Optional[str] = None
    risk_score: Optional[float] = None
    followup_status: str
    reminder: Optional[ReminderSummary] = None


class PatientDetail(PatientQueueItem):
    email: EmailStr
    phone: Optional[str] = None
    doctor_notes: str
    attending_doctor: str
    created_at: datetime
    updated_at: datetime


class PatientCreateResponse(BaseModel):
    patient_id: str
    patient_name: str
    follow_up_date: date
    message: str
    created_at: datetime


class PatientsListResponse(BaseModel):
    patients: list[PatientQueueItem]
    total: int


class PatientDetailResponse(BaseModel):
    patient: PatientDetail


class OutcomeUpdateResponse(BaseModel):
    patient_id: str
    followup_status: str
    message: str
    updated_at: datetime


class WorkflowRunResponse(BaseModel):
    job_id: str
    reminder_patients: list[str]
    escalation_patients: list[str]
    skipped_patients: list[str]
    status: str
    message: str


class WorkflowResultItem(BaseModel):
    patient_id: str
    path: Literal["reminder", "escalation"]
    status: str
    email_status: Optional[str] = None
    error: Optional[str] = None


class WorkflowStatusResponse(BaseModel):
    job_id: str
    status: str
    results: list[WorkflowResultItem] = Field(default_factory=list)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class EscalationItem(BaseModel):
    escalation_id: int
    patient_id: str
    patient_name: str
    diagnosis: str
    follow_up_date: date
    escalation_report: str
    escalation_status: str
    created_at: datetime
    closed_at: Optional[datetime] = None


class EscalationsListResponse(BaseModel):
    escalations: list[EscalationItem]
    total: int


class EscalationCloseResponse(BaseModel):
    escalation_id: int
    patient_id: str
    escalation_status: str
    closed_at: datetime
    message: str


class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None


class WorkflowJobRecord(BaseModel):
    job_id: str
    status: str
    reminder_patients: list[str]
    escalation_patients: list[str]
    skipped_patients: list[str]
    results: list[WorkflowResultItem] = Field(default_factory=list)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)
