# geodoc — the fixed pipeline over one operat PDF. Deterministic orchestration;
# models live INSIDE stages (v1: the wykaz parser is code over the text layer —
# the model extractor plugs into the same contract later). MEASURED LAW baked in:
# the model transcribes, CODE aggregates — sums, areas and counts never pass
# through generation.
#
# jobs/<job>/
#   source/operat.pdf
#   pages/page-00N.png            (raster pages only, v1)
#   transcript/page-00N.md        (text or raster-flag + image reference)
#   extracted/{header,wykaz}.json
#   checks/invariants.json
#   out/przeglad.csv  out/wgranie_<dzialka>.csv
#   tasks/log.jsonl

import csv
import hashlib
import json
import os
import re
import time

import teksty
from pdfpages import (survey, text_layer, render_page, image_coverage,
                      printed_page_number, folio_of_line)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOBS = os.path.join(ROOT, "jobs")

# PL-2000 sanity ranges: Y easting = zone*1e6 + 500000 +/- ~210 km (EPSG
# 2176-2179); X northing for Poland ~5.30-6.13M (verified against spatial
# reference + sample rows in the dossier research)
ZONE_Y = {z: (int(z) * 1_000_000 + 290_000, int(z) * 1_000_000 + 710_000)
          for z in "5678"}
X_RANGE = (5_300_000, 6_130_000)

# official attribute dictionaries, zal. 5 rozp. EGiB (2001 as amended 2013,
# Dz.U. 2015.542) — what archival operaty carry; the 2021 reg (Dz.U. 2021
# poz. 1390) replaces ZRD->SPD, BPP->ISD and drops RZG, but its exact enums
# await the EGiB XSD pull, so post-cutoff violations are review-flags, not fails
ZRD_2015 = set("123456789")
BPP_2015 = set("123456")
STB_2015 = set("1234")
RZG_2015 = set("1234567")
CUTOFF_2021 = "2021-07-31"


def check_slownik(pts, date_str=None):
    """G5: every attribute must belong to its legal dictionary. Returns
    (status, violations): True = all legal; False = violations on a pre-2021
    operat (hard fail); None = violations on a 2021+ operat (possibly the
    SPD/ISD vocabulary — human review, not a fail)."""
    violations = []
    for p in pts:
        for k, allowed in (("zrd", ZRD_2015), ("bpp", BPP_2015),
                           ("stb", STB_2015), ("rzg", RZG_2015)):
            v = p.get(k)
            if v not in (None, "") and str(v) not in allowed:
                violations.append(f"{p.get('id')}: {k}={v}")
    if not violations:
        return True, []
    if date_str and str(date_str) >= CUTOFF_2021:
        return None, violations
    return False, violations

ROW = re.compile(r"^(?P<pid>[\w./-]+)\s+(?P<x>\d{4,7}\.\d{2})\s+(?P<y>\d{4,7}\.\d{2})"
                 r"\s+(?P<zrd>\S+)\s+(?P<bpp>\S+)\s+(?P<stb>\S+)\s+(?P<rzg>\S+)"
                 r"\s+(?P<status>\S+)\s*$")


def _log(job_dir, stage, msg, **kw):
    with open(os.path.join(job_dir, "tasks", "log.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(dict(t=time.strftime("%H:%M:%S"), stage=stage,
                                msg=msg, **kw), ensure_ascii=False) + "\n")


def create_job(pdf_path, name=None):
    name = name or time.strftime("job-%Y%m%d-%H%M%S")
    job_dir = os.path.join(JOBS, name)
    for sub in ("source", "pages", "transcript", "extracted", "checks", "out", "tasks"):
        os.makedirs(os.path.join(job_dir, sub), exist_ok=True)
    dst = os.path.join(job_dir, "source", "operat.pdf")
    with open(pdf_path, "rb") as s, open(dst, "wb") as d:
        d.write(s.read())
    _log(job_dir, "ingest", f"source copied from {pdf_path}")
    return name


def stage_pages(job_name):
    """Survey + per-page transcript; raster pages rendered to PNG and flagged.
    Every transcript carries the reference to where its image lives."""
    job_dir = os.path.join(JOBS, job_name)
    pdf = os.path.join(job_dir, "source", "operat.pdf")
    sv = survey(pdf)
    for row in sv:
        n = row["page"]
        md_path = os.path.join(job_dir, "transcript", f"page-{n:03d}.md")
        if row["has_text"]:
            body = text_layer(pdf, n)
            content = (f"# Strona {n}\n\n```text\n{body}\n```\n")
        else:
            png = os.path.join(job_dir, "pages", f"page-{n:03d}.png")
            render_page(pdf, n, png)
            rel = f"../pages/page-{n:03d}.png"
            head = (f"# Strona {n}\n\n**BRAK WARSTWY TEKSTOWEJ** — strona "
                    f"rastrowa; obraz: [{os.path.basename(png)}]({rel})\n\n"
                    f"![strona {n}]({rel})\n\n")
            content = head + "_Do OCR/VLM w fazie 2._\n"
            try:
                import ocr
                if ocr.available():
                    o = ocr.ocr_page(png)
                    json.dump(o, open(os.path.join(
                        job_dir, "extracted", f"ocr-{n:03d}.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=1)
                    content = (head + "Transkrypcja OCR (RapidOCR PP-OCRv6, "
                               f"śr. pewność {o['mean_conf']}, linii poniżej "
                               f"progu: {o['low_count']}):\n\n```text\n"
                               + o["text"] + "\n```\n")
            except Exception as e:            # OCR never blocks the pipeline
                content = head + f"_OCR niedostępny: {str(e)[:120]}_\n"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(content)
    teksty.jsave(os.path.join(job_dir, "extracted", "survey.json"), sv)
    _log(job_dir, "pages", f"{len(sv)} pages; raster: "
         f"{[r['page'] for r in sv if not r['has_text']]}")
    return sv


def stage_header(job_name):
    """Header fields from the title/report pages (code extractor v1; the model
    extractor replaces this stage behind the same JSON contract)."""
    job_dir = os.path.join(JOBS, job_name)
    pdf = os.path.join(job_dir, "source", "operat.pdf")
    text = "\n".join(text_layer(pdf, n) for n in (1, 2))
    def grab(pat, default=None):
        m = re.search(pat, text, re.I)
        return m.group(1).strip() if m else default
    hdr = dict(
        cel_pracy=grab(r"Cel pracy:\s*(.+)"),
        id_zgloszenia=grab(r"Identyfikator zgloszenia:\s*(\S+)"),
        dzialka=grab(r"Dzialka ewidencyjna:\s*(\S+)"),
        # honest CRS extraction (fala 8): declared line, canonicalized for
        # the PL-2000-strefa phrasing, verbatim for every other system;
        # NEVER a fabricated default
        uklad=next(
            (f"PL-2000/{m.group(1)}" if (m := re.search(
                r"PL-2000[ /]*(?:strefa)?\s*(\d)", u)) else u
             for u in [grab(r"Uklad wspolrzednych:\s*(.+)")
                       or grab(r"(PL-2000 strefa\s*\d)")] if u), None),
        wykonawca=grab(r"Wykonawca:\s*(.+)"),
        nr_uprawnien=grab(r"upr\.\s*nr\s*(\d+)"),
        data_pomiaru=grab(r"Data pomiaru:\s*(\d{4}-\d{2}-\d{2})"),
        data_sporzadzenia=grab(r"Data sporzadzenia:\s*(\d{4}-\d{2}-\d{2})"),
        rodzaj_aktu=None, strona_wykazu=None,
    )
    m = re.search(r"Wykaz wspolrzednych zamieszczono na str\.\s*(\d+)", text)
    if m:
        hdr["strona_wykazu"] = int(m.group(1))
    full = "\n".join(text_layer(pdf, n)
                     for n in range(1, len(json.load(open(os.path.join(
                         job_dir, "extracted", "survey.json"), encoding="utf-8"))) + 1))
    m = re.search(r"Rodzaj aktu:\s*(.+)", full)
    if m:
        hdr["rodzaj_aktu"] = m.group(1).strip()
    teksty.jsave(os.path.join(job_dir, "extracted", "header.json"), hdr)
    _log(job_dir, "header", "extracted", fields=sum(v is not None for v in hdr.values()))
    return hdr


def parse_rows(text):
    """Regex row parser over one page's text — shared by the code extractor
    (v1 pipeline) and the G3 referee over LLM transcription."""
    out = []
    for line in text.splitlines():
        m = ROW.match(line.strip())
        if m:
            out.append(dict(id=m["pid"], x=float(m["x"]), y=float(m["y"]),
                            zrd=m["zrd"], bpp=m["bpp"], stb=m["stb"],
                            rzg=m["rzg"], status=m["status"]))
    return out


def referee_wykaz(parsed_by_page, llm_points, tol=0.005):
    """G3: the deterministic parser referees the LLM transcription on
    text-layer pages. The parser is a REFEREE, not truth — rows only the LLM
    read (layouts the regex can't) stay unverified, never wrong; rows the
    parser read but the LLM missed are omissions; coordinate/attribute
    disagreements are mismatches. Either fails the gate."""
    niezgodne, pominiete, zgodne, tylko_llm = [], [], 0, 0
    for page, rows in parsed_by_page.items():
        by_id = {r["id"]: r for r in rows}
        llm_page = [p for p in llm_points if p.get("page") == page]
        llm_ids = {p.get("id") for p in llm_page}
        pominiete += [dict(page=page, id=rid) for rid in by_id
                      if rid not in llm_ids]
        for p in llm_page:
            r = by_id.get(p.get("id"))
            if not r:
                tylko_llm += 1
                continue
            attr_diff = any(str(p.get(k) or "") != str(r[k] or "")
                            for k in ("zrd", "bpp", "stb", "rzg"))
            if (abs((p.get("x") or 0) - r["x"]) > tol
                    or abs((p.get("y") or 0) - r["y"]) > tol or attr_diff):
                niezgodne.append(dict(page=page, id=p.get("id"),
                                      llm=dict(x=p.get("x"), y=p.get("y")),
                                      parser=dict(x=r["x"], y=r["y"])))
            else:
                zgodne += 1
    if not any(parsed_by_page.values()):
        status = None            # nothing to referee (scans) — not a pass
    else:
        status = not (niezgodne or pominiete)
    return dict(status=status, zgodne=zgodne, niezgodne=niezgodne,
                pominiete_przez_llm=pominiete, tylko_llm=tylko_llm)


def _norm_text(s):
    return re.sub(r"\s+", " ", str(s)).casefold().strip()


def _fold_diacritics(s):
    """Wave-5 enemy: models silently 'correct' diacritics absent from the
    source (z->ż class, arxiv 2510.06743) and strict matching turns that into
    a false hallucination alarm. Folding tier: strip combining marks (ł needs
    its own rule — it does not decompose)."""
    import unicodedata
    s = s.replace("ł", "l").replace("Ł", "L")
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if not unicodedata.combining(c))


def _value_variants(key, val):
    v = [str(val)]
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", str(val))
    if key.startswith("data_") and m:
        y, mo, d = m.groups()
        v += [f"{d}.{mo}.{y}", f"{int(d)}.{int(mo)}.{y}", f"{d}-{mo}-{y}"]
    if key == "uklad":
        mz = re.search(r"(\d)\s*$", str(val))
        if mz:
            z = mz.group(1)
            v += [f"strefa {z}", f"2000/{z}", f"2000({z})", f"2000 strefa {z}"]
    return v


def dup_coords(pts):
    """Wave-5 enemy: temp-0 repetition loops pass span-grounding (every value
    exists in the source) and can mutate the id while repeating coordinates.
    Distinct ids sharing a cm-exact (x,y) is a review flag, not a fail —
    legally two boundary points never share the same position."""
    by_xy = {}
    for p in pts:
        by_xy.setdefault((p["x"], p["y"]), []).append(p["id"])
    return [ids for ids in by_xy.values() if len(ids) > 1]


def grounding_check(pdf_path, fields, zrodla, ocr_texts=None):
    """G2: every extracted value must EXIST in the document (else it is a
    hallucination — hard fail), and SHOULD exist on the page the extractor
    claims as its source (else a mis-attribution — review flag, not a fail).
    Scan pages ground against their OCR transcripts (ocr_texts: {page: text})
    — without them every scan value would false-alarm as a hallucination."""
    from pdfpages import page_count
    texts = {}
    for n in range(1, page_count(pdf_path) + 1):
        t = text_layer(pdf_path, n)
        if not t.strip() and ocr_texts and ocr_texts.get(n):
            t = ocr_texts[n]
        texts[n] = _norm_text(t)
    zr = dict(zrodla or {})
    if "dzialka" not in zr and "dzialki" in zr:
        zr["dzialka"] = zr["dzialki"]
    folded = {n: _fold_diacritics(t) for n, t in texts.items()}
    pola = {}
    for key, val in fields.items():
        if val in (None, "", []) or key == "strona_wykazu":
            continue
        for i, single in enumerate(val if isinstance(val, list) else [val]):
            fkey = key if not isinstance(val, list) else f"{key}[{i}]"
            variants = [_norm_text(x) for x in _value_variants(key, single)]
            found = next((n for n, t in texts.items()
                          if any(vv in t for vv in variants)), None)
            fold = False
            if found is None:
                # tier 2: diacritic-folded match — a diacritic-only mismatch
                # is a silent model 'correction' for dual-OCR arbitration,
                # not a hallucination fail
                fvars = [_fold_diacritics(v) for v in variants]
                found = next((n for n, t in folded.items()
                              if any(fv in t for fv in fvars)), None)
                fold = found is not None
            try:
                claimed = int(zr.get(key)) if zr.get(key) is not None else None
            except (TypeError, ValueError):
                claimed = None
            claim_ok = None
            if claimed is not None and found is not None:
                claim_ok = any(vv in texts.get(claimed, "") for vv in variants)
                if not claim_ok and fold:
                    claim_ok = any(
                        fv in folded.get(claimed, "")
                        for fv in [_fold_diacritics(v) for v in variants])
            pola[fkey] = dict(found_page=found, claimed=claimed,
                              claim_ok=claim_ok, **(dict(fold=True) if fold
                                                    else {}))
    return dict(
        wartosci_w_dokumencie=(all(f["found_page"] is not None
                                   for f in pola.values()) if pola else None),
        zrodla_trafne=(all(f["claim_ok"] is not False for f in pola.values())
                       if pola else None),
        diakrytyka_fold=[k for k, f in pola.items() if f.get("fold")] or None,
        pola=pola)


def dedup_punkty(punkty):
    """Duplicate-id semantics (masywny true-positive 06.08): documents may
    legally LIST the same point twice (wykaz + protokol both carry rows) —
    copies that AGREE within 1 cm merge into the first-page row; copies
    that DISAGREE both stay (truth law) and the duplicate gate fires with
    detail. Returns (punkty, uwagi)."""
    seen = {}
    out, uwagi = [], []
    for p in punkty:
        pid = p.get("id")
        prev = seen.get(pid)
        if prev is None:
            seen[pid] = p
            out.append(p)
            continue
        zgodne = (isinstance(p.get("x"), (int, float))
                  and isinstance(prev.get("x"), (int, float))
                  and abs(p["x"] - prev["x"]) <= 0.01
                  and abs(p["y"] - prev["y"]) <= 0.01)
        if zgodne:
            uwagi.append(f"id {pid}: powtorzony na s. {prev.get('page')} "
                         f"i {p.get('page')} ze zgodnymi wspolrzednymi — "
                         f"scalono")
        else:
            out.append(p)                      # conflict: keep both, gate fires
    return out, uwagi


def stage_wykaz(job_name):
    """The load-bearing table: parse coordinate rows from the wykaz page(s)."""
    job_dir = os.path.join(JOBS, job_name)
    pdf = os.path.join(job_dir, "source", "operat.pdf")
    sv = json.load(open(os.path.join(job_dir, "extracted", "survey.json"),
                        encoding="utf-8"))
    pts, src_page = [], None
    for row in sv:
        if not row["has_text"]:
            continue
        for r in parse_rows(text_layer(pdf, row["page"])):
            src_page = row["page"]
            pts.append(dict(r, page=row["page"]))
    pts, uw = dedup_punkty(pts)
    out = dict(punkty=pts, strona_wykazu=src_page, liczba_punktow=len(pts),
               **(dict(uwagi=uw) if uw else {}))
    teksty.jsave(os.path.join(job_dir, "extracted", "wykaz.json"), out)
    _log(job_dir, "wykaz", f"{len(pts)} points from page {src_page}")
    return out


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _page_heading(text):
    """First substantive line if it looks like a section title (mostly caps,
    short); folio lines are skipped. None -> the page type labels the TOC."""
    for line in text.splitlines():
        s = line.strip()
        if not s or folio_of_line(s) is not None:
            continue
        letters = [c for c in s if c.isalpha()]
        if len(s) <= 64 and letters and \
                sum(c.isupper() for c in letters) / len(letters) > 0.6:
            return s
        return None
    return None


def _page_type(has_text, cov, text):
    if not has_text:
        return "skan"
    if any(ROW.match(l.strip()) for l in text.splitlines()):
        return "tabela"
    return "mieszana" if cov >= 0.35 else "tekst"


def folio_consensus(readings):
    """readings: [(pdf_page, folio|None)]. Real folios are UNIQUE and track the
    PDF order with a constant-ish offset; repeated values (case numbers in
    headers — one public sample report prints its case number on six pages) and offset outliers (dates,
    counts caught by the regex) are noise. Returns folios aligned to input,
    None where rejected; needs >=2 consistent readings to conclude anything."""
    from collections import Counter
    dup = {v for v, c in Counter(f for _, f in readings if f).items() if c > 1}
    cand = [(n, f) for n, f in readings if f and f not in dup]
    if len(cand) < 2:
        return [None] * len(readings)
    offs = sorted(f - n for n, f in cand)
    off = offs[len(offs) // 2]
    ok = {n: f for n, f in cand if abs(f - (n + off)) <= 2}
    if len(ok) < 2:
        return [None] * len(readings)
    return [ok.get(n) for n, _ in readings]


def folio_gaps(pairs):
    """Physically-missing-page report over (pdf_page, folio) READINGS.
    Law: unnumbered-but-present pages are NOT missing — a page is missing only
    when the folio jump EXCEEDS the count of intervening PDF pages (removing a
    page shifts folio-vs-index offset; in one public sample report pages 4-5
    are present, just unnumbered). A folio going backwards = per-section renumbering, reported as an
    observation, never as a gap. Fragment: sequence starting above 1 (operat
    excerpts are normal). Returns (gaps, fragment_start, notes)."""
    rd = sorted((n, f) for n, f in pairs if f)
    gaps, notes = [], []
    for (n1, f1), (n2, f2) in zip(rd, rd[1:]):
        span, between = f2 - f1 - 1, n2 - n1 - 1
        if span < between or f2 <= f1:
            notes.append(f"numeracja niespójna: folio {f1}@s.{n1} -> {f2}@s.{n2}")
        elif span > between:
            gaps.append(dict(
                brakuje=span - between, zakres=[f1 + 1, f2 - 1],
                dowod=f"folio {f1}@s.{n1} -> {f2}@s.{n2}, "
                      f"stron pomiędzy: {between}"))
    fragment_start = rd[0][1] if rd and rd[0][1] > 1 else None
    return gaps, fragment_start, notes


TYPE_LABEL = dict(tekst="strona tekstowa", tabela="tabela współrzędnych",
                  skan="strona rastrowa (skan/szkic)", mieszana="tekst z grafiką")


def stage_mapa(job_name):
    """Document map: canonical page-anchored document.md + machine docmap.json.
    Deterministic code core — anchors {#pNNN}, provenance comments, RFC 8118
    #page=N backlinks; LLM topic labels merge in later behind the same files."""
    job_dir = os.path.join(JOBS, job_name)
    pdf = os.path.join(job_dir, "source", "operat.pdf")
    sv = json.load(open(os.path.join(job_dir, "extracted", "survey.json"),
                        encoding="utf-8"))
    src_sha = _sha256(pdf)

    pages = []
    for row in sv:
        n = row["page"]
        text = text_layer(pdf, n) if row["has_text"] else ""
        cov = image_coverage(pdf, n)
        typ = _page_type(row["has_text"], cov, text)
        heading = _page_heading(text)
        pages.append(dict(
            n=n, folio=printed_page_number(pdf, n), typ=typ,
            naglowek=heading, pokrycie_obrazem=round(cov, 2),
            anchor=f"#p{n:03d}", pdf=f"source/operat.pdf#page={n}",
            znaki=row["chars"], topics=[]))

    consensus = folio_consensus([(p["n"], p["folio"]) for p in pages])
    for p, f in zip(pages, consensus):
        p["folio"] = f
    gaps, fragment_start, folio_notes = folio_gaps(
        [(p["n"], p["folio"]) for p in pages])
    toc = [dict(page=p["n"], tytul=p["naglowek"] or TYPE_LABEL[p["typ"]],
                anchor=p["anchor"]) for p in pages]
    docmap = dict(doc_id=job_name,
                  source=dict(file="source/operat.pdf", sha256=src_sha,
                              pages=len(sv)),
                  pages=pages, toc=toc,
                  braki=dict(folio_luki=gaps, fragment_od=fragment_start,
                             uwagi=folio_notes))
    with open(os.path.join(job_dir, "docmap.json"), "w", encoding="utf-8") as f:
        json.dump(docmap, f, ensure_ascii=False, indent=1, sort_keys=True)

    md = ["---", f"doc_id: {job_name}", "source: source/operat.pdf",
          f"source_sha256: {src_sha}", f"stron: {len(sv)}", "jezyk: pl", "---",
          "", f"# Mapa dokumentu — {job_name}", ""]
    if fragment_start:
        md.append(f"> UWAGA: dokument zaczyna się od strony drukowanej "
                  f"{fragment_start} — to FRAGMENT większego operatu.")
    for g in gaps:
        md.append(f"> BRAKUJE {g['brakuje']} str. w zakresie folio "
                  f"{g['zakres'][0]}–{g['zakres'][1]} ({g['dowod']}).")
    for note in folio_notes:
        md.append(f"> UWAGA: {note}.")
    if fragment_start or gaps or folio_notes:
        md.append("")
    md += ["## Spis treści", ""]
    md += [f"- [s. {t['page']} — {t['tytul']}]({t['anchor']})" for t in toc]
    md.append("")
    for p in pages:
        t = next(x["tytul"] for x in toc if x["page"] == p["n"])
        md += [f"## [s. {p['n']}] {t} {{#p{p['n']:03d}}}",
               f"<!-- page:{p['n']} pdf=\"{p['pdf']}\" "
               f"folio=\"{p['folio'] or ''}\" typ={p['typ']} -->", ""]
        if p["typ"] == "skan":
            md += [f"![strona {p['n']}](pages/page-{p['n']:03d}.png)",
                   "_Strona rastrowa — treść w obrazie; transkrypcja po OCR._", ""]
        else:
            body = text_layer(pdf, p["n"]).rstrip()
            md += ["```text", body, "```", ""]
    with open(os.path.join(job_dir, "document.md"), "w", encoding="utf-8",
              newline="\n") as f:
        f.write("\n".join(md) + "\n")
    _log(job_dir, "mapa", f"{len(sv)} pages, gaps: {len(gaps)}, "
         f"fragment_od: {fragment_start}")
    return docmap


def shoelace(pts):
    n = len(pts)
    s = 0.0
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        s += a["x"] * b["y"] - b["x"] * a["y"]
    return round(abs(s) / 2.0, 1)


def stage_checks(job_name):
    """Invariants BY CODE — the referee inside the product."""
    job_dir = os.path.join(JOBS, job_name)
    wyk = json.load(open(os.path.join(job_dir, "extracted", "wykaz.json"),
                         encoding="utf-8"))
    hdr = json.load(open(os.path.join(job_dir, "extracted", "header.json"),
                         encoding="utf-8"))
    pdf = os.path.join(job_dir, "source", "operat.pdf")
    pts = wyk["punkty"]
    checks = {}
    zone = (hdr.get("uklad") or "?").split("/")[-1]
    y_rng = ZONE_Y.get(zone)
    checks["strefa_vs_wspolrzedne"] = bool(y_rng) and all(
        y_rng[0] <= p["y"] <= y_rng[1] for p in pts)
    checks["x_w_zakresie"] = all(X_RANGE[0] <= p["x"] <= X_RANGE[1] for p in pts)
    checks["liczba_punktow_zgodna"] = None
    decl = re.search(r"Liczba punktow:\s*(\d+)",
                     "\n".join(text_layer(pdf, wyk["strona_wykazu"] or 1).splitlines()))
    if decl:
        checks["liczba_punktow_zgodna"] = int(decl.group(1)) == len(pts)
    area = shoelace(pts) if len(pts) >= 3 else 0.0
    checks["pole_shoelace_m2"] = area
    decl_area = re.search(r"Pole obliczone:\s*([\d.]+)\s*m2",
                          text_layer(pdf, wyk["strona_wykazu"] or 1))
    checks["pole_zgodne_z_deklaracja"] = (
        abs(area - float(decl_area.group(1))) < 0.6 if decl_area else None)
    # uniform polarity LAW: in checks, true is ALWAYS the good value — the
    # judge once flagged "duplikaty_id: false" as a problem because it was the
    # single inverted key; never hand the model mixed semantics
    checks["brak_duplikatow_id"] = len(pts) == len({p["id"] for p in pts})
    if not checks["brak_duplikatow_id"]:
        # after assembly-dedup agreeing copies are merged, so remaining
        # duplicates are CONTRADICTIONS — same id, different coordinates
        # inside one operat; detail feeds operator + rewident digest
        grupy = {}
        for p in pts:
            grupy.setdefault(p.get("id"), []).append(p)
        sprz = [dict(id=i,
                     strony=sorted({p.get("page") for p in ps}),
                     delta_m=round(max(
                         abs(a["x"] - b["x"]) + abs(a["y"] - b["y"])
                         for a in ps for b in ps
                         if isinstance(a.get("x"), (int, float))
                         and isinstance(b.get("x"), (int, float))), 2))
                for i, ps in grupy.items() if len(ps) > 1]
        if sprz:
            checks.setdefault("flagi", {})["sprzeczne_id"] = sprz[:10]
    dup_xy = dup_coords(pts)
    if dup_xy:
        checks.setdefault("flagi", {})["powtorzone_wspolrzedne"] = dup_xy[:10]
    slownik, violations = check_slownik(
        pts, hdr.get("data_sporzadzenia") or hdr.get("data_pomiaru"))
    checks["slownik_atrybutow"] = slownik
    if violations:
        checks["slownik_naruszenia"] = violations[:20]

    # uklad wspolrzednych (fala 8): detection with magnitude cross-check;
    # non-PL-2000 systems are FLAGS (review), never silent range-FAILs —
    # the PL-2000 range gates above only judge PL-2000 documents
    import uklady
    det = uklady.wykryj_uklad(hdr.get("uklad"), pts)
    checks["uklad_wykryty"] = det["system"]
    if det["zgodnosc_deklaracji_z_liczbami"] is False:
        checks.setdefault("flagi", {})["uklad_deklaracja_vs_liczby"] = det
    if det["system"] not in ("PL-2000", None):
        checks.setdefault("flagi", {})["uklad_do_recenzji"] = dict(
            system=det["system"], strefa=det.get("strefa"))
        # non-PL-2000 coordinates: the PL-2000 range gates are NOT verdicts
        checks["strefa_vs_wspolrzedne"] = None
        checks["x_w_zakresie"] = None

    # gates written by the LLM path (G2 grounding, G3 referee) merge in when
    # present; hallucination and referee disagreement are PASS-affecting,
    # source mis-attribution is a review flag only
    def _extra(fname):
        p = os.path.join(job_dir, "extracted", fname)
        return json.load(open(p, encoding="utf-8")) if os.path.isfile(p) else None
    g = _extra("grounding.json")
    if g:
        checks["wartosci_w_dokumencie"] = g.get("wartosci_w_dokumencie")
        # flags list PROBLEMS only (live-series wart: good docs reported
        # '1 flag' for zrodla_trafne=True) — mis-attribution goes in, health
        # does not; the full value stays in grounding.json for audit
        if g.get("zrodla_trafne") is False:
            checks.setdefault("flagi", {})["zrodla_trafne"] = False
        if g.get("diakrytyka_fold"):
            checks.setdefault("flagi", {})["diakrytyka_do_arbitrazu"] = \
                g["diakrytyka_fold"]
    ref = _extra("referee.json")
    if ref:
        checks["referee_zgodny"] = ref.get("status")
    sg = _extra("scan_gate.json")
    if sg:
        if not sg.get("dostepny_drugi"):
            checks["wykaz_ocr_potwierdzony"] = None
        else:
            checks["wykaz_ocr_potwierdzony"] = not sg.get("zaden")
        if sg.get("tylko_jeden"):
            checks.setdefault("flagi", {})["wsp_jeden_silnik"] = \
                sg["tylko_jeden"][:10]

    checks["PASS"] = all(v is True for v in checks.values()
                         if isinstance(v, bool))
    teksty.jsave(os.path.join(job_dir, "checks", "invariants.json"), checks)
    _log(job_dir, "checks", "PASS" if checks["PASS"] else "FAIL", **{
        k: v for k, v in checks.items() if k != "PASS"})
    return checks


DEFAULT_TEMPLATE = dict(
    kolumny=["ID_PKT", "X", "Y", "ZRD", "BPP", "STB", "RZG", "STATUS",
             "NR_OPERATU", "STRONA"],
    separator=";", naglowek=True,
    # operator-movable format (owner 06.08): rename columns per PODGiK and
    # transpose rows<->columns — format lives in PROFILES not prompts,
    # because CSV shape is CODE's job (determinism law)
    nazwy_kolumn={}, transpozycja=False)


def pewnosc_punktow(pts, checks, przeliczenie_uwaga=None):
    """The certainty layer (owner 06.08): per-point categorical tier computed
    by CODE from real signals — never a verbalized probability (calibration
    law: round-number confidences are uncalibrated by construction; colors
    carry tiers instead). Returns {id: {tier, powody, strona}}.
      KRYTYCZNE (red)  — referee mismatch on this id / grounding fail /
                         vocabulary violation on this id
      SPRAWDZ  (amber) — single-OCR-engine coordinate / duplicate-position
                         flag / converted from another CRS / scan source
      PEWNE    (green) — none of the above
    """
    flagi = checks.get("flagi") or {}
    single = {f["id"] for f in (flagi.get("wsp_jeden_silnik") or [])}
    sprzeczne = {f["id"] for f in (flagi.get("sprzeczne_id") or [])}
    dupxy = {i for grp in (flagi.get("powtorzone_wspolrzedne") or [])
             for i in grp}
    viol = {str(v).split(":")[0].strip()
            for v in (checks.get("slownik_naruszenia") or [])}
    referee_bad = checks.get("referee_zgodny") is False
    grounding_bad = checks.get("wartosci_w_dokumencie") is False
    out = {}
    for p in pts:
        pid = p.get("id")
        powody = []
        if referee_bad:
            powody.append("referee niezgodny")
        if grounding_bad:
            powody.append("grounding FAIL")
        if pid in viol:
            powody.append("slownik naruszony")
        if pid in sprzeczne:
            powody.append("id powtorzony ze sprzecznymi wspolrzednymi")
        tier = "KRYTYCZNE" if powody else None
        if tier is None:
            if pid in single:
                powody.append("wspolrzedna potwierdzona jednym silnikiem OCR")
            if pid in dupxy:
                powody.append("pozycja powtorzona miedzy punktami")
            if przeliczenie_uwaga:
                powody.append(przeliczenie_uwaga)
            tier = "SPRAWDZ" if powody else "PEWNE"
        out[pid] = dict(tier=tier, powody=powody, strona=p.get("page"))
    return out


def load_template(name=None):
    """Per-PODGiK upload template (column order/subset, separator, header) —
    powiaty differ and the operator edits these as plain JSON files."""
    if name:
        p = os.path.join(ROOT, "profiles", f"podgik-{name}.json")
        if os.path.isfile(p):
            t = dict(DEFAULT_TEMPLATE)
            t.update(json.load(open(p, encoding="utf-8")))
            return t
    return dict(DEFAULT_TEMPLATE)


def stage_outputs(job_name, template=None):
    """Outputs assembled BY CODE from extracted/*: przeglad CSV + XLSX and the
    upload CSV shaped by the (per-PODGiK) template."""
    job_dir = os.path.join(JOBS, job_name)
    hdr = json.load(open(os.path.join(job_dir, "extracted", "header.json"),
                         encoding="utf-8"))
    wyk = json.load(open(os.path.join(job_dir, "extracted", "wykaz.json"),
                         encoding="utf-8"))
    chk = json.load(open(os.path.join(job_dir, "checks", "invariants.json"),
                         encoding="utf-8"))
    out_dir = os.path.join(job_dir, "out")
    tpl = template if isinstance(template, dict) else load_template(template)

    p1 = os.path.join(out_dir, "przeglad.csv")
    with open(p1, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        cols = ["typ_dokumentu", "cel_pracy", "id_zgloszenia", "dzialka", "uklad",
                "wykonawca", "nr_uprawnien", "data_pomiaru", "data_sporzadzenia",
                "rodzaj_aktu", "liczba_punktow", "strona_wykazu", "pole_m2",
                "kontrole"]
        w.writerow(cols)
        w.writerow(["operat techniczny", hdr.get("cel_pracy"),
                    hdr.get("id_zgloszenia"), hdr.get("dzialka"), hdr.get("uklad"),
                    hdr.get("wykonawca"), hdr.get("nr_uprawnien"),
                    hdr.get("data_pomiaru"), hdr.get("data_sporzadzenia"),
                    hdr.get("rodzaj_aktu"), wyk["liczba_punktow"],
                    wyk.get("strona_wykazu"), chk.get("pole_shoelace_m2"),
                    "PASS" if chk.get("PASS") else "FAIL"])

    dz = (hdr.get("dzialka") or "dzialka").replace("/", "_").replace(".", "-")
    p2 = os.path.join(out_dir, f"wgranie_{dz}.csv")
    field = dict(ID_PKT=lambda p: p["id"], X=lambda p: f"{p['x']:.2f}",
                 Y=lambda p: f"{p['y']:.2f}",
                 H=lambda p: ("" if p.get("h") in (None, "") else f"{p['h']:.2f}"),
                 ZRD=lambda p: p.get("zrd"), BPP=lambda p: p.get("bpp"),
                 STB=lambda p: p.get("stb"), RZG=lambda p: p.get("rzg"),
                 STATUS=lambda p: p.get("status"),
                 NR_OPERATU=lambda p: hdr.get("id_zgloszenia"),
                 STRONA=lambda p: p.get("page"),
                 X_2000=lambda p: ("" if p.get("x_2000") is None
                                   else f"{p['x_2000']:.2f}"),
                 Y_2000=lambda p: ("" if p.get("y_2000") is None
                                   else f"{p['y_2000']:.2f}"),
                 STREFA_2000=lambda p: p.get("strefa_2000") or "")
    # fala 8: exact-convertible CRS gets derived PL-2000 columns; original
    # values stay untouched (truth law) — conversion is provenance-marked
    import uklady
    det = uklady.wykryj_uklad(hdr.get("uklad"), wyk["punkty"])
    pkt_out, przel = uklady.przelicz_punkty(wyk["punkty"], det)
    cols = [c for c in tpl["kolumny"] if c in field]
    if przel.get("przeliczenie"):
        cols += ["X_2000", "Y_2000", "STREFA_2000"]
    naz = tpl.get("nazwy_kolumn") or {}
    rows = ([[naz.get(c, c) for c in cols]]
            if tpl.get("naglowek", True) else [])
    rows += [[field[c](p) for c in cols] for p in pkt_out]
    if tpl.get("transpozycja"):
        rows = [list(r) for r in zip(*rows)]
    with open(p2, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=tpl.get("separator", ";"))
        for r in rows:
            w.writerow(r)

    files = [p1, p2]
    try:                               # XLSX przeglad — openpyxl if present
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Przegląd"
        rows = list(csv.reader(open(p1, encoding="utf-8-sig"), delimiter=";"))
        for r in rows:
            ws.append(r)
        for cell in ws[1]:
            cell.font = cell.font.copy(bold=True)
        ws2 = wb.create_sheet("Wykaz punktów")
        ws2.append(cols + ["PEWNOŚĆ", "POWODY", "ŹRÓDŁO"])
        # certainty layer (owner 06.08): categorical tier as COLOR, never a
        # probability number — computed by code from real signals
        from openpyxl.styles import PatternFill
        fills = dict(PEWNE=PatternFill("solid", start_color="C6EFCE"),
                     SPRAWDZ=PatternFill("solid", start_color="FFEB9C"),
                     KRYTYCZNE=PatternFill("solid", start_color="FFC7CE"))
        pew = pewnosc_punktow(pkt_out, chk, przel.get("uwaga"))
        for p in pkt_out:
            t = pew.get(p.get("id")) or dict(tier="SPRAWDZ", powody=[])
            ws2.append([field[c](p) for c in cols]
                       + [t["tier"], "; ".join(t["powody"])[:120],
                          f"operat s. {p.get('page')}"])
            for cell in ws2[ws2.max_row]:
                cell.fill = fills[t["tier"]]
            link = ws2.cell(row=ws2.max_row, column=len(cols) + 3)
            link.hyperlink = f"../source/operat.pdf#page={p.get('page')}"
            link.style = "Hyperlink"
        for cell in ws2[1]:
            cell.font = cell.font.copy(bold=True)
        # branding law (badanie 06.08): documents carry the CLIENT firm's
        # identity (dominant, left) — the law requires the wykonawca's mark
        # on submissions; the tool's colophon stays small on the right
        # (printer's-mark tradition; prints only, never a data cell)
        firma = (teksty.jread(os.path.join(ROOT, "profiles", "firma.json"))
                 or {}).get("nazwa")
        for sheet in (ws, ws2):
            if firma:
                sheet.oddFooter.left.text = firma
            sheet.oddFooter.right.text = "wygenerowano w geodoc"
        p3 = os.path.join(out_dir, "przeglad.xlsx")
        wb.save(p3)
        files.append(p3)
    except ImportError:
        pass

    # slice 9: record this operat in the domain graph and pin the computed
    # nowy/zmieniony/bez_zmian flags beside the checks (history speaks, not
    # the operat's own claim)
    import domain
    flags = domain.ingest_job(job_name)
    teksty.jsave(os.path.join(job_dir, "checks", "rodowod.json"), flags)
    _log(job_dir, "outputs", "written",
         files=[os.path.basename(x) for x in files],
         rodowod={f: sum(1 for v in flags.values() if v["flaga"] == f)
                  for f in ("nowy", "zmieniony", "bez_zmian")})
    return files


def stage_pieczec(job_name):
    """Pieczec Replay: the job's reproducibility seal. Everything needed to
    re-run the analysis byte-for-byte and to prove no hand edited artifacts:
    engine build + model files, per-agent prompt hashes and profiles (from
    _meta already persisted in extracted/), and sha256 of every text artifact.
    Deterministic output (sorted, no timestamps) — two builds of the same job
    are byte-identical; a court or PODGiK can verify the chain of custody."""
    job_dir = os.path.join(JOBS, job_name)
    import llm  # lazy: the code-only pipeline never needs the engine module
    m = json.load(open(llm.manifest_path(), encoding="utf-8"))

    def _bajty(gguf):
        # sciezki wzgledne (instalacja kliencka) rozwiazuja sie wzgledem
        # ROOT — tak samo jak w llm.manifest(); bez tego pieczec na
        # instalacji uzytkownika zapisywala bajty=null (audyt slepy na rozmiar)
        p = gguf if os.path.isabs(gguf) else os.path.join(ROOT, gguf)
        return os.path.getsize(p) if os.path.isfile(p) else None

    silnik = dict(build=os.path.basename(os.path.dirname(m["server"])),
                  modele={k: dict(plik=os.path.basename(v["gguf"]),
                                  bajty=_bajty(v["gguf"]))
                          for k, v in m["models"].items()})
    agenci = {}
    # agents record their prompt hash in _meta: the extractors in extracted/,
    # the judge in verdict/
    _meta_files = [os.path.join(job_dir, sub, f)
                   for sub in ("extracted", "verdict")
                   if os.path.isdir(os.path.join(job_dir, sub))
                   for f in sorted(os.listdir(os.path.join(job_dir, sub)))
                   if f.endswith(".json")]
    for path in _meta_files:
        try:
            obj = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        meta = obj.get("_meta") if isinstance(obj, dict) else None
        if meta and obj.get("_agent"):
            agenci[obj["_agent"]] = dict(
                prompt_hash=meta.get("prompt_hash"),
                prompt_source=meta.get("prompt_source"),
                model=meta.get("model"), profile=meta.get("profile"))
    artefakty = {}
    # flat folders + the job root, then the chapter map recursively (one
    # folder per chapter); analizy/ (operator questions after the run) stays
    # outside the seal on purpose — it grows after sealing
    _paths = []
    for sub in ("extracted", "checks", "out", "transcript", "verdict", ""):
        d = os.path.join(job_dir, sub) if sub else job_dir
        if os.path.isdir(d):
            _paths += [(os.path.join(d, f), f"{sub}/{f}" if sub else f)
                       for f in sorted(os.listdir(d))]
    for dp, _dn, fn in os.walk(os.path.join(job_dir, "rozdzialy")):
        _paths += [(os.path.join(dp, f), os.path.relpath(
            os.path.join(dp, f), job_dir).replace(os.sep, "/")) for f in fn]
    for p, rel in _paths:
        # xlsx is a VIEW with zip-embedded timestamps (non-deterministic);
        # the sealed record is the CSVs + JSON + Markdown artifacts
        if (not os.path.isfile(p) or rel == "checks/pieczec.json"
                or p.endswith((".png", ".pdf", ".xlsx"))):
            continue
        artefakty[rel] = _sha256(p)
    seal = dict(job=job_name, silnik=silnik, seed=7420, agenci=agenci,
                artefakty=artefakty)
    with open(os.path.join(job_dir, "checks", "pieczec.json"), "w",
              encoding="utf-8") as f:
        json.dump(seal, f, ensure_ascii=False, indent=1, sort_keys=True)
    _log(job_dir, "pieczec", f"{len(artefakty)} artefaktow, "
         f"{len(agenci)} agentow, build {silnik['build']}")
    return seal


def run_all(pdf_path, name=None):
    job = create_job(pdf_path, name)
    stage_pages(job)
    stage_mapa(job)
    stage_header(job)
    stage_wykaz(job)
    checks = stage_checks(job)
    outs = stage_outputs(job)
    stage_pieczec(job)
    return dict(job=job, checks=checks, outputs=outs)
