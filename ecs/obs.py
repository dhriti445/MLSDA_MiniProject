"""Structured JSON logging, correlation id, Prometheus metrics (D5)."""
import contextvars, json, logging, sys, time
from prometheus_client import Counter, Gauge, Histogram

correlation_id = contextvars.ContextVar("correlation_id", default="-")


class JsonFormatter(logging.Formatter):
    def format(self, r):
        d = {"ts": round(time.time(), 3), "level": r.levelname, "logger": r.name,
             "msg": r.getMessage(), "correlation_id": correlation_id.get()}
        d.update(getattr(r, "fields", {}))
        return json.dumps(d, default=str)


def get_logger(name):
    lg = logging.getLogger(name)
    if not lg.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(JsonFormatter())
        lg.addHandler(h)
        lg.setLevel(logging.INFO)
        lg.propagate = False
    return lg


def log(lg, msg, **fields):
    lg.info(msg, extra={"fields": fields})


RUNS = Counter("ecs_runs_total", "Completed runs", ["status", "route"])
RUN_LAT = Histogram("ecs_run_seconds", "Submission-to-result latency", buckets=(.1, .25, .5, 1, 2, 5, 10, 20, 30, 60))
STEP_LAT = Histogram("ecs_step_seconds", "Per-step latency", ["step"], buckets=(.001, .01, .05, .1, .5, 1, 5, 20))
TOOL_CALLS = Counter("ecs_tool_calls_total", "Tool calls", ["tool"])
STEPS_PER_RUN = Histogram("ecs_steps_per_run", "Steps per run", buckets=(2, 4, 6, 8, 10, 14, 20))
LLM_CALLS = Counter("ecs_llm_calls_total", "LLM calls", ["outcome"])
LLM_RETRIES = Counter("ecs_llm_retries_total", "LLM retries")
BREAKER_STATE = Gauge("ecs_breaker_open", "1 when the LLM circuit breaker is open")
TOKENS = Counter("ecs_tokens_total", "Tokens", ["kind", "step"])
COST = Counter("ecs_cost_usd_total", "Cost in USD", ["step"])
QUARANTINED = Counter("ecs_quarantined_total", "Rejected requests", ["reason"])
GUARDRAIL = Counter("ecs_guardrail_blocks_total", "Guardrail blocks", ["category"])
CACHE = Counter("ecs_cache_total", "Cache lookups", ["result"])
VERIFY_FAIL = Counter("ecs_verification_failures_total", "Verifier rejections")
INDEX_CHUNKS = Gauge("ecs_index_chunks", "Chunks in index")
INDEX_BUILT = Gauge("ecs_index_built_timestamp", "Index build time (unix)")
INGEST_RATE = Gauge("ecs_ingest_chunks_per_second", "Ingestion throughput")
HTTP_REQ = Counter("ecs_http_requests_total", "HTTP requests", ["path", "code"])
HTTP_LAT = Histogram("ecs_http_seconds", "HTTP latency", ["path"])
