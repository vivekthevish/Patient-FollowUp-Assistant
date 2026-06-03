import os
import sys
import json
import pandas as pd
from typing import TypedDict, Optional, Literal, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command

from config import DATASET_DIR


class FollowUpState(TypedDict):
    patient_id: str
    patient_data: Optional[dict]
    rag_context: str
    summary: str
    risk_level: str
    reminders: List[dict]
    escalation_message: str
    human_decision: str
    final_output: dict
    error: str
    retry_count: int


# ── Node: Load Patient Data ──────────────────────────────────────────────────
def load_patient_node(state: FollowUpState) -> dict:
    try:
        patients_df = pd.read_csv(os.path.join(DATASET_DIR, "patients.csv"))
        appointments_df = pd.read_csv(os.path.join(DATASET_DIR, "appointments.csv"))
        followups_df = pd.read_csv(os.path.join(DATASET_DIR, "followup_records.csv"))

        patient = patients_df[patients_df["patient_id"] == state["patient_id"]].to_dict("records")
        if not patient:
            return {"error": f"Patient {state['patient_id']} not found.", "retry_count": 0}

        appts = appointments_df[appointments_df["patient_id"] == state["patient_id"]].to_dict("records")
        fups = followups_df[followups_df["patient_id"] == state["patient_id"]].to_dict("records")

        return {
            "patient_data": {
                "profile": patient[0],
                "appointments": appts,
                "followup_history": fups
            },
            "error": "",
            "retry_count": 0
        }
    except Exception as e:
        count = state.get("retry_count", 0)
        return {"error": str(e), "retry_count": count + 1}


# ── Node: RAG Retrieval ──────────────────────────────────────────────────────
def rag_retrieval_node(state: FollowUpState) -> dict:
    if state.get("error"):
        return {}
    try:
        from rag.rag_pipeline import get_rag_context
        profile = state["patient_data"]["profile"]
        query = f"Follow-up care protocol for {profile.get('diagnosis', 'general')} patient"
        context = get_rag_context(query)
        return {"rag_context": context}
    except Exception as e:
        print(f"[RAG Node] Warning: {e}")
        return {"rag_context": ""}


# ── Node: Patient Summary Agent ──────────────────────────────────────────────
def patient_summary_node(state: FollowUpState) -> dict:
    if state.get("error"):
        return {}
    try:
        from agents.patient_summary_agent import generate_patient_summary
        summary, risk_level = generate_patient_summary(
            state["patient_data"],
            state.get("rag_context", "")
        )
        return {"summary": summary, "risk_level": risk_level}
    except Exception as e:
        return {"error": str(e), "summary": "", "risk_level": "medium"}


# ── Node: Reminder Agent ─────────────────────────────────────────────────────
def reminder_node(state: FollowUpState) -> dict:
    if state.get("error"):
        return {}
    try:
        from agents.reminder_agent import generate_reminders
        reminders = generate_reminders(
            state["patient_data"],
            state.get("summary", ""),
            state.get("rag_context", "")
        )
        return {"reminders": reminders}
    except Exception as e:
        return {"error": str(e), "reminders": []}


# ── Node: Escalation Agent ───────────────────────────────────────────────────
def escalation_node(state: FollowUpState) -> dict:
    if state.get("error"):
        return {}
    try:
        from agents.escalation_agent import generate_escalation
        escalation_msg = generate_escalation(
            state["patient_data"],
            state.get("summary", "")
        )
        return {"escalation_message": escalation_msg}
    except Exception as e:
        return {"error": str(e), "escalation_message": ""}


# ── Node: Human Approval (LangGraph Interrupt) ───────────────────────────────
def human_approval_node(state: FollowUpState) -> dict:
    human_decision = interrupt({
        "type": "human_approval_required",
        "patient_id": state["patient_id"],
        "summary": state.get("summary", ""),
        "escalation_message": state.get("escalation_message", ""),
        "risk_level": state.get("risk_level", "high"),
        "instructions": (
            "Review the escalation report above. "
            "Enter 'approve' to proceed with reminders, "
            "'reject' to close without action, "
            "or 'escalate' for immediate intervention."
        )
    })
    return {"human_decision": str(human_decision).strip().lower()}


# ── Node: Output Formatter ───────────────────────────────────────────────────
def output_formatter_node(state: FollowUpState) -> dict:
    if state.get("error"):
        return {
            "final_output": {
                "status": "error",
                "patient_id": state.get("patient_id", "unknown"),
                "message": state["error"]
            }
        }

    profile = state.get("patient_data", {}).get("profile", {})
    return {
        "final_output": {
            "status": "success",
            "patient_id": state["patient_id"],
            "patient_name": profile.get("name", "N/A"),
            "risk_level": state.get("risk_level", "unknown"),
            "summary": state.get("summary", ""),
            "reminders": state.get("reminders", []),
            "escalation_required": state.get("risk_level", "") in ["high", "critical"],
            "escalation_message": state.get("escalation_message", ""),
            "human_decision": state.get("human_decision", "n/a"),
            "rag_used": bool(state.get("rag_context"))
        }
    }


# ── Conditional Routing ──────────────────────────────────────────────────────
def route_by_risk(state: FollowUpState) -> Literal["reminder", "escalation", "output"]:
    if state.get("error"):
        return "output"
    risk = state.get("risk_level", "low").lower()
    if risk in ["high", "critical"]:
        return "escalation"
    return "reminder"


def route_after_human(state: FollowUpState) -> Literal["reminder", "output"]:
    decision = state.get("human_decision", "reject").lower()
    if decision == "approve":
        return "reminder"
    return "output"


# ── Build Graph ──────────────────────────────────────────────────────────────
def build_workflow():
    workflow = StateGraph(FollowUpState)

    workflow.add_node("load_patient", load_patient_node)
    workflow.add_node("rag_retrieval", rag_retrieval_node)
    workflow.add_node("patient_summary", patient_summary_node)
    workflow.add_node("reminder", reminder_node)
    workflow.add_node("escalation", escalation_node)
    workflow.add_node("human_approval", human_approval_node)
    workflow.add_node("output", output_formatter_node)

    workflow.add_edge(START, "load_patient")
    workflow.add_edge("load_patient", "rag_retrieval")
    workflow.add_edge("rag_retrieval", "patient_summary")
    workflow.add_conditional_edges(
        "patient_summary",
        route_by_risk,
        {"reminder": "reminder", "escalation": "escalation", "output": "output"}
    )
    workflow.add_edge("escalation", "human_approval")
    workflow.add_conditional_edges(
        "human_approval",
        route_after_human,
        {"reminder": "reminder", "output": "output"}
    )
    workflow.add_edge("reminder", "output")
    workflow.add_edge("output", END)

    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)


graph = build_workflow()
