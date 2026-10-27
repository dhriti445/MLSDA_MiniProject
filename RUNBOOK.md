# Runbook - two most likely failure modes

## 1. LLM provider unavailable / rate-limited (breaker open)
**Symptom:** results arrive with `degraded: true`, route `specialist-classification-review`; Grafana `ecs_breaker_open = 1`; `ecs_llm_calls_total{outcome="error"}` rising.
**Confirm:** `docker compose logs agent-worker | grep -i llm`; `curl localhost:9090/api/v1/query?query=ecs_breaker_open`. Check the provider's status page / quota.
**Recover:** nothing is lost - runs complete in degraded mode (heuristic extraction, never clear-for-filing). Fix the key/quota/endpoint in `.env`, `docker compose up -d agent-worker`. The breaker half-opens after `BREAKER_COOLDOWN_S` and closes on the first success. Re-submit affected runs (degraded results are not cached).

## 2. Stale / missing index (answers cite old text, or /health = 503 "index": false)
**Symptom:** `/health` returns 503, or `ecs_index_built_timestamp` is older than the last corpus change, or the 4.1 case fails after a corpus edit.
**Confirm:** `docker compose exec api python -c "import json;d=json.load(open('/data/index.json'));print(d['built_at'],d['n_chunks'],list(d['versions']))"`; compare file hashes with `corpus/`.
**Recover:** `docker compose run --rm indexer` (idempotent, only re-parses changed files; `python -m ecs.ingest --full` forces a rebuild), then `docker compose restart api agent-worker`. Run `python -m eval.run_eval --label after_reindex` and compare with the last results in `eval/results/`.
