# Service level objective (declared BEFORE any load measurement - commit this file first, keep the commit hash in the report)

**SLO: p95 of submission-to-result latency for a complete run <= 15 s at 10 concurrent users; error rate < 1 %.**

Justification against the problem context: today a trade-compliance analyst reads the description, finds the heading and policy by hand
(minutes per item). A 15 s p95 is already ~10x faster than that and is acceptable for a "propose, then a broker decides" workflow;
nothing downstream is blocked on sub-second answers. A run makes 2 model calls (extract, rationale) plus ~6 tool calls; with the stub at
~0.8 s per call and local retrieval in milliseconds, the expected p50 is ~2 s, so 15 s leaves headroom for queueing under load.

Status: NOT YET MEASURED. Run `loadtest/locustfile.py` (see its docstring) and record RPS/p50/p95 in the report, plus the concurrency where p95 > 15 s
and the responsible component (look at ecs_step_seconds and Redis/worker CPU before concluding).
