# REFINED DESIGN DOCUMENT — v2

## AI Patient Follow-Up Assistant

*API Reference · Database Schema · Agent Workflow · UI Components*

*Theme 9 — Healthcare Domain — IIT Roorkee Advanced PG Certification in AI Engineering*

**Stack:** FastAPI + LangGraph + Streamlit + AWS EC2 + AWS SES + AWS S3 + SQLite + ChromaDB + GPT-4o

**Submission Deadline: 25 June 2026**

---

## 1. System Overview

The AI Patient Follow-Up Assistant automates post-discharge patient follow-up using a three-agent LangGraph workflow. Staff register patients with a follow-up appointment date. The system determines which patients need reminders today and which have missed appointments, runs the appropriate agent, sends emails via AWS SES, and surfaces escalations for manual review.

| **Layer** | **Technology** | **Responsibility** | **Port** |
|---|---|---|---|
| Frontend | Streamlit | 3-tab UI: Patient Intake, Patient Management, Escalations | 8501 (public) |
| Backend API | FastAPI | All business logic, LangGraph orchestration, DB writes, SES calls | 8000 (internal) |
| Database | SQLite + SQLAlchemy | 3 tables: patients, reminders, escalations | EC2 local |
| Agent workflow | LangGraph + GPT-4o | Patient Summary Agent → Reminder Agent or Escalation Agent | FastAPI internal |
| RAG pipeline | LangChain + ChromaDB | Protocol PDF ingestion, embedding, retrieval for reminder generation | FastAPI internal |
| Email service | AWS SES | Reminder emails to patients | External API |
| File storage | AWS S3 | Disease-specific protocol PDFs for RAG | External |
| Hosting | AWS EC2 (t2.medium) | FastAPI + Streamlit + SQLite + ChromaDB on one instance | ap-south-1 |

---

## 2. Agent Workflow Design

The workflow is triggered by the "Run Follow-Up Workflow" button in Tab 2. LangGraph processes each qualifying patient sequentially. The router decides which path a patient takes based on two conditions.

### 2.1 Patient Selection Logic

Before agents run, FastAPI queries the patients table to split all patients into two groups:

| **Group** | **Condition** | **Agent path** |
|---|---|---|
| Reminder group | `(followup_date - current_date) IN (1, 3, 7)` | Patient Summary Agent → Reminder Agent |
| Escalation group | `current_date > followup_date` | Escalation Agent only |
| Skipped | All other patients (appointment too far, or already fully processed) | No agent runs |

> **ℹ Note:** A patient can only be in one group per run. Once `current_date > followup_date`, they move permanently to the escalation group and will never re-enter the reminder group.

### 2.2 Reminder Path — Patient Summary Agent

Runs for all patients in the reminder group.

| **Property** | **Detail** |
|---|---|
| Input | Patient record from patients table: `patient_name`, `age`, `diagnosis`, `doctor_notes`, `follow_up_date`, `risk_score` (if previously computed) |
| Action | Call GPT-4o to generate a 3-sentence patient summary and compute a risk score (0.0–10.0) based on diagnosis, age, and doctor notes |
| Output | `patient_summary` (string), `risk_score` (float) |
| DB write | `UPDATE patients SET patient_summary = ?, risk_score = ? WHERE patient_id = ?` |
| On failure | Log error, skip to next patient. Do not block Reminder Agent. |

### 2.3 Reminder Path — Reminder Agent

Runs immediately after Patient Summary Agent for each patient in the reminder group.

| **Property** | **Detail** |
|---|---|
| Step 1 — Duplicate check | Query reminders table: `SELECT reminder_sent_dates FROM reminders WHERE patient_id = ? ORDER BY created_at DESC LIMIT 1`. Parse the JSON array. If today's date exists in the array, SKIP this patient entirely. No email, no DB write. |
| Step 2 — RAG retrieval | Query ChromaDB using patient diagnosis as the search term. Retrieve top-3 chunks from disease-specific protocol PDFs stored in S3. Store as `rag_context` string. |
| Step 3 — LLM generation | Call GPT-4o with: `patient_summary` + `rag_context` + patient demographics. Generate a personalised reminder message (150–200 words). |
| Step 4 — DB write | INSERT into reminders: `patient_id`, `reminder_text`, `rag_context_json`, `followup_status = pending`, `reminder_sent_dates` = append today to existing array (or create new array if first reminder). |
| Step 5 — Email | Call AWS SES to send `reminder_text` to patient email. Update reminders row: `email_status = sent`, `email_sent_at = now`. On SES failure: `email_status = failed`, log error. |
| On failure | Catch all exceptions. Log error. Mark `email_status = failed`. Continue to next patient. |

> **⚠ Important:** The duplicate check in Step 1 is critical. Without it, if the button is clicked twice in a day, patients receive duplicate emails. Always check the `reminder_sent_dates` array before proceeding.

### 2.4 Escalation Path — Escalation Agent

Runs for patients where `current_date > followup_date`.

| **Property** | **Detail** |
|---|---|
| Step 1 — Duplicate check | Query escalations table: `SELECT id FROM escalations WHERE patient_id = ?`. If any row exists, SKIP. One escalation per patient maximum. |
| Step 2 — Deactivate reminder | `UPDATE reminders SET is_active = false WHERE patient_id = ?`. This hides the reminder from Tab 2 UI so the patient moves entirely to Tab 3. |
| Step 3 — LLM generation | Call GPT-4o with: `patient_summary` (if exists), `diagnosis`, `doctor_notes`, `follow_up_date`, `current_date`. Generate a clinical escalation summary explaining why follow-up was missed and recommended next actions. |
| Step 4 — DB write | INSERT into escalations: `patient_id`, `escalation_report`, `escalation_status = pending`, plus patient fields copied from patients table. |
| On failure | Catch all exceptions. Log error. Do not insert partial escalation row. Continue to next patient. |

### 2.5 LangGraph Graph Structure

The graph processes one patient at a time in a sequential loop. The router node decides the path after reading patient dates from state.

```python
# Pseudocode — LangGraph graph definition

graph = StateGraph(PatientWorkflowState)

graph.add_node("router",          router_node)
graph.add_node("patient_summary", patient_summary_agent)
graph.add_node("reminder",        reminder_agent)
graph.add_node("escalation",      escalation_agent)

graph.add_edge(START, "router")

graph.add_conditional_edges("router", route_patient, {
    "reminder":   "patient_summary",
    "escalation": "escalation",
    "skip":        END
})

graph.add_edge("patient_summary", "reminder")
graph.add_edge("reminder",         END)
graph.add_edge("escalation",       END)
```

---

## 3. Database Schema

Three tables. No foreign key complexity beyond `patient_id` references. Initialise with:

```bash
python -c "from src.db.models import Base, engine; Base.metadata.create_all(engine)"
```

### 3.1 Table: `patients`

One row per registered patient. Created by `POST /patients`. Patient Summary Agent updates `summary` and `risk_score`. Staff updates `followup_status` via `PATCH /patients/{id}/outcome`.

| **Column** | **Type** | **Constraints** | **Description** |
|---|---|---|---|
| `patient_id` | VARCHAR(10) | PK | Auto-generated. Format: P001–P999 |
| `patient_name` | VARCHAR(100) | NOT NULL | Full name from intake form |
| `age` | INTEGER | NOT NULL · CHECK 18–85 | Age at time of registration |
| `gender` | VARCHAR(10) | NOT NULL | Male / Female / Other |
| `email` | VARCHAR(200) | NOT NULL · UNIQUE | Patient email — used for SES reminder delivery |
| `phone` | VARCHAR(20) | NULLABLE | Optional contact number |
| `diagnosis` | VARCHAR(200) | NOT NULL | Diagnosis string from intake form dropdown |
| `follow_up_date` | DATE | NOT NULL | Hospital appointment date entered by staff at intake |
| `doctor_notes` | TEXT | NOT NULL | Free-text notes from attending doctor — fed into agent prompts |
| `attending_doctor` | VARCHAR(100) | NOT NULL | Doctor name — shown in reminder email |
| `severity` | VARCHAR(20) | NOT NULL · DEFAULT Moderate | Critical / High / Moderate / Low — entered by staff at intake |
| `patient_summary` | TEXT | NULLABLE | Generated by Patient Summary Agent on first workflow run |
| `risk_score` | FLOAT | NULLABLE · CHECK 0–10 | 0.0–10.0 computed by Patient Summary Agent |
| `followup_status` | VARCHAR(20) | DEFAULT pending | `pending` / `completed` — updated manually by staff in Tab 2 |
| `created_at` | DATETIME | NOT NULL · DEFAULT NOW | Registration timestamp |
| `updated_at` | DATETIME | NOT NULL · DEFAULT NOW | Updated on every change |

### 3.2 Table: `reminders`

One row per reminder cycle per patient. A patient can have up to 3 rows (Day-7, Day-3, Day-1 reminders). `is_active = false` hides the reminder from Tab 2 when patient moves to escalation.

| **Column** | **Type** | **Constraints** | **Description** |
|---|---|---|---|
| `reminder_id` | INTEGER | PK · AUTOINCREMENT | Auto ID |
| `patient_id` | VARCHAR(10) | NOT NULL · FK → patients | Owning patient |
| `reminder_text` | TEXT | NOT NULL | Full personalised reminder text generated by LLM |
| `rag_context_json` | TEXT | NULLABLE | JSON array of RAG chunks used: `[{source, page, chunk}]` |
| `reminder_sent_dates` | TEXT | NOT NULL · DEFAULT `"[]"` | JSON array of date strings, e.g. `["2026-05-31","2026-06-04"]`. Appended on each send. Used for duplicate check. |
| `email_status` | VARCHAR(20) | DEFAULT `not_sent` | `not_sent` / `sent` / `failed` |
| `email_sent_at` | DATETIME | NULLABLE | Timestamp of successful SES delivery |
| `is_active` | BOOLEAN | DEFAULT TRUE | Set to FALSE by Escalation Agent to hide from Tab 2 UI |
| `created_at` | DATETIME | NOT NULL · DEFAULT NOW | Row creation timestamp |
| `updated_at` | DATETIME | NOT NULL · DEFAULT NOW | Updated on email send or status change |

> **ℹ Note:** `reminder_sent_dates` is a JSON array stored as TEXT. In Python: `json.loads(row.reminder_sent_dates)` to read, `json.dumps([...])` to write. The duplicate check is: `if str(date.today()) in json.loads(reminder_sent_dates): skip`.

### 3.3 Table: `escalations`

One row per patient. Created by Escalation Agent when `current_date > follow_up_date`. Only one escalation per patient is allowed — agent checks before inserting. Staff closes via Tab 3.

| **Column** | **Type** | **Constraints** | **Description** |
|---|---|---|---|
| `escalation_id` | INTEGER | PK · AUTOINCREMENT | Auto ID |
| `patient_id` | VARCHAR(10) | NOT NULL · UNIQUE · FK → patients | One escalation per patient maximum. UNIQUE enforces this at DB level. |
| `patient_name` | VARCHAR(100) | NOT NULL | Copied from patients table for fast Tab 3 queries |
| `diagnosis` | VARCHAR(200) | NOT NULL | Copied from patients table |
| `follow_up_date` | DATE | NOT NULL | Copied from patients table |
| `doctor_notes` | TEXT | NULLABLE | Copied from patients table |
| `escalation_report` | TEXT | NOT NULL | LLM-generated clinical escalation summary |
| `escalation_status` | VARCHAR(20) | DEFAULT pending | `pending` / `closed` |
| `closed_at` | DATETIME | NULLABLE | Timestamp when staff marked as closed in Tab 3 |
| `created_at` | DATETIME | NOT NULL · DEFAULT NOW | When Escalation Agent created this row |

> **✦ Tip:** The UNIQUE constraint on `patient_id` in the escalations table is a safety net in addition to the agent's duplicate check. Even if the agent logic has a bug, the DB will reject a second INSERT for the same patient.

---

## 4. API Reference

7 endpoints total. Base URL: `http://localhost:8000/api/v1`

| **#** | **Method** | **Endpoint** | **Purpose** | **Tab** | **Owner** |
|---|---|---|---|---|---|
| 1 | POST | `/patients` | Register new patient | Tab 1 | Manisha |
| 2 | GET | `/patients` | Fetch all patients for queue table | Tab 2 | Manisha |
| 3 | PATCH | `/patients/{id}/outcome` | Mark patient follow-up as completed or pending | Tab 2 | Manisha |
| 4 | POST | `/workflow/run` | Trigger LangGraph agent workflow | Tab 2 | Vivek, Rohith |
| 5 | GET | `/workflow/status/{job_id}` | Poll workflow job progress | Tab 2 | Vivek |
| 6 | GET | `/escalations` | Fetch all pending escalations | Tab 3 | Vivek |
| 7 | PATCH | `/escalations/{id}/close` | Mark escalation as closed | Tab 3 | Vivek |

### 4.1 Register Patient

**`POST /api/v1/patients`**

*Register a new discharged patient. Inserts one row into the patients table. No agent runs at this point.*

**Triggered by:** Tab 1 — "Submit" button

**DB writes:** `patients` (INSERT 1 row)

**Request body**

```json
{
  "patient_name":     "Rajan Mehta",
  "age":              58,
  "gender":           "Male",
  "email":            "rajan.mehta@gmail.com",
  "phone":            "+91-9876543210",
  "diagnosis":        "Cardiac — myocardial infarction",
  "follow_up_date":   "2026-06-14",
  "doctor_notes":     "Moderate LV dysfunction. EF 38%. BP 154/92 at discharge.",
  "attending_doctor": "Dr. Anjali Sharma",
  "severity":         "Critical"
}
```

**Response — 201 Created**

```json
{
  "patient_id":    "P001",
  "patient_name":  "Rajan Mehta",
  "follow_up_date":"2026-06-14",
  "message":       "Patient registered successfully.",
  "created_at":    "2026-06-06T14:30:00Z"
}
```

**Response — 400 Bad Request**

```json
{
  "detail":     "Email already exists for another patient.",
  "error_code": "DUPLICATE_EMAIL"
}
```

### 4.2 Fetch All Patients

**`GET /api/v1/patients`**

*Returns all patients for the Tab 2 queue table. Only returns reminders where `is_active = true`. Patients with `is_active = false` reminders have moved to escalation and will not show reminder data.*

**Triggered by:** Tab 2 — page load

**DB writes:** None — read only

**Query parameters**

| **Parameter** | **Type** | **Description** |
|---|---|---|
| `followup_status` | string | Filter: `pending` / `completed` / `all` (default: `all`) |
| `severity` | string | Filter: `Critical` / `High` / `Moderate` / `Low` |
| `search` | string | Partial match on `patient_name` or `email` |

**Response — 200 OK**

```json
{
  "patients": [
    {
      "patient_id":      "P001",
      "patient_name":    "Rajan Mehta",
      "diagnosis":       "Cardiac — myocardial infarction",
      "severity":        "Critical",
      "follow_up_date":  "2026-06-14",
      "patient_summary": "Rajan Mehta, 58M, discharged following acute MI...",
      "risk_score":      8.4,
      "followup_status": "pending",
      "reminder": {
        "reminder_id":         1,
        "reminder_text":       "Dear Rajan, your follow-up appointment is on 14 June...",
        "rag_context_json":    "[{\"source\":\"cardiac_recovery_protocol.pdf\",...}]",
        "reminder_sent_dates": "[\"2026-06-07\",\"2026-06-11\"]",
        "email_status":        "sent",
        "email_sent_at":       "2026-06-07T09:00:00Z"
      }
    }
  ],
  "total": 25
}
```

> **ℹ Note:** The `reminder` object is `null` if no reminder has been generated yet for this patient. The `reminder_sent_dates` array shows all dates on which reminders were sent — useful for Tab 2 display.

### 4.3 Update Follow-Up Outcome

**`PATCH /api/v1/patients/{patient_id}/outcome`**

*Staff manually marks whether the patient attended their follow-up appointment. Updates `followup_status` on the patients table.*

**Triggered by:** Tab 2 — expanded row dropdown: "Attended" or "Pending"

**DB writes:** `patients` (UPDATE `followup_status`, `updated_at`)

**Request body**

```json
{
  "followup_status": "completed",
  "updated_by":      "Nurse Priya S."
}
```

**Response — 200 OK**

```json
{
  "patient_id":     "P001",
  "followup_status":"completed",
  "message":        "Follow-up outcome updated successfully.",
  "updated_at":     "2026-06-14T11:00:00Z"
}
```

### 4.4 Run Follow-Up Workflow

**`POST /api/v1/workflow/run`**

*Triggers the LangGraph agent workflow. Queries patients table to split into reminder group and escalation group. Processes each patient through the appropriate agent. Returns a job ID for polling.*

**Triggered by:** Tab 2 — "Run Follow-Up Workflow" button

**DB writes:** `patients` (UPDATE `patient_summary`, `risk_score`) · `reminders` (INSERT or UPDATE) · `escalations` (INSERT)

**Request body**

```json
{}
```
*(No body required — server selects qualifying patients automatically)*

**Response — 202 Accepted**

```json
{
  "job_id":             "job_abc123",
  "reminder_patients":  ["P001","P007","P014"],
  "escalation_patients":["P019"],
  "skipped_patients":   ["P022","P025"],
  "status":             "running",
  "message":            "Workflow started. 3 reminders, 1 escalation, 2 skipped."
}
```

### 4.5 Poll Workflow Status

**`GET /api/v1/workflow/status/{job_id}`**

*Returns current status of a running or completed workflow job. Streamlit polls this every 2 seconds after triggering `POST /workflow/run`.*

**Triggered by:** Streamlit polling loop after `POST /workflow/run`

**DB writes:** None — read only

**Response — 200 OK (completed)**

```json
{
  "job_id":  "job_abc123",
  "status":  "completed",
  "results": [
    { "patient_id":"P001", "path":"reminder",   "status":"success", "email_status":"sent" },
    { "patient_id":"P007", "path":"reminder",   "status":"success", "email_status":"sent" },
    { "patient_id":"P014", "path":"reminder",   "status":"failed",  "error":"SES delivery failed" },
    { "patient_id":"P019", "path":"escalation", "status":"success" }
  ],
  "completed_at":"2026-06-07T09:05:00Z"
}
```

### 4.6 Fetch Escalations

**`GET /api/v1/escalations`**

*Returns all escalation records with `escalation_status = pending` by default. Populates Tab 3 table.*

**Triggered by:** Tab 3 — page load

**DB writes:** None — read only

**Query parameters**

| **Parameter** | **Type** | **Description** |
|---|---|---|
| `status` | string | `pending` (default) / `closed` / `all` |

**Response — 200 OK**

```json
{
  "escalations": [
    {
      "escalation_id":    1,
      "patient_id":       "P019",
      "patient_name":     "Meena Reddy",
      "diagnosis":        "Hypertension — crisis",
      "follow_up_date":   "2026-06-05",
      "escalation_report":"Patient Meena Reddy (71F) missed her follow-up appointment on 5 June...",
      "escalation_status":"pending",
      "created_at":       "2026-06-06T09:00:00Z"
    }
  ],
  "total": 1
}
```

### 4.7 Close Escalation

**`PATCH /api/v1/escalations/{escalation_id}/close`**

*Staff marks an escalation as closed after taking action. Updates `escalation_status = closed` in the escalations table.*

**Triggered by:** Tab 3 — "Mark as Closed" button

**DB writes:** `escalations` (UPDATE `escalation_status = closed`, `closed_at = now`)

**Request body**

```json
{ "closed_by": "Dr. Anjali Sharma" }
```

**Response — 200 OK**

```json
{
  "escalation_id":    1,
  "patient_id":       "P019",
  "escalation_status":"closed",
  "closed_at":        "2026-06-07T11:30:00Z",
  "message":          "Escalation marked as closed."
}
```

---

## 5. API-to-Database Write Map

| **Endpoint** | **Method** | **Tables written** | **Tables read** |
|---|---|---|---|
| `POST /patients` | POST | `patients` (INSERT) | — |
| `GET /patients` | GET | — | `patients` + `reminders` (LEFT JOIN, `is_active=true`) |
| `PATCH /patients/{id}/outcome` | PATCH | `patients` (UPDATE `followup_status`, `updated_at`) | `patients` |
| `POST /workflow/run` | POST | `patients` (UPDATE summary, risk_score) · `reminders` (INSERT/UPDATE) · `escalations` (INSERT) | `patients` · `reminders` · `escalations` |
| `GET /workflow/status/{job_id}` | GET | — | In-memory job store (not DB) |
| `GET /escalations` | GET | — | `escalations` |
| `PATCH /escalations/{id}/close` | PATCH | `escalations` (UPDATE status, `closed_at`) | `escalations` |

---

## 6. Reminder Date Logic

This section documents exactly how the system determines when reminders fire and how dates are computed. This is the most implementation-critical logic in the entire system.

### 6.1 The Three Reminder Trigger Days

| **Trigger condition** | **What it means** | **Example (`follow_up_date = 2026-06-14`)** |
|---|---|---|
| `followup_date - current_date == 7` | 7 days before appointment | Reminder sent on 2026-06-07 |
| `followup_date - current_date == 3` | 3 days before appointment | Reminder sent on 2026-06-11 |
| `followup_date - current_date == 1` | 1 day before appointment | Reminder sent on 2026-06-13 |

### 6.2 The Escalation Trigger Condition

| **Trigger condition** | **What it means** | **Example (`follow_up_date = 2026-06-05`)** |
|---|---|---|
| `current_date > followup_date` | Appointment date has passed | If today is 2026-06-06 or later → escalation |

### 6.3 Python Implementation

```python
from datetime import date

def classify_patient(follow_up_date: date, current_date: date) -> str:
    diff = (follow_up_date - current_date).days
    if diff in (1, 3, 7):
        return "reminder"
    elif current_date > follow_up_date:
        return "escalation"
    else:
        return "skip"
```

### 6.4 Duplicate Check Implementation

```python
import json

def already_sent_today(reminder_sent_dates_json: str) -> bool:
    sent_dates = json.loads(reminder_sent_dates_json or "[]")
    return str(date.today()) in sent_dates

def append_today(reminder_sent_dates_json: str) -> str:
    sent_dates = json.loads(reminder_sent_dates_json or "[]")
    sent_dates.append(str(date.today()))
    return json.dumps(sent_dates)

# Example reminder_sent_dates after all 3 reminders:
# ["2026-06-07", "2026-06-11", "2026-06-13"]
```

---

## 7. UI Component Documentation

### 7.1 App Shell — All Tabs

| **Component** | **Details** |
|---|---|
| Fixed topbar | App name, deadline pill (25 Jun 2026), user avatar |
| Fixed sidebar | 3 nav items: Patient Intake, Patient Management, Escalations. Quick stats: total patients, pending follow-ups, open escalations. RAG status indicator. |
| Tab bar | 3 tabs matching sidebar nav. Escalations tab shows red count badge of pending escalations. |

### 7.2 Tab 1 — Patient Intake

| **Component** | **API called** | **Details** |
|---|---|---|
| Patient details form | `POST /patients` on submit | Fields: Patient name\*, Age\*, Gender\*, Email\*, Phone, Diagnosis\* (dropdown), Follow-up date\* (date picker — this is the appointment date), Doctor notes\*, Attending doctor\*, Severity\* (dropdown: Critical/High/Moderate/Low). All starred fields required. |
| Submit button | `POST /patients` | Validates required fields. Shows spinner on click. On 201: shows green success toast + clears form. On 400: shows error message with detail. |
| Success confirmation | — | Green box: "Patient [name] registered. Follow-up appointment: [date]. Reminders will be sent on [date-7], [date-3], [date-1]." Computed and shown client-side for staff reference. |

### 7.3 Tab 2 — Patient Management

| **Component** | **API called** | **Details** |
|---|---|---|
| "Run Follow-Up Workflow" button | `POST /workflow/run` → poll `GET /workflow/status` every 2s | Primary blue button at top. On click: fires workflow, shows progress bar, polls status. On complete: shows summary toast "X reminders sent, Y escalations created, Z skipped." Refreshes patient table automatically. |
| Patient queue table | `GET /patients` on load | Columns: Patient name, Diagnosis, Severity badge, Follow-up date, Email status badge, Follow-up status badge. Sorted by `follow_up_date ASC` then `severity_rank ASC`. Patients with `is_active=false` reminders (escalated) not shown here. |
| Search + filters | `GET /patients?search=&severity=&followup_status=` | Search input (300ms debounce). Severity dropdown. Follow-up status dropdown (pending/completed/all). |
| Expandable row | `GET /patients/{id}` on expand click | Clicking any row expands it to show: patient summary box, reminder text sent (full text), RAG context used (source PDF + page numbers), email address reminder was delivered to, email sent timestamp. |
| Follow-up outcome dropdown | `PATCH /patients/{id}/outcome` | Dropdown in expanded row: "Attended follow-up" (completed) / "Yet to attend" (pending). Fires PATCH immediately on selection change. Updates badge in table row. |

### 7.4 Tab 3 — Escalations

| **Component** | **API called** | **Details** |
|---|---|---|
| Escalation table | `GET /escalations` on load | Columns: Patient name, Diagnosis, Severity badge, Follow-up date (missed), Days overdue (computed: `current_date - follow_up_date`), Escalation status badge, Action. |
| Escalation summary row | — | Each row is expandable. Expanded view shows: full `escalation_report` text generated by LLM, patient `doctor_notes` for context. |
| "Mark as Closed" button | `PATCH /escalations/{id}/close` | Green button per row. On click: fires PATCH, removes row from table, shows toast "Escalation closed for [patient name]". Decrements sidebar badge count. |
| Empty state | — | If no pending escalations: shows green box "No open escalations. All patients are on track." |

---

## 8. Pydantic Models

> **ℹ Note:** Define all models in `src/api/models.py`.

### 8.1 `PatientCreate` — `POST /patients` request

```python
class PatientCreate(BaseModel):
    patient_name:     str      = Field(..., min_length=2)
    age:              int      = Field(..., ge=18, le=85)
    gender:           Literal["Male","Female","Other"]
    email:            EmailStr
    phone:            Optional[str] = None
    diagnosis:        str
    follow_up_date:   date
    doctor_notes:     str      = Field(..., min_length=10)
    attending_doctor: str
    severity:         Literal["Critical","High","Moderate","Low"]
```

### 8.2 `PatientOutcomeUpdate` — `PATCH /patients/{id}/outcome` request

```python
class PatientOutcomeUpdate(BaseModel):
    followup_status: Literal["completed","pending"]
    updated_by:      str
```

### 8.3 `EscalationClose` — `PATCH /escalations/{id}/close` request

```python
class EscalationClose(BaseModel):
    closed_by: str
```

---

## 9. AWS SES Email Setup

> **⚠ Important:** AWS SES starts in Sandbox mode. In Sandbox you can only send to verified email addresses. Verify 2–3 team member emails to use as test patients before the demo. Request production access (1–2 business days) to send to any address.

### 9.1 Setup Steps

| **Step** | **Action** |
|---|---|
| 1 | AWS Console → SES → Verified identities → Create identity → Email address. Verify sender email. |
| 2 | Verify 2–3 recipient test emails while in Sandbox mode. |
| 3 | IAM → `capstone-ec2-user` → Attach policy: `AmazonSESFullAccess`. |
| 4 | Add to `.env`: `SES_SENDER_EMAIL=noreply@...` and `AWS_REGION=ap-south-1`. |
| 5 | Test: `python -c "import boto3; ses=boto3.client('ses'); print(ses.list_verified_email_addresses())"` |

### 9.2 Reminder Email Template

| **Field** | **Value** |
|---|---|
| From | `SES_SENDER_EMAIL` from `.env` |
| To | patient email from `patients` table |
| Subject | `"Reminder: Your follow-up appointment is on [follow_up_date] — [attending_doctor]"` |
| Body (HTML) | Patient name, personalised `reminder_text` from Reminder Agent, follow-up date, hospital contact, attending doctor name |

---

## 10. Environment Variables (`.env`)

| **Variable** | **Required** | **Description** | **Example value** |
|---|---|---|---|
| `OPENAI_API_KEY` | Yes | GPT-4o + ada-002 embeddings | `sk-proj-...` |
| `AWS_ACCESS_KEY_ID` | Yes | IAM access key (capstone-ec2-user) | `AKIA...` |
| `AWS_SECRET_ACCESS_KEY` | Yes | IAM secret key | `...` |
| `AWS_REGION` | Yes | Region for S3 and SES | `ap-south-1` |
| `S3_BUCKET_NAME` | Yes | S3 bucket for protocol PDFs | `patient-followup-rag-team` |
| `SES_SENDER_EMAIL` | Yes | Verified SES sender | `noreply@yourdomain.com` |
| `DATABASE_URL` | No | SQLite path | `sqlite:///data/db/app.db` |

---

## 11. Recommended Project Folder Structure

```
patient-followup-assistant/
├── src/
│   ├── api/
│   │   ├── main.py            # FastAPI app, CORS, routers
│   │   ├── models.py          # Pydantic request/response models
│   │   └── routers/
│   │       ├── patients.py    # POST /patients, GET /patients, PATCH /outcome
│   │       ├── workflow.py    # POST /workflow/run, GET /workflow/status
│   │       └── escalations.py # GET /escalations, PATCH /close
│   ├── agents/
│   │   ├── state.py           # LangGraph PatientWorkflowState TypedDict
│   │   ├── graph.py           # LangGraph StateGraph definition
│   │   ├── router.py          # classify_patient() router node
│   │   ├── patient_summary.py # Patient Summary Agent node
│   │   ├── reminder.py        # Reminder Agent node
│   │   └── escalation.py      # Escalation Agent node
│   ├── rag/
│   │   └── pipeline.py        # ChromaDB index, retrieval function
│   ├── db/
│   │   ├── models.py          # SQLAlchemy ORM table definitions
│   │   └── session.py         # DB session factory
│   ├── email/
│   │   └── ses.py             # AWS SES send functions with retry
│   └── frontend/
│       └── app.py             # Streamlit 3-tab application
├── data/
│   ├── db/                    # app.db lives here
│   ├── protocols/             # Local copy of S3 PDFs for RAG
│   └── synthetic/             # patients.csv for testing
├── scripts/
│   ├── generate_patients.py   # Synthetic patient data generator
│   ├── generate_pdfs.py       # Synthetic protocol PDF generator
│   └── index_rag.py           # One-time ChromaDB indexing script
├── requirements.txt
├── .env.example
└── README.md
```

---

*End of Refined Design Document v2 · AI Patient Follow-Up Assistant · Theme 9*