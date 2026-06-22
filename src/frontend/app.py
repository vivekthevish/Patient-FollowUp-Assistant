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


# Custom cohesive CSS theme styling with dark/light mode support
def load_css():
    st.markdown(
        """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Mono:wght@400;500&display=swap');
    
    /* Dark/Light Mode Variables */
    :root {
        --bg-primary: #FFFFFF;
        --bg-secondary: #F8FAFC;
        --bg-tertiary: #F1F5F9;
        --text-primary: #0F172A;
        --text-secondary: #475569;
        --text-tertiary: #64748B;
        --border-color: #E2E8F0;
        --border-light: #F1F5F9;
        --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        --shadow-md: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
    }
    
    @media (prefers-color-scheme: dark) {
        :root {
            --bg-primary: #1E293B;
            --bg-secondary: #0F172A;
            --bg-tertiary: #334155;
            --text-primary: #F1F5F9;
            --text-secondary: #CBD5E1;
            --text-tertiary: #94A3B8;
            --border-color: #334155;
            --border-light: #475569;
            --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.3);
            --shadow-md: 0 1px 3px 0 rgba(0, 0, 0, 0.4);
        }
    }
    
    /* Global App Background and Typography Override */
    .stApp {
        background-color: var(--bg-secondary);
        font-family: 'DM Sans', sans-serif;
        color: var(--text-primary);
    }
    
    /* Clean Header bar alignment */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    .custom-header {
        background: var(--bg-primary);
        border-bottom: 2px solid var(--border-color);
        padding: 16px 32px;
        margin: -80px -80px 24px -80px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: var(--shadow-md);
    }
    
    .brand {
        display: flex;
        align-items: center;
        gap: 14px;
    }
    
    .brand-icon {
        width: 40px;
        height: 40px;
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%);
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: 20px;
        box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.3);
    }
    
    .brand-name {
        font-size: 18px;
        font-weight: 700;
        color: var(--text-primary);
        letter-spacing: -0.02em;
    }
    
    .brand-sub {
        font-size: 11px;
        color: var(--text-tertiary);
        font-weight: 500;
    }
    
    /* Sidebar adjustments */
    [data-testid="stSidebar"] {
        background-color: var(--bg-primary);
        border-right: 2px solid var(--border-color);
    }
    
    [data-testid="stSidebar"] * {
        color: var(--text-primary) !important;
    }
    
    /* Standard Card containers */
    .card {
        background: var(--bg-primary);
        border: 2px solid var(--border-color);
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: var(--shadow-md);
    }
    
    .card-header {
        font-size: 13px;
        font-weight: 700;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 18px;
        padding-bottom: 10px;
        border-bottom: 2px solid var(--border-light);
    }
    
    /* Micro Metric Cards */
    .metric-box {
        background: var(--bg-primary);
        border: 2px solid var(--border-color);
        border-radius: 10px;
        padding: 16px;
        text-align: center;
        box-shadow: var(--shadow-sm);
    }
    .metric-val {
        font-size: 28px;
        font-weight: 700;
        color: var(--text-primary);
        line-height: 1;
        margin-bottom: 4px;
    }
    .metric-lbl {
        font-size: 12px;
        color: var(--text-tertiary);
        font-weight: 500;
    }
    
    /* Design System Badges - Enhanced Contrast */
    .badge {
        display: inline-flex;
        align-items: center;
        padding: 6px 12px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.02em;
        border: 2px solid;
    }
    .badge-red {
        background: #FEE2E2;
        color: #991B1B;
        border-color: #DC2626;
    }
    .badge-amber {
        background: #FEF3C7;
        color: #92400E;
        border-color: #F59E0B;
    }
    .badge-blue {
        background: #DBEAFE;
        color: #1E40AF;
        border-color: #3B82F6;
    }
    .badge-green {
        background: #DCFCE7;
        color: #166534;
        border-color: #22C55E;
    }
    .badge-gray {
        background: var(--bg-tertiary);
        color: var(--text-primary);
        border-color: var(--border-color);
    }
    
    @media (prefers-color-scheme: dark) {
        .badge-red {
            background: #7F1D1D;
            color: #FEE2E2;
            border-color: #EF4444;
        }
        .badge-amber {
            background: #78350F;
            color: #FEF3C7;
            border-color: #FBBF24;
        }
        .badge-blue {
            background: #1E3A8A;
            color: #DBEAFE;
            border-color: #60A5FA;
        }
        .badge-green {
            background: #14532D;
            color: #DCFCE7;
            border-color: #4ADE80;
        }
    }
    
    /* Structured Text Panels */
    .info-panel {
        background: var(--bg-tertiary);
        border: 2px solid var(--border-color);
        border-radius: 8px;
        padding: 14px 16px;
        font-size: 13px;
        line-height: 1.6;
        color: var(--text-primary);
        font-weight: 500;
    }
    
    .clinical-quote {
        background: #DBEAFE;
        border-left: 4px solid #2563EB;
        border-radius: 4px 8px 8px 4px;
        padding: 12px 14px;
        font-size: 13px;
        line-height: 1.6;
        color: #1E40AF;
        margin-top: 8px;
        font-weight: 500;
    }
    
    @media (prefers-color-scheme: dark) {
        .clinical-quote {
            background: #1E3A8A;
            color: #DBEAFE;
            border-left-color: #60A5FA;
        }
    }
    
    .escalation-alert-panel {
        background: #FEE2E2;
        border: 2px solid #DC2626;
        border-left: 4px solid #991B1B;
        border-radius: 8px;
        padding: 14px;
        font-size: 13px;
        line-height: 1.6;
        color: #7F1D1D;
        margin: 12px 0;
        font-weight: 600;
    }
    
    @media (prefers-color-scheme: dark) {
        .escalation-alert-panel {
            background: #7F1D1D;
            color: #FEE2E2;
            border-color: #EF4444;
            border-left-color: #DC2626;
        }
    }

    /* Tab Customizations styling overrides */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: var(--bg-tertiary);
        padding: 6px 6px 0 6px;
        border-radius: 10px 10px 0 0;
        border: 2px solid var(--border-color);
    }
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        white-space: pre;
        background-color: transparent;
        border-radius: 8px 8px 0 0;
        color: var(--text-tertiary);
        font-weight: 600;
        font-size: 13px;
        padding: 0 16px;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background-color: var(--bg-primary);
        color: #2563EB;
        border: 2px solid var(--border-color);
        border-bottom: none;
    }
    
    /* Streamlit Input Fields Enhancement */
    .stTextInput input, .stTextArea textarea, .stSelectbox select, .stNumberInput input {
        background-color: var(--bg-primary) !important;
        color: var(--text-primary) !important;
        border: 2px solid var(--border-color) !important;
        font-weight: 500 !important;
    }
    
    .stTextInput input:focus, .stTextArea textarea:focus, .stSelectbox select:focus {
        border-color: #2563EB !important;
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1) !important;
    }
    
    /* Button Enhancements */
    .stButton button {
        font-weight: 600 !important;
        border: 2px solid transparent !important;
        transition: all 0.2s ease !important;
    }
    
    .stButton button[kind="primary"] {
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%) !important;
        color: white !important;
        box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.3) !important;
    }
    
    .stButton button[kind="primary"]:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 8px -1px rgba(37, 99, 235, 0.4) !important;
    }
    
    /* Expander Enhancement */
    .streamlit-expanderHeader {
        background-color: var(--bg-primary) !important;
        border: 2px solid var(--border-color) !important;
        border-radius: 8px !important;
        color: var(--text-primary) !important;
        font-weight: 600 !important;
    }
    
    .streamlit-expanderContent {
        background-color: var(--bg-primary) !important;
        border: 2px solid var(--border-color) !important;
        border-top: none !important;
        color: var(--text-primary) !important;
    }
    
    /* Markdown text color fix */
    .stMarkdown, .stMarkdown p, .stMarkdown li, .stMarkdown h1, .stMarkdown h2,
    .stMarkdown h3, .stMarkdown h4, .stMarkdown h5, .stMarkdown h6 {
        color: var(--text-primary) !important;
    }
    
    /* Radio button enhancement */
    .stRadio label {
        color: var(--text-primary) !important;
        font-weight: 500 !important;
    }
    
    /* Metric enhancement */
    [data-testid="stMetric"] {
        background-color: var(--bg-primary);
        padding: 12px;
        border-radius: 8px;
        border: 2px solid var(--border-color);
    }
    
    [data-testid="stMetricLabel"] {
        color: var(--text-secondary) !important;
        font-weight: 600 !important;
    }
    
    [data-testid="stMetricValue"] {
        color: var(--text-primary) !important;
        font-weight: 700 !important;
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
    if "workflow_total" not in st.session_state:
        st.session_state.workflow_total = 0


def render_header():
    today_str = datetime.today().strftime("%d %B %Y").lstrip("0")
    st.markdown(
        f"""
    <div class="custom-header">
        <div class="brand">
            <div class="brand-icon">🏥</div>
            <div>
                <div class="brand-name">AI Patient Follow-Up Assistant</div>
                <div class="brand-sub">Capstone Enterprise Clinical Dashboard · Theme 9</div>
            </div>
        </div>
        <div style="font-size: 13px; color: #475569; font-weight: 600; background: #F1F5F9; padding: 6px 14px; border-radius: 20px;">
            📅 System Date: <span style="color: #2563EB;">{today_str}</span>
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
        try:
            res = requests.post(f"{API_BASE_URL}/workflow/run")
            if res.status_code == 202:
                job_data = res.json()
                st.session_state.last_job_id = job_data.get("job_id")
                st.session_state.workflow_running = True
                st.session_state.workflow_total = job_data.get("total", 0)
            else:
                st.error("Workflow initialization error.")
        except Exception as e:
            st.error(f"Error connecting: {e}")

    # Real-time progress tracking with polling
    if st.session_state.workflow_running and st.session_state.last_job_id:
        progress_placeholder = st.empty()
        status_placeholder = st.empty()
        
        try:
            while True:
                status_res = requests.get(
                    f"{API_BASE_URL}/workflow/status/{st.session_state.last_job_id}"
                )
                
                if status_res.status_code == 200:
                    status_data = status_res.json()
                    processed = status_data.get("processed", 0)
                    total = status_data.get("total", st.session_state.workflow_total)
                    status = status_data.get("status", "running")
                    
                    # Calculate progress percentage
                    if total > 0:
                        progress_pct = processed / total
                        progress_placeholder.progress(progress_pct, text=f"Processing patients: {processed}/{total}")
                    else:
                        progress_placeholder.progress(0, text="Initializing workflow...")
                    
                    # Check if completed or failed
                    if status == "completed":
                        progress_placeholder.progress(1.0, text=f"Completed: {processed}/{total} patients processed")
                        st.session_state.workflow_results = status_data
                        status_placeholder.success("✅ Workflow completed successfully! All patients processed.")
                        st.session_state.workflow_running = False
                        time.sleep(1)  # Brief pause to show completion
                        break
                    elif status == "failed":
                        error_msg = status_data.get("error", "Unknown error")
                        status_placeholder.error(f"❌ Workflow failed: {error_msg}")
                        st.session_state.workflow_running = False
                        break
                    
                    # Still running, wait before next poll
                    time.sleep(1)
                else:
                    status_placeholder.error("Failed to fetch workflow status")
                    st.session_state.workflow_running = False
                    break
                    
        except Exception as e:
            status_placeholder.error(f"Error tracking workflow: {e}")
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
        
        # Calculate days pending and days overdue
        try:
            created_date = datetime.fromisoformat(esc["created_at"].replace("Z", "+00:00"))
            today = datetime.now()
            days_pending = (today - created_date).days
            
            # Calculate days overdue from follow-up date
            followup_date = datetime.fromisoformat(esc["follow_up_date"]).date()
            today_date = date.today()
            days_overdue = (today_date - followup_date).days
        except Exception:
            days_pending = 0
            days_overdue = 0

        st.markdown(
            f"""
            <div class="card" style="border-top: 4px solid {"#DC2626" if is_pending else "#64748B"};">
                <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px;">
                    <div style="flex:1;">
                        <h4 style="margin:0; color:var(--text-primary);">Patient: {esc["patient_name"]} <span style="font-size:12px; font-weight:400; color:var(--text-tertiary);">(ID: {esc["patient_id"]})</span></h4>
                        <div style="margin-top:8px; display:flex; gap:16px; flex-wrap:wrap;">
                            <small style="color:var(--text-secondary);"><strong>Missed Appointment:</strong> {esc["follow_up_date"]} <span style="color:#DC2626; font-weight:600;">({days_overdue} days overdue)</span></small>
                            <small style="color:var(--text-secondary);"><strong>Escalation Created:</strong> {esc["created_at"][:10]} <span style="color:#F59E0B; font-weight:600;">({days_pending} days pending)</span></small>
                        </div>
                    </div>
                    <div>{badge_element}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Display key metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                label="Days Since Missed Appointment",
                value=f"{days_overdue} days",
                delta=None,
            )
        with col2:
            st.metric(
                label="Escalation Pending Duration",
                value=f"{days_pending} days",
                delta=None,
            )
        with col3:
            urgency_label = "🔴 CRITICAL" if days_overdue > 7 else "🟡 HIGH" if days_overdue > 3 else "🟠 MODERATE"
            st.markdown(
                f"<div style='text-align:center; padding:12px; background:var(--bg-tertiary); border-radius:8px; border:2px solid var(--border-color);'>"
                f"<div style='font-size:11px; color:var(--text-tertiary); font-weight:600; margin-bottom:4px;'>URGENCY LEVEL</div>"
                f"<div style='font-size:16px; font-weight:700; color:var(--text-primary);'>{urgency_label}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        st.markdown(
            "**🤖 AI-Generated Clinical Escalation Report:**"
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
