"""LangGraph state definition for the patient follow-up workflow."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional
from typing_extensions import TypedDict


class PatientWorkflowState(TypedDict):
    # Patient identifiers and profile
    patient_id: str
    patient_name: str
    age: int
    email: str
    diagnosis: str
    follow_up_date: date
    doctor_notes: str
    attending_doctor: str
    severity: str
    followup_status: str

    # Set by patient_summary node
    patient_summary: Optional[str]
    summary: Optional[str]
    risk_score: Optional[float]

    # Routing decision set by router node
    route: str   # "reminder" | "escalation" | "skip"

    # Set by reminder node
    reminder_text: Optional[str]
    rag_context: Optional[str]
    email_status: Optional[str]

    # Set by escalation node
    escalation_report: Optional[str]
    escalation_status: Optional[str]

    # Error propagation
    error: Optional[str]
