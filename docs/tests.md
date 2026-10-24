# Test spec: offline Hindi/English desk helper
Based on `components.md` (same row numbers). Written 24 Oct 2026 (IST).

## 0. Assumptions and fixtures
- **Target box:** 16 GB RAM, 8-core x86-64 CPU, no GPU, SSD, Linux or Windows. Clerks reach it from LAN browsers.
- **App RAM ceiling:** 12 GB total, leaving 4 GB for the OS. Speed budgets are targets to measure on this box, not proven numbers.
- **Allowed licences:** MIT, Apache-2.0, BSD, MPL-2.0, ISC, public domain; LGPL only when dynamically linked. Data may be CC-BY or CC0; NC datasets are for evaluation only and never ship. **Not allowed:** AGPL, any NC model, BSL, modified OpenRAIL-M.
- **LLM serving = LM Studio**, checked against its docs:
  - OpenAI-compatible `POST http://localhost:1234/v1/chat/completions` ([docs](https://lmstudio.ai/docs/developer/openai-compat)).
  - Structured output via `response_format: {type:"json_schema", json_schema:{name, strict, schema}}`. The result comes back as a string in `choices[0].message.content`. For GGUF models it is enforced with llama.cpp grammar ([docs](https://lmstudio.ai/docs/developer/openai-compat/structured-output)). The docs warn that models **below 7B** may not handle structured output well.
  - Token stats: `POST /api/v0/chat/completions` returns `stats.tokens_per_second`, `time_to_first_token` and `generation_time`, plus `usage` ([docs](https://lmstudio.ai/docs/developer/rest/endpoints)). `POST /api/v1/chat` returns `stats.tokens_per_second`, `time_to_first_token_seconds`, `input_tokens`, `total_output_tokens` and `model_load_time_seconds` ([docs](https://lmstudio.ai/docs/developer/rest/chat)). Whether `/v1/chat/completions` returns a `usage` block is **UNVERIFIED** (no example in the docs), so speed tests use `/api/v0`.
  - Offline: chat and the local server need no internet. Discover/search, model and runtime downloads, and update checks do ([docs](https://lmstudio.ai/docs/app/offline)). Models are sideloaded.
  - "Serve on Local Network" exists ([docs](https://lmstudio.ai/docs/developer/core/server)) and **must stay off**.
  - **Licence:** the [app terms](https://lmstudio.ai/app-terms) are proprietary. Use is free for "internal business purposes", but redistribution, SaaS and service-bureau use are not allowed. So each office installs LM Studio itself and we cannot bundle it. Keep [llama.cpp](https://github.com/ggml-org/llama.cpp) `llama-server` (MIT) as a drop-in fallback on the same OpenAI API.
- **Fixtures** (we build these; no public set exists):
  - `F-101`: a past reply, "पत्र सं. 12/3/2025-प्रशा., दिनांक 15.10.2025, विषय: अर्जित अवकाश का नकदीकरण".
  - `R-07`: a rule extract containing "अर्जित अवकाश का नकदीकरण अधिकतम 300 दिन तक".
  - `E-22`: an English past letter, "No. A-12011/5/2024-Estt., Subject: Leave encashment".
  - `L-1`: the incoming letter, a Kruti Dev 010 digital PDF asking about leave encashment.
  - 200 distractor letters.

## 1. Constraints per component
| # | Component | Offline | CPU | Speed budget | RAM budget | Licence (chosen) |
|---|---|---|---|---|---|---|
| 1 | File watch (watchdog) | Yes | Yes | Picked up in ≤5 s; rescan every ≤60 s | ≤100 MB | Apache-2.0 |
| 2 | Digital PDF text (pypdfium2/pdfplumber) | Yes | Yes | ≤0.2 s/page | ≤300 MB | Apache/BSD, MIT (PyMuPDF AGPL **banned**) |
| 3 | Scanned vs digital | Yes | Yes | ≤50 ms/page | ≤100 MB | own code / MPL-2.0 |
| 4 | OCR (Tesseract hin+eng; PaddleOCR devanagari) | Yes | Yes | ≤5 s/page at 300 DPI | ≤1.5 GB | Apache-2.0 (Surya weights **banned**) |
| 5 | Legacy-font detection | Yes | Yes | ≤20 ms/page | ≤50 MB | MIT / own |
| 6 | Legacy to Unicode | Yes | Yes | ≤50 ms/page | ≤50 MB | MIT (HinLegacy / hindi-font-converter) |
| 7 | Unicode to Kruti Dev | Yes, in browser | Yes | ≤50 ms/letter | n/a | MIT |
| 8 | LID (IndicLID / script ranges) | Yes | Yes | ≤5 ms/chunk (FTN stage) | ≤1 GB | MIT |
| 9 | Chunking (Docling + own regex) | Yes | Yes | ≤3 s/page | ≤2 GB | MIT |
| 10 | Normalisation (indic_nlp) | Yes | Yes | ≤1 ms/sentence | ≤50 MB | MIT |
| 11 | BM25 (SQLite FTS5 / Tantivy) | Yes | Yes | ≤50 ms/query on 100k chunks | ≤500 MB | PD / MIT |
| 12 | Embeddings (multilingual-e5-small, fastembed) | Yes | Yes | ≤30 ms/chunk; ≤100 ms/query | ≤1 GB | MIT / Apache-2.0 |
| 13 | Vector store (sqlite-vec / FAISS) | Yes | Yes | ≤50 ms top-10 over 100k | ≤1 GB | Apache-2.0 / MIT |
| 14 | RRF fusion | Yes | Yes | ≤1 ms | n/a | own code |
| 15 | Reranker (gte-multilingual-reranker-base or bge-reranker-v2-m3 int8) | Yes | Yes | ≤8 s per letter for rules 20 + cases 12 candidates × 256 tokens (whole search) | ≤1.5 GB | Apache-2.0 |
| 16 | LLM (Qwen3-4B or Qwen2.5-7B-Instruct, Q4 GGUF) | Yes (sideloaded) | Yes | Summary ≤30 s | 4B ≤4 GB, 7B ≤6.5 GB with 8k context | Apache-2.0 model |
| 17 | Serving (LM Studio, localhost:1234) | Yes | Yes | Generation ≥8 tok/s (4B) / ≥4 tok/s (7B); time to first token ≤30 s for a 4k-token prompt | Included in row 16 | Proprietary, free for internal business use (see §0) |
| 18 | Grounded drafting (json_schema) | Yes | Yes | Draft ≤120 s | Included in row 16 | n/a |
| 19 | Quote check (exact + RapidFuzz) | Yes | Yes | ≤100 ms/draft | ≤50 MB | MIT |
| 20 | Support check (MiniCheck/AlignScore-base) | Yes | Yes | ≤0.5 s/line | ≤1.5 GB | Apache-2.0 / MIT |
| 21 | Templates (Jinja2 / docxtpl) | Yes | Yes | ≤200 ms | ≤50 MB | BSD / LGPL-2.1 |
| 22 | Egress block (nftables / Windows Firewall) | Yes | n/a | n/a | n/a | OS |
| 23 | Audit log (SHA-256 chain in SQLite) | Yes | Yes | ≤10 ms/append; full verify ≤5 s for 1M entries | ≤100 MB | own code |
| 24 | LAN login (built-in sessions) | Yes | Yes | ≤200 ms/login | ≤50 MB | own code |

> **Latency note (24 Oct 2026, Desk Lead):** the retrieval bar for rows 15/15.4 is relaxed from 3 s to ≤8 s on CPU. The end-to-end budget is 3 min per letter, so ~6 s for search is fine. Measured on the dev PC (Ryzen 7 250, CPU): ~5.5 s per letter for bge-reranker-v2-m3 int8, top 20 × 256 tokens.

> **Retrieval settings (24 Oct 2026, Desk Lead):**
> - **Two lists:** top 3 *past cases* and top 3 *rules*, by a hand-made file-level tag in `desk/doc_types.json` (`rule`: Acts, Rules, CSMOP, guidelines, circulars, memos, notifications; `case`: orders, letters, judgments, tenders; `reference`: glossary, indexed but in neither list).
> - **Pools:** rules 20, cases 12 (BM25 + vector, RRF k=60). The rules pool also gets up to 3 exact-phrase FTS5 hits for statutory cues in the letter (section/rule numbers, "thirty days"/"30 days", "… Act", धारा/नियम) as a union, not a re-score. Each pool is reranked with bge-reranker-v2-m3 (int8, CPU) at 256 tokens per pair; at most 2 chunks per file in each list. The reranker is loaded and warmed up once at process start.
> - **Section chunking (`rule` files only; cases keep paragraph chunks ≤1200 chars):** split at headings at the start of a line (`7.`, `65.`, `12.5.`, `Rule 65`, `Section 7`, `धारा 7`, `नियम 8`; the title must start with a capital, `(` or Devanagari). A section running over a page break gives one piece per page, cited to that page. A section over 1500 characters falls back to paragraph chunks; a piece under 200 characters is merged into the previous piece on the same page.
> - **Heading prefix:** every piece that does not start with its own heading (paragraph pieces of a long section, run-over pieces on the next page) carries its section label, e.g. `Rule 65 — Interest on delayed payment of gratuity, pension and family pension`. The label is used for embedding, FTS and rerank only; it is stored apart from the chunk text (`chunks.heading`), is never quotable, and quotes are verified against the raw page text.

## 2. Unit tests (input → expected)
Legacy-font strings were run on this box through two converters:
- **K**: [hindi-font-converter](https://github.com/manishprajapatidev/hindi-font-converter) `kd.js`/`ch.js`
- **H**: [HinLegacy](https://github.com/satvikmishra44/HinLegacy)

"✔2" means both agree, "✔1" means one source only, and "BUG-H" means HinLegacy gets it wrong.

| ID | Input | Expected |
|---|---|---|
| 1.1 | Copy `L-1.pdf` into `inbox/` | Job queued in ≤5 s; sha256 stored |
| 1.2 | Same file dropped twice | One record (deduplicated by hash) |
| 1.3 | File still being copied (size changing) | Not processed until size is stable for 2 s |
| 1.4 | File added on an SMB share with no event | Picked up by the rescan in ≤60 s |
| 2.1 | Unicode PDF containing "विषय: अर्जित अवकाश का नकदीकरण" | Extracted text (NFC) contains that exact string |
| 2.2 | English PDF `E-22` | Contains "No. A-12011/5/2024-Estt." exactly |
| 2.3 | `L-1.pdf` | Font list contains a name matching `/kruti ?dev ?010/i` |
| 2.4 | Password-protected PDF | Clean error `encrypted`, no crash, logged |
| 3.1 | Image-only scanned page | `scanned` |
| 3.2 | Digital page with ≥200 characters plus a stamp image | `digital` |
| 3.3 | Text layer of junk/control glyphs (e.g. `\x03\x04\x05`) | `needs_ocr` |
| 3.4 | Kruti Dev text page | `digital+legacy` (convert, don't OCR) |
| 4.1 | 300-DPI render of "भारत सरकार" (Noto Sans Devanagari) | Exactly "भारत सरकार" |
| 4.2 | Line "संदर्भ: No. A-12011/5/2024-Estt." (hin+eng) | CER ≤2%; the file no. is exact |
| 4.3 | Same page rotated 90° | Auto-rotated; same text as 4.1 |
| 4.4 | 200-DPI photocopy of `F-101` | CER ≤8% |
| 5.1 | "Hkkjr ljdkj dk i=" | `remington_legacy` (Kruti/DevLys share the layout; H returns `devlys_010` at 0.47 confidence) |
| 5.2 | "Government of India" | `english`, not legacy (H: correctly declines) |
| 5.3 | "ÖæÚUÌ âÚU·¤æÚU" | `chanakya` (H labels it `walkman_chanakya_905`, confidence 1.0, **but its decoder outputs garbage**, BUG-H) |
| 5.4 | "भारत सरकार" | `unicode` |
| 5.5 | PDF font `ABCDEF+KrutiDev010` | `krutidev` from the font name, before any text heuristics |
| 6.1 | Kruti "Hkkjr" | "भारत" ✔2 |
| 6.2 | Kruti "fgUnh" / "ljdkj" / "i=" | "हिन्दी" / "सरकार" / "पत्र" ✔2 |
| 6.3 | Kruti "fo\"k;" / "vkns'k" / "jktHkk\"kk" / "ea=ky;" | "विषय" / "आदेश" / "राजभाषा" / "मंत्रालय" ✔2 |
| 6.4 | Kruti "esjk uke usgy gSA" | "मेरा नाम नेहल है।" ✔2 (also the kru2uni README example) |
| 6.5 | Kruti "dk;kZy;" | "कार्यालय" ✔1 (K). **BUG-H:** H outputs "कार््यालय" (double halant) |
| 6.6 | Chanakya "ÖæÚUÌ" / "âÚU·¤æÚU" / "çßáØ" / "çÎÙæ´·¤" / "ÂG" | "भारत" / "सरकार" / "विषय" / "दिनांक" / "पत्र" ✔1 (K `ch.js` only; round-trips). **No second source confirms it** |
| 6.7 | DevLys 010 "Hkkjr" | "भारत" ✔1 (H; it encodes DevLys the same as Kruti for every word tested). Real DevLys documents **UNVERIFIED** |
| 7.1 | "भारत" → Kruti | "Hkkjr" ✔2 |
| 7.2 | "पत्र" / "मंत्रालय" / "राजभाषा" / "धन्यवाद" / "श्री" | "i=" / "ea=ky;" / "jktHkk\"kk" / "/kU;okn" / "Jh" ✔2 |
| 7.3 | Round trip "कार्यालय" → "dk;kZy;" → back | "कार्यालय" (passes with K; fails with H) |
| 7.4 | "भारत" → Chanakya | "ÖæÚUÌ" ✔1 (K). H's Chanakya encoder is broken: it outputs "्ाH्ाk…" |
| 8.1 | "कृपया संलग्न पत्र देखें" | `hin_Deva` |
| 8.2 | "Please see the enclosed letter" | `eng_Latn` |
| 8.3 | "kripya sanlagn patra dekhen" | `hin_Latn` (IndicLID handles romanised Hindi) |
| 8.4 | "Hkkjr ljdkj" with no legacy gate | Must **not** reach the index as `eng_Latn` (pipeline assert) |
| 9.1 | Hindi letter with a header block | Fields: `ref`="12/3/2025-प्रशा.", `date`="15.10.2025", `subject`="अर्जित अवकाश का नकदीकरण", `signoff`="भवदीय" |
| 9.2 | `E-22` | `ref`="A-12011/5/2024-Estt.", `subject`="Leave encashment", `signoff`="Yours faithfully" |
| 9.3 | 3-page body | Every chunk ≤512 tokens and ends at "।" or "." |
| 9.4 | Letter with a table | Table kept as one chunk with its caption |
| 10.1 | "\u0958" (क़, precomposed) and "\u0915\u093C" (क + nukta) | Both become `U+0915 U+093C` (checked with indic_nlp) |
| 10.2 | "क्\u200dष" (with ZWJ) | "क्ष" (checked) |
| 10.3 | "यह पत्र है। कृपया देखें।" | 2 sentences (checked) |
| 10.4 | "१२/३/२०२५" | Index key "12/3/2025". indic_nlp does **not** do this (checked), so our own step must; display keeps the original |
| 11.1 | Query "12/3/2025-प्रशा." | `F-101` at rank 1 |
| 11.2 | Query "१२/३/२०२५" | `F-101` in the top 3 (via 10.4) |
| 11.3 | Query "A-12011/5/2024" | `E-22` at rank 1 |
| 11.4 | Query "अवकाशों" (plural) | `R-07` in the top 5 (needs a stemmer or prefix query) |
| 12.1 | Query "leave encashment" (English) | Hindi `R-07` in the top 3 |
| 12.2 | Query "छुट्टी के बदले भुगतान" (paraphrase, no shared words) | `R-07` in the top 5 |
| 12.3 | Query "वाहन खरीद" | `R-07` not in the top 10 |
| 12.4 | Any e5 call | Uses the `query: ` / `passage: ` prefixes (unit assert) |
| 13.1 | 100k × 384-d vectors, top-10 search | ≤50 ms; recall@10 vs brute force ≥0.95 |
| 13.2 | Delete doc `F-101` | None of its vectors are returned |
| 13.3 | Restart the service | Same top-10 as before the restart |
| 14.1 | BM25 [d1,d2,d3], vector [d3,d1,d4], k=60 | d1 (0.03252), d3 (0.03227), d2 (0.01613), d4 (0.01587) |
| 14.2 | One list empty | Output = the other list's order |
| 14.3 | Tied scores | Ordered by doc id (deterministic) |
| 15.1 | "अर्जित अवकाश नकदीकरण नियम", `R-07` at rank 8 of 30 | `R-07` in the top 3 after reranking |
| 15.2 | English query against Hindi candidates | Relevant Hindi doc in the top 3 |
| 15.3 | Same input run twice | Identical order |
| 15.4 | rules 20 + cases 12 candidates × 256 tokens | ≤8 s wall time on CPU (whole search per letter) |
| 16.1 | `GET /v1/models` | Lists the loaded model id |
| 16.2 | `/v1/chat/completions`: summarise `L-1` in Hindi | ≤80 words; ≥90% Devanagari letters; contains "12/3/2025-प्रशा." verbatim |
| 16.3 | Summarise `E-22` | English; contains "A-12011/5/2024-Estt." |
| 16.4 | Same request with egress blocked (row 22) | Still 200 OK |
| 17.1 | `POST /api/v0/chat/completions`, 4B Q4, 256 output tokens | `stats.tokens_per_second` ≥8 |
| 17.2 | Same call with a 4k-token prompt | `stats.time_to_first_token` ≤30 s |
| 17.3 | Second call with the model warm (`/api/v1/chat`) | `model_load_time_seconds` absent |
| 17.4 | `curl http://<LAN-IP>:1234/v1/models` from a clerk PC | Connection refused (localhost only) |
| 18.1 | Draft with schema `{lines:[{text, source_id, quote}]}`, `strict:true` | Content parses as JSON and validates 100% |
| 18.2 | Same draft | Every `source_id` is in the retrieved set given in the prompt |
| 18.3 | `L-1` plus retrieved {F-101, R-07} | At least one line cites `R-07` with a quote from it |
| 18.4 | No relevant source in context | Lines carry `source_id:null`, so the UI flags them; no invented ids |
| 19.1 | Quote "अर्जित अवकाश का नकदीकरण", cited as `R-07` | `verbatim` |
| 19.2 | Same quote with a ZWJ or a precomposed nukta | `verbatim_after_norm` |
| 19.3 | "अर्जित छुट्टी का नकदीकरण" (paraphrase) | `FLAG` (fuzzy <95) |
| 19.4 | Real quote, but it is from `F-101` and cited as `R-07` | `FLAG wrong_source` |
| 20.1 | Line "कर्मचारी 300 दिन तक अर्जित अवकाश नकद करा सकते हैं" + quote "अर्जित अवकाश का नकदीकरण अधिकतम 300 दिन तक" | `supported` |
| 20.2 | Same line with "400 दिन" | `unsupported` |
| 20.3 | English line "Encashment is allowed up to 300 days" + the same Hindi quote | `supported` (cross-lingual) |
| 21.1 | Hindi template with all fields | Order: "पत्र सं." → "भारत सरकार" → "दिनांक" → "सेवा में" → "विषय:" → "संदर्भ:" → body → "भवदीय" |
| 21.2 | English template | Order: "No." → "Government of India" → "Dated" → "To" → "Subject:" → "Yours faithfully" |
| 21.3 | `date` missing | Render error, no blank field |
| 21.4 | Date 2025-10-15 | "15.10.2025" (Hindi) / "15th October, 2025" (English) |
| 22.1 | `curl -m5 https://huggingface.co` as the app user | Fails in ≤5 s |
| 22.2 | DNS lookup of `example.com` from the app | Fails |
| 22.3 | Clerk PC → app HTTPS port | Allowed |
| 22.4 | LM Studio update check / Discover tab | Fails quietly; local chat still works |
| 23.1 | Append 3 events, run verify | `OK`, head hash = SHA256(prev ‖ canonical JSON) |
| 23.2 | Edit event 2's payload in SQLite | Verify fails at entry 2 |
| 23.3 | Delete the last entry | Detected against the exported daily checkpoint |
| 23.4 | Swap entries 2 and 3 | Verify fails |
| 24.1 | Clerk opens `/audit` | 403 |
| 24.2 | Boss opens `/audit` | 200 |
| 24.3 | 5 wrong passwords | 15-minute lockout, logged |
| 24.4 | DB dump | Passwords stored only as argon2/bcrypt hashes |

**Count: 97 unit-test rows** across 24 components (rows 6.2, 6.3, 6.6, 7.2 each check 3–5 strings) plus 1 end-to-end test.

## 3. Quality metrics and pass bars
| # | Metric | Pass bar | Evaluation set |
|---|---|---|---|
| 1 | Files missed / duplicated over 1,000 drops | 0 / 0 | Synthetic |
| 2 | Character accuracy on digital Unicode PDFs | ≥99.5% | 50 in-house PDFs |
| 3 | Scanned/digital classification accuracy | ≥99% | 200 mixed pages |
| 4 | OCR CER, printed Hindi | ≤5% words, ≤8% real office scans | [Mozhi-Hindi](https://ilocr.iiit.ac.in/dataset/7/) (CC BY 4.0, word images) + 50 in-house pages |
| 5 | Legacy detection F1 | ≥0.98 | 300 in-house pages (Kruti/DevLys/Chanakya/Unicode/English) |
| 6 | Conversion character accuracy (Kruti, DevLys) | ≥99% | 2,000 in-house word pairs |
| 6b | Chanakya character accuracy | ≥97% (lower bar; see §6) | In-house |
| 7 | Unicode→Kruti→Unicode round-trip exact | ≥99% of words | IndicCorp v2 Hindi sample (via [IndicBERT repo](https://github.com/AI4Bharat/IndicBERT)) |
| 8 | LID accuracy, hin/eng | ≥98% | [Bhasha-Abhijnaanam](https://huggingface.co/datasets/ai4bharat/Bhasha-Abhijnaanam) (CC0) |
| 9 | Header-field extraction exact match | ≥95% | 100 in-house letters |
| 10 | Normalisation idempotence (norm(norm(x)) = norm(x)) | 100% | IndicCorp sample |
| 11–15 | Retrieval recall@3 / MRR@10 (hybrid + rerank) | ≥0.85 / ≥0.70 in-house; report nDCG@10 | [MIRACL hi](https://huggingface.co/datasets/miracl/miracl) (Apache-2.0; [MTEB copy](https://huggingface.co/datasets/mteb/MIRACLRetrieval)) as a sanity check + 100 in-house query→file pairs |
| 12 | Embedding: hybrid beats BM25-only on recall@3 | +5 points | Same |
| 16 | Summary: key facts kept (ref no., date, ask) | ≥95%; human score ≥4/5 | In-house; [XL-Sum hi](https://huggingface.co/datasets/csebuetnlp/xlsum) (CC-BY-NC-SA, eval only) for ROUGE-L, report only |
| 16b | Model Hindi knowledge | Report the score; compare 4B vs 7B | [MILU](https://huggingface.co/datasets/ai4bharat/MILU) (CC-BY-4.0); [IndicGenBench](https://github.com/google-research-datasets/indic-gen-bench) (licence not stated) |
| 17 | Generation speed / time to first token | ≥8 tok/s (4B), ≥4 (7B) / ≤30 s at 4k | `/api/v0` `stats` |
| 18 | JSON-schema valid / lines with a source | 100% / ≥90% | 50 in-house letters |
| 19 | Quotes found verbatim (after normalisation) | ≥95%; every non-verbatim quote flagged (0 missed flags) | Same |
| 20 | Support-check balanced accuracy | ≥0.85 in-house; report on [IndicXNLI](https://github.com/divyanshuaggarwal/IndicXNLI) hi ([HF](https://huggingface.co/datasets/Divyanshu/indicxnli), CC0) | 200 hand-labelled Hindi line/quote pairs |
| 18–20 | Citation recall/precision, ALCE-style | ≥0.80 / ≥0.85 | Method from [ALCE](https://github.com/princeton-nlp/ALCE) (MIT; English data) applied to in-house letters |
| 21 | Format compliance | 100% of required parts in order | 20 templates |
| 22 | Outbound connections in a 24 h soak | 0 | nftables counters / firewall log |
| 23 | Tamper detection on 1,000 random edit/delete/reorder attacks | 100% | Synthetic |
| 24 | Access-control matrix | 100% of cases pass | Role × route list |
| E2E | Time per letter (digital / scanned) | ≤3 min / ≤5 min | 20 in-house letters |

## 4. End-to-end test (letter `L-1`, Kruti Dev PDF)
| Step | Action | Pass criteria |
|---|---|---|
| 1 Ingest | Drop `L-1.pdf` into Inbox | Queued in ≤5 s; type `digital+legacy`; converted text contains "अर्जित अवकाश"; no OCR run |
| 2 Summary | Auto | ≤80 words in Hindi; contains the sender's ref no. and date verbatim; done in ≤30 s |
| 3 Past files | Auto | `F-101` and `R-07` both in the top 3; `E-22` in the top 5; the 200 distractors stay out of the top 3 |
| 4 Cited draft | Clerk clicks Draft (Hindi) | Valid JSON; Hindi template order as in 21.1; ≥90% of lines cite a source; every quote is either `verbatim` or shown flagged; no invented source ids; ≤120 s |
| 5 Edit + Approve | Clerk edits 1 line, presses Approve | The edited line is marked `human_edited` and loses its citation unless re-checked; Approve needs a logged-in clerk |
| 6 Outbox | Auto | Saved to `outbox/` as Unicode text; "Copy as Kruti Dev" gives text that converts back to the approved text exactly (7.3) |
| 7 Log | Boss opens Audit | 6 new entries (ingest, summary, retrieve, draft, approve, outbox), each with user, time (IST), input/output sha256; chain verify `OK` |
| 8 No egress | Run the whole flow with a packet capture on the WAN interface | 0 outbound packets |
| Total | | ≤3 min wall time; app RSS ≤12 GB at peak |

## 5. Public datasets named (all links fetched)
[Mozhi-Hindi](https://ilocr.iiit.ac.in/dataset/7/) (printed OCR, CC BY 4.0) · [Bhasha-Abhijnaanam](https://huggingface.co/datasets/ai4bharat/Bhasha-Abhijnaanam) (LID, CC0) · [MIRACL](https://huggingface.co/datasets/miracl/miracl) hi (retrieval, Apache-2.0) · [MTEB MIRACLRetrieval](https://huggingface.co/datasets/mteb/MIRACLRetrieval) (CC-BY-SA) · [XL-Sum](https://huggingface.co/datasets/csebuetnlp/xlsum) (summaries, CC-BY-NC-SA, eval only) · [MILU](https://huggingface.co/datasets/ai4bharat/MILU) (CC-BY-4.0, gated) · [IndicGenBench](https://github.com/google-research-datasets/indic-gen-bench) (licence not stated) · [IndicXNLI](https://github.com/divyanshuaggarwal/IndicXNLI) (NLI, CC0/MIT) · [ALCE](https://github.com/princeton-nlp/ALCE) (citation method, MIT) · IndicCorp v2 via [IndicBERT](https://github.com/AI4Bharat/IndicBERT) (text corpus for fuzzing).
- **Considered, not used:** [IN22-Gen](https://huggingface.co/datasets/ai4bharat/IN22-Gen) (CC-BY-4.0) and [FLORES+](https://huggingface.co/datasets/openlanguagedata/flores_plus) (CC-BY-SA). Translation isn't in scope; only relevant if we add hi↔en drafting.
- **No public dataset exists** for: Kruti/DevLys/Chanakya conversion, Hindi government-letter retrieval, Hindi citation attribution, official-letter format. These are built in-house (≈2,000 word pairs, 100 query pairs, 200 line/quote pairs, 50 letters).

## 6. UNVERIFIED / caveats
- `/v1/chat/completions` returning `usage` (no doc example). LM Studio's API-token setting was not read in detail.
- Chanakya mappings come from **one** table only (hindi-font-converter `ch.js`). [legacylipi](https://github.com/biswasbiplob/legacylipi)'s "Chanakya" table is Kruti-like (`d`→क), and [lipi](https://github.com/aparsoft/lipi) treats Walkman-Chanakya-905 as Kruti plus overrides. That means **at least two incompatible "Chanakya" encodings exist** and must be detected by font name.
- DevLys is confirmed only through HinLegacy, which encodes it the same as Kruti for every word tested; no real DevLys document was tested.
- HinLegacy bugs found here (Kruti "कार्यालय" decode, Chanakya encode/decode): prefer the `kd.js`/`ch.js` tables, ported, with tests 6.x and 7.x as regression tests.
- The IIIT "Hindi100" page set (`ocr.iiit.ac.in/Hindi100.html`) did not load, so it is UNVERIFIED and not used.
- Every speed and RAM budget is an estimate to measure on the target box. Nothing was benchmarked.
- The 300-day leave figure in the fixtures is fixture text, not a legal claim.
