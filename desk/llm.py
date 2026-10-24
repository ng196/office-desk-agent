"""LM Studio client (OpenAI-compatible, localhost only). Key comes from env LMSTUDIO_API_KEY; never logged."""
import json
import os
import time

import requests

BASE = os.environ.get("LMSTUDIO_URL", "http://localhost:1234")
DEFAULT_MODEL = "qwen3.8-4b-distill"


class LLMError(Exception):
    pass


def api_key():
    key = os.environ.get("LMSTUDIO_API_KEY")
    if not key and os.name == "nt":  # also check the Windows *user* environment (set via setx / System settings)
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                key = winreg.QueryValueEx(k, "LMSTUDIO_API_KEY")[0]
        except OSError:
            key = None
    return key or None


def _headers():
    key = api_key()
    if not key:
        raise LLMError("LMSTUDIO_API_KEY is not set (process or user env). LM Studio returns 401 without it.")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def list_models(timeout=10):
    r = requests.get(f"{BASE}/v1/models", headers=_headers(), timeout=timeout)
    if r.status_code != 200:
        raise LLMError(f"/v1/models returned HTTP {r.status_code}")
    return [m["id"] for m in r.json().get("data", [])]


def chat_json(messages, schema, model=DEFAULT_MODEL, temperature=0.1, max_tokens=1500, timeout=600, extra=None):
    """POST /v1/chat/completions with response_format json_schema. Returns (parsed_json, stats)."""
    body = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens,
            "stream": False,
            "response_format": {"type": "json_schema", "json_schema": {"name": "desk_draft", "strict": True, "schema": schema}}}
    body.update(extra or {})
    t0 = time.perf_counter()
    r = requests.post(f"{BASE}/v1/chat/completions", headers=_headers(), json=body, timeout=timeout)
    wall = time.perf_counter() - t0
    if r.status_code != 200:
        raise LLMError(f"chat/completions returned HTTP {r.status_code}: {r.text[:300]}")
    data = r.json()
    content = data["choices"][0]["message"]["content"]
    usage = data.get("usage") or {}
    out_tok = usage.get("completion_tokens")
    stats = {"model": data.get("model", model), "wall_s": round(wall, 2), "prompt_tokens": usage.get("prompt_tokens"),
             "completion_tokens": out_tok,
             "tokens_per_s_incl_prompt": round(out_tok / wall, 2) if out_tok else None}
    if isinstance(data.get("stats"), dict):  # LM Studio-specific, if present
        stats["lmstudio_stats"] = data["stats"]
    try:
        return json.loads(content), stats
    except json.JSONDecodeError as e:
        raise LLMError(f"model output is not valid JSON: {e}") from e
