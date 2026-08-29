import unittest

from pipeline.reporting import analyze_errors, generate_report, suggest_improvements
from pipeline.scoring import calculate_metrics, score_predictions


class ScoringReportingTests(unittest.TestCase):
    def setUp(self):
        self.labels = [
            {
                "ticket_id": "b",
                "category": "login_access",
                "priority": "low",
                "sentiment": "neutral",
            },
            {
                "ticket_id": "a",
                "category": "payment_issue",
                "priority": "high",
                "sentiment": "urgent",
            },
        ]
        self.predictions = [
            {
                "ticket_id": "a",
                "category": "payment_issue",
                "priority": "high",
                "sentiment": "urgent",
                "reasoning": "matches",
            },
            {
                "ticket_id": "b",
                "category": "other",
                "priority": "medium",
                "sentiment": "frustrated",
                "reasoning": "does not match",
            },
        ]

    def test_scores_each_dimension_and_exact_match(self):
        result = score_predictions(self.labels, self.predictions)

        self.assertEqual(result["category_accuracy"], 0.5)
        self.assertEqual(result["priority_accuracy"], 0.5)
        self.assertEqual(result["sentiment_accuracy"], 0.5)
        self.assertEqual(result["exact_match_rate"], 0.5)
        self.assertEqual([item["ticket_id"] for item in result["ticket_results"]], ["a", "b"])
        self.assertEqual([item["passed"] for item in result["ticket_results"]], [True, False])
        self.assertEqual(result["ticket_results"][1]["errors"], [
            "category_mismatch",
            "priority_mismatch",
            "sentiment_mismatch",
        ])

    def test_missing_or_invalid_predictions_never_receive_credit(self):
        result = score_predictions(
            self.labels,
            [{"ticket_id": "a", "category": "payment_issue", "priority": "high", "sentiment": "urgent"}],
        )

        self.assertEqual(result["valid_predictions"], 1)
        self.assertEqual(result["invalid_predictions"], 1)
        self.assertEqual(result["exact_match_rate"], 0.5)
        missing = result["ticket_results"][1]
        self.assertFalse(missing["passed"])
        self.assertEqual(missing["errors"], ["missing_prediction"])

    def test_validation_record_can_invalidate_an_otherwise_matching_prediction(self):
        validation = [
            {"ticket_id": "a", "valid": True},
            {"ticket_id": "b", "valid": False, "errors": ["invalid_enum"]},
        ]
        result = score_predictions(self.labels, self.predictions, validation)

        self.assertEqual(result["valid_predictions"], 1)
        self.assertFalse(result["ticket_results"][1]["passed"])
        self.assertEqual(result["ticket_results"][1]["errors"], ["invalid_prediction"])

    def test_calculate_metrics_is_the_metric_only_view(self):
        metrics = calculate_metrics(self.labels, self.predictions)
        self.assertEqual(metrics["passed_tickets"], 1)
        self.assertNotIn("ticket_results", metrics)

    def test_error_analysis_and_suggestions_are_deterministic(self):
        result = score_predictions(self.labels, self.predictions)
        errors = analyze_errors(result["ticket_results"])
        self.assertEqual([item["ticket_id"] for item in errors], ["b"])
        suggestions = suggest_improvements(errors)
        self.assertGreaterEqual(len(suggestions), 2)
        self.assertLessEqual(len(suggestions), 4)
        self.assertEqual(suggestions, suggest_improvements(errors))

    def test_report_contains_metrics_errors_and_provider_boundary(self):
        result = score_predictions(self.labels, self.predictions)
        report = generate_report(result, provider={"provider": "local", "fallback": True})

        self.assertIn("# Evaluation report", report)
        self.assertIn("Category accuracy", report)
        self.assertIn("`b`: category_mismatch, priority_mismatch, sentiment_mismatch", report)
        self.assertIn("fallback output", report)
        self.assertGreaterEqual(report.count("\n"), 10)


if __name__ == "__main__":
    unittest.main()
