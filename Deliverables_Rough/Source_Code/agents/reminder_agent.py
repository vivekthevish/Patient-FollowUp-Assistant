import os
import sys
import json
from typing import List
from tenacity import retry, stop_after_attempt, wait_fixed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OPENAI_API_KEY, MODEL_NAME, TEMPERATURE, MAX_RETRIES, RETRY_DELAY
from openai import OpenAI

client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """You are a patient engagement specialist at a hospital.
Your role is to generate personalized, empathetic follow-up reminders for patients.
Reminders must be:
- Patient-friendly and non-alarming
- Specific to the patient's diagnosis and follow-up needs
- Actionable with clear next steps
- Compliant with HIPAA guidelines (no overly sensitive information in message body)

Always respond in valid JSON format."""

REMINDER_PROMPT = """Generate personalized follow-up reminders for the following patient.

Patient Name: {name}
Age: {age}
Diagnosis: {diagnosis}
Risk Level: {risk_level}
Next Follow-up Due: {next_followup_due}
Medications: {medications}
Primary Physician: {primary_physician}

Clinical Summary:
{summary}

Relevant Protocol Guidance:
{rag_context}

Generate 3 reminders across these channels: SMS, Email, Phone Call Script.
Respond with JSON in this format:
{{
    "reminders": [
        {{
            "channel": "SMS",
            "message": "concise SMS under 160 chars",
            "timing": "when to send this"
        }},
        {{
            "channel": "Email",
            "subject": "email subject",
            "body": "full email body with greeting and sign-off",
            "timing": "when to send this"
        }},
        {{
            "channel": "Phone Script",
            "script": "full phone call script for the care coordinator",
            "timing": "when to make this call"
        }}
    ],
    "follow_up_priority": "routine|urgent|critical",
    "suggested_appointment_window": "e.g., within 7 days"
}}"""


@retry(stop=stop_after_attempt(MAX_RETRIES), wait=wait_fixed(RETRY_DELAY))
def generate_reminders(patient_data: dict, summary: str, rag_context: str) -> List[dict]:
    profile = patient_data.get("profile", {})

    prompt = REMINDER_PROMPT.format(
        name=profile.get("name", "Patient"),
        age=profile.get("age", "N/A"),
        diagnosis=profile.get("diagnosis", "N/A"),
        risk_level=profile.get("risk_level", "medium"),
        next_followup_due=profile.get("next_followup_due", "N/A"),
        medications=profile.get("medications", "N/A"),
        primary_physician=profile.get("primary_physician", "Your Doctor"),
        summary=summary,
        rag_context=rag_context if rag_context else "Standard follow-up protocol applies."
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
    return result.get("reminders", [])
