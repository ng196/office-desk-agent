# Core engine (CLI only)

Index -> retrieve -> draft -> verify. No UI, Kruti Dev, OCR, Approve/Outbox, egress block or audit log yet.

## Setup (once, needs internet only for the first model download)
```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m desk index            # indexes samples/ into data/index.db (downloads e5 to .cache/; the first search downloads the ~0.6 GB reranker)
```
For the offline office box, copy `.cache/` along with the code and set `HF_HUB_OFFLINE=1`.

## Use
```powershell
# drafting (dev): copy .env.example to .env and fill CEREBRAS_API_KEY (.env is git-ignored; never commit it)
.venv\Scripts\python -m desk answer tests\letters\c5_late_pension.txt --lang en --json data\c5.json
.venv\Scripts\python -m desk answer letter.txt --lang hi --ref-no "12/3/2025-प्रशा." --office "..." --to "..." --signatory "..."
.venv\Scripts\python -m desk answer letter.txt --no-llm   # retrieval only
.venv\Scripts\python -m desk models                       # models the drafting API offers
.venv\Scripts\python -m pytest -q tests                   # unit + scenario tests
.venv\Scripts\python -m desk.evaluate                     # recall@3, % quotes verified, time, tokens/s -> data/eval.json
```
Output: readable summary on screen (top files with page + snippet, summary, each draft line with its source, page,
quote and verified/FLAG status, then the filled template); full JSON with `--json`.

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
| Draft | `desk/draft.py`, `desk/llm.py` | OpenAI-compatible `chat/completions` with `response_format: json_schema` (falls back to a strict JSON prompt + parse if the server rejects it); each line `{sentence, source_file, page, verbatim_quote}`; a source number like `[2]` in `source_file` is mapped back to that source. Development default: Cerebras `qwen-3.8-27b`, settings from the git-ignored `.env` (`CEREBRAS_API_KEY`, `CEREBRAS_BASE_URL`, `DESK_LLM_MODEL`). LM Studio only with `DESK_LLM_PROVIDER=lmstudio` (`LMSTUDIO_API_KEY`) |
| Verify | `desk/verify.py` | exact -> after normalisation -> RapidFuzz partial_ratio >= 95; else FLAG / FLAG wrong_source; cited file must be in the retrieved set |
| Template | `desk/template.py` | fixed Hindi / English official layout; the model only fills the body lines |

## Credits (third-party, used as dependencies, not copied)
pypdfium2 (Apache-2.0/BSD-3) · fastembed (Apache-2.0) · ONNX Runtime (MIT) · intfloat/multilingual-e5-small model (MIT) ·
BAAI/bge-reranker-v2-m3 model (Apache-2.0; int8 ONNX export by onnx-community/bge-reranker-v2-m3-ONNX) · tokenizers (Apache-2.0) · huggingface_hub (Apache-2.0) ·
sqlite-vec (Apache-2.0/MIT) · SQLite FTS5 (public domain) · RapidFuzz (MIT) · requests (Apache-2.0) · NumPy (BSD-3) ·
pytest (MIT) · jsonschema (MIT). RRF: Cormack, Clarke & Büttcher, SIGIR 2009. Drafting LLM is an external API (Cerebras for development; LM Studio optional, proprietary, not bundled).
