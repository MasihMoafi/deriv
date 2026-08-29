# Replayable AI Ticket Evaluation

This project evaluates structured support-ticket classifications while keeping model output separate from deterministic validation, scoring, and reporting.

## Run
Inputs use a JSON array of `{ticket_id, subject, message, channel}` ticket objects and a JSON object keyed by `ticket_id` for gold labels.

The primary provider is OpenRouter. The default model is the sibling-project-confirmed `openai/gpt-5.6-luna`; set `OPENROUTER_MODEL` to override it with `openai/gpt-oss-120b` or `openai/gpt-oss-20b`:

```bash
export OPENROUTER_API_KEY='...'
export OPENROUTER_MODEL='openai/gpt-5.6-luna'
python run.py
```

If a live response is wrapped in a Markdown JSON fence, the fence is stripped locally before validation; no second LLM request is made.

The request sends only the original ticket fields and asks for the exact prediction JSON schema. There is one request and one `llm_calls.jsonl` record per ticket. If credentials/model configuration is unavailable, select the inspectable deterministic fallback explicitly:

```bash
python run.py --provider local
```

Fallback output proves artifact mechanics only; it is not evidence of LLM quality. A different output directory can be used for replay inspection:

```bash
python run.py --provider local --output-dir /tmp/ticket-evaluation-run
python validate.py --output-dir /tmp/ticket-evaluation-run
```

## Stage order and artifacts

`run.py` executes `LOAD_INPUTS -> CLASSIFY -> VALIDATE -> SCORE -> REPORT` and writes `tickets.json`, `labels.json`, `predictions/{ticket_id}.json`, `validation.json`, `metrics.json`, `report.md`, and `llm_calls.jsonl`. `validate.py` independently checks presence, prediction schemas/source IDs, one classification log per ticket, report existence, and exact deterministic metric recomputation.

For the standalone synthetic failure-case experiment:

```bash
python run.py --provider local \
  --tickets tests/fixtures/synthetic_tickets.json \
  --labels tests/fixtures/synthetic_labels.json \
  --output-dir /tmp/deriv-synthetic-e2e/output
python validate.py --output-dir /tmp/deriv-synthetic-e2e/output
```

The raw run record is in `EXPERIMENT_WORKFLOW.md`; these five tickets intentionally produce a different metric profile from the sample run.

## Focused checks

The project uses small dependency-free focused checks. The scoring/reporting and integration groups use `unittest`; the validation tests are pytest-style functions and can be run with pytest when available (or with the direct six-function fallback used in this environment):

```bash
python -m unittest discover -s tests -p 'test_scoring_reporting.py' -v
python -m unittest discover -s tests -p 'test_integration.py' -v
python run.py --provider local
python validate.py
```

The sample labels include an intentionally ambiguous synthetic case so the deterministic report has useful error analysis. Do not interpret its fallback metrics as a provider benchmark.
