"""Executes one run: used by the worker container and by INLINE_WORKER mode. Persists the full trace (D5)."""
import time

from ecs import obs
from ecs.agents import run_agent
from ecs.config import cfg
from ecs.retrieval import Index
from ecs.store import store

lg = obs.get_logger("runner")
_index = None


def index():
    global _index
    if _index is None: _index = Index.load(cfg.index_path)
    return _index


def execute(run_id):
    s = store(); run = s.get(f"run:{run_id}")
    if not run: return
    obs.correlation_id.set(run["correlation_id"])
    run["status"] = "running"; run["started_at"] = time.time(); s.set(f"run:{run_id}", run, 86400)
    try:
        res = run_agent(run_id, run["request"], index(), t0=run["started_at"])
        run.update(status="completed", result=res)
    except Exception as e:                       # should not happen: run_agent converts failures into escalations
        run.update(status="failed", error=f"{type(e).__name__}: {e}")
    run["finished_at"] = time.time()
    dt = run["finished_at"] - run["submitted_at"]            # submission -> result (D6)
    obs.RUN_LAT.observe(dt); obs.RUNS.labels(run["status"], (run.get("result") or {}).get("route", "none")).inc()
    if run.get("result"):
        obs.STEPS_PER_RUN.observe(run["result"]["steps"])
        if run["result"]["reason_code"] == "verified":
            s.set(f"cache:{run['cache_key']}", run["result"], cfg.cache_ttl_s)
    s.set(f"run:{run_id}", run, 86400)
    obs.log(lg, "run_finished", run_id=run_id, status=run["status"], seconds=round(dt, 3),
            route=(run.get("result") or {}).get("route"))
