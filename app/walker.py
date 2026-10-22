# geodoc — the sequential chapter WALKER (panel-shaped, 06.08): agent N
# starts where N-1 ended and claims where the current chapter ends and where
# the next begins. Laws baked in:
#   - CLAIMS ONLY: the walker writes chapters_claims.json; it never creates
#     folders, never re-transcribes, never touches the PDF — assembly and
#     materialization are pure code over immutable page transcripts.
#   - CODE CONTAINMENT: the walker chooses among CODE-detected heading
#     candidates (or abstains) — it cannot invent a boundary page.
#   - MONOTONE: enforced in code; a claim can never move the cursor backward.
#   - ABSTENTION-FIRST: pewnosc "niska" is a recorded observation, not a
#     boundary; unanchored spans become `nieoznaczony` at assembly.
# Runs entirely on the WORKER (30B) — the client box pays zero model swaps
# in phase A (judge-2 lens: per-chapter 80B calls would mean swap hell).

import json
import os

import llm
import rozdzialy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOBS = os.path.join(ROOT, "jobs")

WINDOW = 6          # pages per hop; transcripts are a few hundred tokens each


def _transcript(job, n):
    # md when it carries text, OCR transcript for scan pages — the walker
    # walks scans through OCR (owner's heavy-OCR page-by-page reality)
    return rozdzialy.page_text_job(job, n)


def _default_runner(payload):
    return llm.call_agent("detektor_rozdzialow", payload, max_tokens=400)


def walk(job, pdf_path, runner=None, window=WINDOW):
    """The chain. Each hop sees: chain state (where the previous chapter
    ended, current title), CODE candidates inside the window, and the window's
    page transcripts. Returns the claims list; writes chapters_claims.json."""
    runner = runner or _default_runner
    from pdfpages import page_count
    total = page_count(pdf_path)
    # scan branch: same idempotent OCR pass the assembler uses — without it
    # a scan document yields ZERO candidates and containment (correctly)
    # confirms nothing; the walker must see what the code sees
    boxes = rozdzialy.ocr_all_raster(job, pdf_path)
    cands = rozdzialy.heading_candidates(pdf_path, ocr_boxes=boxes or None)
    claims, start, hop = [], 1, 0
    prev_title = None
    while start <= total:
        hop += 1
        end_w = min(start + window - 1, total)
        wnd_c = [c for c in cands if start <= c["page"] <= end_w]
        cand_lines = "\n".join(
            f"- s. {c['page']}: \"{c['text']}\" (poziom {c['level']})"
            for c in wnd_c) or "- (brak kandydatow z detekcji kodu w oknie)"
        pages_block = "\n\n".join(
            f"=== s. {n} ===\n{_transcript(job, n)[:1200]}"
            for n in range(start, end_w + 1))
        payload = (
            f"STAN LANCUCHA: analizujesz od s. {start} z {total}. "
            + (f"Poprzedni rozdzial: \"{prev_title}\" zakonczyl sie na "
               f"s. {start - 1}." if prev_title else
               "To poczatek dokumentu (szukaj spisu tresci / pierwszego "
               "rozdzialu).")
            + f"\n\nKANDYDACI NAGLOWKOW (detekcja kodu — wybieraj TYLKO "
              f"z tych stron albo wstrzymaj sie):\n{cand_lines}"
            + f"\n\n===DOKUMENT===\n{pages_block}\n===KONIEC===\n\n"
            f"ZADANIE: wskaz gdzie zaczyna sie NASTEPNY rozdzial w oknie "
            f"(strona + tytul) i czy dokument konczy sie w tym oknie.")
        out = runner(payload) or {}
        claim = dict(
            hop=hop, okno=[start, end_w],
            nastepny_start=out.get("nastepny_start"),
            nastepny_tytul=out.get("nastepny_tytul"),
            pewnosc=out.get("pewnosc") or "niska",
            koniec_dokumentu=bool(out.get("koniec_dokumentu")))
        # code containment: a claimed start must be a candidate page ahead
        ns = claim["nastepny_start"]
        if ns is not None:
            if not any(c["page"] == ns for c in wnd_c) or ns <= start - 1:
                claim["pewnosc"] = "odrzucona-przez-kod"
                claim["nastepny_start"] = None
                ns = None
        claims.append(claim)
        if claim["koniec_dokumentu"] and ns is None:
            break
        if ns is not None:
            prev_title = claim["nastepny_tytul"] or prev_title
            start = max(ns + 1, start + 1)          # monotone law
        else:
            start = end_w + 1
    path = os.path.join(JOBS, job, "extracted", "chapters_claims.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(claims, open(path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    return claims


def confirmed_claims(claims):
    """Claims usable by assembly: high confidence, code-contained."""
    return [c for c in claims or []
            if c.get("nastepny_start") and c.get("pewnosc") == "wysoka"]
