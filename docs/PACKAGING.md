# geodoc — packaging (uTorrent-Web pattern, two-artifact delivery)

Delivery = **a small signed setup.exe** + **a model-pack** (GGUFs next to the
installer on USB, or downloaded on first start). Never 60 GB in a single
installer without need (NSIS/Tauri-bundler have a hard 2 GB limit; Inno
can read large files from `{src}` without compiling them inside).

## Artifacts and where they come from

| Artifact | Source | Status |
|---|---|---|
| `installer/geodoc.iss` | repo | EXISTS — installer definition |
| `start_geodoc.pyw` | repo | EXISTS — launcher: single-instance, CSPRNG token, browser |
| Localhost security triad | `app/server.py --token auto` | EXISTS — token→cookie, Host allowlist (DNS rebinding), Origin check; tested 403/200 |
| `installer/python-embed/` | python.org embeddable 3.12 + `pip install -r requirements.txt --target` | to be prepared at build time |
| `installer/llama-bin/` | llama.cpp release b10155 (Windows CPU, MIT; CPU-dispatch DLLs: zen4/haswell/... — one build for every CPU; tools/fetch_runtime.py) | to be copied at build time |
| model-pack `models/` | GGUFs + `manifest.json` (sha256 + sizes) | 30B: Q4_K_M (present); 80B: **fresh bartowski IQ4_NL (imatrix, 45.31 GB) DOWNLOADING** — found ready-made, owner's BF16 pull NOT NEEDED; after the bench, swap the manifest (E6c in IDEAS) |
| code signing | **Certum** (Polish CA; Azure Trusted Signing without EU validation) | owner's decision/purchase |
| PyMuPDF AGPL | runtime on pypdfium2 (BSD/Apache); PyMuPDF only in dev tools | RESOLVED 06.08 (wave 15) |

## Build steps (eventually the script `tools/build_installer.ps1`)

1. `python -m pip download/install -r requirements.txt --target installer\python-embed\Lib\site-packages`
   on top of the unpacked python-3.12-embed-amd64 (uncomment `import site`
   in `python312._pth`).
2. Copy `llama-server.exe` + DLLs to `installer\llama-bin\`;
   `models.json` in the package points to `{app}\llama-bin\llama-server.exe`
   and `{app}\models\*.gguf`.
3. Model-pack: `models\` with the GGUFs + `manifest.json`; place it NEXT TO setup.exe
   (USB) — the installer will import it; if absent = download wizard (resume+sha256).
4. `tools\build_tray.ps1` → `src-tauri\geodoc-tray.exe` (0.5 MB). On a machine without
   MSVC: the script sets up rustup's GNU toolchain itself (self-contained ld) and shims
   llvm-ar as llvm-dlltool (the bundled binutils-dlltool has no as.exe).
   Compile ONLY from PowerShell — Git-Bash substitutes the coreutils `link.exe`
   for the MSVC linker and the build dies on "extra operand".
5. `iscc installer\geodoc.iss` → `installer\Output\geodoc-setup.exe`.
6. Signing: `signtool` with a code-signing key (e.g. Certum SimplySign) on setup.exe and all
   exe/dll files in the package (including `geodoc-tray.exe`).

## PDF and licences

**PDF and licences — resolved 06.08 (wave 15):** the runtime reads PDFs through
pypdfium2 (BSD/Apache, facade app/pdfpages.py); PyMuPDF (AGPL) remains only
in the dev tools for generating fixtures (requirements-dev.txt) and does not go
into the installer.

## Security (implemented, lessons from real CVEs)

- bind to 127.0.0.1 only; 128-bit CSPRNG token in the first-open URL →
  HttpOnly cookie; hard allowlist of the Host header (uTorrent RCE, Ollama
  CVE-2024-28224 = DNS rebinding); rejecting foreign Origins.
- launcher: single-instance via a lock-file holding the URL of the running instance
  (a second start only opens the browser); a watchdog waits on the server process;
  `atexit` in the server kills the llama sidecar (never an orphaned 42 GB process).
- tray (`src-tauri\geodoc-tray.exe`, tray-icon+tao without webview, 0.5 MB,
  imports only system DLLs) = the front entry: an icon in the notification area,
  „Otwórz" ("Open") → the default browser on the URL from the lock-file, „Zakończ" ("Quit") →
  `taskkill /T /F` on the launcher's PID — kills the WHOLE tree (launcher → server →
  llama; the smoke test caught even a great-grandchild). Job Object KILL_ON_JOB_CLOSE remains
  as a future hardening (resilience against the tray being killed from Task Manager).
