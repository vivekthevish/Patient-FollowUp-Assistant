# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**CareConnect** is an AI-powered patient follow-up assistant for post-discharge care. It uses a LangGraph multi-agent workflow to generate clinical summaries, personalized reminders, and escalation reports for patients based on their follow-up dates and risk levels.

## Running the Application

**Recommended: Streamlit dashboard + FastAPI backend**
```powershell
# From project root (Windows)
.\run.ps1
# Streamlit UI: http://localhost:8501
# FastAPI backend: http://localhost:8000
```

**Manual startup:**
```bash
# Backend (from project root)
uvicorn src.api.main:app --reload --port 8000

# Frontend (separate terminal)
streamlit run src/frontend/app.py
```

**CLI mode (no UI):**
```bash
cd src
python main.py --patient P001          # single patient
python main.py --all --limit 5         # batch with limit
python main.py --rebuild-rag           # rebuild RAG index
```

## Running Tests

```bash
python -m pytest tests/test_api.py
python -m pytest tests/test_agents.py
```

## Environment Setup

Copy `.env.template` to `.env` and set at minimum:
```
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-3.1-flash-lite     # default
DATABASE_URL=sqlite:///data/db/app.db  # default
```

AWS credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_BUCKET_NAME`, `SES_SENDER_EMAIL`) are optional — the system runs fully locally without them.

## Architecture

The system has two runtimes: a **Streamlit frontend** (`src/frontend/app.py`) that calls a **FastAPI backend** (`src/api/main.py`) which invokes the **LangGraph workflow** (`src/agents/graph.py`).

### LangGraph Workflow (`src/agents/graph.py`)

The core pipeline runs as a state machine:

1. **Load Patient Data** — reads from `data/datasets/` CSVs
2. **RAG Retrieval** — fetches relevant protocol chunks from `data/documents/`
3. **Patient Summary Agent** (`src/agents/patient_summary.py`) — generates a clinical summary and `risk_score` (0–10)
4. **Risk Router** (`src/agents/router.py`) — routes by risk level:
   - `LOW`/`MEDIUM` → Reminder Agent
   - `HIGH`/`CRITICAL` → Escalation Agent → **Human Approval interrupt**
5. **Reminder Agent** (`src/agents/reminder.py`) — generates SMS + Email + Phone Script (150–200 words each)
6. **Escalation Agent** (`src/agents/escalation.py`) — generates clinical action items for overdue high-risk patients
7. **Output Formatter** — returns final JSON

The human-in-the-loop interrupt for HIGH/CRITICAL patients is handled via LangGraph's `interrupt()` mechanism; the Streamlit UI presents Approve/Reject/Escalate buttons that resume the graph.

### Patient Selection Logic

The router (`src/agents/router.py`) categorizes patients by comparing `follow_up_date` to the current date:
- **Reminder group**: follow-up due in 1, 3, or 7 days
- **Escalation group**: follow-up date is past (overdue)
- **Skipped**: all others

### RAG Pipeline (`src/rag/pipeline.py`)

Uses **local keyword scoring** — no vector database. Reads `.txt`/`.md` files from `data/documents/` (and `data/protocols/`), chunks them at 700 words, and ranks by term-frequency matching. `retrieve_context_chunks(query, k=3)` returns the top-3 chunks.

### Database (`src/db/`)

SQLite via SQLAlchemy 2.0 with three tables: `Patient`, `Reminder`, `Escalation`. Tables are auto-created by `init_db()` on FastAPI startup. `reminder_sent_dates` on `Reminder` is stored as a JSON array.

### Gemini Integration (`src/agents/gemini.py`)

All LLM calls go through `generate_structured_response()`, which uses `tenacity` retry logic (3 attempts, exponential backoff). Structured outputs use Pydantic models (`_SummaryResponse`, `_ReminderResponse`). Agents have fallback functions that calculate risk/generate reminders without Gemini if the API key is absent.

### Risk Score Calculation

When Gemini is unavailable, risk is calculated as:
`base_score (2.2–9.2 by diagnosis severity) + overdue_days × 0.25`

## Key Paths

| Purpose | Path |
|---------|------|
| LangGraph graph definition | `src/agents/graph.py` |
| Workflow state schema | `src/agents/state.py` |
| FastAPI app factory | `src/api/main.py` |
| API route definitions | `src/api/routers/` |
| Pydantic request/response schemas | `src/api/models.py` |
| Streamlit dashboard | `src/frontend/app.py` |
| Configuration & env loading | `src/config.py` |
| SQLAlchemy ORM models | `src/db/models.py` |
| Synthetic patient data | `data/datasets/patients.csv` |
| Medical protocol documents | `data/documents/` |

## Synthetic Test Data

20 patients with IDs `P001`–`P020` are pre-loaded in `data/datasets/patients.csv`. Representative test cases:
- **P001** – Acute Myocardial Infarction, HIGH risk, overdue (triggers escalation)
- **P003** – Type 2 Diabetes, MEDIUM risk, due in 3 days (triggers reminder)
- **P007** – Hypertension, LOW risk, future date (skipped)

The Streamlit dashboard loads these patients from the CSV on startup.
