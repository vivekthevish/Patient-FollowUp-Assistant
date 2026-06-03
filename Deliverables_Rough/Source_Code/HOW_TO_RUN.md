# CareConnect — How to Run

AI-Powered Patient Follow-Up and Reminder Management System  
IIT Roorkee AIOps Capstone | Team 11 | Theme 9

---

## Prerequisites

| Requirement | Minimum Version | Notes |
|-------------|----------------|-------|
| Python | 3.10+ | 3.11 recommended |
| pip | 23+ | Comes with Python |
| OpenAI API Key | — | Required — get from platform.openai.com |
| AWS Account | — | Optional (for S3 doc storage + EC2 deployment) |

---

## Step 1 — Clone / Place the Project

Ensure the folder structure looks like this:

```
Source_Code/
├── agents/
├── rag/
├── workflow/
├── utils/
├── frontend/
├── config.py
├── main.py
├── requirements.txt
├── .env.template
└── HOW_TO_RUN.md        ← this file

Dataset/
├── patients.csv
├── appointments.csv
└── followup_records.csv

Synthetic_Documents/
├── medical_followup_protocols.txt
└── patient_discharge_summaries.txt
```

The `Dataset/` and `Synthetic_Documents/` folders must sit **one level above** `Source_Code/`.

---

## Step 2 — Create a Virtual Environment (Recommended)

```bash
cd Source_Code

python3 -m venv venv
source venv/bin/activate        # Linux / macOS
# venv\Scripts\activate         # Windows
```

---

## Step 3 — Install Dependencies

```bash
pip install -r requirements.txt
```

This installs: `openai`, `langgraph`, `langchain`, `langchain-openai`, `langchain-chroma`,
`chromadb`, `streamlit`, `pandas`, `boto3`, `python-dotenv`, `pydantic`, `tenacity`.

---

## Step 4 — Configure Environment Variables

Copy the template and fill in your API key:

```bash
cp .env.template .env
```

Open `.env` and set:

```env
OPENAI_API_KEY=sk-your-openai-api-key-here

# Optional — only needed if using AWS S3 for document storage
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
AWS_REGION=us-east-1
S3_BUCKET_NAME=careconnect-documents
```

> **Note:** If AWS keys are not set, the app automatically falls back to loading
> documents from the local `../Synthetic_Documents/` folder. The app works fully
> without AWS for local testing.

---

## Step 5 — Build the RAG Vector Store (First Run Only)

This indexes the clinical protocol documents into ChromaDB. Run once before starting the app:

```bash
python main.py --rebuild-rag
```

Expected output:
```
[CareConnect] Initializing RAG pipeline...
[RAG] Building new vector store...
[RAG] Indexed 42 chunks from 2 documents.
```

The vector store is saved to `./chroma_db/` and reused on subsequent runs.

---

## Step 6 — Run the Streamlit Dashboard (Recommended)

```bash
streamlit run frontend/app.py
```

Then open your browser at: **http://localhost:8501**

### What you'll see:
1. **Sidebar** — Select a patient from the dropdown (20 synthetic patients available)
2. **Patient Card** — Shows demographics, diagnosis, risk badge, next follow-up date
3. Click **"Generate Follow-Up Plan"** — the LangGraph workflow runs
4. For **HIGH / CRITICAL** patients — a Human Approval panel appears with the escalation report
   - Click **Approve** to proceed with reminders
   - Click **Reject** to close without action
   - Click **Escalate** to flag for immediate intervention
5. **Follow-Up Plan** — shows clinical summary, risk level, and 3 personalized reminders (SMS / Email / Phone Script)
6. **Session History** — table of all patients processed this session

---

## Step 7 — Run via CLI (Optional)

Process a single patient:
```bash
python main.py --patient P001
```

Process all 20 patients in batch:
```bash
python main.py --all
```

Process first 5 patients only:
```bash
python main.py --all --limit 5
```

Print full JSON output:
```bash
python main.py --patient P003 --verbose
```

Force rebuild the RAG vector store:
```bash
python main.py --rebuild-rag
```

---

## Patient IDs for Testing

| Patient ID | Name | Diagnosis | Risk Level |
|-----------|------|-----------|-----------|
| P001 | Rajesh Kumar | Acute Myocardial Infarction | High |
| P003 | Suresh Nair | Congestive Heart Failure | Critical |
| P004 | Meena Joshi | Post Appendectomy | Low |
| P008 | Lakshmi Iyer | Breast Cancer Post-Chemo | Critical |
| P010 | Anita Bose | Stroke Recovery | Critical |
| P015 | Ramesh Choudhary | Post CABG | Critical |

> Use **P003** or **P010** to trigger the Human Approval flow (critical risk patients).  
> Use **P004** or **P009** to see the direct reminder flow (low risk patients).

---

## AWS Deployment (EC2)

### Launch EC2 Instance
1. Create a `t2.medium` instance (Ubuntu 22.04 LTS)
2. Security Group: allow inbound TCP on **port 8501** and **port 22**
3. Assign an Elastic IP

### Deploy the App

```bash
# SSH in
ssh -i your-key.pem ubuntu@<your-ec2-public-ip>

# Install Python
sudo apt update && sudo apt install -y python3.11 python3-pip python3.11-venv

# Upload project files (from local machine)
# Option A: scp
scp -i your-key.pem -r /path/to/project ubuntu@<ec2-ip>:~/careconnect/

# Option B: git
git clone https://your-repo-url ~/careconnect/

# Setup
cd ~/careconnect/Source_Code
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.template .env
nano .env   # paste your OPENAI_API_KEY

# Build RAG
python main.py --rebuild-rag

# Start app (runs in background, survives SSH disconnect)
nohup streamlit run frontend/app.py \
  --server.port 8501 \
  --server.address 0.0.0.0 \
  > ~/careconnect/streamlit.log 2>&1 &
```

App will be live at: `http://<your-ec2-public-ip>:8501`

### AWS S3 Setup (Optional — for cloud document storage)

```bash
# Create S3 bucket
aws s3 mb s3://careconnect-documents

# Upload documents
aws s3 cp ../Synthetic_Documents/medical_followup_protocols.txt    s3://careconnect-documents/documents/
aws s3 cp ../Synthetic_Documents/patient_discharge_summaries.txt   s3://careconnect-documents/documents/
aws s3 cp ../Dataset/patients.csv          s3://careconnect-documents/datasets/
aws s3 cp ../Dataset/appointments.csv      s3://careconnect-documents/datasets/
aws s3 cp ../Dataset/followup_records.csv  s3://careconnect-documents/datasets/

# Rebuild RAG from S3
python main.py --rebuild-rag
```

---

## Project Structure Reference

```
Source_Code/
├── config.py                  — API keys, paths, model settings
├── main.py                    — CLI entry point
├── requirements.txt           — All Python dependencies
├── .env.template              — Copy to .env and fill keys
│
├── agents/
│   ├── patient_summary_agent.py   — GPT-4o: clinical summary + risk_level
│   ├── reminder_agent.py          — GPT-4o: SMS + Email + Phone Script
│   └── escalation_agent.py        — GPT-4o: escalation report
│
├── rag/
│   └── rag_pipeline.py            — LangChain + ChromaDB ingestion & retrieval
│
├── workflow/
│   └── graph.py                   — LangGraph StateGraph (full workflow)
│
├── utils/
│   ├── memory.py                  — ConversationMemory class
│   └── error_handler.py           — Retry logic + error decorators
│
└── frontend/
    └── app.py                     — Streamlit clinical dashboard
```

---

## Common Errors and Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `OPENAI_API_KEY not set` | Missing .env file | Run `cp .env.template .env` and add your key |
| `Patient P001 not found` | Dataset path wrong | Ensure `Dataset/` is one level above `Source_Code/` |
| `No module named 'langgraph'` | Dependencies not installed | Run `pip install -r requirements.txt` |
| `ChromaDB: no such file` | RAG not initialized | Run `python main.py --rebuild-rag` |
| `openai.AuthenticationError` | Wrong API key | Check key in `.env` — should start with `sk-` |
| `Port 8501 already in use` | Another Streamlit running | Run `pkill -f streamlit` then restart |
| Streamlit page goes blank on approval | Normal Streamlit re-render | The workflow pauses correctly — click the approval button again if needed |

---

## Stopping the App

```bash
# Find the process
ps aux | grep streamlit

# Kill it
pkill -f streamlit

# Or on EC2 with nohup
kill $(cat ~/careconnect/streamlit.pid)
```

---

*CareConnect | IIT Roorkee AIOps Capstone | Team 11 | June 2026*
