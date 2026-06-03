import json
from datetime import datetime
from typing import List, Dict, Optional
from collections import deque


class ConversationMemory:
    """In-session conversation memory for the CareConnect workflow."""

    def __init__(self, max_history: int = 20):
        self.max_history = max_history
        self._history: deque = deque(maxlen=max_history)
        self._session_metadata: Dict = {
            "session_start": datetime.now().isoformat(),
            "total_patients_processed": 0,
            "escalations_triggered": 0
        }

    def add_interaction(self, patient_id: str, action: str, output: str, risk_level: Optional[str] = None):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "patient_id": patient_id,
            "action": action,
            "output_preview": output[:200] + "..." if len(output) > 200 else output,
            "risk_level": risk_level
        }
        self._history.append(entry)
        self._session_metadata["total_patients_processed"] += 1
        if risk_level in ["high", "critical"]:
            self._session_metadata["escalations_triggered"] += 1

    def get_history(self) -> List[Dict]:
        return list(self._history)

    def get_patient_context(self, patient_id: str) -> List[Dict]:
        return [e for e in self._history if e["patient_id"] == patient_id]

    def get_session_summary(self) -> Dict:
        return {
            **self._session_metadata,
            "recent_interactions": self.get_history()[-5:],
            "history_length": len(self._history)
        }

    def clear(self):
        self._history.clear()
        self._session_metadata["total_patients_processed"] = 0
        self._session_metadata["escalations_triggered"] = 0

    def to_langchain_messages(self, patient_id: Optional[str] = None) -> List[Dict]:
        history = self.get_patient_context(patient_id) if patient_id else self.get_history()
        messages = []
        for entry in history:
            messages.append({"role": "assistant", "content": f"[{entry['timestamp']}] {entry['action']}: {entry['output_preview']}"})
        return messages

    def export_json(self) -> str:
        return json.dumps({
            "metadata": self._session_metadata,
            "history": self.get_history()
        }, indent=2)


session_memory = ConversationMemory()
