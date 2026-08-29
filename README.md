# Replayable AI Ticket Evaluation

This project evaluates structured support-ticket classifications while keeping model output separate from deterministic validation, scoring, and reporting.

## Run

The primary provider is OpenRouter. Configure both variables to use it:

```bash
export OPENROUTER_API_KEY='...'
export OPENROUTER_MODEL='...'
python run.py
```

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

## Focused checks

The project uses dependency-free `unittest` tests:

```bash
python -m unittest discover -s tests -p 'test_validation.py' -v
python -m unittest discover -s tests -p 'test_scoring_reporting.py' -v
python -m unittest discover -s tests -p 'test_integration.py' -v
python run.py --provider local
python validate.py
```

The sample labels include an intentionally ambiguous synthetic case so the deterministic report has useful error analysis. Do not interpret its fallback metrics as a provider benchmark.
