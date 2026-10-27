"""LLM client behind our own interface (provider changed by config). A5: timeout, bounded exponential backoff,
circuit breaker, graceful degradation (callers catch LLMUnavailable and fall back)."""
import json, time, threading
import httpx

from ecs.config import cfg
from ecs.obs import BREAKER_STATE, COST, LLM_CALLS, LLM_RETRIES, TOKENS


class LLMUnavailable(Exception):
    pass


class CircuitBreaker:
    def __init__(self):
        self.fails = 0; self.opened_at = None; self.lock = threading.Lock()

    def allow(self):
        with self.lock:
            if self.opened_at is None: return True
            if time.time() - self.opened_at >= cfg.breaker_cooldown_s:
                return True                                   # half-open: allow one probe
            return False

    def ok(self):
        with self.lock: self.fails = 0; self.opened_at = None; BREAKER_STATE.set(0)

    def fail(self):
        with self.lock:
            self.fails += 1
            if self.fails >= cfg.breaker_threshold:
                self.opened_at = time.time(); BREAKER_STATE.set(1)

    @property
    def is_open(self): return self.opened_at is not None and not self.allow()


breaker = CircuitBreaker()


def enabled(): return cfg.llm_provider != "heuristic"


def complete(system, user, step):
    """Returns (text, usage dict). Raises LLMUnavailable when breaker is open or retries are exhausted."""
    if not enabled(): raise LLMUnavailable("provider=heuristic")
    if not breaker.allow():
        LLM_CALLS.labels("breaker_open").inc(); raise LLMUnavailable("circuit_open")
    last = None
    for attempt in range(cfg.llm_max_retries + 1):
        try:
            r = httpx.post(cfg.llm_base_url.rstrip("/") + "/chat/completions", timeout=cfg.llm_timeout_s,
                           headers={"Authorization": f"Bearer {cfg.llm_api_key}"},
                           json={"model": cfg.llm_model, "messages": [{"role": "system", "content": system},
                                                                      {"role": "user", "content": user}], "temperature": 0})
            r.raise_for_status(); d = r.json()
            u = d.get("usage", {}); pi, po = u.get("prompt_tokens", 0), u.get("completion_tokens", 0)
            cost = pi / 1000 * cfg.price_in_per_1k + po / 1000 * cfg.price_out_per_1k
            TOKENS.labels("prompt", step).inc(pi); TOKENS.labels("completion", step).inc(po); COST.labels(step).inc(cost)
            breaker.ok(); LLM_CALLS.labels("ok").inc()
            return d["choices"][0]["message"]["content"], {"prompt_tokens": pi, "completion_tokens": po, "cost_usd": cost}
        except Exception as e:                                # timeout, 5xx, 429, bad payload
            last = e; breaker.fail(); LLM_CALLS.labels("error").inc()
            if attempt < cfg.llm_max_retries and breaker.allow():
                LLM_RETRIES.inc(); time.sleep(min(0.2 * 2 ** attempt, 5))   # 0.2, 0.4, 0.8 ... capped
            else:
                break
    raise LLMUnavailable(f"{type(last).__name__}: {last}")
