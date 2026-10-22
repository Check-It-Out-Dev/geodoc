"""geodoc: fetch the two things a clone does not carry: the llama.cpp server
build and the model weights. Standard library only (the zero-dependency law).

  python tools/fetch_runtime.py                 # download both, verify sha256
  python tools/fetch_runtime.py --check         # only ask both URLs if they answer
  python tools/fetch_runtime.py --gguf-from D:/models/Qwen3-30B-A3B-Instruct-2507-Q4_K_M.gguf
                                                # reuse a copy you already have

Layout written (the same one the Windows installer produces, and the one the
committed models.json points at):
  llama-bin/b10155/llama-server.exe (+ DLLs)    the directory name is the build
                                                id the reproducibility seal records
  models/Qwen3-30B-A3B-Instruct-2507-Q4_K_M.gguf

Downloads go to <name>.part and are renamed only after the sha256 matches, so
an interrupted run never leaves a file that looks complete; a rerun resumes.
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LLAMA_BUILD = "b10155"
LLAMA = dict(
    url=(f"https://github.com/ggml-org/llama.cpp/releases/download/"
         f"{LLAMA_BUILD}/llama-{LLAMA_BUILD}-bin-win-cpu-x64.zip"),
    sha256="1f38b45dd037844145fecf2bffe2e85b49798d8ec0b3ab8abec1314e01277fed",
    bytes=18305748,
)
GGUF_NAME = "Qwen3-30B-A3B-Instruct-2507-Q4_K_M.gguf"
GGUF_URL = ("https://huggingface.co/unsloth/Qwen3-30B-A3B-Instruct-2507-GGUF/"
            f"resolve/main/{GGUF_NAME}")


def gguf_pin():
    """sha256 and size come from the installer's model-pack manifest — one
    home for the pin, shared with the launcher's integrity check."""
    p = os.path.join(ROOT, "installer", "manifesty", "pack-lekki.json")
    for f in json.load(open(p, encoding="utf-8"))["pliki"]:
        if f["name"] == GGUF_NAME:
            return f["sha256"], f["bytes"]
    raise SystemExit(f"{GGUF_NAME} is not pinned in {p}")


def sha256_of(path, size_hint=0):
    h = hashlib.sha256()
    done, shown = 0, -1
    with open(path, "rb") as f:
        while True:
            b = f.read(8 << 20)
            if not b:
                break
            h.update(b)
            done += len(b)
            pct = done * 100 // max(1, size_hint)
            if size_hint > 1 << 30 and pct // 10 != shown:   # one line per 10 %
                shown = pct // 10
                print(f"  sha256 {pct:3d}%", flush=True)
    return h.hexdigest()


def download(url, dest, size):
    part = dest + ".part"
    have = os.path.getsize(part) if os.path.isfile(part) else 0
    if have > size:
        os.remove(part)
        have = 0
    if have == size:      # complete download whose hash check was interrupted
        return part
    req = urllib.request.Request(url, headers={"User-Agent": "geodoc-fetch"})
    if have:
        req.add_header("Range", f"bytes={have}-")
    with urllib.request.urlopen(req, timeout=60) as r:
        if have and r.status != 206:      # server ignored the range: start over
            have = 0
        with open(part, "ab" if have else "wb") as out:
            done, shown = have, -1
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                out.write(b)
                done += len(b)
                pct = done * 100 // size
                if pct // 5 != shown:              # one line per 5 %: log-friendly
                    shown = pct // 5
                    print(f"  {os.path.basename(dest)}: {pct:3d}% "
                          f"({done / 1e6:,.0f} of {size / 1e6:,.0f} MB)", flush=True)
    return part


def verify_and_place(part, dest, sha):
    got = sha256_of(part, os.path.getsize(part))
    if got != sha:
        os.remove(part)
        raise SystemExit(f"sha256 mismatch for {os.path.basename(dest)}: "
                         f"{got} != {sha} (partial file removed; run again)")
    os.replace(part, dest)


def fetch_llama(root):
    target = os.path.join(root, "llama-bin", LLAMA_BUILD)
    if os.path.isfile(os.path.join(target, "llama-server.exe")):
        print(f"llama.cpp {LLAMA_BUILD}: already present")
        return
    os.makedirs(target, exist_ok=True)
    zpath = os.path.join(target, f"llama-{LLAMA_BUILD}.zip")
    part = download(LLAMA["url"], zpath, LLAMA["bytes"])
    verify_and_place(part, zpath, LLAMA["sha256"])
    with zipfile.ZipFile(zpath) as z:
        z.extractall(target)
    os.remove(zpath)
    print(f"llama.cpp {LLAMA_BUILD}: {target}")


def fetch_gguf(root, source=None):
    sha, size = gguf_pin()
    models = os.path.join(root, "models")
    os.makedirs(models, exist_ok=True)
    dest = os.path.join(models, GGUF_NAME)
    if os.path.isfile(dest) and os.path.getsize(dest) == size:
        print(f"model: already present ({dest})")
        return
    if source:
        if os.path.getsize(source) != size:
            raise SystemExit(f"{source} has the wrong size for {GGUF_NAME}")
        try:
            os.link(source, dest)          # same volume: instant, no extra space
            how = "hard-linked"
        except OSError:
            shutil.copyfile(source, dest)  # other volume: plain copy
            how = "copied"
        if sha256_of(dest, size) != sha:
            os.remove(dest)
            raise SystemExit(f"{source} is not the pinned {GGUF_NAME}")
        print(f"model: {how} from {source}, sha256 verified")
        return
    part = download(GGUF_URL, dest, size)
    verify_and_place(part, dest, sha)
    print(f"model: {dest}")


def check():
    ok = True
    for name, url in (("llama.cpp", LLAMA["url"]), ("model", GGUF_URL)):
        req = urllib.request.Request(url, method="HEAD",
                                     headers={"User-Agent": "geodoc-fetch"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                print(f"{name}: HTTP {r.status}  {url}")
        except Exception as e:  # noqa: BLE001 — report every failure the same way
            ok = False
            print(f"{name}: FAILED {e}  {url}")
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="only test that both download URLs answer")
    ap.add_argument("--gguf-from", metavar="FILE",
                    help="use an existing copy of the model instead of downloading")
    ap.add_argument("--root", default=ROOT,
                    help="where llama-bin/ and models/ go (default: the repo)")
    a = ap.parse_args(argv)
    if a.check:
        return 0 if check() else 1
    if sys.platform != "win32":
        print("note: the pinned llama.cpp build is the Windows x64 CPU zip; on "
              "other systems build llama.cpp b10155 yourself and point "
              "models.local.json at its llama-server")
    else:
        fetch_llama(a.root)
    fetch_gguf(a.root, a.gguf_from)
    return 0


if __name__ == "__main__":
    sys.exit(main())
