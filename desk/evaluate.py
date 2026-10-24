"""Metrics over the scenario letters: recall@3, % quotes verified, time per letter, tokens/s.
python -m desk.evaluate [--no-llm] [--out data/eval.json]"""
import argparse
import json
import re
import sys
from pathlib import Path

from .cli import DEFAULT_DB, ROOT, answer
from .embed import Embedder
from .store import connect
from . import llm

LETTERS = ROOT / "tests" / "letters"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "data" / "eval.json"))
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    use_llm = not a.no_llm and bool(llm.api_key())
    con, emb = connect(DEFAULT_DB), Embedder()
    cases = json.loads((LETTERS / "cases.json").read_text(encoding="utf-8"))
    emb.query("warm up")
    if __import__("os").environ.get("DESK_NO_RERANK") != "1":
        from . import rerank
        print(json.dumps({"reranker_load_s": rerank.warm_up()}))  # once per process, not per letter
    rows, found, total, ver, lines, tps = [], 0, 0, 0, 0, []
    per_list = {"cases": [0, 0], "rules": [0, 0]}
    for c in cases:
        out = answer(con, emb, LETTERS / c["letter"], lang=c.get("lang", "en"), top=3, use_llm=use_llm)
        res = {"cases": [], "rules": []}
        for e in c["expected"]:
            hit = expected_ok(con, out[e["list"]], e)
            res[e["list"]].append(hit)
            per_list[e["list"]][0] += hit
            per_list[e["list"]][1] += 1
            found += hit
            total += 1
        row = {"id": c["id"], **{f"recall@3_{t}": f"{sum(v)}/{len(v)}" for t, v in res.items() if v},
               "retrieval_s": out["retrieval_s"], "rerank_s": out.get("rerank_s"), "total_s": out["total_s"],
               "cases_top3": [(h["file"], h["page"]) for h in out["cases"]],
               "rules_top3": [(h["file"], h["page"]) for h in out["rules"]]}
        d = out.get("draft")
        if d:
            v = sum(l["verified"] for l in d["lines"])
            ver += v
            lines += len(d["lines"])
            row["quotes_verified"] = f"{v}/{len(d['lines'])}"
            row["llm_stats"] = d["llm_stats"]
            row["cites"] = sorted(set(re.findall(r"\b(?:rule|section|नियम|धारा)\s*\d+[A-Z]?\b", " ".join(l["sentence"] for l in d["lines"]), re.I)))
            if d["llm_stats"].get("tokens_per_s_incl_prompt"):
                tps.append(d["llm_stats"]["tokens_per_s_incl_prompt"])
        elif out.get("draft_error"):
            row["draft_error"] = out["draft_error"]
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False))
    summary = {"recall@3": round(found / total, 3) if total else None,
               **{f"recall@3_{t}": round(f / n, 3) if n else None for t, (f, n) in per_list.items()},
               "quotes_verified_pct": round(100 * ver / lines, 1) if lines else None,
               "mean_time_per_letter_s": round(sum(r["total_s"] for r in rows) / len(rows), 2),
               "mean_rerank_s": round(sum(r["rerank_s"] or 0 for r in rows) / len(rows), 2),
               "rerank": __import__("os").environ.get("DESK_NO_RERANK") != "1",
               "mean_tokens_per_s": round(sum(tps) / len(tps), 2) if tps else None, "llm_used": use_llm}
    print(json.dumps(summary))
    Path(a.out).write_text(json.dumps({"cases": rows, "summary": summary}, ensure_ascii=False, indent=2), encoding="utf-8")


def _chunk_text(con, h):
    return h.get("text") or con.execute("SELECT text FROM chunks WHERE id=?", (h["chunk_id"],)).fetchone()[0]


def expected_ok(con, hits, e):
    """e: {list, file, text_regex?, page?, not_pages?}. A matching hit must be in `hits` (top 3), and no hit
    from the same file on a `not_pages` page may rank above it."""
    for h in hits:
        if h["file"] == e["file"] and h["page"] in e.get("not_pages", []):
            return False
        if h["file"] == e["file"] and (e.get("page") is None or h["page"] == e["page"]) and \
                (not e.get("text_regex") or re.search(e["text_regex"], _chunk_text(con, h), re.I | re.S)):
            return True
    return False


if __name__ == "__main__":
    main()
