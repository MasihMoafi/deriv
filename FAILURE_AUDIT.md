# Adversarial Failure Audit

## Method

A clean temporary baseline was generated with `python run.py --provider local` and independently confirmed with `python validate.py`. Every mutation was applied to a disposable copy; the repository artifacts were not intentionally used as the mutation target. The first harness run was discarded because it had a harness bug and an incomplete untracked baseline. The matrix was rerun from the verified temporary baseline.

## Matrix results

| Mutation | Initial result | Final result | Evidence |
|---|---|---|---|
| Remove ticket `channel` | rejected by `run.py` | rejected | input schema check |
| Change keyed labels object to array | rejected by `run.py` | rejected | label shape check |
| Replace a label key with an unknown ticket ID | rejected by `run.py` | rejected | key-set equality |
| Invalid prediction JSON | rejected | rejected | `INVALID_JSON` |
| Prediction source-ID mismatch | rejected | rejected | `SOURCE_TICKET_ID_MISMATCH` |
| Invalid prediction enum | rejected | rejected | `INVALID_ENUM_VALUE` |
| Unexpected prediction field | rejected | rejected | `UNEXPECTED_FIELD` |
| Missing prediction file | rejected | rejected | missing-file error and record mismatch |
| Duplicate log record | rejected | rejected | exactly-one-call check |
| Uppercase log stage | rejected | rejected | lowercase `classify` check |
| Invalid ISO timestamp | **accepted escape** | rejected | ISO-8601 parsing added |
| Tampered metrics | rejected | rejected | deterministic recomputation mismatch |
| Tampered validation wrapper | **accepted escape** | rejected | wrapper/record consistency added |
| Missing report | rejected | rejected | required artifact check |
| Empty report | rejected | rejected | empty-report check |
| Nonempty fake report | **accepted escape** | rejected | required report headings added |
| Extra prediction file | **accepted escape** | rejected | unexpected-file check added |

## Reverse-engineered conclusions

The initial core prediction validation was stronger than the surrounding artifact-integrity validation. Four escapes existed in the independent validator: it checked timestamp field presence rather than timestamp validity, trusted the validation wrapper, treated any nonempty report as sufficient, and ignored stale extra predictions. These were narrow robustness gaps and are now fixed.

The validator still cannot cryptographically prove that a call log was produced by an LLM rather than forged by a local process. It verifies the declared artifact contract and deterministic consistency. Provider execution evidence comes from the live run's provider/model fields and the actual network path, not from the log alone.

An extra arbitrary file outside the required artifact set is intentionally irrelevant; unexpected prediction JSON files are now rejected because they can create stale replay state.

## Current regression evidence

- Full unittest suite: 16 passed, including the exact authoritative sample E2E test, fixture-backed synthetic E2E test, scoring tests, validation tests, and JSON-fence repair tests.
- Direct validation functions: 6 passed.
- Root independent validation after final live run: `VALIDATION OK`.
- Live records: 6, provider `openrouter`, model `openai/gpt-5.6-luna`, fallback count 0.
