"""Agent worker: pops run ids from the queue. Scale with: docker compose up --scale agent-worker=3"""
from prometheus_client import start_http_server

from ecs import obs
from ecs.config import cfg
from ecs.runner import execute
from ecs.store import store

if __name__ == "__main__":
    start_http_server(cfg.worker_metrics_port)
    lg = obs.get_logger("worker"); obs.log(lg, "worker_started")
    while True:
        rid = store().blpop("runs:queue", timeout=2)
        if rid: execute(rid)
