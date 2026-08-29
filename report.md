# Evaluation report

## Summary
- Tickets evaluated: 6
- Tickets passed: 3
- Tickets failed: 3
- Valid predictions: 6
- Invalid or missing predictions: 0
- Results represent provider output from openrouter (openai/gpt-oss-120b); this report does not treat fallback behavior as LLM quality evidence.

## Metrics
| Metric | Rate |
| --- | ---: |
| Category accuracy | 0.8333 |
| Priority accuracy | 0.8333 |
| Sentiment accuracy | 0.8333 |
| Exact-match rate | 0.5000 |

## Validation status
- Validation records supplied: yes
- Invalid and missing predictions are counted as failed, never as correct.

## Deterministic error analysis
- `ticket-002`: priority_mismatch
- `ticket-003`: sentiment_mismatch
- `ticket-006`: category_mismatch

## Improvement suggestions
1. Add category-boundary examples to the classification prompt and regression set, especially for tickets that could fit more than one category.
2. Make priority criteria explicit with observable urgency and impact thresholds, and test low/medium/high boundary cases.
3. Expand sentiment examples to distinguish neutral requests, frustrated complaints, and urgent language before deployment.
