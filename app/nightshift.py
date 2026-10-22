# geodoc — Nocna zmiana: drop a list of operaty in the evening, read one
# morning report with coffee. A single worker thread runs auto-mode crews
# sequentially (the per-model queue law — zero swaps inside a batch) and
# writes raport_poranny.md: per job PASS/verdict/flag-count with links.
# Batch state lives under jobs/kolejka-<id>/ so the existing /file scope
# serves the report with no new endpoints.

import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import agents  # noqa: E402
import stages  # noqa: E402
import teksty  # noqa: E402

_worker = None
_lock = threading.Lock()


def _batch_dir(bid):
    return os.path.join(stages.JOBS, f"kolejka-{bid}")


def _state_path(bid):
    return os.path.join(_batch_dir(bid), "kolejka.json")


def _load(bid):
    st = teksty.jread(_state_path(bid))    # retries the Windows replace seam
    if st is None:
        raise FileNotFoundError(f"kolejka {bid}")
    return st


def _save(bid, st):
    teksty.jsave(_state_path(bid), st)   # atomic: server threads read live


def submit(pdf_paths, runner=None):
    """Queue a batch; returns its id. Unknown paths are marked immediately."""
    # microsecond-unique: two submits in one SECOND collided on one dir
    # and interleaved writers tore kolejka.json (suite caught it live)
    from datetime import datetime
    bid = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    os.makedirs(_batch_dir(bid), exist_ok=True)
    items = [dict(pdf=p, status=("czeka" if os.path.isfile(p) else "blad"),
                  blad=(None if os.path.isfile(p) else "plik nie istnieje"),
                  job=None, PASS=None, werdykt=None)
             for p in pdf_paths]
    _save(bid, dict(id=bid, items=items, done=False))
    _ensure_worker(bid, runner or _run_one)
    return bid


def _run_one(pdf):
    res = agents.run_llm(pdf, verdict=True)
    checks = res.get("checks") or {}
    v = res.get("verdict") or {}
    flagi = checks.get("flagi") or {}
    n_flags = sum(len(x) if isinstance(x, list) else 1
                  for x in flagi.values()) if flagi else 0
    return dict(job=res["job"], PASS=checks.get("PASS"),
                werdykt=v.get("werdykt"), flagi=n_flags)


_pending = []          # bids queued behind a live worker (audit find: a
                       # submit during an alive worker was silently LOST —
                       # its batch stayed 'czeka' forever)


def _ensure_worker(bid, runner):
    global _worker
    with _lock:
        _pending.append((bid, runner))
        if _worker and _worker.is_alive():
            return
        _worker = threading.Thread(target=_drain, daemon=True)
        _worker.start()


_current = None        # bid under processing — the batch-mode indicator


def _drain():
    global _current
    while True:
        with _lock:
            if not _pending:
                return
            bid, runner = _pending.pop(0)
            _current = bid
        try:
            _process(bid, runner)
        finally:
            with _lock:
                _current = None


def active():
    """Batch-mode probe for UI + mode-exclusion guards: the bid being
    processed now (or queued next), else None."""
    with _lock:
        if _current:
            return _current
        return _pending[0][0] if _pending else None


def postep(bid):
    """Progress + ETA for the queue bar: counts, current file, and a
    seconds estimate from the mean of completed items (None until the
    first item lands — an honest 'brak danych', never a guess)."""
    st = _load(bid)
    items = st["items"]
    skonczone = [i for i in items if i["status"] in ("done", "blad")]
    czas = [i["sekundy"] for i in skonczone if i.get("sekundy")]
    zostalo = sum(1 for i in items if i["status"] in ("czeka", "w_toku"))
    eta = round(sum(czas) / len(czas) * zostalo) if czas and zostalo else None
    biezacy = next((os.path.basename(i["pdf"]) for i in items
                    if i["status"] == "w_toku"), None)
    return dict(bid=bid, zrobione=len(skonczone), wszystkie=len(items),
                biezacy=biezacy, eta_s=eta, done=st.get("done", False))


_stops = set()         # in-memory truth: the worker's own _save would
                       # clobber a file-only flag (suite caught the race)


def stop(bid):
    """Queue stop: the CURRENT item finishes, the rest are skipped
    (pominiety) and the report records the interruption."""
    with _lock:
        _stops.add(bid)
    st = _load(bid)
    st["stop"] = True                       # for status/UI display only
    _save(bid, st)
    return dict(id=bid, stop=True)


def _process(bid, runner):
    st = _load(bid)
    for it in st["items"]:
        if it["status"] != "czeka":
            continue
        with _lock:
            ciecie = bid in _stops
        if ciecie:                          # operator stopped the queue
            for r in st["items"]:
                if r["status"] == "czeka":
                    r["status"] = "pominiety"
            st["przerwana"] = True
            break
        it["status"] = "w_toku"
        _save(bid, st)
        t0 = time.time()
        try:
            out = runner(it["pdf"])
            it.update(out)
            it["status"] = "done"
        except Exception as e:
            it["status"] = "blad"
            it["blad"] = str(e)[:200]
        it["sekundy"] = round(time.time() - t0, 1)
        _save(bid, st)
    st["done"] = True
    _save(bid, st)
    with _lock:
        _stops.discard(bid)
    _raport(bid, st)


def _raport(bid, st):
    lines = [f"# Raport poranny — kolejka {bid}", ""]
    ok = sum(1 for i in st["items"] if i.get("PASS") is True)
    zrobione = [i for i in st["items"] if i["status"] == "done"]
    lines.append(f"Przetworzono {len(zrobione)}/{len(st['items'])} operatów; "
                 f"kontrole PASS: {ok}/{len(zrobione) or 1}."
                 + (f" Łączny czas {sum(i.get('sekundy', 0) for i in zrobione):.0f} s"
                    f" (śr. {sum(i.get('sekundy', 0) for i in zrobione)/len(zrobione):.0f} s/operat)."
                    if zrobione else ""))
    if st.get("przerwana"):
        pominiete = [i["pdf"] for i in st["items"]
                     if i["status"] == "pominiety"]
        lines.append("")
        lines.append("**Kolejka zatrzymana przez operatora.** Bieżące "
                     "zadanie zostało dokończone; pozycje poniżej nie "
                     "zostały przetworzone. Aby je przeliczyć, uruchom "
                     "nową kolejkę z tą listą:")
        lines.append("")
        lines.append("```")
        lines += pominiete
        lines.append("```")
    lines.append("")
    lines.append("| Operat | Job | Kontrole | Werdykt | Flagi | Czas [s] | Raport |")
    lines.append("|---|---|---|---|---|---|---|")
    for it in st["items"]:
        base = os.path.basename(it["pdf"])
        if it["status"] == "pominiety":
            lines.append(f"| {base} | — | POMINIĘTY | — | — | — | — |")
            continue
        if it["status"] == "blad":
            lines.append(f"| {base} | — | BŁĄD | {it.get('blad')} | — "
                         f"| {it.get('sekundy', '—')} | — |")
            continue
        job = it.get("job") or "—"
        lines.append(
            f"| {base} | {job} | {'PASS' if it.get('PASS') else 'FAIL'} "
            f"| {it.get('werdykt') or '—'} | {it.get('flagi', 0)} "
            f"| {it.get('sekundy', '—')} "
            f"| [dokument](../{job}/document.md) |")
    lines += ["", "_Raport wygenerowany automatycznie po zakończeniu "
              "kolejki. Pozycje z flagami wymagają przeglądu przed "
              "eksportem._"]
    with open(os.path.join(_batch_dir(bid), "raport_poranny.md"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def status(bid):
    st = _load(bid)
    st["raport"] = (f"/file/kolejka-{bid}/raport_poranny.md"
                    if os.path.isfile(os.path.join(_batch_dir(bid),
                                                   "raport_poranny.md"))
                    else None)
    return st
