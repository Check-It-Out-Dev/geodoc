# geodoc — teksty: the one home for text folding, job-artifact JSON IO and
# page text (audit R3: _fold lived in three modules with drift, ~45 scattered
# json.load(open(...)) sites, TWO 'one truthful page-text sources', and NO
# atomic write anywhere — a crash mid-json.dump corrupted kolejka/meta state
# read live by server threads). Functions and dicts only — house style.

import json
import os
import re
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOBS = os.path.join(ROOT, "jobs")


def fold(s):
    """Diacritic-fold + casefold; ł/Ł handled by hand (never decomposes)."""
    s = (s or "").replace("ł", "l").replace("Ł", "L")
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if not unicodedata.combining(c)).casefold()


def jread(path, default=None):
    """JSON read with a context-managed handle; default on absence.
    Windows seam, reader side (suite caught it live): while jsave's
    os.replace swaps the destination, a concurrent open() can throw a
    TRANSIENT PermissionError — mirror of the writer's retry."""
    import time
    if not os.path.isfile(path):
        return default
    for i in range(20):                    # up to ~100 ms
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except PermissionError:
            time.sleep(0.005)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def jsave(path, obj, indent=1):
    """ATOMIC JSON write: tmp in the same directory + os.replace — a reader
    (server thread, SSE poll) sees the old file or the new file, never a
    torn one; a crash never destroys the previous state. Windows nuance the
    suite caught immediately: os.replace throws WinError 32 while a reader
    briefly holds the destination (CPython open() lacks FILE_SHARE_DELETE)
    — the reader's handle lives milliseconds, so replace retries briefly."""
    import time
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    import threading
    tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=indent)
    for i in range(40):                    # up to ~200 ms
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.005)
    os.replace(tmp, path)                  # final attempt surfaces the error


def artefakt(job, *parts, default=None, jobs_root=None):
    """Job artifact reader: artefakt(job, 'extracted', 'wykaz.json')."""
    return jread(os.path.join(jobs_root or JOBS, job, *parts),
                 default=default)


_MD_DRESSING = re.compile(
    r"^(# strona \d+|!\[.*\]\(.*\)|```.*|transkrypcja ocr.*)$")


def page_text(job, n, jobs_root=None):
    """The one truthful page-text source: transcript md when it carries real
    text, else the page's OCR transcript. Dressing (page header, image links,
    fences, OCR banner, raster flag) is NEVER content."""
    jr = jobs_root or JOBS
    p = os.path.join(jr, job, "transcript", f"page-{n:03d}.md")
    body = ""
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as f:
            body = f.read()
    if not body.strip() or "raster" in body[:200]:
        o = jread(os.path.join(jr, job, "extracted", f"ocr-{n:03d}.json"))
        if o and (o.get("text") or "").strip():
            return o["text"].strip()
    return body


def page_core(text):
    """Content of a page with all transcript dressing stripped — the unit
    the duplicate/blank detector and G13 grounding compare on."""
    out = []
    for ln in (text or "").splitlines():
        s = ln.strip()
        if s and not _MD_DRESSING.match(fold(s)) \
                and "brak warstwy tekstowej" not in fold(s):
            out.append(s)
    return fold("\n".join(out)).strip()
