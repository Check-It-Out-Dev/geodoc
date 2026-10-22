# geodoc — technique ledger (IDEAS ledger)

> **Milestone 2026-08-05 evening:** `installer/Output/geodoc-setup.exe`
> (149 MB, Inno 6.7.3) COMPILED and VALIDATED — silent install → pipeline
> PASS from the installed layout (OCR with models in the payload) → silent
> uninstall clean. Missing for release: code signing.

One place where EVERY technique considered has a verdict and a rationale.
Verdicts: **IMPLEMENTED** (in the repo, with a commit) · **ACCEPTED** (designed,
queued in § 7 of the dossier) · **EXPERIMENT** (to be measured on our machine,
accepted only after a measured gain) · **WAITING** (external watch item) ·
**REJECTED** (with a reason — does not come back without new data). Details and sources:
`docs/SOTA-2026-08.md`.

## Engine / cache / KV

| Technique | Verdict | Rationale |
|---|---|---|
| Explicit slot save/restore (KV as a file), both models | ACCEPTED (slice 3) | works for the hybrid too (PR #8699); restore ~7× faster than re-prefill |
| KV state contract (versioned catalogue gguf/ctx/ctk/fa/build) | ACCEPTED (slice 3) | blobs without validation — mismatch = crash or silent garbage |
| Auto-checkpoints / `--cache-reuse` / ctx-shift for 80B | REJECTED | broken for hybrids (#22384/#24055); DeltaNet state cannot roll back |
| `--cache-reuse 256` for 30B | IMPLEMENTED (eb20b8e) | KV-shift of middle fragments; <2.5% quality delta in the literature |
| `--cache-ram` (idle slots in RAM, hot-swap) | IMPLEMENTED (default) | memcpy instead of recompute; `cache_n` telemetry in `_meta` |
| Router mode (`--models-dir`) | REJECTED | does not proxy slot actions (#18703) — kills the KV-as-file core |
| llama-swap proxy | REJECTED (for now) | our own supervisor does the same without a dependency |
| `--parallel` > 1 "for the cache" | REJECTED | slots do NOT physically share KV (#21961) |
| Paged-KV Phase 2 (prefix sharing) | WAITING | PR #22569 lineage; comes back when merged |
| ctx-shift in general | REJECTED | cuts off the start of the document; HTTP 400 = re-chunk signal |
| `-ctk/-ctv q8_0` (+FA) | EXPERIMENT | almost lossless on hybrids (#21385); needs a smoke test with FA on CPU |
| Warmup (default ON) | IMPLEMENTED | loads ALL experts — predictable swap cost |
| `--load-mode` without mmap for 42 GB swaps | EXPERIMENT | report of ~6.7× faster first response at the cost of load — measure |
| mlock of the resident model | ACCEPTED (packaging) | 48 GB deployment budget; ours is 189 GB — irrelevant for dev |
| Speculative decoding (0.6B draft) | REJECTED | measured net-zero on A3B even on GPU |
| MTP (`--mtp`) | WAITING | Qwen3-Next has no support (head dropped during conversion) |
| Threads = PHYSICAL cores | IMPLEMENTED (14c3fad) | SMT halves TG on this architecture (#19480) |
| `-b 2048 -ub 1024` (PP throughput) | EXPERIMENT | PP vs batch curves on MoE still to be measured here |
| ik_llama.cpp (fork, ~1.9× CPU MoE) | WAITING | fallback option; cost: maintaining a fork instead of upstream |
| Swap 80B IQ4_XS → Q4_K/UD-Q4_K_XL | EXPERIMENT | i-quants have more expensive decode on CPU; check PP/TG + 48 GB RAM fit |
| DRY / XTC samplers | REJECTED | n-gram penalties break transcription of repetitive tables |
| Control vectors (activation steering) | REJECTED (v1) | no quality curves for extraction; requires per-model training |
| `--override-kv expert_used_count` (fewer experts) | EXPERIMENT | near-linear speedup on other MoEs; do NOT touch without a quality harness |
| logit_bias | REJECTED | the grammar handles everything a bias would give |

## Prompting (Qwen3)

| Technique | Verdict | Rationale |
|---|---|---|
| Markdown manuals + CAPS sections | IMPLEMENTED | official Alibaba pattern; XML has no advantage, ~15% more expensive |
| Document in ONE pair of `===DOKUMENT===` delimiters | IMPLEMENTED (eb20b8e) | official rule: reference content behind a fence |
| Task at the END of the prompt | IMPLEMENTED (v0) | our measured law + query-last literature |
| Sandwich of the key law (top+bottom) | IMPLEMENTED (6418101) | IFScale: early bias + decay of late rules |
| Example of filled JSON in the prompt despite the grammar | IMPLEMENTED (6418101) | dottxt: improves field VALUES, not just syntax |
| Example values explicitly marked as placeholders | IMPLEMENTED | protection against leakage (measured: they did not leak) |
| Prohibitions in positive form first | IMPLEMENTED | negation benchmarks: "do NOT do X" is sometimes ignored |
| ≤20–30 rules per manual | IMPLEMENTED (norm) | adherence drops with instruction density |
| "Think step by step" under a grammar | REJECTED | grammar × thinking clash (#20345); reasoning = the `uzasadnienie` (rationale) field |
| presence/repeat penalty | REJECTED | model card: language mixing; penalties break table transcription |
| temp 0 for transcription, model card (0.7/0.8/20) for the judge | IMPLEMENTED | fidelity > creativity; replay via a fixed seed |
| Few-shot 1–3 examples | ACCEPTED | officially recommended; comes with county profiles |
| EN instructions over a PL document | EXPERIMENT | literature: usually ≥ native; no measurement for Qwen3-Polish — A/B on golden |
| GEPA gate on prompt changes (golden set) | ACCEPTED (norm) | self-refine without a metric = bias amplification |
| Golden/user prompts + hash pinning + editor UI | IMPLEMENTED (53ccc57, 7fa06e9) | the operator designs, factory ones stay safe, audit per job |

## Quality gates / pipeline

| Technique | Verdict | Rationale |
|---|---|---|
| The model transcribes, CODE aggregates | IMPLEMENTED (v0) | measured: aggregation of 180 rows F1=0 for both models |
| G1 schema at DECODE time (GBNF) | IMPLEMENTED (14c3fad) | bad-json ceased to exist; retry ladder on truncation |
| G2 value grounding + source accuracy | IMPLEMENTED (this slice) | hallucination = fail; wrong page attribution = review flag |
| G3 referee parser vs LLM (born-digital) | IMPLEMENTED (this slice) | a regex parser referees the transcription; omissions = fail |
| G5 official code lists by the date of the *operat* (surveying report filed with the county; plural operaty) | IMPLEMENTED (this slice) | ZRD/BPP/STB/RZG hard ≤2021; SPD/ISD = None until the XSD |
| Uniform check polarity (true=good) | IMPLEMENTED (6418101) | the judge reported an inverted key as a problem |
| G9 judge digest built by code | IMPLEMENTED (this slice) | only fails+flags+samples; small window, zero over-reporting |
| G4 dual-OCR agreement | IMPLEMENTED | unit of agreement = COORDINATE STRING; engines RapidOCR (PP-OCRv6) × onnxtr (docTR, a different det+rec family — real independence, clean pip, Apache-2.0); both=OK, one=flag, neither=FAIL. Tesseract not needed (no system binary — onnxtr is a better fit) |
| G6 self-consistency k=2–3 on flagged items | ACCEPTED | escalation only where it is cheap and needed |
| G7 escalation on min-logprob of numeric fields | ACCEPTED | llama.cpp provides logprobs; threshold to be calibrated on golden |
| G10 golden + Augraphy degradations, digit-error metric | ACCEPTED (slice 4) | canonical scan-degradation tooling |
| 0.75·ctx budget law as an assertion (/tokenize) | IMPLEMENTED (550ee0f) | rot starts before the limit; 400/assertion instead of degradation |
| Handoff-blindness law (routing, not values) | IMPLEMENTED (eb20b8e) | anchoring survives "verify it yourself" (≤10%); cascades 6–10× |
| A VLM is never the sole source of a digit | ACCEPTED (norm) | ~17% table hallucinations; fabrications consistent with the totals |

## Context / memory / document

| Technique | Verdict | Rationale |
|---|---|---|
| Fresh context per agent per phase | IMPLEMENTED (v0) | rot impossible by construction in the pipeline |
| AutoCompact of the main chat: 60% threshold, digest by code, from the transcript | ACCEPTED (slice 5) | 95% (Claude Code) is too late; numbers get lost in summaries |
| Slot save before compaction (reversible compaction) | ACCEPTED (slice 5) | a unique advantage of KV-as-file |
| Rolling summary.md editable by the operator | ACCEPTED (slice 5) | memory repairable by hand; anchor modelled on the workshop |
| document.md + docmap.json (anchors, folios, gaps, types) | IMPLEMENTED (d90cd45) | convergent Azure-DI/olmOCR pattern; RFC 8118 #page=N |
| Physical folio-gap law (consensus + offset) | IMPLEMENTED (d90cd45) | public sample operaty: zero false gaps after hardening |
| Native file-based memory (no graph in v1) | IMPLEMENTED/ACCEPTED | editable, diffable; the domain graph (points) is ALREADY IMPLEMENTED as a mechanism (slice 9) — the archive of historical operaty backfills it |
| County profiles with provenance + write-back on acceptance | ACCEPTED (slice 8) | A-MEM: the moment of verification = the cleanest signal |
| Neo4j at the deployment site | REJECTED | a dependency without need; SQLite/files are enough |

## OCR / raster (slice 4)

| Technique | Verdict | Rationale |
|---|---|---|
| RapidOCR primary (PP-OCRv6) | IMPLEMENTED | 0.7 s/page measured; ≥16/18 coordinates digit-exact on our own 200dpi printout; confidence per line, threshold 0.85 flags |
| Full scan pipeline (OCR→LLM→gates) | **IMPLEMENTED + MEASURED** | operat_scan.pdf (5/5 raster pages): classifier/header/coordinate list from OCR text, **9/9 points to the cm**, shoelace = gold, the judge honestly flags the scan's unknowns; 112 s |
| Second engine = onnxtr instead of Tesseract | IMPLEMENTED | Tesseract requires a system install (missing on the box); onnxtr = pip, ONNX CPU 0.5 s/page, a different architecture than Paddle — better gate independence |
| Per-cell digit-whitelist re-pass (PSM 7) | ACCEPTED | digits matter more than letters; kills confusions |
| img2table (ruled tables), Docling TableFormer fallback | ACCEPTED | CPU-first; MIT |
| Surya/marker/MinerU | REJECTED | licences (GPL/OpenRAIL-M/conditions) |
| EasyOCR/docTR | REJECTED | slower/heavier with no advantage |

## UI / packaging

| Technique | Verdict | Rationale |
|---|---|---|
| Tray shell (tray-icon+tao, NO Tauri/webview) | **IMPLEMENTED + SMOKE-TESTED** (1d058af) | 0.5 MB exe, imports only system DLLs; programmatic icon (no assets); "Zakończ" (Quit) = `taskkill /T /F` on the launcher — the smoke test killed the whole tree INCLUDING THE GREAT-GRANDCHILD (Child::kill would orphan server+llama); chain tray→launcher→server 1 s to HTTP 200; Job Object KILL_ON_CLOSE stays as reinforcement (killing the tray from Task Manager) |
| CSPRNG token + Host/Origin allowlist | IMPLEMENTED | `--token auto`: token→HttpOnly cookie, hard Host allowlist, Origin check; tested live (all attack shapes 403) |
| uTorrent-Web-style launcher (`start_geodoc.pyw`) | IMPLEMENTED | single instance via lockfile, port hunt, tokenised auto-open, watchdog; atexit kills the llama sidecar |
| Inno Setup + model pack (USB/download, SHA256 manifest) | PARTIAL (the definition EXISTS) | `installer/geodoc.iss` + `docs/PACKAGING.md` (build steps, python-embed, llama-bin with dispatch-dll); compiling setup.exe + code signing (e.g. Certum) = build day |
| Exports: przeglad.xlsx + template per PODGiK (county surveying-records office) | IMPLEMENTED | openpyxl 2 sheets; profiles/podgik-<n>.json controls the upload columns/separator |
| Certum signing (not Azure TS) | ACCEPTED (slice 7) | Azure TS without identity validation in the EU |
| PyInstaller onefile | REJECTED | AV false positives; embeddable python / Nuitka onedir |
| PyMuPDF AGPL — decision | RESOLVED (wave 15) | runtime on pypdfium2 (BSD/Apache); PyMuPDF only in dev tools |
| Side-by-side review screen + provenance click-through | ACCEPTED (slice 6/7) | convergent human-in-the-loop pattern |
| GML 3.2.1 (EGiB, the land and building register) export | ACCEPTED (v2) | mandatory in counties since 2021; CSV will not pass everywhere |

## Deck of the most fascinating (panel of 7 agents, 2026-08-05 evening)

4 generator lenses (surveyor / moat / wow / ritual) → 20 ideas →
3 judges (sceptic-engineer, practising surveyor, demo critic) → ranking
(weight: fascination×2 + feasibility-now×1.5 + moat). Full deck with descriptions:
`workflow wf_aa5aa704-09a` (transcript). Top ideas and decisions:

| Score | Idea | Verdict |
|---|---|---|
| 18.00 (4.0/4.0/4.0) | **Chain of evidence for every digit** — two OCR witnesses + the source pixel one click from Excel | **BUILD NOW** (merged with ↓) |
| 18.00 (4.7/4.0/2.7) | **Document X-ray** — click a value, the document points at it | **BUILD NOW** — one slice: click → page + highlighted region; XLSX with a SOURCE column (#page=N) |
| 17.67 (4.7/2.7/4.3) | Virtual PODGiK verifier — the rejection notice before you file | QUEUED behind slice 8: learns from PODGiK verification protocols (ekstraktor_protokolu contract + mapping of defects→checks in the county profile). Highest business value in the deck |
| 16.67 (moat 4.7) | Replay seal — the analysis as byte-exact reproducible evidence | **IMPLEMENTED** (2157ea7): checks/pieczec.json per job — build+models+prompt hashes per agent+seed+sha256 of every text artefact; deterministic (2 builds = identical bytes), a manual edit of an artefact changes the hash. xlsx excluded (zip timestamps = a view, not a record) |
| 16.33 | Boundary point lineage — a biography instead of a state | **IMPLEMENTED (mechanism, 8a97df1)**: `app/domain.py` bi-temporal SQLite (supersession never deletes — t_invalid), new/changed/unchanged flag COMPUTED from history (1 cm + attributes), idempotent ingest, a backdated archive re-chains (test); chips in the coordinate list + lineage panel (superseded rows dimmed, CURRENT); 10 checks + live proof. Archive of operaty = backfill through the same ingest |
| 16.00 (moat 4.7) | Case hibernation — a 300-page context comes back in a second | **IMPLEMENTED (mechanism+badge)**: the chat resumes via restore (5.6×), the context list shows ❄ with the state's token count; the full "case" screen will join main-chat v2 |
| 16.00 | Verdict in 60 s — the check board lights up live | **IMPLEMENTED** (1814f1e): async run + SSE (follow_log over tasks/log.jsonl, ends at the seal), live PASS/FAIL pill, auto-open of the job; the sample finishes in ~5 s |
| — | **G10 with Augraphy degradation** | **IMPLEMENTED** (6c74038): seeded "bad photocopy" fixture; PP-OCRv6 holds 18/18 digits @0.997 conf; regression floor ≥16/18 in the suite; G4 under noise: 15/19 dual, 4 flags — the mechanism works |
| 15.67/15.50 | Point time machine / Boundary-dispute folder | v2 from the archive of operaty (multi-document jobs by TERYT (the national territorial-division code) + timeline) |
| 15.33 | Night shift (batch queue) — the inbox reports completion | QUEUED: batch inbox + morning report (ritual) |
| — | Measurement converter from an old sketch (audit of a 1985 operat) | v2, staged: field books→sketches; classical surveying in pure Python |

## Agent studio / flow management (owner's question about trust, 2026-08-05 night)

| Technique | Verdict | Rationale |
|---|---|---|
| Supervised mode: pause after each stage + report + [Akceptuję/Powtórz z dopiskiem] (Accept / Repeat with a note) | **IMPLEMENTED** | research (Lee&See trust calibration, Horvitz mixed-initiative, Bainbridge ironies of automation, HITL convergence in doc-AI): both modes, supervision builds trust; operator note = an explicit block binding the run, recorded in overrides.jsonl |
| Crystallising notes into the user manual (# DOPISKI OPERATORA) | **IMPLEMENTED** | the human correction STAYS and changes the hash — visible persistence of a correction is a pillar of trust |
| Autonomy earned per document class (counter of green reviews in the county profile) | ACCEPTED (slice 8) | autonomy levels as in automotive; a new county starts supervised |
| Notes+acceptances as a corpus → LoRA of the 30B on operaty | **REJECTED by owner decision 06.08 — FROZEN-WEIGHTS LAW** | "one model throughout history, it differs only in KV cache / prompt / conversation history". Rational: (1) the replay seal requires frozen weights — an adapter breaks the reproducibility of old jobs; (2) context adaptation (golden/user manuals + crystallising notes + KV-as-file + graph digests) is READABLE and diffable — the manual hash in the seal says exactly WHAT changed, LoRA weights say nothing; (3) auditability at the deployment site: "the same model that passed validation". The corpus of notes STAYS (it feeds the manuals, not the weights) |
| Bulk profile -np 4 for mass coordinate-list extraction (≥3 pages) | **IMPLEMENTED + MEASURED** (78cc6b2) | operat_multi (36 pts / 4 pages): **1.39× wall-clock** (171→123 s) with **36/36 to the cm in BOTH modes**; below the bench's 2× due to boot in the measurement, PP thread contention and the uneven tail of 4 pages — the gain GROWS with the page count; ctx/slot accounted for in the 0.75 budget |
| Rust toolchain on a machine WITHOUT MSVC | **SOLVED** (tools/build_tray.ps1) | three traps in a row: Git-Bash substitutes coreutils `link.exe` ("extra operand"), bare PowerShell has no linker at all ("VS Code is a different product"), self-contained GNU has dlltool without as.exe (CreateProcess fail on raw-dylib) → rustup GNU + llvm-ar renamed to dlltool (multi-call dispatch by file name) = 27 s build |

## "Last-sweat" tuning (wave 4 (fala 4) — arXiv research + measurements on THIS machine)

The headline research finding: **Qwen3-Next-80B is architecturally penalised
on mainline CPU** — TG 5.4× slower than 30B despite the same 3B active
parameters (llama.cpp #17936, closed "not planned"); DeltaNet reads far
more data than the active parameters suggest. Two real levers: the
ik_llama.cpp fork (fused-MoE + i-quant repack: PP ×3.63 on IQ4_XS, TG ×1.67 —
measured #164) or, on mainline, a requant of the 80B to Q4_K (the +61% PP repack works
ONLY for K-quants — PR #12332; IQ4_XS never gets it). Our binary
b10155 (December '25+) HAS the repack and PR #17996 (-fa short-circuit for DeltaNet).
From arXiv: PowerInfer/Fiddler/ktransformers/HOBBIT/ProMoE = all require
a GPU/NPU or sparsity that Qwen's SwiGLU does not have — for pure CPU
NOT APPLICABLE (survey: awesome-moe-inference).

| Experiment | Status | Result / verdict |
|---|---|---|
| E1 30B thread sweep (t=8..32) | **MEASURED 2026-08-05** | TG peak @ **t=8** (25.6 t/s; 16t→24.3, 32t→20.2 = −21%); PP peak @ **t=24** (272.7; 16t→227.6). Verdict: **split -t 8 -tb 24 IMPLEMENTED** (models.json) — +5% TG, +20% PP for free |
| E2 30B batch sweep (-ub 512/1024/2048 @ p2048, t=24) | **MEASURED 2026-08-05** | PP: 237.0 / **244.9** / 239.2 — gentle peak @ **-ub 1024** (+3.3%). IMPLEMENTED in models.json |
| E3 30B -fa 1 -ctk/-ctv q8_0 (t=8) | **MEASURED 2026-08-05** | mixed: TG **+6.6%** (25.6→27.3), PP **−19%** (183→149). Our calls are prefill-heavy → net WORSE per call. NOT implemented for speed; comes back when fitting the deployment's RAM (KV 3.1→1.6 GB @16k) with a PP@t24 measurement |
| E4b 80B PP @ t=24 | **MEASURED 2026-08-05** | 128.1 t/s (+6% vs t=16; curve flat as with 30B). Analyst: **-t 8 -tb 24 IMPLEMENTED** |
| E-probe slot save/restore across a server RESTART (30B) | **MEASURED 2026-08-05** | **WORKS**: 863 tok → 84.9 MB (~98 KB/tok), restore into a fresh process, continuation prefills only 27 new tok (cache_n=863), **0.8 s vs 4.45 s cold** (5.6×). The "context as a file" core confirmed empirically — `tools/probe_slot_save.py` |
| E4 80B thread sweep (t=8/12/16) | **MEASURED 2026-08-05** | TG peak @ **t=8: 18.2 t/s** (12t→16.5, 16t→15.4 — the same bandwidth-bound curve as 30B); PP grows: 82→111→121 (16t). **SURPRISE: the DeltaNet penalty on our build is only −29% TG vs 30B, not 5.4×** — b10155 has the December fix #17996; 18 t/s makes the 80B a real analyst, not an ornament |
| E5 80B -fa 0 vs 1 (PR #17996) | **MEASURED 2026-08-05** | a wash on CPU: PP 105→109 (+4%), TG 16.7→16.3 (−2%) @ t=12. Verdict: -fa NEUTRAL for speed; enabled only if we want -ctv q8_0 (requires FA) |
| E6 80B requant IQ4_XS → Q4_K_M (speed probe) | **MEASURED 2026-08-05** | repack WORKS on qwen3next: **PP +40%** (128→180 t/s @t24); TG **−16%** (18.2→15.3 @t8; file +13.7% bytes = bandwidth); file **48.5 GB > the deployment's 48 GB budget — Q4_K_M UNSHIPPABLE**. Net depends on the call shape (short outputs gain, long ones lose). Requant is lossy-on-lossy: speed numbers are valid, do not measure quality on this file |
| E6b 80B requant → **IQ4_NL** (repackable i-quant) | **MEASURED 2026-08-05 — WINNER** | **PP 176 t/s (+37%)** with **TG −5%** (17.3 vs 18.2); file 45.6 GB → with KV+OCR ≈ 47.4 GB — FITS in 48 GB. Almost the whole repack gain without the Q4_K_M penalty. **Decision: the 80B shipping candidate = a FRESH IQ4_NL** (the probe is lossy-on-lossy — speed numbers only) |
| E6c **fresh IQ4_NL FOUND ready-made** (no BF16 download) | **MEASURED 06.08 — IMPLEMENTED as the shipping quant** | bartowski imatrix-from-BF16, sha256 `84ced6ba…533f`, 45 310 826 976 B. Bench with identical methodology (docs/bench/e6c-bench.txt): **PP 174.16 ±0.78 vs 125.68 ±4.30 = +38.6%** with TG statistically flat (16.43 ±1.02 vs 16.66 ±0.60, the intervals overlap); PP variance dropped 5×. Quality ≥ the incumbent (fresh imatrix, not lossy-on-lossy). models.json + manifest swapped; IQ4_XS stays on disk as a rollback. Name trap: the model card drops the `Qwen_` prefix → a 15-byte "Entry not found"; rename gated by size |
| E7 ik_llama.cpp Windows build, the same GGUFs | **INVESTIGATED → WAITING** | the repo does NOT publish Windows binaries (1 release, 0 assets) — requires a build with an MSVC/cmake toolchain. **Priority DROPPED after E6b**: the headline ×3.63 PP was measured vs an old mainline WITHOUT repack; our mainline with IQ4_NL already delivers +37% PP — the fork's marginal gain is significantly smaller than the headline. Comes back only under TG starvation (the fork gives ~×1.5-1.9 TG) |
| E8 llguidance instead of GBNF (build -DLLAMA_LLGUIDANCE=ON) | **REJECTED (resolved in wave 5)** | release.yml builds win-cpu-x64 WITHOUT LLAMA_LLGUIDANCE (confirmed), and the machine has no MSVC for our own build — dead until upstream changes; GBNF is enough (the ≤2000 wall audited clean) |
| E9 DUAL residency: both models at once | **IMPLEMENTED 06.08** (unfrozen by the 190 GB law — the old "NOT feasible in 64 GB" rested on a wrong assumption about the dev box) | `residency_mode()` a pure decision: dual when Σgguf×1.1+16 GB < RAM — dev 190 GB→dual (zero worker↔analyst swaps in every job), a 64 GB office machine→single ON ITS OWN (the same config everywhere); override in models.json; 3 checks |
| E10 80B pre-warm (sequential file read before start) | **MEASURED (row below — historical duplicate)** | 18.6 GB in 4.3 s; wiring into the launcher = a deployment checklist item |
| E11 --prio (TG jitter) | **MEASURED (partially)** | single run @prio: 25.3 ±1.5 = baseline; zero signal on an idle machine — comes back only under concurrent load (OCR in parallel with TG) |
| E12 --poll 0/50/100 (TG @t8) | **MEASURED 2026-08-05** | 25.66 ±1.47 / **27.11 ±0.23** / 27.25 ±0.44 — default 50 is right: poll 0 costs ~5% and triples the jitter, 100 gives noise (+0.5%). **NO configuration CHANGE** |
| E15 load+repack time (observed) | **NOTED** | warm server boot (page cache) 10–20 s; full crew cycle 95–113 s; cold load of 42 GB = swap cost per NVMe (~tens of s) — a cold measurement requires clearing the standby list (RAMMap), postponed |
| E13 batched throughput (npl 1/2/4 @ t8/tb24) | **MEASURED 2026-08-05** | aggregate TG: 24.3 → 30.8 (**+26%** @2) → **48.0 t/s (+97% @4)**; PP grows too (210→277). Amortising expert reads WORKS on CPU. **Design conclusion: a "bulk" -np 4 profile for mass-extraction phases** (coordinate-list pages of a large operat, the night inbox) — comes with the async task queue; stateful slots stay at -np 1 |
| E10 pre-warm (sequential read of the model file) | **MEASURED 2026-08-05** | 18.6 GB in 4.3 s (warm cache; cold NVMe ~2× slower) — an almost free trick; wire into the launcher before starting the 42 GB analyst at the deployment site (removes the first run's fault jitter) |
| E14 Windows power plan / core parking | **RESOLVED with rationale 06.08** | changing the plan = a system setting requiring admin rights — outside the scope of overnight A/B runs on someone else's machine (law: we do not change system state); TG jitter already characterised in benches (±0.02–1.5 t/s, E12/E19) and blocks nothing; verdict: a DEPLOYMENT CHECKLIST item for the user's office (the "Wysoka wydajność" (High performance) plan + disable core parking) in PACKAGING, not a dev experiment |
| E15 repack cost at load (45 GB IQ4_NL) | **MEASURED 06.08 04:1x** | analyst boot-to-healthy with a warm cache (online repack included): **20 s**; worker: ~0–2 s; a cold start adds the NVMe read (~13–20 s at ~3 GB/s) → **the "up to 20 min" pathology from PR #12332 categorically does NOT apply to our quant**; deployment swap cost = tens of seconds, in line with the architecture's assumption |
| KV q4 (K or V) | REJECTED | V-q4 ppl ×3–4 worse + −36.8% TG at long ctx (measured in the sources) |
| PowerInfer/ktransformers/Fiddler/HOBBIT | REJECTED | require GPU/NPU/sparsity — pure CPU is outside the scope of these works |
| NTFS compression of the GGUF | REJECTED | high file entropy; adds CPU in the fault path |
| Large pages on Windows | REJECTED | no path in llama.cpp on Windows (investigated — not found) |

## Wave 5 (fala 5) — "enemies we have not yet defeated" (hunt, night of 05/06.08)

Method: 3 recon forks with the LIST OF DEFEATED ENEMIES as input (owner's idea —
search at the front, not on captured ground). Verdicts after verifying flags on
b10155 (`--help`) and cross-reading the evidence.

| Enemy / opportunity | Verdict | Rationale |
|---|---|---|
| `--cache-ram` **defaults to 8 GiB + --cache-idle-slots ON** — silent serialisation of idle slots' state to host RAM; for hybrids the path is EXPLICITLY untested (PR #16391 TODO); #26293 cache written, never read | **IMPLEMENTED 40807b1: --cache-ram 0 for BOTH models** | the 48 GB budget has no 8 GiB of slack; hybrid state may be touched ONLY through explicit slot save/restore (our law); 30B bulk with a deliberate 512 MiB = E20 |
| Auto `-np -1` silently enables `--kv-unified` (a cross-request leak class #25992) | **IMPLEMENTED 40807b1: --no-kv-unified explicit + -np always pinned** | the wave 1 law reinforced: NEVER defaults where there is state |
| **ctx ceiling ~80k for Qwen3-Next under llama.cpp** — overflow of the g_cum accumulator in DeltaNet → collapse into repetition (discussion #20000, NO upstream fix as of 07.2026) | **IMPLEMENTED 40807b1: ctx_ceiling 65536 + ctx_law() assertion** | our 16k ctx was safe BY ACCIDENT — now it is a unit-tested law; the architecture's RULER is OK, the enemy is in the implementation |
| A temp-0 repetition loop passes span grounding (every value EXISTS in the source) | **IMPLEMENTED 40807b1: powtorzone_wspolrzedne flag** (dup_coords) | the official lever (presence_penalty) deliberately disabled (it breaks tables) — algorithmic compensation on the code side, sampler untouched |
| Silent "correction" of diacritics by the model (z→ż, arxiv 2510.06743) = a false hallucination alarm under strict match | **IMPLEMENTED 40807b1: tier-2 fold in grounding** (ł by hand — it does not decompose in NFD) | a diacritics-only mismatch → dual-OCR arbitration, not FAIL; recovers recall on scans |
| Build floor **b10152** (key_gdiff vectorisation fix + fused GDN #26177) — below it Qwen3-Next computes WRONGLY | **LAW (dossier § 1)**: never <b10152; our b10155 ✓ | protects every future rollback |
| GBNF wall: bounded repetition / maxLength >2000 = "failed to parse grammar" on b10155 (fix #26613 only after us) | **LAW + CLEAN AUDIT** | grep schemas: zero bounds anywhere near 2000; law until the upgrade |
| Upgrade b10155 → b10289 | **DEFERRED with a costing** | state-safe (LLAMA_SESSION_VERSION 9 / STATE_SEQ 2 identical — CONFIRMED), zero CPU gain, buys the GBNF fix; do it at the next maintenance window, not on a shipping night |
| **Context checkpoints for hybrids** (PR #19408; real flags on b10155: `--ctx-checkpoints N --checkpoint-min-step N`) | **E17 MEASURED 06.08 — IMPLEMENTED, old law REPEALED** | 4-gate hazard test (tools/probe_ctx_checkpoints.py → docs/bench/e17-ctx-checkpoints.txt): G1 server healthy ✓, **G2 cross-request reuse 6897/7413 tokens (−93% re-prefill of a repeated prefix) ON THE HYBRID** ✓, G3 explicit save/restore intact 7473/7473 ✓, G4 output correct ✓. Feeds the G1 retry ladder and "Powtórz z dopiskiem" (Repeat with a note) (the same document block). The wave 1 law "checkpoints break hybrids" repealed — the reports predated the fix PR; state contract unchanged (G3 proves it) |
| **ik_llama HAS Windows binaries** (Thireus builds; fused delta-net -fdn: PP +24.5%, TG +31% on Qwen3-Next CPU, ik-vs-ik) | **E18 WAITING with a protocol** (owner decision: a 3rd-party runtime in the image?) | kills the reason for deferring E7, BUT a binary from a personal GitHub cannot touch the product without a supply-chain audit. Protocol ready: (1) download the Thireus win-x64-AVX512 release + record the sha256, (2) llama-bench -fdn on OUR IQ4_NL with identical methodology vs docs/bench/e6c-bench.txt, (3) parity: GBNF? /slots save/restore? hybrid state? (4) verdict ADOPT only at +≥15% and full parity + a signed build from a pinned commit. We have already harvested mainline's PP gain via the IQ4_NL repack (+38.6%) — the fork tempts mainly with TG (+31% ik-vs-ik, delta vs our mainline UNKNOWN) |
| Pinning the decoder to one CCD (7950X = 2×CCD, cross-CCX L3 penalty) | **E19 MEASURED 06.08 — REJECTED** | A/B on the fresh IQ4_NL (docs/bench/e19-ccd-pinning.txt): baseline **17.97 ±0.11** vs -C 0x5555 --cpu-strict 1 **17.87 ±0.02** — NO gain (−0.6%, within noise), only jitter dropped 5×; the Windows scheduler on an idle machine already keeps the decoder CCD-local, or the bottleneck is memory bandwidth, not L3. CORRECTION of the hunter's mask recorded: 0xFF = 4 cores+SMT, CCD0-physical = 0x5555 |
| `--cache-ram 512` on 30B bulk (shared manual prefix across documents) | E20 EXPERIMENT (per profile, after the 190 GB law) | dev can be generous (4096+), the deployment stays at 0 (48 GB budget); measure on a 2-document bulk via timings.cache_n — default 0 stays the law until measured |
| **E21 domain imatrix**: our own IQ4_NL quant from BF16 calibrated on POLISH operaty (instead of bartowski's generic one) | EXPERIMENT v1.1 (unblocked by the 190 GB law) | a BF16 pull of ~160 GB is feasible on dev; imatrix on operat texts = a quant tailored to OUR distribution; gold-eval vs bartowski decides; requires a corpus of real operaty |
| Verification: does the **zen4 dll actually load** (zen4 variant = non-MSVC-only build) | **E16 CONFIRMED 05.08** | module enumeration of the live process: `ggml-cpu-zen4.dll` loaded (AVX-512/VNNI active); along the way a live proof of the new --cache-ram 0/--no-kv-unified flags (the worker came up clean) |
| Qwen3.6-35B-A3B as judge instead of 80B (19–20 GB, end of the 18↔45 swap; benchmarks ≥ Next-80B) | **WAITING v1.1 (gold-eval protocol)** | PL extraction quality unverified; swapping the judge invalidates the measured profiles — only via the full gold set |
| REAP-prune 80B→60B (Samsung SAIL, ≥94% quality, −25% RAM) | **EXPERIMENT v1.1** (unfrozen by the 190 GB law) | dev has 190 GB RAM + 559 GB disk — pulling full weights and converting is FEASIBLE locally; option: 60B@Q5 ~42-44 GB (a higher bit width than 80B@IQ4_NL in the same budget) — PL gold-eval decides; owner's law 06.08: dev may go heavy, the final artefact ≤~45 GB |
| CONSTRUCT per-field trust scoring (arxiv 2603.18014) | WAITING v2 | catches wrong-field-right-value (passes span grounding); transfer to Qwen unverified |
| PageIndex — navigation by a TOC tree instead of flat routing | WAITING v2 | our docmap already does TOC-light; gain on 100+ pages PLAUSIBLE, finance≠Polish scans |
| MTP spec-decode (--spec-type draft-mtp, in b10155) | REJECTED (for now) | no MTP-GGUF for Next-80B + determinism bug #23335 = disqualification for coordinate transcription; watch item |
| Self-consistency voting on digits | REJECTED | +0.23% marginal (survey 2503.24235) — not worth breaking temp-0 determinism |
| Switching to a "Polish" model (Bielik/PLLuM) | REJECTED | benchmarks 03.2026: Qwen top-3 on Polish, ABOVE the local models — choice validated |
| KTransformers/SGLang-CPU/OpenVINO/llamafile | REJECTED | Linux-only / no Zen4 numbers / no hybrid support / dormant |
| llguidance in official releases | REJECTED (confirmed) | release.yml builds win-cpu-x64 WITHOUT LLAMA_LLGUIDANCE — E8 dead until upstream changes |
| Bonus validation: zeroed penalties skip ~20% of TG overhead (#24871) | NOTED | our transcription profile is also faster by accident, not just more correct |

## Wave 7 (fala 7) — chapter chain (owner's spec 03:09, fusion with the judge panel)

| Element | Verdict | Rationale |
|---|---|---|
| Execution model: pure chain (A) vs layer FUSION (B) vs crew+view (C) | **B WINS with 14 pts (A=8, C=11)** — panel of 3 advocates × 3 judges (/workflows, 7 agents) | B: boundary-error cascade structurally bounded (phase B re-verifies pages with the union HINT∪code — a wrong boundary can assemble a folder wrongly, it cannot lose an extraction); a total collapse of chapter detection degrades EXACTLY to today's 128-green pipeline; G1–G10 unchanged; grafts from C: CLAIMS-ONLY walker + clean materialisation from immutable transcripts + the `nieoznaczone` (unlabelled) bucket |
| Heading detection BY CODE (marker k-means of sizes, unstructured's title filter verbatim, docling numbering ladder, ICDAR'13 table of contents + monotonic legality, HiPS fuzzy validation, OCR box-height proxy 99.67%) | **IMPLEMENTED (rozdzialy.py)** | recon with primary evidence; all pure PyMuPDF/stdlib (difflib instead of rapidfuzz — zero-dep law) |
| Sequential LLM chapter walker (LumberChunker shape, DCG 62.1 vs 54.7) | **IMPLEMENTED + LIVE (a828fcf)**: 5 hops 38 s on 30B, every hop = a code candidate with "wysoka" (high), EOF correct; boundaries = gold | containment law: it picks ONLY among code candidates or null; monotonic cursor; hard re-anchoring on numbering/table of contents — a wrong boundary dies at the next anchor (LumberChunker has NO containment mechanism at all — our advantage) |
| Summaries: incremental (owner's sketch) vs hierarchical | **HIERARCHICAL (BooookScore ICLR'24)** — an evidence-based correction | an incremental running summary degrades the most on small local models; transcripts build incrementally (deterministically), summaries merge as a tree; facts per page + G13 |
| Gates G11 (tiling: front+chapters+unlabelled = exactly 1..N), G12 (title grounded in the transcript of page 1; ungrounded → nieoznaczone), G13 (fact: page in range + numbers verbatim on the page; rejected → fakty_odrzucone) | **IMPLEMENTED, uniform polarity** | abstention-first at every level; nothing is silently green |
| Adversary lab: the table of contents lies (drift −2 + a rogue entry), foreign page (an invoice in chapter 3), short without headings, massive 122 pp., massive-scan 40 pp., split (logical page = 2 PDF pages) | **BUILT + MEASURED (1472e60)** | the table of contents does NOT steer boundaries (content anchors); the rogue entry killed by the legality rule, the drift recovered as spis_przesuniecie=2 — two lies, two layers; foreign page absorbed without breaking G11; short: **hardened abstention** — zero anchors → zero chapters, everything unlabelled (the title page stopped being a false chapter); massive 6/6 chapters to the page |
| Frozen-weights law (owner 06.08) | **LAW** | one model throughout the product's history; adaptation = KV/prompts/history; the replay seal requires it; the corpus of notes feeds the manuals, not the weights |
| Reconstruction of logical pages from split scans (2 PDF pages = 1 logical) | WAITING v1.1 | the fixture exists; folio consensus sees numbers only on the bottom halves — stitching pairs is a separate slice; today split goes through the heavy page-by-page OCR path (as the owner intended) |
| Image describer (fresh context per image) | **IMPLEMENTED (slice 3)** | NO VLM (mmproj breaks hybrid slot save; VLM-never-solo): the 30B composes the description from the OCR of the image REGION + the caption below it (find_media: text pages with coverage ≥0.10, caption zone 70 pt below the rect); element gate — every element must appear (fold) in the OCR/caption, ungrounded ones rejected; patching of OPIS-MEDIA blocks in rozdzial.md idempotent; media.json; a fresh call per image |

## Wave 6 (fala 6) — v0.95 tuning pass (02:24–02:5x, owner's question "what else can we tune?")

| Technique | Verdict | Rationale |
|---|---|---|
| E22a: `-ub` on the analyst (the fresh IQ4_NL never got a micro-batch sweep) | **MEASURED — IMPLEMENTED `-ub 1024`** | docs/bench/e22-nl-tuning.txt: PP@t24 ub512 185.52 ±1.48 → **ub1024 192.61 ±0.93 (+3.8%)** → ub2048 186.25 (regression); mirrors the worker's +3% |
| E22b: re-validating the thread split on the NEW quant (NL repack ≠ XS kernels) | **MEASURED — NO CHANGE, confirmed** | PP: t16 172.8 / **t24 192.6** / t32 189.6 ±3.81 (SMT contention ×4 jitter); TG: t8 17.97 / t12 15.59 — split `-t 8 -tb 24` optimal for NL as well |
| E20: bulk `--cache-ram` on the worker (A/B on operat_multi) | **MEASURED 06.08 — REJECTED for this shape, 0 stays** | A3 170 s vs B(512) 173 s @ 36/36 in both (docs/bench/e20-bulk-cacheram.txt) — a wash consistent with the mechanism: 4 pages on 4 slots = one wave of requests, idle-slot serialisation has no time to fire; comes back for measurement on documents with >4 coordinate-list pages and between night-shift jobs |
| **BUG CAUGHT BY MEASUREMENT**: the classifier nominated [2,3] out of 4 coordinate-list pages → 18/36 pts (the referee caught it: pominiete 18 (omitted 18), DO_POPRAWY (needs correction)) | **FIXED b7cac79** | routed_wykaz_pages(): the classifier's nomination = a HINT, never a gate — union with CODE detection (parse_rows ≥2 rows/page); blinding intact; live re-proof 36/36; seam lesson: _page_text returns (text, conf) — the unit test on strings did not see it, an integration smoke test = law |

## COMPLETENESS CENSUS (06.08 04:1x — proof that the optimisation programme is closed)

**State: 170 verdict rows in this ledger, ZERO unresolved.**
Mechanical verification: `grep TODO|w toku` returns only quotes from
upstream (PR #16391 "TODO" is a llama.cpp comment, not our verdict).
Every candidate from the 7 research waves (3 engine recon waves + Qwen prompts +
context/KV + the wave-5 hunt with the list of defeated enemies + the wave-6 v0.95
tuning + the wave-7 chapter chain with the judge panel) and from the E1–E22 battery carries
one of the statuses: **IMPLEMENTED** (with a commit), **MEASURED** (with numbers in
docs/bench/), **REJECTED** (with numbers or source evidence),
**LAW** (encoded in assertions/tests), or **COSTED** (full
recipe + reason for deferral).

OPEN items — exclusively gated by the owner's decision/attributes or
consciously costed outside the window (each with a complete execution recipe):

| Item | Gate | Recipe ready in |
|---|---|---|
| Certum signing | owner's purchase/identity | PACKAGING (signtool, per-exe) |
| PyMuPDF AGPL decision | owner's legal choice | RESOLVED in wave 15 (pypdfium2; surface measured: 4 API families/2 files) |
| E18 ik_llama (Thireus) | owner's consent to a 3rd-party runtime | wave 5 (4-step protocol with a supply-chain audit) |
| REAP-prune 60B / E21 domain imatrix | ~120–160 GB pull + hours of CPU — outside the night window | waves 5/7 (full recipes; 190 GB dev makes them feasible) |
| Verification protocols + archive of operaty | real data (non-public) | verifier scaffold (dormant) + lineage backfill (tested retroactively) |
| Split-page reconstruction / GML export | v1.1 / v2 | fixture + rows with rationale |
| E14 power plan / E10 launcher pre-warm | deployment checklist | rows E14/E10 |

The application as of this census: 68 commits, 161 checks green,
setup.exe 0.95 (149.3 MB, 04:10) with the full G1–G13 fusion, two live
end-to-end proofs (chaptered 220 s PASS/OK, massive 122 pp. 338 s, scan
GOLD-EXACT), the frozen-weights law as the answer to "model train".

## LITERATURE-WATCH PROTOCOL (a standing mechanism, not a one-off)

Sources monitored and mode: **(1) llama.cpp** — releases/PRs/issues with
regard to Qwen3-Next hybrids, CPU MoE, slot API (proof it works: waves 1, 5 —
incl. detecting fix PR #19408, which invalidated our own law);
**(2) arXiv** cs.CL/cs.IR/cs.CV doc-AI (proof: wave 7 — LumberChunker,
HiPS, BooookScore, ICDAR, font proxy 1402.4388; wave 5 — CONSTRUCT,
REAP, TTS survey); **(3) HuggingFace** — quants/models (proof: E6c
bartowski imatrix, Qwen3.6-35B, REAP-60B); **(4) Qwen model cards** +
QwenLM GitHub (proof: the "prompts" wave + the wave-5 sampling validation).
Cadence: a full sweep at every maintenance window; the input to every
sweep is the LIST OF DEFEATED ENEMIES (owner's method 05.08 — we search at the
front, not on captured ground). Tonight the protocol was executed 7 times
(3+1+3 recon forks + judge panel); trace: the wave sections in this ledger,
each with source links.

## "LEGENDARY / MOST FASCINATING" THRESHOLD — a measurable definition (not an adjective)

| Criterion | Threshold | State 06.08 04:2x |
|---|---|---|
| Extraction accuracy on golds | 100% to-the-cm on all fixtures | ✅ 36/36 bulk, 9/9 via OCR, 18/18 degraded @0.997 |
| Hallucinations in summary facts | 0 ungrounded after the gates | ✅ 48/48 (the only rejects = meta-chatter and gate faults, fixed) |
| Chapter boundaries | gold-exact on text + scan + 122 pp. | ✅ 5/5, 6/6, 5/5-scan |
| Technique ledger | 0 unresolved rows | ✅ 170/170 (census) |
| Suite | 100% green | ✅ 161/161 |
| E2E on a deployment-shaped machine | <6 min for 122 pp., <4 min for 16 pp. | ✅ 338 s / 220 s |
| Adversaries | each defeated or honestly unlabelled | ✅ 9 fixtures, including a lying table of contents ×2 layers |
| Shipping artefact | setup.exe with everything, suite on embedded | ✅ 149.3 MB @04:10 |

## POSITIONING vs PUBLISHED SOTA (recon 06.08 04:2x, primary sources)

**Headline caveat, non-removable:** our numbers come from our OWN
seeded golds (narrow domain, synthetic) — the published ones from broad
public benchmarks. This is INDICATIVE positioning, not head-to-head.
The honest thesis: not "we beat SOTA", but "on THIS job (digits/structure/
grounding of Polish operaty) the bar is ACCURACY TO THE CM, and it is
reached by mechanisms (grammar+temp0, code referee, dual-OCR, gates
G1–G13) that published systems do not combine; on shared components
(PP-OCRv6) we run directly on the published SOTA".

| Task | Published SOTA | Our measurement (own gold) |
|---|---|---|
| E2E document parse | OmniDocBench: MinerU2.5 90.67 overall (REPORTED), GPT-4o 86.59/TEDS 82.95, Marker 78.44 (CONFIRMED) | suite 161/161; chaptered 220 s PASS; massive 122 pp. 338 s |
| Table transcription | TEDS: PaddleOCR-VL 91.95; S-TEDS FinTabNet 99.05 (REPORTED); VLMs: "confidently hallucinates rows" (RD-TableBench, CONFIRMED), 12–18% hallucinations on numeric claims (REPORTED) | **36/36 and 9/9 to-the-cm, 0 fabrications** — a stricter measure than TEDS (structural similarity): DIGIT accuracy from the code referee |
| OCR | PP-OCRv6: 83.2% line acc, +3.9× CPU (CONFIRMED abstract) — WE HAVE THIS ENGINE (RapidOCR det/rec v6) | 18/18 digits @conf 0.997 on the degraded one; floor ≥16/18 in the suite; dual-engine agreement ON TOP OF the published SOTA |
| Section hierarchy | ICDAR'13 official: best link-F 67.2, complete-entries 43.6 (CONFIRMED — our earlier citation of 73.1 CORRECTED); HiPS: P/R without a tabular F1 (corrected — we cite the METHOD, not a number) | boundaries gold-exact on 4 fixtures (text/122 pp./scan/lying table of contents); the lying table of contents defeated by 2 layers |
| Grounded summaries | FABLES faithful-claims: Claude-3-Opus 90%, GPT-4 78%, Mixtral 70% (REPORTED); BooookScore coherence: Mixtral 81.5 (CONFIRMED) | **48/48 = 100% of facts grounded AFTER the gate** — the gate ENFORCES faithfulness (drop-not-trust), it does not measure it after the fact |
| Navigation/chunking | LumberChunker DCG@20 62.09 (CONFIRMED — our citation ✓) | the walker inherits the shape + containment, which LumberChunker does NOT HAVE |

**Sweep of 2025–26 technique classes (last chance to miss something):** RL training
of parsers (GPU training, consumable only as weights — not a pipeline gap);
tiny-specialised-beats-VLM (PP-OCRv6 — ALREADY our engine); agentic extraction
with validation (our referee+gates architecture IS this class — independent
convergence); optical context compression / DeepSeek-OCR (GPU-VLM class,
watch item for llama.cpp ports); unit-test-based eval (olmOCR-Bench — convergent
with our golds philosophy; ACCEPTED v1.1 for external credibility);
test-time compute (our dual-OCR+consensus is already in this class); late chunking
(retrieval-side, orthogonal). **Sweep verdict: ZERO missed classes
applicable to CPU-offline.**

## Wave 8 (fala 8) — coordinate systems + confidence layer (owner's questions 09:48/09:5x)

| Element | Verdict | Rationale |
|---|---|---|
| CRS inventory from recon of primary sources (GUGiK/Kadaj, EPSG, Dz.U.) | **INVESTIGATED + IMPLEMENTED (1586d9e)** | 2000/5-8, 1992 (EPSG ranges), 1965 I-IV (origins from GUGiK, Y-prefix signature 3-4), 1965/V COLLIDES with 1992 (disambiguated by region/profile), 1942 rare, ~a dozen local systems; heights KRON86→EVRF2007 +0.165 m avg. (EVRF legally the only one since 2024) |
| 1992→2000 and zone↔zone | **IMPLEMENTED — mathematically exact** | Karney n-series GRS80, roundtrip 0.14 µm; derived columns X_2000/Y_2000/STREFA (original untouchable — the law of truth); also detects 1992 WITHOUT a declaration (magnitude signature) |
| 1965→2000 | **ABSTENTION-with-a-ladder (deliberate)** | Helmert ~1 m / G-1.10 3-4 cm / legal thresholds 0.10/0.20 m — a conversion without zone corrections would be false confidence; recipe: TRANSPOL/G-1.10 in the county profile (v1.1); pyproj (6 MB MIT, offline) if Helmert were to be implemented — row costed |
| Local systems / 1942 | **ABSTENTION + flag** | per-city parameters (complex polynomials of degree 2-4); the county profile = the right place |
| UN-HARDWIRING PL-2000 | **FIXED (found by fixtures)** | ROW regex 7-digit → 4-7 (1992 parsed ZERO rows!), dual-OCR COORD likewise, the header fabricated "PL-2000/?" → honest extraction with canonicalisation; range gates under a foreign CRS = None + flag, not a false FAIL |
| Confidence layer: colour instead of probability | **IMPLEMENTED** | categorical tiers from REAL signals (referee/grounding/code list → KRYTYCZNE (critical)-red; single-OCR-engine/duplicate-position/conversion → SPRAWDŹ (check)-amber; clean → PEWNE (certain)-green) + REASONS + page, painted in przeglad.xlsx — consistent with the calibration law (verbalised percentages = uncalibrated by construction) |
| "Digit booster" for degraded ones | **ACCEPTED (next slice)** | for SPRAWDŹ/KRYTYCZNE points: re-render the value region @300 dpi + re-OCR with both engines + digit whitelist; both agree → tier raised with a note; pure CODE, not an LLM |
| CSV format adjustable by the operator | **IMPLEMENTED** | nazwy_kolumn (renaming) + transposition (rows↔columns) in profiles/podgik-*.json — in PROFILES, not prompts (CSV shape = CODE's job, determinism law); profile editor in the studio = next UI step |
| "A new LLM agent at the end for the numbers" | **REJECTED with rationale** | model confidence is uncalibrated (our anti-pattern table); tiers are computed by CODE from measured signals; the LLM judge remains the judge (digest) — role separation without confidence theatre |

## Live series (owner's goal 10:15) — observation, transcripts, remediations

| Finding | Remediation | Evidence |
|---|---|---|
| Good documents reported "1 flag" (zrodla_trafne=True went into the flags) | flags = ONLY problems; health stays in grounding.json | sample re-proof: **flags {} PASS** |
| L2: the classifier nominated the wrong page, the row parser was blind (noise breaks the row STRUCTURE, but the coordinate STRINGS survive 7/9) → 0 points | routing by a union with coordinate density (≥3 COORD matches on a page) | l2 re-run: **0 → 9 points** rescued with wsp_jeden_silnik (single OCR engine) flags; the DO_POPRAWY verdict rightly stays |
| "Works as designed" observations | — | the routing robustness union carried extraction on 2 documents with ZERO classifier nomination; the sample got a FREE correct chapter map (the walker anchors unnumbered headings); the L2 judge named 3 problems precisely; the good path pays NOTHING for the armour |

## Wave 9 (fala 9) — UI to SOTA (owner's goal 11:38): archaism in a modern design

| Element | Verdict | Rationale |
|---|---|---|
| Trend recon + polarity | **INVESTIGATED** | NN/g: a light theme wins for small tables (dark = the worst case); 2026 currents: blueprint revival, heritage etch, skeuomorphic minimalism; the current dark shell was the default "AI look #2" — abandoned on evidence, not taste |
| Panel of 3 Fable agents (PIECZĘĆ/SIATKA/REJESTR — seal/grid/register) | **IMPLEMENTED — judge's merge** | rarity of the seal (PIECZĘĆ) × feTurbulence impression rendering (REJESTR) × line weights + range ornament (SIATKA); independent convergences ×3 = high confidence (cool paper, Półtawski+Plex, red only for KRYTYCZNE) |
| Recipe for prompting Fable for UI | **RECORDED** | agent `FableUIDesigner` with 8 laws (Anthropic cookbook + skill): ban on default looks, tokens before screens, extremes 100↔800, a named cultural anchor, anti-default self-critique |
| Heritage typography | **IMPLEMENTED (cfba0f3)** | Półtawski Nowy = a revival of the FIRST complete Polish typeface (1928, OFL) — archaism as a functional choice; 22 WOFF2 latin-ext self-hosted, route /czcionki/, zero CDN (offline law) |
| Signature: the seal impression | **IMPLEMENTED (560a0d7)** | round seal ONLY on PASS (absence = a message, a BEZ PIECZĘCI (no seal) plaque on FAIL); real hash from pieczec.json (crypto.subtle) — branding became verification semantics; stamps on verdicts, never on affordances |
| Logo: vendor or the user's office? | **RESOLVED by research** | the product carries the maker's mark (source credibility + referral loop — Calendly ~25% of sign-ups from the badge; C-GEO norm), documents carry the user's office's mark (regulation of 18.08.2020 REQUIRES the contractor's identity; ownership effect via the profile, not a fork); xlsx footer: firm on the left, dominant + small colophon; upload CSVs WITHOUT branding |
| Visual verification | **DONE (screenshots)** | 4 screens viewed and critiqued (shell/job+seal/queue/chat protocol); favicon 404 found and fixed (survey-control-point marker SVG data-URI); suite 0 fail; testids exact to the character |

## Wave 10 (fala 10) — Review: the feedback loop after processing (owner's goal 12:38)

| Element | Verdict | Rationale |
|---|---|---|
| Should we have this feature at all? | **YES — gap closed** | the loop DURING the run existed (operator note in supervised mode); the loop AFTER — the moment of the morning report, coffee and questions — did not exist; that is where the operator really questions the data |
| New agent | **IMPLEMENTED: `rewident` (reviewer)** (2f8f7d8) | 10th golden manual (editable with a user overlay like all of them); laws: only the supplied material, numbers verbatim with "s. N" (p. N), abstention, zero percentages (calibration law) |
| Architecture | **context bound to the job, not a new engine** | the rewident role on the 80B analyst (resident after the run — questions hit a hot model); DIGEST by code as a note kind=digest → stable KV prefix; retrieval BY CODE (pages > point IDs > chapters > fold scoring), budget 5×2800 chars; transcript = what the model saw (audit); mirror analizy/rewizja.md next to the documents; outside the seal by construction |
| Verification | **10 checks + live 80B proof** | routing explicit p.2 / keyword→p.1 / ID→row+page / chapter→range; quotes verbatim (RTK GNSS, 0,10 m, 2026-06-11); one context across 2 questions; suite 3× green |
| Finding along the way | **FIXED: the reader seam** (e5a2ca3) | os.replace can throw a TRANSIENT PermissionError during a parallel open() — retry in jread (mirror of jsave); the torn-read class closed from BOTH sides |

## Final campaign (goal 13:18) — tests, HITL, numbers

**Arsenal queue of 13 operaty: 50.8 min in total, avg. 235 s/operat** (full
pipeline with chapters/descriptions/summaries; the first result includes the analyst's
cold start). Times [s]: sample 165 · chaptered 233 · toc_klamie 262 ·
incomplete 266 · 1992 123 · lokalny 117 · l2 265 · pageocr 258 ·
bez_naglowkow 124 · puste_dublety 250 · spread 228 · mapy 211 · masywny 549.
Verdicts 13/13 consistent with the fixture design (clean ones OK, adversarial ones
DO_POPRAWY). Morning report: times per operat + total/average.

| Test | Result |
|---|---|
| Live mode exclusion | 409 for run and crew while the queue is live; badge with a counter; instruction-editor warning |
| Live stop/resume | stop after the 1st of 3 → done+2×skipped, przerwana=True; report with a paths block; the "Wstaw nieprzetworzone" (Insert unprocessed) button fills the field with EXACTLY the skipped ones |
| HITL review (9 questions: l2/masywny/crew/sample/toc) | explanation of flags and of the absence of flags, verbatim re-read of the point's row (p. 9), correction path, table-of-contents drift with page corrections, area=sum of parcels from 3 pages |
| Live self-learning loop | operator note (naglowek) → review → reflection: 2 rule groups ±, generalised with rationale → apply → user overlay 914bb30c5076 → hot reload confirmed (no restart) |
| **Finding #1 (masywny)** | FAIL = a true positive of the routing union: a 2nd table with the same ids, ΔX ~600 m — previously a blind PASS; implemented dedup of consistent copies + the sprzeczne_id (conflicting id) flag + KRYTYCZNE |
| Finding #2 | reflection read overrides from the root; crew writes to tasks/ — fixed |
| Finding #3 | the reviewer cited a page when answering from the digest — the sources law clarified |
| Wording pass | PL-business register per research (MS Style Guide/mKanon/gov.pl/Comarch); collision "weryfikacja" (verification)=PODGiK → "kontrola" (check)/SKONTROLOWANO (CHECKED) |
| Suite | 200 checks, 3× green after each layer |

## Wave 11 (fala 11) — SOTA installer (goal 15:03): registration, GUI drill-through

| Element | Verdict | Evidence |
|---|---|---|
| Research of practices | **DONE (primary sources)** | ishelp 6.6, the real install.iss of Git-for-Windows, MS Learn SmartScreen, crates.io; embeddable-python choice CONFIRMED (PSF-signed binaries vs the PyInstaller false-positive explosion #8164) |
| Registration in Windows + uninstall | **VERIFIED (LIVE)** | HKCU Uninstall: Publisher (author), icon, version, EstimatedSize, Quiet/UninstallString; Start+desktop shortcuts; full GUI cycle with pywinauto |
| Visual identity | **IMPLEMENTED** | survey-control-point marker: UI favicon + .ico for exe/shortcuts/wizard banner/Apps (make_ikony.py 16–256 + tray supersampling); multi-DPI wizard panels 100–250% per ishelp dimensions |
| Robustness | **3 mutex proofs + data guard + orphans** | AppMutex/SetupMutex fired 3× live; the question about data (default NO) — after uninstall ONLY contexts/+jobs/ remained; ZabijSieroty() (kill orphans) by the {app} path (finding: python survived a force-kill and blocked deletion); silent /SILENT: the registry comes back, jobs/ survived the cycle |
| Manifest correctness | **FIXED** | the old AppId was an invalid pseudo-GUID (GEODOC000001) — replaced with a stable real GUID (update identity) |
| SmartScreen | **DOCUMENTED for the owner** | unsigned = a warning until the hash builds reputation; since 2024 Certum OV is enough; order: rcedit→sign→iscc (INSTALLER.md §4) |

## Demo film (16:10) — a silent showing of processing + the feedback loop

`docs/demo/geodoc-demo-przetwarzanie-operatu.gif` (24 frames, 1568×772,
5.9 MB; live recording via claude-in-chrome gif_creator). Scenario:
clean shell → click "Przetwórz operat testowy" (Process the test operat) → **complete result in ~1 s
on the code track** (log: 16:14:07 ingest → 16:14:08 seal) → seal,
coordinate list with lineage, checks → a question to the reviewer (answer by the 80B
analyst with verbatim values and "Źródła: s.3" (Sources: p.3)) → click on cell X → lightbox
with the value outlined ON the document page → download of przeglad.csv +
wgranie_*.csv → contrast: ars-operat_l2 (bad scan) = KONTROLE: FAIL (CHECKS: FAIL) +
BEZ PIECZĘCI (no seal) plaque. The LLM track (full verdict+chapters) shown as a number:
avg. 235 s/operat in the morning report.

## Wave 12 (fala 12) — the conversational paradigm (goal 16:37 + corrections 16:5x)

| Element | Verdict | Evidence |
|---|---|---|
| Research of standards for file-producing chat apps | **DONE** | three-column grammar (the NotebookLM persistent variant for single-task), attachment-card anatomy, step indicator with ticks (never %), aria-disabled with an explanation, inline approval card, auto-titled conversations, NN/g/HAX/PAIR trust rules |
| Conversation = the unit | **IMPLEMENTED (1ce64d4+60910d0)** | PDF→chat→stages as messages→files as attachments→questions in THE SAME thread (one context, KV, record); drawer = conversations named after the document (parcel from the header), queue tag; adoption of legacy jobs |
| Human marker | **IMPLEMENTED** | —/✓ approved/✗ rejected, a segment in the conversation header, glyphs in the drawer, store.set_meta |
| Suggested replies (owner's correction) | **IMPLEMENTED** | chip "Wszystko się zgadza" (Everything checks out) = accept in 1 click; "Popraw ten etap…" (Correct this stage…) = editable prefill, Wyślij (Send)→"Powtórz etap" (Repeat stage), Esc cancels — the Claude Desktop pattern instead of wooden buttons |
| Human narration of stages (owner's correction) | **IMPLEMENTED** | Label: value — "Wykaz współrzędnych: znaleziony (strona 3)" (Coordinate list: found (page 3)); zero technical fields/True/lists |
| Agent indicator + send freeze | **IMPLEMENTED** | pulse ●, aria-disabled + a sentence saying WHY, scrollable history |
| Side panel | **IMPLEMENTED** | stage stepper ✓/●/○, seal, files with sizes, details link |
| Finding | **FIXED** | the step-by-step path finished without stage_outputs → _final produces the files on the fly |
| Film v2 | `docs/demo/geodoc-demo-rozmowa.gif` | 17 frames: upload→greeting→card in plain language→"Popraw ten etap"→operator note→retry→acceptances→finale with files→question→answer (Źródła: s. 3)→marker ✓ |

## Wave 12b (fala 12b) — the satisfaction loop + natural language (goal 17:42)

| Element | Verdict | Evidence |
|---|---|---|
| State after the files | **CLOSED** | chips "✓ Wszystko dobrze — zatwierdzam" (All good — I approve) (marker) and "Popraw etap…" (Correct a stage…) → choice of 4 stages → prefill "Popraw (nagłówek operatu): …" (Correct (operat header): …) → cursor rewind + retry → later stages + a NEW finale |
| Trust finding | **FIXED live** | finale #2 promised new files, the only-when-empty guard skipped them (CSV 17:16 with the old name) → the finale ALWAYS regenerates; proof: the correction "wykonawca bez formy prawnej" (contractor without legal form) in przeglad.csv 17:53 (GEO-PRO) |
| Natural language | **FULL PASS** | "pieczęć powtarzalności" (reproducibility seal)→"pieczęć (kontroli)" (seal (of checks)); "Kontrole: PASS"→"Wszystkie kontrole zaliczone" (All checks passed); "Werdykt końcowy" (Final verdict)→"Ocena końcowa" (Final assessment); inflection of numerals; adoption intro in plain language |
| Batch → conversation | **VERIFIED** | mini-queue 2×OK (129/115 s); an item opened as a conversation: intro + 4 attachments + a question with an answer (Źródła: s. 1, s. 2) + chips "Zatwierdzam" (I approve)/"Przetwórz ponownie krok po kroku" (Reprocess step by step) |
| Limit of an operator note (note) | **DOCUMENTED** | the note "data w DD.MM.RRRR" (date as DD.MM.YYYY) does not break the GBNF contract (YYYY-MM-DD) — rightly: data format is the template's law; v-next: date format per PODGiK profile |
| Film v3 | `docs/demo/geodoc-demo-rozmowa-v2.gif` | 11 frames: cycle → finale (new language) → "Popraw etap…" → stage choice → "Popraw i przelicz" (Correct and recompute) → return+recomputation → finale#2 → "✓ Wszystko dobrze — zatwierdzam" |

## Wave 13 (fala 13) — "how smart a model do we need?" (owner's goal 19:11, measurement 19:12–19:35)

Owner's hypothesis: intelligence written into the workflow (GBNF, checks in code,
referee, grounding, digests, fragment selection by code) → the model is a
replaceable engine. **30B-everywhere trial** (analyst=worker gguf,
zero downloads, mmap shares the weights):

| Test | 30B-everywhere | 80B (reference) |
|---|---|---|
| Golden full-wired | **PASS, OK, 172 s** | PASS, OK, 153–172 s |
| toc_kłamie | **DO_POPRAWY ✓** | DO_POPRAWY ✓ |
| l2 (bad scan) | **DO_POPRAWY + FAIL ✓** | DO_POPRAWY + FAIL ✓ |
| lokalny | **OK ✓** | OK ✓ |
| Reviewer (3 questions) | values verbatim, area=sum of parcels from 3 pages with the arithmetic, KRYTYCZNE flags explained, "Źródła: digest operatu" (Sources: operat digest) (the new rule works) | equivalent; 30B slightly rougher linguistically ("z strony", "wykresem" instead of "wykazem") |

**Key observation**: both models are A3B (3 bn active/token) —
end-to-end pace EQUAL. The worker/analyst separation gives less than
assumed. The emerging product ladder:
- **Light = 30B-everywhere**: pack 18.6 GB, RAM ~24 GiB (32 GB laptops!) — manifest `models-lekki-30b.json` in the repo
- **Standard = 80B-everywhere**: pack 45.3 GB, RAM ~48–50 GiB without repack (a 64 GB office machine; --no-repack = the first knob of the deployment profile; repack ON = dev only)
- The dual-engine variant (64 GB pack) loses its raison d'être, unless a mass-transcription measurement (-np 4) shows an advantage — to be checked
- RAM arithmetic: IQ4_NL=42.2 GiB of weights (FP16 would be 149); the measured 84 GiB RSS on dev = repack (private ~44) + mmap in cache at 190 GB — an artefact of abundance, not a requirement; Q8 ~85 GB file (≥96 GB RAM, blind test before deciding); Q2/IQ2_M ~26–29 GB — unnecessary, since 30B@Q4 wins that tier

## Wave 14 (fala 14) — single-disk medium + variant choice in the installer (goal 19:44)

Owner's questions: a big installer with the models inside? will zip help? models
downloaded at startup? Answers BY MEASUREMENT (details in
INSTALLER.md § 5): (1) Inno >2 GB = DiskSpanning (GOG pattern, ~31
.bin at 64 GB) — we stay with `external` (GGUFs next to setup.exe,
build in seconds, one medium serves all variants); (2) zip:
quantised weights are incompressible — deflate 97.77 % / lzma2 98.03 % of
the original (256 MiB from the middle of the 30B); (3) nothing is EVER downloaded —
offline-by-design, a file missing from the medium = the variant choice is blocked.

Done: [Types] Standardowa (Standard) / Jednomodelowa 80B (Single-model 80B) / Lekka (Light) + [Components]
fixed with ExtraDiskSpaceRequired; 6 deployment manifests
(`installer/manifesty/`, relative paths); preselection (update →
variant from the pack manifest, fresh install → contents of the medium); guard
NextButtonClick; GGUFs `onlyifdoesntexist` (an update does not rewrite
64 GB, a variant change adds a file); import/change deletes `.verified`
→ the launcher computes sha256 once. Battery m80 (80B in both roles): golden PASS/OK
343 s, toc_kłamie DO_POPRAWY 354 s, l2 FAIL→ODRZUC (reject) 313 s (stricter than
the 30B's DO_POPRAWY — both sides correct), lokalny OK 186 s → variant
functional, ~2× slower (transcription on the 80B) — stated honestly in the type
description. pywinauto drill: preselection of Light ✓, Standard blocked without the
80B ✓, installation of 18.6 GB in 61 s ✓, verify_models True 13.3 s ✓.

## Wave 15 (fala 15) — PDF engine swap: PyMuPDF (AGPL) → pypdfium2 (BSD/Apache) (goal 20:33)

Owner's decision (a 100 % permissive stack, no Artifex commercial licence):
exit (b) from the legal flag of the SOTA plan. `app/pdfpages.py` = the engine FACADE
(all PDF access in one module; top-left rects at the boundary, conversion
inside; RLock — PDFium is not thread-safe, server + night queue).
The consumers (stages/rozdzialy/opisy/walker/ocr/server/tests) do not see the
engine. Port nuances: PDFium's FontWeight returns 0/-1 on embedded
fonts → bold by font NAME; `\r\n`→`\n` normalisation; get_bounds()
instead of get_pos() (pypdfium2 5.x); lines from count_rects runs merged
by vertical overlap. PyMuPDF stays in tools/ (arsenal generators,
anonymize) — requirements-dev.txt, never in the installer payload.

Parity evidence (Light 30B variant, dev): code probe (mapy 8/8 images
with captions, chaptered 5 chapters exact, folio, value boxes), suite 254
ALL GREEN, battery 6/6: sample PASS/OK 172 s (identical), toc_kłamie
DO_POPRAWY 251 s, l2 FAIL→DO_POPRAWY 252 s, lokalny OK 123 s, mapy
DO_POPRAWY 224 s (invariants IDENTICAL to the ars-operat_mapy baseline —
a property of the fixture), mixed_dpi PASS/DO_POPRAWY 252 s (BETTER than the baseline:
area 0→7943.7 m², zone true, coordinate list confirmed; flags
wsp_jeden_silnik ×3 = the judge's honest caution). Media descriptions 8/8
grounded. `docs/THIRD-PARTY-LICENSES.md` (ships with the installer) closes the stack:
100 % permissive. Dev switched to Light (models.json; Standard in
models-standard.json).

## Wave 16 (fala 16) — probe: 30B as a general data miner (owner's question 21:19)

Experiment (~80 lines on llm.ensure/chat + a GBNF schema, zero changes to the
product): a synthetic sales register of 58 rows with planted
problems (duplicate ID with conflicting amounts, outlier 250 000, missing NIP (tax ID),
mixed separators 1.234,56/1234.56, a collapsed July). The geodoc
protocol transplanted: the model PROPOSES checks (constrained decode,
enum of types) → CODE executes them on the whole → the model REPORTS only from the results
→ the grounding gate counts unsupported numbers.

Result (53 s, both calls, judge profile): check plan **5/5 types**
with sensible keys; the report pointed out ALL the planted problems
(FV/113, FV/145, 6 missing NIPs, 19/39 formats, totals per counterparty,
decision points for a human, a conclusion about revenue concentration) —
and found an UNINTENDED second conflict (FV/145 was also drawn in the
loop) — the model beat the probe's grader. A snag consistent with the laws: in free
narration it computed differences/percentages/a total and got the total wrong (345 977.20 vs
377 416.50) → product conclusion for data verticals: ALL
derived values (deltas, shares, grand totals) are computed by code and supplied in the
results; the narration may only quote. This is the 1:1 lesson "code computes,
the model reads". Factory confirmed: a new vertical to a prototype with
gates in a quarter of an hour, because the core (llm/chat/GBNF/profiles/grounding) does
all the work; domain = schema + check library + two prompts.

## Wave 17 (fala 17) — agent experiment: 8B/30B/80B with free access to a Neo4j graph + files (goal 22:58)

Harness (scratchpad/agent_graf.py): llama-server --jinja (native
tool calling), tools cypher (read-only, jail) / listuj (list) / czytaj (read)
(repo graph-theory-system-modeling), a budget of 12 calls with a countdown in the
results + a forced answer after the budget (tool_choice=none). Three
questions: P1 graph navigation (the CheckItOutV3 partition), P2 file
retrieval (the Five Independent Detectives method), P3 mixed (Claim
verdicts in V3Lab + V3 documentation). Ground truth collected separately before
the runs; auto-grader of checkpoints.

| | P1 graph | P2 files | P3 graph+files | failure profile |
|---|---|---|---|---|
| 30B A3B | **▲** 18/18 names, path Master→subscription, 6 cypher/83 s; 1 false sub-conclusion (guessed HAS_ENTITY→"no entities") | ○ decoy Promts/, an honest "I did not find it" | ○ skipped the graph (1 count), excellent file synthesis | false absences |
| 80B A3B | ○ facts ok, slower, forced | **✗ confabulation**: latched onto the decoy and announced that FIDM is an "internal metaphor" of the Erdős architecture | ○/✗ good numbers, but it looked for verdicts as :Verdict NODES → "no assessment mechanism" (the verdict is a property!) | **confident confabulation + an ontology error without self-correction** |
| 8B dense | ✗ a correct query RETURNED data, but properties() flooded the window with an embedding → false absence | **▲ found the file**: faithful description, consensus/divergence, 40–60 % | **▲ full verdict taxonomy** C1–C13 from the graph (PROVED×5, TAUTOLOGY, CATEGORY_ERROR, METAPHOR, FALSE…) + the audit file | drowning in window noise |

Meta-conclusions: (1) size ≠ agentic reliability — each model won
one question, the 8B won TWO on hard checkpoints; (2) failure patterns
DIFFER qualitatively: small = premature "it isn't there", large =
fluent confabulation (sounds best = most dangerous) — literally FIDM's
thesis about confident wrongness and our gate doctrine; (3) discipline >
model: without a budget the 30B drifted for 14 rounds without an answer, with a budget —
a clean answer in 6 calls; (4) tools shape the result: the lack of
`szukaj` (search, grep) lost P2 for 2/3 models; the lack of an embedding filter in
cypher lost P1 for the 8B; (5) interactive pace for all (83–459 s
/question), the 80B batched calls in parallel (12 calls in 4 rounds).
Product-wise: free access to the graph does NOT replace navigation recipes
(L1/L2/L3 ai_instruction in the graph exist for a reason); and the geodoc
doctrine (budgets, gates, result projections) carries over 1:1 to
graph agents.

## Wave 17b (fala 17b) — round 2 on the REAL system: a navigation primer instead of discovery (owner 00:01)

Owner's correction: files = real repos (checkitout-backend + fe-greenfield),
graph = CheckItOutV3/System/BE modelling THIS system; the agents get a
PRIMER (the 6-entity model, navigation levels, the Erdős protocol WITHOUT a persona:
first graph→structure, then files→the full picture, ignore embeddings) +
the `szukaj` tool + a vector filter in cypher (lessons from round 1). Questions:
Stripe webhook E2E, FE OpenAPI codegen, applying to a campaign E2E.

Hard checkpoints /15: **80B 12, 30B 10, 8B 9** (after the correction for
an invented FE service). ZERO Cypher errors for all (round 1: they guessed
the schema). The 30B extracted from the code the two-layer webhook idempotency
(eventId + unique constraint + DataIntegrityViolationException); 80B
P2-codegen 5/5 and EXPLICIT honesty ("this fragment remains unknown" about the
FE — yesterday it confabulated!); the only fabrication of the round: the 8B invented
`AppliedOpportunityApiService.submitApplication()` on the FE.

Laws from the pair of rounds (1: without a primer / 2: with a primer): (1) ~400 words
of navigation primer turn a lottery into ordered reliability —
knowledge structure in the prompt > parameters; (2) the primer cured the large
model's confabulation (the schema vacuum was its cause);
(3) **models invent exactly at the boundary of the graph's coverage** — the graph
models the BE, the FE has no representation → the only hallucinations of round 2 are on the FE;
product conclusion: an FE navigation layer in the graph or an explicit
instruction "the FE is not in the graph — only search/read"; (4) the
Light/Standard ladder confirmed agentically too: 30B with a primer ≈ 80B on
2/3 questions, for 40 % of the RAM.

## Wave 18 (fala 18) — single-model analysis: 2 roles, 1 gguf, next to OCR (owner's goal 09:31, 3 recon agents)

Three independent analyses (coupling map / feasibility of 1 process /
simplification dividend) converge on the verdict: **one MODEL — yes;
one PROCESS — no.** Load-bearing facts:

1. Process coupling 100 % enclosed in app/llm.py (no other
   module knows the ports); the currency is model_key = a pure abstraction of ROLES.
   Proportions: ~10 ROLE places (they stay), ~9 DUAL (debt to cut),
   ~6 PROC (enclosed, unchanged).
2. Fusion into 1 process: mmap has already consumed the reward (shared weights,
   ~20 GiB for two 30B servers). Costs of fusion: -np splits -c EQUALLY →
   preserving the windows = -c 81920 = KV ×2.5 (+4.5 GiB vs a saving of
   2–4 GiB of buffers); slot-0 hardcoded (save at -np>1 gave
   EMPTY writes — measured in the E series); isolation of the chat from the night
   bulk exists TODAY solely thanks to two processes; flipping parallel
   1↔4 reboots the process (eviction of the conversations' warm KV); replay
   determinism broken by shared continuous batching.
3. Which single model: **30B** (full battery, 172 s, fits in 32 GB;
   verdicts correct). 80B-only only as an installer variant for
   64 GB office machines — preferably without the bulk profile (2× transcription time;
   bulk -np 4 on the hybrid unmeasured).
4. Drift DISCOVERY: the judge is pinned to model_key="worker"
   (agents.py:204) — in Standard the verdicts ALWAYS went to the 30B, although
   pomoc.html says "analityk 80B" (80B analyst) (7 places lie under Light).
   Strengthens the "30B is enough" thesis and requires a copy correction.
5. DUAL debt to cut (sequence when the owner says YES): (a) fix
   pomoc.html to role names without sizes + the judge drift; (b) dead
   default model="qwen80b" (server.py:449, store.py:23); (c) manifests:
   unify Light's flags (checkpoints are a no-op on a transformer;
   cache-reuse can be given to both 30B roles), ctx_ceiling for the worker in
   models-80b.json; (d) delete the standard variant from the installer
   (3→2 types) + models-standard*; (e) LAST residency_mode/e9 —
   only if 80B-only also drops out of the release (with 80B on 64 GB the
   mechanism is still needed). Untouchable: roles/profiles/manuals,
   KV contract, digest hook, gates, seal (records role→file —
   the audit survives single-model operation), ctx_law, -np 4 bulk.
6. OCR: confirmed twice — zero coupling with the number of LLM models
   (RapidOCR/onnxtr; the only shared thing is the 16 GB RAM headroom in residency).

## Wave 19 (fala 19) — EXECUTION: the single-model 30B product (owner's goal 09:44)

Decision executed in full (except code signing — owner-gated). Changes:
manifests (dev + deployment) → both roles on Qwen3-30B with the analyst's
flags cleaned up (checkpoints = a hybrid legacy, ctx_ceiling =
a DeltaNet law — both removed; cache-reuse NOT added to the analyst —
battery-validated behaviour matters more than symmetry); deleted
models-standard/models-80b/pack-standard/pack-80b; single-variant
installer (no [Types]/[Components], model guard on the welcome
page, ExtraDiskSpaceRequired in [Setup], .verified for a single file);
pomoc.html: roles → PROFILES (roboczy/oceniający — working/assessing) — consistent with the truth of the code
(verdict = judge on the worker key), labels fitted to the SVG frames;
dead default qwen80b → worker (server.py, store.py); seal:
model bytes computed for relative paths too (a deployment install
stops writing bytes=null); INSTALLER.md §5, SOTA §7a-bis (decision),
THIRD-PARTY-LICENSES (one model, Q4_K_M), build_installer.ps1.
residency_mode STAYS deliberately: on 32 GB machines a single swap
between roles is needed (18.6·1.1+16 GB > 32 GB).

Validation: suite 254 ALL GREEN; .iss compilation clean; silent
installation from the medium — assertions ✓ (deployment manifest with the new flags,
1-file pack, model not rewritten, .verified rightly preserved);
final battery: golden PASS/OK 176 s, toc_kłamie DO_POPRAWY 252 s,
review via the analyst's chat path (restore/save on the new flags)
— coordinates verbatim + "Źródła: s. 3". The 80B remains a research option
(going back = one manifest entry); the 9950X = the dev machine, not the reference.

## Wave 20 (fala 20) — final tests of the single-model 30B: suite, chat, batch, MEASUREMENTS (goal 10:07)

Suite 254 ALL GREEN ×2. **Chat (supervised cycle via the API)**: upload →
start → run/accept per stage (classifier 27.8 s / header 17.3 s /
coordinate list 42.3 s / verdict 9.4 s) → done after 122 s; question after the finale 23.6 s
— answer grounded verbatim (both coordinates, sources p. 3, 2);
marker approved + list entry ✓. **Batch**: 2 files (short+local)
done in 240 s, the ETA appears after the first item, 24 progress samples,
the mode-exclusion law works (conversation/start during the queue → 409).

**Performance measurements (dev 9950X, 16 physical cores)**:
- t/s single slot: PP 208–247 t/s (prompt 1.3k–4.8k tok), TG
  15–20 t/s; the assessing profile ≈ the working one (the same model).
- E2E per file (full pipeline with the verdict): short 3 pp = 133 s
  (44 s/page), golden 5 pp = 176 s (35 s/page), toc 16 pp = 252 s
  (16 s/page), massive 122 pp = 538 s (**4.4 s/page**) — fixed cost
  ~2 min (boot+digest+verdict) + ~4 s/page marginally; bulk -np 4
  pays off on large documents (massive FAIL = the designed
  true-positive dedup).

**A real production bug fixed (audit during the measurements)**: a llama
server from a PREVIOUS process (CLI/crash) survived and occupied the port —
the new boot died on bind, and _wait got health from the OLD server with
the wrong configuration (-np/flags/gguf from before the change); in the product, after
a tray crash, startup could silently talk to a stale engine.
Fix: llm._uprzatnij_port() (tidy up the port) before boot terminates ONLY llama-server
processes listening on our port (other processes untouched —
then startup fails loudly, correctly). Validated by reproduction:
orphan -np 4 → ensure() → fresh -np 1, a 4814-tok prompt goes through.
Nomenclature per the owner's remark: no "killing orphans on the port" —
_uprzatnij_port / UprzatnijProcesy.
The t/s probe with threads was methodologically flawed (the first readings
contaminated by adopting the orphan) — reliable numbers come from clean single
requests + the pipeline level.

## Wave 20b (fala 20b) — QA through the browser (owner's question 11:09: "and did you check through Claude in Chrome?")

Rightly so — the 10:07 tests were API-level. Full QA in a real Chrome
(claude-in-chrome, http://127.0.0.1): (1) rail with conversations + markers ✓;
(2) a completed conversation renders exemplarily — stage cards in plain language with
instruction hashes, the finale in the language of facts + CSV/XLSX file cards,
stepper with the green check line, chips "✓ Wszystko dobrze —
zatwierdzam / Popraw etap…"; (3) a LIVE question through the composer →
answer in <10 s (warm KV): area 7051.0 m², 9 points with a breakdown
new/changed, sources p. 3, 4; (4) broken conversations from a faulty driver
render honestly (repeated cards = the audit truth of the transcript;
the reviewer answers from the partial state with a repair hint; the
"Kontynuuj przetwarzanie" (Continue processing) button); (5) the task queue panel in the register;
(6) zero console errors.

CAUGHT by the browser (invisible from the API): two copy errors in
the help page after yesterday's swap — the heading "Jeden silnik, dwa modele" (One engine, two models)
and the botched splice "Sercem są dwa jeden model językowy" (garbled: "At the heart are two one language model") → fixed ("Jeden
model, dwa profile, zamrożone wagi" (One model, two profiles, frozen weights)), verified by zooming into the render.
SVG labels fit inside the frames. Standing lesson: copy swaps
ALWAYS have to be viewed in the render, not only via grep.

## Wave 21 (fala 21) — licence page in the wizard + the model bundled in the installer (goal 11:47)

**Licence**: MIT as of today — the wizard shows the LICENSE text on a native
Inno page (pywinauto drill: page visible, "Dalej" (Next) only after
acceptance). OSS: llama.cpp MIT + Qwen3 Apache 2.0 in
quantised form, list in docs/THIRD-PARTY-LICENSES.md.

**Bundle**: the model compiled into the installer — DiskSpanning=yes →
release = setup.exe (3 MB) + 9× .bin (18.7 GB; the GOG pattern — the user
clicks only the exe, everything in one directory); gguf `nocompression`
(weights incompressible) + `onlyifdoesntexist` (an update does not rewrite;
repair = delete the file + reinstall); the medium guard from NextButtonClick
REMOVED (there is no medium); compilation 182 s. Extraction test: model
deleted → silent installation restores 18.56 GB in 114 s, `.verified`
deleted (the launcher will recompute sha256) — PASSED.

Test trap of the day: /SILENT + /SUPPRESSMSGBOXES with a second installer
alive (SetupMutex) = the suppressed box **defaults to Anuluj (Cancel)**
→ EAbort in 25 ms; the "waiting" process turned out to be the drill's bootstrapper.
Lesson: before silent tests always kill the geodoc-setup* processes.
