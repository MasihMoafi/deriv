#!/usr/bin/env python3
"""Independently verify a completed pipeline artifact directory."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

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

    if not isinstance(tickets, list) or not isinstance(labels, list):
        errors.append("tickets.json and labels.json must be arrays")
        return errors
    ticket_ids = [ticket.get("ticket_id") for ticket in tickets]
    if any(not isinstance(ticket_id, str) or not ticket_id for ticket_id in ticket_ids):
        errors.append("every ticket must have a non-empty string ticket_id")
    if len(set(ticket_ids)) != len(ticket_ids):
        errors.append("tickets.json contains duplicate ticket IDs")

    prediction_values: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    for ticket_id in ticket_ids:
        prediction_path = root / "predictions" / f"{ticket_id}.json"
        if not prediction_path.is_file():
            errors.append(f"missing prediction file: {prediction_path.name}")
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

    artifact_records = validation_artifact.get("records") if isinstance(validation_artifact, dict) else None
    if artifact_records != records:
        errors.append("validation.json does not match independently recomputed validation")

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
    call_ids = [item.get("ticket_id") for item in calls if item.get("stage") == "CLASSIFY"]
    if len(calls) != len(ticket_ids) or sorted(call_ids) != sorted(ticket_ids):
        errors.append("llm_calls.jsonl must contain exactly one CLASSIFY record per ticket")
    for item in calls:
        for field in ("stage", "ticket_id", "timestamp", "provider", "model", "prompt_version", "output_artifact"):
            if field not in item:
                errors.append(f"call record missing field: {field}")

    recomputed = calculate_metrics(labels, prediction_values, records)
    if metrics != recomputed:
        errors.append("metrics.json does not match deterministic recomputation")
    if not (root / "report.md").read_text(encoding="utf-8").strip():
        errors.append("report.md is empty")
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
