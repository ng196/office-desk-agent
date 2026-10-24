"""Grounded draft: retrieved chunks -> LLM (json_schema) -> verified lines -> fixed template."""
import datetime as dt

from . import llm
from .template import render
from .verify import verify_lines

LINE_SCHEMA = {
    "type": "object",
    "properties": {
        "sentence": {"type": "string"},
        "source_file": {"type": ["string", "null"]},
        "page": {"type": ["integer", "null"]},
        "verbatim_quote": {"type": ["string", "null"]},
    },
    "required": ["sentence", "source_file", "page", "verbatim_quote"],
    "additionalProperties": False,
}
SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "subject": {"type": "string"},
        "lines": {"type": "array", "minItems": 1, "maxItems": 8, "items": LINE_SCHEMA},
    },
    "required": ["summary", "subject", "lines"],
    "additionalProperties": False,
}

SYSTEM = {
    "en": ("You draft the BODY of an official Government of India reply letter. Use ONLY the numbered sources. "
           "For every sentence give source_file and page exactly as shown in the source header, and verbatim_quote: "
           "a short phrase copied character-for-character from that source that supports the sentence. "
           "Cite rule/section numbers only as they appear in the source text. If no source supports a sentence, "
           "set source_file, page and verbatim_quote to null. Do not write the address, salutation or signature. "
           "summary: at most 60 words summarising the incoming letter, in English."),
    "hi": ("आप सरकारी उत्तर पत्र का केवल मुख्य भाग (body) हिन्दी में लिखते हैं। केवल दिए गए स्रोतों का उपयोग करें। "
           "हर वाक्य के लिए source_file और page ठीक वैसे ही दें जैसे स्रोत शीर्षक में है, और verbatim_quote में स्रोत से "
           "अक्षरशः कॉपी किया गया छोटा अंश दें (स्रोत अंग्रेज़ी में हो तो उद्धरण अंग्रेज़ी में ही रहे)। नियम/धारा संख्या वही लिखें जो स्रोत में है। "
           "कोई स्रोत न हो तो source_file, page, verbatim_quote को null रखें। पता, संबोधन या हस्ताक्षर न लिखें। "
           "summary: आने वाले पत्र का अधिकतम 60 शब्दों में हिन्दी सारांश।"),
}


def as_lists(hits):
    """hits: {"rules": [...], "cases": [...]} (or a plain list, treated as one untyped list)."""
    return hits if isinstance(hits, dict) else {"sources": hits}


def flat(hits):
    return [h for lst in as_lists(hits).values() for h in lst]


def build_messages(letter_text, hits, lang):
    titles = {"rules": "RULES (Acts, Rules, manuals, circulars)", "cases": "PAST CASES (orders, letters, judgments)", "sources": "SOURCES"}
    parts, i = [], 0
    for key, lst in as_lists(hits).items():
        if not lst:
            continue
        block = []
        for h in lst:
            i += 1
            block.append(f"[{i}] source_file: {h['file']} | page: {h['page']}\n{h['text']}")
        parts.append(f"{titles.get(key, key.upper())}:\n" + "\n\n".join(block))
    src = "\n\n".join(parts)
    user = (f"INCOMING LETTER:\n{letter_text[:4000]}\n\n{src}\n\n"
            "Write 3-6 body sentences for the reply. Cite the rule that applies from RULES; use PAST CASES as precedent.")
    return [{"role": "system", "content": SYSTEM[lang]}, {"role": "user", "content": user}]


def make_draft(letter_text, hits, archive, lang="en", fields=None, model=llm.DEFAULT_MODEL, chat=llm.chat_json, **kw):
    """archive: {file: [(page, text)]} used for quote checking. `chat` is injectable for tests."""
    data, stats = chat(build_messages(letter_text, hits, lang), SCHEMA, model=model, **kw)
    retrieved = {h["file"] for h in flat(hits)}
    lines = verify_lines(data["lines"], archive)
    for ln in lines:
        if ln.get("source_file") and ln["source_file"] not in retrieved:
            ln["status"], ln["verified"] = "FLAG not_in_retrieved", False
    f = {"ref_no": "____", "office": "____", "to": "____", "signatory": "____", "date": dt.date.today(),
         "subject": data.get("subject") or "____", **(fields or {})}
    body = [ln["sentence"] + ("" if ln["verified"] else " [UNVERIFIED]") for ln in lines]
    return {"summary": data.get("summary", ""), "subject": f["subject"], "lines": lines,
            "letter": render(f, body, lang), "llm_stats": stats,
            "verified_pct": round(100 * sum(l["verified"] for l in lines) / len(lines), 1) if lines else 0.0}
