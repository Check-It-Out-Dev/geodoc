# geodoc launcher — the uTorrent-Web pattern: background server, UI in the
# DEFAULT browser at a tokenized loopback URL. Single instance: a second
# launch just reopens the browser at the running instance's URL.
#
# Double-click (pythonw, no console) or: python start_geodoc.pyw

import os
import secrets
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = 7420
LOCK = os.path.join(ROOT, "contexts", ".shell.lock")   # port + token of the
                                                       # running instance


def running_url():
    try:
        with open(LOCK, encoding="utf-8") as f:
            url = f.read().strip()
        with urllib.request.urlopen(url.split("?")[0] + "api/prompts"
                                    + ("?" + url.split("?")[1] if "?" in url
                                       else ""), timeout=2) as r:
            if r.status in (200, 403):
                return url
    except Exception:
        pass
    return None


def port_free(port):
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def verify_models():
    """Model-pack integrity: sizes at EVERY launch (instant), full sha256 once
    (first run after install/import; marker .verified caches success). Errors
    land in geodoc-error.log next to this file — the browser shell never
    starts on a corrupted pack."""
    import hashlib
    import json as _json
    mp = os.path.join(ROOT, "models", "manifest.json")
    if not os.path.isfile(mp):
        return True                      # dev layout: no pack, no check
    man = _json.load(open(mp, encoding="utf-8"))
    marker = os.path.join(ROOT, "models", ".verified")
    deep = not os.path.isfile(marker)
    for f in man.get("pliki", []):
        p = os.path.join(ROOT, "models", f["name"])
        if not os.path.isfile(p) or os.path.getsize(p) != f["bytes"]:
            _fail(f"model {f['name']}: brak pliku albo zly rozmiar")
            return False
        if deep:
            h = hashlib.sha256()
            with open(p, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 24), b""):
                    h.update(chunk)
            if h.hexdigest() != f["sha256"]:
                _fail(f"model {f['name']}: sha256 niezgodny — uszkodzony plik")
                return False
    if deep:
        open(marker, "w").close()
    return True


def _fail(msg):
    with open(os.path.join(ROOT, "geodoc-error.log"), "a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")


def main():
    url = running_url()
    if url:
        webbrowser.open(url)
        return 0
    if not verify_models():
        return 1
    port = PORT
    while not port_free(port):
        port += 1
    token = secrets.token_urlsafe(16)
    proc = subprocess.Popen(
        [sys.executable.replace("pythonw.exe", "python.exe"),
         os.path.join(ROOT, "app", "server.py"),
         "--port", str(port), "--token", token],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}/?token={token}"
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    with open(LOCK, "w", encoding="utf-8") as f:
        f.write(url)
    for _ in range(50):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/?token={token}",
                                   timeout=1)
            break
        except Exception:
            time.sleep(0.2)
    webbrowser.open(url)
    proc.wait()                        # watchdog: launcher lives with server
    try:
        os.remove(LOCK)
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
