"""Escalation agent for missed follow-up patients."""

from __future__ import annotations

import logging
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping, Optional

from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from src.agents.gemini import gemini_enabled, generate_structured_response


logger = logging.getLogger(__name__)


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    return value if value is not None and value != "" else default


MAX_RETRIES = int(_env("MAX_RETRIES", "3"))
RETRY_DELAY = float(_env("RETRY_DELAY", "1"))
DATABASE_URL = _env("DATABASE_URL", "sqlite:///data/db/app.db")


class _EscalationResponse(BaseModel):
    clinical_brief: str
    missed_follow_up_reason: str
    immediate_actions: list[str]
    recommended_next_steps: list[str]
    urgency_timeline: str


def _database_path(database_url: str) -> Path:
    if database_url.startswith("sqlite:///"):
        return Path(database_url.removeprefix("sqlite:///"))
    if database_url.startswith("sqlite://"):
        return Path(database_url.removeprefix("sqlite://"))
    return Path(database_url)


def _connect(database_url: str = DATABASE_URL) -> sqlite3.Connection:
    database_path = _database_path(database_url)
    if not database_path.exists():
        raise FileNotFoundError(
            f"Database file not found at {database_path}. "
            "Create the SQLite database before running the escalation agent."
        )
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    return connection


def _extract_patient_context(patient_data: Mapping[str, Any]) -> dict[str, Any]:
    profile = patient_data.get("profile") if isinstance(patient_data.get("profile"), Mapping) else patient_data

    follow_up_date = profile.get("follow_up_date") or profile.get("followup_date")
    if hasattr(follow_up_date, "isoformat"):
        follow_up_date = follow_up_date.isoformat()

    return {
        "patient_id": profile.get("patient_id", ""),
        "patient_name": profile.get("patient_name") or profile.get("name", ""),
        "diagnosis": profile.get("diagnosis", ""),
        "doctor_notes": profile.get("doctor_notes", ""),
        "follow_up_date": follow_up_date or "",
        "patient_summary": profile.get("patient_summary") or patient_data.get("summary", ""),
        "risk_score": profile.get("risk_score"),
    }


def _parse_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    if value is None:
        return date.today()
    return date.fromisoformat(str(value))


def _fallback_report(context: dict[str, Any], current_date: date) -> dict[str, Any]:
    follow_up_date = _parse_date(context.get("follow_up_date"))
    days_overdue = max((current_date - follow_up_date).days, 0)
    urgency = "within 24 hours" if days_overdue <= 3 else "immediately"

    return {
        "clinical_brief": (
            f"{context['patient_name'] or 'The patient'} missed a scheduled follow-up on "
            f"{follow_up_date.isoformat()}. The follow-up is now {days_overdue} day(s) overdue."
        ),
        "missed_follow_up_reason": (
            "Follow-up date has passed and the patient has not been processed through the reminder path."
        ),
        "immediate_actions": [
            "Review the patient's chart and recent clinical notes.",
            "Contact the patient or care team to confirm current status.",
            "Arrange an urgent clinical review if symptoms have worsened.",
        ],
        "recommended_next_steps": [
            "Document outreach attempts in the care record.",
            "Schedule the next available follow-up slot.",
            "Escalate to the attending physician if there are red-flag symptoms.",
        ],
        "urgency_timeline": urgency,
    }


def _format_report(report: Mapping[str, Any], context: dict[str, Any], current_date: date) -> str:
    follow_up_date = _parse_date(context.get("follow_up_date"))
    parts = [
        "ESCALATION REPORT",
        f"Patient: {context.get('patient_name', 'N/A')} ({context.get('patient_id', 'N/A')})",
        f"Diagnosis: {context.get('diagnosis', 'N/A')}",
        f"Follow-up Date: {follow_up_date.isoformat()}",
        f"Current Date: {current_date.isoformat()}",
        "",
        f"Clinical Brief: {report.get('clinical_brief', '')}",
        "",
        f"Missed Follow-up Reason: {report.get('missed_follow_up_reason', '')}",
        "",
        "Immediate Actions:",
    ]
    parts.extend(f"- {action}" for action in report.get("immediate_actions", []))
    parts.extend(
        [
            "",
            "Recommended Next Steps:",
        ]
    )
    parts.extend(f"- {action}" for action in report.get("recommended_next_steps", []))
    parts.extend(
        [
            "",
            f"Urgency Timeline: {report.get('urgency_timeline', 'as soon as possible')}",
        ]
    )
    patient_summary = context.get("patient_summary")
    if patient_summary:
        parts.extend(["", "Patient Summary:", patient_summary])
    return "\n".join(parts).strip()


@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    reraise=True
)
def _generate_report_with_llm(context: dict[str, Any], current_date: date) -> dict[str, Any]:
    if not gemini_enabled():
        return _fallback_report(context, current_date)

    prompt = (
        "Generate a concise clinical escalation summary for a missed hospital follow-up.\n"
        "Use the following patient details and return valid JSON with keys:\n"
        "clinical_brief, missed_follow_up_reason, immediate_actions, recommended_next_steps, urgency_timeline.\n\n"
        f"Patient ID: {context.get('patient_id', '')}\n"
        f"Patient Name: {context.get('patient_name', '')}\n"
        f"Diagnosis: {context.get('diagnosis', '')}\n"
        f"Doctor Notes: {context.get('doctor_notes', '')}\n"
        f"Follow-up Date: {context.get('follow_up_date', '')}\n"
        f"Current Date: {current_date.isoformat()}\n"
        f"Patient Summary: {context.get('patient_summary', '') or 'Not available.'}\n"
    )
    parsed = generate_structured_response(
        prompt=prompt,
        schema_model=_EscalationResponse,
        system_instruction=(
            "You are a hospital escalation assistant. "
            "Be clinically careful, concise, and actionable."
        ),
    )
    return {
        "clinical_brief": parsed.clinical_brief,
        "missed_follow_up_reason": parsed.missed_follow_up_reason,
        "immediate_actions": parsed.immediate_actions,
        "recommended_next_steps": parsed.recommended_next_steps,
        "urgency_timeline": parsed.urgency_timeline,
    }


def _existing_escalation(connection: sqlite3.Connection, patient_id: str) -> Optional[int]:
    cursor = connection.execute(
        "SELECT escalation_id FROM escalations WHERE patient_id = ? LIMIT 1",
        (patient_id,),
    )
    row = cursor.fetchone()
    return int(row["escalation_id"]) if row else None


def _deactivate_reminders(connection: sqlite3.Connection, patient_id: str) -> None:
    connection.execute(
        "UPDATE reminders SET is_active = 0, updated_at = ? WHERE patient_id = ?",
        (datetime.utcnow().isoformat(timespec="seconds"), patient_id),
    )


def _insert_escalation(
    connection: sqlite3.Connection,
    context: dict[str, Any],
    escalation_report: str,
    current_date: date,
) -> int:
    now = datetime.utcnow().isoformat(timespec="seconds")
    cursor = connection.execute(
        """
        INSERT INTO escalations (
            patient_id,
            patient_name,
            diagnosis,
            follow_up_date,
            doctor_notes,
            escalation_report,
            escalation_status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
        """,
        (
            context.get("patient_id"),
            context.get("patient_name"),
            context.get("diagnosis"),
            _parse_date(context.get("follow_up_date")).isoformat(),
            context.get("doctor_notes"),
            escalation_report,
            now,
        ),
    )
    return int(cursor.lastrowid)


def generate_escalation(
    patient_data: Mapping[str, Any],
    summary: str = "",
    current_date: Any = None,
    database_url: str = DATABASE_URL,
) -> dict[str, Any]:
    context = _extract_patient_context(patient_data)
    if summary and not context.get("patient_summary"):
        context["patient_summary"] = summary

    today = _parse_date(current_date)
    if not context.get("patient_id"):
        raise ValueError("patient_id is required to create an escalation record.")
    if not context.get("follow_up_date"):
        raise ValueError("follow_up_date is required to create an escalation record.")

    with _connect(database_url) as connection:
        if _existing_escalation(connection, context["patient_id"]) is not None:
            logger.info(f"Skipping patient {context['patient_id']}: escalation already exists")
            return {
                "patient_id": context["patient_id"],
                "escalation_skipped": True,
                "escalation_status": "skipped",
                "message": "Escalation already exists for this patient.",
            }

        _deactivate_reminders(connection, context["patient_id"])
        report = _generate_report_with_llm(context, today)
        escalation_report = _format_report(report, context, today)
        escalation_id = _insert_escalation(connection, context, escalation_report, today)
        connection.commit()

    return {
        "patient_id": context["patient_id"],
        "escalation_id": escalation_id,
        "escalation_report": escalation_report,
        "escalation_status": "pending",
        "escalation_skipped": False,
        "message": "Escalation created successfully.",
    }


def escalation_agent(state: Mapping[str, Any]) -> dict[str, Any]:
    patient_data = state.get("patient_data") if isinstance(state.get("patient_data"), Mapping) else state
    summary = state.get("summary", "") if isinstance(state, Mapping) else ""
    current_date = state.get("current_date") if isinstance(state, Mapping) else None

    try:
        result = generate_escalation(
            patient_data=patient_data,
            summary=summary,
            current_date=current_date,
        )
        return {
            "escalation_report": result.get("escalation_report", ""),
            "escalation_status": result.get("escalation_status", "pending"),
            "escalation_id": result.get("escalation_id"),
            "escalation_skipped": result.get("escalation_skipped", False),
            "error": "",
        }
    except Exception as exc:
        return {
            "escalation_report": "",
            "escalation_status": "error",
            "escalation_id": None,
            "escalation_skipped": False,
            "error": str(exc),
        }


__all__ = ["generate_escalation", "escalation_agent"]
