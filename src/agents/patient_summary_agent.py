import os
import sys
from typing import Tuple
from tenacity import retry, stop_after_attempt, wait_fixed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OPENAI_API_KEY, MODEL_NAME, TEMPERATURE, MAX_RETRIES, RETRY_DELAY
from openai import OpenAI

client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """You are a clinical AI assistant specializing in patient follow-up management.
Your role is to analyze patient data and generate a concise, structured patient summary
that helps healthcare providers prioritize follow-up care.

You must assess risk level as one of: low, medium, high, or critical.

Risk guidelines:
- critical: Life-threatening conditions, missed multiple critical follow-ups, severe symptoms reported
- high: Post-cardiac/surgical patients, uncontrolled chronic disease, overdue critical follow-up
- medium: Chronic disease management, upcoming follow-up within 2 weeks, moderate risk factors
- low: Routine monitoring, stable condition, follow-up not yet due

Always respond in valid JSON format."""

SUMMARY_PROMPT = """Analyze the following patient data and medical protocol context.
Generate a structured patient summary with risk assessment.

Patient Profile:
{patient_profile}

Appointment History:
{appointments}

Follow-up History:
{followup_history}

Relevant Medical Protocols:
{rag_context}

Respond with JSON in this exact format:
{{
    "risk_level": "low|medium|high|critical",
    "clinical_summary": "2-3 sentence summary of patient's current status",
    "key_concerns": ["concern1", "concern2"],
    "recommended_actions": ["action1", "action2"],
    "days_since_last_followup": <number>,
    "urgency_reason": "brief reason for the risk level assigned"
}}"""


@retry(stop=stop_after_attempt(MAX_RETRIES), wait=wait_fixed(RETRY_DELAY))
def generate_patient_summary(patient_data: dict, rag_context: str) -> Tuple[str, str]:
    import json

    profile = patient_data.get("profile", {})
    appointments = patient_data.get("appointments", [])
    followup_history = patient_data.get("followup_history", [])

    prompt = SUMMARY_PROMPT.format(
        patient_profile=json.dumps(profile, indent=2),
        appointments=json.dumps(appointments, indent=2),
        followup_history=json.dumps(followup_history, indent=2),
        rag_context=rag_context if rag_context else "No specific protocol context available."
    )

    response = client.chat.completions.create(
        model=MODEL_NAME,
        temperature=TEMPERATURE,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
    )

    result = json.loads(response.choices[0].message.content)
    risk_level = result.get("risk_level", "medium").lower()

    summary_text = (
        f"[{risk_level.upper()} RISK] {result.get('clinical_summary', '')}\n\n"
        f"Key Concerns: {', '.join(result.get('key_concerns', []))}\n"
        f"Recommended Actions: {', '.join(result.get('recommended_actions', []))}\n"
        f"Urgency: {result.get('urgency_reason', '')}"
    )

    return summary_text, risk_level
