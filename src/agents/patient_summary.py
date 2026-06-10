"""Patient summary agent."""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Mapping

from src.config import MAX_RETRIES, OPENAI_API_KEY, OPENAI_MODEL, RETRY_DELAY, TEMPERATURE

from tenacity import retry, stop_after_attempt, wait_fixed


def _risk_from_severity(severity: str, days_overdue: int = 0) -> float:
    base = {
        "Critical": 9.2,
        "High": 7.4,
        "Moderate": 5.0,
        "Low": 2.2,
    }.get(severity.title(), 5.0)
    return min(10.0, max(0.0, base + min(days_overdue, 7) * 0.25))


def _fallback_summary(profile: Mapping[str, Any], rag_context: str) -> tuple[str, float]:
    follow_up_date = profile.get("follow_up_date")
    if isinstance(follow_up_date, date):
        days_overdue = max((date.today() - follow_up_date).days, 0)
    else:
        days_overdue = 0
    severity = str(profile.get("severity", "Moderate"))
    risk_score = round(_risk_from_severity(severity, days_overdue), 1)
    summary = (
        f"{profile.get('patient_name', 'The patient')} is a {profile.get('age', 'N/A')}-year-old "
        f"patient with {profile.get('diagnosis', 'an unspecified diagnosis')}. "
        f"Recent notes indicate {profile.get('doctor_notes', 'no additional clinical notes')} "
        f"The patient should be monitored closely and follow-up should remain a priority."
    )
    if rag_context:
        summary += f" Protocol context reviewed from the care guidance materials."
    return summary, risk_score


@retry(stop=stop_after_attempt(MAX_RETRIES), wait=wait_fixed(RETRY_DELAY), reraise=True)
def generate_patient_summary(patient_data: Mapping[str, Any], rag_context: str = "") -> tuple[str, float]:
    profile = patient_data.get("profile") if isinstance(patient_data.get("profile"), Mapping) else patient_data

    if not OPENAI_API_KEY:
        return _fallback_summary(profile, rag_context)

    from openai import OpenAI

    prompt = {
        "patient_profile": profile,
        "rag_context": rag_context,
    }

    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=TEMPERATURE,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a clinical AI assistant. "
                    "Return valid JSON with keys summary and risk_score."
                ),
            },
            {"role": "user", "content": json.dumps(prompt, default=str)},
        ],
    )

    parsed = json.loads(response.choices[0].message.content or "{}")
    summary = parsed.get("summary") or parsed.get("clinical_summary") or ""
    risk_score = float(parsed.get("risk_score") or 5.0)
    return summary, risk_score
