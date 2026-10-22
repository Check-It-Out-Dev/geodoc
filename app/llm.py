# geodoc — llama-server sidecar + agent-call primitive. Model paths come from
# models.json (or a per-machine models.local.json). One server at a
# time (the 64 GB law); chat is stateless per call — every agent stage is a
# fresh context by construction.
#
# Harness laws (SOTA dossier § 1, all source-verified 2026-08):
#  - threads = PHYSICAL cores; SMT halves generation on A3B MoE (llama.cpp #19480)
#  - per-role sampling: `transcribe` = greedy with ALL penalties zeroed (penalties
#    corrupt repetitive coordinate tables); `judge` = Qwen card settings
#  - every agent answer is grammar-constrained via response_format + schemas/<agent>.json
#  - finish_reason=length is detected and retried with a doubled budget, never
#    silently truncated into "bad-json"
#  - --slot-save-path is armed from boot so KV state save/restore is available

import hashlib
import json
import os
import re
import subprocess
import threading
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# models.json describes the INSTALLED layout (llama-bin/<build>/, models/) and
# is committed; models.local.json (gitignored) overrides it on one machine,
# e.g. a developer box that keeps its GGUFs elsewhere. Read through
# manifest_path() everywhere (the seal included) so both agree.
MANIFEST_SHIPPED = os.path.join(ROOT, "models.json")
MANIFEST_LOCAL = os.path.join(ROOT, "models.local.json")
PROMPTS = os.path.join(ROOT, "prompts")
SCHEMAS = os.path.join(ROOT, "schemas")

SEED = 7420  # fixed for replay determinism (diffable reruns)

PROFILES = {
    # faithful transcription: greedy, penalties explicitly OFF — coordinate
    # tables are legitimately repetitive text and any repetition penalty
    # perturbs shared numeric prefixes
    "transcribe": dict(temperature=0.0, repeat_penalty=1.0,
                       presence_penalty=0.0, frequency_penalty=0.0, seed=SEED),
    # judge/chat: official Qwen3-Instruct card settings; presence stays 0 —
    # the card warns nonzero presence_penalty can cause LANGUAGE MIXING, fatal
    # for Polish reports; loop degeneration is caught by code gates instead
    "judge": dict(temperature=0.7, top_p=0.8, top_k=20, min_p=0.0,
                  presence_penalty=0.0, repeat_penalty=1.0, seed=SEED),
}

_procs = {}          # model_key -> dict(proc=Popen, parallel=int, port=int)
_cores = None


def manifest_path():
    return MANIFEST_LOCAL if os.path.isfile(MANIFEST_LOCAL) else MANIFEST_SHIPPED


def manifest():
    """The model manifest. RELATIVE server/gguf paths resolve against the app
    root, so one file serves the installed layout and a clone after
    tools/fetch_runtime.py; absolute paths (a dev box's models.local.json)
    are taken as they are."""
    m = json.load(open(manifest_path(), encoding="utf-8"))
    def _abs(p):
        return p if os.path.isabs(p) else os.path.join(ROOT, p)
    m["server"] = _abs(m["server"])
    for cfg in m["models"].values():
        cfg["gguf"] = _abs(cfg["gguf"])
    return m


def prompt(name):
    """Effective manual: user overlay (operator-edited) wins over shipped golden.
    Reset-to-golden = delete the overlay file; golden is never written at runtime."""
    for sub in ("user", "golden"):
        p = os.path.join(PROMPTS, sub, name + ".md")
        if os.path.isfile(p):
            return open(p, encoding="utf-8").read()
    raise FileNotFoundError(f"no manual for agent '{name}'")


def prompt_info(name):
    user = os.path.isfile(os.path.join(PROMPTS, "user", name + ".md"))
    text = prompt(name)
    return dict(name=name, source="user" if user else "golden",
                hash=hashlib.sha256(text.encode("utf-8")).hexdigest()[:12])


def prompt_list():
    gold = os.path.join(PROMPTS, "golden")
    return sorted(f[:-3] for f in os.listdir(gold) if f.endswith(".md"))


def fill_slots(text, slots=None):
    """{{KEY}} placeholders: filled from slots, unused ones stripped — a manual
    stays valid with or without learned-memory injections."""
    for k, v in (slots or {}).items():
        text = text.replace("{{" + k + "}}", v)
    return re.sub(r"[ \t]*\{\{[A-Z_]+\}\}[ \t]*\n?", "", text)


def schema(name):
    p = os.path.join(SCHEMAS, name + ".json")
    return json.load(open(p, encoding="utf-8")) if os.path.isfile(p) else None


def physical_cores():
    """SMT measurably halves TG on this arch — count real cores, not threads."""
    global _cores
    if _cores:
        return _cores
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_Processor | "
             "Measure-Object -Property NumberOfCores -Sum).Sum"],
            text=True, stderr=subprocess.DEVNULL, timeout=30)
        _cores = int(out.strip().splitlines()[-1])
    except Exception:
        _cores = max(2, (os.cpu_count() or 8) // 2)  # assume SMT 2x
    _cores = max(2, _cores)
    return _cores


def count_tokens(port, text):
    """Real tokenizer count via llama-server /tokenize — chars lie, tokens don't."""
    req = urllib.request.Request(f"http://127.0.0.1:{port}/tokenize",
                                 json.dumps({"content": text}).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return len(json.loads(r.read().decode("utf-8"))["tokens"])


def budget_check(tokens_in, max_tokens, ctx, frac=0.75):
    """The measured 0.75 law as an ASSERTION: attention degrades long before
    the hard limit, so input + planned output must fit in frac*ctx. Returns
    (ok, allowed_total). The margin also absorbs chat-template overhead."""
    allowed = int(ctx * frac)
    return tokens_in + max_tokens <= allowed, allowed


def _wait(port, tries=300):
    for _ in range(tries):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(1)
    return False


def state_contract(model_key):
    """KV-state blobs carry ZERO validation metadata — restoring under a
    different gguf/ctx/build crashes or silently corrupts. The contract id
    versions the state directory by everything that must match."""
    m = manifest()
    cfg = m["models"][model_key]
    sig = "|".join([os.path.basename(cfg["gguf"]),
                    str(os.path.getsize(cfg["gguf"])),
                    str(cfg.get("ctx", 16384)),
                    os.path.basename(os.path.dirname(m["server"]))])
    return hashlib.sha256(sig.encode("utf-8")).hexdigest()[:12]


def state_dir(model_key):
    d = os.path.join(ROOT, "contexts", "kv", model_key,
                     state_contract(model_key))
    os.makedirs(d, exist_ok=True)
    return d


def _slot_action(port, action, filename):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/slots/0?action={action}",
        json.dumps({"filename": filename}).encode(),
        {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode("utf-8"))


def save_state(model_key, name):
    """Persist slot-0 KV as contexts/kv/<model>/<contract>/<name>.bin.
    Probe-verified: survives full server restart; resume 5.6x faster."""
    port = ensure(model_key)
    out = _slot_action(port, "save", name + ".bin")
    return dict(file=os.path.join(state_dir(model_key), name + ".bin"),
                n_saved=out.get("n_saved"))


def restore_state(model_key, name):
    """Resume ladder step 1: restore KV if a blob exists under the CURRENT
    contract. warm=False -> caller re-prefills from transcript (truth)."""
    if not os.path.isfile(os.path.join(state_dir(model_key), name + ".bin")):
        return dict(warm=False, reason="no-state-for-contract")
    port = ensure(model_key)
    out = _slot_action(port, "restore", name + ".bin")
    return dict(warm=True, n_restored=out.get("n_restored"))


def ctx_law(cfg):
    """Wave-5 enemy: llama.cpp's DeltaNet g_cum accumulator overflows past
    ~80k ctx and the hybrid collapses into repetition (upstream discussion
    #20000, unfixed) — any config carrying ctx_ceiling must stay under it.
    Pure function so the law is unit-testable without booting a server."""
    ceiling = cfg.get("ctx_ceiling")
    ctx = cfg.get("ctx", 16384)
    if ceiling and ctx > ceiling:
        raise AssertionError(
            f"ctx {ctx} exceeds ctx_ceiling {ceiling} (DeltaNet g_cum "
            f"overflow law - hybrid collapses past ~80k)")
    return ctx


def _total_ram_bytes():
    import ctypes
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong)] + [
                    (n, ctypes.c_ulonglong) for n in
                    ("ullTotalPhys", "ullAvailPhys", "ullTotalPageFile",
                     "ullAvailPageFile", "ullTotalVirtual",
                     "ullAvailVirtual", "ullAvailExtendedVirtual")]
    st = MEMORYSTATUSEX()
    st.dwLength = ctypes.sizeof(st)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
    return st.ullTotalPhys


def residency_mode(models_cfg, total_ram, override=None):
    """E9 (unlocked by the 190 GB dev box): 'dual' keeps BOTH llama servers
    resident — kills the 30-60 s model swap every job pays between transcribe
    (worker) and verdict (analityk). Pure decision fn: dual only when every
    gguf together + 16 GB headroom (KV+OCR+OS) fits total RAM. The 64 GB
    client box decides 'single' by itself — same config ships everywhere."""
    if override in ("single", "dual"):
        return override
    # ten sam gguf w dwoch rolach (warianty Lekki/80B) liczy sie RAZ —
    # mmap dzieli strony wag miedzy procesy (zmierzone 06.08: dwa serwery
    # 30B = ~20 GiB fizycznie, nie 2x18.6)
    files = {os.path.abspath(c["gguf"]) for c in models_cfg.values()
             if os.path.isfile(c["gguf"])}
    need = sum(os.path.getsize(f) for f in files)
    return "dual" if need * 1.1 + 16 * 2**30 < total_ram else "single"


_ensure_lock = threading.Lock()


def _uprzatnij_port(port):
    """Obrona przed pozostalym serwerem z poprzedniego uruchomienia
    (audyt 07.08): llama-server z POPRZEDNIEGO procesu (CLI, awaria tray'a,
    skrypt) potrafi dzialac dalej i zajmowac port — nowy start ginie na
    bind, a _wait dostaje zdrowie od STAREGO serwera z niewlasciwa juz
    konfiguracja (-np/flagi/gguf sprzed zmiany). Konczymy wylacznie procesy
    o nazwie llama-server nasluchujace na naszym porcie; inne procesy
    pozostaja nietkniete (wtedy start i tak zakonczy sie glosnym bledem,
    co jest poprawne)."""
    cmd = ("$c = Get-NetTCPConnection -LocalPort {p} -State Listen "
           "-ErrorAction SilentlyContinue; if ($c) {{ "
           "$proc = Get-Process -Id $c.OwningProcess "
           "-ErrorAction SilentlyContinue; "
           "if ($proc -and $proc.Name -eq 'llama-server') "
           "{{ Stop-Process -Id $proc.Id -Force }} }}").format(p=port)
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                       capture_output=True, timeout=15)
    except Exception:
        pass


def ensure(model_key, parallel=1):
    """Boot (or switch to) the given model; returns its port. parallel=1 is
    the stateful default (slot-0 save/restore target); parallel=4 is the BULK
    profile for mass extraction — measured +97% aggregate TG at 4 sequences
    (expert-read amortization); ctx is per-slot so bulk slots get ctx/4.
    Residency: 'dual' hosts leave the other model running (E9).
    Lock: server request threads + the nightshift worker both call in —
    unlocked, two callers could double-spawn one port (audit find)."""
    with _ensure_lock:
        m = manifest()
        cfg = m["models"][model_key]
        live = _procs.get(model_key)
        if live and live["parallel"] == parallel and live["proc"].poll() is None:
            return cfg["port"]
        if residency_mode(m["models"], _total_ram_bytes(),
                          m.get("residency")) == "single":
            stop()
        else:
            _stop_one(model_key)      # restart only this model (parallel flip)
        _uprzatnij_port(cfg["port"])
        kv_dir = state_dir(model_key)
        args = [m["server"], "-m", cfg["gguf"], "-c", str(ctx_law(cfg)),
                "--port", str(cfg["port"]),
                "-t", str(cfg.get("threads") or physical_cores()),
                "-np", str(parallel),
                "--slot-save-path", kv_dir,
                "--no-webui"] + list(cfg.get("extra_args") or [])
        if cfg.get("threads_batch"):
            args += ["-tb", str(cfg["threads_batch"])]
        proc = subprocess.Popen(args, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        _procs[model_key] = dict(proc=proc, parallel=parallel,
                                 port=cfg["port"])
        if not _wait(cfg["port"]):    # never assert: -O strips asserts and a
            raise RuntimeError(       # packaged app would talk to a corpse
                f"llama-server for {model_key} never became healthy")
        return cfg["port"]


def _stop_one(model_key):
    live = _procs.pop(model_key, None)
    if live and live["proc"].poll() is None:
        live["proc"].kill()


def stop():
    for key in list(_procs):
        _stop_one(key)


def chat_messages(port, messages, max_tokens=1800, profile="transcribe",
                  json_schema=None):
    """Multi-turn exchange. Returns (content, finish_reason, timings, usage)."""
    body = dict(model="geodoc", max_tokens=max_tokens, messages=messages,
                **PROFILES[profile])
    if json_schema is not None:
        body["response_format"] = {"type": "json_object", "schema": json_schema}
    req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions",
                                 json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        resp = json.loads(r.read().decode("utf-8"))
    choice = resp["choices"][0]
    t = resp.get("timings") or {}
    timings = dict(cache_n=t.get("cache_n"), prompt_n=t.get("prompt_n"),
                   predicted_n=t.get("predicted_n"))
    return (choice["message"]["content"], choice.get("finish_reason"),
            timings, resp.get("usage") or {})


def chat(port, system, user, max_tokens=1800, profile="transcribe", json_schema=None):
    """One stateless exchange. Returns (content, finish_reason, timings)."""
    content, fin, timings, _ = chat_messages(
        port, [{"role": "system", "content": system},
               {"role": "user", "content": user}],
        max_tokens, profile, json_schema)
    return content, fin, timings


def _parse(raw):
    txt = re.sub(r"^```[a-z]*\n?|```$", "", raw.strip(), flags=re.M).strip()
    m = re.search(r"\{.*\}", txt, flags=re.S)
    if not m:
        return None, "no-json"
    try:
        return json.loads(m.group(0)), None
    except json.JSONDecodeError as e:
        return None, f"bad-json {e}"


def call_agent(agent, user_payload, model_key="worker", max_tokens=1800,
               profile="transcribe", slots=None, parallel=1):
    """One agent invocation: system = the agent's manual (user overlay > golden,
    {{SLOT}}s filled), task at the END of the user turn (the measured position
    law), answer grammar-constrained by schemas/<agent>.json when present.
    Returns parsed JSON with _meta incl. the exact prompt hash that ran."""
    port = ensure(model_key, parallel)
    sch = schema(agent)
    manual = fill_slots(prompt(agent), slots)
    pinfo = prompt_info(agent)
    ctx = manifest()["models"][model_key].get("ctx", 16384) // max(1, parallel)
    tokens_in = count_tokens(port, manual) + count_tokens(port, user_payload)
    out_cap = int(ctx * 0.75) - tokens_in
    if out_cap < 256:
        return dict(_error=f"budget: input {tokens_in} tokens leaves only "
                           f"{out_cap} of the 0.75*{ctx} window — re-chunk",
                    _agent=agent,
                    _meta=dict(model=model_key, profile=profile,
                               tokens_in=tokens_in, prompt_source=pinfo["source"],
                               prompt_hash=pinfo["hash"]))
    attempts, raw, fin, tim = 0, "", None, {}
    budget = min(max_tokens, out_cap)
    while attempts < 3:
        attempts += 1
        raw, fin, tim = chat(port, manual, user_payload, budget, profile, sch)
        if fin == "length":          # truncated mid-answer: retry, bigger budget
            budget = min(budget * 2, out_cap)   # never past the 0.75 window
            continue
        out, err = _parse(raw)
        if out is None:              # constrained decode makes this near-dead
            continue                 # one blind retry, then give up honestly
        out["_agent"] = agent
        out["_meta"] = dict(model=model_key, profile=profile,
                            attempts=attempts, finish_reason=fin,
                            tokens_in=tokens_in, cache_n=tim.get("cache_n"),
                            prompt_source=pinfo["source"], prompt_hash=pinfo["hash"])
        return out
    out, err = _parse(raw)
    return dict(_error=(err or f"truncated at {budget // 2} tokens"),
                _raw=raw[:400], _agent=agent,
                _meta=dict(model=model_key, profile=profile,
                           attempts=attempts, finish_reason=fin,
                           prompt_source=pinfo["source"], prompt_hash=pinfo["hash"]))
