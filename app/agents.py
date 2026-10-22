# geodoc — the specialized-agent pipeline (LLM stages behind the SAME contracts
# as the code stages). Flow: klasyfikator -> ekstraktor_naglowka ->
# ekstraktor_wykazu (per candidate page) -> code invariants -> werdyktor.
# Every agent call is a fresh context; documents go in the prompt with the task
# LAST; aggregation stays in code (stage_checks/stage_outputs from stages.py).
#
# Usage: PYTHONUTF8=1 python app/agents.py <pdf> [--job name] [--verdict]

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import llm  # noqa: E402
import stages  # noqa: E402
from pdfpages import text_layer  # noqa: E402


def _page_text(job, pdf, n):
    """Text for a page from the cheapest truthful source: PDF text layer,
    else the page's OCR transcript (raster branch). ('', None) when neither."""
    t = text_layer(pdf, n).strip()
    if t:
        return t, None
    p = os.path.join(stages.JOBS, job, "extracted", f"ocr-{n:03d}.json")
    if os.path.isfile(p):
        o = json.load(open(p, encoding="utf-8"))
        return (o.get("text") or "").strip(), o.get("mean_conf")
    return "", None


def usable_pages(job, pdf, sv):
    """Pages the crew can READ: text layer or OCR transcript present."""
    out = []
    for r in sv:
        t, _ = _page_text(job, pdf, r["page"])
        if t:
            out.append(r["page"])
    return out


def _doc_block(job, pdf, pages, cap=6000):
    # one rare delimiter pair around the WHOLE document (official Qwen guide:
    # fence reference content, never interleave it with instructions); OCR
    # pages carry their confidence so the model knows the source quality
    parts = ["===DOKUMENT==="]
    for n in pages:
        t, conf = _page_text(job, pdf, n)
        tag = f" (OCR, pewnosc {conf})" if conf is not None else ""
        parts.append(f"--- STRONA {n}{tag} ---\n{t[:cap]}")
    parts.append("===KONIEC DOKUMENTU===")
    return "\n".join(parts)


def stage_klasyfikator(job, pdf, sv):
    readable = usable_pages(job, pdf, sv)
    payload = (f"MAPA STRON: {json.dumps(sv, ensure_ascii=False)}\n\n"
               f"DOKUMENT (pierwsze czytelne strony):\n"
               f"{_doc_block(job, pdf, readable[:3])}\n\n"
               "ZADANIE: sklasyfikuj dokument wg kontraktu.")
    out = llm.call_agent("klasyfikator", payload)
    _save(job, "klasyfikacja.json", out)
    return out


def _hint_block(klas, keys):
    """Cross-agent handoff — BLINDING LAW (measured): never feed an upstream
    VALUE guess to a generative stage extracting those very fields; anchoring
    survives "verify it yourself" phrasing (<=10% recovery), and error cascades
    amplify 6-10x. The classifier hands off by ROUTING (page candidates narrow
    the input) — values may only flow to the judge, which generates nothing."""
    label = dict(cel_pracy="cel pracy", uklad_wspolrzednych="uklad wspolrzednych",
                 strony_wykazu_kandydaci="strony wykazu (kandydaci)")
    hints = [f"- {label[k]}: {klas[k]}" for k in keys
             if klas.get(k) not in (None, [], "")]
    if not hints:
        return ""
    return ("KONTEKST z klasyfikacji (informacyjnie):\n"
            + "\n".join(hints) + "\n\n")


def stage_naglowek_llm(job, pdf, sv, klas):
    # page 1 ALWAYS rides along — title pages carry id/wykonawca/daty, and the
    # klasyfikator's sprawozdanie candidates alone once starved this stage.
    # Handoff is ROUTING-ONLY: candidates narrow the input; no value hints
    # (the extractor extracts cel_pracy/uklad — feeding it the classifier's
    # guesses is the textbook anchoring case).
    cands = sorted(set([1] + (klas.get("strony_sprawozdania_kandydaci") or [])))[:3]
    payload = (f"DOKUMENT:\n{_doc_block(job, pdf, cands)}\n\n"
               "ZADANIE: wyekstrahuj naglowek operatu wg kontraktu.")
    out = llm.call_agent("ekstraktor_naglowka", payload)
    _save(job, "header_llm.json", out)
    return out


BULK_THRESHOLD = 3     # >=3 wykaz pages: boot the -np 4 bulk profile —
                       # measured +97% aggregate TG (expert-read amortization)


def _wykaz_one_page(job, pdf, n, parallel=1):
    # routing-only handoff here too: the transcriber copies digits; a zone
    # hint could only anchor it — the zone is validated by code (G5)
    payload = (f"DOKUMENT:\n{_doc_block(job, pdf, [n], cap=9000)}\n\n"
               "ZADANIE: transkrybuj tabele wspolrzednych z tej strony wg kontraktu.")
    return n, llm.call_agent("ekstraktor_wykazu", payload, max_tokens=3000,
                             parallel=parallel)


def routed_wykaz_pages(cands, page_texts):
    """Routing resilience (bug found live 06.08: classifier nominated [2,3]
    of 4 wykaz pages and 18 points silently never reached extraction — the
    referee caught it, DO_POPRAWY). The classifier nomination is a HINT, not
    a gate: CODE detection (deterministic parse_rows per page) unions in any
    page carrying >=2 coordinate rows. Blinding law holds — no LLM values
    are involved, code parse is ground truth."""
    pages = list(cands or [])
    from ocr import COORD
    for n, text in sorted(page_texts.items()):
        if n in pages:
            continue
        # full parsed rows OR raw coordinate density (live-series l2 find:
        # degradation breaks row STRUCTURE while coordinate STRINGS survive
        # — the page must still be routed to the transcriber, which reads
        # what OCR salvaged and the gates flag the rest)
        if (len(stages.parse_rows(text or "")) >= 2
                or len(COORD.findall(text or "")) >= 3):
            pages.append(n)
    return sorted(pages)


def stage_wykaz_llm(job, pdf, sv, klas):
    cands = klas.get("strony_wykazu_kandydaci") or []
    if not cands and klas.get("ma_wykaz_granic") in (True, "niepewne"):
        cands = usable_pages(job, pdf, sv)
    cands = routed_wykaz_pages(
        cands, {r["page"]: _page_text(job, pdf, r["page"])[0] for r in sv})
    results = {}
    if len(cands) >= BULK_THRESHOLD:
        from concurrent.futures import ThreadPoolExecutor
        llm.ensure("worker", parallel=4)      # one reboot, then 4 slots
        with ThreadPoolExecutor(max_workers=4) as ex:
            for n, out in ex.map(
                    lambda n: _wykaz_one_page(job, pdf, n, parallel=4), cands):
                results[n] = out
    else:
        for n in cands:
            results[n] = _wykaz_one_page(job, pdf, n)[1]
    punkty, uwagi = [], []
    for n in cands:                            # deterministic page order
        out = results.get(n) or {}
        if out.get("_error"):
            uwagi.append(f"str.{n}: {out['_error']}")
            continue
        for p in out.get("punkty") or []:
            p["page"] = n
            punkty.append(p)
        if out.get("uwagi"):
            uwagi.append(f"str.{n}: {out['uwagi']}")
    punkty, uw_dedup = stages.dedup_punkty(punkty)
    res = dict(punkty=punkty, strona_wykazu=(cands[0] if punkty else None),
               liczba_punktow=len(punkty), uwagi=uwagi + uw_dedup)
    _save(job, "wykaz_llm.json", res)
    return res


def _digest(header, wykaz, checks, referee=None):
    """G9: the judge reads a CODE-BUILT digest, not raw dumps — only failed or
    unknown checks, review flags, referee disagreements, and three spot rows.
    (Measured failure this fixes: raw dumps invited problem-listing of passing
    checks; digests also keep the judge's window tiny.)"""
    fails = {k: v for k, v in checks.items()
             if (isinstance(v, bool) and v is False) or v is None}
    pts = wykaz.get("punkty") or []
    spot = [dict((k, pts[i].get(k)) for k in ("id", "x", "y", "page"))
            for i in sorted({0, len(pts) // 2, len(pts) - 1})] if pts else []
    d = dict(PASS=checks.get("PASS"),
             kontrole_niezaliczone_lub_nieznane=fails,
             flagi=checks.get("flagi"),
             liczba_punktow=wykaz.get("liczba_punktow"),
             probki_wierszy=spot,
             uwagi_ekstrakcji=wykaz.get("uwagi"),
             naglowek=header)
    if referee:
        d["referee"] = dict(status=referee.get("status"),
                            zgodne=referee.get("zgodne"),
                            tylko_llm=referee.get("tylko_llm"),
                            niezgodne=(referee.get("niezgodne") or [])[:5],
                            pominiete=(referee.get("pominiete_przez_llm")
                                       or [])[:5])
    return d


def stage_werdyktor(job, header, wykaz, checks, klas=None, referee=None):
    payload = ((_hint_block(klas, ["cel_pracy", "uklad_wspolrzednych"])
                if klas else "")
               + "DIGEST KONTROLI (zbudowany przez program):\n"
               + json.dumps(_digest(header, wykaz, checks, referee),
                            ensure_ascii=False)
               + "\n\nZADANIE: wydaj werdykt wg kontraktu.")
    out = llm.call_agent("werdyktor", payload, model_key="worker", max_tokens=1600,
                         profile="judge")
    _save(job, "werdykt.json", out, sub="verdict")
    if isinstance(out.get("raport_md"), str):
        with open(os.path.join(stages.JOBS, job, "verdict", "report.md"), "w",
                  encoding="utf-8") as f:
            f.write(out["raport_md"])
    return out


def _save(job, fname, obj, sub="extracted"):
    d = os.path.join(stages.JOBS, job, sub)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, fname), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def run_llm(pdf_path, name=None, verdict=False, chapters=True):
    t0 = time.perf_counter()
    job = stages.create_job(pdf_path, name)
    sv = stages.stage_pages(job)
    pdf = os.path.join(stages.JOBS, job, "source", "operat.pdf")
    if chapters:
        stages.stage_mapa(job)         # docmap carries the chapters key later
    klas = stage_klasyfikator(job, pdf, sv)
    print("[klasyfikator]", json.dumps(klas, ensure_ascii=False)[:300], flush=True)
    hdr = stage_naglowek_llm(job, pdf, sv, klas)
    print("[naglowek]", json.dumps({k: v for k, v in hdr.items()
                                    if k != 'zrodla'}, ensure_ascii=False)[:300],
          flush=True)
    wyk = stage_wykaz_llm(job, pdf, sv, klas)
    print(f"[wykaz] {wyk['liczba_punktow']} pkt, uwagi: {wyk['uwagi']}", flush=True)

    checks = finish_llm_job(job, pdf, sv, klas, hdr, wyk)
    outs = stages.stage_outputs(job) if json.load(
        open(os.path.join(stages.JOBS, job, "extracted", "wykaz.json"),
             encoding="utf-8"))["punkty"] else []
    referee = json.load(open(os.path.join(stages.JOBS, job, "extracted",
                                          "referee.json"), encoding="utf-8"))
    hdr_code = json.load(open(os.path.join(stages.JOBS, job, "extracted",
                                           "header.json"), encoding="utf-8"))
    v = stage_werdyktor(job, hdr_code, wyk, checks, klas, referee) \
        if verdict else None
    if chapters:
        # fusion phase A+summary surface (panel 06.08): walker -> assembly
        # with gates -> media descriptions -> chapter summaries. Runs after
        # the domain crew, before the seal — the pieczec covers everything.
        import walker as walker_mod
        import rozdzialy
        import opisy
        import podsumowania
        jdir = os.path.join(stages.JOBS, job)
        claims = walker_mod.walk(job, pdf)
        chdoc = rozdzialy.rozdzialy_job(
            job, pdf, claims=walker_mod.confirmed_claims(claims))
        stages._log(jdir, "rozdzialy",
                    f"{len(chdoc['rozdzialy'])} rozdzialow",
                    G11=chdoc["podzial_kompletny"],
                    G12=chdoc["tytuly_ugruntowane"],
                    nieoznaczone=chdoc["nieoznaczone"])
        print(f"[rozdzialy] {len(chdoc['rozdzialy'])} rozdz., "
              f"G11={chdoc['podzial_kompletny']} "
              f"G12={chdoc['tytuly_ugruntowane']}", flush=True)
        med = opisy.describe_media(job, pdf)
        stages._log(jdir, "media", f"{len(med)} obrazow opisanych")
        print(f"[media] {len(med)} obrazow", flush=True)
        if chdoc["rozdzialy"]:
            ps = podsumowania.phase_podsumowania(job)
            stages._log(jdir, "podsumowania",
                        f"{ps['rozdzialy']} streszczen",
                        fakty=ps["fakty"],
                        fakty_ugruntowane=ps["fakty_ugruntowane"])
            print(f"[podsumowania] {ps['rozdzialy']} rozdz., "
                  f"{ps['fakty']} faktow", flush=True)
    stages.stage_pieczec(job)          # seal AFTER the verdict artifact lands
    dt = time.perf_counter() - t0
    print(f"[done] job={job} checks_PASS={checks.get('PASS')} "
          f"outputs={len(outs)} verdict={v.get('werdykt') if v else '-'} "
          f"{dt:.0f}s", flush=True)
    return dict(job=job, klasyfikacja=klas, checks=checks, verdict=v)


def finish_llm_job(job, pdf, sv, klas, hdr, wyk):
    """CODE finishes what the models transcribed: contract mapping, gates
    (grounding, referee, G4), invariants. Shared by auto and supervised crews."""
    # map LLM outputs onto the code-stage contracts, then CODE does the rest
    hdr_code = dict(cel_pracy=hdr.get("cel_pracy"),
                    id_zgloszenia=hdr.get("id_zgloszenia"),
                    dzialka=(hdr.get("dzialki") or [None])[0],
                    uklad=hdr.get("uklad"), wykonawca=hdr.get("wykonawca"),
                    nr_uprawnien=hdr.get("nr_uprawnien"),
                    data_pomiaru=hdr.get("data_pomiaru"),
                    data_sporzadzenia=hdr.get("data_sporzadzenia"),
                    rodzaj_aktu=hdr.get("rodzaj_aktu"),
                    strona_wykazu=wyk.get("strona_wykazu"))
    _save(job, "header.json", hdr_code)
    wyk_code = dict(punkty=[dict(id=p.get("id"), x=p.get("x"), y=p.get("y"),
                                 zrd=p.get("zrd"), bpp=p.get("bpp"),
                                 stb=p.get("stb"), rzg=p.get("rzg"),
                                 status=p.get("status"), page=p.get("page"))
                            for p in wyk["punkty"]
                            if isinstance(p.get("x"), (int, float))],
                    strona_wykazu=wyk.get("strona_wykazu"),
                    liczba_punktow=wyk["liczba_punktow"])
    _save(job, "wykaz.json", wyk_code)

    # G2 grounding: extracted values must exist in the document (and on the
    # claimed pages); G3 referee: the regex parser cross-checks every LLM row
    # on text-layer pages — both BEFORE checks so invariants absorb them
    ocr_texts = {}
    for r in sv:
        if not r["has_text"]:
            t, _ = _page_text(job, pdf, r["page"])
            if t:
                ocr_texts[r["page"]] = t
    grounding = stages.grounding_check(pdf, hdr_code, hdr.get("zrodla"),
                                       ocr_texts)
    _save(job, "grounding.json", grounding)
    parsed = {r["page"]: stages.parse_rows(text_layer(pdf, r["page"]))
              for r in sv if r["has_text"]}
    referee = stages.referee_wykaz(parsed, wyk_code["punkty"])
    _save(job, "referee.json", referee)

    # G4 dual-OCR agreement on scan pages: a coordinate the LLM transcribed
    # counts as CONFIRMED only when BOTH engines read it; one engine = review
    # flag; neither = hard fail (hallucination-on-scan analog of G2)
    scan_pages = sorted({p["page"] for p in wyk_code["punkty"]
                         if p.get("page") in ocr_texts})
    if scan_pages:
        import ocr as ocrmod
        gate = dict(dostepny_drugi=ocrmod.second_available(),
                    strony={}, tylko_jeden=[], zaden=[])
        for n in scan_pages:
            second = ""
            if gate["dostepny_drugi"]:
                second = ocrmod.ocr_page_second(os.path.join(
                    stages.JOBS, job, "pages", f"page-{n:03d}.png"))
            agr = ocrmod.coord_agreement(ocr_texts[n], second)
            gate["strony"][str(n)] = agr
            both = set(agr["obie"])
            one = set(agr["tylko_pierwszy"]) | set(agr["tylko_drugi"])
            for p in wyk_code["punkty"]:
                if p["page"] != n:
                    continue
                for coord in (f"{p['x']:.2f}", f"{p['y']:.2f}"):
                    if coord in both:
                        continue
                    (gate["tylko_jeden"] if coord in one
                     else gate["zaden"]).append(
                        dict(id=p["id"], wsp=coord, strona=n))
        _save(job, "scan_gate.json", gate)
        print(f"[gates] G4 dual-OCR: potwierdzone_obiema="
              f"{sum(len(v['obie']) for v in gate['strony'].values())} "
              f"jeden_silnik={len(gate['tylko_jeden'])} "
              f"zaden={len(gate['zaden'])}", flush=True)
    print(f"[gates] grounding: w_dok={grounding['wartosci_w_dokumencie']} "
          f"zrodla={grounding['zrodla_trafne']} | referee: {referee['status']} "
          f"(zgodne {referee['zgodne']}, niezgodne {len(referee['niezgodne'])}, "
          f"pominiete {len(referee['pominiete_przez_llm'])})", flush=True)

    return stages.stage_checks(job)


if __name__ == "__main__":
    # Windows gives a redirected or DEVNULL stdout the ANSI code page
    # (cp1252), and the first Polish letter in a log line would raise
    # UnicodeEncodeError and kill the run; UTF-8 with replacement never does.
    for _s in (sys.stdout, sys.stderr):
        if _s is not None and hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--job")
    ap.add_argument("--verdict", action="store_true")
    a = ap.parse_args()
    try:
        run_llm(a.pdf, a.job, a.verdict)
    finally:
        llm.stop()
