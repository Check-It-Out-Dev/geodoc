# geodoc — PDF page operations. FASADA silnika PDF: caly dostep do biblioteki
# PDF zyje w tym pliku (konsumenci importuja funkcje, nigdy silnik) — wymiana
# silnika to wymiana tego modulu. Silnik: pypdfium2/PDFium (Chrome, licencje
# BSD-3/Apache-2.0; zamiana z PyMuPDF/AGPL 06.08 — decyzja licencyjna ownera,
# parnosc dowiedziona arsenalem: mapy 8/8 media, mixed_dpi walker, l2).
#
# Kontrakty fasady (zgodne z poprzednim silnikiem):
# - wszystkie rect-y WCHODZACE i WYCHODZACE sa w ukladzie TOP-LEFT
#   [x0, y0, x1, y1] w punktach PDF (PDFium liczy od dolu — konwersja tutaj);
# - tekst normalizowany do \n (PDFium daje \r\n);
# - PDFium nie jest thread-safe: kazda operacja pod globalnym RLock
#   (serwer renderuje strony na zadanie, gdy nocna kolejka przetwarza).

import ctypes
import functools
import os
import re
import threading

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

MIN_TEXT_CHARS = 40  # below this a page counts as "no usable text layer" (raster)

_LOCK = threading.RLock()


def _norm(t):
    return t.replace("\r\n", "\n").replace("\r", "\n")


def _top(rect_lbrt, page_h):
    """PDFium (left, bottom, right, top) -> [x0, y0, x1, y1] top-left."""
    l, b, r, t = rect_lbrt
    return [l, page_h - t, r, page_h - b]


def page_count(path):
    with _LOCK:
        pdf = pdfium.PdfDocument(path)
        try:
            return len(pdf)
        finally:
            pdf.close()


@functools.lru_cache(maxsize=64)
def _doc_texts(path, mtime):
    """Whole-document text cache (profile-proven: text_layer was called 668x
    for a 122-page job, each call opening the PDF afresh — 0.87 s of pure
    re-opening). One open per document; mtime in the key keeps regenerated
    fixtures correct; 64 docs bound the memory; lru_cache is thread-safe."""
    with _LOCK:
        pdf = pdfium.PdfDocument(path)
        try:
            out = []
            for i in range(len(pdf)):
                page = pdf[i]
                tp = page.get_textpage()
                out.append(_norm(tp.get_text_range()))
                tp.close()
                page.close()
            return tuple(out)
        finally:
            pdf.close()


def text_layer(path, page_no):
    """1-based page number -> extracted text ('' if none)."""
    try:
        mt = os.path.getmtime(path)
    except OSError:
        return ""
    pages = _doc_texts(path, mt)
    return pages[page_no - 1] if 1 <= page_no <= len(pages) else ""


def has_text(path, page_no):
    return len(text_layer(path, page_no).strip()) >= MIN_TEXT_CHARS


def render_page(path, page_no, out_png, dpi=200):
    with _LOCK:
        pdf = pdfium.PdfDocument(path)
        try:
            bmp = pdf[page_no - 1].render(scale=dpi / 72)
            os.makedirs(os.path.dirname(out_png), exist_ok=True)
            bmp.to_pil().save(out_png)
        finally:
            pdf.close()
    return out_png


def render_clip(path, page_no, rect, out_png, dpi=200):
    """Wycinek strony (rect top-left, punkty PDF) -> PNG w zadanym DPI."""
    x0, y0, x1, y1 = rect
    with _LOCK:
        pdf = pdfium.PdfDocument(path)
        try:
            page = pdf[page_no - 1]
            w, h = page.get_size()
            crop = (max(0.0, x0), max(0.0, h - y1),
                    max(0.0, w - x1), max(0.0, y0))
            bmp = page.render(scale=dpi / 72, crop=crop)
            os.makedirs(os.path.dirname(out_png), exist_ok=True)
            bmp.to_pil().save(out_png)
        finally:
            pdf.close()
    return out_png


def page_size(path, page_no):
    with _LOCK:
        pdf = pdfium.PdfDocument(path)
        try:
            return pdf[page_no - 1].get_size()
        finally:
            pdf.close()


def _match_rects(tp, idx, count):
    n = tp.count_rects(idx, count)
    return [tp.get_rect(i) for i in range(n)]


def find_value_boxes(path, page_no, value):
    """Where a VALUE sits on a text-layer page: normalized rects (fractions of
    page width/height) via the PDF's own geometry — the 'dokument pokazuje
    palcem' primitive."""
    with _LOCK:
        pdf = pdfium.PdfDocument(path)
        try:
            page = pdf[page_no - 1]
            W, H = page.get_size()
            tp = page.get_textpage()
            out = []
            searcher = tp.search(str(value), match_case=False)
            while True:
                m = searcher.get_next()
                if m is None:
                    break
                for lbrt in _match_rects(tp, m[0], m[1]):
                    x0, y0, x1, y1 = _top(lbrt, H)
                    out.append([round(x0 / W, 4), round(y0 / H, 4),
                                round(x1 / W, 4), round(y1 / H, 4)])
            return out
        finally:
            pdf.close()


def _image_rects_raw(page):
    """PDFium image placements on the page: list of (l, b, r, t)."""
    return [tuple(obj.get_bounds()) for obj in page.get_objects(
        filter=(pdfium_c.FPDF_PAGEOBJ_IMAGE,), max_depth=4)]


def image_rects(path, page_no):
    """Placement rects (top-left) of embedded raster images on the page."""
    with _LOCK:
        pdf = pdfium.PdfDocument(path)
        try:
            page = pdf[page_no - 1]
            _, H = page.get_size()
            return [_top(r, H) for r in _image_rects_raw(page)]
        finally:
            pdf.close()


def survey(path):
    """Per-page survey: [{page, has_text, chars}] — the ingest phase's map.
    has_text discriminates by text AND geometry (profil-proven fix: 17
    one-line REAL text pages of a 122-page doc were branded raster and
    burned 6 s of needless OCR): a short text layer counts as text when no
    image dominates the page; short text OVER a full-page image is a scan
    with stray chars (digital stamp on a skan) and still goes to OCR."""
    out = []
    with _LOCK:
        pdf = pdfium.PdfDocument(path)
        try:
            for i in range(len(pdf)):
                page = pdf[i]
                tp = page.get_textpage()
                t = _norm(tp.get_text_range())
                chars = len(t.strip())
                if chars >= MIN_TEXT_CHARS:
                    ht = True
                elif chars == 0:
                    ht = False
                else:
                    w, h = page.get_size()
                    area = (w * h) or 1.0
                    cov = sum(max(0.0, (r - l)) * max(0.0, (tt - b))
                              for l, b, r, tt in _image_rects_raw(page)) / area
                    ht = cov < 0.5
                out.append(dict(page=i + 1, chars=chars, has_text=ht))
                tp.close()
                page.close()
            return out
        finally:
            pdf.close()


def image_coverage(path, page_no):
    """Fraction of the page area covered by raster images (0.0-1.0) — the
    photo/map/sketch detector for the document map."""
    with _LOCK:
        pdf = pdfium.PdfDocument(path)
        try:
            page = pdf[page_no - 1]
            w, h = page.get_size()
            area = w * h
            if area <= 0:
                return 0.0
            covered = 0.0
            for l, b, r, t in _image_rects_raw(page):
                il, ib = max(0.0, l), max(0.0, b)
                ir, it = min(w, r), min(h, t)
                if ir > il and it > ib:
                    covered += (ir - il) * (it - ib)
            return min(1.0, covered / area)
        finally:
            pdf.close()


def text_in_rect(path, page_no, rect):
    """Tekst wewnatrz rect-a (top-left, punkty PDF) — strefy podpisow."""
    x0, y0, x1, y1 = rect
    with _LOCK:
        pdf = pdfium.PdfDocument(path)
        try:
            page = pdf[page_no - 1]
            _, H = page.get_size()
            tp = page.get_textpage()
            return _norm(tp.get_text_bounded(
                left=x0, bottom=H - y1, right=x1, top=H - y0))
        finally:
            pdf.close()


def _char_style(tp, lbrt):
    """(size, bold) reprezentatywnego znaku w prostokacie runu; bold po
    NAZWIE fontu — PDFium FontWeight zwraca 0/-1 dla wbudowanych fontow
    (zmierzone na arsenale), nazwa 'X-Bold' jest wiarygodna."""
    l, b, r, t = lbrt
    idx = pdfium_c.FPDFText_GetCharIndexAtPos(
        tp, (l + r) / 2, (b + t) / 2, 3.0, 3.0)
    if idx < 0:
        idx = pdfium_c.FPDFText_GetCharIndexAtPos(tp, l + 1, (b + t) / 2,
                                                  3.0, 3.0)
    if idx < 0:
        return 12.0, False
    size = pdfium_c.FPDFText_GetFontSize(tp, idx) or 12.0
    buf = ctypes.create_string_buffer(96)
    flags = ctypes.c_int()
    pdfium_c.FPDFText_GetFontInfo(tp, idx, buf, 96, ctypes.byref(flags))
    name = buf.value.decode("utf-8", "replace").lower()
    return float(size), ("bold" in name)


def text_lines(path):
    """Per-page linie tekstu dla detektora naglowkow:
    {page: [{text, y0, y1, size, bold}]} (y top-left, rosnie w dol).
    Runy PDFium (count_rects) scalane w linie po nakladaniu pionowym."""
    out = {}
    with _LOCK:
        pdf = pdfium.PdfDocument(path)
        try:
            for i in range(len(pdf)):
                page = pdf[i]
                _, H = page.get_size()
                tp = page.get_textpage()
                runs = []
                n = tp.count_rects(0, -1)
                for k in range(n):
                    lbrt = tp.get_rect(k)
                    txt = _norm(tp.get_text_bounded(
                        left=lbrt[0], bottom=lbrt[1],
                        right=lbrt[2], top=lbrt[3])).strip()
                    if not txt:
                        continue
                    size, bold = _char_style(tp, lbrt)
                    x0, y0, x1, y1 = _top(lbrt, H)
                    runs.append(dict(x0=x0, y0=y0, x1=x1, y1=y1,
                                     text=txt, size=size, bold=bold))
                runs.sort(key=lambda rr: (rr["y0"], rr["x0"]))
                lines = []
                for rr in runs:
                    if lines:
                        ln = lines[-1]
                        overlap = (min(ln["y1"], rr["y1"])
                                   - max(ln["y0"], rr["y0"]))
                        min_h = min(ln["y1"] - ln["y0"], rr["y1"] - rr["y0"])
                        if min_h > 0 and overlap >= 0.5 * min_h:
                            ln["text"] += " " + rr["text"]
                            ln["y0"] = min(ln["y0"], rr["y0"])
                            ln["y1"] = max(ln["y1"], rr["y1"])
                            ln["size"] = max(ln["size"], rr["size"])
                            ln["bold"] = ln["bold"] or rr["bold"]
                            continue
                    lines.append(dict(text=rr["text"], y0=rr["y0"],
                                      y1=rr["y1"], size=rr["size"],
                                      bold=rr["bold"]))
                out[i + 1] = lines
                tp.close()
                page.close()
            return out
        finally:
            pdf.close()


_FOLIO = [  # printed page-number shapes seen in operaty (margins, top or bottom)
    re.compile(r"^\s*(?:-\s*)?(\d{1,4})(?:\s*-)?\s*$"),
    re.compile(r"^\s*str(?:ona)?\.?\s*(\d{1,4})\s*(?:/\s*\d{1,4})?\s*$", re.I),
]


def folio_of_line(line):
    """Folio number if the line IS a printed page number, else None."""
    s = line.strip()
    if not s or len(s) > 24:
        return None
    for rx in _FOLIO:
        m = rx.match(s)
        if m:
            n = int(m.group(1))
            if 1 <= n <= 2000:
                return n
    return None


def printed_page_number(path, page_no):
    """The folio number PRINTED on the page (not the PDF index) — feeds the
    missing-page gap detector. GEOMETRIC rule: a folio lives in the top or
    bottom 12% margin band; body text full of numbers must never match."""
    with _LOCK:
        pdf = pdfium.PdfDocument(path)
        try:
            page = pdf[page_no - 1]
            _, H = page.get_size()
            tp = page.get_textpage()
            n = tp.count_rects(0, -1)
            for k in range(n):
                lbrt = tp.get_rect(k)
                x0, y0, x1, y1 = _top(lbrt, H)
                if y0 > 0.12 * H and y1 < 0.88 * H:
                    continue
                s = _norm(tp.get_text_bounded(
                    left=lbrt[0], bottom=lbrt[1],
                    right=lbrt[2], top=lbrt[3]))
                f = folio_of_line(s)
                if f is not None:
                    return f
            return None
        finally:
            pdf.close()
