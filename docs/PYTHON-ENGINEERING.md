# PYTHON-ENGINEERING — audit, research, decisions (06.08, "old-fashioned good engineering")

Method: static scan (ruff) + profile (cProfile on a 122-page document) as
MEASURED INPUT → 3 crawler audits with extended thinking (architecture/
SOLID, algorithms/performance, robustness/Python quality) → decisions with
rationale → implementation in slices with the suite after each one. Baseline: 5 959 LOC,
17 app/ modules, zero circular imports.

## 1. Static scan (ruff) — result and decisions

14 findings / 5 959 LOC. **IMPLEMENTED**: 2×F401 (dead imports), 2×F841,
1×F541 — removed. **REJECTED with rationale**: 7×E741 (`l` as a loop
variable) — local comprehensions with a 1-line scope; renaming does not
reduce risk, it increases diff diffusion; 2×E402 (server.py imports after
sys.path.insert) — a necessity of the application layout, deliberate.

## 2. Profile (measured) — IMPLEMENTED, result **20×: 9.9 s → 0.5 s**

| Finding | Cause | Fix | Effect |
|---|---|---|---|
| 60% of the time = OCR of 17 TEXT pages | has_text: a 40-character threshold branded 1-line pages as raster | a text+geometry discriminator: short text without a dominant image = text; short text ON a full-page image = a scan with a stamp | 17→0 unnecessary OCR runs, −6.0 s |
| text_layer: 668 calls = 668 PDF opens | no cache; 5.5×/page via walker/assembly/gates/summaries | lru_cache of the whole document keyed by (path, mtime); 64 docs, thread-safe | 668→6 opens, −1.5 s |

## 3. Architecture audit (SOLID/DRY/OCP) — verdicts

**IMPLEMENTED**: R3 `teksty.py` (one home for fold/jread/jsave-atomic/
page_text/page_core — three copies of _fold with DRIFT eliminated at the source of
future bugs); a setdefault crash in the flag merge (a clean document with a
SINGLE diacritic signal threw a KeyError).
**ACCEPTED with a recipe (v1.0 service window, not the shipping night)**: R1 a table of
stage definitions shared by agents↔crew (~40 lines moved; today the
payloads are duplicated verbatim — a prompt change in agents silently desynchronises supervised
mode; recipe in crawler A's report); R2 a gate registry in
stage_checks (every gate = a function (ctx)→(checks,flags); a new gate =
one function); jobs_root ordering in walker/opisy (testability).
**REJECTED**: classes/enterprise ceremony — the audit confirmed: "no class is
warranted anywhere"; a registry of CRS coordinate systems as a table — the domain is finite
(national coordinate systems), the if-chain is more readable.

## 4. Algorithms audit — verdicts

**IMPLEMENTED**: both top ones (profile § 2). **CONFIRMED-OK**: dup_coords,
folio_consensus, chapters_assemble O(n log n); memory a non-issue up to ~500
pages (worst ~30 MB transient); openpyxl OK up to 10⁵ rows.
**ACCEPTED with a recipe**: hoisting candidates/boxes through walk→rozdzialy_job
(2-3 full get_text('dict') scans per job on the crew path, ~1-1.5 s);
memoisation of page_text per (job,n); fold-once in page_pathologies._core;
lazy folds in grounding_check (folding 122 pages up front when tier-2 may
not fire). All localised, with no contract changes.

## 5. Robustness audit — verdicts (66 open() without a CM counted, 27 fitz.open)

**IMPLEMENTED**:
- **Atomic writes** (jsave: tmp+os.replace) at the corruption points: the
  queue of the night shift (batch queue), survey/header/wykaz/invariants/rodowod. A Windows nuance
  discovered by the suite WITHIN MINUTES of the change: os.replace throws WinError 32 when
  a reader momentarily holds the target (open() without FILE_SHARE_DELETE) → retry
  ≤200 ms. **An exposed collision**: queue bids had a resolution of one
  SECOND — two submits within one second shared a directory and two writers
  interleaved on a single tmp (a trailing `}`, a deterministic offset). Fix at the
  source (microsecond bids) + defence in depth (tmp per pid+tid). Suite 3×
  green in a row.
- **The llm.ensure race**: a Lock around the whole boot path (server threads +
  the night-shift worker mutated _procs without locking → a double spawn
  on the port); health assert → RuntimeError (python -O strips asserts —
  the packaged app would be talking to a corpse).
- **The lost batch**: a submit while the worker was alive was NOT scheduled
  anywhere — the batch hung at „czeka" (waiting) forever; the worker drains the bid queue
  + a regression test (2 batches against a live worker).
- **Compactor abstention**: a compactor error NO LONGER truncates the window (placeholder
  + keep_from = a silent loss of conversation memory).
- **Confidence trust**: slownik_naruszenia are STRINGS — a dict filter
  rendered points with code-list violations IN GREEN in the xlsx. Parsing the
  id prefix.
- **domain.py**: try/finally on 3 paths (Windows held graph.db).
**ACCEPTED with a recipe**: POST body→400 (server), /file commonpath,
crew accept-without-run→refusal, a cheap /api/jobs list, prints→_log in
the library, PYTHONUTF8 in the launcher (insurance), probe_slot_save
hygiene. **REJECTED**: type hints across the board — the house style is functions+dicts;
hints only on trap signatures alongside R1; mass with-wrapping of
53 ONE-LINE reads — refcounting closes them immediately, a purely
cosmetic change with large diffusion (new reads go through teksty.jread).

## 6. Process lesson (recorded, because it is true)

Two suite runs AT ONCE race in the shared jobs/ (my own
operational mistake during the fix) — the symptom is identical to the torn-read class.
Norm: one suite at a time; read the result from the file, do not infer it from a partial one.

## Balance

3 layers of commits (measured / correctness / robustness), 79 commits,
suite of 180 checks green 3× in a row. Code-path performance **20×**.
Three bug classes removed (crash/lost-work/corruption) + two trust
flaws (phantom flag, green code-list violations). The ACCEPTED items
have recipes in the crawler reports (task transcripts) and here — they land
in a service window, not on the shipping night: stability > completeness of the list.
