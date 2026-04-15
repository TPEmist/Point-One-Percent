# RT-1 Red Team Harness (Python parity)

Mirror of `pop-pay-npm/tests/redteam/`. Same corpus, same metrics shape, thin Python runners.

## Corpus source

The canonical corpus lives in the TypeScript repo: `pop-pay-npm/tests/redteam/corpus/attacks.json`.

The Python harness expects a local copy at `tests/redteam/corpus/attacks.json`. Keep it in sync via:

```bash
python tests/redteam/sync_corpus.py --from ../pop-pay-npm/tests/redteam/corpus/attacks.json
```

Corpus hash is recorded at the top of each JSONL artifact; a parity-regression alert fires if hashes differ between the two repos on the same run.

## Running

```bash
# Full corpus, Layer 1 only (no LLM)
POP_REDTEAM=1 pytest tests/redteam -v

# Full corpus + all 5 paths
export POP_LLM_API_KEY=sk-...
export POP_LLM_MODEL=gpt-4o-mini-2024-07-18
POP_REDTEAM=1 python -m tests.redteam.run_corpus --n 5 --concurrency 20

# B-class only (S1.1 input)
POP_REDTEAM=1 python -m tests.redteam.run_corpus --filter B
```

**Does NOT read `~/.config/pop-pay/.env`.** Same rule as TS.

## Parity contract

- Same corpus hash
- Same aggregator output shape (see `aggregator.py`)
- Same B-class decision thresholds (per `docs/CATEGORIES_DECISION_CRITERIA.md`)
- Bypass rate drift >5pp between TS and Python on the same corpus = parity regression → head-of-eng

## Engine TODO — retry-exhaustion must surface as `error`, not silent `block`

`pop_pay/engine/llm_guardrails.py` falls through to `return False, f"LLM Guardrail API Error: ..."` on tenacity `RetryError`. The aggregator scores `approved=False` as a `block` verdict, so quota exhaustion or sustained 5xx storms look identical to a model that has learned to over-reject.

This footgun cost us the Step 2 v3 benchmark on 2026-04-15 (TS run, but the Python fallback path is structurally identical): 2923/2925 gemini layer2 rows were retry-exhausted (Gemini free-tier quota burn), result scored as 99.8% FR, and we briefly declared the model architecturally unfit. A re-run with fresh quota gave bypass 29.5% / FR 8.6% — the model was fine; the engine was lying. Full retraction in `docs/benchmark-history/prompt-iterations.md`.

Fix surface (bundle with a future hardening release; not blocking the v1 benchmark):

- Engine: distinguish "model said block" from "infrastructure failed" — raise a typed exception or return a third-state sentinel.
- Runner: tag `verdict: "error"` for infra failure; aggregator excludes errors when computing bypass/FR; `error_rate` becomes a first-class reported metric.
- Benchmark gate: refuse to publish numbers when any LLM-backed runner has non-zero `error_rate`.
