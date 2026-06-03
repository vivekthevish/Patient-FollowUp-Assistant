#!/usr/bin/env python3
"""
CareConnect — AI Patient Follow-Up and Reminder Management System
Entry point for CLI usage and batch processing.
"""

import os
import sys
import json
import argparse
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import OPENAI_API_KEY
from rag.rag_pipeline import initialize_rag
from workflow.graph import graph
from langgraph.types import Command


def check_env():
    if not OPENAI_API_KEY:
        print("[ERROR] OPENAI_API_KEY not set. Please configure your .env file.")
        sys.exit(1)


def run_single_patient(patient_id: str, verbose: bool = False) -> dict:
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

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

    print(f"\n{'='*60}")
    print(f"Processing Patient: {patient_id}")
    print(f"{'='*60}")

    result = None
    for event in graph.stream(initial_state, config=config, stream_mode="values"):
        last_state = event

        if "__interrupt__" in str(event):
            # Human-in-the-loop: get input from CLI
            print("\n[HUMAN APPROVAL REQUIRED]")
            print(f"Patient: {last_state.get('patient_id')}")
            print(f"Risk Level: {last_state.get('risk_level', '').upper()}")
            print(f"\nEscalation Report:\n{last_state.get('escalation_message', '')}")
            print(f"\nSummary:\n{last_state.get('summary', '')}")
            print("\nOptions: approve / reject / escalate")
            decision = input("Your decision: ").strip().lower()

            for event in graph.stream(
                Command(resume=decision),
                config=config,
                stream_mode="values"
            ):
                last_state = event

    final = last_state.get("final_output", {})

    if verbose:
        print(json.dumps(final, indent=2))
    else:
        print(f"\nStatus      : {final.get('status', 'unknown').upper()}")
        print(f"Patient     : {final.get('patient_name', patient_id)}")
        print(f"Risk Level  : {final.get('risk_level', 'N/A').upper()}")
        print(f"Reminders   : {len(final.get('reminders', []))} generated")
        print(f"Escalation  : {'YES' if final.get('escalation_required') else 'NO'}")

    return final


def run_all_patients(limit: int = 0) -> None:
    import pandas as pd
    from config import DATASET_DIR

    patients_df = pd.read_csv(os.path.join(DATASET_DIR, "patients.csv"))
    patient_ids = patients_df["patient_id"].tolist()

    if limit > 0:
        patient_ids = patient_ids[:limit]

    print(f"\nBatch processing {len(patient_ids)} patients...\n")
    results = []
    for pid in patient_ids:
        result = run_single_patient(pid)
        results.append(result)

    successes = sum(1 for r in results if r.get("status") == "success")
    escalations = sum(1 for r in results if r.get("escalation_required"))
    print(f"\n{'='*60}")
    print(f"Batch Complete: {successes}/{len(results)} successful, {escalations} escalations")


def main():
    check_env()

    parser = argparse.ArgumentParser(description="CareConnect AI Patient Follow-Up System")
    parser.add_argument("--patient", type=str, help="Process a single patient by ID (e.g. P001)")
    parser.add_argument("--all", action="store_true", help="Process all patients in the dataset")
    parser.add_argument("--limit", type=int, default=0, help="Limit batch processing to N patients")
    parser.add_argument("--rebuild-rag", action="store_true", help="Force rebuild the RAG vector store")
    parser.add_argument("--verbose", action="store_true", help="Print full JSON output")
    args = parser.parse_args()

    print("[CareConnect] Initializing RAG pipeline...")
    initialize_rag(force_rebuild=args.rebuild_rag)

    if args.patient:
        run_single_patient(args.patient, verbose=args.verbose)
    elif args.all:
        run_all_patients(limit=args.limit)
    else:
        parser.print_help()
        print("\nExample: python main.py --patient P001")
        print("Example: python main.py --all --limit 5")


if __name__ == "__main__":
    main()
