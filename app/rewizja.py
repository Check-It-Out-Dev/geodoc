# geodoc — Rewizja: the after-run feedback loop (owner 06.08 12:38). The
# operator interrogates a COMPLETED job in chat; every question spawns one
# grounded analysis by the analityk under the rewident manual. Retrieval is
# CODE's job (deterministic routing of pages/points/chapters/keywords into
# the payload — the model never searches); the conversation is a job-bound
# context (KV resume, AutoCompact, append-only truth), and every exchange
# is mirrored to jobs/<job>/analizy/rewizja.md beside the documents.
# Analyses are post-hoc and operator-ordered: they live OUTSIDE the pieczec
# sweep by design (the seal proves the pipeline; rewizja is conversation).

import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import teksty  # noqa: E402
import store  # noqa: E402

MAX_STRON = 5          # fragment budget per question
MAX_ZNAKOW = 2800      # per-page excerpt cap

_STOP = {"czy", "jaka", "jaki", "jakie", "gdzie", "kiedy", "dlaczego",
         "sprawdz", "sprawdzic", "strona", "strony", "stronie", "rozdzial",
         "rozdziale", "punkt", "punktu", "punkty", "operat", "operacie",
         "prosze", "podaj", "pokaz", "czego", "ktora", "ktory", "przez",
         "jest", "byla", "byly", "zgadza", "wykaz", "dane"}

_RE_STRONA = re.compile(r"(?:\bs\.|\bstr\.?|\bstron[aey]?)\s*(\d{1,3})")
_RE_ROZDZ = re.compile(r"rozdzia\w*\s+(\d{1,2})")


def _art(job, *parts, jobs_root=None):
    return teksty.artefakt(job, *parts, jobs_root=jobs_root)


def digest(job, jobs_root=None):
    """The context primer built BY CODE from artifacts — stable for the
    context's lifetime (KV prefix law: computed once, stored as a note)."""
    hdr = _art(job, "extracted", "header.json", jobs_root=jobs_root) or {}
    chk = _art(job, "checks", "invariants.json", jobs_root=jobs_root) or {}
    wyk = _art(job, "extracted", "wykaz.json", jobs_root=jobs_root) \
        or {"punkty": []}
    dm = _art(job, "docmap.json", jobs_root=jobs_root) or {}
    pts = wyk.get("punkty") or []
    lines = [f"OPERAT {job}",
             f"Cel: {hdr.get('cel_pracy')} · zgłoszenie {hdr.get('id_zgloszenia')}"
             f" · działka {hdr.get('dzialka')} · układ {hdr.get('uklad')}",
             f"Wykonawca: {hdr.get('wykonawca')} (upr. {hdr.get('nr_uprawnien')})"
             f" · pomiar {hdr.get('data_pomiaru')} · operat {hdr.get('data_sporzadzenia')}"]
    zle = [k for k, v in chk.items() if v is False]
    flagi = chk.get("flagi") or {}
    nfl = {k: len(v) if isinstance(v, list) else 1 for k, v in flagi.items()}
    lines.append(f"KONTROLE: {'PASS' if chk.get('PASS') else 'FAIL'}"
                 + (f" · niezaliczone: {', '.join(zle)}" if zle else "")
                 + (f" · flagi: {nfl}" if nfl else " · flagi: brak"))
    if pts:
        xs = [p["x"] for p in pts if isinstance(p.get("x"), (int, float))]
        ys = [p["y"] for p in pts if isinstance(p.get("y"), (int, float))]
        lines.append(f"WYKAZ: {len(pts)} pkt, s. {wyk.get('strona_wykazu')}"
                     + (f", X {min(xs):.0f}–{max(xs):.0f}"
                        f", Y {min(ys):.0f}–{max(ys):.0f}" if xs and ys else ""))
        try:
            import stages
            import uklady
            det = uklady.wykryj_uklad(hdr.get("uklad"), pts)
            _, przel = uklady.przelicz_punkty(pts, det)
            pew = stages.pewnosc_punktow(pts, chk, przel.get("uwaga"))
            tally = {}
            for v in pew.values():
                tally[v["tier"]] = tally.get(v["tier"], 0) + 1
            nie_pewne = [f"{pid} ({d['tier']}: {'; '.join(d['powody'])})"
                         for pid, d in pew.items() if d["tier"] != "PEWNE"]
            lines.append("PEWNOŚĆ: " + ", ".join(
                f"{k} {v}" for k, v in sorted(tally.items())))
            if nie_pewne:
                lines.append("DO RECENZJI: " + " | ".join(nie_pewne[:12]))
        except Exception:
            pass
    ch = (dm.get("chapters") or {})
    if ch.get("rozdzialy"):
        lines.append("ROZDZIAŁY: " + " · ".join(
            f"{c['nr']}. {c['tytul']} (s. {c['od']}–{c['do']})"
            for c in ch["rozdzialy"]))
    for z in ch.get("nieoznaczone") or []:
        lines.append(f"NIEOZNACZONE: s. {z[0]}–{z[1]}")
    braki = (dm.get("braki") or {})
    for u in braki.get("uwagi") or []:
        lines.append(f"UWAGA: {u}")
    src = dm.get("source") or {}
    if src.get("pages"):
        lines.append(f"STRON: {src['pages']}")
    return "\n".join(lines)


def wybierz_fragmenty(job, pytanie, jobs_root=None):
    """Deterministic retrieval: explicit pages > mentioned point IDs >
    chapter references > folded-keyword scoring over page cores. Returns
    (fragment_text, source_page_list)."""
    dm = _art(job, "docmap.json", jobs_root=jobs_root) or {}
    n_stron = (dm.get("source") or {}).get("pages") or 0
    wyk = _art(job, "extracted", "wykaz.json", jobs_root=jobs_root) \
        or {"punkty": []}
    pts = wyk.get("punkty") or []
    fold_q = teksty.fold(pytanie)

    strony = []                      # ordered, unique

    def dodaj(n):
        if isinstance(n, int) and 1 <= n <= max(n_stron, 1) \
                and n not in strony and len(strony) < MAX_STRON:
            strony.append(n)

    for m in _RE_STRONA.finditer(fold_q):
        dodaj(int(m.group(1)))

    pkt_hit = [p for p in pts if p.get("id") and str(p["id"]) in pytanie]
    for p in pkt_hit:
        dodaj(p.get("page"))

    ch = (dm.get("chapters") or {}).get("rozdzialy") or []
    for m in _RE_ROZDZ.finditer(fold_q):
        nr = int(m.group(1))
        for c in ch:
            if c.get("nr") == nr:
                for n in range(c["od"], min(c["do"], c["od"] + 2) + 1):
                    dodaj(n)

    if len(strony) < MAX_STRON and n_stron:
        slowa = [w for w in re.findall(r"[a-z0-9]{4,}", fold_q)
                 if w not in _STOP]
        wyniki = []
        for n in range(1, n_stron + 1):
            if n in strony:
                continue
            core = teksty.page_core(
                teksty.page_text(job, n, jobs_root=jobs_root))
            score = sum(core.count(w) for w in slowa)
            if score:
                wyniki.append((score, n))
        for _, n in sorted(wyniki, reverse=True):
            dodaj(n)

    czesci = []
    if pkt_hit:
        czesci.append("PUNKTY Z WYKAZU (wiersze wprost z ekstrakcji):\n" +
                      "\n".join(
                          f"  {p.get('id')}: X={p.get('x')} Y={p.get('y')} "
                          f"ZRD={p.get('zrd')} BPP={p.get('bpp')} "
                          f"STB={p.get('stb')} RZG={p.get('rzg')} "
                          f"status={p.get('status')} s.{p.get('page')}"
                          for p in pkt_hit[:20]))
    for n in strony:
        txt = (teksty.page_text(job, n, jobs_root=jobs_root) or "").strip()
        czesci.append(f"=== STRONA {n} ===\n{txt[:MAX_ZNAKOW]}")
    return ("\n\n".join(czesci) if czesci
            else "(kod nie dobrał żadnej strony — odpowiadaj z DIGESTU "
                 "albo poproś operatora o numer strony)"), strony


def _znajdz_ctx(job):
    for m in store.listing():
        if m.get("role") in ("rewident", "rozmowa") and m.get("job") == job:
            return m["id"]
    return None


def zapytaj(job, pytanie, turn_fn=None, jobs_root=None, ctx=None):
    """One rewizja exchange. Uses the given conversation context (rozmowa)
    or finds/creates the job-bound one, routes fragments by code, runs the
    chat turn, and mirrors the exchange into jobs/<job>/analizy/rewizja.md."""
    if turn_fn is None:
        import chat
        turn_fn = chat.turn
    ctx = ctx or _znajdz_ctx(job)
    if not ctx:
        ctx = store.create(role="rewident", model="analityk", job=job)
        store.append(ctx, "note", digest(job, jobs_root=jobs_root),
                     kind="digest")
    frag, strony = wybierz_fragmenty(job, pytanie, jobs_root=jobs_root)
    payload = (f"PYTANIE OPERATORA:\n{pytanie}\n\n"
               f"FRAGMENTY OPERATU (dobrane przez kod):\n{frag}")
    out = turn_fn(ctx, payload,
                  user_extra=dict(pytanie=pytanie, zrodla=strony))
    odp = out.get("reply") or ""
    adir = os.path.join(jobs_root or teksty.JOBS, job, "analizy")
    os.makedirs(adir, exist_ok=True)
    with open(os.path.join(adir, "rewizja.md"), "a", encoding="utf-8") as f:
        zr = ", ".join(f"s. {n}" for n in strony) or "digest"
        f.write(f"## {time.strftime('%Y-%m-%d %H:%M')} · {pytanie}\n\n"
                f"**Rewident** (materiał: {zr}):\n\n{odp}\n\n---\n\n")
    return dict(ctx_id=ctx, odpowiedz=odp, zrodla=strony,
                utilization=out.get("utilization"))


def rozmowa(job):
    """Paired Q/A view for the UI card (raw payloads stay in the context
    transcript — the audit view; here only the operator-facing pairs)."""
    ctx = _znajdz_ctx(job)
    if not ctx:
        return dict(ctx_id=None, wpisy=[])
    wpisy = []
    for r in store.transcript(ctx):
        if r.get("role") == "user":
            wpisy.append(dict(pytanie=r.get("pytanie") or r.get("content"),
                              zrodla=r.get("zrodla") or [], odpowiedz=None,
                              t=r.get("t")))
        elif r.get("role") == "assistant" and wpisy:
            wpisy[-1]["odpowiedz"] = r.get("content")
    return dict(ctx_id=ctx, wpisy=wpisy)
