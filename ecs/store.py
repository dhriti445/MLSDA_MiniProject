"""Run store / queue / cache / rate-limit. Redis in compose; in-memory fallback for tests and single-process dev."""
import json, threading, time
from ecs.config import cfg


class Mem:
    def __init__(self): self.d, self.q, self.l = {}, [], threading.Lock()
    def get(self, k):
        v = self.d.get(k)
        if v and (v[1] is None or v[1] > time.time()): return v[0]
    def set(self, k, v, ex=None): self.d[k] = (v, time.time() + ex if ex else None)
    def incr(self, k, ex):
        with self.l:
            n = (self.get(k) or 0) + 1
            cur = self.d.get(k); self.d[k] = (n, cur[1] if cur and cur[1] else time.time() + ex)
            return n
    def rpush(self, k, v): self.q.append(v)
    def blpop(self, k, timeout=1):
        end = time.time() + timeout
        while time.time() < end:
            if self.q: return self.q.pop(0)
            time.sleep(0.02)
    def lpush(self, k, v): self.d.setdefault(k, ([], None))[0].append(v)
    def lrange(self, k): return list((self.d.get(k) or ([], None))[0])


class Rds:
    def __init__(self, url):
        import redis; self.r = redis.Redis.from_url(url, decode_responses=True)
    def get(self, k):
        v = self.r.get(k); return json.loads(v) if v else None
    def set(self, k, v, ex=None): self.r.set(k, json.dumps(v), ex=ex)
    def incr(self, k, ex):
        n = self.r.incr(k)
        if n == 1: self.r.expire(k, ex)
        return n
    def rpush(self, k, v): self.r.rpush(k, v)
    def blpop(self, k, timeout=1):
        x = self.r.blpop(k, timeout=timeout); return x[1] if x else None
    def lpush(self, k, v): self.r.rpush(k, json.dumps(v))
    def lrange(self, k): return [json.loads(x) for x in self.r.lrange(k, 0, -1)]


_store = None
def store():
    global _store
    if _store is None: _store = Rds(cfg.redis_url) if cfg.redis_url else Mem()
    return _store
