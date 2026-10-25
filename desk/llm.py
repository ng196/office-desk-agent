"""Drafting LLM client (OpenAI-compatible chat/completions). Keys are never printed, logged or stored.

Default (development): Cerebras, settings from the repo-root .env (git-ignored):
  CEREBRAS_API_KEY, CEREBRAS_BASE_URL (https://api.cerebras.ai/v1), DESK_LLM_MODEL (qwen-3.8-27b).
LM Studio is off unless DESK_LLM_PROVIDER=lmstudio (key LMSTUDIO_API_KEY, URL LMSTUDIO_URL)."""
import json
import os
import re
import time
from pathlib import Path

import requests

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def load_env(path=ENV_FILE):
    """Minimal .env reader (KEY=VALUE, # comments). Fills only variables not already set; values stay in this process."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and v and not os.environ.get(k):
            os.environ[k] = v


load_env()
PROVIDER = os.environ.get("DESK_LLM_PROVIDER", "cerebras").lower()
if PROVIDER == "lmstudio":
    BASE = os.environ.get("LMSTUDIO_URL", "http://localhost:1234").rstrip("/") + "/v1"
    KEY_VAR = "LMSTUDIO_API_KEY"
    DEFAULT_MODEL = os.environ.get("DESK_LLM_MODEL", "qwen3.8-4b-distill")
else:
    BASE = os.environ.get("CEREBRAS_BASE_URL", "https://api.cerebras.ai/v1").rstrip("/")
    KEY_VAR = "CEREBRAS_API_KEY"
    DEFAULT_MODEL = os.environ.get("DESK_LLM_MODEL", "qwen-3.8-27b")


class LLMError(Exception):
    pass


def api_key():
    key = os.environ.get(KEY_VAR)
    if not key and PROVIDER == "lmstudio" and os.name == "nt":  # Windows *user* env (setx)
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                key = winreg.QueryValueEx(k, KEY_VAR)[0]
        except OSError:
            key = None
    return key or None


def _headers():
    key = api_key()
    if not key:
        raise LLMError(f"{KEY_VAR} is not set (.env or environment).")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def list_models(timeout=20):
    r = requests.get(f"{BASE}/models", headers=_headers(), timeout=timeout)
    if r.status_code != 200:
        raise LLMError(f"/models returned HTTP {r.status_code}")
    return [m["id"] for m in r.json().get("data", [])]


_THINK = re.compile(r"<think>.*?</think>", re.S)


def parse_json(content):
    """Model text -> JSON object: drops <think> blocks and ``` fences, then takes the outermost {...}."""
    s = _THINK.sub("", content or "").strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s).strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        i, j = s.find("{"), s.rfind("}")
        if i >= 0 and j > i:
            return json.loads(s[i:j + 1])
        raise


def _fallback_messages(messages, schema):
    """Strict-JSON prompt for servers that reject response_format json_schema."""
    rule = ("\n\nReply with ONE JSON object only, no prose, no code fences, matching this JSON Schema exactly:\n"
            + json.dumps(schema, ensure_ascii=False))
    out = [dict(m) for m in messages]
    out[0]["content"] = out[0]["content"] + rule
    return out


def _post(body, timeout):
    t0 = time.perf_counter()
    r = requests.post(f"{BASE}/chat/completions", headers=_headers(), json=body, timeout=timeout)
    return r, time.perf_counter() - t0


def chat_json(messages, schema, model=None, temperature=0.1, max_tokens=4000, timeout=600, extra=None):
    """POST chat/completions with response_format json_schema; if the server rejects json_schema (HTTP 400/422),
    retry once with a strict JSON prompt and parse. Returns (parsed_json, stats)."""
    model = model or DEFAULT_MODEL
    body = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens, "stream": False,
            "response_format": {"type": "json_schema", "json_schema": {"name": "desk_draft", "strict": True, "schema": schema}}}
    body.update(extra or {})
    r, wall = _post(body, timeout)
    fallback = False
    if r.status_code in (400, 422) and re.search(r"response_format|json_schema|schema", r.text, re.I):
        fallback = True
        body = {k: v for k, v in body.items() if k != "response_format"}
        body["messages"] = _fallback_messages(messages, schema)
        r, wall = _post(body, timeout)
    if r.status_code != 200:
        raise LLMError(f"chat/completions returned HTTP {r.status_code}: {r.text[:300]}")
    data = r.json()
    content = data["choices"][0]["message"].get("content")
    usage = data.get("usage") or {}
    out_tok = usage.get("completion_tokens")
    ti = data.get("time_info") or {}
    stats = {"provider": PROVIDER, "model": data.get("model", model), "wall_s": round(wall, 2),
             "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": out_tok,
             "tokens_per_s_incl_prompt": round(out_tok / wall, 2) if out_tok else None,
             "json_schema_fallback": fallback}
    if out_tok and ti.get("completion_time"):  # Cerebras server-side generation time
        stats["tokens_per_s_generation"] = round(out_tok / ti["completion_time"], 1)
    if isinstance(data.get("stats"), dict):  # LM Studio-specific, if present
        stats["lmstudio_stats"] = data["stats"]
    try:
        return parse_json(content), stats
    except (json.JSONDecodeError, TypeError) as e:
        raise LLMError(f"model output is not valid JSON: {e}") from e
