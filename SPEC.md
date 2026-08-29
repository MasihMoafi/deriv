# Specification

## Goal

Build a genuine, replayable AI evaluation pipeline for support-ticket classification. The pipeline must separate model behavior from deterministic validation and evaluation, preserve the inputs and outputs needed for replay, and make provider use auditable.

## Exact input schemas

`tickets.json` is a JSON array. Each ticket object has exactly these required fields:

```json
{
  "ticket_id": "string",
  "subject": "string",
  "message": "string"
}
```

`labels.json` is a JSON array. Each label object has these required fields:

```json
{
  "ticket_id": "string",
  "category": "payment_issue | account_verification | login_access | trading_problem | other",
  "priority": "low | medium | high",
  "sentiment": "neutral | frustrated | urgent"
}
```

The set of label ticket IDs must match the input ticket IDs. Ticket IDs are unique non-empty strings.

## Exact prediction schema

Each `predictions/{ticket_id}.json` file must contain exactly the following required fields:

```text
ticket_id: string
category: payment_issue | account_verification | login_access | trading_problem | other
priority: low | medium | high
sentiment: neutral | frustrated | urgent
reasoning: string
```

`reasoning` is model-produced explanatory text and is not used as a scoring dimension.

## Required pipeline

`LOAD_INPUTS -> CLASSIFY -> VALIDATE -> SCORE -> REPORT`

`python run.py` must execute those stages in that order and produce all required artifacts. The run is replayable from the saved inputs, labels, predictions, validation records, metrics, report, and LLM call log.

## Required artifacts

- `tickets.json`
- `labels.json`
- `predictions/{ticket_id}.json`
- `validation.json`
- `metrics.json`
- `report.md`
- `llm_calls.jsonl`

The output directory may be configurable, but the default is the repository root and the artifact names remain unchanged.

## LLM contract

OpenRouter is the primary provider. Credentials are read from `OPENROUTER_API_KEY`; the configured model is read from `OPENROUTER_MODEL`. There must be exactly one LLM request per ticket. The request sends the original ticket fields and asks for JSON only using the exact prediction schema. It must not include labels, gold answers, scoring instructions, or hardcoded ticket-specific expected outputs. One prediction file and one classification log record are written per ticket. Each log record includes `stage`, `ticket_id`, ISO timestamp, `provider`, `model`, `prompt_version`, and `output_artifact`.

If local JSON repair is implemented, it may repair a response without making a second LLM request. If live credentials are unavailable, an explicitly selected deterministic local fallback may be used so the artifact pipeline remains inspectable. Fallback results must be identified as fallback output and must not be presented as evidence of LLM quality.

## Deterministic-code requirement

Prediction parsing/schema validation, source-ID validation, enum checks, per-ticket validation records, scoring, metric computation, metric comparison, artifact checks, and report generation are deterministic Python code. No labels or scoring instructions may enter the classification prompt. No ticket IDs, exact sample text, or expected sample outputs may be hardcoded into implementation logic.

## Metrics

`metrics.json` must contain overall accuracy for category, priority, and sentiment, plus exact-match rate. Exact match means all three scored fields match the corresponding label for a valid prediction. Metrics must be recomputable from labels, predictions, and validation records and must be compared by `validate.py`.

## Validation behavior

Validation must detect invalid JSON, missing required fields, invalid enum values, wrong or missing source `ticket_id`, and missing prediction files. It must emit deterministic per-ticket records and stable error codes. Invalid predictions must not silently receive a correct score.

## Report behavior

`report.md` must contain a summary, metric results, validation status, deterministic error analysis, and 2–4 concrete improvement suggestions. It must distinguish model/provider quality from fallback or invalid-output pipeline behavior.

## Independent validation command

`python validate.py` independently verifies that required artifacts exist, every input ticket has a prediction file, prediction files are valid JSON with valid schemas and source IDs, exactly one classification call log exists per ticket, metrics can be recomputed deterministically and match `metrics.json`, and `report.md` exists.

## Testing and time control

Use focused checks only: one validation test group, one scoring/report test group, one end-to-end integration run, and one independent validation-command run. Do not build a large test framework or speculative abstractions. Stop within the 30-minute execution limit unless a narrow blocker fix is required.
