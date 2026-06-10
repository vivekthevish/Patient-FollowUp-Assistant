"""Business logic for the FastAPI routes."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import date, datetime
from typing import Iterable, Mapping, Optional

from sqlalchemy import and_, case, desc, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.agents.escalation import generate_escalation
from src.agents.patient_summary import generate_patient_summary
from src.agents.reminder import generate_reminder
from src.db.models import Escalation, Patient, Reminder
from src.db.session import SessionLocal
from src.email.ses import send_email
from src.rag.pipeline import get_rag_context, retrieve_context_chunks


REMINDER_WINDOWS = {7, 3, 1}
WORKFLOW_JOBS: dict[str, dict] = {}
WORKFLOW_JOBS_LOCK = threading.Lock()


def now_utc() -> datetime:
    return datetime.utcnow().replace(microsecond=0)


def _workflow_error_message(exc: Exception) -> str:
    last_attempt = getattr(exc, "last_attempt", None)
    if last_attempt is not None:
        inner_exception = getattr(last_attempt, "exception", lambda: None)()
        if inner_exception is not None and inner_exception is not exc:
            return _workflow_error_message(inner_exception)

    exception_name = exc.__class__.__name__
    if exception_name == "RateLimitError":
        return "OpenAI rate limit reached. Please retry the workflow in a moment."
    if exception_name == "AuthenticationError":
        return "OpenAI authentication failed. Check OPENAI_API_KEY and try again."

    message = str(exc).strip()
    return message or exception_name


def isoformat(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.isoformat() + "Z"


def _severity_rank(severity: str) -> int:
    mapping = {"Critical": 0, "High": 1, "Moderate": 2, "Low": 3}
    return mapping.get(severity, 99)


def _patient_to_dict(patient: Patient, reminder: Reminder | None = None) -> dict:
    return {
        "patient_id": patient.patient_id,
        "patient_name": patient.patient_name,
        "diagnosis": patient.diagnosis,
        "severity": patient.severity,
        "follow_up_date": patient.follow_up_date,
        "patient_summary": patient.patient_summary,
        "risk_score": patient.risk_score,
        "followup_status": patient.followup_status,
        "email": patient.email,
        "phone": patient.phone,
        "doctor_notes": patient.doctor_notes,
        "attending_doctor": patient.attending_doctor,
        "created_at": patient.created_at,
        "updated_at": patient.updated_at,
        "reminder": _reminder_to_dict(reminder) if reminder else None,
    }


def _reminder_to_dict(reminder: Reminder | None) -> dict | None:
    if reminder is None:
        return None
    return {
        "reminder_id": reminder.reminder_id,
        "reminder_text": reminder.reminder_text,
        "rag_context_json": reminder.rag_context_json,
        "reminder_sent_dates": reminder.reminder_sent_dates,
        "email_status": reminder.email_status,
        "email_sent_at": reminder.email_sent_at,
    }


def _escalation_to_dict(escalation: Escalation) -> dict:
    return {
        "escalation_id": escalation.escalation_id,
        "patient_id": escalation.patient_id,
        "patient_name": escalation.patient_name,
        "diagnosis": escalation.diagnosis,
        "follow_up_date": escalation.follow_up_date,
        "escalation_report": escalation.escalation_report,
        "escalation_status": escalation.escalation_status,
        "created_at": escalation.created_at,
        "closed_at": escalation.closed_at,
    }


def _next_patient_id(session: Session) -> str:
    rows = session.execute(select(Patient.patient_id)).scalars().all()
    max_number = 0
    for patient_id in rows:
        if isinstance(patient_id, str) and patient_id.startswith("P"):
            try:
                max_number = max(max_number, int(patient_id[1:]))
            except ValueError:
                continue
    return f"P{max_number + 1:03d}"


def create_patient(session: Session, payload) -> dict:
    duplicate_email = session.execute(
        select(Patient).where(func.lower(Patient.email) == payload.email.lower())
    ).scalar_one_or_none()
    if duplicate_email:
        raise ValueError("Email already exists for another patient.")

    patient = Patient(
        patient_id=_next_patient_id(session),
        patient_name=payload.patient_name,
        age=payload.age,
        gender=payload.gender,
        email=payload.email,
        phone=payload.phone,
        diagnosis=payload.diagnosis,
        follow_up_date=payload.follow_up_date,
        doctor_notes=payload.doctor_notes,
        attending_doctor=payload.attending_doctor,
        severity=payload.severity,
        followup_status="pending",
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    session.add(patient)
    session.flush()
    return {
        "patient_id": patient.patient_id,
        "patient_name": patient.patient_name,
        "follow_up_date": patient.follow_up_date,
        "message": "Patient registered successfully.",
        "created_at": patient.created_at,
    }


def get_latest_active_reminder(session: Session, patient_id: str) -> Reminder | None:
    return (
        session.execute(
            select(Reminder)
            .where(and_(Reminder.patient_id == patient_id, Reminder.is_active.is_(True)))
            .order_by(desc(Reminder.created_at), desc(Reminder.reminder_id))
        )
        .scalars()
        .first()
    )


def list_patients(
    session: Session,
    followup_status: str = "all",
    severity: str | None = None,
    search: str | None = None,
) -> list[dict]:
    statement = select(Patient)
    conditions = []
    if followup_status != "all":
        conditions.append(Patient.followup_status == followup_status)
    if severity:
        conditions.append(Patient.severity == severity)
    if search:
        search_term = f"%{search.lower()}%"
        conditions.append(
            or_(
                func.lower(Patient.patient_name).like(search_term),
                func.lower(Patient.email).like(search_term),
            )
        )
    if conditions:
        statement = statement.where(and_(*conditions))

    severity_order = case(
        {"Critical": 0, "High": 1, "Moderate": 2, "Low": 3},
        value=Patient.severity,
        else_=99,
    )
    patients = session.execute(statement.order_by(Patient.follow_up_date.asc(), severity_order.asc())).scalars().all()

    results: list[dict] = []
    for patient in patients:
        reminder = get_latest_active_reminder(session, patient.patient_id)
        results.append(_patient_to_dict(patient, reminder))
    return results


def get_patient_detail(session: Session, patient_id: str) -> dict:
    patient = session.get(Patient, patient_id)
    if not patient:
        raise LookupError("Patient not found.")
    reminder = get_latest_active_reminder(session, patient_id)
    return _patient_to_dict(patient, reminder)


def update_patient_outcome(session: Session, patient_id: str, followup_status: str) -> dict:
    patient = session.get(Patient, patient_id)
    if not patient:
        raise LookupError("Patient not found.")
    patient.followup_status = followup_status
    patient.updated_at = now_utc()
    session.flush()
    return {
        "patient_id": patient.patient_id,
        "followup_status": patient.followup_status,
        "message": "Follow-up outcome updated successfully.",
        "updated_at": patient.updated_at,
    }


def _summarize_patient(session: Session, patient: Patient) -> tuple[str, float]:
    patient_data = {
        "profile": {
            "patient_id": patient.patient_id,
            "patient_name": patient.patient_name,
            "age": patient.age,
            "gender": patient.gender,
            "diagnosis": patient.diagnosis,
            "doctor_notes": patient.doctor_notes,
            "follow_up_date": patient.follow_up_date,
            "attending_doctor": patient.attending_doctor,
            "severity": patient.severity,
        }
    }
    rag_context = get_rag_context(patient.diagnosis, k=3)
    summary, risk_score = generate_patient_summary(patient_data, rag_context)
    patient.patient_summary = summary
    patient.risk_score = risk_score
    patient.updated_at = now_utc()
    session.flush()
    return summary, risk_score


def _duplicate_reminder_today(session: Session, patient_id: str) -> bool:
    reminder = (
        session.execute(
            select(Reminder)
            .where(Reminder.patient_id == patient_id)
            .order_by(desc(Reminder.created_at), desc(Reminder.reminder_id))
        )
        .scalars()
        .first()
    )
    if not reminder:
        return False
    try:
        reminder_dates = json.loads(reminder.reminder_sent_dates or "[]")
    except json.JSONDecodeError:
        reminder_dates = []
    return str(date.today()) in reminder_dates


def _create_reminder(session: Session, patient: Patient, summary: str) -> dict:
    rag_context = get_rag_context(patient.diagnosis, k=3)
    reminder_payload = generate_reminder(
        {
            "profile": {
                "patient_id": patient.patient_id,
                "patient_name": patient.patient_name,
                "diagnosis": patient.diagnosis,
                "follow_up_date": patient.follow_up_date,
                "attending_doctor": patient.attending_doctor,
            }
        },
        summary=summary,
        rag_context=rag_context,
    )

    previous_reminder = (
        session.execute(
            select(Reminder)
            .where(Reminder.patient_id == patient.patient_id)
            .order_by(desc(Reminder.created_at), desc(Reminder.reminder_id))
        )
        .scalars()
        .first()
    )
    sent_dates = []
    if previous_reminder:
        try:
            sent_dates = json.loads(previous_reminder.reminder_sent_dates or "[]")
        except json.JSONDecodeError:
            sent_dates = []
    sent_dates.append(str(date.today()))

    reminder = Reminder(
        patient_id=patient.patient_id,
        reminder_text=reminder_payload["reminder_text"],
        rag_context_json=json.dumps(reminder_payload["rag_context_json"]),
        reminder_sent_dates=json.dumps(sent_dates),
        email_status="not_sent",
        is_active=True,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    session.add(reminder)
    session.flush()

    email_result = send_email(
        to_email=patient.email,
        subject=reminder_payload["email_subject"],
        html_body=f"<pre>{reminder_payload['reminder_text']}</pre>",
        text_body=reminder_payload["reminder_text"],
    )

    reminder.email_status = "sent" if email_result.sent else "failed"
    reminder.email_sent_at = now_utc() if email_result.sent else None
    reminder.updated_at = now_utc()
    session.flush()
    return {
        "reminder_id": reminder.reminder_id,
        "email_status": reminder.email_status,
        "error": email_result.error if not email_result.sent else None,
    }


def _create_escalation(session: Session, patient: Patient, summary: str) -> dict:
    patient_data = {
        "profile": {
            "patient_id": patient.patient_id,
            "patient_name": patient.patient_name,
            "diagnosis": patient.diagnosis,
            "doctor_notes": patient.doctor_notes,
            "follow_up_date": patient.follow_up_date,
            "patient_summary": summary or patient.patient_summary or "",
        },
        "summary": summary or patient.patient_summary or "",
    }
    session.commit()
    result = generate_escalation(patient_data, summary=summary, current_date=date.today())
    escalation = (
        session.execute(
            select(Escalation).where(Escalation.patient_id == patient.patient_id)
        )
        .scalars()
        .first()
    )
    return {
        "patient_id": patient.patient_id,
        "status": "success" if escalation or result.get("escalation_skipped") else "failed",
        "error": result.get("error"),
    }


def _classify_patients(session: Session) -> tuple[list[Patient], list[Patient], list[Patient]]:
    today = date.today()
    reminder_patients: list[Patient] = []
    escalation_patients: list[Patient] = []
    skipped_patients: list[Patient] = []

    patients = session.execute(select(Patient).order_by(Patient.follow_up_date.asc(), Patient.patient_id.asc())).scalars().all()
    for patient in patients:
        if patient.followup_status == "completed":
            skipped_patients.append(patient)
            continue
        days_until_follow_up = (patient.follow_up_date - today).days
        if days_until_follow_up < 0:
            escalation_patients.append(patient)
        elif days_until_follow_up in REMINDER_WINDOWS:
            reminder_patients.append(patient)
        else:
            skipped_patients.append(patient)

    return reminder_patients, escalation_patients, skipped_patients


def _run_workflow_job(job_id: str) -> None:
    with SessionLocal() as session:
        try:
            reminder_patients, escalation_patients, skipped_patients = _classify_patients(session)
            for patient in reminder_patients:
                try:
                    summary, _risk_score = _summarize_patient(session, patient)
                    session.commit()
                    if _duplicate_reminder_today(session, patient.patient_id):
                        with WORKFLOW_JOBS_LOCK:
                            WORKFLOW_JOBS[job_id]["results"].append(
                                {
                                    "patient_id": patient.patient_id,
                                    "path": "reminder",
                                    "status": "skipped",
                                "error": "Reminder already sent today.",
                            }
                        )
                        session.commit()
                        continue
                    reminder_result = _create_reminder(session, patient, summary)
                    with WORKFLOW_JOBS_LOCK:
                        WORKFLOW_JOBS[job_id]["results"].append(
                            {
                                "patient_id": patient.patient_id,
                                "path": "reminder",
                                "status": "success" if reminder_result["email_status"] == "sent" else "failed",
                                "email_status": reminder_result["email_status"],
                                "error": reminder_result["error"],
                            }
                        )
                    session.commit()
                except Exception as exc:
                    session.rollback()
                    with WORKFLOW_JOBS_LOCK:
                        WORKFLOW_JOBS[job_id]["results"].append(
                            {
                                "patient_id": patient.patient_id,
                                "path": "reminder",
                                "status": "failed",
                                "error": _workflow_error_message(exc),
                            }
                        )

            for patient in escalation_patients:
                try:
                    summary, _risk_score = _summarize_patient(session, patient)
                    escalation_result = _create_escalation(session, patient, summary)
                    with WORKFLOW_JOBS_LOCK:
                        WORKFLOW_JOBS[job_id]["results"].append(
                            {
                                "patient_id": patient.patient_id,
                                "path": "escalation",
                                "status": escalation_result["status"],
                                "error": escalation_result["error"],
                            }
                        )
                    session.commit()
                except Exception as exc:
                    session.rollback()
                    with WORKFLOW_JOBS_LOCK:
                        WORKFLOW_JOBS[job_id]["results"].append(
                            {
                                "patient_id": patient.patient_id,
                                "path": "escalation",
                                "status": "failed",
                                "error": _workflow_error_message(exc),
                            }
                        )

            with WORKFLOW_JOBS_LOCK:
                WORKFLOW_JOBS[job_id]["status"] = "completed"
                WORKFLOW_JOBS[job_id]["completed_at"] = now_utc()
        except Exception as exc:
            with WORKFLOW_JOBS_LOCK:
                WORKFLOW_JOBS[job_id]["status"] = "failed"
                WORKFLOW_JOBS[job_id]["error"] = _workflow_error_message(exc)
                WORKFLOW_JOBS[job_id]["completed_at"] = now_utc()


def start_workflow_job(session: Session) -> dict:
    reminder_patients, escalation_patients, skipped_patients = _classify_patients(session)
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    record = {
        "job_id": job_id,
        "status": "running",
        "reminder_patients": [patient.patient_id for patient in reminder_patients],
        "escalation_patients": [patient.patient_id for patient in escalation_patients],
        "skipped_patients": [patient.patient_id for patient in skipped_patients],
        "results": [],
        "completed_at": None,
        "error": None,
    }
    with WORKFLOW_JOBS_LOCK:
        WORKFLOW_JOBS[job_id] = record

    thread = threading.Thread(target=_run_workflow_job, args=(job_id,), daemon=True)
    thread.start()
    return record


def get_workflow_status(job_id: str) -> dict:
    with WORKFLOW_JOBS_LOCK:
        job = WORKFLOW_JOBS.get(job_id)
        if job is None:
            raise LookupError("Workflow job not found.")
        return dict(job)


def list_escalations(session: Session, status: str = "pending") -> list[dict]:
    statement = select(Escalation).order_by(Escalation.created_at.desc())
    if status != "all":
        statement = statement.where(Escalation.escalation_status == status)
    return [_escalation_to_dict(row) for row in session.execute(statement).scalars().all()]


def close_escalation(session: Session, escalation_id: int, closed_by: str) -> dict:
    escalation = session.get(Escalation, escalation_id)
    if not escalation:
        raise LookupError("Escalation not found.")
    escalation.escalation_status = "closed"
    escalation.closed_at = now_utc()
    session.flush()
    return {
        "escalation_id": escalation.escalation_id,
        "patient_id": escalation.patient_id,
        "escalation_status": escalation.escalation_status,
        "closed_at": escalation.closed_at,
        "message": "Escalation marked as closed.",
    }
