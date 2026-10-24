"""SQLite archive index: chunks + FTS5 keyword index + sqlite-vec vectors."""
import hashlib
import json
import sqlite3
import struct
from pathlib import Path

from .embed import DIM
from .extract import chunk_page, extract_pages, section_chunks, ExtractError
from .normalize import tokens

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS docs(id INTEGER PRIMARY KEY, file TEXT UNIQUE, sha256 TEXT, pages INTEGER, doc_type TEXT);
CREATE TABLE IF NOT EXISTS chunks(id INTEGER PRIMARY KEY, doc_id INTEGER REFERENCES docs(id),
  file TEXT, page INTEGER, text TEXT, heading TEXT DEFAULT '');
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(terms, tokenize="porter unicode61 remove_diacritics 0 categories 'L* N* Co M*'");
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec USING vec0(embedding float[{DIM}]);
"""


def connect(db_path) -> sqlite3.Connection:
    import sqlite_vec
    con = sqlite3.connect(str(db_path))
    con.enable_load_extension(True)
    sqlite_vec.load(con)
    con.enable_load_extension(False)
    con.executescript(SCHEMA)
    if "doc_type" not in [r[1] for r in con.execute("PRAGMA table_info(docs)")]:  # older index.db
        con.execute("ALTER TABLE docs ADD COLUMN doc_type TEXT")
        con.commit()
    if "heading" not in [r[1] for r in con.execute("PRAGMA table_info(chunks)")]:
        con.execute("ALTER TABLE chunks ADD COLUMN heading TEXT DEFAULT ''")
        con.commit()
    return con


DOC_TYPES_FILE = Path(__file__).with_name("doc_types.json")
ROOT_SAMPLES = Path(__file__).resolve().parent.parent / "samples"
DOC_TYPES = ("rule", "case", "reference")  # reference: indexed, never in the rules/cases lists
# chunking per type; part of the stored digest so a change of chunker or tag re-indexes the file
CHUNKER = {"rule": "section-v2", "case": "para-v1", "reference": "para-v1"}
DEFAULT_TYPE = "case"


def load_doc_types(path=DOC_TYPES_FILE) -> dict:
    """Explicit file -> 'rule' | 'case' table (desk/doc_types.json)."""
    t = {k: v for k, v in json.loads(Path(path).read_text(encoding="utf-8")).items() if not k.startswith("_")}
    bad = {k: v for k, v in t.items() if v not in DOC_TYPES}
    if bad:
        raise ValueError(f"doc_types.json: unknown type(s) {bad}")
    return t


def heading_kind(name, path=DOC_TYPES_FILE) -> str:
    """Word for bare heading numbers in a rule file's section labels ('Rule 65', 'Section 7'); from doc_types.json."""
    return json.loads(Path(path).read_text(encoding="utf-8")).get("_heading_kind", {}).get(name, "")


def load_page_types(path=DOC_TYPES_FILE) -> dict:
    """Explicit page ranges inside a file that override its file-level type, e.g. the forms, annexures and
    sample letters at the back of a rule book are 'case'. {file: [(first, last, type), ...]} (pages 1-based, inclusive)."""
    raw = json.loads(Path(path).read_text(encoding="utf-8")).get("_page_types", {})
    out = {}
    for name, by_type in raw.items():
        if name.startswith("_"):
            continue
        for t, ranges in by_type.items():
            if t not in DOC_TYPES:
                raise ValueError(f"doc_types.json _page_types: unknown type {t!r} for {name}")
            for r in ranges:
                a, b = (r, r) if isinstance(r, int) else r
                out.setdefault(name, []).append((int(a), int(b), t))
    return out


def page_type(name, page, file_type=None, pages=None) -> str:
    """Type of one page: the _page_types range it falls in, else the file's type."""
    pages = load_page_types() if pages is None else pages
    for a, b, t in pages.get(name, ()):
        if a <= page <= b:
            return t
    return doc_type_of(name) if file_type is None else file_type


def chunk_types(con, pages=None) -> dict:
    """chunk id -> 'rule' | 'case' | 'reference' (file type from docs, page ranges from _page_types)."""
    pages = load_page_types() if pages is None else pages
    return {cid: page_type(f, pg, t, pages) for cid, f, pg, t in
            con.execute("SELECT c.id, c.file, c.page, d.doc_type FROM chunks c JOIN docs d ON d.id=c.doc_id")}


def doc_type_of(name, table=None) -> str:
    table = load_doc_types() if table is None else table
    return table.get(name, DEFAULT_TYPE)


def retag(con, table=None, log=None) -> int:
    """Apply the table to docs already in the DB (no re-embedding). Returns rows changed."""
    table = load_doc_types() if table is None else table
    n = 0
    for (name, cur) in con.execute("SELECT file, doc_type FROM docs").fetchall():
        t = table.get(name)
        if t is None and log:
            log(f"warning: {name} not in doc_types.json, tagged '{DEFAULT_TYPE}'")
        t = t or DEFAULT_TYPE
        if t != cur:
            con.execute("UPDATE docs SET doc_type=? WHERE file=?", (t, name))
            n += 1
    con.commit()
    return n


def pack(vec) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def fts_terms(text: str) -> str:
    """What FTS5 indexes: our normalised+stemmed tokens joined by spaces."""
    return " ".join(tokens(text))


def with_heading(text, heading) -> str:
    """What embedding / FTS / rerank see. chunks.text stays the raw page text (the only quotable text)."""
    return f"{heading} — {text}" if heading else text


def add_document(con, embedder, path, name=None, pages=None, min_page_chars=30, doc_type=None) -> int:
    """Index one file (or given [(page, text)] pages). Re-indexing the same name replaces it. Returns chunk count."""
    name = name or Path(path).name
    digest = sha256(path) if path and Path(path).exists() else hashlib.sha256(repr(pages).encode()).hexdigest()
    row = con.execute("SELECT id, sha256 FROM docs WHERE file=?", (name,)).fetchone()
    doc_type = doc_type or doc_type_of(name)
    if doc_type not in DOC_TYPES:
        raise ValueError(f"doc_type must be one of {DOC_TYPES}")
    digest = f"{digest}:{CHUNKER[doc_type]}"
    if row and row[1] == digest:
        con.execute("UPDATE docs SET doc_type=? WHERE id=?", (doc_type, row[0]))
        con.commit()
        return 0
    if row:
        delete_document(con, name)
    pages = pages if pages is not None else extract_pages(path)
    n_pages = len(pages)
    pages = [(pg, txt) for pg, txt in pages if len(txt.strip()) >= min_page_chars]
    if doc_type == "rule":
        items = section_chunks(pages, kind=heading_kind(name))
    else:
        items = [(pg, c, "") for pg, txt in pages for c in chunk_page(txt)]
    cur = con.execute("INSERT INTO docs(file, sha256, pages, doc_type) VALUES(?,?,?,?)", (name, digest, n_pages, doc_type))
    doc_id = cur.lastrowid
    vecs = embedder.passages([with_heading(c, h) for _, c, h in items]) if items else []
    for (pg, c, h), v in zip(items, vecs):
        cid = con.execute("INSERT INTO chunks(doc_id, file, page, text, heading) VALUES(?,?,?,?,?)", (doc_id, name, pg, c, h)).lastrowid
        con.execute("INSERT INTO chunks_fts(rowid, terms) VALUES(?,?)", (cid, fts_terms(with_heading(c, h))))
        con.execute("INSERT INTO chunks_vec(rowid, embedding) VALUES(?,?)", (cid, pack(v)))
    con.commit()
    return len(items)


def delete_document(con, name):
    ids = [r[0] for r in con.execute("SELECT c.id FROM chunks c JOIN docs d ON d.id=c.doc_id WHERE d.file=?", (name,))]
    for cid in ids:
        con.execute("DELETE FROM chunks_fts WHERE rowid=?", (cid,))
        con.execute("DELETE FROM chunks_vec WHERE rowid=?", (cid,))
        con.execute("DELETE FROM chunks WHERE id=?", (cid,))
    con.execute("DELETE FROM docs WHERE file=?", (name,))
    con.commit()


# Files in samples/ that are legacy-font (Kruti Dev/Chanakya) or have a garbled/scanned text layer
# (see samples/INDEX.md). They need the later Kruti Dev / OCR layers, so the core skips them.
SKIP_SAMPLES = {
    "gazette_india_2026_272395.pdf", "gazette_india_2025_263348.pdf", "gazette_india_2018_184457.pdf",
    "godl_gazette_2017.pdf", "raj_pwd_tender_140.pdf", "raj_pwd_tender_38.pdf",
    "rajbhasha_unicode_circular_2017.pdf", "csmop_2022_hi.pdf", "prashasnik_shabdavali_en_hi.pdf",
}


def index_folder(con, embedder, folder, skip=SKIP_SAMPLES, log=print):
    total = 0
    for p in sorted(Path(folder).iterdir()):
        if p.suffix.lower() not in (".pdf", ".txt") or p.name in skip or p.name.upper() == "INDEX.MD":
            continue
        try:
            n = add_document(con, embedder, p)
            total += n
            log(f"indexed {p.name}: {n} chunks" if n else f"unchanged {p.name}")
        except ExtractError as e:
            log(f"skipped {p.name}: {e}")
    retag(con, log=log)
    return total
