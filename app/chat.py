# geodoc — main chat on the context store. Truth = transcript.jsonl; KV slot
# state = cache saved per turn (resume ladder: warm restore -> re-prefill).
# AutoCompact: at 60% window utilization the transcript is summarized FROM THE
# FILE (never from the degraded window) by the kompaktor agent into a rolling
# summary note; numbers travel only as pointers to artifacts. Compaction is
# UNDOABLE — the pre-compact KV state is saved first.

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import llm  # noqa: E402
import store  # noqa: E402

COMPACT_AT = 0.60      # research: degradation starts well before the limit
KEEP_TURNS = 4         # verbatim turns carried across a compaction

SYSTEM_MAIN = (
    "Jestes glownym asystentem aplikacji geodoc dla firmy geodezyjnej. "
    "Pomagasz operatorowi pracowac z operatami: co przetworzono, co wymaga "
    "recenzji, gdzie leza artefakty (jobs/<job>/...). Odpowiadasz po polsku, "
    "zwiezle i konkretnie. Liczb i wspolrzednych nie cytujesz z pamieci — "
    "wskazujesz plik zrodlowy.")


def build_messages(rows):
    """Window assembly from transcript rows: system prompt (+ the rolling
    summary from the LAST compact note) + rows after that note's keep_from.
    Append-only truth; the window is a VIEW, never a rewrite."""
    system = SYSTEM_MAIN
    base = None            # rewizja: digest note swaps the base system prompt
    start = 0
    for i, r in enumerate(rows):
        if r.get("role") == "note" and r.get("kind") == "digest":
            import llm
            base = (llm.prompt("rewident")
                    + "\n\nDIGEST OPERATU (policzony przez kod):\n"
                    + r["content"])
            system = base
        if r.get("role") == "note" and r.get("kind") == "compact":
            system = ((base or SYSTEM_MAIN)
                      + "\n\nPODSUMOWANIE DOTYCHCZASOWEJ PRACY "
                      "(kompakt):\n" + r["content"])
            start = r.get("keep_from", i + 1)
    msgs = [dict(role="system", content=system)]
    for r in rows[start:]:
        if r.get("role") in ("user", "assistant"):
            msgs.append(dict(role=r["role"], content=r["content"]))
    return msgs


def _model_key(meta_model):
    return meta_model if meta_model in llm.manifest()["models"] else "worker"


def compact(ctx_id, model_key):
    """Summarize from the transcript FILE via the kompaktor agent (fresh
    context), append a compact note with keep_from, write summary.md."""
    llm.save_state(model_key, ctx_id + "-precompact")   # undo point
    rows = store.transcript(ctx_id)
    convo = "\n".join(f"[{r['role']}] {r['content']}" for r in rows
                      if r.get("role") in ("user", "assistant"))
    out = llm.call_agent("kompaktor", f"TRANSKRYPT:\n{convo}\n\n"
                         "ZADANIE: skompaktuj rozmowe wg kontraktu.",
                         model_key=model_key, max_tokens=1400, profile="judge")
    if out.get("_error") or not out.get("podsumowanie_md"):
        # abstention law: a failed kompaktor must not shrink the window —
        # a placeholder summary with keep_from truncation would LOSE memory
        return None
    summary = out["podsumowanie_md"]
    turn_rows = [i for i, r in enumerate(rows)
                 if r.get("role") in ("user", "assistant")]
    keep_from = turn_rows[-KEEP_TURNS] if len(turn_rows) > KEEP_TURNS \
        else (turn_rows[0] if turn_rows else len(rows))
    store.append(ctx_id, "note", summary, kind="compact", keep_from=keep_from)
    with open(os.path.join(store.CONTEXTS, ctx_id, "summary.md"), "w",
              encoding="utf-8") as f:
        f.write(summary + "\n")
    return summary


def turn(ctx_id, user_text, force_compact=False, user_extra=None):
    """One main-chat exchange with resume ladder, per-turn state save and
    AutoCompact. Returns reply + window utilization telemetry. user_extra
    rides into the stored user row (rewizja: display question + sources
    beside the full payload — the transcript stays what the model SAW)."""
    meta = store.meta(ctx_id)
    model_key = _model_key(meta.get("model"))
    ctx = llm.manifest()["models"][model_key].get("ctx", 16384)
    llm.ensure(model_key)
    llm.restore_state(model_key, ctx_id)          # warm when possible
    store.append(ctx_id, "user", user_text, **(user_extra or {}))
    msgs = build_messages(store.transcript(ctx_id))
    reply, fin, tim, usage = llm.chat_messages(
        llm.ensure(model_key), msgs, max_tokens=1200, profile="judge")
    used = (usage.get("prompt_tokens") or 0) + (usage.get("completion_tokens") or 0)
    store.append(ctx_id, "assistant", reply, tokens=used)
    llm.save_state(model_key, ctx_id)
    store.attach_state(ctx_id, model_key, llm.state_contract(model_key), used)
    util = used / ctx
    compacted = False
    if force_compact or util >= COMPACT_AT:
        compact(ctx_id, model_key)
        compacted = True
    return dict(reply=reply, ctx_id=ctx_id, utilization=round(util, 3),
                compacted=compacted, finish_reason=fin)
