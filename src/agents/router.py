"""Router node — classifies each patient into reminder / escalation / skip."""

from __future__ import annotations

from datetime import date

from src.agents.state import PatientWorkflowState

REMINDER_WINDOWS = {7, 3, 1}


def classify_patient(
    follow_up_date: date,
    current_date: date,
    followup_status: str = "pending",
) -> str:
    """Return the workflow path for this patient."""
    if followup_status == "completed":
        return "skip"
    days_until = (follow_up_date - current_date).days
    if days_until < 0:
        return "escalation"
    if days_until in REMINDER_WINDOWS:
        return "reminder"
    return "skip"


def router_node(state: PatientWorkflowState) -> PatientWorkflowState:
    follow_up_date = state["follow_up_date"]
    if isinstance(follow_up_date, str):
        follow_up_date = date.fromisoformat(follow_up_date)
    route = classify_patient(
        follow_up_date,
        date.today(),
        state.get("followup_status", "pending"),
    )
    return {**state, "route": route}


def route_patient(state: PatientWorkflowState) -> str:
    """Conditional edge function — returns the next node name."""
    return state["route"]
