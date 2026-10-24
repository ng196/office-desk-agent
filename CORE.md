# Core engine (CLI only)

Index -> retrieve -> draft -> verify. No UI, Kruti Dev, OCR, Approve/Outbox, egress block or audit log yet.

## Setup (once, needs internet only for the first model download)
```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m desk index            # indexes samples/ into data/index.db (downloads e5 model to .cache/)
```
For the offline office box, copy `.cache/` along with the code and set `HF_HUB_OFFLINE=1`.

## Use
```powershell
$env:LMSTUDIO_API_KEY = "<your LM Studio key>"   # never commit it
.venv\Scripts\python -m desk answer tests\letters\c5_late_pension.txt --lang en --json data\c5.json
.venv\Scripts\python -m desk answer letter.txt --lang hi --ref-no "12/3/2025-प्रशा." --office "..." --to "..." --signatory "..."
.venv\Scripts\python -m desk answer letter.txt --no-llm   # retrieval only
.venv\Scripts\python -m desk models                       # what LM Studio has loaded
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
| Retrieve | `desk/retrieve.py` | BM25 top-50 + vector top-50, RRF k=60, ties by id |
| Draft | `desk/draft.py`, `desk/llm.py` | LM Studio `/v1/chat/completions`, `response_format: json_schema`; each line `{sentence, source_file, page, verbatim_quote}`; key from `LMSTUDIO_API_KEY` (process or Windows user env) |
| Verify | `desk/verify.py` | exact -> after normalisation -> RapidFuzz partial_ratio >= 95; else FLAG / FLAG wrong_source; cited file must be in the retrieved set |
| Template | `desk/template.py` | fixed Hindi / English official layout; the model only fills the body lines |

## Credits (third-party, used as dependencies, not copied)
pypdfium2 (Apache-2.0/BSD-3) · fastembed (Apache-2.0) · ONNX Runtime (MIT) · intfloat/multilingual-e5-small model (MIT) ·
sqlite-vec (Apache-2.0/MIT) · SQLite FTS5 (public domain) · RapidFuzz (MIT) · requests (Apache-2.0) · NumPy (BSD-3) ·
pytest (MIT) · jsonschema (MIT). RRF: Cormack, Clarke & Büttcher, SIGIR 2009. LM Studio is a separate install (proprietary; not bundled).
