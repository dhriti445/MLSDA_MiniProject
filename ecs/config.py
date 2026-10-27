"""All environment-specific configuration is read at call time (D4). No defaults for secrets/models."""
import os


def _i(k, d): return int(os.environ.get(k, d))
def _f(k, d): return float(os.environ.get(k, d))


class Cfg:
    @property
    def corpus_dir(self): return os.environ.get("CORPUS_DIR", "corpus")
    @property
    def index_path(self): return os.environ.get("INDEX_PATH", "data/index.json")
    @property
    def quarantine_path(self): return os.environ.get("QUARANTINE_PATH", "data/quarantine.jsonl")
    @property
    def redis_url(self): return os.environ.get("REDIS_URL", "")
    @property
    def inline_worker(self): return os.environ.get("INLINE_WORKER", "0") == "1"
    # LLM provider: heuristic (no calls) | openai (any OpenAI-compatible endpoint, incl. the stub)
    @property
    def llm_provider(self): return os.environ.get("LLM_PROVIDER", "heuristic")
    @property
    def llm_base_url(self): return os.environ.get("LLM_BASE_URL", "")
    @property
    def llm_model(self): return os.environ.get("LLM_MODEL", "")
    @property
    def llm_api_key(self): return os.environ.get("LLM_API_KEY", "")
    @property
    def llm_timeout_s(self): return _f("LLM_TIMEOUT_S", 20)
    @property
    def llm_max_retries(self): return _i("LLM_MAX_RETRIES", 3)
    @property
    def breaker_threshold(self): return _i("BREAKER_THRESHOLD", 3)
    @property
    def breaker_cooldown_s(self): return _f("BREAKER_COOLDOWN_S", 30)
    @property
    def price_in_per_1k(self): return _f("PRICE_IN_PER_1K", 0)
    @property
    def price_out_per_1k(self): return _f("PRICE_OUT_PER_1K", 0)
    # agent loop bounds (A1)
    @property
    def max_steps(self): return _i("MAX_STEPS", 26)
    @property
    def max_tool_calls(self): return _i("MAX_TOOL_CALLS", 22)
    @property
    def run_timeout_s(self): return _f("RUN_TIMEOUT_S", 60)
    @property
    def max_verify_retries(self): return _i("MAX_VERIFY_RETRIES", 1)
    @property
    def prompt_version(self): return os.environ.get("PROMPT_VERSION", "v1")
    @property
    def enable_article_search(self): return os.environ.get("ENABLE_ARTICLE_SEARCH", "1") == "1"
    @property
    def inject_fault(self): return os.environ.get("INJECT_FAULT", "")
    # API
    @property
    def rate_limit_per_min(self): return _i("RATE_LIMIT_PER_MIN", 30)
    @property
    def cache_ttl_s(self): return _i("CACHE_TTL_S", 3600)
    @property
    def worker_metrics_port(self): return _i("WORKER_METRICS_PORT", 9100)


cfg = Cfg()
