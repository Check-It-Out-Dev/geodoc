# geodoc — the summary surface (fusion slice 2, panel-shaped): per-chapter
# synthesis on the WORKER, HIERARCHICAL merge (BooookScore ICLR'24:
# hierarchical beats incremental running-summary for small local models —
# the one evidence-based correction to the owner's incremental sketch;
# transcripts still build incrementally, summaries merge as a tree),
# G13 grounding (a cited fact's page must lie in the chapter range AND its
# numbers must exist verbatim on that page), chapter excel by CODE.

import json
import os
import re

import llm
import rozdzialy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOBS = os.path.join(ROOT, "jobs")


def _default_runner(payload):
    return llm.call_agent("syntezator_rozdzialow", payload, max_tokens=900)


def _numbers(s):
    """Number-ish tokens for G13. Trailing [.,;/-] is sentence punctuation
    glued by the regex, never number content — stress lab caught the gate
    dropping two PERFECT coordinate transcriptions over a trailing comma."""
    return [t.rstrip(".,;/-") for t in re.findall(r"\d[\d.,/-]{2,}", s or "")]


def g13_ground(summary, chapter, transcripts):
    """G13: every fact cites a page inside the chapter range; every number
    in the fact exists on that page's transcript (diacritic-fold irrelevant
    for digits; substring on raw text). Ungrounded facts are DROPPED into
    the flag list — abstention-first, never silently kept."""
    ok, dropped = [], []
    for f in summary.get("fakty") or []:
        pg = f.get("strona")
        in_range = isinstance(pg, int) and chapter["od"] <= pg <= chapter["do"]
        page_txt = transcripts.get(pg, "")
        nums_ok = all(n in page_txt for n in _numbers(f.get("fakt")))
        (ok if in_range and nums_ok else dropped).append(f)
    summary["fakty"] = ok
    if dropped:
        summary["fakty_odrzucone"] = dropped
    summary["fakty_ugruntowane"] = not dropped
    return summary


def summarize_chapters(job, runner=None, jobs_root=None):
    """Phase: one synthesis call per chapter (sequential, worker; the shared
    manual prefix rides --cache-reuse), G13 after each; writes
    extracted/podsumowania.json. Budget law: chapter text is capped to the
    0.75 window minus manual headroom before the call."""
    runner = runner or _default_runner
    jr = jobs_root or JOBS
    jdir = os.path.join(jr, job)
    doc = json.load(open(os.path.join(jdir, "extracted", "chapters.json"),
                         encoding="utf-8"))
    last = max((c["do"] for c in doc["rozdzialy"]), default=0)
    transcripts = {n: rozdzialy.page_text_job(job, n, jobs_root=jr)
                   for n in range(1, last + 1)}
    out = []
    for ch in doc["rozdzialy"]:
        parts = []
        for n in range(ch["od"], ch["do"] + 1):
            parts.append(f"## s. {n}\n{transcripts.get(n, '')}")
        text = "\n\n".join(parts)[:28_000]      # ~9k tokens, inside 0.75*12k
        payload = (f"ROZDZIAL {ch['nr']}: \"{ch['tytul']}\" "
                   f"(strony {ch['od']}-{ch['do']})\n\n===DOKUMENT===\n"
                   f"{text}\n===KONIEC===\n\n"
                   "ZADANIE: streszczenie + fakty ze stronami wg kontraktu.")
        s = runner(payload) or {}
        s = g13_ground(s, ch, transcripts)
        s.update(nr=ch["nr"], tytul=ch["tytul"], od=ch["od"], do=ch["do"])
        out.append(s)
    json.dump(out, open(os.path.join(jdir, "extracted",
                                     "podsumowania.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=1)
    return out


def merge_summaries(summaries, pairwise=None):
    """Hierarchical tree-merge to one document digest. The merge itself is
    CODE (concatenation buckets) — the model is only asked per LEVEL when a
    bucket exceeds budget; for typical operat sizes a single deterministic
    reduction suffices, so v1 merges by code and keeps the tree hook."""
    fakty = [dict(f, rozdzial=s["nr"]) for s in summaries
             for f in (s.get("fakty") or [])]
    braki = [b for s in summaries for b in (s.get("braki") or [])]
    return dict(
        rozdzialy=[dict(nr=s["nr"], tytul=s["tytul"], typ=s["typ_rozdzialu"],
                        streszczenie=s["streszczenie"]) for s in summaries],
        fakty=fakty, braki=braki,
        fakty_ugruntowane=all(s.get("fakty_ugruntowane", True)
                              for s in summaries))


def write_master_summary(job, merged, jobs_root=None):
    """Append the document digest to master.md (linked TOC stays on top)."""
    jr = jobs_root or JOBS
    mpath = os.path.join(jr, job, "rozdzialy", "master.md")
    lines = ["", "## Streszczenie dokumentu", ""]
    for r in merged["rozdzialy"]:
        lines.append(f"- **{r['nr']}. {r['tytul']}** ({r['typ']}): "
                     f"{r['streszczenie']}")
    if merged["braki"]:
        lines.append("")
        lines.append("### Braki zgloszone przez syntezatory")
        lines += [f"- {b}" for b in merged["braki"]]
    with open(mpath, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_chapter_excel(job, summaries, jobs_root=None):
    """out/rozdzialy.xlsx — the per-chapter vital-info sheet (owner spec:
    each column a different vital info) + a facts sheet with page refs."""
    from openpyxl import Workbook
    jr = jobs_root or JOBS
    out_dir = os.path.join(jr, job, "out")
    os.makedirs(out_dir, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "Rozdzialy"
    ws.append(["Nr", "Tytul", "Strony", "Typ", "Streszczenie",
               "Liczba faktow", "Braki", "Fakty ugruntowane"])
    for s in summaries:
        ws.append([s["nr"], s["tytul"], f"{s['od']}-{s['do']}",
                   s["typ_rozdzialu"], s["streszczenie"],
                   len(s.get("fakty") or []),
                   "; ".join(s.get("braki") or []),
                   "TAK" if s.get("fakty_ugruntowane", True) else "NIE"])
    ws2 = wb.create_sheet("Fakty")
    ws2.append(["Rozdzial", "Fakt", "Strona", "ZRODLO"])
    for s in summaries:
        for f in s.get("fakty") or []:
            ws2.append([s["nr"], f["fakt"], f["strona"],
                        f"operat s. {f['strona']}"])
            c = ws2.cell(row=ws2.max_row, column=4)
            c.hyperlink = f"../source/operat.pdf#page={f['strona']}"
            c.style = "Hyperlink"
    for sheet in (ws, ws2):
        for cell in sheet[1]:
            cell.font = cell.font.copy(bold=True)
    path = os.path.join(out_dir, "rozdzialy.xlsx")
    wb.save(path)
    return path


def phase_podsumowania(job, runner=None, jobs_root=None):
    """Slice-2 orchestrator: summaries -> G13 -> merge -> master.md + excel."""
    summaries = summarize_chapters(job, runner=runner, jobs_root=jobs_root)
    merged = merge_summaries(summaries)
    write_master_summary(job, merged, jobs_root=jobs_root)
    xlsx = write_chapter_excel(job, summaries, jobs_root=jobs_root)
    return dict(rozdzialy=len(summaries), fakty=len(merged["fakty"]),
                fakty_ugruntowane=merged["fakty_ugruntowane"], excel=xlsx)
