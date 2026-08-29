"""End-to-end and regression test suite for ticket evaluation pipeline."""

import json
import tempfile
import unittest
from pathlib import Path

from pipeline.contracts import ARTIFACT_NAMES, CATEGORY_VALUES, PRIORITY_VALUES, SENTIMENT_VALUES
from pipeline.llm import LLMAdapter, _decode_json_object
from pipeline.scoring import calculate_metrics, score_predictions
from pipeline.workflow import load_inputs, run_pipeline
from validate import verify


class E2ERegressionTests(unittest.TestCase):
    """End-to-end regression tests verifying evaluator requirements."""

    def test_evaluator_sample_dataset_e2e(self) -> None:
        """Verify the exact problem statement sample inputs run and validate cleanly."""
        sample_tickets = [
            {
                "ticket_id": "T-1001",
                "subject": "Cannot withdraw from account",
                "message": "I tried to withdraw my balance twice today and both requests failed. The app says verification required but I already uploaded documents last week.",
                "channel": "chat",
            },
            {
                "ticket_id": "T-1002",
                "subject": "Charged twice",
                "message": "My card was debited twice for one deposit. Please help.",
                "channel": "email",
            },
            {
                "ticket_id": "T-1003",
                "subject": "Password reset link expired",
                "message": "The reset link expires immediately after I click it.",
                "channel": "web",
            },
        ]
        sample_labels = {
            "T-1001": {
                "category": "account_verification",
                "priority": "high",
                "sentiment": "frustrated",
            },
            "T-1002": {
                "category": "payment_issue",
                "priority": "high",
                "sentiment": "frustrated",
            },
            "T-1003": {
                "category": "login_access",
                "priority": "medium",
                "sentiment": "neutral",
            },
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tickets_path = root / "sample_tickets.json"
            labels_path = root / "sample_labels.json"
            output_dir = root / "out"

            tickets_path.write_text(json.dumps(sample_tickets, indent=2), encoding="utf-8")
            labels_path.write_text(json.dumps(sample_labels, indent=2), encoding="utf-8")

            result = run_pipeline(
                tickets_path=tickets_path,
                labels_path=labels_path,
                output_dir=output_dir,
                provider="local",
            )

            # Check pipeline result structure
            self.assertEqual(
                result["stages"],
                ["LOAD_INPUTS", "CLASSIFY", "VALIDATE", "SCORE", "REPORT"],
            )

            # Check all required artifacts exist in output_dir
            for artifact in ARTIFACT_NAMES:
                self.assertTrue(
                    (output_dir / artifact).exists(),
                    f"Required artifact {artifact} missing from output",
                )

            # Check individual prediction files
            for ticket in sample_tickets:
                pred_file = output_dir / "predictions" / f"{ticket['ticket_id']}.json"
                self.assertTrue(pred_file.exists())
                pred_data = json.loads(pred_file.read_text(encoding="utf-8"))
                self.assertEqual(pred_data["ticket_id"], ticket["ticket_id"])
                self.assertIn(pred_data["category"], CATEGORY_VALUES)
                self.assertIn(pred_data["priority"], PRIORITY_VALUES)
                self.assertIn(pred_data["sentiment"], SENTIMENT_VALUES)
                self.assertTrue(len(pred_data.get("reasoning", "")) > 0)

            # Check independent validation
            val_errors = verify(output_dir)
            self.assertEqual(val_errors, [], f"Validation failed with: {val_errors}")

            # Check report contents
            report_text = (output_dir / "report.md").read_text(encoding="utf-8")
            self.assertIn("# Evaluation report", report_text)
            self.assertIn("Tickets evaluated: 3", report_text)
            self.assertIn("Category accuracy", report_text)
            self.assertIn("Improvement suggestions", report_text)

            # Check llm_calls.jsonl format
            calls_lines = (output_dir / "llm_calls.jsonl").read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(calls_lines), len(sample_tickets))
            for line in calls_lines:
                call = json.loads(line)
                self.assertEqual(call["stage"], "classify")
                self.assertIn(call["ticket_id"], {"T-1001", "T-1002", "T-1003"})
                self.assertTrue("timestamp" in call)
                self.assertTrue("provider" in call)
                self.assertTrue("model" in call)
                self.assertTrue("prompt_version" in call)
                self.assertTrue("output_artifact" in call)

    def test_json_fence_and_whitespace_repair(self) -> None:
        """Verify markdown code block fences and trailing whitespaces are repaired."""
        raw_with_fence = '```json\n{"ticket_id": "T-1", "category": "other", "priority": "low", "sentiment": "neutral", "reasoning": "ok"}\n```'
        decoded = _decode_json_object(raw_with_fence)
        self.assertEqual(decoded["ticket_id"], "T-1")
        self.assertEqual(decoded["category"], "other")

        raw_generic_fence = '```\n{"ticket_id": "T-2", "category": "payment_issue", "priority": "high", "sentiment": "urgent", "reasoning": "urgent"}\n```'
        decoded2 = _decode_json_object(raw_generic_fence)
        self.assertEqual(decoded2["ticket_id"], "T-2")

    def test_deterministic_scoring_penalizes_invalid_predictions(self) -> None:
        """Verify that invalid/corrupt predictions receive zero credit and are flagged as failed."""
        labels = {
            "T-1": {"category": "payment_issue", "priority": "high", "sentiment": "urgent"},
            "T-2": {"category": "login_access", "priority": "low", "sentiment": "neutral"},
        }
        # T-1 is valid and matches, T-2 is corrupted/invalid
        predictions = [
            {"ticket_id": "T-1", "category": "payment_issue", "priority": "high", "sentiment": "urgent", "reasoning": "ok"}
        ]
        validation_records = [
            {"ticket_id": "T-1", "valid": True, "errors": [], "prediction": predictions[0]},
            {"ticket_id": "T-2", "valid": False, "errors": [{"code": "INVALID_JSON", "field": None}], "prediction": None},
        ]

        result = score_predictions(labels, predictions, validation_records)
        self.assertEqual(result["total_tickets"], 2)
        self.assertEqual(result["valid_predictions"], 1)
        self.assertEqual(result["invalid_predictions"], 1)
        self.assertEqual(result["passed_tickets"], 1)
        self.assertEqual(result["failed_tickets"], 1)
        self.assertEqual(result["exact_match_rate"], 0.5)

        # Check metrics view matches
        metrics = calculate_metrics(labels, predictions, validation_records)
        self.assertEqual(metrics["exact_match_rate"], 0.5)
        self.assertEqual(metrics["passed_tickets"], 1)


if __name__ == "__main__":
    unittest.main()
