"""
CareConnect — Streamlit Frontend
AI Patient Follow-Up and Reminder Management System
"""

import os
import sys
import uuid
import json
import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import OPENAI_API_KEY, DATASET_DIR
from rag.rag_pipeline import initialize_rag
from workflow.graph import graph
from langgraph.types import Command


# ── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CareConnect — AI Follow-Up System",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

RISK_COLORS = {
    "low": "#28a745",
    "medium": "#ffc107",
    "high": "#fd7e14",
    "critical": "#dc3545"
}

RISK_BADGES = {
    "low": "🟢 LOW",
    "medium": "🟡 MEDIUM",
    "high": "🟠 HIGH",
    "critical": "🔴 CRITICAL"
}


@st.cache_resource
def load_rag():
    if not OPENAI_API_KEY:
        return None
    return initialize_rag()


@st.cache_data
def load_patients():
    try:
        df = pd.read_csv(os.path.join(DATASET_DIR, "patients.csv"))
        return df
    except Exception as e:
        st.error(f"Failed to load patient data: {e}")
        return pd.DataFrame()


def init_session():
    defaults = {
        "thread_id": str(uuid.uuid4()),
        "workflow_phase": "idle",
        "current_patient_id": None,
        "interrupt_data": None,
        "final_output": None,
        "processing": False,
        "history": []
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def render_sidebar(patients_df: pd.DataFrame):
    with st.sidebar:
        st.image("https://via.placeholder.com/200x60?text=CareConnect", use_container_width=True)
        st.markdown("### Patient Selection")

        if patients_df.empty:
            st.error("No patient data loaded.")
            return None

        patient_options = {
            f"{row['patient_id']} — {row['name']} ({row['diagnosis'][:30]}...)": row["patient_id"]
            for _, row in patients_df.iterrows()
        }

        selected_label = st.selectbox("Select Patient", options=list(patient_options.keys()))
        selected_id = patient_options[selected_label]

        st.markdown("---")
        st.markdown("### Session Stats")
        st.metric("Patients Processed", len(st.session_state.history))

        if st.button("Clear Session", use_container_width=True):
            for key in ["thread_id", "workflow_phase", "current_patient_id",
                        "interrupt_data", "final_output", "history"]:
                st.session_state.pop(key, None)
            st.rerun()

        return selected_id


def render_patient_card(patient_row: pd.Series):
    risk = patient_row.get("risk_level", "medium")
    color = RISK_COLORS.get(risk, "#6c757d")
    badge = RISK_BADGES.get(risk, risk.upper())

    st.markdown(f"""
    <div style="border-left: 5px solid {color}; padding: 12px 16px; background: #f8f9fa; border-radius: 6px; margin-bottom: 12px;">
        <h4 style="margin:0">{patient_row['name']} &nbsp; <span style="font-size:0.85rem; color:{color};">{badge}</span></h4>
        <p style="margin:4px 0; color:#555;">
            Age: {patient_row['age']} &nbsp;|&nbsp; {patient_row['gender']} &nbsp;|&nbsp; {patient_row['blood_group']}
        </p>
        <p style="margin:4px 0;"><b>Diagnosis:</b> {patient_row['diagnosis']}</p>
        <p style="margin:4px 0;"><b>Physician:</b> {patient_row['primary_physician']}</p>
        <p style="margin:4px 0;"><b>Next Follow-up Due:</b> {patient_row['next_followup_due']}</p>
        <p style="margin:4px 0;"><b>Status:</b> {patient_row['followup_status'].upper()}</p>
    </div>
    """, unsafe_allow_html=True)


def run_workflow_phase1(patient_id: str):
    config = {"configurable": {"thread_id": st.session_state.thread_id}}
    initial_state = {
        "patient_id": patient_id,
        "patient_data": None,
        "rag_context": "",
        "summary": "",
        "risk_level": "",
        "reminders": [],
        "escalation_message": "",
        "human_decision": "",
        "final_output": {},
        "error": "",
        "retry_count": 0
    }

    interrupted = False
    last_state = {}

    for event in graph.stream(initial_state, config=config, stream_mode="values"):
        last_state = event
        if isinstance(event, dict) and event.get("__interrupt__"):
            interrupted = True
            break

    snapshot = graph.get_state(config)
    if snapshot.next and "human_approval" in snapshot.next:
        interrupted = True
        interrupt_val = snapshot.tasks[0].interrupts[0].value if snapshot.tasks and snapshot.tasks[0].interrupts else {}
        st.session_state.interrupt_data = interrupt_val
        st.session_state.workflow_phase = "awaiting_approval"
    else:
        st.session_state.final_output = last_state.get("final_output", {})
        st.session_state.workflow_phase = "complete"

    st.session_state.current_patient_id = patient_id


def run_workflow_phase2(decision: str):
    config = {"configurable": {"thread_id": st.session_state.thread_id}}
    last_state = {}

    for event in graph.stream(Command(resume=decision), config=config, stream_mode="values"):
        last_state = event

    st.session_state.final_output = last_state.get("final_output", {})
    st.session_state.workflow_phase = "complete"
    st.session_state.interrupt_data = None


def render_results(output: dict):
    if output.get("status") == "error":
        st.error(f"Workflow Error: {output.get('message', 'Unknown error')}")
        return

    risk = output.get("risk_level", "unknown")
    color = RISK_COLORS.get(risk, "#6c757d")
    badge = RISK_BADGES.get(risk, risk.upper())

    col1, col2, col3 = st.columns(3)
    col1.metric("Patient", output.get("patient_name", "N/A"))
    col2.metric("Risk Level", badge)
    col3.metric("RAG Context Used", "Yes" if output.get("rag_used") else "No")

    st.markdown("#### Clinical Summary")
    st.info(output.get("summary", "No summary available."))

    if output.get("escalation_required"):
        st.markdown("#### Escalation Report")
        st.warning(output.get("escalation_message", ""))
        decision = output.get("human_decision", "n/a")
        st.markdown(f"**Clinician Decision:** `{decision.upper()}`")

    reminders = output.get("reminders", [])
    if reminders:
        st.markdown(f"#### Follow-Up Reminders ({len(reminders)} generated)")
        for i, reminder in enumerate(reminders, 1):
            channel = reminder.get("channel", f"Reminder {i}")
            with st.expander(f"{channel} — {reminder.get('timing', '')}"):
                if channel == "SMS":
                    st.code(reminder.get("message", ""), language=None)
                elif channel == "Email":
                    st.markdown(f"**Subject:** {reminder.get('subject', '')}")
                    st.text_area("Email Body", value=reminder.get("body", ""), height=150, key=f"email_{i}", disabled=True)
                elif channel == "Phone Script":
                    st.text_area("Phone Script", value=reminder.get("script", ""), height=200, key=f"phone_{i}", disabled=True)
                else:
                    st.json(reminder)


def main():
    init_session()
    load_rag()
    patients_df = load_patients()

    st.title("🏥 CareConnect — AI Patient Follow-Up System")
    st.markdown("*Powered by GPT-4 + LangGraph + RAG | IIT Roorkee AIOps Capstone — Team 11*")
    st.divider()

    if not OPENAI_API_KEY:
        st.error("OPENAI_API_KEY not configured. Set it in your .env file.")
        return

    selected_id = render_sidebar(patients_df)
    if selected_id is None:
        return

    patient_row = patients_df[patients_df["patient_id"] == selected_id].iloc[0]

    col_info, col_action = st.columns([2, 1])

    with col_info:
        st.markdown("#### Patient Overview")
        render_patient_card(patient_row)

    with col_action:
        st.markdown("#### Actions")
        if st.button("Generate Follow-Up Plan", type="primary", use_container_width=True):
            st.session_state.thread_id = str(uuid.uuid4())
            st.session_state.workflow_phase = "processing"
            st.session_state.final_output = None
            st.session_state.current_patient_id = selected_id
            with st.spinner("Running AI workflow..."):
                run_workflow_phase1(selected_id)
            st.rerun()

    st.divider()

    if st.session_state.workflow_phase == "awaiting_approval":
        interrupt_data = st.session_state.interrupt_data or {}
        st.markdown("### Human Approval Required")
        st.error("This patient has been flagged as HIGH/CRITICAL risk. Clinician review needed.")

        with st.expander("View Escalation Details", expanded=True):
            st.text(interrupt_data.get("escalation_message", ""))
            st.text(interrupt_data.get("summary", ""))

        col_a, col_r, col_e = st.columns(3)
        if col_a.button("Approve — Send Reminders", type="primary", use_container_width=True):
            with st.spinner("Resuming workflow..."):
                run_workflow_phase2("approve")
            st.rerun()
        if col_r.button("Reject — No Action", use_container_width=True):
            with st.spinner("Closing case..."):
                run_workflow_phase2("reject")
            st.rerun()
        if col_e.button("Escalate — Immediate Intervention", use_container_width=True):
            with st.spinner("Escalating..."):
                run_workflow_phase2("escalate")
            st.rerun()

    elif st.session_state.workflow_phase == "complete" and st.session_state.final_output:
        st.markdown("### Follow-Up Plan")
        render_results(st.session_state.final_output)

        history_entry = {
            "patient_id": selected_id,
            "patient_name": st.session_state.final_output.get("patient_name"),
            "risk_level": st.session_state.final_output.get("risk_level"),
            "status": st.session_state.final_output.get("status")
        }
        if not any(h["patient_id"] == selected_id for h in st.session_state.history):
            st.session_state.history.append(history_entry)

    if st.session_state.history:
        with st.expander("Session History"):
            st.dataframe(pd.DataFrame(st.session_state.history), use_container_width=True)


if __name__ == "__main__":
    main()
