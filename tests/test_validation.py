import json
import unittest

from pipeline.validation import (
    INVALID_ENUM_VALUE,
    INVALID_JSON,
    MISSING_REQUIRED_FIELD,
    MISSING_SOURCE_TICKET_ID,
    SOURCE_TICKET_ID_MISMATCH,
    UNEXPECTED_FIELD,
    parse_prediction,
)

SOURCE_TICKET_ID = "ticket-42"


def prediction(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "ticket_id": SOURCE_TICKET_ID,
        "category": "payment_issue",
        "priority": "high",
        "sentiment": "frustrated",
        "reasoning": "The payment was declined.",
    }
    value.update(overrides)
    return value


class ValidationTests(unittest.TestCase):
    def test_valid_prediction_is_normalized_into_a_stable_record(self) -> None:
        raw = json.dumps(prediction())

        record = parse_prediction(raw, SOURCE_TICKET_ID)

        self.assertEqual(
            record,
            {
                "ticket_id": SOURCE_TICKET_ID,
                "valid": True,
                "errors": [],
                "prediction": prediction(),
            },
        )

    def test_invalid_json_has_a_stable_error_code(self) -> None:
        record = parse_prediction('{"ticket_id":', SOURCE_TICKET_ID)

        self.assertFalse(record["valid"])
        self.assertEqual(record["errors"], [{"code": INVALID_JSON, "field": None}])
        self.assertIsNone(record["prediction"])

    def test_missing_required_fields_are_reported_in_schema_order(self) -> None:
        raw = json.dumps({"ticket_id": SOURCE_TICKET_ID})

        record = parse_prediction(raw, SOURCE_TICKET_ID)

        self.assertEqual(
            record["errors"],
            [
                {"code": MISSING_REQUIRED_FIELD, "field": "category"},
                {"code": MISSING_REQUIRED_FIELD, "field": "priority"},
                {"code": MISSING_REQUIRED_FIELD, "field": "sentiment"},
                {"code": MISSING_REQUIRED_FIELD, "field": "reasoning"},
            ],
        )

    def test_missing_and_unexpected_fields_are_invalid(self) -> None:
        value = prediction()
        del value["ticket_id"]
        value["extra"] = "not part of the schema"

        record = parse_prediction(json.dumps(value), SOURCE_TICKET_ID)

        self.assertEqual(
            record["errors"],
            [
                {"code": MISSING_SOURCE_TICKET_ID, "field": "ticket_id"},
                {"code": UNEXPECTED_FIELD, "field": "extra"},
            ],
        )

    def test_invalid_enum_values_are_reported_for_each_enum_field(self) -> None:
        raw = json.dumps(
            prediction(category="unknown", priority="critical", sentiment="angry")
        )

        record = parse_prediction(raw, SOURCE_TICKET_ID)

        self.assertEqual(
            record["errors"],
            [
                {"code": INVALID_ENUM_VALUE, "field": "category"},
                {"code": INVALID_ENUM_VALUE, "field": "priority"},
                {"code": INVALID_ENUM_VALUE, "field": "sentiment"},
            ],
        )

    def test_prediction_must_match_the_source_ticket_id(self) -> None:
        record = parse_prediction(
            json.dumps(prediction(ticket_id="ticket-99")), SOURCE_TICKET_ID
        )

        self.assertEqual(
            record["errors"],
            [{"code": SOURCE_TICKET_ID_MISMATCH, "field": "ticket_id"}],
        )


if __name__ == "__main__":
    unittest.main()
