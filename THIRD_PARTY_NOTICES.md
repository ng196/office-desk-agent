# Third-party notices

This project's own code is MIT (see LICENSE). It depends on the components below, each under its own licence.
They are installed by pip or downloaded at first run; none are vendored in this repo.

## Python packages (requirements.txt)
| Package | Use | Licence |
|---|---|---|
| fastapi | web app | MIT |
| uvicorn[standard] | web server | BSD-3-Clause |
| python-multipart | letter upload form | Apache-2.0 |
| pypdfium2 (PDFium) | PDF text | Apache-2.0 / BSD-3-Clause |
| fastembed | ONNX embedding runtime | Apache-2.0 |
| onnxruntime | reranker on CPU | MIT |
| tokenizers | reranker tokenizer | Apache-2.0 |
| huggingface_hub | one-time model download | Apache-2.0 |
| sqlite-vec | vector search in SQLite | MIT / Apache-2.0 |
| rapidfuzz | fuzzy quote check | MIT |
| requests | drafting API HTTP client | Apache-2.0 |
| numpy | arrays | BSD-3-Clause |
| httpx, pytest, jsonschema (tests only) | tests | BSD-3-Clause, MIT, MIT |

## Models (downloaded at runtime, not in this repo)
| Model | Use | Licence |
|---|---|---|
| intfloat/multilingual-e5-small | embeddings | MIT |
| BAAI/bge-reranker-v2-m3 (ONNX: onnx-community/bge-reranker-v2-m3-ONNX) | reranker | Apache-2.0 |

## Drafting LLM (external service, optional)
Drafts call an OpenAI-compatible API over HTTP (default provider: Groq; also Cerebras or a local LM Studio server).
No provider SDK or model weights are shipped; use of those services is under their own terms.
PyMuPDF (AGPL) is deliberately NOT used.
