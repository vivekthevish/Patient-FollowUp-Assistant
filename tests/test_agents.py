from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import src.agents.escalation as escalation_module
import src.agents.patient_summary as patient_summary_module
import src.agents.reminder as reminder_module


class AgentTestCase(unittest.TestCase):
    def test_generate_patient_summary_fallback(self) -> None:
        profile = {
            "patient_name": "Rajan Mehta",
            "age": 58,
            "diagnosis": "Cardiac — myocardial infarction",
            "doctor_notes": "Moderate LV dysfunction. EF 38%. BP 154/92 at discharge.",
            "severity": "Critical",
            "follow_up_date": date.today() - timedelta(days=1),
        }

        with patch.object(patient_summary_module, "OPENAI_API_KEY", ""):
            summary, risk_score = patient_summary_module.generate_patient_summary({"profile": profile}, "Protocol context")

        self.assertIn("Rajan Mehta", summary)
        self.assertIn("Protocol context reviewed", summary)
        self.assertGreater(risk_score, 9.0)

    def test_generate_patient_summary_with_openai_uses_json_safe_payload(self) -> None:
        profile = {
            "patient_name": "Rajan Mehta",
            "age": 58,
            "diagnosis": "Cardiac — myocardial infarction",
            "doctor_notes": "Moderate LV dysfunction. EF 38%. BP 154/92 at discharge.",
            "severity": "Critical",
            "follow_up_date": date.today(),
        }

        mock_response = unittest.mock.MagicMock()
        mock_response.choices = [
            unittest.mock.MagicMock(
                message=unittest.mock.MagicMock(content='{"summary":"ok","risk_score":8.8}')
            )
        ]

        with patch.object(patient_summary_module, "OPENAI_API_KEY", "test-key"), patch("openai.OpenAI") as mocked_openai:
            mocked_openai.return_value.chat.completions.create.return_value = mock_response
            summary, risk_score = patient_summary_module.generate_patient_summary({"profile": profile}, "Protocol context")

        self.assertEqual(summary, "ok")
        self.assertEqual(risk_score, 8.8)

    def test_generate_reminder_fallback(self) -> None:
        profile = {
            "patient_name": "Meena Reddy",
            "diagnosis": "Hypertension",
            "follow_up_date": date(2026, 6, 14),
            "attending_doctor": "Dr. Anjali Sharma",
        }

        rag_context = "Chunk one from the protocol.\n\n---\n\nChunk two from the protocol."
        with patch.object(reminder_module, "OPENAI_API_KEY", ""):
            result = reminder_module.generate_reminder({"profile": profile}, summary="Please attend follow-up.", rag_context=rag_context)

        self.assertIn("Meena Reddy", result["reminder_text"])
        self.assertIn("Hypertension", result["reminder_text"])
        self.assertEqual(len(result["rag_context_json"]), 2)
        self.assertIn("Dr. Anjali Sharma", result["email_subject"])

    def test_generate_reminder_with_openai_uses_json_safe_payload(self) -> None:
        profile = {
            "patient_name": "Meena Reddy",
            "diagnosis": "Hypertension",
            "follow_up_date": date.today(),
            "attending_doctor": "Dr. Anjali Sharma",
        }

        mock_response = unittest.mock.MagicMock()
        mock_response.choices = [
            unittest.mock.MagicMock(message=unittest.mock.MagicMock(content='{"reminder_text":"Take your follow-up."}'))
        ]

        with patch.object(reminder_module, "OPENAI_API_KEY", "test-key"), patch("openai.OpenAI") as mocked_openai:
            mocked_openai.return_value.chat.completions.create.return_value = mock_response
            result = reminder_module.generate_reminder({"profile": profile}, summary="Please attend follow-up.", rag_context="")

        self.assertEqual(result["reminder_text"], "Take your follow-up.")
        self.assertIn("Dr. Anjali Sharma", result["email_subject"])

    def test_generate_escalation_creates_database_row(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "app.db"
            self._create_escalation_schema(database_path)
            self._insert_reminder_row(database_path, patient_id="P019")

            patient_data = {
                "profile": {
                    "patient_id": "P019",
                    "patient_name": "Meena Reddy",
                    "diagnosis": "Hypertension — crisis",
                    "doctor_notes": "BP remained elevated at discharge.",
                    "follow_up_date": date.today() - timedelta(days=2),
                    "patient_summary": "Patient missed follow-up.",
                },
                "summary": "Patient missed follow-up.",
            }

            with patch.object(escalation_module, "OPENAI_API_KEY", ""):
                result = escalation_module.generate_escalation(
                    patient_data,
                    current_date=date.today(),
                    database_url=f"sqlite:///{database_path}",
                )

            self.assertFalse(result["escalation_skipped"])
            self.assertEqual(result["escalation_status"], "pending")
            self.assertIn("Meena Reddy", result["escalation_report"])

            connection = sqlite3.connect(database_path)
            connection.row_factory = sqlite3.Row
            escalation_row = connection.execute("SELECT * FROM escalations WHERE patient_id = ?", ("P019",)).fetchone()
            reminder_row = connection.execute("SELECT * FROM reminders WHERE patient_id = ?", ("P019",)).fetchone()
            connection.close()

            self.assertIsNotNone(escalation_row)
            self.assertEqual(escalation_row["escalation_status"], "pending")
            self.assertEqual(reminder_row["is_active"], 0)

    def test_generate_escalation_skips_duplicate_row(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "app.db"
            self._create_escalation_schema(database_path)
            self._insert_escalation_row(database_path, patient_id="P020")

            patient_data = {
                "profile": {
                    "patient_id": "P020",
                    "patient_name": "Rohit Kumar",
                    "diagnosis": "Asthma",
                    "doctor_notes": "Missed review.",
                    "follow_up_date": date.today() - timedelta(days=5),
                    "patient_summary": "Existing escalation should cause skip.",
                },
                "summary": "Existing escalation should cause skip.",
            }

            with patch.object(escalation_module, "OPENAI_API_KEY", ""):
                result = escalation_module.generate_escalation(
                    patient_data,
                    current_date=date.today(),
                    database_url=f"sqlite:///{database_path}",
                )

            self.assertTrue(result["escalation_skipped"])
            self.assertEqual(result["escalation_status"], "skipped")
            self.assertNotIn("escalation_report", result)

    @staticmethod
    def _create_escalation_schema(database_path: Path) -> None:
        connection = sqlite3.connect(database_path)
        connection.execute(
            """
            CREATE TABLE reminders (
                reminder_id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT NOT NULL,
                reminder_text TEXT NOT NULL,
                rag_context_json TEXT,
                reminder_sent_dates TEXT NOT NULL,
                email_status TEXT NOT NULL DEFAULT 'not_sent',
                email_sent_at TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE escalations (
                escalation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT NOT NULL UNIQUE,
                patient_name TEXT NOT NULL,
                diagnosis TEXT NOT NULL,
                follow_up_date TEXT NOT NULL,
                doctor_notes TEXT,
                escalation_report TEXT NOT NULL,
                escalation_status TEXT NOT NULL DEFAULT 'pending',
                closed_at TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.commit()
        connection.close()

    @staticmethod
    def _insert_reminder_row(database_path: Path, patient_id: str) -> None:
        connection = sqlite3.connect(database_path)
        connection.execute(
            """
            INSERT INTO reminders (
                patient_id, reminder_text, rag_context_json, reminder_sent_dates,
                email_status, email_sent_at, is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                patient_id,
                "Existing reminder",
                json.dumps([]),
                json.dumps(["2026-06-01"]),
                "sent",
                None,
                1,
                "2026-06-01T10:00:00",
                "2026-06-01T10:00:00",
            ),
        )
        connection.commit()
        connection.close()

    @staticmethod
    def _insert_escalation_row(database_path: Path, patient_id: str) -> None:
        connection = sqlite3.connect(database_path)
        connection.execute(
            """
            INSERT INTO escalations (
                patient_id, patient_name, diagnosis, follow_up_date,
                doctor_notes, escalation_report, escalation_status, closed_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                patient_id,
                "Existing",
                "Existing",
                "2026-06-01",
                None,
                "Existing escalation",
                "pending",
                None,
                "2026-06-01T10:00:00",
            ),
        )
        connection.commit()
        connection.close()


if __name__ == "__main__":
    unittest.main()
