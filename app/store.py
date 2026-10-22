# geodoc — context store: conversations as first-class artifacts.
# TRUTH is transcript.jsonl (append-only text); KV snapshots (state.bin via
# llama-server slot save) are cache, attached later by the supervisor. Fork and
# rerun are file operations — which is exactly why they are reliable.

import json
import os
import time
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTEXTS = os.path.join(ROOT, "contexts")


def _dir(ctx_id):
    return os.path.join(CONTEXTS, ctx_id)


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def create(role="main", model="worker", parent=None, note=None, **extra):
    ctx_id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    d = _dir(ctx_id)
    os.makedirs(d, exist_ok=False)
    meta = dict(id=ctx_id, role=role, model=model, parent=parent,
                created=_now(), archived=False, **extra)
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    open(os.path.join(d, "transcript.jsonl"), "w", encoding="utf-8").close()
    if note:
        append(ctx_id, "note", note)
    return ctx_id


def meta(ctx_id):
    with open(os.path.join(_dir(ctx_id), "meta.json"), encoding="utf-8") as f:
        return json.load(f)


def set_meta(ctx_id, **kv):
    """Conversation metadata update (nazwa, marker operatora, job binding)."""
    m = meta(ctx_id)
    m.update(kv)
    with open(os.path.join(_dir(ctx_id), "meta.json"), "w",
              encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=1)
    return m


def append(ctx_id, role, content, **extra):
    """role: user|assistant|tool|note. Returns the entry index."""
    path = os.path.join(_dir(ctx_id), "transcript.jsonl")
    entry = dict(t=_now(), role=role, content=content, **extra)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return sum(1 for _ in open(path, encoding="utf-8")) - 1


def transcript(ctx_id, upto=None):
    path = os.path.join(_dir(ctx_id), "transcript.jsonl")
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    return rows if upto is None else rows[:upto]


def fork(ctx_id, upto=None, note=None):
    """Copy transcript (optionally to step `upto`) into a NEW context. The KV
    snapshot is deliberately NOT copied — a forked context re-prefills from text
    (truth), never from cache."""
    src_meta = meta(ctx_id)
    new_id = create(role=src_meta["role"], model=src_meta["model"],
                    parent=f"{ctx_id}@{upto if upto is not None else 'end'}",
                    note=note)
    rows = transcript(ctx_id, upto)
    path = os.path.join(_dir(new_id), "transcript.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return new_id


def listing(include_archived=False):
    out = []
    if not os.path.isdir(CONTEXTS):
        return out
    for name in sorted(os.listdir(CONTEXTS)):
        mp = os.path.join(CONTEXTS, name, "meta.json")
        if not os.path.isfile(mp):
            continue
        m = json.load(open(mp, encoding="utf-8"))
        if m.get("archived") and not include_archived:
            continue
        m["turns"] = sum(1 for _ in open(os.path.join(CONTEXTS, name,
                                                      "transcript.jsonl"),
                                        encoding="utf-8"))
        out.append(m)
    return out


def archive(ctx_id):
    m = meta(ctx_id)
    m["archived"] = True
    with open(os.path.join(_dir(ctx_id), "meta.json"), "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=1)


def attach_state(ctx_id, model_key, contract, n_tokens=None):
    """Record that a KV snapshot exists for this context under the given
    state contract. The blob itself lives in contexts/kv/<model>/<contract>/
    — meta only points; deleting blobs never loses truth (transcript)."""
    m = meta(ctx_id)
    m["state"] = dict(model=model_key, contract=contract, n=n_tokens,
                      saved=_now())
    with open(os.path.join(_dir(ctx_id), "meta.json"), "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=1)
    return m["state"]
