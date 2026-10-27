"""D2: idempotent, incremental pipeline: read -> parse -> chunk -> index. CLI: python -m ecs.ingest [--full]"""
import argparse, hashlib, json, os, re, time

from ecs.config import cfg
from ecs.obs import INDEX_BUILT, INDEX_CHUNKS, INGEST_RATE, get_logger, log

lg = get_logger("ingest")


def _sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()


def parse_seed(path):
    """Seed/annotated text: blocks starting '@@ id=.. type=.. chapter=.. source=..'."""
    chunks, cur = [], None
    for line in open(path, encoding="utf-8").read().splitlines():
        if line.startswith("@@ "):
            if cur: chunks.append(cur)
            meta = dict(kv.split("=", 1) for kv in line[3:].split())
            cur = {"id": meta["id"], "type": meta["type"], "chapter": meta["chapter"], "source": meta.get("source", ""), "text": ""}
        elif cur is not None and not line.startswith("#"):
            cur["text"] += (" " if cur["text"] else "") + line.strip()
    if cur: chunks.append(cur)
    for c in chunks: c["text"] = c["text"].strip()
    return chunks



def parse_pdf(path):
    """Heuristic PDF chunker for tariff headings and notes."""
    from pypdf import PdfReader

    text = "\n".join(
        (page.extract_text() or "") for page in PdfReader(path).pages
    )
    base = re.sub(r"\W+", "_", os.path.basename(path).rsplit(".", 1)[0])

    chunks = []
    ch = re.search(
        r"chapter\s+(\d{2})",
        os.path.basename(path).lower() + text[:400].lower()
    )
    chapter = ch.group(1) if ch else "0"

    # Normalize line endings and whitespace before detecting heading boundaries.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.splitlines()

    heading_start = re.compile(
        r"^\s*\*?\s*(\d{4})(?=\s|$)\s*(.*)$"
    )

    headings = []
    current_code = None
    current_lines = []

    for line in lines:
        match = heading_start.match(line)

        # A new heading must have a plausible four-digit code and description.
        if match:
            code = match.group(1)
            description = match.group(2).strip()

            # Ignore heading-like numbers embedded in obvious non-heading text.
            if not description or description[0].isalpha() or description.startswith(("—", "-")):
                if current_code is not None:
                    headings.append((current_code, current_lines))
                current_code = code
                current_lines = [description]
                continue

        if current_code is not None:
            current_lines.append(line.strip())

    if current_code is not None:
        headings.append((current_code, current_lines))

    for code, body_lines in headings:
        body = " ".join(" ".join(body_lines).split())
        chunks.append({
            "id": f"H{code}",
            "type": "heading",
            "chapter": code[:2],
            "source": base,
            "text": f"{code} - {body}"
        })

    for m in re.finditer(r"(?ms)^(Notes?\.?\s*\d*.*?)(?=^\d{4}\s|\Z)", text):
        body = " ".join(m.group(1).split())
        cid = "NOTE_" + hashlib.sha1(body.encode()).hexdigest()[:8]
        chunks.append({
            "id": cid,
            "type": "note",
            "chapter": chapter,
            "source": base,
            "text": body[:1500]
        })

    return chunks



def run(full=False):
    t0 = time.time()
    old = {}
    if os.path.exists(cfg.index_path) and not full:
        old = json.load(open(cfg.index_path))
    versions, by_src, reused = {}, {}, 0
    for c in old.get("chunks", []): by_src.setdefault(c["_file"], []).append(c)
    files = sorted(os.path.join(r, f) for r, _, fs in os.walk(cfg.corpus_dir) for f in fs if f.endswith((".txt", ".pdf")))
    chunks = {}
    for p in files:
        sha = _sha(p); versions[os.path.relpath(p, cfg.corpus_dir)] = sha
        if old.get("versions", {}).get(os.path.relpath(p, cfg.corpus_dir)) == sha and p in by_src:
            parsed, reused = by_src[p], reused + 1          # unchanged file: do not re-parse/re-embed
        else:
            parsed = parse_seed(p) if p.endswith(".txt") else parse_pdf(p)
            for c in parsed: c["_file"] = p
        for c in parsed: chunks[c["id"]] = c                 # keyed by id => re-running never duplicates
    out = [chunks[k] for k in sorted(chunks)]
    dt = max(time.time() - t0, 1e-6)
    meta = {"built_at": time.time(), "versions": versions, "n_chunks": len(out), "chunks_per_second": round(len(out) / dt, 1)}
    os.makedirs(os.path.dirname(cfg.index_path) or ".", exist_ok=True)
    tmp = cfg.index_path + ".tmp"
    json.dump({**meta, "chunks": out}, open(tmp, "w"))
    os.replace(tmp, cfg.index_path)                           # atomic swap
    INDEX_CHUNKS.set(len(out)); INDEX_BUILT.set(meta["built_at"]); INGEST_RATE.set(meta["chunks_per_second"])
    log(lg, "ingest_complete", files=len(files), reused_files=reused, **{k: meta[k] for k in ("n_chunks", "chunks_per_second")})
    return meta


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--full", action="store_true", help="ignore previous index")
    print(json.dumps({k: v for k, v in run(ap.parse_args().full).items() if k != "versions"}))
