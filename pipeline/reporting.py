"""Deterministic Markdown reporting for evaluation results."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .scoring import SCORED_FIELDS


def _evaluation_parts(
    evaluation: Mapping[str, Any],
    ticket_results: Sequence[Mapping[str, Any]] | None,
) -> tuple[Mapping[str, Any], list[Mapping[str, Any]]]:
    metrics = evaluation.get("metrics", evaluation)
    if not isinstance(metrics, Mapping):
        raise TypeError("evaluation metrics must be a mapping")
    if ticket_results is None:
        embedded = evaluation.get("ticket_results", [])
        ticket_results = embedded if isinstance(embedded, Sequence) else []
    return metrics, list(ticket_results)


def analyze_errors(ticket_results: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return stable, machine-readable error details for failed tickets."""
    errors: list[dict[str, Any]] = []
    for result in ticket_results:
        result_errors = [str(error) for error in result.get("errors", [])]
        if not result_errors and not result.get("passed", False):
            result_errors = [
                f"{field}_mismatch"
                for field in SCORED_FIELDS
                if not result.get("field_matches", {}).get(field, False)
            ] or ["failed_evaluation"]
        if result_errors:
            errors.append(
                {
                    "ticket_id": str(result.get("ticket_id", "")),
                    "errors": result_errors,
                    "expected": result.get("expected", result.get("label")),
                    "predicted": result.get("predicted", result.get("prediction")),
                }
            )
    return sorted(errors, key=lambda item: item["ticket_id"])


def suggest_improvements(error_analysis: Sequence[Mapping[str, Any]]) -> list[str]:
    """Generate 2–4 concrete suggestions in a fixed priority order."""
    codes = {
        code
        for item in error_analysis
        for code in item.get("errors", [])
    }
    suggestions: list[str] = []
    if "invalid_prediction" in codes or "missing_prediction" in codes:
        suggestions.append(
            "Harden structured-output handling by validating required fields and enum values before scoring, then retrying or routing invalid outputs for review."
        )
    if "category_mismatch" in codes:
        suggestions.append(
            "Add category-boundary examples to the classification prompt and regression set, especially for tickets that could fit more than one category."
        )
    if "priority_mismatch" in codes:
        suggestions.append(
            "Make priority criteria explicit with observable urgency and impact thresholds, and test low/medium/high boundary cases."
        )
    if "sentiment_mismatch" in codes:
        suggestions.append(
            "Expand sentiment examples to distinguish neutral requests, frustrated complaints, and urgent language before deployment."
        )

    # A clean run still receives actionable maintenance guidance, and a sparse
    # error set receives a second suggestion without inventing an error type.
    if len(suggestions) < 2:
        suggestions.append(
            "Keep a deterministic labeled regression set and review metric changes after each prompt or model update."
        )
    if len(suggestions) < 2:
        suggestions.append(
            "Track invalid-output rate separately from label accuracy so provider and fallback behavior remain auditable."
        )
    return suggestions[:4]


def _format_rate(value: Any) -> str:
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return "n/a"


def _provider_note(provider: Any) -> str:
    if provider is None:
        return "Provider quality was not inferred from the deterministic score."
    if isinstance(provider, Mapping):
        name = provider.get("provider", provider.get("name", "unknown provider"))
        model = provider.get("model")
        fallback = provider.get("fallback", provider.get("is_fallback", False))
        mode = "fallback output" if fallback else "provider output"
        suffix = f" ({model})" if model else ""
        return f"Results represent {mode} from {name}{suffix}; this report does not treat fallback behavior as LLM quality evidence."
    if str(provider).lower() == "fallback":
        return "Results include fallback output; fallback behavior is not treated as LLM quality evidence."
    return f"Results are attributed to {provider}; provider quality is reported separately from deterministic scoring."


def generate_report(
    evaluation: Mapping[str, Any],
    ticket_results: Sequence[Mapping[str, Any]] | None = None,
    validation_records: Any = None,
    provider: Any = None,
) -> str:
    """Build a stable Markdown report from a score result or metric mapping."""
    metrics, results = _evaluation_parts(evaluation, ticket_results)
    error_analysis = analyze_errors(results)
    suggestions = suggest_improvements(error_analysis)
    total = metrics.get("total_tickets", len(results))
    valid = metrics.get("valid_predictions", "n/a")
    invalid = metrics.get("invalid_predictions", "n/a")

    lines = [
        "# Evaluation report",
        "",
        "## Summary",
        f"- Tickets evaluated: {total}",
        f"- Tickets passed: {metrics.get('passed_tickets', 'n/a')}",
        f"- Tickets failed: {metrics.get('failed_tickets', 'n/a')}",
        f"- Valid predictions: {valid}",
        f"- Invalid or missing predictions: {invalid}",
        f"- {_provider_note(provider)}",
        "",
        "## Metrics",
        "| Metric | Rate |",
        "| --- | ---: |",
        f"| Category accuracy | {_format_rate(metrics.get('category_accuracy'))} |",
        f"| Priority accuracy | {_format_rate(metrics.get('priority_accuracy'))} |",
        f"| Sentiment accuracy | {_format_rate(metrics.get('sentiment_accuracy'))} |",
        f"| Exact-match rate | {_format_rate(metrics.get('exact_match_rate'))} |",
        "",
        "## Validation status",
        f"- Validation records supplied: {'yes' if validation_records is not None else 'no'}",
        "- Invalid and missing predictions are counted as failed, never as correct.",
        "",
        "## Deterministic error analysis",
    ]
    if error_analysis:
        for item in error_analysis:
            codes = ", ".join(item["errors"])
            lines.append(f"- `{item['ticket_id']}`: {codes}")
    else:
        lines.append("- No failed tickets.")

    lines.extend(["", "## Improvement suggestions"])
    lines.extend(f"{index}. {suggestion}" for index, suggestion in enumerate(suggestions, 1))
    return "\n".join(lines) + "\n"


# Alias useful to pipeline callers that name the artifact builder explicitly.
build_report = generate_report

__all__ = [
    "analyze_errors",
    "build_report",
    "generate_report",
    "suggest_improvements",
]
