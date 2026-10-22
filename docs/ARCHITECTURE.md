# geodoc — architecture and methods (design document)

The definitive description of HOW this application is built and WHAT tricks it uses.
Research history and sources: `SOTA-2026-08.md`. Technique verdicts: `IDEAS.md`.
Packaging: `PACKAGING.md`. Repo state when this was first written (2026-08-05): 33 commits, 87 checks, setup.exe
validated by installation.

## 1. The big picture

```
browser (UI, token in URL→cookie)
   │  HTTP 127.0.0.1:7420  — triad: CSPRNG token · Host allowlist · Origin
   ▼
shell (app/server.py, stdlib)───── start_geodoc.pyw (single-instance, watchdog,
   │                                model-pack verification: sizes always,
   │                                sha256 once — marker .verified)
   ├── pipeline (app/stages.py)     CODE: pages→map→header→list→checks→outputs
   ├── LLM crew (app/agents.py)     MODEL: classifier→extractors→judge
   ├── main chat (app/chat.py)      persistent context + reversible AutoCompact
   ├── OCR (app/ocr.py)             RapidOCR (primary) × onnxtr (G4 witness)
   └── llm supervisor (app/llm.py)  llama-server per model, slot-0, KV-as-file
                                    (one resident at a time — the 64 GB law)
artefacts:  jobs/<job>/{source,pages,transcript,extracted,checks,out,document.md,docmap.json}
contexts:   contexts/<id>/{transcript.jsonl,meta.json,summary.md} + kv/<model>/<contract>/*.bin
prompts:    prompts/golden (factory, RO) + prompts/user (operator overlay)
profiles:   profiles/podgik-<n>.json (templates), powiat-<teryt>.json (learning, slice 8)
```

## 2. Laws (measured, not stylistic)

1. **The model transcribes, CODE aggregates** — aggregating 180 rows: F1=0 for 30B and 80B.
2. **Truth = text, KV = cache** — transcript.jsonl/artefacts are the source;
   any KV blob can be deleted without losing anything.
3. **A fresh context per agent call** — rot is impossible by construction
   in the pipeline; the only long-lived context is the main chat.
4. **The 0.75-window law as an assertion** — `/tokenize` before every call;
   input+output > 0.75·ctx = refusal with a re-chunk message (attention degradation
   starts long before the limit; our measurements broke down at 8–16k).
5. **The handoff-blindness law** — the classifier ROUTES pages; its guesses
   at values never go to the extractor of those fields (anchoring survives
   "verify it yourself" in ≤10%; error cascades ×6–10). Only the judge sees the values.
6. **Uniform check polarity** — in checks, true ALWAYS means good
   (an inverted key taught the judge a false alarm — measured).
7. **Abstention > guessing** — null + a „DO SPRAWDZENIA" (to check) flag instead of a guess;
   the judge flags unknowns (None), never passes them.
8. **Slice-per-commit behind a golden gate** — every change to the LLM path goes through
   the full cycle on the golden file (9/9 to the cm) before it lands.

## 3. Context machinery (the core)

- **KV-as-file**: explicit `POST /slots/0?action=save|restore` into a directory
  versioned by the state CONTRACT `sha256(gguf|size|ctx|build)[:12]` — blobs
  carry no validation, a mismatch = silent corruption. Measured: restore across
  a server RESTART works, 5.6× faster than re-prefill. `-np 1` mandatory
  (auto-slots routed requests past slot 0 → empty saves).
- **Resume ladder**: state.bin (warm) → re-prefill from the transcript (truth).
- **Chat AutoCompact** (60% of the window): the compactor reads the transcript FILE, not
  the degraded window; the summary carries POINTERS to artefacts, never numbers
  (summaries lose numbers/entities/dates first — measured in the literature);
  slot-save before compaction → **reversible compaction**. Window = a VIEW: system+
  summary from the last compact note + tail of turns; transcript append-only.
- **Cache discipline**: manual in a STATIC system prompt (prefix hit), per-call dynamics
  in the USER payload, per-job knowledge in {{SLOT}}; 30B: `--cache-reuse 256`
  + `--cache-ram`; telemetry `cache_n`+`tokens_in` in the `_meta` of every result.

## 4. Gates G1–G10 (judges inside the product)

| G | What | Where |
|---|---|---|
| G1 | JSON schema enforced at DECODE (GBNF) + retry ladder + budget | llm.call_agent |
| G2 | grounding: the value MUST exist in the document (hallucination=FAIL); wrong source page=flag | stages.grounding_check |
| G3 | a regex referee parser judges the LLM transcription on born-digital files; omissions=FAIL | stages.referee_wykaz |
| G4 | dual OCR: a coordinate confirmed by BOTH engines; one=flag, neither=FAIL | ocr.coord_agreement |
| G5 | official code lists by the date of the *operat* (surveying report filed with the county) (ZRD/BPP/STB/RZG, after 2021 SPD/ISD=None-review) + zones/ranges/shoelace/count/duplicates/dates | stages.stage_checks |
| G6 | self-consistency k on FLAGGED items (escalation, not a carpet) | designed — REJECTED: about +0.23 % on digits, not worth breaking temperature-0 determinism (IDEAS.md) |
| G7 | escalation by min-logprob of numeric fields | designed and accepted — not implemented; covered in practice by G2 (value must exist in the document), G3 (regex referee) and G4 (two OCR engines agree) |
| G8 | generation health: finish_reason, degeneration detection, budget | llm.call_agent: finish_reason=length → retry with a doubled budget; stages.dup_coords flags repeated coordinates; degeneration detection — designed, not implemented |
| G9 | the judge reads a DIGEST built by code (fails+flags+samples), not dumps | agents._digest |
| G10 | golden regression + Augraphy degradations; digit-error-rate metric | golden smokes (Augraphy queued) |

## 5. Model harness

- **Casting**: 30B-A3B Q4_K_M = worker (the whole crew); 80B-Next = analyst/chat
  (policy: FAILs, hard pages, main chat); shipping quant for 80B = **fresh
  IQ4_NL** (repack +37% PP at −5% TG, fits in 48 GB — E6b).
- **Sampling per role**: `transcribe` = temp 0 + ALL penalties 0 (penalties break
  repetitive tables) + fixed seed; `judge/chat` = Qwen model card (0.7/0.8/20/minP 0),
  presence 0 (language mixing). Non-thinking; --jinja; NO CoT under a grammar.
- **Measured CPU flags** (this machine, 16C Zen4): `-t 8` (TG peak 25.6 t/s;
  SMT/more threads HURTS) + `-tb 24` (PP peak 272.7) + `-ub 1024` (+3%);
  80B: t8=18.2 TG / tb24=128 PP; -fa neutral; speculation/DRY/XTC/control
  vectors REJECTED (reasons in IDEAS). Warmup ON (loads all experts).
- **Prompts**: markdown CAPS (the official pattern), document inside `===DOKUMENT===`,
  task AT THE END, a sandwich of the key law, a JSON example despite the grammar
  (improves the VALUES), golden/user with hash pinning in `_meta` (per-job audit).

## 6. The raster branch

RapidOCR (PP-OCRv6, 0.7 s/page) as primary with per-line confidence (a 0.85 threshold
flags) + onnxtr as an INDEPENDENT witness (a different det+rec family). The unit
of G4 agreement = the COORDINATE STRING. The crew reads `_page_text`: the text layer
or the OCR transcript (with confidence in the page header). Measured: a 100%
raster *operat* → 9/9 points to the cm via OCR→LLM; grounding grounded against the OCR
text (no false hallucination alarms).

## 7. Document map and X-ray

`document.md` (front matter, table of contents, sections `## [s. N] … {#pNNN}`,
provenance comments, RFC 8118 links `#page=N`) + `docmap.json` (page types,
folio, TOC, gaps). Folio: margin band located geometrically + consensus
(uniqueness + offset vs PDF index; ≥2 consistent readings) + **the law of physical
gaps**: a page is missing only when the folio jump EXCEEDS the number of PDF pages
in between. ***Operat* X-ray**: click a value → the page + a pulsing frame on the
region (text pages: PDF geometry; scans: OCR line boxes in PIXELS — not
points!); Excel with a „ŹRÓDŁO" (source) column (#page=N).

## 7a. Chapter layer — fusion (judge panel 06.08: B=14 vs A=8/C=11)

Phase A (INTAKE, entirely on 30B — zero swaps on the office machine) over immutable
page transcripts; phase B (DOMAIN) = the existing crew, routed by the
chapter map as a HINT (union with code detection — a wrong boundary can
assemble a folder badly, it cannot lose an extraction; a total collapse of phase A
degrades exactly to today's pipeline).

```
page transcripts (md / OCR — page_text_job)
   ▼
rozdzialy.heading_candidates    CODE: k-means of sizes (marker), title filter
   │                            (unstructured), numbering ladder (docling),
   │                            scan: OCR box heights ≥1.15×median
   ├── rozdzialy.detect_toc     ICDAR'13: monotonic legality + fuzzy ≥0.8;
   │                            TOC drift → spis_przesuniecie (TOCs lie)
   ▼
walker.walk (30B, GBNF)         CLAIMS-ONLY: picks ONLY from the code's
   │                            candidates or null; monotonic cursor; 6-page window
   ▼
rozdzialy.chapters_assemble     pure function: spine from anchors (numbering
   │                            ∪ TOC ∪ confirmed claims); no anchors =
   │                            ZERO chapters (abstention); numbering gaps
   │                            FLAGGED, never fabricated
   ├── G11 tiling               front+chapters+unlabelled = exactly 1..N
   ├── G12 title grounding      title (fold) in the 1st page's transcript; fail →
   │                            unlabelled + flag
   ▼
rozdzialy.materialize           CODE: NN-slug/rozdzial.md folders from immutable
   │                            transcripts + page sha256 (provenance);
   │                            scans: image link + OCR + description placeholder
   ▼
podsumowania.phase_podsumowania per-chapter synthesis (30B) → G13 (fact: page
                                in range + numbers VERBATIM on the page;
                                rejected → fakty_odrzucone) → HIERARCHICAL
                                merging (BooookScore: incremental merging
                                degrades small models) → master.md digest +
                                out/rozdzialy.xlsx (vital-info sheet +
                                facts sheet with #page=N links)
```

Measured (docs/bench/): masywny 122 pp. **338 s** end-to-end (code 9 s,
chapter walker 24 hops/139 s — 6/6 chapters to the page, summaries 190 s,
**48/48 facts grounded**, zero hallucinations — the gate's only stumble
was the fault of the G13 tokenizer, fixed). Adversary lab: the lying TOC defeated
by two layers (legality + drift consensus), the foreign page absorbed,
krotki without headings = an honest zero chapters.

## 8. Memory

prompts golden/user (reset=delete, hash in _meta) · profiles with entry provenance
(learned/confirmed/manual; write-back on acceptance — slice 8) ·
transcript.jsonl + summary.md (chat anchor, editable) · domain graph
(SQLite, point biography, bi-temporal supersession) = v2 from the *operat* archive.
Zero graph/embeddings as truth — indexes are a cache rebuildable from text.

## 9. Packaging and security

Two-artefact delivery: **geodoc-setup.exe 149 MB** (python-embed with wheels
and pre-cached OCR models + llama-bin with CPU-dispatch DLLs incl. zen4;
validated: silent install → pipeline PASS from the installed layout → clean
uninstall) + **model-pack** (GGUFs + a sha256 manifest next to setup.exe; launcher:
sizes always, deep hash once). The localhost triad from the lessons of real CVEs
(uTorrent RCE, Ollama DNS rebinding). User entry point = **tray**
(`geodoc-tray.exe` 0.5 MB, tray-icon+tao without webview; „Otwórz" (Open) → default
browser on the URL from the lock file, „Zakończ" (Quit) → `taskkill /T` kills the whole
launcher→server→llama tree; build recipe without MSVC: `tools/build_tray.ps1`).
Left with the owner: code signing (e.g. Certum), a fresh IQ4_NL; the AGPL decision
(PyMuPDF) resolved 06.08 — runtime on pypdfium2.
Stage-2 hardening: Job Object KILL_ON_JOB_CLOSE.

## 10a. Trust and working modes (interaction sociology, grounded in research)

**The owner's question:** autonomous mode, or supervised with a report after every
step and the operator's right to correct by prompt? **The research answer: BOTH, with
a trust ladder — and it is supervision that builds trust, rather than robbing
autonomy of its point.**

- Trust calibration (Lee & See 2004, "appropriate reliance"): trust should
  be COMMENSURATE with the tool's capability; process transparency + a track record
  of results + predictability > self-confidence. Overtrust (automation
  bias) and distrust are EQUALLY costly.
- Mixed-initiative (Horvitz 1999): automation should add value where
  it is confident and HAND BACK the initiative under uncertainty; the cost of a
  human taking over must be low.
- Ironies of automation (Bainbridge 1983): full autonomy from day one
  degrades the supervisor's vigilance and competence — and it is the surveyor who signs the *operat*.
- HITL in doc-AI (convergence of EndoExtract/CitePrism/the invoice industry):
  side-by-side + mandatory review of low confidence + thresholds = the standard.

**Our implementation — the autonomy ladder:**
1. **Supervised mode** (`crew.py`, „Tryb nadzorowany" (Supervised mode) in the UI): the pipeline stops
   after every stage; report = agent + manual hash + result; operator:
   [Accept → continue] or [Repeat with an OPERATOR NOTE] — the operator note is an explicitly
   marked block BINDING on this run (but the contracts and hard gates
   remain), saved in `overrides.jsonl` with provenance.
2. **Crystallisation**: with one button a proven operator note goes into
   the user manual overlay (section `# DOPISKI OPERATORA` (operator notes)) — the human's correction
   STAYS, and visibly so (a new hash in every subsequent job). This is the
   mechanism by which interactive prompts become product prompts.
3. **EARNED autonomy**: auto mode becomes the default only for a class of documents
   with a history of green reviews (per county/*operat* type — a counter in the
   profile); a new county starts supervised. Levels as in automotive.
4. Trust is built by ARTEFACTS, not declarations: the X-ray (evidence on a click),
   the replay seal (reproducibility to the byte), abstention (null instead of
   guessing), two-witness flags. A tool that can say
   "I don't know" and point with a finger beats a tool that always knows.
5. **Flywheel → LoRA**: accepted jobs + operator notes = a corpus of pairs
   (input, corrected answer). An earlier measurement of our own (a 4B model: 0.9752
   vs 0.246 prompt-only on our own domain) says it plainly: on a narrow domain
   fine-tuning WINS — but only once the corpus exists. The supervision studio is
   the factory of that corpus; a 30B LoRA on *operaty* = a stage after ~hundreds of jobs.

## 10b. Review — the feedback loop AFTER processing (owner's goal 06.08 12:38)

The operator note closes the loop DURING a run; review closes it AFTER:
the operator asks about FINISHED data in the chat beside the documents, each question =
one grounded analysis by the reviewer (the 80B analyst — resident after the run
anyway, so the moment of questions hits a hot model).

Mechanics: a context bound to the job (`store` with meta `job`, role
`rewident`) — the primer is a DIGEST computed by CODE (header, checks,
flags, confidence with reasons, chapters, gaps) saved as a
`kind=digest` note → a stable KV prefix (the resume ladder works; AutoCompact
composes with the digest). Material per question is selected by CODE, not by the
model: explicit pages (`s. 7`) > mentioned point IDs (coordinate-list row +
its page) > references to chapters (range from docmap) > keyword fold-scoring
over `page_core`; budget 5 pages × 2800 chars. The context
transcript stores WHAT THE MODEL SAW (the full payload — an audit
view in the left panel), the user row carries `pytanie`+`zrodla` for the UI;
every exchange is mirrored to `analizy/rewizja.md` next to the documents.
Separation of responsibility from the seal: the seal proves the pipeline,
review is a conversation — `analizy/` lies outside the seal's sweep
BY CONSTRUCTION (the sweep takes files, not subdirectories).

Manual `rewident.md` (golden, editable like any other): only the supplied
material; numbers verbatim with the address `s. N`; abstention „nie mam w
materiale — dopisz stronę" (not in my material — add the page); corrections → pointer to supervised mode;
zero confidence percentages (calibration law). Live evidence: routing to p. 2 +
keyword→p. 1, verbatim quotes (RTK GNSS / 0,10 m / 2026-06-11), one
context across both questions.

## 10. Index of tricks ("methods that survived measurement")

KV state contract · reversible compaction · digest-only judge · check
polarity · blind handoff (routing) · two OCR witnesses on digits · folio
consensus + the gap law · the 0.75 budget as an exception · sampling profile per
role · penalties=0 for transcription · example-in-the-prompt under a grammar · slots
{{…}} without breaking the prefix cache · prompt hash pinning · replay seal
(seed+hash+build) · sizes-always/hash-once on the model-pack · the page-points-with-a-
finger (X-ray) · abstention as first-class UX.
