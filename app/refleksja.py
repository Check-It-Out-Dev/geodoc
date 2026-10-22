# geodoc — Refleksja: the self-learning half of the human loop (owner 13:18).
# After a hard job — many operator dopiski, a long rewizja — the model reads
# the TRACE of human interventions and PROPOSES durable manual rules
# (positive and negative). The system never applies them itself: proposals
# go to the operator, one click writes them into the user overlay (golden
# stays immutable), and manuals hot-reload — llm.prompt() reads the file on
# every call, so the next invocation runs the new rules with no restart.
# Frozen-weights law honored: adaptation = prompts, never weights.

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import teksty  # noqa: E402

AGENCI = ["klasyfikator", "ekstraktor_naglowka", "ekstraktor_wykazu",
          "werdyktor", "detektor_rozdzialow", "syntezator_rozdzialow",
          "opisywacz_zdjec", "rewident"]

NAGLOWEK_BLOKU = "# DOPISKI OPERATORA"


def material(job, jobs_root=None):
    """The intervention trace, assembled BY CODE: crew dopiski
    (overrides.jsonl), the rewizja mirror, and check flags."""
    jr = jobs_root or teksty.JOBS
    czesci = [f"OPERAT: {job}", f"AGENCI DO WYBORU: {', '.join(AGENCI)}"]
    ov = os.path.join(jr, job, "tasks", "overrides.jsonl")
    if not os.path.isfile(ov):                 # older jobs kept it at root
        ov = os.path.join(jr, job, "overrides.jsonl")
    if os.path.isfile(ov):
        wpisy = [json.loads(ln) for ln in open(ov, encoding="utf-8")
                 if ln.strip()]
        if wpisy:
            czesci.append("DOPISKI OPERATORA (tryb nadzorowany):\n" + "\n".join(
                f"- etap {w.get('stage')}: {w.get('dopisek')}"
                for w in wpisy if w.get("dopisek")))
    rw = os.path.join(jr, job, "analizy", "rewizja.md")
    if os.path.isfile(rw):
        tekst = open(rw, encoding="utf-8").read()
        czesci.append("REWIZJA (pytania operatora i odpowiedzi):\n"
                      + tekst[:6000])
    chk = teksty.artefakt(job, "checks", "invariants.json",
                          jobs_root=jr) or {}
    flagi = chk.get("flagi") or {}
    if flagi:
        czesci.append("FLAGI KONTROLI: " + json.dumps(
            {k: (len(v) if isinstance(v, list) else v)
             for k, v in flagi.items()}, ensure_ascii=False))
    zle = [k for k, v in chk.items() if v is False]
    if zle:
        czesci.append("KONTROLE NIEZALICZONE: " + ", ".join(zle))
    return "\n\n".join(czesci)


def zaproponuj(job, runner=None, jobs_root=None):
    """One reflection call. Returns {propozycje: [...]} filtered to known
    agents; the empty list is a legitimate answer (no clear patterns)."""
    mat = material(job, jobs_root=jobs_root)
    if runner is None:
        import llm
        def runner(payload):
            return llm.call_agent("refleksja", payload,
                                  model_key="analityk", profile="judge",
                                  max_tokens=1600)
    out = runner("ŚLAD INTERWENCJI:\n" + mat
                 + "\n\nZADANIE: zaproponuj reguły manuali wg kontraktu.")
    if out.get("_error"):
        return dict(error=out["_error"])
    props = [p for p in (out.get("propozycje") or [])
             if p.get("agent") in AGENCI and p.get("zasady")]
    return dict(propozycje=props)


def zastosuj(agent, zasady):
    """Operator-approved application: append rules to the USER overlay
    (golden untouched). Manuals hot-reload on the next call by design."""
    if agent not in AGENCI:
        raise ValueError(f"nieznany agent: {agent}")
    import llm
    baza = llm.prompt(agent)
    blok = "" if NAGLOWEK_BLOKU in baza else f"\n\n{NAGLOWEK_BLOKU}\n"
    linie = "".join(
        f"- [{z.get('typ', 'pozytywna')}] {z['tresc']}\n"
        for z in zasady if z.get("tresc"))
    if not linie:
        raise ValueError("puste zasady")
    user_dir = os.path.join(teksty.ROOT, "prompts", "user")
    os.makedirs(user_dir, exist_ok=True)
    with open(os.path.join(user_dir, agent + ".md"), "w",
              encoding="utf-8") as f:
        f.write(baza + blok + linie)
    return llm.prompt_info(agent)
