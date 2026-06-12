"""Reminder agent."""

from __future__ import annotations

from datetime import date
from typing import Any, Mapping

import json
from pydantic import BaseModel

from src.agents.gemini import gemini_enabled, generate_structured_response
from tenacity import retry, stop_after_attempt, wait_fixed

from src.config import MAX_RETRIES, RETRY_DELAY


class _ReminderResponse(BaseModel):
    reminder_text: str


def _fallback_reminder(profile: Mapping[str, Any], summary: str, rag_context: str) -> str:
    follow_up_date = profile.get("follow_up_date")
    follow_up_text = follow_up_date.isoformat() if hasattr(follow_up_date, "isoformat") else str(follow_up_date)
    patient_name = profile.get("patient_name") or profile.get("name") or "Patient"
    doctor = profile.get("attending_doctor", "your care team")
    diagnosis = profile.get("diagnosis", "your recent condition")
    return (
        f"Dear {patient_name}, this is a friendly reminder that your follow-up for {diagnosis} is scheduled "
        f"for {follow_up_text} with {doctor}. {summary or 'Please keep this appointment so your care team can review your recovery.'} "
        f"Please contact the hospital if you need help rescheduling or if your symptoms change. "
        f"We have also reviewed the latest care guidance to support your follow-up plan."
    )


@retry(stop=stop_after_attempt(MAX_RETRIES), wait=wait_fixed(RETRY_DELAY), reraise=True)
def generate_reminder(patient_data: Mapping[str, Any], summary: str = "", rag_context: str = "") -> dict[str, Any]:
    profile = patient_data.get("profile") if isinstance(patient_data.get("profile"), Mapping) else patient_data

    reminder_text = _fallback_reminder(profile, summary, rag_context)
    rag_chunks = []
    if rag_context:
        rag_chunks = [
            {"source": "protocols", "page": index + 1, "chunk": chunk.strip()}
            for index, chunk in enumerate([part for part in rag_context.split("\n\n---\n\n") if part.strip()])
        ]

    if gemini_enabled():
        prompt = {
            "patient_profile": profile,
            "patient_summary": summary,
            "rag_context": rag_context,
        }
        parsed = generate_structured_response(
            prompt=json.dumps(prompt, default=str),
            schema_model=_ReminderResponse,
            system_instruction=(
                "You are a hospital reminder assistant. "
                "Return valid JSON with key reminder_text."
            ),
        )
        reminder_text = parsed.reminder_text or reminder_text

    return {
        "reminder_text": reminder_text,
        "rag_context_json": rag_chunks,
        "email_subject": (
            f"Reminder: Your follow-up appointment is on {profile.get('follow_up_date')} — "
            f"{profile.get('attending_doctor', 'Your Care Team')}"
        ),
    }
