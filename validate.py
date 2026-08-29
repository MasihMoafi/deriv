#!/usr/bin/env python3
"""Independently verify a completed pipeline artifact directory."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from pipeline.contracts import CATEGORY_VALUES, PRIORITY_VALUES, SENTIMENT_VALUES
from pipeline.scoring import calculate_metrics
from pipeline.validation import parse_prediction


def _load(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def verify(output_dir: str | Path = ".") -> list[str]:
    root = Path(output_dir)
    errors: list[str] = []
    required = (
        "tickets.json",
        "labels.json",
        "validation.json",
        "metrics.json",
        "report.md",
        "llm_calls.jsonl",
    )
    for name in required:
        if not (root / name).is_file():
            errors.append(f"missing artifact: {name}")
    if errors:
        return errors

    try:
        tickets = _load(root / "tickets.json")
        labels = _load(root / "labels.json")
        validation_artifact = _load(root / "validation.json")
        metrics = _load(root / "metrics.json")
    except (OSError, json.JSONDecodeError) as exc:
        return [f"invalid core artifact JSON: {exc}"]

    if not isinstance(tickets, list) or not isinstance(labels, dict):
        errors.append("tickets.json must be an array and labels.json must be an object keyed by ticket_id")
        return errors
    required_ticket_fields = ("ticket_id", "subject", "message", "channel")
    ticket_ids: list[Any] = []
    for index, ticket in enumerate(tickets):
        if not isinstance(ticket, dict):
            errors.append(f"ticket at index {index} is not an object")
            ticket_ids.append(None)
            continue
        ticket_ids.append(ticket.get("ticket_id"))
        for field in required_ticket_fields:
            if not isinstance(ticket.get(field), str):
                errors.append(f"ticket {index} missing string field: {field}")
    if any(not isinstance(ticket_id, str) or not ticket_id for ticket_id in ticket_ids):
        errors.append("every ticket must have a non-empty string ticket_id")
    valid_ticket_ids = [ticket_id for ticket_id in ticket_ids if isinstance(ticket_id, str)]
    if len(set(valid_ticket_ids)) != len(valid_ticket_ids):
        errors.append("tickets.json contains duplicate ticket IDs")

    label_ids = list(labels)
    if any(not isinstance(ticket_id, str) or not ticket_id for ticket_id in label_ids):
        errors.append("labels.json keys must be non-empty string ticket IDs")
    if sorted(label_ids) != sorted(valid_ticket_ids):
        errors.append("labels.json keys must match tickets.json ticket IDs")
    allowed = {
        "category": set(CATEGORY_VALUES),
        "priority": set(PRIORITY_VALUES),
        "sentiment": set(SENTIMENT_VALUES),
    }
    for ticket_id, label in labels.items():
        if not isinstance(label, dict):
            errors.append(f"label {ticket_id} is not an object")
            continue
        for field, values in allowed.items():
            if label.get(field) not in values:
                errors.append(f"label {ticket_id} has invalid or missing {field}")
    if errors:
        return errors

    prediction_values: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    for ticket_id in ticket_ids:
        prediction_path = root / "predictions" / f"{ticket_id}.json"
        if not prediction_path.is_file():
            errors.append(f"missing prediction file: {prediction_path.name}")
            records.append({
                "ticket_id": ticket_id,
                "valid": False,
                "errors": [{"code": "MISSING_PREDICTION_FILE", "field": None}],
                "prediction": None,
            })
            continue
        try:
            raw = prediction_path.read_bytes()
            record = parse_prediction(raw, ticket_id)
        except OSError as exc:
            errors.append(f"cannot read prediction {ticket_id}: {exc}")
            continue
        records.append(record)
        if not record["valid"]:
            errors.append(f"invalid prediction {ticket_id}: {record['errors']}")
        elif record["prediction"] is not None:
            prediction_values.append(record["prediction"])

    expected_prediction_names = {f"{ticket_id}.json" for ticket_id in ticket_ids}
    predictions_dir = root / "predictions"
    if predictions_dir.is_dir():
        for prediction_path in predictions_dir.glob("*.json"):
            if prediction_path.name not in expected_prediction_names:
                errors.append(f"unexpected prediction file: {prediction_path.name}")

    artifact_records = validation_artifact.get("records") if isinstance(validation_artifact, dict) else None
    if artifact_records != records:
        errors.append("validation.json does not match independently recomputed validation")
    if isinstance(validation_artifact, dict):
        expected_valid = all(record["valid"] for record in records)
        expected_summary = {
            "total": len(records),
            "valid": sum(record["valid"] for record in records),
            "invalid": sum(not record["valid"] for record in records),
        }
        if validation_artifact.get("valid") is not expected_valid:
            errors.append("validation.json valid flag does not match its records")
        if validation_artifact.get("summary") != expected_summary:
            errors.append("validation.json summary does not match its records")


    calls: list[dict[str, Any]] = []
    try:
        with (root / "llm_calls.jsonl").open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    calls.append(json.loads(line))
                except json.JSONDecodeError:
                    errors.append(f"invalid JSON in llm_calls.jsonl line {line_number}")
    except OSError as exc:
        errors.append(f"cannot read llm_calls.jsonl: {exc}")
    call_ids = [item.get("ticket_id") for item in calls if item.get("stage") == "classify"]
    if len(calls) != len(ticket_ids) or sorted(call_ids) != sorted(ticket_ids):
        errors.append("llm_calls.jsonl must contain exactly one classify record per ticket")
    for item in calls:
        for field in ("stage", "ticket_id", "timestamp", "provider", "model", "prompt_version", "output_artifact"):
            if field not in item:
                errors.append(f"call record missing field: {field}")
        timestamp = item.get("timestamp")
        if not isinstance(timestamp, str):
            errors.append("call record timestamp must be a string")
        else:
            try:
                datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError:
                errors.append("call record timestamp must be ISO-8601")

    recomputed = calculate_metrics(labels, prediction_values, records)
    if metrics != recomputed:
        errors.append("metrics.json does not match deterministic recomputation")
    report_text = (root / "report.md").read_text(encoding="utf-8")
    if not report_text.strip():
        errors.append("report.md is empty")
    required_report_sections = (
        "# Evaluation report",
        "## Summary",
        "## Metrics",
        "## Validation status",
        "## Deterministic error analysis",
        "## Improvement suggestions",
    )
    for section in required_report_sections:
        if section not in report_text:
            errors.append(f"report.md missing required section: {section}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=".", type=Path)
    args = parser.parse_args()
    errors = verify(args.output_dir)
    if errors:
        print("VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("VALIDATION OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
