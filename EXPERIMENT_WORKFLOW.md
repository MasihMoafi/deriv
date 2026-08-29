# Synthetic End-to-End Experiment Record

## Objective

Determine whether the ticket pipeline can consume standalone synthetic fixtures using the authoritative schema, execute all five stages end to end, preserve one output and one classification record per ticket, and detect deterministic scoring failures without reusing the six-ticket sample metrics.

This experiment is intentionally a ticket-classification integration test, not a retrieval experiment. It does not use semantic, keyword, or hybrid document queries.

## Source material

- Tickets: `/home/masih/Desktop/p/deriv/tests/fixtures/synthetic_tickets.json`
  - JSON array, 884 bytes, 5 tickets.
  - Each record has `ticket_id`, `subject`, `message`, and `channel`.
- Gold labels: `/home/masih/Desktop/p/deriv/tests/fixtures/synthetic_labels.json`
  - Keyed JSON object, 540 bytes, 5 label entries.
  - Keys match the synthetic ticket IDs.
- Input parser: standard-library JSON loading in `pipeline/workflow.py`.
- Prediction validator: deterministic `pipeline/validation.py`.
- Scorer/report generator: deterministic `pipeline/scoring.py` and `pipeline/reporting.py`.

## Execution

```bash
python run.py \
  --provider local \
  --tickets /home/masih/Desktop/p/deriv/tests/fixtures/synthetic_tickets.json \
  --labels /home/masih/Desktop/p/deriv/tests/fixtures/synthetic_labels.json \
  --output-dir /tmp/deriv-synthetic-e2e/output
python validate.py --output-dir /tmp/deriv-synthetic-e2e/output
```

The local fallback was selected deliberately to isolate pipeline mechanics from provider quality. No second LLM request or retry was used.

## Raw metrics

- Wall-clock command time: 104 ms.
- Ticket count: 5.
- Label key count: 5.
- Prediction files: 5.
- Classification log records: 5.
- Validation summary: valid.
- Pipeline output: `LOAD_INPUTS -> CLASSIFY -> VALIDATE -> SCORE -> REPORT`.
- Independent validation: `VALIDATION OK`.
- Category accuracy: `0.8`.
- Priority accuracy: `0.4`.
- Sentiment accuracy: `0.4`.
- Exact-match rate: `0.0`.
- Valid predictions: `5`.
- Invalid predictions: `0`.
- Passed tickets: `0`.
- Failed tickets: `5`.

Deterministic error analysis:

- `SYN-001`: priority mismatch, sentiment mismatch.
- `SYN-002`: sentiment mismatch.
- `SYN-003`: priority mismatch.
- `SYN-004`: priority mismatch, sentiment mismatch.
- `SYN-005`: category mismatch.

## Conclusion

The fixture-backed end-to-end path works with standalone files and produces metrics different from the six-ticket sample. It also exposes deliberate label/prediction disagreements without treating valid-but-wrong predictions as invalid. This is evidence of deterministic pipeline behavior, not evidence of LLM quality because the local fallback was selected.

## Query approval boundary

The experiment-workflow skill describes a 3x10 semantic/keyword/hybrid query campaign for retrieval systems and requires creator approval before execution. No such campaign was run or represented as completed here. Running one would be out of scope for this ticket-classification pipeline without an explicit query design and approval.
