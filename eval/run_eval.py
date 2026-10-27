"""L3: batch evaluation.  python -m eval.run_eval --label baseline [--prompt v2] [--no-article-search]
Metrics (deterministic, claim-level; swap in TruLens feedback functions for an LLM-judged version):
 groundedness       = supported claims / total claims. Claims: proposed heading, each cited rule/note/policy. A claim is supported iff its
                      citation resolves to a retrieved passage AND the quote is a verbatim substring of it.
 context_relevance  = |retrieved ∩ expected supporting passages| / |retrieved|, averaged over scenarios that have supporting passages.
 faithfulness       = share of answered runs whose proposed heading id is present in retrieved text with matching chapter and whose rationale
                      mentions only the proposed heading code (no other 4-digit code).
 hallucination_rate = share of runs with >=1 unsupported claim (runs that escalate make no claims and count as 0).
Also: route accuracy, heading accuracy, false_clear_rate (cleared something that should not be)."""
import argparse, json, os, re, sys, time

p = argparse.ArgumentParser()
p.add_argument("--set", default="eval/eval_set.jsonl"); p.add_argument("--label", default="run"); p.add_argument("--prompt", default="v1")
p.add_argument("--no-article-search", action="store_true"); a = p.parse_args()
os.environ["PROMPT_VERSION"] = a.prompt
if a.no_article_search: os.environ["ENABLE_ARTICLE_SEARCH"] = "0"

from ecs import ingest
from ecs.agents import run_agent
from ecs.retrieval import Index
from ecs.config import cfg

if not os.path.exists(cfg.index_path): ingest.run()
ix = Index.load(cfg.index_path)
rows = [json.loads(l) for l in open(a.set)]
gs = []; rel = []; faith = []; halluc = []; route_ok = head_ok = false_clear = n_head = n_clear_expected = 0; out = []
for r in rows:
    x = run_agent(r["id"], {"product_description": r["description"]}, ix)
    pr = x["proposal"]; claims = unsupported = 0
    if pr:
        cites = [("heading", pr["basis"][0])] + [("rule", b) for b in pr["basis"][1:]] + [("note", e["citation"]) for e in pr["excluded_alternatives"]] + \
                ([("policy", pr["export_policy"]["citation"])] if pr["export_policy"] else [])
        for _, c in cites:
            claims += 1
            t = x["retrieved_passages"].get(c["chunk_id"])
            if t is None or c["quote"] not in t: unsupported += 1
        gs.append((claims - unsupported) / claims)
        h = x["retrieved_passages"].get("H" + pr["heading"])
        codes = set(re.findall(r"\b\d{4}\b", x["rationale"] or ""))
        faith.append(1.0 if h and codes <= {pr["heading"]} else 0.0)
    halluc.append(1.0 if unsupported else 0.0)
    if r["supporting_chunks"]:
        got = set(x["retrieved_passages"]); rel.append(len(got & set(r["supporting_chunks"])) / len(got))
    ok_r = x["route"] == r["expected_route"]; route_ok += ok_r
    if r["expected_heading"]:
        n_head += 1; head_ok += bool(pr and pr["heading"] == r["expected_heading"] and ok_r)
    if x["route"] == "clear-for-filing" and r["expected_route"] != "clear-for-filing": false_clear += 1
    out.append({"id": r["id"], "route": x["route"], "expected_route": r["expected_route"], "heading": pr and pr["heading"],
                "expected_heading": r["expected_heading"], "steps": x["steps"], "tool_calls": x["tool_calls"], "ok": ok_r})
m = lambda v: round(sum(v) / len(v), 3) if v else None
res = {"label": a.label, "prompt_version": a.prompt, "article_search": not a.no_article_search, "n": len(rows),
       "route_accuracy": round(route_ok / len(rows), 3), "heading_accuracy": round(head_ok / n_head, 3), "false_clear": false_clear,
       "groundedness": m(gs), "context_relevance": m(rel), "faithfulness": m(faith), "hallucination_rate": m(halluc),
       "mean_steps": m([o["steps"] for o in out]), "failures": [o for o in out if not o["ok"]], "ts": time.time()}
os.makedirs("eval/results", exist_ok=True); json.dump({**res, "scenarios": out}, open(f"eval/results/{a.label}.json", "w"), indent=1)
print(json.dumps(res, indent=1))
