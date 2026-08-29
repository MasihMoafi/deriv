# Vision

## What this is

This is a compact, replayable AI ticket-evaluation project. It turns support tickets into structured category, priority, and sentiment predictions, preserves the model interaction, validates the output, compares it with labels, and writes an inspectable report.

## Why it exists

A model response is not an evaluation pipeline by itself. This project exists to make the boundary between nondeterministic model output and deterministic engineering explicit: every ticket should have one attributable classification attempt, every prediction should be checked against a contract, and every reported metric should be reproducible from saved artifacts.

## Top-level layout

```text
ES.md                 execution intent and verification record
SPEC.md               complete data, stage, artifact, and behavior specification
VISION.md             project purpose and honest scope
README.md             usage and replay instructions
run.py                pipeline entry point
validate.py           independent artifact/metric verifier
tickets.json          sample ticket inputs
labels.json           sample gold labels
pipeline/
  contracts.py        shared schemas, enum values, and artifact names
  llm.py              OpenRouter adapter and explicit local fallback
  workflow.py         LOAD_INPUTS through REPORT orchestration
tests/
  test_validation.py
  test_scoring_reporting.py
  test_integration.py
predictions/          one prediction JSON file per ticket at runtime
validation.json       deterministic validation results at runtime
metrics.json          deterministic metrics at runtime
report.md             deterministic evaluation report at runtime
llm_calls.jsonl       one classification record per ticket at runtime
```

## Starting-point honesty

The repository begins as an empty project. At this point only the starting worktree state is verified; implementation claims, live-provider behavior, and quality conclusions must be backed by focused tests and artifact validation. A deterministic local fallback can prove pipeline mechanics, but it cannot prove LLM quality.
