"""LangGraph workflow graph — wires all agents into a stateful pipeline."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any

from langgraph.graph import END, START, StateGraph

from src.agents.escalation import escalation_agent
from src.agents.patient_summary import generate_patient_summary
from src.agents.reminder import generate_reminder
from src.agents.router import REMINDER_WINDOWS, route_patient, router_node
from src.agents.state import PatientWorkflowState
from src.db.session import SessionLocal
from src.db.models import Patient, Reminder
from src.email.ses import send_email
from src.rag.pipeline import get_rag_context

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.utcnow().replace(microsecond=0)


def _patient_summary_node(state: PatientWorkflowState) -> PatientWorkflowState:
    patient_id = state["patient_id"]
    try:
        patient_data = {
            "profile": {
                "patient_id": patient_id,
                "patient_name": state["patient_name"],
                "age": state["age"],
                "diagnosis": state["diagnosis"],
                "doctor_notes": state.get("doctor_notes", ""),
                "follow_up_date": state["follow_up_date"],
                "attending_doctor": state["attending_doctor"],
                "severity": state["severity"],
            }
        }
        rag_context = get_rag_context(state["diagnosis"])
        summary, risk_score = generate_patient_summary(patient_data, rag_context)

        with SessionLocal() as db:
            patient = db.get(Patient, patient_id)
            if patient:
                patient.patient_summary = summary
                patient.risk_score = risk_score
                patient.updated_at = _now()
                db.commit()

        return {**state, "patient_summary": summary, "summary": summary, "risk_score": risk_score}

    except Exception as exc:
        logger.error(f"Patient summary node failed for {patient_id}: {exc}", exc_info=True)
        return {**state, "error": str(exc)}


def _reminder_node(state: PatientWorkflowState) -> PatientWorkflowState:
    patient_id = state["patient_id"]

    # Duplicate check — skip if a reminder was already sent today
    with SessionLocal() as db:
        from sqlalchemy import desc, select
        existing = (
            db.execute(
                select(Reminder)
                .where(Reminder.patient_id == patient_id)
                .order_by(desc(Reminder.created_at), desc(Reminder.reminder_id))
            )
            .scalars()
            .first()
        )
        if existing:
            try:
                sent_dates = json.loads(existing.reminder_sent_dates or "[]")
            except json.JSONDecodeError:
                sent_dates = []
            if str(date.today()) in sent_dates:
                logger.info(f"Duplicate reminder for {patient_id}, skipping.")
                return {**state, "email_status": "skipped_duplicate"}

    try:
        patient_data = {
            "profile": {
                "patient_id": patient_id,
                "patient_name": state["patient_name"],
                "diagnosis": state["diagnosis"],
                "follow_up_date": state["follow_up_date"],
                "attending_doctor": state["attending_doctor"],
            }
        }
        rag_context = get_rag_context(state["diagnosis"])
        summary = state.get("summary") or state.get("patient_summary") or ""
        reminder_payload = generate_reminder(patient_data, summary=summary, rag_context=rag_context)

        # Build sent_dates list
        sent_dates = []
        with SessionLocal() as db:
            from sqlalchemy import desc, select
            prev = (
                db.execute(
                    select(Reminder)
                    .where(Reminder.patient_id == patient_id)
                    .order_by(desc(Reminder.created_at))
                )
                .scalars()
                .first()
            )
            if prev:
                try:
                    sent_dates = json.loads(prev.reminder_sent_dates or "[]")
                except json.JSONDecodeError:
                    sent_dates = []
        sent_dates.append(str(date.today()))

        # Insert reminder row
        with SessionLocal() as db:
            reminder = Reminder(
                patient_id=patient_id,
                reminder_text=reminder_payload["reminder_text"],
                rag_context_json=json.dumps(reminder_payload["rag_context_json"]),
                reminder_sent_dates=json.dumps(sent_dates),
                email_status="not_sent",
                is_active=True,
                created_at=_now(),
                updated_at=_now(),
            )
            db.add(reminder)
            db.flush()

            # Send email
            result = send_email(
                to_email=state["email"],
                subject=reminder_payload["email_subject"],
                html_body=f"<pre>{reminder_payload['reminder_text']}</pre>",
                text_body=reminder_payload["reminder_text"],
            )
            reminder.email_status = "sent" if result.sent else "failed"
            reminder.email_sent_at = _now() if result.sent else None
            reminder.updated_at = _now()
            db.commit()

        return {
            **state,
            "reminder_text": reminder_payload["reminder_text"],
            "rag_context": rag_context,
            "email_status": reminder.email_status,
        }

    except Exception as exc:
        logger.error(f"Reminder node failed for {patient_id}: {exc}", exc_info=True)
        return {**state, "email_status": "failed", "error": str(exc)}


def _escalation_node(state: PatientWorkflowState) -> PatientWorkflowState:
    try:
        result = escalation_agent(state)
        return {
            **state,
            "escalation_report": result.get("escalation_report", ""),
            "escalation_status": result.get("escalation_status", "pending"),
            "error": result.get("error") or state.get("error"),
        }
    except Exception as exc:
        logger.error(f"Escalation node failed for {state['patient_id']}: {exc}", exc_info=True)
        return {**state, "escalation_report": None, "escalation_status": "error", "error": str(exc)}


def build_workflow() -> Any:
    graph = StateGraph(PatientWorkflowState)

    graph.add_node("router", router_node)
    graph.add_node("patient_summary", _patient_summary_node)
    graph.add_node("reminder", _reminder_node)
    graph.add_node("escalation", _escalation_node)

    graph.add_node("patient_summary_escalation", _patient_summary_node)

    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router",
        route_patient,
        {
            "reminder": "patient_summary",
            "escalation": "patient_summary_escalation",
            "skip": END,
        },
    )
    graph.add_edge("patient_summary", "reminder")
    graph.add_edge("reminder", END)
    graph.add_edge("patient_summary_escalation", "escalation")
    graph.add_edge("escalation", END)

    return graph.compile()


workflow_graph = build_workflow()
