"""Hybrid retrieval: FTS5 BM25 + sqlite-vec KNN, fused with Reciprocal Rank Fusion."""
import re

from .normalize import tokens
from .store import pack

STOP = set("""the a an of to and or in on for is are was were be by with as at this that it from your you our we
i my me has have had not no shall may will under any such which who whom been being its their there these those
than then into upon also per sir madam dear kindly please request letter
का के की है हैं में से को और या पर यह वह इस उस भी तो ही एक कि जो""".split())
_NUMLIKE = re.compile(r"[0-9]")


def rrf(lists, k=60):
    """Fuse ranked id lists. Score = sum 1/(k + rank). Ties broken by id (tests.md 14.x)."""
    scores = {}
    for lst in lists:
        for rank, doc in enumerate(lst, start=1):
            scores[doc] = scores.get(doc, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: (-kv[1], str(kv[0])))


def fts_query(text: str, max_terms: int = 64) -> str:
    toks = tokens(text)
    seen, terms = set(), []
    for t in toks:
        if t in STOP or t in seen or (len(t) < 2 and not _NUMLIKE.search(t)):
            continue
        seen.add(t)
        terms.append('"' + t.replace('"', "") + '"')
    # number-like sequences (file nos., rule nos.) also as phrases: "12 3 2025"
    phrases = []
    run = []
    for t in toks + [""]:
        if _NUMLIKE.search(t):
            run.append(t)
        else:
            if len(run) >= 2:
                phrases.append('"' + " ".join(run) + '"')
            run = []
    return " OR ".join(phrases + terms[:max_terms])


def keyword_search(con, text, n=50):
    q = fts_query(text)
    if not q:
        return []
    rows = con.execute("SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY bm25(chunks_fts) LIMIT ?", (q, n))
    return [r[0] for r in rows]


def vector_search(con, embedder, text, n=50):
    v = embedder.query(text[:2000])
    rows = con.execute("SELECT rowid FROM chunks_vec WHERE embedding MATCH ? AND k = ? ORDER BY distance", (pack(v), n))
    return [r[0] for r in rows]


def snippet(text, query_tokens, width=300):
    low = text.lower()
    best = 0
    for t in query_tokens:
        i = low.find(t)
        if i >= 0:
            best = i
            break
    start = max(0, best - width // 3)
    s = text[start:start + width]
    return ("…" if start else "") + s + ("…" if start + width < len(text) else "")


def search(con, embedder, text, top=8, candidates=20, max_per_file=2, rerank=None, timings=None):
    """Return top chunks: [{rank, chunk_id, file, page, score, snippet, text}].
    BM25 + vector -> RRF -> cross-encoder rerank of the top `candidates` (20) -> at most `max_per_file` chunks per file."""
    import os
    import time
    rerank = (os.environ.get("DESK_NO_RERANK") != "1") if rerank is None else rerank
    kw = keyword_search(con, text)
    vec = vector_search(con, embedder, text)
    fused = rrf([kw, vec])[:candidates]
    rows = {cid: con.execute("SELECT file, page, text FROM chunks WHERE id=?", (cid,)).fetchone() for cid, _ in fused}
    order = fused
    if rerank and fused:
        from . import rerank as rr
        t0 = time.perf_counter()
        sc = rr.get().scores(text[:2000], [rows[cid][2] for cid, _ in fused])
        if timings is not None:
            timings["rerank_s"] = round(time.perf_counter() - t0, 3)
        order = sorted(zip([c for c, _ in fused], sc), key=lambda kv: (-kv[1], kv[0]))
    qt = [t for t in tokens(text) if t not in STOP and len(t) > 3]
    out, per_file = [], {}
    for cid, score in order:
        file, page, body = rows[cid]
        if per_file.get(file, 0) >= max_per_file:
            continue
        per_file[file] = per_file.get(file, 0) + 1
        out.append({"rank": len(out) + 1, "chunk_id": cid, "file": file, "page": page, "score": round(score, 5),
                    "in_keyword": cid in kw, "in_vector": cid in vec,
                    "snippet": snippet(body, qt), "text": body})
        if len(out) >= top:
            break
    return out


def top_files(hits):
    seen, files = set(), []
    for h in hits:
        if h["file"] not in seen:
            seen.add(h["file"])
            files.append({"file": h["file"], "best_page": h["page"], "rank": h["rank"]})
    return files
