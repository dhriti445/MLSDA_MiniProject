# Export Classification Check Service (Mini Project 07)

Multi-agent service: product description -> validated -> proposed HS heading + GRI rule + citations -> route
(`clear-for-filing` | `seek-product-clarification` | `specialist-classification-review`). It never files anything; a licensed broker decides.

## Run it (from a clean clone)
```bash
cp .env.example .env            # LLM_PROVIDER=heuristic needs no key; see .env.example for a real provider
docker compose up --build       # api http://localhost:8000 (web client at /), prometheus :9090, grafana :3000
docker compose up --scale agent-worker=3
curl -s localhost:8000/v1/classify -H 'content-type: application/json' -d '{"client_id":"me","product_description":"Stainless steel vacuum flask with a moulded plastic outer body.","destination_country":"US","quantity":10,"unit":"pcs","declared_value_inr":5000}'
curl -s localhost:8000/v1/runs/<run_id>          # poll; /v1/runs/<id>/trace = full reconstruction
```
Without Docker (dev): `pip install -r requirements.txt; python -m ecs.ingest; INLINE_WORKER=1 uvicorn services.api.main:app`.
Tests: `PYTHONPATH=. pytest tests -q`. Eval: `PYTHONPATH=. python -m eval.run_eval --label x [--prompt v2] [--no-article-search]`.

## Design
**Agents (LangGraph, `ecs/agents.py`)**: *extractor* (article + materials; LLM with heuristic fallback) -> *classifier* (loop; each turn the planner picks
a tool: `search_corpus`, `get_clause`, `get_request_field`) -> *verifier* (every citation must resolve to retrieved text, quote must be a verbatim substring,
heading must be retrieved and in scope, rule cited) -> *router*. Verification failure -> one retry with a broader search strategy, then escalation.
Loop bounds: steps, tool calls, wall-clock (`MAX_*`, `RUN_TIMEOUT_S`). Agent crash mid-run -> converted to a `specialist-classification-review`
escalation (`agent_failure`); LLM failure -> `degraded` result that can never be `clear-for-filing`.
**The 4.1 case**: first search (whole description) is material-led; the classifier then derives a *new* query from the extracted article ("vacuum flask"),
finds heading 9617, searches for notes excluding Chapter 96 articles from Section XV (the modifier the request never mentions), cites GRI 1, H9617, the note and the policy row.
**Interfaces**: async via Redis queue (runs take tens of seconds; polling keeps HTTP short and lets workers scale independently).
**Deployment boundaries**: api (stateless, I/O) | agent-worker (LLM/CPU bound, scaled and crash-isolated) | redis (state) | indexer (batch job, own release cadence) | llm-stub | prometheus/grafana.
**Guardrails**: regex injection/toxicity screens on every free-text field (blocked + quarantined, no run starts), `<untrusted>` wrapping + system prompt, output filter against determinations.
**Caching/rate limit**: whole-run cache (verified results only) keyed on normalised request; per-client fixed-window limit.

## Evaluation (20 scenarios, `eval/eval_set.jsonl`, results in `eval/results/`)
| run | route acc. | heading acc. | groundedness | context relevance | faithfulness | hallucination |
|---|---|---|---|---|---|---|
| article-name search ON (final) | 1.00 | 1.00 | 1.00 | 0.25 | 0.87 | 0.00 |
| deliberate change: article search OFF (material-first baseline) | 0.50 | 0.27 | 1.00 | 0.34 | 1.00 | 0.00 |
Metric definitions are in `eval/run_eval.py`. **Caveats, read before quoting these:** (1) metrics are deterministic claim-level proxies, not TruLens LLM-judged;
(2) the classifier was fixed against failures this same set exposed (INCIDENTS.md), so 1.00 is optimistic - add held-out scenarios; (3) the seed corpus is tiny, so a single
pass is much easier than on the full chapters; (4) the OFF variant fails by *escalating*, not by confidently misclassifying (false_clear 0).
Prompt variants v1/v2 exist, but with `LLM_PROVIDER=heuristic` they are never used, so **no v1-vs-v2 comparison has been run** (L2 needs a real provider).

## Requirement status (be honest in the viva)
Done and tested locally: F1-F8, A1 (LangGraph, 3 tools, bounds), A2, A3, A4, A5 (timeout/backoff/breaker/degradation), A8, L1 (BM25, incremental re-index), L3 (set + runner + ablation), L4 (baseline), L5 (per-step tokens/cost recorded; pricing via env),
L6 (feedback endpoint + summary), D1, D2, D4, D5 (structured logs, correlation id, Prometheus, trace reconstruction by run id), D7 (cache + rate limit), D8 (runbook + incident log).
**Written but NOT run here (no Docker in my environment): docker-compose stack, `--scale` measurement (A7), Locust results (D6), cost per 100 runs against a real provider.**
**Not built:** OpenTelemetry/Jaeger tracing, Grafana dashboard JSON (datasource only), A6 dashboard panels (metrics exist: `ecs_*`), embedding/FAISS retrieval (BM25 used - add behind `Index.search`),
TruLens integration, automatic scoring of live runs over time (L6 second half), ML toxicity detector, the real CBIC/DGFT corpus.
Policy rows in the seed corpus are placeholders (`verified_against_official_schedule: false` in every response).
