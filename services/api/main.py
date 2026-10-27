import hashlib, json, os, time, uuid

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from ecs import contract, guardrails, obs
from ecs.config import cfg
from ecs.runner import execute
from ecs.store import store

app = FastAPI(title="Export Classification Check Service", version="1.0")
lg = obs.get_logger("api")
WEB = os.path.join(os.path.dirname(__file__), "..", "..", "web", "index.html")


@app.middleware("http")
async def mw(request: Request, call_next):
    cid = request.headers.get("x-correlation-id") or uuid.uuid4().hex[:16]
    obs.correlation_id.set(cid); t = time.time()
    resp = await call_next(request)
    p = request.url.path if not request.url.path.startswith("/v1/runs/") else "/v1/runs/{id}"
    obs.HTTP_REQ.labels(p, str(resp.status_code)).inc(); obs.HTTP_LAT.labels(p).observe(time.time() - t)
    resp.headers["x-correlation-id"] = cid
    return resp


@app.get("/")
def web(): return FileResponse(WEB)


@app.get("/health")
def health():
    ok_index = os.path.exists(cfg.index_path)
    try: store().get("ping"); ok_store = True
    except Exception: ok_store = False
    return JSONResponse({"status": "ok" if ok_index and ok_store else "degraded", "index": ok_index, "store": ok_store},
                        status_code=200 if ok_index and ok_store else 503)


@app.get("/metrics")
def metrics(): return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/v1/contract")
def get_contract(): return contract.contract_schema()


@app.post("/v1/classify", status_code=202)
async def classify(request: Request, bg: BackgroundTasks):
    try: payload = await request.json()
    except Exception:
        qid = contract.quarantine(None, [{"field": "body", "error": "not valid JSON"}], "malformed_json")
        return JSONResponse({"error": "invalid_request", "quarantine_id": qid, "details": [{"field": "body", "error": "not valid JSON"}]}, 422)
    req, errs = contract.validate(payload)
    if errs:                                                       # D1: nothing downstream sees this; no run is created
        qid = contract.quarantine(payload, errs)
        return JSONResponse({"error": "invalid_request", "quarantine_id": qid, "details": errs, "run_started": False}, 422)
    cat = guardrails.scan_request(req)
    if cat:                                                        # L4
        obs.GUARDRAIL.labels(cat).inc(); qid = contract.quarantine(payload, [{"field": "product_description", "error": cat}], f"guardrail_{cat}")
        return JSONResponse({"error": "blocked_by_guardrail", "category": cat, "quarantine_id": qid, "run_started": False}, 400)
    s = store()
    n = s.incr(f"rl:{req['client_id']}:{int(time.time() // 60)}", 70)   # D7 rate limit per client
    if n > cfg.rate_limit_per_min:
        return JSONResponse({"error": "rate_limited", "limit_per_min": cfg.rate_limit_per_min}, 429, headers={"Retry-After": "30"})
    key = hashlib.sha256(json.dumps([req["product_description"].lower(), sorted(m.lower() for m in req.get("materials") or [])]).encode()).hexdigest()
    run_id = uuid.uuid4().hex[:16]; now = time.time()
    run = {"run_id": run_id, "correlation_id": obs.correlation_id.get(), "request": req, "submitted_at": now, "cache_key": key,
           "prompt_version": cfg.prompt_version, "status": "queued"}
    cached = s.get(f"cache:{key}")
    if cached:                                                     # whole-run cache (only verified results are cached)
        obs.CACHE.labels("hit").inc()
        run.update(status="completed", result={**cached, "run_id": run_id, "cache_hit": True}, finished_at=now)
        s.set(f"run:{run_id}", run, 86400)
    else:
        obs.CACHE.labels("miss").inc(); s.set(f"run:{run_id}", run, 86400)
        if cfg.inline_worker: bg.add_task(execute, run_id)
        else: s.rpush("runs:queue", run_id)                        # A4: queue between submission and execution
    return {"run_id": run_id, "status": run["status"], "status_url": f"/v1/runs/{run_id}"}


@app.get("/v1/runs/{run_id}")
def get_run(run_id: str):
    r = store().get(f"run:{run_id}")
    if not r: return JSONResponse({"error": "not_found"}, 404)
    out = {k: r.get(k) for k in ("run_id", "status", "submitted_at", "finished_at", "error")}
    if r.get("result"): out["result"] = {k: v for k, v in r["result"].items() if k not in ("trace", "retrieved_passages")}; out["result"]["passages"] = r["result"].get("retrieved_passages")
    return out


@app.get("/v1/runs/{run_id}/trace")
def get_trace(run_id: str):
    r = store().get(f"run:{run_id}")
    if not r or not r.get("result"): return JSONResponse({"error": "not_found_or_not_finished"}, 404)
    return {"run_id": run_id, "correlation_id": r["correlation_id"], "request": r["request"], "trace": r["result"]["trace"],
            "cost": r["result"]["cost"], "verification": r["result"]["verification"], "prompt_version": r["result"]["prompt_version"]}


@app.post("/v1/feedback")
async def feedback(request: Request):
    b = await request.json()
    if not isinstance(b, dict) or not store().get(f"run:{b.get('run_id')}") or not isinstance(b.get("satisfactory"), bool) or not str(b.get("reason", "")).strip():
        return JSONResponse({"error": "need run_id (existing), satisfactory (bool), reason (non-empty)"}, 422)
    if guardrails.scan_text(b["reason"]): return JSONResponse({"error": "blocked_by_guardrail"}, 400)
    store().lpush("feedback", {"run_id": b["run_id"], "satisfactory": b["satisfactory"], "reason": b["reason"][:500], "ts": time.time()})
    return {"stored": True}


@app.get("/v1/feedback/summary")
def fb_summary():
    f = store().lrange("feedback"); n = len(f); good = sum(1 for x in f if x["satisfactory"])
    return {"count": n, "satisfactory_rate": round(good / n, 3) if n else None, "recent_reasons": [x["reason"] for x in f[-5:]]}
