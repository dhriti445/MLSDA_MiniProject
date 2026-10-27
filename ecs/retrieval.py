"""Lexical BM25 retrieval over chunks (pure python). Embedding backends can be added behind Index.search."""
import json, math, re
from collections import Counter

STOP = set("a an and the of with for to in on or by is are be as at from this that it its into than other".split())


def stem(w):
    if len(w) > 4 and w.endswith("ies"): return w[:-3] + "y"
    if len(w) > 4 and re.search(r"(xes|ches|shes|sses)$", w): return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"): return w[:-1]
    return w


def tokens(text):
    return [stem(w) for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP and len(w) > 1]


def title_of(chunk):
    """Heading title: text after 'NNNN - '."""
    return re.sub(r"^\d{4}\s*-\s*", "", chunk["text"]).strip()


class Index:
    def __init__(self, chunks, meta=None):
        self.chunks = {c["id"]: c for c in chunks}
        self.meta = meta or {}
        self.tf = {i: Counter(tokens(c["text"])) for i, c in self.chunks.items()}
        self.df = Counter(t for tf in self.tf.values() for t in tf)
        self.n = max(len(self.chunks), 1)
        self.avg = sum(sum(tf.values()) for tf in self.tf.values()) / self.n or 1

    @classmethod
    def load(cls, path):
        d = json.load(open(path))
        return cls(d["chunks"], {k: v for k, v in d.items() if k != "chunks"})

    def search(self, query, k=5, types=None, chapters=None):
        q = list(dict.fromkeys(tokens(query)))
        res = []
        for i, c in self.chunks.items():
            if types and c["type"] not in types: continue
            if chapters and c["chapter"] not in chapters: continue
            tf = self.tf[i]; dl = sum(tf.values()); s = 0.0; hit = 0
            for t in q:
                if t in tf:
                    hit += 1
                    idf = math.log(1 + (self.n - self.df[t] + .5) / (self.df[t] + .5))
                    s += idf * tf[t] * 2.2 / (tf[t] + 1.2 * (.25 + .75 * dl / self.avg))
            if hit:
                res.append({"id": i, "score": round(s, 4), "coverage": round(hit / max(len(q), 1), 3),
                            "type": c["type"], "chapter": c["chapter"], "text": c["text"]})
        res.sort(key=lambda r: (-r["score"], r["id"]))
        return res[:k]

    def get(self, cid):
        c = self.chunks.get(cid)
        return None if not c else {"id": cid, "score": None, "coverage": None, "type": c["type"],
                                   "chapter": c["chapter"], "text": c["text"]}
