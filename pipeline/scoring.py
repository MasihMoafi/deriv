"""Deterministic scoring for ticket labels and predictions.

The scorer deliberately treats a missing or invalid prediction as incorrect.  This
keeps metrics conservative and makes them reproducible from the saved labels,
predictions, and validation records.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .contracts import CATEGORY_VALUES, PRIORITY_VALUES, SENTIMENT_VALUES

SCORED_FIELDS = ("category", "priority", "sentiment")
_METRIC_NAMES = {
    "category": "category_accuracy",
    "priority": "priority_accuracy",
    "sentiment": "sentiment_accuracy",
}
_ALLOWED_VALUES = {
    "category": frozenset(CATEGORY_VALUES),
    "priority": frozenset(PRIORITY_VALUES),
    "sentiment": frozenset(SENTIMENT_VALUES),
}


def _records_by_ticket(records: Any, *, name: str) -> dict[str, Mapping[str, Any]]:
    """Return records keyed by ticket ID without changing caller-owned data."""
    if records is None:
        return {}
    if isinstance(records, Mapping):
        if "ticket_id" in records:
            values = [records]
        else:
            values = []
            for ticket_id in sorted(records, key=str):
                value = records[ticket_id]
                if isinstance(value, Mapping):
                    if "ticket_id" not in value:
                        value = {"ticket_id": ticket_id, **value}
                    values.append(value)
                else:
                    raise TypeError(f"{name} record for {ticket_id!r} is not a mapping")
    elif isinstance(records, Sequence) and not isinstance(records, (str, bytes, bytearray)):
        values = list(records)
    else:
        raise TypeError(f"{name} must be a mapping or sequence of mappings")

    result: dict[str, Mapping[str, Any]] = {}
    for record in values:
        if not isinstance(record, Mapping):
            raise TypeError(f"{name} contains a non-mapping record")
        ticket_id = record.get("ticket_id")
        if not isinstance(ticket_id, str) or not ticket_id:
            raise ValueError(f"{name} contains a record without a non-empty ticket_id")
        if ticket_id in result:
            raise ValueError(f"duplicate {name} ticket_id: {ticket_id}")
        result[ticket_id] = record
    return result


def _validation_is_valid(record: Mapping[str, Any] | None) -> bool:
    """Interpret common validation-record shapes without relying on one validator."""
    if record is None:
        return True
    for key in ("valid", "is_valid"):
        if key in record:
            return record[key] is True
    status = record.get("status")
    if status is not None:
        return str(status).lower() in {"valid", "ok", "passed", "pass"}
    errors = record.get("errors", record.get("error_codes"))
    if errors is not None:
        return not bool(errors)
    return True


def _prediction_is_valid(prediction: Mapping[str, Any] | None, ticket_id: str) -> bool:
    if prediction is None or prediction.get("ticket_id") != ticket_id:
        return False
    return all(
        prediction.get(field) in _ALLOWED_VALUES[field] for field in SCORED_FIELDS
    )


def _sorted_ids(labels: Mapping[str, Mapping[str, Any]], predictions: Mapping[str, Mapping[str, Any]]) -> list[str]:
    return sorted(set(labels) | set(predictions), key=str)


def _score_ticket(
    ticket_id: str,
    label: Mapping[str, Any] | None,
    prediction: Mapping[str, Any] | None,
    validation_record: Mapping[str, Any] | None,
) -> dict[str, Any]:
    valid_prediction = _prediction_is_valid(prediction, ticket_id)
    if not _validation_is_valid(validation_record):
        valid_prediction = False

    expected = {field: label.get(field) for field in SCORED_FIELDS} if label else None
    predicted = (
        {field: prediction.get(field) for field in SCORED_FIELDS}
        if prediction
        else None
    )
    field_matches = {
        field: bool(
            valid_prediction
            and label is not None
            and prediction is not None
            and prediction.get(field) == label.get(field)
        )
        for field in SCORED_FIELDS
    }
    errors: list[str] = []
    if label is None:
        errors.append("missing_label")
    if prediction is None:
        errors.append("missing_prediction")
    elif not valid_prediction:
        errors.append("invalid_prediction")
    if label is not None and valid_prediction and prediction is not None:
        errors.extend(
            f"{field}_mismatch"
            for field in SCORED_FIELDS
            if not field_matches[field]
        )

    exact_match = bool(valid_prediction and label is not None and all(field_matches.values()))
    return {
        "ticket_id": ticket_id,
        "expected": expected,
        "predicted": predicted,
        "label": expected,
        "prediction": predicted,
        "valid_prediction": valid_prediction,
        "field_matches": field_matches,
        "exact_match": exact_match,
        "passed": exact_match,
        "errors": errors,
    }


def _metrics(ticket_results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    total = len(ticket_results)
    metrics: dict[str, Any] = {
        "total_tickets": total,
        "valid_predictions": sum(bool(item["valid_prediction"]) for item in ticket_results),
        "invalid_predictions": sum(not bool(item["valid_prediction"]) for item in ticket_results),
        "passed_tickets": sum(bool(item["passed"]) for item in ticket_results),
        "failed_tickets": sum(not bool(item["passed"]) for item in ticket_results),
    }
    for field, metric_name in _METRIC_NAMES.items():
        correct = sum(
            bool(item["field_matches"][field]) for item in ticket_results
        )
        metrics[metric_name] = correct / total if total else 0.0
    exact_matches = sum(bool(item["exact_match"]) for item in ticket_results)
    metrics["exact_match_rate"] = exact_matches / total if total else 0.0
    return metrics


def score_predictions(
    labels: Any,
    predictions: Any,
    validation_records: Any = None,
) -> dict[str, Any]:
    """Score predictions and return metrics with deterministic ticket results.

    ``labels`` and ``predictions`` may be sequences of records or mappings keyed
    by ticket ID.  Ticket results are sorted by ticket ID, so output does not
    depend on dictionary insertion order.
    """
    label_map = _records_by_ticket(labels, name="labels")
    prediction_map = _records_by_ticket(predictions, name="predictions")
    validation_map = _records_by_ticket(validation_records, name="validation_records")
    ticket_results = [
        _score_ticket(
            ticket_id,
            label_map.get(ticket_id),
            prediction_map.get(ticket_id),
            validation_map.get(ticket_id),
        )
        for ticket_id in _sorted_ids(label_map, prediction_map)
    ]
    metrics = _metrics(ticket_results)
    return {
        "metrics": metrics,
        "ticket_results": ticket_results,
        "errors": [item for item in ticket_results if item["errors"]],
        **metrics,
    }


def calculate_metrics(
    labels: Any,
    predictions: Any,
    validation_records: Any = None,
) -> dict[str, Any]:
    """Return only the deterministic metric mapping."""
    return score_predictions(labels, predictions, validation_records)["metrics"]


# A descriptive alias for callers that prefer evaluation terminology.
evaluate_predictions = score_predictions

__all__ = [
    "SCORED_FIELDS",
    "calculate_metrics",
    "evaluate_predictions",
    "score_predictions",
]
