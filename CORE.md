# Core engine + desk web app

Index -> retrieve -> draft -> verify (frozen core, tag `core-frozen-mvp-ui`), plus one web desk: Inbox -> sources -> cited draft -> edit -> Approve -> Outbox + audit log. No Kruti Dev, OCR, Excel, email or e-Office API yet.

## Setup (once, needs internet only for the first model download)
```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m desk index            # indexes samples/ into data/index.db (downloads e5 to .cache/; the first search downloads the ~0.6 GB reranker)
```
For the offline office box, copy `.cache/` along with the code and set `HF_HUB_OFFLINE=1`.

## Use
```powershell
# drafting (dev): copy .env.example to .env and fill GROQ_API_KEY (.env is git-ignored; never commit it)
.venv\Scripts\python -m desk answer tests\letters\c5_late_pension.txt --lang en --json data\c5.json
.venv\Scripts\python -m desk answer letter.txt --lang hi --ref-no "12/3/2025-प्रशा." --office "..." --to "..." --signatory "..."
.venv\Scripts\python -m desk answer letter.txt --no-llm   # retrieval only
.venv\Scripts\python -m desk models                       # models the drafting API offers
.venv\Scripts\python -m pytest -q tests                   # unit + scenario tests
.venv\Scripts\python -m desk.evaluate                     # recall@3, % quotes verified, time, tokens/s -> data/eval.json
```
Output: readable summary on screen (top files with page + snippet, summary, each draft line with its source, page,
quote and verified/FLAG status, then the filled template); full JSON with `--json`.

## Demo web (local)
```powershell
$env:DESK_DEMO_PASSCODE = "pick-one"          # demo mode needs a passcode (process env or .env)
.venv\Scripts\python -m desk web --port 8000   # open http://127.0.0.1:8000
```
One page (`mockup/index.html`) served by `desk/web.py` (FastAPI + uvicorn). Drop a letter -> the answer job runs in the
background (status queued/running/done/error/approved; the page polls every 2 s) -> edit lines -> Approve -> `outbox/reply.txt`.
Each draft line is `cited` (quote re-checked against the stored page text on every save and Approve), `clerk_fact`
(needs the clerk's note) or `standard`. A cited line with FLAG / not verified / source not in the retrieved set blocks
Approve unless an override reason is given (logged). Nothing is ever sent: Outbox = file download / copy to clipboard.
Data per case in `DESK_DATA_DIR/cases/<id>/` (inbound letter, meta.json, drafts/v1..n.json, answer.json,
archive_snapshot.json, outbox/reply.txt); append-only `DESK_DATA_DIR/audit.jsonl` (intake, answer_started, answer_done,
draft_edited, verify, approve, override, outbox). Per-line applicability (`desk/applicability.py`): rule/section number in
the letter vs the cited heading -> matches / against / not_assessed.

## Demo vs Office
| | demo | office |
|---|---|---|
| `DESK_MODE` | `demo` (default) | `office` |
| Data | public samples only | the office archive |
| Model | cloud (Groq) via `desk/llm.py`, capped at 3 calls / ~20k tokens per case | local only (LM Studio on localhost); refuses to start if the provider is groq/cerebras or any LLM URL is not localhost; sets `HF_HUB_OFFLINE=1` |
| Access | passcode (`DESK_DEMO_PASSCODE`) -> HttpOnly cookie; yellow DEMO banner | no passcode (single PC) |

## Deploy (Fly)
Long-running app with one volume (not serverless). Needs a Fly account and `fly auth login` once.
```powershell
fly launch --no-deploy --copy-config            # app name in fly.toml: office-desk-agent-ng, region bom
fly volumes create desk_data --size 3 --region bom
fly secrets set GROQ_API_KEY=... DESK_DEMO_PASSCODE=...   # secrets only here, never in files or the image
fly deploy
```
The image (`Dockerfile`, `.dockerignore` keeps `.env` out) carries the public-samples index as a seed; first boot copies it to
`/data/index.db` and downloads the models (~1 GB) into `/data/cache` (health check grace 120 s; the page shows "engine warming up").

## How it works
| Step | File | What |
|---|---|---|
| Extract | `desk/extract.py` | pypdfium2 page text (PDF), `.txt` = page 1; paragraph chunks of up to 1200 chars |
| Normalise | `desk/normalize.py` | NFC, nukta split, drop ZWJ/ZWNJ, Devanagari digits -> ASCII, light Hindi plural stemmer |
| Index | `desk/store.py` | SQLite: `chunks` + FTS5 (`chunks_fts`) + sqlite-vec (`chunks_vec`, 384-d). Legacy-font / garbled samples are skipped (`SKIP_SAMPLES`) until the Kruti Dev / OCR layers exist |
| Embed | `desk/embed.py` | intfloat/multilingual-e5-small via fastembed (ONNX, CPU), `query:` / `passage:` prefixes |
| Doc types | `desk/doc_types.json` | Hand-made table: each sample file is `rule` (Acts, Rules, CSMOP, guidelines, circulars, memos) or `case` (orders, letters, judgments). `reference` (glossary) is indexed but kept out of both lists. Stored in `docs.doc_type`; unlisted files default to `case` with a warning. A page-range table (`_page_types`) tags the forms / appendices / sample letters inside rule books as `case` (Pension Rules pp. 60–111, Leave Rules pp. 56–73, CSMOP appendix pages), applied per chunk by page at search time |
| Chunk | `desk/extract.py` | `rule` files: one chunk per section/rule (headings like `7.`, `Rule 65`, `धारा 7`, `नियम 8`); a section running over a page break gives one piece per page (cited to that page); oversized sections (>1500 chars) fall back to paragraph chunks; pieces without their own heading carry the section label (e.g. `Rule 65 — Interest on …`, stored in `chunks.heading`) for embedding/FTS/rerank only, never as quotable text. Other files: paragraph chunks (≤1200 chars) |
| Retrieve | `desk/retrieve.py` | Two lists, **past cases** and **rules**, top 3 each. Per type: BM25 + vector, RRF k=60 (ties by id) -> pool of 16 rules / 12 cases; the rules pool also gets up to 3 exact-phrase hits for statutory cues in the letter (section/rule numbers, "thirty days", "... Act", धारा/नियम) -> reranked (section label ≤20 tokens + raw text, 256 tokens per pair) -> at most 2 chunks per file. Both lists go to the drafter |
| Rerank | `desk/rerank.py` | BAAI/bge-reranker-v2-m3 cross-encoder, int8 ONNX (onnx-community export), onnxruntime CPU. Loaded and warmed up once at CLI/eval start. `DESK_NO_RERANK=1` turns it off |
| Draft | `desk/draft.py`, `desk/llm.py` | OpenAI-compatible `chat/completions` with `response_format: json_schema` (falls back to a strict JSON prompt + parse if the server rejects it); each line `{sentence, source_file, page, verbatim_quote}`; a source number like `[2]` in `source_file` is mapped back to that source. Development default: Groq `qwen/qwen3.8-27b`, settings from the git-ignored `.env` (`DESK_LLM_PROVIDER=groq`, `GROQ_API_KEY`, `GROQ_BASE_URL`, `DESK_LLM_MODEL`). Cerebras or LM Studio only when `DESK_LLM_PROVIDER=cerebras`/`lmstudio`; HTTP errors report the status code only |
| Verify | `desk/verify.py` | exact -> after normalisation -> RapidFuzz partial_ratio >= 95; else FLAG / FLAG wrong_source; cited file must be in the retrieved set |
| Template | `desk/template.py` | fixed Hindi / English official layout; the model only fills the body lines |

## Credits (third-party, used as dependencies, not copied)
pypdfium2 (Apache-2.0/BSD-3) · fastembed (Apache-2.0) · ONNX Runtime (MIT) · intfloat/multilingual-e5-small model (MIT) ·
BAAI/bge-reranker-v2-m3 model (Apache-2.0; int8 ONNX export by onnx-community/bge-reranker-v2-m3-ONNX) · tokenizers (Apache-2.0) · huggingface_hub (Apache-2.0) ·
sqlite-vec (Apache-2.0/MIT) · SQLite FTS5 (public domain) · RapidFuzz (MIT) · requests (Apache-2.0) · NumPy (BSD-3) ·
pytest (MIT) · jsonschema (MIT) · FastAPI (MIT) · Starlette (BSD-3) · uvicorn (BSD-3) · python-multipart (Apache-2.0) · HTTPX (BSD-3). RRF: Cormack, Clarke & Büttcher, SIGIR 2009. Drafting LLM is an external API (Groq for development; Cerebras or LM Studio optional; LM Studio is proprietary, not bundled).
