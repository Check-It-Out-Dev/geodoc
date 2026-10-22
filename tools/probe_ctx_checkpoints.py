# E17 hazard-test: do context checkpoints (PR #19408 line) give the HYBRID
# analityk cross-request prefix reuse without breaking explicit slot
# save/restore? Our wave-1 law says auto checkpoint machinery breaks
# Qwen3-Next state (#22384/#24055) — but those reports POSTDATE the fix PR,
# so only measurement settles it. Gates, all must hold to ADOPT:
#   G1 server healthy with the flags
#   G2 second same-prefix call reuses cache (timings.cache_n > 0)
#   G3 explicit slot save -> restore still works (n_saved/n_restored > 0)
#   G4 output stays sane (no repetition collapse)
# Probe boots its OWN server on :7497 — shipping config stays untouched.

import json
import os
import subprocess
import sys
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "app"))
import llm  # noqa: E402

PORT = 7497
PREFIX = "".join(
    f"Punkt graniczny numer {i} zostal pomierzony metoda precyzyjna w "
    f"ukladzie PL-2000 strefa 6, stabilizacja kamieniem granicznym. "
    for i in range(1, 151))


def call(tail):
    body = dict(model="probe", max_tokens=60, temperature=0.0, seed=7420,
                messages=[dict(role="user", content=PREFIX + tail)])
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORT}/v1/chat/completions",
        json.dumps(body).encode(), {"Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=900).read())
    return (r["choices"][0]["message"]["content"] or "",
            r.get("timings", {}))


def slot(action, filename):
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORT}/slots/0?action={action}",
        json.dumps(dict(filename=filename)).encode(),
        {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=900).read())


def main():
    m = llm.manifest()
    cfg = m["models"]["analityk"]
    kv = llm.state_dir("analityk")
    proc = subprocess.Popen(
        [m["server"], "-m", cfg["gguf"], "-c", "16384", "--port", str(PORT),
         "-t", "8", "-tb", "24", "-np", "1", "--slot-save-path", kv,
         "--no-webui", "--cache-ram", "0", "--no-kv-unified",
         "--ctx-checkpoints", "8", "--checkpoint-min-step", "512"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        g1 = llm._wait(PORT, tries=600)
        print("G1 server-healthy-with-flags:", g1)
        if not g1:
            print("VERDICT: REJECTED (server refused flags)")
            return
        c1, t1 = call("Pytanie: ile punktow wymieniono?")
        c2, t2 = call("Pytanie: jaki uklad wspolrzednych?")
        print("call1 prompt_n", t1.get("prompt_n"), "cache_n", t1.get("cache_n"))
        print("call2 prompt_n", t2.get("prompt_n"), "cache_n", t2.get("cache_n"))
        g2 = (t2.get("cache_n") or 0) > 0
        sv = slot("save", "e17probe.bin")
        rs = slot("restore", "e17probe.bin")
        g3 = (sv.get("n_saved") or 0) > 0 and (rs.get("n_restored") or 0) > 0
        print("G3 save/restore n_saved", sv.get("n_saved"),
              "n_restored", rs.get("n_restored"))
        words = c2.split()
        g4 = len(words) >= 3 and len(set(words)) / max(1, len(words)) > 0.3
        print("G4 output-sane:", g4, "| odpowiedz:", c2[:120])
        print("G2 cross-request-cache-reuse:", g2)
        verdict = "ADOPT-CANDIDATE" if (g2 and g3 and g4) else "REJECTED"
        print(f"VERDICT: {verdict} (G2={g2} G3={g3} G4={g4})")
    finally:
        proc.kill()
        try:
            os.remove(os.path.join(kv, "e17probe.bin"))
        except OSError:
            pass


if __name__ == "__main__":
    main()
