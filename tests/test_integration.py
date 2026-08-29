import json
import tempfile
import unittest
from pathlib import Path

from pipeline.workflow import run_pipeline
from validate import verify


class IntegrationTests(unittest.TestCase):
    def test_local_pipeline_writes_replayable_artifacts_and_validates(self) -> None:
        fixture_dir = Path(__file__).parent / "fixtures"
        tickets_path = fixture_dir / "synthetic_tickets.json"
        labels_path = fixture_dir / "synthetic_labels.json"
        tickets = json.loads(tickets_path.read_text(encoding="utf-8"))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
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
            call_records = [json.loads(line) for line in calls]
            self.assertEqual({record["stage"] for record in call_records}, {"classify"})
            self.assertEqual(result["evaluation"]["metrics"]["total_tickets"], len(tickets))
            self.assertEqual(result["evaluation"]["metrics"]["category_accuracy"], 0.8)
            self.assertEqual(result["evaluation"]["metrics"]["priority_accuracy"], 0.4)
            self.assertEqual(result["evaluation"]["metrics"]["sentiment_accuracy"], 0.4)
            self.assertEqual(result["evaluation"]["metrics"]["exact_match_rate"], 0.0)
            self.assertEqual(result["evaluation"]["metrics"]["failed_tickets"], 5)


if __name__ == "__main__":
    unittest.main()
