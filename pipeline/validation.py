"""Deterministic parsing and validation for model prediction JSON."""

from __future__ import annotations

import json
from typing import Any, Final, TypedDict

from pipeline.contracts import (
    CATEGORY_VALUES,
    PREDICTION_FIELDS,
    PRIORITY_VALUES,
    SENTIMENT_VALUES,
)


INVALID_JSON: Final[str] = "INVALID_JSON"
INVALID_PREDICTION_SHAPE: Final[str] = "INVALID_PREDICTION_SHAPE"
MISSING_REQUIRED_FIELD: Final[str] = "MISSING_REQUIRED_FIELD"
MISSING_SOURCE_TICKET_ID: Final[str] = "MISSING_SOURCE_TICKET_ID"
UNEXPECTED_FIELD: Final[str] = "UNEXPECTED_FIELD"
INVALID_FIELD_TYPE: Final[str] = "INVALID_FIELD_TYPE"
INVALID_ENUM_VALUE: Final[str] = "INVALID_ENUM_VALUE"
SOURCE_TICKET_ID_MISMATCH: Final[str] = "SOURCE_TICKET_ID_MISMATCH"


class ValidationError(TypedDict):
    """One deterministic validation failure."""

    code: str
    field: str | None


class ValidationRecord(TypedDict):
    """The stable result for one source ticket."""

    ticket_id: str
    valid: bool
    errors: list[ValidationError]
    prediction: dict[str, Any] | None


_FIELD_TYPES: Final[dict[str, type[str]]] = {
    "ticket_id": str,
    "category": str,
    "priority": str,
    "sentiment": str,
    "reasoning": str,
}
_FIELD_VALUES: Final[dict[str, tuple[str, ...]]] = {
    "category": CATEGORY_VALUES,
    "priority": PRIORITY_VALUES,
    "sentiment": SENTIMENT_VALUES,
}


def _error(code: str, field: str | None = None) -> ValidationError:
    return {"code": code, "field": field}


def _invalid_record(
    source_ticket_id: str, errors: list[ValidationError]
) -> ValidationRecord:
    return {
        "ticket_id": source_ticket_id,
        "valid": False,
        "errors": errors,
        "prediction": None,
    }


def _reject_non_json_constants(value: str) -> Any:
    raise ValueError(f"non-standard JSON constant: {value}")


def parse_prediction(raw_json: str | bytes, source_ticket_id: str) -> ValidationRecord:
    """Parse and validate one JSON prediction for ``source_ticket_id``.

    Parsing and validation are side-effect free.  Every failure is represented
    in the returned record rather than raised, making results suitable for a
    deterministic validation artifact.
    """

    try:
        decoded = json.loads(raw_json, parse_constant=_reject_non_json_constants)
    except (TypeError, ValueError, json.JSONDecodeError):
        return _invalid_record(source_ticket_id, [_error(INVALID_JSON)])
    return validate_prediction(decoded, source_ticket_id)


def validate_prediction(
    prediction: object, source_ticket_id: str
) -> ValidationRecord:
    """Validate a decoded prediction against the shared prediction contract."""

    if not isinstance(prediction, dict):
        return _invalid_record(source_ticket_id, [_error(INVALID_PREDICTION_SHAPE)])

    errors: list[ValidationError] = []
    expected_fields = set(PREDICTION_FIELDS)
    actual_fields = set(prediction)

    for field in PREDICTION_FIELDS:
        if field not in prediction:
            if field == "ticket_id":
                errors.append(_error(MISSING_SOURCE_TICKET_ID, field))
            else:
                errors.append(_error(MISSING_REQUIRED_FIELD, field))

    for field in sorted(actual_fields - expected_fields):
        errors.append(_error(UNEXPECTED_FIELD, field))

    for field in PREDICTION_FIELDS:
        if field not in prediction:
            continue
        value = prediction[field]
        if not isinstance(value, _FIELD_TYPES[field]):
            errors.append(_error(INVALID_FIELD_TYPE, field))
            continue
        if field in _FIELD_VALUES and value not in _FIELD_VALUES[field]:
            errors.append(_error(INVALID_ENUM_VALUE, field))

    if "ticket_id" in prediction and isinstance(prediction["ticket_id"], str):
        if prediction["ticket_id"] != source_ticket_id:
            errors.append(_error(SOURCE_TICKET_ID_MISMATCH, "ticket_id"))

    if errors:
        return _invalid_record(source_ticket_id, errors)

    normalized = {field: prediction[field] for field in PREDICTION_FIELDS}
    return {
        "ticket_id": source_ticket_id,
        "valid": True,
        "errors": [],
        "prediction": normalized,
    }


# Explicit name for callers that already have JSON text and prefer a schema-
# oriented function name.
def validate_prediction_json(
    raw_json: str | bytes, source_ticket_id: str
) -> ValidationRecord:
    """Alias for :func:`parse_prediction`."""

    return parse_prediction(raw_json, source_ticket_id)
