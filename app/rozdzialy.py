# geodoc — chapter machinery, CODE layer (recon-grounded 06.08: marker's
# k-means-on-sizes, unstructured's title filter, docling-hierarchical's
# numbering>style>bookmark ladder, ICDAR'13 TOC legality + offset consensus,
# HiPS fuzzy TOC validation, LumberChunker walker shape). Laws carried over:
# code detects, the LLM walker (next layer) only CONFIRMS/REJECTS candidates;
# boundaries monotone; numbering-consistent or TOC-matched heading = HARD
# RE-ANCHOR so a wrong boundary dies at the next anchor. Uniform polarity.

import difflib
import json
import os
import re
import statistics

from pdfpages import page_count as pdf_page_count
from pdfpages import text_layer as pdf_text_layer
from pdfpages import text_lines as pdf_text_lines

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# numbering ladder: arabic outline (1. / 2.3 / 4)), ROZDZIAL N, paragraph
# sign, roman numerals — depth overrides any font-cluster level
NUM_RE = re.compile(
    r"^(?:(\d+(?:\.\d+)*)[.)]?|ROZDZIA[ŁL]\s+(\S+)|§\s*(\d+)|([IVXL]+)\.)\s+\S")


def _num_depth(m):
    if m.group(1):
        return m.group(1).count(".") + 1
    return 1


def _title_ok(t):
    """unstructured's is_possible_title, verbatim logic: short, mostly alpha,
    no trailing comma, not bare number, single sentence."""
    words = t.split()
    if not words or len(words) > 12:
        return False
    alpha = sum(c.isalpha() for c in t)
    if alpha < 0.5 * max(1, len(t.replace(" ", ""))):
        return False
    if t[-1] in ",;" or t.replace(".", "").replace(" ", "").isdigit():
        return False
    return t.count(". ") <= 1


def _cluster_levels(sizes):
    """1-D clustering, marker-style: sort unique sizes desc, new cluster when
    drop exceeds 25%; cluster rank = heading level (k<=4)."""
    levels = {}
    cluster, head = 1, None
    for s in sorted(set(sizes), reverse=True):
        if head is not None and s < 0.75 * head:
            cluster = min(4, cluster + 1)
            head = s
        elif head is None:
            head = s
        levels[s] = cluster
    return levels


def heading_candidates(pdf_path, ocr_boxes=None):
    """Per-page heading candidates. Text-layer pages: span dicts (size, bold,
    caps, numbering, y-gap). Scan pages (no text layer): OCR line boxes via
    ocr_boxes={page: [{text, box=[x0,y0,x1,y1 normalized]}]} — line height
    >=1.15x page median is the font-size proxy (99.67% accurate per
    arxiv 1402.4388), y-gap >=1.8x median leading."""
    out = []
    doc_lines = pdf_text_lines(pdf_path)
    for pno in sorted(doc_lines):
        lines = doc_lines[pno]
        if lines:
            body = statistics.mode(
                round(ln["size"] * 2) / 2 for ln in lines)
            leads = [b["y0"] - a["y1"] for a, b in zip(lines, lines[1:])
                     if b["y0"] > a["y1"]]
            med_lead = statistics.median(leads) if leads else 12.0
            prev_y1 = None
            for ln in lines:
                t = ln["text"]
                gap = (ln["y0"] - prev_y1) if prev_y1 is not None else med_lead
                prev_y1 = ln["y1"]
                if not _title_ok(t):
                    continue
                m = NUM_RE.match(t.upper())
                score = (int(ln["size"] >= 1.15 * body) + int(ln["bold"])
                         + int(t.isupper()) + int(bool(m))
                         + int(gap > 1.8 * med_lead))
                if m or score >= 2:
                    out.append(dict(page=pno, text=t, size=ln["size"],
                                    num=(m.group(0).split()[0] if m else None),
                                    depth=(_num_depth(m) if m else None),
                                    score=score))
        elif ocr_boxes and ocr_boxes.get(pno):
            boxes = ocr_boxes[pno]
            heights = [b["box"][3] - b["box"][1] for b in boxes]
            med_h = statistics.median(heights) if heights else 0.02
            for b in boxes:
                t = (b.get("text") or "").strip()
                h = b["box"][3] - b["box"][1]
                if not t or not _title_ok(t):
                    continue
                # scan law (pageocr stress): HEIGHT is the primary
                # evidence on OCR pages — line fragmentation makes
                # digit-leading fragments ("2 (uwagi)") that pass the
                # numbering regex; numbering refines depth but never
                # creates a candidate alone
                if h < 1.15 * med_h:
                    continue
                m = NUM_RE.match(t.upper())
                out.append(dict(page=pno, text=t, size=round(h, 4),
                                num=(m.group(0).split()[0] if m else None),
                                depth=(_num_depth(m) if m else None),
                                score=2 + int(bool(m))))
    lv = _cluster_levels([c["size"] for c in out] or [12])
    for c in out:
        c["level"] = c["depth"] or lv.get(c["size"], 2)
    return out


def detect_toc(pdf_path, pages_total=None):
    """ICDAR'13-shaped TOC finder: look in the first min(20, N/5)+2 pages for
    a 'SPIS TRESCI' page; entries = lines whose trailing number obeys the
    monotone-nondecreasing legality rule. Validation (TOCs lie — even SOTA
    rules reach best link-F 67.2, ICDAR13 official): constant-offset consensus between declared and
    physical pages, else per-entry fuzzy match downstream."""
    entries = []
    total = pdf_page_count(pdf_path)
    n = pages_total or total
    scan_to = min(total, max(3, min(20, n // 5) + 2))
    for pno in range(scan_to):
        text = pdf_text_layer(pdf_path, pno + 1)
        if not re.search(r"SPIS\s+TRE[SŚ]CI|CONTENTS", text.upper()):
            continue
        last = 0
        for ln in text.splitlines():
            m = re.match(r"^(.*?)[\s.]{3,}(?:str\.\s*)?(\d+)\s*$",
                         ln.strip())
            if not m:
                continue
            title, pg = m.group(1).strip(" ."), int(m.group(2))
            if title and pg >= last:          # monotone legality
                entries.append(dict(tytul=title, strona=pg))
                last = pg
        if entries:
            return dict(strona_spisu=pno + 1, wpisy=entries)
    return None


def _fuzzy(a, b):
    return difflib.SequenceMatcher(None, a.upper(), b.upper()).ratio()


def chapters_assemble(candidates, toc, pages_total, claims=None):
    """Deterministic assembly: level-1 candidates partition the document;
    TOC (when present) cross-validates by fuzzy title match (>=0.8, HiPS).
    Gates (uniform polarity computed by caller): monotone, full cover,
    numbering-gap detection (3. -> 5. = missing chapter FLAG, never an
    invented chapter). Front matter before the first heading = rozdzial 0."""
    tops = [c for c in candidates if c["level"] == 1]
    # dedupe: keep the first candidate per page (a heading page may emit
    # its title twice via caps + numbering)
    seen_pages, uniq = set(), []
    for c in tops:
        if c["page"] not in seen_pages:
            uniq.append(c)
            seen_pages.add(c["page"])
    for c in uniq:
        c["toc_match"] = None
        if toc:
            best = max(toc["wpisy"],
                       key=lambda w: _fuzzy(w["tytul"], c["text"]),
                       default=None)
            if best and _fuzzy(best["tytul"], c["text"]) >= 0.8:
                c["toc_match"] = best
    # walker claims (panel graft: claims-only chain) join as ANCHORED
    # boundaries — code containment already guaranteed a claim page is a
    # candidate page; only high-confidence claims arrive here
    for cl in (claims or []):
        pg = cl.get("nastepny_start")
        if not pg:
            continue
        hit = next((c for c in uniq if c["page"] == pg), None)
        if hit:
            hit["walker"] = True          # claim ANCHORS the code candidate
        else:
            uniq.append(dict(page=pg, text=cl.get("nastepny_tytul") or "?",
                             num=None, toc_match=None, walker=True,
                             size=0, level=1))
    uniq.sort(key=lambda c: c["page"])
    # the SPINE is built from ANCHORED candidates ONLY (numbering, TOC match,
    # or confirmed walker claim). Unanchored candidates NEVER create
    # boundaries anywhere — not as a prefix (krotki: the title page became a
    # fake chapter) and not mid-document (pageocr: tall single-line scan
    # pages became fake chapters after the first anchor). They remain the
    # walker's MENU: a walker confirmation is exactly what anchors them,
    # which is how unnumbered documents still get chapters. Zero anchors ->
    # zero chapters, everything nieoznaczone (abstention-first).
    uniq = [c for c in uniq
            if c.get("num") or c.get("toc_match") or c.get("walker")]
    chapters = []
    for i, c in enumerate(uniq):
        end = (uniq[i + 1]["page"] - 1) if i + 1 < len(uniq) else pages_total
        chapters.append(dict(
            nr=i + 1, tytul=c["text"], od=c["page"], do=end,
            num=c.get("num"), zrodlo=("walker" if c.get("walker") else "kod"),
            spis=(c["toc_match"]["strona"] if c.get("toc_match") else None)))
    braki = []
    nums = [int(c["num"].rstrip(".)")) for c in chapters
            if c.get("num") and c["num"].rstrip(".)").isdigit()]
    for a, b in zip(nums, nums[1:]):
        if b > a + 1:
            braki.append(f"numeracja skacze {a} -> {b}: brak rozdzialu "
                         f"{a + 1}" + ("" if b == a + 2 else f"..{b - 1}"))
    front = chapters[0]["od"] - 1 if chapters else 0
    covered = set()
    for c in chapters:
        covered.update(range(c["od"], c["do"] + 1))
    covered.update(range(1, front + 1))
    nieoznaczone = []
    run = None
    for n in range(1, pages_total + 1):
        if n not in covered:
            run = [n, n] if run is None else [run[0], n]
        elif run:
            nieoznaczone.append(run)
            run = None
    if run:
        nieoznaczone.append(run)
    overlap = sum(c["do"] - c["od"] + 1 for c in chapters) + front \
        + sum(b - a + 1 for a, b in nieoznaczone) != pages_total
    # TOC-drift validation (TOCs lie — ICDAR13 official: best link-F 67.2, complete entries 43.6):
    # declared vs actual start per matched chapter; uniform drift = stale
    # spis (recoverable knowledge), mixed drift = spis niewiarygodny
    drifts = [c["od"] - c["spis"] for c in chapters if c.get("spis")]
    spis_zgodny = None
    przesuniecie = None
    if drifts:
        spis_zgodny = all(d == 0 for d in drifts)
        if not spis_zgodny and len(set(drifts)) == 1:
            przesuniecie = drifts[0]          # stale-but-consistent
    return dict(
        rozdzialy=chapters,
        strony_wstepne=front,
        nieoznaczone=nieoznaczone,
        braki_numeracji=braki,
        spis_zgodny=spis_zgodny,
        spis_przesuniecie=przesuniecie,
        # G11 tiling referee: front + chapters + nieoznaczone partition
        # 1..N exactly, no overlaps (uniform polarity: true = good)
        podzial_kompletny=not overlap,
        pokrycie_ciagle=bool(chapters) and all(
            chapters[i + 1]["od"] == chapters[i]["do"] + 1
            for i in range(len(chapters) - 1)),
        do_konca=bool(chapters) and chapters[-1]["do"] == pages_total)


def stage_rozdzialy(pdf_path, ocr_boxes=None, claims=None):
    """One-call code layer: candidates -> TOC -> assembly + gates."""
    total = pdf_page_count(pdf_path)
    cands = heading_candidates(pdf_path, ocr_boxes=ocr_boxes)
    toc = detect_toc(pdf_path, total)
    out = chapters_assemble(cands, toc, total, claims=claims)
    out["spis_tresci"] = toc
    out["kandydaci"] = len(cands)
    return out


def page_text_job(job, n, jobs_root=None):
    """The one truthful page-text source for the chapter machinery (mirrors
    agents._page_text): transcript md when it carries text, else the page's
    OCR transcript — scan documents walk and summarize through OCR."""
    jr = jobs_root or os.path.join(ROOT, "jobs")
    p = os.path.join(jr, job, "transcript", f"page-{n:03d}.md")
    body = open(p, encoding="utf-8").read() if os.path.isfile(p) else ""
    if body.strip() and "raster" not in body[:200]:
        return body
    op = os.path.join(jr, job, "extracted", f"ocr-{n:03d}.json")
    if os.path.isfile(op):
        o = json.load(open(op, encoding="utf-8"))
        return (o.get("text") or "").strip() or body
    return body


def ocr_all_raster(job, pdf_path, jobs_root=None):
    """Scan branch: OCR every page without a text layer into ocr-NNN.json
    (idempotent — existing files are kept; the crew path writes the same
    shape). Returns the page->lines map for heading candidates."""
    from pdfpages import render_page, text_layer
    import ocr as ocr_mod
    jr = jobs_root or os.path.join(ROOT, "jobs")
    jdir = os.path.join(jr, job)
    boxes = {}
    total = pdf_page_count(pdf_path)
    for n in range(1, total + 1):
        if text_layer(pdf_path, n).strip():
            continue
        op = os.path.join(jdir, "extracted", f"ocr-{n:03d}.json")
        if not os.path.isfile(op):
            png = os.path.join(jdir, "pages", f"page-{n:03d}.png")
            if not os.path.isfile(png):
                os.makedirs(os.path.dirname(png), exist_ok=True)
                render_page(pdf_path, n, png)
            res = ocr_mod.ocr_page(png)
            os.makedirs(os.path.dirname(op), exist_ok=True)
            json.dump(res, open(op, "w", encoding="utf-8"),
                      ensure_ascii=False)
        o = json.load(open(op, encoding="utf-8"))
        if o.get("lines"):
            boxes[n] = o["lines"]
    return boxes


def _fold(s):
    import unicodedata
    s = s.replace("ł", "l").replace("Ł", "L")
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if not unicodedata.combining(c)).casefold()


def _slug(t, maxlen=40):
    s = re.sub(r"[^a-z0-9]+", "-", _fold(t)).strip("-")
    return (s[:maxlen].rstrip("-")) or "rozdzial"


def page_pathologies(transcripts):
    """Scanner pathologies from text evidence: PUSTE (blank) pages and
    DUBLETY (double-feed: consecutive pages with identical folded text).
    A duplicate of a heading page must never anchor a phantom chapter —
    arsenal fixture operat_puste_dublety caught exactly that."""
    def _core(t):
        # page CORE: transcript minus page-specific dressing — the
        # '# Strona N' header, raster-flag boilerplate with its page-numbered
        # image link, and code fences; what remains is the page's content
        out = []
        for ln in t.splitlines():
            s = ln.strip()
            if (re.match(r"^# strona \d+$", _fold(s))
                    or "brak warstwy tekstowej" in _fold(s)
                    or _fold(s).startswith("transkrypcja ocr")
                    or s.startswith("```")
                    or re.match(r"^!\[.*\]\(.*\)$", s)):
                continue
            out.append(s)
        return _fold("\n".join(out)).strip()

    puste, dublety = [], []
    prev_n, prev_txt = None, None
    for n in sorted(transcripts):
        txt = _core(transcripts[n])
        if not txt:
            puste.append(n)
            continue
        if prev_txt is not None and txt == prev_txt:
            dublety.append([n, prev_n])
        prev_n, prev_txt = n, txt
    return dict(puste=puste, dublety=dublety)


def guard_titles(chapters_doc, transcripts):
    """G12 grounding: a chapter's declared title must appear (diacritic-folded)
    in the transcript of its FIRST page; failures are demoted to nieoznaczone
    (abstention-first) and flagged — never silently kept green."""
    ok, demoted = [], []
    for c in chapters_doc["rozdzialy"]:
        first = _fold(transcripts.get(c["od"], ""))
        if _fold(c["tytul"]) in first:
            ok.append(c)
        else:
            demoted.append(c)
            chapters_doc["nieoznaczone"].append([c["od"], c["do"]])
    chapters_doc["rozdzialy"] = [dict(c, nr=i + 1) for i, c in enumerate(ok)]
    chapters_doc["nieoznaczone"].sort()
    chapters_doc["tytuly_ugruntowane"] = not demoted
    if demoted:
        chapters_doc["g12_zdegradowane"] = [
            dict(tytul=c["tytul"], od=c["od"], do=c["do"]) for c in demoted]
    return chapters_doc


def materialize(job, chapters_doc, jobs_root=None):
    """Pure-code materialization (panel graft from model C): chapter folders
    + rozdzial.md assembled from IMMUTABLE page transcripts (no second
    transcription), per-page sha256 provenance recorded, master.md with a
    linked TOC. Media pages get placeholder image links — image analysis
    fills descriptions later in fresh contexts."""
    import hashlib
    jr = jobs_root or os.path.join(ROOT, "jobs")
    jdir = os.path.join(jr, job)
    tdir = os.path.join(jdir, "transcript")
    rdir = os.path.join(jdir, "rozdzialy")
    os.makedirs(rdir, exist_ok=True)

    def _raw_md(n):
        p = os.path.join(tdir, f"page-{n:03d}.md")
        return open(p, encoding="utf-8").read() if os.path.isfile(p) else ""

    prov = {}
    toc_lines = []
    for c in chapters_doc["rozdzialy"]:
        folder = f"{c['nr']:02d}-{_slug(c['tytul'])}"
        cdir = os.path.join(rdir, folder)
        os.makedirs(cdir, exist_ok=True)
        parts = [f"# {c['tytul']}", "",
                 f"Strony operatu: {c['od']}–{c['do']} · zrodlo granic: "
                 f"{c['zrodlo']}" + (f" · spis tresci: s. {c['spis']}"
                                     if c.get("spis") else ""), ""]
        for n in range(c["od"], c["do"] + 1):
            raw = _raw_md(n)
            txt = page_text_job(job, n, jobs_root=jr)
            prov[str(n)] = hashlib.sha256(txt.encode("utf-8")).hexdigest()[:16]
            parts.append(f"## s. {n}")
            if "raster" in raw[:200] or not raw.strip():
                # scan page: keep the image reference AND its OCR text
                parts.append(f"![strona {n}](../../pages/page-{n:03d}.png)")
                parts.append("<!-- OPIS OBRAZU: uzupelnia analiza obrazu "
                             "w swiezym kontekscie -->")
            parts.append(txt.strip() or "(strona bez warstwy tekstowej)")
            parts.append("")
        with open(os.path.join(cdir, "rozdzial.md"), "w",
                  encoding="utf-8") as f:
            f.write("\n".join(parts))
        toc_lines.append(
            f"{c['nr']}. [{c['tytul']}]({folder}/rozdzial.md) — "
            f"s. {c['od']}–{c['do']}")
    master = ["# Mapa rozdzialow", ""]
    if chapters_doc.get("strony_wstepne"):
        master.append(f"Strony wstepne: 1–{chapters_doc['strony_wstepne']}")
    master += ["", *toc_lines, ""]
    for a, b in chapters_doc.get("nieoznaczone") or []:
        master.append(f"- NIEOZNACZONE: s. {a}–{b} (do decyzji operatora)")
    for br in chapters_doc.get("braki_numeracji") or []:
        master.append(f"- UWAGA: {br}")
    with open(os.path.join(rdir, "master.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(master) + "\n")
    chapters_doc["prowieniencja_stron"] = prov
    json.dump(chapters_doc, open(os.path.join(jdir, "extracted",
                                              "chapters.json"), "w",
                                 encoding="utf-8"),
              ensure_ascii=False, indent=1)
    return chapters_doc


def rozdzialy_job(job, pdf_path, claims=None, jobs_root=None):
    """Phase-A orchestrator (code side): detect -> assemble (+walker claims)
    -> G12 vs transcripts -> materialize folders/master -> docmap update."""
    jr = jobs_root or os.path.join(ROOT, "jobs")
    jdir = os.path.join(jr, job)
    ocr_boxes = ocr_all_raster(job, pdf_path, jobs_root=jr)
    doc = stage_rozdzialy(pdf_path, ocr_boxes=ocr_boxes or None,
                          claims=claims)
    total = pdf_page_count(pdf_path)
    transcripts = {n: page_text_job(job, n, jobs_root=jr)
                   for n in range(1, total + 1)}
    pat = page_pathologies(transcripts)
    if pat["dublety"]:
        # a duplicated page never anchors: re-assemble without candidates
        # standing on duplicate pages (the original page keeps its anchor)
        dup_pages = {d[0] for d in pat["dublety"]}
        cands = [c for c in heading_candidates(
            pdf_path, ocr_boxes=ocr_boxes or None)
            if c["page"] not in dup_pages]
        doc = chapters_assemble(cands, doc.get("spis_tresci"), total,
                                claims=claims)
        doc["spis_tresci"] = detect_toc(pdf_path, total)
        doc["kandydaci"] = len(cands)
    doc["patologie_stron"] = pat
    doc = guard_titles(doc, transcripts)
    doc = materialize(job, doc, jobs_root=jr)
    dm_path = os.path.join(jdir, "docmap.json")
    if os.path.isfile(dm_path):
        dm = json.load(open(dm_path, encoding="utf-8"))
        dm["chapters"] = dict(
            rozdzialy=doc["rozdzialy"], nieoznaczone=doc["nieoznaczone"],
            braki_numeracji=doc["braki_numeracji"])
        json.dump(dm, open(dm_path, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    return doc
