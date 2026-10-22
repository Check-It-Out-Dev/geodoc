# geodoc — opisywacz zdjec/map (fusion slice 3): every embedded image gets a
# description composed by the WORKER from the OCR of the image region plus
# harvested captions — one FRESH stateless call per image (owner spec: image
# analysis in fresh conversations, ordered by the chapter detector). There is
# NO VLM in this product (mmproj breaks hybrid slot-save; VLM-never-sole-
# source law) — the describer narrates what OCR and captions PROVE, and the
# elements gate drops anything not present in that evidence.

import json
import os
import re

import llm
from pdfpages import (image_rects, page_count, page_size, render_clip,
                      text_in_rect, text_layer)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOBS = os.path.join(ROOT, "jobs")

MIN_COVERAGE = 0.10        # image area / page area — below this it's an icon


def find_media(pdf_path):
    """Embedded images on TEXT-layer pages: (page, rect, caption). Captions =
    text lines within 70 pt below the image rect. Full-raster pages are NOT
    media here — they already carry image+OCR in rozdzial.md."""
    out = []
    for pno in range(1, page_count(pdf_path) + 1):
        if not text_layer(pdf_path, pno).strip():
            continue                     # raster page - other branch
        w, h = page_size(pdf_path, pno)
        area = (w * h) or 1.0
        for rect in image_rects(pdf_path, pno):
            x0, y0, x1, y1 = rect
            if (x1 - x0) * (y1 - y0) / area < MIN_COVERAGE:
                continue
            cap_zone = [x0, y1, x1, y1 + 70]
            caption = " ".join(
                text_in_rect(pdf_path, pno, cap_zone).split()) or None
            out.append(dict(page=pno,
                            rect=[round(v, 1) for v in rect],
                            caption=caption))
    return out


def _ocr_region(job, pdf_path, page, rect, idx):
    """Render the page once (cache), crop the image region, OCR it."""
    from pdfpages import render_page
    import ocr as ocr_mod
    jdir = os.path.join(JOBS, job)
    png = os.path.join(jdir, "pages", f"page-{page:03d}.png")
    if not os.path.isfile(png):
        os.makedirs(os.path.dirname(png), exist_ok=True)
        render_page(pdf_path, page, png)
    crop = os.path.join(jdir, "pages", f"media-{page:03d}-{idx}.png")
    render_clip(pdf_path, page, rect, crop, dpi=200)
    res = ocr_mod.ocr_page(crop)
    return crop, (res.get("text") or "").strip()


def _fold(s):
    import unicodedata
    s = (s or "").replace("ł", "l").replace("Ł", "L")
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if not unicodedata.combining(c)).casefold()


def ground_elements(opis, evidence):
    """Gate: every declared element must appear (folded substring) in the
    OCR/caption evidence; ungrounded elements dropped, never kept."""
    ev = _fold(evidence)
    kept = [e for e in (opis.get("elementy") or []) if _fold(e) in ev]
    dropped = [e for e in (opis.get("elementy") or []) if _fold(e) not in ev]
    opis["elementy"] = kept
    if dropped:
        opis["elementy_odrzucone"] = dropped
    opis["elementy_ugruntowane"] = not dropped
    return opis


def _default_runner(payload):
    return llm.call_agent("opisywacz_zdjec", payload, max_tokens=500)


def describe_media(job, pdf_path, runner=None):
    """One fresh call per image; writes extracted/media.json and patches each
    chapter's rozdzial.md placeholder section with the description."""
    runner = runner or _default_runner
    media = find_media(pdf_path)
    jdir = os.path.join(JOBS, job)
    chapters_p = os.path.join(jdir, "extracted", "chapters.json")
    chapters = (json.load(open(chapters_p, encoding="utf-8"))["rozdzialy"]
                if os.path.isfile(chapters_p) else [])

    def chapter_of(page):
        return next((c for c in chapters
                     if c["od"] <= page <= c["do"]), None)

    out = []
    for i, m in enumerate(media, 1):
        crop, ocr_text = _ocr_region(job, pdf_path, m["page"], m["rect"], i)
        ch = chapter_of(m["page"])
        payload = (
            f"KONTEKST: obraz osadzony na s. {m['page']}"
            + (f" w rozdziale \"{ch['tytul']}\"" if ch else "") + ".\n"
            + (f"PODPIS POD OBRAZEM: {m['caption']}\n" if m["caption"] else "")
            + f"\n===TEKST-OCR-Z-OBRAZU===\n{ocr_text or '(OCR pusty)'}\n"
              f"===KONIEC===\n\n"
              "ZADANIE: opisz obraz wg kontraktu — tylko to, co dowodzi OCR "
              "i podpis.")
        opis = runner(payload) or {}
        opis = ground_elements(opis, (ocr_text or "") + " "
                               + (m["caption"] or ""))
        opis.update(page=m["page"], caption=m["caption"], plik=os.path.
                    basename(crop), rozdzial=(ch["nr"] if ch else None))
        out.append(opis)
    json.dump(out, open(os.path.join(jdir, "extracted", "media.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=1)
    _patch_chapters(job, chapters, out)
    return out


def _patch_chapters(job, chapters, media):
    """Write the descriptions under the right '## s. N' section of each
    chapter's rozdzial.md (idempotent: a previous OPIS block is replaced)."""
    jdir = os.path.join(JOBS, job)
    rdir = os.path.join(jdir, "rozdzialy")
    if not os.path.isdir(rdir):
        return
    by_page = {}
    for m in media:
        by_page.setdefault(m["page"], []).append(m)
    for folder in os.listdir(rdir):
        fpath = os.path.join(rdir, folder, "rozdzial.md")
        if not os.path.isfile(fpath):
            continue
        text = open(fpath, encoding="utf-8").read()
        text = re.sub(r"\n<!-- OPIS-MEDIA START -->.*?<!-- OPIS-MEDIA END -->",
                      "", text, flags=re.S)
        lines = text.split("\n")
        out_lines = []
        for ln in lines:
            out_lines.append(ln)
            mm = re.match(r"^## s\. (\d+)$", ln.strip())
            if mm and int(mm.group(1)) in by_page:
                blocks = ["", "<!-- OPIS-MEDIA START -->"]
                for m in by_page[int(mm.group(1))]:
                    blocks.append(
                        f"**{m.get('typ', 'obraz').upper()}** "
                        f"([{m['plik']}](../../pages/{m['plik']})): "
                        f"{m.get('opis', '(bez opisu)')}")
                    if m.get("elementy"):
                        blocks.append("Elementy: "
                                      + "; ".join(m["elementy"]))
                blocks.append("<!-- OPIS-MEDIA END -->")
                out_lines += blocks
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("\n".join(out_lines))
