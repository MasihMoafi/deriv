"""Replayable orchestration for LOAD_INPUTS -> CLASSIFY -> VALIDATE -> SCORE -> REPORT."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import ARTIFACT_NAMES
from .llm import LLMAdapter, PROMPT_VERSION
from .reporting import generate_report
from .scoring import score_predictions
from .validation import parse_prediction


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, sort_keys=True)
        handle.write("\n")


def load_inputs(tickets_path: Path, labels_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    tickets = _read_json(tickets_path)
    labels = _read_json(labels_path)
    if not isinstance(tickets, list) or not isinstance(labels, list):
        raise ValueError("tickets.json and labels.json must contain arrays")
    return tickets, labels


def classify(
    tickets: list[dict[str, Any]], output_dir: Path, adapter: LLMAdapter
) -> list[dict[str, Any]]:
    predictions_dir = output_dir / "predictions"
    predictions_dir.mkdir(parents=True, exist_ok=True)
    for old_file in predictions_dir.glob("*.json"):
        old_file.unlink()
    calls_path = output_dir / "llm_calls.jsonl"
    predictions: list[dict[str, Any]] = []
    with calls_path.open("w", encoding="utf-8") as calls:
        for ticket in tickets:
            result = adapter.classify(ticket)
            artifact = f"predictions/{ticket['ticket_id']}.json"
            _write_json(output_dir / artifact, result.prediction)
            predictions.append(result.prediction)
            calls.write(
                json.dumps(
                    {
                        "stage": "CLASSIFY",
                        "ticket_id": ticket["ticket_id"],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "provider": result.provider,
                        "model": result.model,
                        "prompt_version": PROMPT_VERSION,
                        "output_artifact": artifact,
                        "fallback": result.fallback,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
    return predictions


def validate_stage(
    tickets: list[dict[str, Any]], output_dir: Path
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for ticket in tickets:
        prediction_path = output_dir / "predictions" / f"{ticket['ticket_id']}.json"
        if not prediction_path.exists():
            record = {
                "ticket_id": ticket["ticket_id"],
                "valid": False,
                "errors": [{"code": "MISSING_PREDICTION_FILE", "field": None}],
                "prediction": None,
            }
        else:
            record = parse_prediction(prediction_path.read_bytes(), ticket["ticket_id"])
        records.append(record)
    result = {
        "valid": all(record["valid"] for record in records),
        "records": records,
        "summary": {
            "total": len(records),
            "valid": sum(record["valid"] for record in records),
            "invalid": sum(not record["valid"] for record in records),
        },
    }
    _write_json(output_dir / "validation.json", result)
    return result


def score_stage(
    labels: list[dict[str, Any]],
    validation: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    predictions: list[dict[str, Any]] = []
    for record in validation["records"]:
        prediction = record.get("prediction")
        if prediction is not None:
            predictions.append(prediction)
    evaluation = score_predictions(labels, predictions, validation["records"])
    _write_json(output_dir / "metrics.json", evaluation["metrics"])
    return evaluation


def report_stage(
    evaluation: dict[str, Any], validation: dict[str, Any], adapter: LLMAdapter, output_dir: Path
) -> str:
    report = generate_report(
        evaluation,
        validation_records=validation["records"],
        provider={
            "provider": adapter.provider,
            "model": adapter.model,
            "fallback": adapter.provider != "openrouter",
        },
    )
    (output_dir / "report.md").write_text(report, encoding="utf-8")
    return report


def run_pipeline(
    tickets_path: str | Path = "tickets.json",
    labels_path: str | Path = "labels.json",
    output_dir: str | Path = ".",
    provider: str | None = None,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    tickets, labels = load_inputs(Path(tickets_path), Path(labels_path))
    _write_json(output / "tickets.json", tickets)
    _write_json(output / "labels.json", labels)
    adapter = LLMAdapter.from_environment(provider)
    classify(tickets, output, adapter)
    validation = validate_stage(tickets, output)
    evaluation = score_stage(labels, validation, output)
    report = report_stage(evaluation, validation, adapter, output)
    return {
        "stages": ["LOAD_INPUTS", "CLASSIFY", "VALIDATE", "SCORE", "REPORT"],
        "validation": validation,
        "evaluation": evaluation,
        "report": report,
        "provider": adapter.provider,
        "model": adapter.model,
        "artifacts": list(ARTIFACT_NAMES),
    }
