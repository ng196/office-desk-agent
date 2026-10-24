"""Fixed official reply templates (CSMOP style). The LLM only fills body lines; tests.md 21.x."""
import datetime as dt

HI_ORDER = ["पत्र सं.", "भारत सरकार", "दिनांक", "सेवा में", "विषय:", "संदर्भ:", "<body>", "भवदीय"]
EN_ORDER = ["No.", "Government of India", "Dated", "To", "Subject:", "Reference:", "<body>", "Yours faithfully"]

REQUIRED = ["ref_no", "office", "date", "to", "subject", "signatory"]


class TemplateError(Exception):
    pass


def _ordinal(n):
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def format_date(d: dt.date, lang: str) -> str:
    if lang == "hi":
        return d.strftime("%d.%m.%Y")
    return f"{_ordinal(d.day)} {d.strftime('%B')}, {d.year}"


def render(fields: dict, body_lines: list[str], lang: str = "en") -> str:
    missing = [k for k in REQUIRED if not fields.get(k)]
    if missing:
        raise TemplateError(f"missing field(s): {', '.join(missing)}")
    d = fields["date"]
    d = d if isinstance(d, dt.date) else dt.date.fromisoformat(str(d))
    date = format_date(d, lang)
    ref = fields.get("reference") or ("—")
    body = "\n\n".join(body_lines) if body_lines else "—"
    if lang == "hi":
        return (f"पत्र सं. {fields['ref_no']}\n{fields.get('govt', 'भारत सरकार')}\n{fields['office']}\n"
                f"दिनांक: {date}\n\nसेवा में,\n{fields['to']}\n\nविषय: {fields['subject']}\n"
                f"संदर्भ: {ref}\n\nमहोदय/महोदया,\n\n{body}\n\nभवदीय,\n\n{fields['signatory']}")
    return (f"No. {fields['ref_no']}\n{fields.get('govt', 'Government of India')}\n{fields['office']}\n"
            f"Dated: {date}\n\nTo,\n{fields['to']}\n\nSubject: {fields['subject']}\n"
            f"Reference: {ref}\n\nSir/Madam,\n\n{body}\n\nYours faithfully,\n\n{fields['signatory']}")
