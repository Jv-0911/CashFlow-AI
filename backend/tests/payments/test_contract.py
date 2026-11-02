import json
from datetime import datetime
from pathlib import Path
import unittest

from backend.app.ledger.models import State


class ContractTests(unittest.TestCase):
    def test_contract_is_labelled_and_cash_excludes_nonverified_states(self):
        path = Path(__file__).resolve().parents[3] / "contracts/payment-ledger.example.json"
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        self.assertIs(value.get("is_demo_data"), True, "Shared fixture must carry the Member 3 demo-data label.")
        self.assertEqual(value["contract_status"], "MEMBER_3_IMPLEMENTATION_CONTRACT")
        self.assertEqual(value["version"], "1.0")
        response = value["ledger_response"]
        verified_total = 0
        for entry in response["entries"]:
            self.assertIs(type(entry["amount_cents"]), int)
            self.assertEqual(entry["currency"], "USD")
            self.assertIn(State(entry["status"]), State)
            datetime.fromisoformat(entry["created_at"])
            datetime.fromisoformat(entry["updated_at"])
            if entry["status"] == "VERIFIED_PAID":
                self.assertEqual(entry["provider_status"], "PAID")
                self.assertEqual(entry["paid_amount_cents"], entry["amount_cents"])
                datetime.fromisoformat(entry["verified_at"])
                verified_total += entry["amount_cents"]
            else:
                self.assertIsNone(entry["verified_at"])
        self.assertEqual(response["recovered_cash"], [{"amount_cents": verified_total, "currency": "USD"}])
        self.assertEqual(set(value["error_response"]["error"]), {"code", "message", "request_id"})
        self.assertNotIn("approved_by", value["requests"]["approve_internal"])
