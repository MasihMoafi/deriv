# Prompt Comparison

## Experimental control

Both prompt versions used the same six `tickets.json` inputs, the same `labels.json`, the same model (`openai/gpt-oss-120b` via OpenRouter), temperature `0`, one request per ticket, identical deterministic validation/scoring, and no sample-specific answers.

## Results

| Metric | v1: minimal schema instruction | v2: general decision guidance | Delta |
|---|---:|---:|---:|
| Category accuracy | 0.8333 | 1.0000 | +0.1667 |
| Priority accuracy | 0.8333 | 0.8333 | +0.0000 |
| Sentiment accuracy | 0.8333 | 0.8333 | +0.0000 |
| Exact-match rate | 0.5000 | 0.6667 | +0.1667 |
| Passed tickets | 3 | 4 | +1 |
| Failed tickets | 3 | 2 | -1 |
| Valid predictions | 6 | 6 | +0 |
| Invalid predictions | 0 | 0 | +0 |

## Selection

v2 is selected because it improves category accuracy and exact-match rate without reducing priority/sentiment accuracy or structured-output validity. The v2 guidance is general: it defines category boundaries, priority levels, sentiment distinctions, and a multi-issue tie-break. It contains no ticket IDs, gold labels, sample answers, or scoring instructions.

This is a six-ticket prompt experiment, not a general benchmark. The improvement is evidence for this controlled sample only; broader evaluation would require a larger held-out set.
