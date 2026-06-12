from __future__ import annotations

import unittest
from concurrent.futures import Future
from datetime import date, datetime
from unittest.mock import patch

from fastapi.testclient import TestClient
from tenacity import RetryError

from src.api.main import app
from src.api.services import _workflow_error_message


class APITestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.init_patch = patch("src.api.main.init_db", autospec=True)
        self.init_patch.start()
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.client_context.__exit__(None, None, None)
        self.init_patch.stop()

    def test_health_check(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_register_patient_success(self) -> None:
        payload = {
            "patient_name": "Rajan Mehta",
            "age": 58,
            "gender": "Male",
            "email": "rajan.mehta@example.com",
            "phone": "+91-9876543210",
            "diagnosis": "Cardiac — myocardial infarction",
            "follow_up_date": "2026-06-14",
            "doctor_notes": "Moderate LV dysfunction. EF 38%. BP 154/92 at discharge.",
            "attending_doctor": "Dr. Anjali Sharma",
            "severity": "Critical",
        }

        with patch("src.api.routers.patients.create_patient") as mocked_create:
            mocked_create.return_value = {
                "patient_id": "P001",
                "patient_name": "Rajan Mehta",
                "follow_up_date": date(2026, 6, 14),
                "message": "Patient registered successfully.",
                "created_at": datetime(2026, 6, 6, 14, 30, 0),
            }

            response = self.client.post("/api/v1/patients", json=payload)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["patient_id"], "P001")
        self.assertEqual(response.json()["message"], "Patient registered successfully.")

    def test_register_patient_duplicate_email(self) -> None:
        payload = {
            "patient_name": "Rajan Mehta",
            "age": 58,
            "gender": "Male",
            "email": "rajan.mehta@example.com",
            "phone": "+91-9876543210",
            "diagnosis": "Cardiac — myocardial infarction",
            "follow_up_date": "2026-06-14",
            "doctor_notes": "Moderate LV dysfunction. EF 38%. BP 154/92 at discharge.",
            "attending_doctor": "Dr. Anjali Sharma",
            "severity": "Critical",
        }

        with patch("src.api.routers.patients.create_patient") as mocked_create:
            mocked_create.side_effect = ValueError("Email already exists for another patient.")
            response = self.client.post("/api/v1/patients", json=payload)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "Email already exists for another patient.", "error_code": "DUPLICATE_EMAIL"})

    def test_fetch_patients(self) -> None:
        with patch("src.api.routers.patients.list_patients") as mocked_list:
            mocked_list.return_value = [
                {
                    "patient_id": "P001",
                    "patient_name": "Rajan Mehta",
                    "diagnosis": "Cardiac — myocardial infarction",
                    "severity": "Critical",
                    "follow_up_date": date(2026, 6, 14),
                    "patient_summary": "Patient summary",
                    "risk_score": 8.4,
                    "followup_status": "pending",
                    "reminder": None,
                }
            ]
            response = self.client.get("/api/v1/patients")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["patients"][0]["patient_id"], "P001")

    def test_fetch_patient_detail(self) -> None:
        with patch("src.api.routers.patients.get_patient_detail") as mocked_detail:
            mocked_detail.return_value = {
                "patient_id": "P001",
                "patient_name": "Rajan Mehta",
                "diagnosis": "Cardiac — myocardial infarction",
                "severity": "Critical",
                "follow_up_date": date(2026, 6, 14),
                "patient_summary": "Patient summary",
                "risk_score": 8.4,
                "followup_status": "pending",
                "reminder": None,
                "email": "rajan.mehta@example.com",
                "phone": "+91-9876543210",
                "doctor_notes": "Moderate LV dysfunction. EF 38%. BP 154/92 at discharge.",
                "attending_doctor": "Dr. Anjali Sharma",
                "created_at": datetime(2026, 6, 6, 14, 30, 0),
                "updated_at": datetime(2026, 6, 6, 15, 0, 0),
            }
            response = self.client.get("/api/v1/patients/P001")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["patient"]["patient_id"], "P001")

    def test_update_outcome(self) -> None:
        with patch("src.api.routers.patients.update_patient_outcome") as mocked_update:
            mocked_update.return_value = {
                "patient_id": "P001",
                "followup_status": "completed",
                "message": "Follow-up outcome updated successfully.",
                "updated_at": datetime(2026, 6, 14, 11, 0, 0),
            }
            response = self.client.patch(
                "/api/v1/patients/P001/outcome",
                json={"followup_status": "completed", "updated_by": "Nurse Priya S."},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["followup_status"], "completed")

    def test_run_workflow(self) -> None:
        with patch("src.api.routers.workflow.start_workflow_job") as mocked_start:
            mocked_start.return_value = {
                "job_id": "job_abc123",
                "reminder_patients": ["P001", "P007"],
                "escalation_patients": ["P019"],
                "skipped_patients": ["P022"],
                "status": "running",
            }
            response = self.client.post("/api/v1/workflow/run")

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["job_id"], "job_abc123")
        self.assertEqual(response.json()["status"], "running")

    def test_workflow_status(self) -> None:
        with patch("src.api.routers.workflow.get_workflow_status") as mocked_status:
            mocked_status.return_value = {
                "job_id": "job_abc123",
                "status": "completed",
                "results": [
                    {
                        "patient_id": "P001",
                        "path": "reminder",
                        "status": "success",
                        "email_status": "sent",
                        "error": None,
                    }
                ],
                "completed_at": datetime(2026, 6, 7, 9, 5, 0),
                "error": None,
            }
            response = self.client.get("/api/v1/workflow/status/job_abc123")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "completed")
        self.assertEqual(response.json()["results"][0]["email_status"], "sent")

    def test_workflow_error_message_unwraps_rate_limit(self) -> None:
        direct_error = Exception("rate limit exceeded")
        future = Future()
        future.set_exception(direct_error)
        wrapped_error = RetryError(future)

        self.assertEqual(
            _workflow_error_message(wrapped_error),
            "Gemini rate limit reached. Please retry the workflow in a moment.",
        )
        self.assertEqual(
            _workflow_error_message(direct_error),
            "Gemini rate limit reached. Please retry the workflow in a moment.",
        )

    def test_fetch_escalations(self) -> None:
        with patch("src.api.routers.escalations.list_escalations") as mocked_list:
            mocked_list.return_value = [
                {
                    "escalation_id": 1,
                    "patient_id": "P019",
                    "patient_name": "Meena Reddy",
                    "diagnosis": "Hypertension — crisis",
                    "follow_up_date": date(2026, 6, 5),
                    "escalation_report": "Patient missed follow-up.",
                    "escalation_status": "pending",
                    "created_at": datetime(2026, 6, 6, 9, 0, 0),
                    "closed_at": None,
                }
            ]
            response = self.client.get("/api/v1/escalations")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)
        self.assertEqual(response.json()["escalations"][0]["patient_id"], "P019")

    def test_close_escalation(self) -> None:
        with patch("src.api.routers.escalations.close_escalation") as mocked_close:
            mocked_close.return_value = {
                "escalation_id": 1,
                "patient_id": "P019",
                "escalation_status": "closed",
                "closed_at": datetime(2026, 6, 7, 11, 30, 0),
                "message": "Escalation marked as closed.",
            }
            response = self.client.patch(
                "/api/v1/escalations/1/close",
                json={"closed_by": "Dr. Anjali Sharma"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["escalation_status"], "closed")


if __name__ == "__main__":
    unittest.main()
