import streamlit as st
import pandas as pd
from datetime import datetime, date
import requests
import time

# Configuration point for the API backend
API_BASE_URL = "http://127.0.0.1:8000/api/v1"

# Page configuration
st.set_page_config(
    page_title="AI Patient Follow-Up Assistant",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)


# Custom cohesive CSS theme styling mimicking the modern wireframe layout
def load_css():
    st.markdown(
        """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Mono:wght@400;500&display=swap');
    
    /* Global App Background and Typography Override */
    .stApp {
        background-color: #F8FAFC;
        font-family: 'DM Sans', sans-serif;
    }
    
    /* Clean Header bar alignment */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    .custom-header {
        background: #FFFFFF;
        border-bottom: 1px solid #E2E8F0;
        padding: 16px 32px;
        margin: -80px -80px 24px -80px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
    }
    
    .brand {
        display: flex;
        align-items: center;
        gap: 14px;
    }
    
    .brand-icon {
        width: 40px;
        height: 40px;
        background: #2563EB;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: 20px;
    }
    
    .brand-name {
        font-size: 18px;
        font-weight: 700;
        color: #0F172A;
        letter-spacing: -0.02em;
    }
    
    .brand-sub {
        font-size: 11px;
        color: #64748B;
        font-weight: 500;
    }
    
    /* Sidebar adjustments */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #E2E8F0;
    }
    
    /* Standard Card containers */
    .card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.02);
    }
    
    .card-header {
        font-size: 13px;
        font-weight: 700;
        color: #475569;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 18px;
        padding-bottom: 10px;
        border-bottom: 1px solid #F1F5F9;
    }
    
    /* Micro Metric Cards */
    .metric-box {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.02);
    }
    .metric-val {
        font-size: 28px;
        font-weight: 700;
        color: #0F172A;
        line-height: 1;
        margin-bottom: 4px;
    }
    .metric-lbl {
        font-size: 12px;
        color: #64748B;
        font-weight: 500;
    }
    
    /* Design System Badges */
    .badge {
        display: inline-flex;
        align-items: center;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.02em;
    }
    .badge-red { background: #FEF2F2; color: #DC2626; border: 1px solid #FEE2E2; }
    .badge-amber { background: #FFFBEB; color: #D97706; border: 1px solid #FEF3C7; }
    .badge-blue { background: #EFF6FF; color: #2563EB; border: 1px solid #DBEAFE; }
    .badge-green { background: #F0FDF4; color: #16A34A; border: 1px solid #DCFCE7; }
    .badge-gray { background: #F8FAFC; color: #475569; border: 1px solid #E2E8F0; }
    
    /* Structured Text Panels */
    .info-panel {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 14px 16px;
        font-size: 12px;
        line-height: 1.6;
        color: #334155;
    }
    
    .clinical-quote {
        background: #F0F9FF;
        border-left: 4px solid #0EA5E9;
        border-radius: 4px 8px 8px 4px;
        padding: 12px 14px;
        font-size: 12px;
        line-height: 1.6;
        color: #0369A1;
        margin-top: 8px;
    }
    
    .escalation-alert-panel {
        background: #FFF5F5;
        border: 1px solid #FEB2B2;
        border-left: 4px solid #E53E3E;
        border-radius: 8px;
        padding: 14px;
        font-size: 12px;
        line-height: 1.6;
        color: #9B2C2C;
        margin: 12px 0;
    }

    /* Tab Customizations styling overrides */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #F1F5F9;
        padding: 6px 6px 0 6px;
        border-radius: 10px 10px 0 0;
    }
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        white-space: pre;
        background-color: transparent;
        border-radius: 8px 8px 0 0;
        color: #64748B;
        font-weight: 600;
        font-size: 13px;
        padding: 0 16px;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background-color: #FFFFFF;
        color: #2563EB;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )


def init_session_state():
    if "workflow_running" not in st.session_state:
        st.session_state.workflow_running = False
    if "last_job_id" not in st.session_state:
        st.session_state.last_job_id = None
    if "workflow_results" not in st.session_state:
        st.session_state.workflow_results = None


def render_header():
    st.markdown(
        """
    <div class="custom-header">
        <div class="brand">
            <div class="brand-icon">🏥</div>
            <div>
                <div class="brand-name">AI Patient Follow-Up Assistant</div>
                <div class="brand-sub">Capstone Enterprise Clinical Dashboard · Theme 9</div>
            </div>
        </div>
        <div style="font-size: 13px; color: #475569; font-weight: 600; background: #F1F5F9; padding: 6px 14px; border-radius: 20px;">
            📅 System Date: <span style="color: #2563EB;">15 June 2026</span>
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )


def render_sidebar_metrics():
    all_patients = []
    pending_escalations = []

    try:
        r_patients = requests.get(
            f"{API_BASE_URL}/patients", params={"followup_status": "all"}
        )
        if r_patients.status_code == 200:
            all_patients = r_patients.json().get("patients", [])

        r_esc = requests.get(
            f"{API_BASE_URL}/escalations", params={"status": "pending"}
        )
        if r_esc.status_code == 200:
            pending_escalations = r_esc.json().get("escalations", [])
    except Exception:
        pass

    total = len(all_patients)
    completed = len(
        [p for p in all_patients if p.get("followup_status") == "completed"]
    )
    active_esc = len(pending_escalations)

    with st.sidebar:
        st.markdown(
            '<div class="card-header" style="margin-top:10px;">📋 System Statistics</div>',
            unsafe_allow_html=True,
        )

        # Grid layout for sidebar statistics
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(
                f'<div class="metric-box"><div class="metric-val">{total}</div><div class="metric-lbl">Total</div></div>',
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(
                f'<div class="metric-box"><div class="metric-val" style="color:#16A34A;">{completed}</div><div class="metric-lbl">Attended</div></div>',
                unsafe_allow_html=True,
            )

        st.markdown("<div style='margin-top:12px;'></div>", unsafe_allow_html=True)
        st.markdown(
            f'<div class="metric-box" style="border-left: 4px solid #DC2626;"><div class="metric-val" style="color:#DC2626;">{active_esc}</div><div class="metric-lbl">Open Escalations</div></div>',
            unsafe_allow_html=True,
        )

        st.markdown("---")
        st.markdown(
            "💡 **RAG Engine:** Connected to ChromaDB vector layers containing current medical protocol references."
        )


# Tab 1: Patient Intake Form Layout
def render_patient_intake():
    st.markdown("### 📋 New Patient Electronic Intake Registration")
    st.markdown(
        "Register incoming discharge configurations directly into the monitoring subsystem."
    )

    with st.container():
        with st.form("intake_form", clear_on_submit=True):
            st.markdown(
                '<div class="card-header">Patient Identity & Clinical Metadata</div>',
                unsafe_allow_html=True,
            )

            col1, col2, col3 = st.columns(3)
            with col1:
                patient_name = st.text_input("Full Name *")
            with col2:
                age = st.number_input("Age *", min_value=18, max_value=85, value=45)
            with col3:
                gender = st.selectbox("Gender *", ["Male", "Female", "Other"])

            col4, col5, col6 = st.columns(3)
            with col4:
                email = st.text_input("Email Address *")
            with col5:
                phone = st.text_input("Phone Number")
            with col6:
                severity = st.selectbox(
                    "Clinical Severity Tier *", ["Critical", "High", "Moderate", "Low"]
                )

            st.markdown(
                '<div class="card-header" style="margin-top:20px;">Discharge Parameters</div>',
                unsafe_allow_html=True,
            )
            col7, col8 = st.columns(2)
            with col7:
                diagnosis = st.text_input("Primary Diagnosis Summary *")
            with col8:
                follow_up_date = st.date_input(
                    "Target Follow-up Appointment Date *", value=date(2026, 6, 20)
                )

            attending_doctor = st.text_input(
                "Attending Physician *", value="Dr. Anjali Sharma"
            )
            doctor_notes = st.text_area(
                "Physician Discharge Instructions & Notes (Min. 10 chars) *", height=120
            )

            st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
            submit_btn = st.form_submit_button(
                "Save Entry to Database Record", type="primary"
            )

            if submit_btn:
                if not patient_name or not email or not diagnosis or not doctor_notes:
                    st.error("Please fill out all fields marked with (*)")
                else:
                    payload = {
                        "patient_name": patient_name,
                        "age": int(age),
                        "gender": gender,
                        "email": email,
                        "phone": phone if phone else None,
                        "diagnosis": diagnosis,
                        "follow_up_date": follow_up_date.isoformat(),
                        "doctor_notes": doctor_notes,
                        "attending_doctor": attending_doctor,
                        "severity": severity,
                    }
                    try:
                        res = requests.post(f"{API_BASE_URL}/patients", json=payload)
                        if res.status_code == 201:
                            st.success(
                                f"🎉 Secure record stored successfully! Patient ID generated: {res.json()['patient_id']}"
                            )
                        else:
                            st.error(
                                f"Backend validation failed: {res.json().get('detail')}"
                            )
                    except Exception as e:
                        st.error(f"Could not reach API server instance: {e}")


# Tab 2: Patient Management Queue Layout
def render_patient_management():
    st.markdown("### 👥 Active Monitoring & Patient Queue")

    # Grid search filtering row layout
    filter_box = st.container()
    with filter_box:
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            search_query = st.text_input(
                "🔍 Quick Search",
                placeholder="Filter by patient name, diagnosis or email identification...",
            )
        with c2:
            severity_filter = st.selectbox(
                "Severity Classification",
                ["all", "Critical", "High", "Moderate", "Low"],
            )
        with c3:
            outcome_filter = st.selectbox(
                "Follow-up Lifecycle State", ["all", "pending", "completed"]
            )

    # Engine Activation Bar Config
    st.markdown(
        """
        <div style="background: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 8px; padding: 16px; margin: 16px 0; display:flex; justify-content:space-between; align-items:center;">
            <div>
                <span style="font-weight:700; color:#1E40AF; font-size:14px;">LangGraph Agentic Evaluation Routine</span><br/>
                <span style="font-size:12px; color:#1E40AF;">Scans pending records, cross-references logs, crafts customized communication, or automatically generates medical escalation alerts.</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("▶️ Execute Automation Engine Loop Run", type="primary"):
        with st.spinner("Processing background agent operations..."):
            try:
                res = requests.post(f"{API_BASE_URL}/workflow/run")
                if res.status_code == 202:
                    st.session_state.last_job_id = res.json().get("job_id")
                    st.session_state.workflow_running = True
                else:
                    st.error("Workflow initialization error.")
            except Exception as e:
                st.error(f"Error connecting: {e}")

    # Handling pseudo async interface update tracking
    if st.session_state.workflow_running and st.session_state.last_job_id:
        p_bar = st.progress(0)
        for p in [25, 60, 90, 100]:
            time.sleep(0.3)
            p_bar.progress(p)
        try:
            status_res = requests.get(
                f"{API_BASE_URL}/workflow/status/{st.session_state.last_job_id}"
            )
            if status_res.status_code == 200:
                st.session_state.workflow_results = status_res.json()
                st.success("Analysis cycle concluded successfully!")
            st.session_state.workflow_running = False
        except Exception:
            st.session_state.workflow_running = False

    # Pull and cleanly map down tabular results
    params = {}
    if outcome_filter != "all":
        params["followup_status"] = outcome_filter
    if severity_filter != "all":
        params["severity"] = severity_filter
    if search_query:
        params["search"] = search_query

    try:
        res = requests.get(f"{API_BASE_URL}/patients", params=params)
        patients_list = res.json().get("patients", []) if res.status_code == 200 else []
    except Exception:
        st.error("Unable to contact live services to fetch patient records.")
        return

    if not patients_list:
        st.info("No monitoring entries found matching selected parameter matrices.")
        return

    # Visual layout configuration styling mapping logic for rows block entries
    for p in patients_list:
        p_id = p["patient_id"]
        sev_style = (
            "badge-red"
            if p["severity"] == "Critical"
            else ("badge-amber" if p["severity"] == "High" else "badge-blue")
        )
        stat_style = (
            "badge-green" if p["followup_status"] == "completed" else "badge-amber"
        )

        with st.expander(
            f"👤 {p['patient_name']} ({p_id}) — Diagnosis: {p['diagnosis']}"
        ):
            m1, m2 = st.columns([1, 1])
            with m1:
                st.markdown(
                    f"**Urgency Stratification:** <span class='badge {sev_style}'>{p['severity']}</span>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"**Appointment Follow-up Target:** `{p['follow_up_date']}`"
                )
                st.markdown(
                    f"**Current State Indicator:** <span class='badge {stat_style}'>{p['followup_status'].upper()}</span>",
                    unsafe_allow_html=True,
                )

                # Render underlying reminders nested models if existing within item context payload
                rem = p.get("reminder")
                if rem:
                    st.markdown(
                        "<div style='margin-top:14px;'><b>Communication Outbound Summary Logs:</b></div>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f"📋 Send Timeline Stamps: `{rem.get('reminder_sent_dates')}`"
                    )
                    st.markdown(
                        f"📬 Mail Transfer Status Flag: `{rem.get('email_status')}`"
                    )

            with m2:
                if p.get("risk_score") is not None:
                    st.metric(
                        label="System Synthesized Risk Value Index",
                        value=f"{p['risk_score']} / 10",
                    )
                if p.get("patient_summary"):
                    st.markdown("**🤖 AI Clinical Extraction Executive Summary:**")
                    st.markdown(
                        f"<div class='info-panel'>{p['patient_summary']}</div>",
                        unsafe_allow_html=True,
                    )
                if rem and rem.get("reminder_text"):
                    st.markdown("**💬 Generated Outbound Communications Copy:**")
                    st.markdown(
                        f"<div class='clinical-quote'>{rem.get('reminder_text')}</div>",
                        unsafe_allow_html=True,
                    )

            # Manual override diagnostic option forms row panel blocks injection
            st.markdown("<br/>", unsafe_allow_html=True)
            st.markdown("##### ⚙️ Immediate Lifecycle Status Adjustments")
            sc1, sc2 = st.columns([2, 1])
            with sc1:
                selected_next_state = st.selectbox(
                    "Set confirmed outcome update choice",
                    ["pending", "completed"],
                    index=0 if p["followup_status"] == "pending" else 1,
                    key=f"state_choice_{p_id}",
                )
            with sc2:
                if st.button("Commit Status Update", key=f"commit_action_{p_id}"):
                    try:
                        patch_payload = {
                            "followup_status": selected_next_state,
                            "updated_by": "UI Console Admin",
                        }
                        patch_res = requests.patch(
                            f"{API_BASE_URL}/patients/{p_id}/outcome",
                            json=patch_payload,
                        )
                        if patch_res.status_code == 200:
                            st.success("Database record modified!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error executing transaction: {e}")


# Tab 3: Escalation Action Center Layout
def render_escalations():
    st.markdown("### ⚠️ Critical Escalations Management Center")
    st.markdown(
        "Active overview lists targeting clinical entries requiring intervention due to missed follow-ups."
    )

    status_filter = st.radio(
        "Display Filter Category Mode", ["pending", "closed", "all"], horizontal=True
    )

    try:
        res = requests.get(
            f"{API_BASE_URL}/escalations", params={"status": status_filter}
        )
        escalations = (
            res.json().get("escalations", []) if res.status_code == 200 else []
        )
    except Exception:
        st.error("Failed to fetch current system escalation logs.")
        return

    if not escalations:
        st.success(
            "Clean Desk! No open clinical alerts discovered under this filtering configuration."
        )
        return

    for esc in escalations:
        is_pending = esc["escalation_status"] == "pending"
        badge_element = (
            '<span class="badge badge-red">⚠️ UNRESOLVED ALERT</span>'
            if is_pending
            else '<span class="badge badge-green">✅ RESOLVED TRACKING</span>'
        )

        st.markdown(
            f"""
            <div class="card" style="border-top: 4px solid {"#DC2626" if is_pending else "#64748B"};">
                <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px;">
                    <div>
                        <h4 style="margin:0; color:#0F172A;">Patient: {esc["patient_name"]} <span style="font-size:12px; font-weight:400; color:#64748B;">(ID: {esc["patient_id"]})</span></h4>
                        <small style="color:#64748B;">Target Appointment Date: {esc["follow_up_date"]} | Discovered Trigger Log: {esc["created_at"]}</small>
                    </div>
                    <div>{badge_element}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            "**🤖 Synthesized Patient Clinical Analysis Escalation Report Summary:**"
        )
        st.markdown(
            f"<div class='escalation-alert-panel'>{esc['escalation_report']}</div>",
            unsafe_allow_html=True,
        )

        if is_pending:
            with st.container():
                c1, c2 = st.columns([2, 1])
                with c1:
                    signature_auth = st.text_input(
                        "Enter Clinician Sign-off Validation Credentials Code *",
                        key=f"sign_{esc['escalation_id']}",
                    )
                with c2:
                    st.markdown(
                        "<div style='margin-top:24px;'></div>", unsafe_allow_html=True
                    )
                    if st.button(
                        "Authorize Resolution & Close Ticket",
                        key=f"close_btn_{esc['escalation_id']}",
                        type="secondary",
                    ):
                        if not signature_auth:
                            st.error(
                                "Clinician sign-off is required to change this status."
                            )
                        else:
                            try:
                                close_payload = {"closed_by": signature_auth}
                                close_res = requests.patch(
                                    f"{API_BASE_URL}/escalations/{esc['escalation_id']}/close",
                                    json=close_payload,
                                )
                                if close_res.status_code == 200:
                                    st.success(
                                        "Ticket closed and archived successfully."
                                    )
                                    st.rerun()
                            except Exception as e:
                                st.error(f"Error dispatching resolution payload: {e}")
        else:
            st.markdown(
                f"🔒 *Resolution Record signed closed by user identity: **{esc.get('closed_at')}***"
            )
        st.markdown("<hr style='margin:20px 0;'/>", unsafe_allow_html=True)


# Main orchestrator function entry logic
def main():
    load_css()
    init_session_state()
    render_header()
    render_sidebar_metrics()

    # Create top level navigation blocks inside UI Frame
    tab1, tab2, tab3 = st.tabs(
        ["📋 Patient Intake", "👥 Patient Management", "⚠️ Escalations Desk"]
    )

    with tab1:
        render_patient_intake()
    with tab2:
        render_patient_management()
    with tab3:
        render_escalations()


if __name__ == "__main__":
    main()
