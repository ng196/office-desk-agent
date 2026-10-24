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


# Statutory cues in a letter: section/rule/article numbers, "thirty days"/"30 days", "... Act", धारा/नियम.
_CUES = [
    re.compile(r"\b(?:section|sec\.|rule|article|clause|para)\s*\d+[a-z]?(?:\s*\(\d+\))?", re.I),
    re.compile(r"\b(?:thirty|30|forty[- ]five|45|sixty|60|ninety|90)\s+days\b", re.I),
    re.compile(r"\b(?:[A-Z][a-z]+\s+){1,5}Act\b"),
    re.compile(r"(?:धारा|नियम)\s*[0-9०-९]+"),
]


def statutory_cues(text: str) -> list[str]:
    seen, out = set(), []
    for rx in _CUES:
        for m in rx.finditer(text or ""):
            c = " ".join(m.group(0).split())
            if c.lower() not in seen:
                seen.add(c.lower())
                out.append(c)
    return out


def cue_phrase_search(con, text, n=3, exclude=(), doc_type=None, types=None):
    """Exact-phrase FTS5 hits for the letter's statutory cues.

    For each cue phrase, chunks containing that exact phrase are ranked by BM25 against the
    whole letter; chunks already in the pool are skipped. Picks round-robin across cues, up to n.
    """
    rest = fts_query(text)
    per_cue = []
    for c in statutory_cues(text):
        t = tokens(c)
        if not t:
            continue
        q = '"' + " ".join(t) + '"' + (f" AND ({rest})" if rest else "")
        rows = con.execute("SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY bm25(chunks_fts) LIMIT ?",
                           (q, n + len(exclude) + (300 if doc_type else 0)))
        if doc_type:  # filter in Python: an `IN (subquery)` on the FTS table cost ~3.6 s per letter
            types = types or dict(con.execute("SELECT c.id, d.doc_type FROM chunks c JOIN docs d ON d.id=c.doc_id"))
            rows = [r for r in rows if types.get(r[0]) == doc_type][:n + len(exclude)]
        per_cue.append([r[0] for r in rows if r[0] not in exclude])
    out = []
    for i in range(n):
        for ids in per_cue:
            if i < len(ids) and ids[i] not in out and len(out) < n:
                out.append(ids[i])
    return out


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


def search(con, embedder, text, top=8, candidates=20, max_per_file=2, rerank=None, timings=None, cue_hits=3):
    """Return top chunks: [{rank, chunk_id, file, page, score, snippet, text}].
    BM25 + vector -> RRF -> cross-encoder rerank of the top `candidates` (20) -> at most `max_per_file` chunks per file."""
    import os
    import time
    rerank = (os.environ.get("DESK_NO_RERANK") != "1") if rerank is None else rerank
    kw = keyword_search(con, text)
    vec = vector_search(con, embedder, text)
    fused = rrf([kw, vec])[:candidates]
    # keyword boost: union (not re-score) the top exact-phrase hits for statutory cues into the rerank pool
    pool = {cid for cid, _ in fused}
    cues = cue_phrase_search(con, text, n=cue_hits, exclude=pool)
    fused = fused + [(cid, 0.0) for cid in cues]
    if timings is not None:
        timings["cue_candidates"] = len(cues)
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


def _hits(con, order, kw, vec, text, top, max_per_file):
    rows = {cid: con.execute("SELECT file, page, text FROM chunks WHERE id=?", (cid,)).fetchone() for cid, _ in order}
    qt = [t for t in tokens(text) if t not in STOP and len(t) > 3]
    out, per_file = [], {}
    for cid, score in order:
        file, page, body = rows[cid]
        if per_file.get(file, 0) >= max_per_file:
            continue
        per_file[file] = per_file.get(file, 0) + 1
        out.append({"rank": len(out) + 1, "chunk_id": cid, "file": file, "page": page, "score": round(score, 5),
                    "in_keyword": cid in kw, "in_vector": cid in vec, "snippet": snippet(body, qt), "text": body})
        if len(out) >= top:
            break
    return out


def search_split(con, embedder, text, top=3, candidates=12, max_per_file=2, rerank=None, timings=None, cue_hits=3,
                 per_type=50, depth=400):
    """Two lists, each from its own pool and reranked on its own: {"cases": [...], "rules": [...]}.

    BM25 + vector (deep) -> split by the file's doc_type -> RRF of the top `per_type` of each -> top `candidates` (12)
    per type ('reference' files are in neither list); the rules pool also gets the statutory cue-phrase hits -> bge rerank (256 tokens) -> 2 per file -> top."""
    import os
    import time
    rerank = (os.environ.get("DESK_NO_RERANK") != "1") if rerank is None else rerank
    kw = keyword_search(con, text, n=depth)
    vec = vector_search(con, embedder, text, n=depth)
    ids = set(kw) | set(vec)
    types = dict(con.execute("SELECT c.id, d.doc_type FROM chunks c JOIN docs d ON d.id=c.doc_id")) if ids else {}
    pools = {}
    for t in ("cases", "rules"):
        dt_ = t[:-1]
        fused = rrf([[c for c in kw if types.get(c) == dt_][:per_type], [c for c in vec if types.get(c) == dt_][:per_type]])[:candidates]
        if t == "rules":
            cues = cue_phrase_search(con, text, n=cue_hits, exclude={c for c, _ in fused}, doc_type="rule", types=types)
            fused += [(c, 0.0) for c in cues]
            if timings is not None:
                timings["cue_candidates"] = len(cues)
        pools[t] = fused
    if rerank and any(pools.values()):
        from . import rerank as rr
        t0 = time.perf_counter()
        allc = pools["cases"] + pools["rules"]
        body = dict(con.execute(f"SELECT id, text FROM chunks WHERE id IN ({','.join('?' * len(allc))})", [c for c, _ in allc]))
        # one batched call; each pair is scored on its own, so this equals reranking the two pools separately
        sc = rr.get().scores(text[:2000], [body[c] for c, _ in allc])
        if timings is not None:
            timings["rerank_s"] = round(time.perf_counter() - t0, 3)
        n = len(pools["cases"])
        for t, part in (("cases", sc[:n]), ("rules", sc[n:])):
            pools[t] = sorted(zip([c for c, _ in pools[t]], part), key=lambda kv: (-kv[1], kv[0]))
    return {t: _hits(con, pools[t], kw, vec, text, top, max_per_file) for t in ("cases", "rules")}


def top_files(hits):
    seen, files = set(), []
    for h in hits:
        if h["file"] not in seen:
            seen.add(h["file"])
            files.append({"file": h["file"], "best_page": h["page"], "rank": h["rank"]})
    return files
