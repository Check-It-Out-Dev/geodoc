# geodoc — Rozmowa: the conversation-first layer (owner 16:37). The unit the
# operator sees is a CONVERSATION about one document: the PDF is dropped INTO
# the chat, pipeline stages arrive as messages with approve/retry actions,
# generated files land as attachments, and the SAME context continues as the
# after-run Q&A (rewident) — one thread, persisted, resumable. Machine state
# (job artifacts) stays where it was; this module binds it to a chat context
# and narrates it. The operator closes a conversation with a MARKER:
# brak / zatwierdzona / odrzucona — the human verdict, distinct from PASS.

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import crew  # noqa: E402
import stages  # noqa: E402
import store  # noqa: E402
import teksty  # noqa: E402

MARKERY = ("brak", "zatwierdzona", "odrzucona")

POWITANIE = ("Przyjąłem dokument {plik}. Przetwarzanie przebiega etapami — "
             "po każdym etapie zobaczysz wynik i zdecydujesz: zatwierdzić "
             "czy powtórzyć z dopiskiem. W każdej chwili możesz też zadać "
             "pytanie o dotychczasowe dane.")


def start(pdf_path, nazwa=None):
    """Open a conversation around a document: crew job + bound context +
    the opening exchange (file-drop message, assistant welcome)."""
    import re
    r = crew.start(pdf_path, nazwa)
    job = r["job"]
    plik = re.sub(r"^\d{8}-\d{6}-", "", os.path.basename(pdf_path))
    ctx = store.create(role="rozmowa", model="analityk", job=job,
                       nazwa=plik, marker="brak")
    # rewident laws bind from the FIRST message (digest note = system hook);
    # the full post-run digest arrives later IN-WINDOW (prefix stays stable)
    store.append(ctx, "note",
                 f"Rozmowa dotyczy dokumentu {plik} (zadanie {job}). "
                 "Etapy przetwarzania są raportowane w tej rozmowie; "
                 "fragmenty dokumentu dokleja program przy pytaniach.",
                 kind="digest")
    store.append(ctx, "user", f"[dokument] {plik}", kind="plik", plik=plik)
    store.append(ctx, "assistant", POWITANIE.format(plik=plik),
                 kind="powitanie")
    return dict(rozmowa=ctx, job=job, next_stage=r["next_stage"])


def _strony(nn):
    nn = nn or []
    if not nn:
        return None
    if len(nn) == 1:
        return f"strona {nn[0]}"
    return "strony " + ", ".join(str(n) for n in nn)


def _skrot_etapu(stage, out):
    """Stage result narrated for a HUMAN (owner 16:5x): label: value lines,
    no field names, no True/False, no list dumps — a first-time user must
    understand every line."""
    if out.get("_error"):
        return f"Nie udało się wykonać etapu — {out['_error']}"
    if stage == "klasyfikator":
        w = []
        w.append("Typ dokumentu: "
                 + (out.get("typ_dokumentu") or "operat techniczny"))
        ma = out.get("ma_wykaz_granic")
        sw = _strony(out.get("strony_wykazu_kandydaci"))
        w.append("Wykaz współrzędnych: "
                 + ("znaleziony" + (f" ({sw})" if sw else "") if ma is True
                    else "prawdopodobny — sprawdzę dokładnie" if ma == "niepewne"
                    else "nie znaleziono — sprawdzę wszystkie strony"))
        ss = _strony(out.get("strony_sprawozdania_kandydaci"))
        if ss:
            w.append(f"Sprawozdanie techniczne: {ss}")
        return "\n".join(w)
    if stage == "naglowek":
        w = []
        if out.get("id_zgloszenia"):
            w.append(f"Zgłoszenie pracy: {out['id_zgloszenia']}")
        dz = (out.get("dzialki") or [None])[0]
        if dz:
            w.append(f"Działka: {dz}")
        if out.get("uklad"):
            w.append(f"Układ współrzędnych: {out['uklad']}")
        if out.get("wykonawca"):
            w.append("Wykonawca: " + out["wykonawca"]
                     + (f" (upr. {out['nr_uprawnien']})"
                        if out.get("nr_uprawnien") else ""))
        if out.get("data_pomiaru"):
            w.append(f"Data pomiaru: {out['data_pomiaru']}")
        return "\n".join(w) or "Nagłówek odczytany."
    if stage == "wykaz":
        w = [f"Punkty graniczne: {out.get('liczba_punktow', 0)}"
             + (f" (strona {out.get('strona_wykazu')})"
                if out.get("strona_wykazu") else "")]
        if out.get("uwagi"):
            w.append(f"Uwagi do przejrzenia: {len(out['uwagi'])}")
        return "\n".join(w)
    if stage == "werdykt":
        n = len(out.get("problemy") or [])
        v = out.get("werdykt", "—")
        ocena = ("bez zastrzeżeń" if v == "OK" and not n
                 else f"zastrzeżenia: {n} — zapytaj o szczegóły"
                 if n else v)
        return (f"Ocena dokumentu: {v} ({ocena})")
    return "Etap zakończony."


def _zalaczniki(job):
    out_dir = os.path.join(stages.JOBS, job, "out")
    if not os.path.isdir(out_dir):
        return []
    wyn = []
    for f in sorted(os.listdir(out_dir)):
        p = os.path.join(out_dir, f)
        wyn.append(dict(plik=f, bajty=os.path.getsize(p),
                        url=f"/file/{job}/out/{f}"))
    return wyn


def _final(ctx, job):
    """Completion message: checks digest + files as chat attachments + the
    full digest appended IN-WINDOW (append-only truth; KV prefix intact) so
    the same conversation answers post-run questions with rewident grounding."""
    chk = teksty.artefakt(job, "checks", "invariants.json") or {}
    # ALWAYS regenerate outputs at a final — the correction loop rewrites
    # extracted data, and a fresh promise over stale files would be a lie
    # (caught live 06.08: final #2 said "wygeneruję od nowa", files were
    # from before the correction)
    try:
        stages.stage_outputs(job)
    except Exception:
        pass
    zal = _zalaczniki(job)
    pass_ = chk.get("PASS") is True
    # maszyna raportuje FAKTY (obróbka, kontrole); orzeka CZŁOWIEK markerem
    # — „pieczęć nadana” w ustach programu to uzurpacja (owner 18:19)
    tekst = (("Obróbka dokumentu zakończona. Wszystkie kontrole zaliczone. "
              if pass_ else
              "Obróbka dokumentu zakończona. Część kontroli się nie "
              "powiodła — sprawdź, co się nie zgadza. ")
             + ((f"Przygotowałem "
                 + ("1 plik wynikowy" if len(zal) == 1 else
                    f"{len(zal)} pliki wynikowe" if 2 <= len(zal) <= 4 else
                    f"{len(zal)} plików wynikowych")
                 + " — możesz je pobrać poniżej. ")
                if zal else "")
             + "Jeśli coś wymaga poprawy, wskaż etap i napisz, co zmienić "
             "— przeliczę go ponownie razem z plikami. Możesz też po "
             "prostu pytać o wyniki.")
    store.append(ctx, "assistant", tekst, kind="final",
                 zalaczniki=zal, pass_=pass_)
    import rewizja
    store.append(ctx, "user",
                 "AKTUALNY DIGEST OPERATU (po przetworzeniu, policzony "
                 "przez program):\n" + rewizja.digest(job),
                 kind="digest", pytanie="[digest po przetworzeniu]")
    # a header-named conversation reads better than a job id in the rail
    hdr = teksty.artefakt(job, "extracted", "header.json") or {}
    dz = hdr.get("dzialka")
    if dz:
        m = store.meta(ctx)
        store.set_meta(ctx, nazwa=f"{m.get('nazwa')} · dz. {dz}")


def krok(ctx, action="run", dopisek=None, runner=None):
    """One conversation step of the pipeline: crew.step + the narration
    appended to the SAME chat context. Returns crew's state + the message."""
    m = store.meta(ctx)
    job = m["job"]
    if dopisek:
        store.append(ctx, "user", dopisek, kind="dopisek",
                     stage=crew.STAGES[crew._load(job)["cursor"]])
    r = crew.step(job, action, dopisek, runner=runner)
    if r.get("awaiting"):
        w = _skrot_etapu(r["stage"], r.get("wynik") or {})
        store.append(ctx, "assistant", w, kind="etap", stage=r["stage"],
                     prompt_hash=r.get("prompt_hash"))
        r["wiadomosc"] = w
    elif r.get("done"):
        _final(ctx, job)
    return r


ETAP_LUDZKI = dict(klasyfikator="klasyfikacja dokumentu",
                   naglowek="nagłówek operatu",
                   wykaz="wykaz współrzędnych", werdykt="ocena końcowa")


def popraw(ctx, stage, dopisek, runner=None):
    """The satisfaction loop: after files exist the operator can still send
    a stage back with an instruction — downstream stages re-run and the
    files regenerate at a fresh final message."""
    m = store.meta(ctx)
    job = m["job"]
    crew.cofnij(job, stage)
    store.append(ctx, "user", dopisek, kind="dopisek", stage=stage)
    store.append(ctx, "assistant",
                 f"Wracam do etapu „{ETAP_LUDZKI.get(stage, stage)}” "
                 "z Twoją uwagą. Kolejne etapy przeliczę ponownie, "
                 "a pliki wynikowe wygeneruję od nowa.",
                 kind="powrot", stage=stage)
    r = crew.step(job, "retry", dopisek, runner=runner)
    if r.get("awaiting"):
        w = _skrot_etapu(r["stage"], r.get("wynik") or {})
        store.append(ctx, "assistant", w, kind="etap", stage=r["stage"],
                     prompt_hash=r.get("prompt_hash"))
        r["wiadomosc"] = w
    return r


def przetworz_ponownie(job):
    """Batch/auto-processed document pulled INTO a supervised conversation:
    a fresh chat starts from the job's own source PDF."""
    src = os.path.join(stages.JOBS, job, "source", "operat.pdf")
    if not os.path.isfile(src):
        raise FileNotFoundError("brak pliku źródłowego dokumentu")
    nazwa = _nazwa_joba(job)
    r = start(src, None)
    store.set_meta(r["rozmowa"], nazwa=f"{nazwa} (poprawka)")
    return r


def pytanie(ctx, tekst, turn_fn=None):
    """A question inside the conversation — at ANY point of the lifecycle.
    Same retrieval law as rewizja (code picks fragments), same context."""
    import rewizja
    m = store.meta(ctx)
    return rewizja.zapytaj(m["job"], tekst, turn_fn=turn_fn, ctx=ctx)


def marker(ctx, status):
    """The operator's completion marker: brak / zatwierdzona / odrzucona."""
    if status not in MARKERY:
        raise ValueError(f"nieznany marker: {status}")
    store.set_meta(ctx, marker=status,
                   marker_t=time.strftime("%Y-%m-%d %H:%M"))
    return dict(id=ctx, marker=status)


def adoptuj(job):
    """Give an existing job (batch/legacy) a conversation identity: the
    rail's marker and further questions need a context; artifacts untouched."""
    ctx = None
    for m in store.listing():
        if m.get("job") == job and m.get("role") in ("rozmowa", "rewident"):
            ctx = m["id"]
            break
    if not ctx:
        import rewizja
        ctx = store.create(role="rozmowa", model="analityk", job=job,
                           nazwa=_nazwa_joba(job), marker="brak")
        store.append(ctx, "note", rewizja.digest(job), kind="digest")
    return dict(rozmowa=ctx, job=job)


def _nazwa_joba(job):
    """Legacy jobs (no conversation yet): document-first naming — działka
    from the header, else the ingested file name, else the job id."""
    hdr = teksty.artefakt(job, "extracted", "header.json") or {}
    if hdr.get("dzialka"):
        return f"dz. {hdr['dzialka']}"
    logp = os.path.join(stages.JOBS, job, "tasks", "log.jsonl")
    if os.path.isfile(logp):
        try:
            first = json.loads(open(logp, encoding="utf-8").readline())
            src = (first.get("msg") or "")
            if "source copied from" in src:
                return os.path.basename(src.split("source copied from")[-1]
                                        .strip())
        except Exception:
            pass
    return job


def _kolejki_map():
    """job -> kolejka bid (batch grouping for the rail)."""
    mapa = {}
    root = stages.JOBS
    if not os.path.isdir(root):
        return mapa
    for d in os.listdir(root):
        if not d.startswith("kolejka-"):
            continue
        try:                        # tolerate pre-fix torn state files
            st = teksty.jread(os.path.join(root, d, "kolejka.json")) or {}
        except Exception:
            continue
        for it in st.get("items") or []:
            if it.get("job"):
                mapa[it["job"]] = d[len("kolejka-"):]
    return mapa


def lista():
    """The rail: every conversation and every job AS a conversation entry —
    document-named, machine status + human marker."""
    wyn = []
    zajete = set()
    kol = _kolejki_map()
    for m in store.listing():
        if m.get("role") not in ("rozmowa", "rewident"):
            continue
        job = m.get("job")
        zajete.add(job)
        chk = teksty.artefakt(job, "checks", "invariants.json") if job else None
        wyn.append(dict(id=m["id"], job=job,
                        nazwa=m.get("nazwa") or (job and _nazwa_joba(job))
                        or m["id"],
                        kolejka=kol.get(job),
                        marker=m.get("marker", "brak"),
                        maszyna=(None if chk is None
                                 else bool(chk.get("PASS"))),
                        turns=m.get("turns", 0), t=m.get("created")))
    root = stages.JOBS
    jobs = sorted(os.listdir(root)) if os.path.isdir(root) else []
    for j in jobs:
        if j in zajete or j.startswith("kolejka-") or j.startswith("_"):
            continue
        if not os.path.isdir(os.path.join(root, j)):
            continue
        chk = teksty.artefakt(j, "checks", "invariants.json")
        wyn.append(dict(id=None, job=j, nazwa=_nazwa_joba(j),
                        kolejka=kol.get(j),
                        marker="brak",
                        maszyna=(None if chk is None
                                 else bool(chk.get("PASS"))),
                        turns=0, t=None))
    wyn.sort(key=lambda r: (r["t"] or "", r["job"] or ""), reverse=True)
    return wyn
