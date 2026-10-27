"""D6: measures submission -> final result (not just the POST). Run against the stub:
   LLM_PROVIDER=openai LLM_BASE_URL=http://llm-stub:8001/v1 LLM_MODEL=stub docker compose up --scale agent-worker=N
   locust -f loadtest/locustfile.py --host http://localhost:8000 --headless -u 20 -r 2 -t 2m --csv results/n1
Each user posts a UNIQUE description so the run cache does not flatter the numbers (measure caching separately, D7)."""
import itertools, time, uuid
from locust import HttpUser, between, task

SLO_P95_S = 15.0   # declared in SLO.md BEFORE measurement
_n = itertools.count()


class Analyst(HttpUser):
    wait_time = between(0.5, 1.5)

    def on_start(self): self.cid = "load-" + uuid.uuid4().hex[:8]

    @task
    def full_run(self):
        t0 = time.time()
        body = {"client_id": self.cid, "product_description": f"Stainless steel vacuum flask with a moulded plastic outer body, lot {next(_n)}-{uuid.uuid4().hex[:6]}",
                "destination_country": "US", "quantity": 10, "unit": "pcs", "declared_value_inr": 1000}
        with self.client.post("/v1/classify", json=body, name="POST /v1/classify", catch_response=True) as r:
            if r.status_code != 202: r.failure(f"{r.status_code}"); return
            url = r.json()["status_url"]
        while time.time() - t0 < 120:
            g = self.client.get(url, name="GET /v1/runs/{id}").json()
            if g["status"] in ("completed", "failed"):
                dt = (time.time() - t0) * 1000
                self.environment.events.request.fire(request_type="RUN", name="submission_to_result", response_time=dt, response_length=0,
                                                     exception=None if g["status"] == "completed" and dt / 1000 <= SLO_P95_S * 3 else Exception(g["status"]))
                return
            time.sleep(0.3)
        self.environment.events.request.fire(request_type="RUN", name="submission_to_result", response_time=120000, response_length=0, exception=Exception("timeout"))
