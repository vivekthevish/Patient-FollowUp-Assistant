import os
import sys
import json
from tenacity import retry, stop_after_attempt, wait_fixed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OPENAI_API_KEY, MODEL_NAME, TEMPERATURE, MAX_RETRIES, RETRY_DELAY
from openai import OpenAI

client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """You are a critical care coordinator AI at a hospital.
When a patient is flagged as HIGH or CRITICAL risk, your role is to:
1. Generate a concise clinical escalation report for the attending physician
2. Identify immediate action items
3. Flag potential complications that require urgent attention
4. Prepare a brief for the human reviewer who will approve or reject escalation

Be clinical, precise, and prioritize patient safety above all else.
Always respond in valid JSON format."""

ESCALATION_PROMPT = """A patient has been flagged as {risk_level} risk.
Generate an escalation report for immediate physician review.

Patient Profile:
{patient_profile}

AI-Generated Clinical Summary:
{summary}

Generate an escalation report with this JSON format:
{{
    "escalation_id": "ESC-{patient_id}-AUTO",
    "escalation_level": "high|critical",
    "clinical_brief": "3-4 sentence clinical brief for the physician",
    "immediate_actions": ["action1", "action2", "action3"],
    "potential_complications": ["complication1", "complication2"],
    "recommended_timeline": "e.g., within 24 hours",
    "contact_instructions": "How the care team should reach out",
    "requires_human_approval": true,
    "escalation_reason": "concise reason for escalation"
}}"""


@retry(stop=stop_after_attempt(MAX_RETRIES), wait=wait_fixed(RETRY_DELAY))
def generate_escalation(patient_data: dict, summary: str) -> str:
    profile = patient_data.get("profile", {})
    risk_level = profile.get("risk_level", "high")
    patient_id = profile.get("patient_id", "UNKNOWN")

    prompt = ESCALATION_PROMPT.format(
        risk_level=risk_level.upper(),
        patient_profile=json.dumps(profile, indent=2),
        summary=summary,
        patient_id=patient_id
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

    escalation_text = (
        f"ESCALATION REPORT — {result.get('escalation_id', 'N/A')}\n"
        f"Level: {result.get('escalation_level', 'high').upper()}\n\n"
        f"Clinical Brief:\n{result.get('clinical_brief', '')}\n\n"
        f"Immediate Actions Required:\n"
        + "\n".join(f"  • {a}" for a in result.get("immediate_actions", []))
        + f"\n\nPotential Complications:\n"
        + "\n".join(f"  • {c}" for c in result.get("potential_complications", []))
        + f"\n\nTimeline: {result.get('recommended_timeline', 'ASAP')}"
        + f"\n\nReason: {result.get('escalation_reason', '')}"
    )

    return escalation_text
