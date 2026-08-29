import json
import tempfile
import unittest
from pathlib import Path

from pipeline.workflow import run_pipeline
from validate import verify


class IntegrationTests(unittest.TestCase):
    def test_local_pipeline_writes_replayable_artifacts_and_validates(self) -> None:
        tickets = [
            {
                "ticket_id": "synthetic-a",
                "subject": "Login problem",
                "message": "I cannot sign in and need access urgently.",
            },
            {
                "ticket_id": "synthetic-b",
                "subject": "General question",
                "message": "Please explain this feature.",
            },
        ]
        labels = [
            {
                "ticket_id": "synthetic-a",
                "category": "login_access",
                "priority": "high",
                "sentiment": "urgent",
            },
            {
                "ticket_id": "synthetic-b",
                "category": "other",
                "priority": "low",
                "sentiment": "neutral",
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tickets_path = root / "source-tickets.json"
            labels_path = root / "source-labels.json"
            tickets_path.write_text(json.dumps(tickets), encoding="utf-8")
            labels_path.write_text(json.dumps(labels), encoding="utf-8")

            result = run_pipeline(tickets_path, labels_path, root, provider="local")

            self.assertEqual(
                result["stages"],
                ["LOAD_INPUTS", "CLASSIFY", "VALIDATE", "SCORE", "REPORT"],
            )
            self.assertEqual(result["provider"], "local-fallback")
            self.assertTrue(all((root / name).exists() for name in (
                "tickets.json", "labels.json", "validation.json", "metrics.json",
                "report.md", "llm_calls.jsonl",
            )))
            self.assertEqual(len(list((root / "predictions").glob("*.json"))), len(tickets))
            self.assertEqual(verify(root), [])
            calls = (root / "llm_calls.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(calls), len(tickets))
            self.assertEqual(result["evaluation"]["metrics"]["total_tickets"], len(tickets))


if __name__ == "__main__":
    unittest.main()
