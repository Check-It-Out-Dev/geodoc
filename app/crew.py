# geodoc — tryb nadzorowany (supervised crew): the pipeline pauses after
# every LLM stage, reports WHAT ran (agent, prompt hash, result digest) and
# waits for the operator: accept -> next stage, or retry WITH A DOPISEK — an
# operator override appended to the stage's payload. Overrides are first-class
# artifacts (overrides.jsonl with provenance) and, once they prove themselves,
# can graduate into the agent's user-overlay manual (prompt editor).
#
# Trust design (research-grounded, see docs/ARCHITECTURE.md § 11): trust is built by
# evidence + correction-that-sticks + recoverability, not by confidence
# theater. Autonomy is EARNED per document class; supervised is the default
# for a new powiat, auto for a proven one.

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import agents  # noqa: E402
import llm  # noqa: E402
import stages  # noqa: E402

STAGES = ["klasyfikator", "naglowek", "wykaz", "werdykt"]


def _state_path(job):
    return os.path.join(stages.JOBS, job, "crew_state.json")


def _load(job):
    return json.load(open(_state_path(job), encoding="utf-8"))


def _save_state(job, st):
    with open(_state_path(job), "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)


def _record_override(job, stage, dopisek):
    p = os.path.join(stages.JOBS, job, "tasks", "overrides.jsonl")
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(dict(t=time.strftime("%H:%M:%S"), stage=stage,
                                dopisek=dopisek), ensure_ascii=False) + "\n")


def _dopisek_block(dopisek):
    """Operator instruction rides in the USER payload (cache-safe) as an
    explicitly-labeled block — the operator OUTRANKS the manual's defaults
    but never the hard laws (contracts stay grammar-enforced)."""
    if not dopisek:
        return ""
    return ("DOPISEK OPERATORA (wiazacy dla tego przebiegu):\n"
            + dopisek.strip() + "\n\n")


def start(pdf_path, name=None):
    job = stages.create_job(pdf_path, name)
    sv = stages.stage_pages(job)
    stages.stage_mapa(job)
    _save_state(job, dict(cursor=0, sv=sv, overrides={}, done=False))
    return dict(job=job, next_stage=STAGES[0])


def _run_stage(job, st, dopisek=None):
    """Execute the stage under the cursor; returns the stage report."""
    stage = STAGES[st["cursor"]]
    job_dir = os.path.join(stages.JOBS, job)
    pdf = os.path.join(job_dir, "source", "operat.pdf")
    sv = st["sv"]
    extra = _dopisek_block(dopisek)

    if stage == "klasyfikator":
        readable = agents.usable_pages(job, pdf, sv)
        payload = (extra + f"MAPA STRON: {json.dumps(sv, ensure_ascii=False)}"
                   f"\n\nDOKUMENT (pierwsze czytelne strony):\n"
                   f"{agents._doc_block(job, pdf, readable[:3])}\n\n"
                   "ZADANIE: sklasyfikuj dokument wg kontraktu.")
        out = llm.call_agent("klasyfikator", payload)
        agents._save(job, "klasyfikacja.json", out)
    elif stage == "naglowek":
        klas = json.load(open(os.path.join(job_dir, "extracted",
                                           "klasyfikacja.json"),
                              encoding="utf-8"))
        cands = sorted(set([1] + (klas.get("strony_sprawozdania_kandydaci")
                                  or [])))[:3]
        payload = (extra + f"DOKUMENT:\n{agents._doc_block(job, pdf, cands)}"
                   "\n\nZADANIE: wyekstrahuj naglowek operatu wg kontraktu.")
        out = llm.call_agent("ekstraktor_naglowka", payload)
        agents._save(job, "header_llm.json", out)
    elif stage == "wykaz":
        klas = json.load(open(os.path.join(job_dir, "extracted",
                                           "klasyfikacja.json"),
                              encoding="utf-8"))
        out = agents.stage_wykaz_llm(job, pdf, sv, klas)  # per-page loop
        if dopisek:                       # dopisek applies via a rerun marker
            out["dopisek"] = dopisek
    else:                                 # werdykt: assemble like run_llm does
        hdr = json.load(open(os.path.join(job_dir, "extracted",
                                          "header_llm.json"), encoding="utf-8"))
        wyk = json.load(open(os.path.join(job_dir, "extracted",
                                          "wykaz_llm.json"), encoding="utf-8"))
        klas = json.load(open(os.path.join(job_dir, "extracted",
                                           "klasyfikacja.json"),
                              encoding="utf-8"))
        agents.finish_llm_job(job, pdf, sv, klas, hdr, wyk)
        checks = json.load(open(os.path.join(job_dir, "checks",
                                             "invariants.json"),
                                encoding="utf-8"))
        referee = json.load(open(os.path.join(job_dir, "extracted",
                                              "referee.json"),
                                 encoding="utf-8"))
        out = agents.stage_werdyktor(job, checks_digest_header(job), wyk,
                                     checks, klas, referee)
    return out


def checks_digest_header(job):
    p = os.path.join(stages.JOBS, job, "extracted", "header.json")
    return json.load(open(p, encoding="utf-8")) if os.path.isfile(p) else {}


def cofnij(job, stage):
    """Post-completion correction (owner 17:42): rewind the cursor to the
    chosen stage so the conversation can redo it with a dopisek and re-run
    everything downstream — files regenerate at the new final."""
    if stage not in STAGES:
        raise ValueError(f"nieznany etap: {stage}")
    st = _load(job)
    st["cursor"] = STAGES.index(stage)
    st["done"] = False
    _save_state(job, st)
    return dict(job=job, stage=stage)


def step(job, action="accept", dopisek=None, runner=None):
    """One supervised transition. action=run executes the current stage;
    accept advances the cursor; retry re-runs the current stage with the
    operator's dopisek recorded and injected."""
    st = _load(job)
    if st.get("done"):
        return dict(done=True, job=job)
    stage = STAGES[st["cursor"]]
    run = runner or _run_stage
    if action == "retry":
        if dopisek:
            st.setdefault("overrides", {})[stage] = dopisek
            _record_override(job, stage, dopisek)
        out = run(job, st, dopisek)
        _save_state(job, st)
        return dict(job=job, stage=stage, wynik=out, awaiting=True,
                    prompt_hash=(out.get("_meta") or {}).get("prompt_hash"))
    if action == "run":
        out = run(job, st, None)
        _save_state(job, st)
        return dict(job=job, stage=stage, wynik=out, awaiting=True,
                    prompt_hash=(out.get("_meta") or {}).get("prompt_hash"))
    # accept -> advance
    st["cursor"] += 1
    if st["cursor"] >= len(STAGES):
        st["done"] = True
        _save_state(job, st)
        return dict(done=True, job=job)
    _save_state(job, st)
    nxt = STAGES[st["cursor"]]
    return dict(job=job, next_stage=nxt, awaiting=False)
