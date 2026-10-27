# Incident log (development)
Entries record real failures hit while building. Add your own as you hit them; keep date, symptom, cause, fix, prevention.

## 2026-10-09 - Agent escalated a valid case after a verifier retry (limits_exceeded)
Symptom: with fault injection on, `test_verifier_catches_fabricated_citation` returned no proposal. Cause: default `MAX_STEPS=14` was less than two passes (~10 steps each), so the retry was cut off and the run correctly escalated. Fix: bounds raised to 26 steps / 22 tool calls. Prevention: test asserts retry path completes; bounds documented in `.env.example`.

## 2026-10-09 - Eval found three misclassifications after the first agent version
Symptoms (eval set E13, E19, E20): "coil spring" tied between 7320 and 7318; "some product made of plastic" not flagged for clarification; "hand tool set of steel spanners" cleared as 9605 (travel *sets*) - a false clear. Causes: head-noun match counted a parenthetical example ("spring washers") as naming the article; determiners not stripped; "set of X" parsed as the article; material-only fallback allowed a clear without any article-token match. Fix: primary-wording match preferred over parentheticals; determiner/container handling; fallback now escalates when only material matches. Prevention: the three cases are in `eval/eval_set.jsonl`.

## 2026-10-09 - Circuit breaker did not open in test
Symptom: breaker stayed closed after a failed call. Cause: 1 retry = 2 failures < threshold 3 (config, not a bug). Fix: test sets `BREAKER_THRESHOLD=2` and asserts the second run fails fast.
