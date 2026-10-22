# geodoc shell — stdlib HTTP server (zero-dependency law: standard library
# only). Browser IS the UI (owner's testability requirement); the same surface
# gets wrapped by Tauri later. v1 endpoints: jobs (run pipeline, inspect,
# download outputs) + contexts (list/fork — the core store, model wiring next).
#
# Usage: PYTHONUTF8=1 python app/server.py [--port 7420]

import argparse
import atexit
import json
import os
import secrets
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import threading
import time

import chat  # noqa: E402
import crew  # noqa: E402
import domain  # noqa: E402
import nightshift  # noqa: E402
import llm  # noqa: E402
import refleksja  # noqa: E402
import rewizja  # noqa: E402
import rozmowa  # noqa: E402
import stages  # noqa: E402
import store  # noqa: E402


def follow_log(job, timeout_s=180.0, poll_s=0.25):
    """Generator over a job's tasks/log.jsonl lines as they appear — the feed
    behind live gate-lighting. Ends after the 'pieczec' stage (the pipeline's
    last write) or on timeout."""
    path = os.path.join(stages.JOBS, job, "tasks", "log.jsonl")
    seen = 0
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if os.path.isfile(path):
            lines = open(path, encoding="utf-8").read().splitlines()
            for line in lines[seen:]:
                yield line
                if '"stage": "pieczec"' in line:
                    return
            seen = len(lines)
        time.sleep(poll_s)

UI = os.path.join(HERE, "ui.html")
TESTDATA_PDF = os.path.join(ROOT, "testdata", "operat_sample.pdf")
PROMPTS_USER = os.path.join(ROOT, "prompts", "user")


def _prompt_paths(name):
    """Validated pair (golden, user) for an agent name; None if unknown agent."""
    if name not in llm.prompt_list():
        return None
    return (os.path.join(ROOT, "prompts", "golden", name + ".md"),
            os.path.join(PROMPTS_USER, name + ".md"))


def job_detail(name):
    d = os.path.join(stages.JOBS, name)
    def load(*parts, default=None):
        p = os.path.join(d, *parts)
        return json.load(open(p, encoding="utf-8")) if os.path.isfile(p) else default
    log_p = os.path.join(d, "tasks", "log.jsonl")
    log = [json.loads(l) for l in open(log_p, encoding="utf-8")] \
        if os.path.isfile(log_p) else []
    outs = sorted(os.listdir(os.path.join(d, "out"))) \
        if os.path.isdir(os.path.join(d, "out")) else []
    pages = sorted(os.listdir(os.path.join(d, "transcript"))) \
        if os.path.isdir(os.path.join(d, "transcript")) else []
    return dict(name=name, log=log, header=load("extracted", "header.json"),
                wykaz=load("extracted", "wykaz.json"),
                checks=load("checks", "invariants.json"),
                rodowod=load("checks", "rodowod.json", default={}),
                pieczec=load("checks", "pieczec.json"),
                docmap=load("docmap.json"),
                outputs=outs, transcript_pages=pages)


TOKEN = None          # set by --token; None = open dev mode on loopback
PORT = 7420

# mode-exclusion law (owner 13:18): the per-model queue holds ONE consumer —
# a single/supervised run racing a live batch would interleave two jobs on
# one engine; the batch wins, the single mode explains itself and points at
# the civilized stop
BATCH_BUSY = ("Trwa przetwarzanie kolejki zadań. Analiza pojedynczego "
              "dokumentu i tryb krok po kroku są niedostępne do jej "
              "zakończenia. Możesz zatrzymać kolejkę — bieżące zadanie "
              "zostanie dokończone, kolejne nie zostaną rozpoczęte.")


def _allowed_hosts():
    return {f"localhost:{PORT}", f"127.0.0.1:{PORT}", "localhost", "127.0.0.1"}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _authorized(self):
        """uTorrent-Web triad (lessons of the uTorrent RCE + Ollama
        CVE-2024-28224): Host allowlist kills DNS rebinding, Origin check
        kills cross-site calls, CSPRNG token (URL once -> cookie) gates
        every request when enabled."""
        host = (self.headers.get("Host") or "").strip()
        if host and host not in _allowed_hosts():
            return False
        origin = self.headers.get("Origin")
        if origin:
            o = urllib.parse.urlparse(origin)
            if f"{o.hostname}:{o.port}" not in _allowed_hosts() \
                    and o.hostname not in ("localhost", "127.0.0.1"):
                return False
        if TOKEN is None:
            return True
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if qs.get("token", [None])[0] == TOKEN:
            self._grant_cookie = True
            return True
        return f"geodoc_token={TOKEN}" in (self.headers.get("Cookie") or "")

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path, ctype):
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if getattr(self, "_grant_cookie", False) and TOKEN:
            self.send_header("Set-Cookie",
                             f"geodoc_token={TOKEN}; HttpOnly; SameSite=Strict")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self._authorized():
            return self._json(dict(error="unauthorized"), 403)
        p = urllib.parse.urlparse(self.path)
        if p.path == "/":
            return self._file(UI, "text/html; charset=utf-8")
        if p.path == "/pomoc":
            return self._file(os.path.join(HERE, "pomoc.html"),
                              "text/html; charset=utf-8")
        if p.path.startswith("/czcionki/"):
            # self-hosted fonts (offline law: no CDN); path-scoped like /file/
            base = os.path.normpath(os.path.join(HERE, "czcionki"))
            rel = urllib.parse.unquote(p.path[len("/czcionki/"):])
            full = os.path.normpath(os.path.join(base, rel))
            if (not full.startswith(base) or not os.path.isfile(full)
                    or not full.endswith((".woff2", ".css"))):
                return self._json(dict(error="not found"), 404)
            ctype = ("font/woff2" if full.endswith(".woff2")
                     else "text/css; charset=utf-8")
            return self._file(full, ctype)
        if p.path == "/api/rozmowy":
            return self._json(rozmowa.lista())
        if p.path == "/api/firma":
            # installation identity (branding law 06.08): client firm's name
            # in the chrome — operator drops profiles/firma.json by hand
            fp = os.path.join(stages.ROOT, "profiles", "firma.json")
            f = json.load(open(fp, encoding="utf-8")) \
                if os.path.isfile(fp) else {}
            return self._json(dict(nazwa=f.get("nazwa")))
        if p.path == "/api/jobs":
            jobs = sorted(os.listdir(stages.JOBS)) if os.path.isdir(stages.JOBS) else []
            return self._json([job_detail(j)["checks"] and j or j for j in jobs])
        if p.path.startswith("/api/job/"):
            return self._json(job_detail(p.path.split("/", 3)[3]))
        if p.path == "/api/contexts":
            return self._json(store.listing())
        if p.path.startswith("/api/context/") and p.path.endswith("/rows"):
            cid = p.path.split("/")[3]
            try:
                return self._json(store.transcript(cid))
            except FileNotFoundError:
                return self._json(dict(error="unknown context"), 404)
        if p.path == "/api/prompts":
            return self._json([llm.prompt_info(n) for n in llm.prompt_list()])
        if p.path.startswith("/api/prompt/"):
            name = p.path.rsplit("/", 1)[1]
            paths = _prompt_paths(name)
            if not paths:
                return self._json(dict(error="unknown agent"), 404)
            golden_p, user_p = paths
            return self._json(dict(
                name=name,
                golden=open(golden_p, encoding="utf-8").read(),
                user=(open(user_p, encoding="utf-8").read()
                      if os.path.isfile(user_p) else None),
                **{k: v for k, v in llm.prompt_info(name).items() if k != "name"}))
        if p.path == "/api/queue/active":
            bid = nightshift.active()
            if not bid:
                return self._json(dict(bid=None))
            try:
                return self._json(nightshift.postep(bid))
            except Exception:
                return self._json(dict(bid=bid))
        if p.path.startswith("/api/queue/"):
            bid = p.path.rsplit("/", 1)[1]
            try:
                return self._json(nightshift.status(bid))
            except FileNotFoundError:
                return self._json(dict(error="unknown batch"), 404)
        if p.path.startswith("/api/rewizja/"):
            job = urllib.parse.unquote(p.path.rsplit("/", 1)[1])
            return self._json(rewizja.rozmowa(job))
        if p.path.startswith("/api/rodowod/"):
            # slice 9: full measurement pedigree of one point from the
            # domain graph (bi-temporal — superseded rows stay visible)
            return self._json(domain.rodowod(p.path.rsplit("/", 1)[1]))
        if p.path == "/api/domain/summary":
            return self._json(domain.summary())
        if p.path.startswith("/api/events/"):
            # SSE: gates light up live while the pipeline runs
            job = p.path.rsplit("/", 1)[1]
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            try:
                for line in follow_log(job):
                    self.wfile.write(f"data: {line}\n\n".encode("utf-8"))
                    self.wfile.flush()
                self.wfile.write(b"event: end\ndata: {}\n\n")
                self.wfile.flush()
            except (ConnectionAbortedError, BrokenPipeError):
                pass
            return
        if p.path.startswith("/api/evidence/"):
            # rentgen operatu: value -> page image + highlighted region(s);
            # text layer answers with PDF geometry, scans with OCR line boxes
            parts = p.path.split("/")
            if len(parts) < 5:
                return self._json(dict(error="evidence path"), 400)
            job, page_s = parts[3], parts[4]
            qs = urllib.parse.parse_qs(p.query)
            value = (qs.get("value") or [""])[0]
            try:
                page_n = int(page_s)
            except ValueError:
                return self._json(dict(error="bad page"), 400)
            job_dir = os.path.join(stages.JOBS, job)
            pdf = os.path.join(job_dir, "source", "operat.pdf")
            if not os.path.isfile(pdf) or not value:
                return self._json(dict(error="unknown job or empty value"), 404)
            png_rel = f"pages/page-{page_n:03d}.png"
            png_abs = os.path.join(job_dir, "pages", f"page-{page_n:03d}.png")
            if not os.path.isfile(png_abs):
                from pdfpages import render_page
                render_page(pdf, page_n, png_abs)
            from pdfpages import find_value_boxes
            rects = find_value_boxes(pdf, page_n, value)
            src = "warstwa tekstowa PDF"
            if not rects:
                op = os.path.join(job_dir, "extracted", f"ocr-{page_n:03d}.json")
                if os.path.isfile(op):
                    o = json.load(open(op, encoding="utf-8"))
                    rects = [l["box"] for l in o.get("lines", [])
                             if l.get("box") and value in (l.get("text") or "")]
                    src = "OCR (RapidOCR)"
            return self._json(dict(
                found=bool(rects), rects=rects, zrodlo=src,
                png=f"/file/{urllib.parse.quote(job)}/{png_rel}",
                pdf=f"/file/{urllib.parse.quote(job)}/source/operat.pdf"
                    f"#page={page_n}"))
        if p.path.startswith("/file/"):
            rel = urllib.parse.unquote(p.path[len("/file/"):])
            full = os.path.normpath(os.path.join(stages.JOBS, rel))
            if not full.startswith(os.path.normpath(stages.JOBS)):
                return self._json(dict(error="scope"), 403)
            if not os.path.isfile(full):
                return self._json(dict(error="not found"), 404)
            ctype = ("image/png" if full.endswith(".png") else
                     "application/pdf" if full.endswith(".pdf") else
                     "text/csv; charset=utf-8" if full.endswith(".csv") else
                     "application/vnd.openxmlformats-officedocument."
                     "spreadsheetml.sheet" if full.endswith(".xlsx") else
                     "text/plain; charset=utf-8")
            return self._file(full, ctype)
        return self._json(dict(error="?"), 404)

    def do_POST(self):
        if not self._authorized():
            return self._json(dict(error="unauthorized"), 403)
        p = urllib.parse.urlparse(self.path)
        ln = int(self.headers.get("Content-Length") or 0)
        if p.path == "/api/upload":
            # PDF dropped into the chat: raw body, name in the query;
            # 200 MB cap (scans bywają wielkie), scope: uploads/ only
            if ln > 200 * 1024 * 1024:
                return self._json(dict(error="plik przekracza 200 MB"), 413)
            qs = urllib.parse.parse_qs(p.query)
            nazwa = os.path.basename((qs.get("nazwa") or ["dokument.pdf"])[0])
            if not nazwa.lower().endswith(".pdf"):
                return self._json(dict(error="oczekiwany plik PDF"), 400)
            updir = os.path.join(stages.ROOT, "uploads")
            os.makedirs(updir, exist_ok=True)
            path = os.path.join(
                updir, time.strftime("%Y%m%d-%H%M%S-") + nazwa)
            with open(path, "wb") as f:
                pozostalo = ln
                while pozostalo > 0:
                    czesc = self.rfile.read(min(1 << 20, pozostalo))
                    if not czesc:
                        break
                    f.write(czesc)
                    pozostalo -= len(czesc)
            return self._json(dict(path=path, nazwa=nazwa, bajty=ln))
        body = json.loads(self.rfile.read(ln) or b"{}") if ln else {}
        if p.path == "/api/rozmowa/start":
            if (akt := nightshift.active()):
                return self._json(dict(error=BATCH_BUSY, bid=akt), 409)
            pdf = body.get("pdf_path") or TESTDATA_PDF
            if not os.path.isfile(pdf):
                return self._json(dict(error="pdf_path not a file"), 400)
            return self._json(rozmowa.start(pdf, body.get("nazwa")))
        if p.path == "/api/rozmowa/krok":
            try:
                return self._json(rozmowa.krok(
                    body["rozmowa"], body.get("action", "run"),
                    body.get("dopisek")))
            except Exception as e:
                return self._json(dict(error=str(e)[:300]), 500)
        if p.path == "/api/rozmowa/popraw":
            try:
                return self._json(rozmowa.popraw(
                    body["rozmowa"], body["stage"], body["dopisek"]))
            except Exception as e:
                return self._json(dict(error=str(e)[:300]), 500)
        if p.path == "/api/rozmowa/ponownie":
            try:
                return self._json(rozmowa.przetworz_ponownie(body["job"]))
            except Exception as e:
                return self._json(dict(error=str(e)[:300]), 400)
        if p.path == "/api/rozmowa/pytanie":
            try:
                return self._json(rozmowa.pytanie(
                    body["rozmowa"], body["tekst"]))
            except Exception as e:
                return self._json(dict(error=str(e)[:300]), 500)
        if p.path == "/api/rozmowa/adoptuj":
            job = body.get("job")
            if not (job and os.path.isdir(os.path.join(stages.JOBS, job))):
                return self._json(dict(error="unknown job"), 400)
            return self._json(rozmowa.adoptuj(job))
        if p.path == "/api/rozmowa/marker":
            try:
                return self._json(rozmowa.marker(
                    body["rozmowa"], body.get("status", "brak")))
            except Exception as e:
                return self._json(dict(error=str(e)[:200]), 400)
        if p.path == "/api/run-sample":
            res = stages.run_all(TESTDATA_PDF)
            return self._json(res)
        if p.path == "/api/queue":
            paths = body.get("pdf_paths") or []
            if not isinstance(paths, list) or not paths:
                return self._json(dict(error="pdf_paths list required"), 400)
            return self._json(dict(id=nightshift.submit(paths)))
        if p.path == "/api/queue/stop":
            try:
                return self._json(nightshift.stop(body["id"]))
            except Exception as e:
                return self._json(dict(error=str(e)[:200]), 400)
        if p.path == "/api/crew/start":
            if (akt := nightshift.active()):
                return self._json(dict(error=BATCH_BUSY, bid=akt), 409)
            pdf = body.get("pdf_path") or TESTDATA_PDF
            if not os.path.isfile(pdf):
                return self._json(dict(error="pdf_path not a file"), 400)
            return self._json(crew.start(pdf, body.get("name")))
        if p.path == "/api/crew/step":
            try:
                return self._json(crew.step(body["job"],
                                            body.get("action", "accept"),
                                            body.get("dopisek")))
            except Exception as e:
                return self._json(dict(error=str(e)[:300]), 500)
        if p.path == "/api/run-sample-async":
            if (akt := nightshift.active()):
                return self._json(dict(error=BATCH_BUSY, bid=akt), 409)
            job = time.strftime("job-%Y%m%d-%H%M%S-live")
            threading.Thread(target=stages.run_all,
                             args=(TESTDATA_PDF, job), daemon=True).start()
            return self._json(dict(job=job))
        if p.path == "/api/run":
            if (akt := nightshift.active()):
                return self._json(dict(error=BATCH_BUSY, bid=akt), 409)
            pdf = body.get("pdf_path")
            if not (pdf and os.path.isfile(pdf)):
                return self._json(dict(error="pdf_path missing or not a file"), 400)
            return self._json(stages.run_all(pdf, name=body.get("name")))
        if p.path == "/api/refleksja/zastosuj":
            try:
                return self._json(refleksja.zastosuj(
                    body["agent"], body.get("zasady") or []))
            except Exception as e:
                return self._json(dict(error=str(e)[:200]), 400)
        if p.path == "/api/refleksja":
            job = body.get("job")
            if not (job and os.path.isdir(os.path.join(stages.JOBS, job))):
                return self._json(dict(error="unknown job"), 400)
            try:
                return self._json(refleksja.zaproponuj(job))
            except Exception as e:
                return self._json(dict(error=str(e)[:300]), 500)
        if p.path == "/api/rewizja":
            job = body.get("job")
            pyt = (body.get("pytanie") or "").strip()
            if not (job and os.path.isdir(os.path.join(stages.JOBS, job))):
                return self._json(dict(error="unknown job"), 400)
            if not pyt:
                return self._json(dict(error="pytanie missing"), 400)
            try:
                return self._json(rewizja.zapytaj(job, pyt))
            except Exception as e:
                return self._json(dict(error=str(e)[:300]), 500)
        if p.path == "/api/chat":
            msg = (body.get("message") or "").strip()
            if not msg:
                return self._json(dict(error="message missing"), 400)
            cid = body.get("ctx_id") or store.create(
                role="main", model=body.get("model", "worker"),
                note="czat operatora")
            try:
                res = chat.turn(cid, msg,
                                force_compact=bool(body.get("force_compact")))
                return self._json(res)
            except Exception as e:
                return self._json(dict(error=str(e)[:300], ctx_id=cid), 500)
        if p.path == "/api/context/create":
            cid = store.create(role=body.get("role", "main"),
                               model=body.get("model", "worker"),
                               note=body.get("note"))
            return self._json(dict(id=cid))
        if p.path == "/api/context/fork":
            fid = store.fork(body["id"], upto=body.get("upto"),
                             note=body.get("note"))
            return self._json(dict(id=fid))
        if p.path == "/api/context/append":
            i = store.append(body["id"], body.get("role", "note"),
                             body.get("content", ""))
            return self._json(dict(index=i))
        if p.path.startswith("/api/prompt/") and p.path.endswith("/reset"):
            name = p.path.split("/")[3]
            paths = _prompt_paths(name)
            if not paths:
                return self._json(dict(error="unknown agent"), 404)
            if os.path.isfile(paths[1]):
                os.remove(paths[1])
            return self._json(llm.prompt_info(name))
        if p.path.startswith("/api/prompt/"):
            name = p.path.rsplit("/", 1)[1]
            paths = _prompt_paths(name)
            if not paths:
                return self._json(dict(error="unknown agent"), 404)
            content = body.get("content")
            if not isinstance(content, str) or not content.strip():
                return self._json(dict(error="content missing"), 400)
            os.makedirs(PROMPTS_USER, exist_ok=True)
            with open(paths[1], "w", encoding="utf-8") as f:
                f.write(content)
            return self._json(llm.prompt_info(name))
        return self._json(dict(error="?"), 404)


def main():
    global TOKEN, PORT
    # Windows gives a redirected or DEVNULL stdout the ANSI code page
    # (cp1252), and the first Polish letter in a log line would raise
    # UnicodeEncodeError and kill the run; UTF-8 with replacement never does.
    for _s in (sys.stdout, sys.stderr):
        if _s is not None and hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=7420)
    ap.add_argument("--token", help="'auto' generates a CSPRNG token; "
                                    "omit for open dev mode on loopback")
    a = ap.parse_args()
    PORT = a.port
    if a.token:
        TOKEN = secrets.token_urlsafe(16) if a.token == "auto" else a.token
    atexit.register(llm.stop)          # never orphan a 42 GB sidecar
    url = f"http://127.0.0.1:{a.port}/" + (f"?token={TOKEN}" if TOKEN else "")
    print(f"geodoc shell: {url}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()


if __name__ == "__main__":
    main()
