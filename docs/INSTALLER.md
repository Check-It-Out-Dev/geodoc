# INSTALLER — research, decisions, evidence (06.08)

Method: reconnaissance of primary sources (ishelp Inno 6.6, the real install.iss of
Git-for-Windows, crates.io, MS Learn) → implementation of the checklist → a live
GUI drill (pywinauto: installation → registration → launch →
uninstallation → silent reinstall) → fixes from the findings.

## 1. Decisions (with research rationale)

| Decision | Value | Why |
|---|---|---|
| Engine | Inno Setup 6 | no 2 GB limit (NSIS/Tauri have one), {src} for the model-pack, GfW pattern |
| Python→exe | embeddable zip + Rust tray | binaries signed by the PSF ≈ zero AV false alarms; PyInstaller v6+ = an explosion of false positives (#8164) |
| AppId | `{2319CCFB-738C-41E5-ACF9-867B7D75EB32}` FIXED — the open-source release's own GUID | update identity; the previous pseudo-GUID (GEODOC000001) was invalid |
| Mode | per-user (`lowest`) + `PrivilegesRequiredOverridesAllowed=dialog` | VS Code convention (%LOCALAPPDATA%\Programs); the dialog allows a deliberate /ALLUSERS |
| Mutexes | `AppMutex=geodoc-tray-mutex` (tray: raw CreateMutexW, zero dependencies) + `SetupMutex` | installer and uninstaller refuse while the application is running — proven in the drill ×2 |
| Exe resources | rcedit after the build (build_tray.ps1) | no windres/llvm-rc in the GNU toolchain; winresource would require MinGW; NOTE: future code signing (e.g. Certum) MUST come AFTER rcedit |
| Icon | survey-control marker (design system), multi-size .ico from tools/make_ikony.py | product identity: exe, shortcuts, wizard title bar, Apps entry |
| Wizard branding | wizard panels with the geodoc mark, multi-DPI (100–250%, sizes per ishelp 6.6: 202×386… / 58×58…; tools/make_ikony.py) | the product mark on the large panel and in the header |
| Language | Polish (Languages\Polish.isl) | PL-business register consistent with the application |
| Compression | lzma2/ultra64 solid | 144.6 MB (−4.9 MB vs before) |
| Logs | SetupLogging=yes | %TEMP%\Setup Log <date>.txt — diagnostics on the office machine |
| Data on uninstall | a question defaulting to NO (MB_DEFBUTTON2) | researched pattern; removes jobs/models/profiles/prompts\user/contexts ONLY with consent |
| Orphans on uninstall | [Code] ZabijSieroty(): Stop-Process by the {app} path (only python/pythonw/geodoc-tray/llama-server) | drill finding: the python console survived a force-kill of the tray and blocked deletion |
| VersionInfo setup+tray | Norbert Marchewka / 0.95 | Properties→Details without an amateurish 0.0.0.0 |

## 2. Registration in Windows (verified live)

`HKCU\...\Uninstall\{AppId}_is1`: DisplayName geodoc · DisplayVersion 0.95 ·
Publisher **Norbert Marchewka** · DisplayIcon → geodoc-tray.exe (marker) ·
URLInfoAbout · EstimatedSize (auto ~576 MB) · Uninstall/QuietUninstallString.
Shortcuts: Start menu + desktop (task, checked by default).

## 3. GUI drill (pywinauto) — run and evidence

1. Mode dialog („Wybierz typ instalacji aplikacji" (Choose the application install type)) → „dla bieżącego
   użytkownika (zalecane)" (for the current user (recommended)).
2. Polish wizard: „Witamy" (Welcome; geodoc panel + marker) → „Lokalizacja" (Location) → „Zadania" (Tasks) →
   „Gotowy" (Ready) → progress → „Zakończ" (Finish) with „Uruchom geodoc" (Launch geodoc) → **tray + server 7420
   came up from the install location**.
3. Uninstall while the application is running → guard: „Dezinstalator wykrył, iż
   aplikacja geodoc jest aktualnie uruchomiona" (the uninstaller detected that geodoc is currently running) (AppMutex works).
4. Data question (modal title: „Dezinstalator" (Uninstaller)) → NO → **only contexts/
   and jobs/ remained** — the operator's data untouched.
5. Silent reinstall `/SILENT /CURRENTUSER`: the registry entry returns, **jobs/
   survived the cycle** (continuity), the tray does not start (skipifsilent).
6. Bonus evidence: the hanging final screen of the old uninstall held
   SetupMutex — the new installer politely WAITED with a dialog instead of
   crashing. The mutex system confirmed three times.

## 4. SmartScreen — the truth for the owner

An unsigned exe = "Windows protected your PC" until reputation is built for the
SPECIFIC hash (every release starts from zero). Nothing bypasses this (MOTW
propagates through zip). Since 2024 EV has no instant reputation — **Certum OV
is enough**; sign every build (timestamp!), reputation grows from
clean installs. For the user: „Więcej informacji → Uruchom mimo to" (More info → Run anyway) +
publish the SHA-256. Build order once signing is in place:
cargo → rcedit → **sign** → iscc (SignTool=certum).

## 5. Single-disk medium — a SINGLE-MODEL product (owner's decision 07.08)

**Release (since 07.08 11:47 — model BUNDLED, owner's decision)**:
a directory with `geodoc-setup-<version>.exe` + volumes
`geodoc-setup-<version>-N.bin` (Inno DiskSpanning; >2 GB of compressed
data does not fit in a single exe — the GOG pattern). The user clicks
ONLY setup.exe; the bins are read automatically; all files must sit
in one directory. The model goes `nocompression` (weights are incompressible) +
`onlyifdoesntexist` (an update does not rewrite 18.6 GB; repairing
a damaged file = delete it and run the installer again).
`models.json` and `models\manifest.json` are installed by setup. The application is
fully offline. Build cost: every `iscc` rewrites ~18.7 GB of
volumes (~2–5 min on NVMe).

**Licence in the wizard**: the licence page shows the MIT text (LicenseFile =
LICENSE in the root directory; a copy also goes to {app}); the list of OSS
components → docs\THIRD-PARTY-LICENSES.md. geodoc = the product name.

**One model, two roles.** Qwen3-30B serves both roles as request
PROFILES (worker = deterministic transcription; evaluator = verdicts and
conversation) on two llama-server processes — mmap shares the weights, physically
~20–24 GiB. Pack 18.6 GB; golden E2E 172 s (dev); the full golden battery
+ arsenal + review (waves 13/15). The 80B/„Standardowa" (Standard) variants were withdrawn from the
release on 07.08 (wave 18 analysis: verdicts were always computed by the worker
model anyway; 80B = 2× the transcription time and a 64 GB RAM threshold) — 80B remains
a research option, return = one manifest entry.

An application update does not rewrite 18.6 GB (`onlyifdoesntexist`);
a freshly copied model or a manifest change deletes `models\.verified`
— the launcher then computes the full sha256 once (18.6 GB ≈ 13 s on NVMe).

**Why the models are not compiled into setup.exe.** Above 2 GB of
compressed data Inno requires DiskSpanning (setup.exe + ~31 .bin files
at 64 GB — the GOG pattern, it works, but the build rewrites 64 GB on
every iteration); the `external` flag reads the GGUFs from `{src}` without
compiling them — the build takes seconds, and the medium carries separate files anyway.

**Why not zip.** Quantisation ALREADY is compression (FP16 149 GB →
IQ4_NL 45.3 GB); after it the weights are high-entropy noise. Measured 06.08
on 256 MiB from the middle of the 30B file: deflate-6 = 97.77 % of the original, lzma2-6 =
98.03 %. A gain of ~2 % (≈1.4 GB on 64 GB) at the cost of an unpacking step and 2×
temporary space — pointless. Quality: lossless compression changes
nothing; quality is set by the choice of quantisation, not by archiving.

**GUI drill evidence (06.08 20:1x, pywinauto).** A medium with only the 30B:
preselection „Lekka" (Light) ✓ (a historical drill from the 3-variant era — the
external/guard/verified mechanics are the same); switching to a variant without its file → blocked
with a message about the missing file ✓; installing „Lekka": copying
18.6 GB in 61 s, `models.json`/`manifest.json` = lekki, `.verified`
absent after import ✓; `verify_models()` = True after 13.3 s, marker
written ✓.

## 6. v-next items

- The tray's Job Object did not cover the server console on taskkill /F (emergency
  path; a normal „Zakończ" (Quit) cleans up) — review the spawn in start_geodoc.
- An .ico icon for exported documents (associations) — after the format decision.
- Code signing (e.g. Certum): setup+tray+unins (SignTool), section 4.

## 5. E2E findings 11.08 (silent drill of the built 0.95 from Output/)

Run: `/VERYSILENT /SUPPRESSMSGBOXES /CURRENTUSER /DIR=<test>` ->
installation 98 s (exit 0, model 17.28 GB) -> HKCU registry correct -> tray ->
server 7420 with the token gate (contexts\.shell.lock) -> upload -> classifier
27.2 s (including the lazy start of llama-server; llama RAM 31.6 GB at 2x ctx 16k)
-> uninstall.

| Finding | Effect | Fix |
|---|---|---|
| The data MsgBox in [Code] is not subject to /SUPPRESSMSGBOXES; the second phase (_unins.tmp in %TEMP%) holds the dialog and the files | a silent uninstall hangs forever (mass deployments!) | guard `not UninstallSilent` - silent = data stays without asking |
| Licence text only in the wizard, not on disk | the user cannot see the licence they accepted | `Source: LICENSE -> {app}` — LICENSE in the wizard and on disk |
| uploads/ outside the data-deletion list | orphaned PDFs after uninstalling with YES | DelTree uploads/ |
| Install target >~130 path characters | MoveFile code 3 (MAX_PATH 260; the deepest site-packages file ~128 chars), rollback with auto-Abort | no change - the default %LOCALAPPDATA%\Programs\geodoc has headroom; documented |
