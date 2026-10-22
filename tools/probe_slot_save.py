# geodoc — slice-3 probe: does slot save/restore survive a SERVER RESTART on
# our build/model, and does restore actually skip the re-prefill? Prints hard
# numbers; exit 0 only when the restored continuation reuses the saved cache.
#
# Method: boot worker (-np 1, --slot-save-path) -> long system+user exchange ->
# save slot 0 -> kill server -> boot fresh -> restore slot 0 -> send the SAME
# prefix + one more turn -> if restore works, timings.prompt_n covers only the
# new tokens (cache_n ~ saved length); cold control run measures full prefill.
#
# Usage: PYTHONUTF8=1 python tools/probe_slot_save.py

import json
import os
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))
import llm  # noqa: E402

PORT = 7429
KV_DIR = os.path.join(ROOT, "contexts", "kv", "probe")
STATE = "probe-main.bin"

SYSTEM = ("Jestes asystentem geodezyjnym. " * 40).strip()   # fat static prefix
TURN1 = ("Wymien osiem atrybutow punktu granicznego wedlug rozporzadzenia "
         "EGiB i opisz kazdy jednym zdaniem. " * 6).strip()
TURN2 = "Teraz podaj sam pierwszy atrybut, jednym slowem."


def boot():
    m = llm.manifest()
    cfg = m["models"]["worker"]
    os.makedirs(KV_DIR, exist_ok=True)
    args = [m["server"], "-m", cfg["gguf"], "-c", "16384",
            "--port", str(PORT), "-t", str(llm.physical_cores()),
            "-np", "1", "--slot-save-path", KV_DIR, "--no-webui"]
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    assert llm._wait(PORT), "server never became healthy"
    return proc


def chat(messages, max_tokens=160):
    body = json.dumps(dict(model="probe", temperature=0, seed=7420,
                           max_tokens=max_tokens, messages=messages)).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/v1/chat/completions",
                                 body, {"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=1800) as r:
        resp = json.loads(r.read().decode("utf-8"))
    dt = time.perf_counter() - t0
    t = resp.get("timings") or {}
    return (resp["choices"][0]["message"]["content"],
            dict(s=round(dt, 2), prompt_n=t.get("prompt_n"),
                 cache_n=t.get("cache_n"), predicted_n=t.get("predicted_n")))


def slot(action, filename):
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORT}/slots/0?action={action}",
        json.dumps({"filename": filename}).encode(),
        {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    msgs = [dict(role="system", content=SYSTEM),
            dict(role="user", content=TURN1)]

    print("[1] boot + prefill long exchange")
    proc = boot()
    try:
        a1, t1 = chat(msgs)
        print("    turn1:", t1)
        msgs.append(dict(role="assistant", content=a1))
        saved = slot("save", STATE)
        print("[2] slot save:", {k: saved.get(k) for k in
                                 ("n_saved", "n_written", "save_ms")})
        size = os.path.getsize(os.path.join(KV_DIR, STATE))
        print(f"    state file: {size / 1e6:.1f} MB")
    finally:
        proc.kill()
    time.sleep(2)

    print("[3] fresh server, RESTORE, continue")
    proc = boot()
    try:
        restored = slot("restore", STATE)
        print("    restore:", {k: restored.get(k) for k in
                               ("n_restored", "n_read", "restore_ms")})
        a2, t2 = chat(msgs + [dict(role="user", content=TURN2)], max_tokens=40)
        print("    continuation:", t2, "| answer:", a2[:80].replace("\n", " "))
    finally:
        proc.kill()
    time.sleep(2)

    print("[4] control: fresh server, NO restore (cold re-prefill)")
    proc = boot()
    try:
        a3, t3 = chat(msgs + [dict(role="user", content=TURN2)], max_tokens=40)
        print("    cold:", t3)
    finally:
        proc.kill()

    reused = (t2.get("cache_n") or 0)
    cold_prompt = t3.get("prompt_n") or 0
    warm_prompt = t2.get("prompt_n") or 0
    ok = reused > 0.8 * cold_prompt and warm_prompt < 0.3 * cold_prompt
    print(f"\nVERDICT: {'RESTORE WORKS ACROSS RESTART' if ok else 'RESTORE DID NOT REUSE CACHE'} "
          f"(warm prompt_n={warm_prompt}, cache_n={reused}, cold prompt_n={cold_prompt}; "
          f"warm {t2['s']}s vs cold {t3['s']}s)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
