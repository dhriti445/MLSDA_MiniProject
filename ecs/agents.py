"""Multi-agent reasoning layer on LangGraph.
Topology:  extractor -> classifier (tool loop) -> verifier -> router      (verifier may send classifier back once)
Agents have separate responsibilities and a hand-off through a typed context; see README for failure behaviour."""
import json, re, time
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from ecs import guardrails, llm
from ecs.config import cfg
from ecs.obs import STEP_LAT, TOOL_CALLS, VERIFY_FAIL
from ecs.retrieval import stem, title_of, tokens
from ecs.tools import Toolbox

MATERIALS = {"stainless steel": "steel", "steel": "steel", "cast iron": "iron", "iron": "iron", "plastic": "plastics",
             "plastics": "plastics", "brass": "copper", "copper": "copper", "aluminium": "aluminium", "aluminum": "aluminium",
             "glass": "glass", "wood": "wood", "ceramic": "ceramic", "cotton": "cotton", "rubber": "rubber"}
ADJ = set("moulded molded cast forged stamped small large new used heavy light portable insulated double walled wall".split())
GENERIC = {"thing", "item", "product", "article", "goods", "part", "object", "equipment", "material", "stuff", "component", ""}
CONTAINER_WORDS = {"set", "pair", "box", "pack", "lot", "kit"}


def load_prompts(version):
    return json.load(open(f"prompts/{version}.json"))


def heuristic_entities(desc):
    d = desc.lower()
    head = re.split(r"\b(?:with|having|containing|made of|made from|in|for)\b|[,;(]", d, maxsplit=1)[0]
    hw = re.findall(r"[a-z]+", head.split(" of ")[0])
    if hw and hw[-1] in CONTAINER_WORDS and " of " in d:   # "hand tool set of steel spanners" -> the goods are the spanners
        head = d.split(" of ", 1)[1]
        head = re.split(r"\b(?:with|having|containing|made of|in|for)\b|[,;(]", head, maxsplit=1)[0]
    head = re.split(r"\bof\b", head, maxsplit=1)[0]
    mats = []
    for k in sorted(MATERIALS, key=len, reverse=True):
        if re.search(rf"\b{k}\b", d) and MATERIALS[k] not in mats: mats.append(MATERIALS[k])
        head = re.sub(rf"\b{k}\b", " ", head)
    head = re.sub(r"\b\d+(\.\d+)?\s*(mm|cm|kg|g|l|ml|litres?)?\b", " ", head)
    art = " ".join(w for w in re.findall(r"[a-z]+", head) if w not in ADJ and w not in ("a", "an", "the", "of", "some", "any", "various", "assorted", "certain"))
    return {"article": art, "materials": mats}


class Ctx:
    def __init__(self, run_id, req, index, t0=None):
        self.run_id, self.req, self.index, self.tb = run_id, req, index, Toolbox(index, req)
        self.t0 = t0 or time.time()
        self.prompts = load_prompts(cfg.prompt_version)
        self.retrieved, self.trace = {}, []
        self.steps = self.tool_calls = self.retries = 0
        self.entities = None; self.phase = "start"; self.strategy = "normal"
        self.first_hits, self.named, self.notes, self.gri, self.policy = [], {}, {}, [], None
        self.decision = self.proposal = self.verification = None
        self.escalation = None; self.degraded = False; self.result = None
        self.cost = {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0}

    def over(self):
        return (self.steps >= cfg.max_steps or self.tool_calls >= cfg.max_tool_calls or time.time() - self.t0 > cfg.run_timeout_s)

    def rec(self, agent, step, t, **kw):
        dt = time.time() - t; STEP_LAT.labels(step).observe(dt); self.steps += 1
        self.trace.append({"ts": round(time.time(), 3), "agent": agent, "step": step, "latency_ms": round(dt * 1000, 2),
                           "prompt_version": cfg.prompt_version, **kw})

    def tool(self, name, **kw):
        t = time.time(); self.tool_calls += 1; TOOL_CALLS.labels(name).inc()
        res = getattr(self.tb, name)(**kw)
        for r in res: self.retrieved[r["id"]] = r
        self.rec("classifier", f"tool:{name}", t, tool=name, args=kw, passages=[r["id"] for r in res],
                 scores={r["id"]: r["score"] for r in res})
        return res

    def add_cost(self, step, u):
        for k in self.cost: self.cost[k] += u.get(k, 0)
        self.trace[-1]["usage"] = u


class S(TypedDict):
    ctx: Any


# ------------------------------------------------------------------ Agent 1: extractor
def extractor(s: S):
    c = s["ctx"]; t = time.time(); ent = None; usage = {}
    if llm.enabled():
        try:
            txt, usage = llm.complete(c.prompts["extract_system"], guardrails.wrap_untrusted(c.req["product_description"]), "extract")
            j = json.loads(re.search(r"\{.*\}", txt, re.S).group(0))
            if isinstance(j.get("article"), str) and isinstance(j.get("materials"), list):
                ent = {"article": j["article"].lower().strip(), "materials": [MATERIALS.get(m.lower(), m.lower()) for m in j["materials"]]}
            else: raise ValueError("bad shape")
        except Exception:
            c.degraded = True                                   # provider failed -> deterministic fallback
    if ent is None: ent = heuristic_entities(c.req["product_description"])
    for m in c.req.get("materials") or []:                      # caller-declared materials supplement
        m = MATERIALS.get(m.lower(), m.lower())
        if m not in ent["materials"]: ent["materials"].append(m)
    c.entities = ent
    c.rec("extractor", "extract_entities", t, entities=ent, degraded=c.degraded)
    if usage: c.add_cost("extract", usage)
    return s


# ------------------------------------------------------------------ Agent 2: classifier (one tool action per loop turn)
def names_article(chunk, ent):
    """2 = head noun in the heading's primary wording; 1 = only in a parenthetical example; 0 = not named."""
    toks = tokens(ent["article"])
    if not toks: return 0
    t = title_of(chunk)
    if toks[-1] in tokens(re.sub(r"\([^)]*\)", " ", t)): return 2
    return 1 if toks[-1] in tokens(t) else 0



def classifier(s: S):
    c = s["ctx"]; e = c.entities; ph = c.phase
    if c.over():
        c.escalation = ("limits_exceeded", "loop bounds hit before a verified answer")
        c.phase = "propose"
        return s

    if ph == "start":
        q = c.req["product_description"] if cfg.enable_article_search else " ".join(e["materials"]) or c.req["product_description"]
        c.first_hits = c.tool("search_corpus", query=q, types=["heading"], k=5)
        c.phase = "article" if cfg.enable_article_search else "notes"

    elif ph == "article":
        # Search for headings that name the article.
        qs = [e["article"]] if c.strategy == "normal" else [w for w in tokens(e["article"])] + [e["article"] + " " + " ".join(e["materials"])]

        for q in [q for q in qs if q.strip()]:
            for h in c.tool("search_corpus", query=q, types=["heading"], k=5):
                heading_id = h.get("id", "")
                heading_text = h.get("text", "")

                # Skip a chunk if it contains a different embedded tariff heading.
                embedded_heading = re.findall(
                    r"(?m)^\s*\*?\s*(\d{4})\s+[A-Z]",
                    heading_text
                )
                if any(code != heading_id[1:] for code in embedded_heading):
                    continue

                lvl = names_article(h, e)
                if lvl:
                    c.named[h["id"]] = {**h, "lvl": lvl}

        if c.named and max(h["lvl"] for h in c.named.values()) == 2:
            c.named = {k: v for k, v in c.named.items() if v["lvl"] == 2}

        c.phase = "notes"

    elif ph == "notes":
        chs = {h["chapter"] for h in c.named.values()} | {h["chapter"] for h in c.first_hits[:3]}
        for ch in sorted(chs):
            for n in c.tool("search_corpus", query=f"does not cover articles of Chapter {ch} excluded", types=["note"], k=3):
                if f"Chapter {ch}" in n["text"] and re.search(r"not cover|exclud", n["text"]):
                    c.notes[n["id"]] = (ch, n)
        c.gri += c.tool("get_clause", clause_id="GRI_1")
        c.phase = "decide"

    elif ph == "decide":
        decide(c)
        if c.decision["kind"] == "gri3":
            c.gri += c.tool("get_clause", clause_id="GRI_3a")
        elif c.decision["kind"] in ("named", "material"):
            c.policy = c.tool("get_clause", clause_id=f"POL_{c.decision['heading']}")
        c.phase = "propose"

    return s


def decide(c):
    t = time.time(); e = c.entities; names = list(c.named.values())
    art = tokens(e["article"])
    if not art or e["article"] in GENERIC or (len(art) == 1 and art[0] in GENERIC):
        d = {"kind": "clarify", "reason": "article not identifiable from the description", "questions": ["What is the article (its name or function)?"]}
    elif len(names) == 1:
        d = {"kind": "named", "heading": names[0]["id"][1:], "rule": "GRI 1"}
    elif len(names) > 1:
        cov = sorted(((sum(1 for a in art if a in tokens(title_of(h))) / len(art), h["id"]) for h in names), reverse=True)
        if cov[0][0] > cov[1][0]: d = {"kind": "named", "heading": cov[0][1][1:], "rule": "GRI 3(a)"}
        else: d = {"kind": "tie", "reason": "two headings equally supported after GRI 3: " + ", ".join(x[1][1:] for x in cov[:2])}
        if d["kind"] == "named": d["kind"] = "gri3"; d["heading"] = cov[0][1][1:]
    else:
        q = set(art) | {stem(m) for m in e["materials"]}
        scored = sorted(((sum(1 for x in q if x in tokens(h["text"])) / max(len(q), 1), h["id"]) for h in c.first_hits), reverse=True)
        top = c.retrieved.get("H" + scored[0][1][1:]) if scored else None
        if scored and not (set(art) & set(tokens(top["text"]))):
            d = {"kind": "out_of_scope", "reason": "no indexed heading names the article; only its material matches, so it may belong to a chapter outside 73/96"}
        elif not scored or scored[0][0] < 0.34:
            d = {"kind": "out_of_scope", "reason": "no heading in the indexed chapters (73, 96) matches the article"}
        elif scored[0][0] < 0.5:
            d = {"kind": "clarify", "reason": "only a weak match to any heading", "questions": ["Please give a more specific description of the article and its use."]}
        elif len(scored) > 1 and abs(scored[0][0] - scored[1][0]) < 1e-9 and scored[0][1] != scored[1][1]:
            d = {"kind": "tie", "reason": f"headings {scored[0][1][1:]} and {scored[1][1][1:]} are equally supported"}
        else:
            d = {"kind": "material", "heading": scored[0][1][1:], "rule": "GRI 1", "coverage": scored[0][0]}
    c.decision = d
    c.rec("classifier", "decide", t, decision=d)


def quote(chunk, hint):
    """Verbatim sentence from the retrieved passage that best overlaps the hint (so citations resolve to retrieved text)."""
    ht = set(tokens(hint)); best = (-1, chunk["text"][:200])
    for m in re.finditer(r"[^.\n]+[.\n]?", chunk["text"]):
        seg = m.group().strip()
        if seg:
            sc = len(ht & set(tokens(seg)))
            if sc > best[0]: best = (sc, seg[:240])
    return best[1]


def cite(c, cid, hint):
    return {"chunk_id": cid, "quote": quote(c.retrieved[cid], hint)}


def propose(s: S):
    c = s["ctx"]; t = time.time(); d = c.decision
    if c.escalation or d is None: c.proposal = None; c.rec("classifier", "propose", t, note="no proposal"); return s
    if d["kind"] in ("tie", "out_of_scope", "clarify"): c.proposal = None; c.rec("classifier", "propose", t, note=d["kind"]); return s
    hid = "H" + d["heading"]; ch = c.retrieved[hid]["chapter"]
    cites = [cite(c, hid, c.entities["article"])]
    rule_id = "GRI_3a" if d["rule"] == "GRI 3(a)" else "GRI_1"
    cites.append(cite(c, rule_id, "classification determined according to the terms of the headings"))
    excl = []
    for other in c.first_hits:
        if other["id"] != hid and other["chapter"] != ch:
            for nid, (nch, n) in c.notes.items():
                if nch == ch:    # a note that excludes *this* chapter's articles from the other (material) heading's section
                    excl.append({"heading": other["id"][1:], "reason": f"excluded by note: articles of Chapter {ch} are not covered by the section containing heading {other['id'][1:]}",
                                 "citation": cite(c, nid, f"articles of Chapter {ch}")}); break
            break
    pol = None
    if c.policy:
        pol = {"text": c.policy[0]["text"], "citation": cite(c, c.policy[0]["id"], "export policy"), "verified_against_official_schedule": False}
    if cfg.inject_fault == "unsupported_citation" and c.retries == 0:
        cites.append({"chunk_id": "NOTE_FAKE_99", "quote": "Heading 9999 specifically provides for this article."})
    c.proposal = {"heading": d["heading"], "rule": d["rule"], "basis": cites, "excluded_alternatives": excl, "export_policy": pol}
    c.rec("classifier", "propose", t, heading=d["heading"], rule=d["rule"])
    return s


# ------------------------------------------------------------------ Agent 3: verifier (A3)
def verify(s: S):
    c = s["ctx"]; t = time.time(); p = c.proposal; reasons = []
    if p:
        cites = list(p["basis"]) + [x["citation"] for x in p["excluded_alternatives"]] + ([p["export_policy"]["citation"]] if p.get("export_policy") else [])
        for ci in cites:
            r = c.retrieved.get(ci["chunk_id"])
            if r is None: reasons.append(f"citation {ci['chunk_id']} does not resolve to a retrieved passage")
            elif ci["quote"] not in r["text"]: reasons.append(f"quote for {ci['chunk_id']} not found in retrieved text")
        h = c.retrieved.get("H" + p["heading"])
        if h is None or h["chapter"] not in ("73", "96"): reasons.append("proposed heading not retrieved or outside indexed chapters")
        if p["rule"] == "GRI 3(a)" and "GRI_3a" not in c.retrieved: reasons.append("GRI 3(a) cited but not retrieved")
        if not any(b["chunk_id"].startswith("GRI_") for b in p["basis"]): reasons.append("no GRI rule cited")
    c.verification = {"ok": not reasons, "reasons": reasons, "attempt": c.retries}
    c.rec("verifier", "verify", t, verification=c.verification)
    if reasons: VERIFY_FAIL.inc()
    return s


def after_verify(s: S):
    c = s["ctx"]
    if c.verification["ok"] or c.escalation: return "route"
    if c.retries < cfg.max_verify_retries and not c.over():
        c.retries += 1; c.strategy = "broad"; c.phase = "start"; c.named = {}; c.notes = {}; c.gri = []; c.policy = None; c.decision = None
        return "classify"                                        # search again with a different strategy
    c.escalation = ("verification_failed", "; ".join(c.verification["reasons"])); return "route"


# ------------------------------------------------------------------ router
def router(s: S):
    c = s["ctx"]; t = time.time(); d = c.decision or {}; p = c.proposal
    if c.escalation: route, why = "specialist-classification-review", c.escalation[1]; reason_code = c.escalation[0]
    elif d.get("kind") == "tie": route, why, reason_code = "specialist-classification-review", d["reason"], "tie_after_gri3"
    elif d.get("kind") == "out_of_scope": route, why, reason_code = "specialist-classification-review", d["reason"], "out_of_scope"
    elif d.get("kind") == "clarify": route, why, reason_code = "seek-product-clarification", d["reason"], "insufficient_description"
    elif p and c.degraded: route, why, reason_code = "specialist-classification-review", "LLM provider degraded during run; proposal not eligible for clear-for-filing", "degraded"
    else: route, why, reason_code = "clear-for-filing", f"verified proposal under {p['rule']} naming heading {p['heading']}", "verified"
    rationale = None
    if p and route == "clear-for-filing" and llm.enabled() and not c.degraded:
        try:
            txt, u = llm.complete(c.prompts["rationale_system"], json.dumps({"proposal": p}, default=str)[:3000], "rationale")
            rationale = guardrails.filter_output(txt); c.add_cost("rationale", u) if c.trace else None
        except llm.LLMUnavailable: c.degraded = True
    if rationale is None and p:
        rationale = guardrails.filter_output(f"Proposed heading {p['heading']} under {p['rule']}: " + p["basis"][0]["quote"] + " Proposal only; a licensed customs broker decides.")
    resp = {"run_id": c.run_id, "route": route, "reason_code": reason_code, "basis": why,
            "proposal": p, "rationale": rationale, "entities": c.entities,
            "questions": d.get("questions"), "degraded": c.degraded,
            "escalation_path": {"route": route, "next": "licensed customs broker decides; the system never files a declaration"},
            "verification": c.verification, "prompt_version": cfg.prompt_version,
            "steps": c.steps, "tool_calls": c.tool_calls, "cost": c.cost,
            "retrieved_passages": {k: v["text"] for k, v in c.retrieved.items()}}
    c.rec("router", "route", t, route=route)
    c.result = resp
    return s


def build():
    g = StateGraph(S)
    g.add_node("extract", extractor); g.add_node("classify", classifier); g.add_node("propose", propose)
    g.add_node("verify", verify); g.add_node("route", router)
    g.set_entry_point("extract"); g.add_edge("extract", "classify")
    g.add_conditional_edges("classify", lambda s: "propose" if s["ctx"].phase == "propose" else "classify", {"propose": "propose", "classify": "classify"})
    g.add_edge("propose", "verify")
    g.add_conditional_edges("verify", after_verify, {"route": "route", "classify": "classify"})
    g.add_edge("route", END)
    return g.compile()


_graph = None


def run_agent(run_id, req, index, t0=None):
    global _graph
    _graph = _graph or build()
    c = Ctx(run_id, req, index, t0)
    try:
        _graph.invoke({"ctx": c}, {"recursion_limit": 80})
    except Exception as ex:                       # agent failure mid-run -> honest escalation, never a confident answer
        c.escalation = ("agent_failure", f"{type(ex).__name__}: {ex}"); c.proposal = None; c.verification = {"ok": False, "reasons": [str(ex)], "attempt": c.retries}
        router({"ctx": c})
    c.result["trace"] = c.trace
    return c.result
