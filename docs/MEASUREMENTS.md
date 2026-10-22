# Measurements

How geodoc was measured, on what, and where each figure comes from. The README states the claims; this page is the path to check them. Raw logs live in [`bench/`](bench/), and the decision ledger [`IDEAS.md`](IDEAS.md) records every run with its date.

## What the figures are measured against

Every accuracy figure comes from **synthetic, seeded reports** with a known answer. [`tools/make_test_operat.py`](../tools/make_test_operat.py) and its siblings generate the PDFs and the gold files (`testdata/gold*.json`, seed 20260729). A real operat has no gold answer, so no accuracy figure exists for real reports. On three public sample reports, used during development and not shipped here, the checks failed where the format differed from the synthetic one. That was the expected, honest result.

## The check suite

```
python tests/test_core.py
```

The suite is a plain script, not a pytest suite. It runs without a model, in about ten seconds, and prints one line per check. It covers PDF reading, OCR, the gates, the code invariants, coordinate-system detection, chapter detection on the synthetic family (including exact chapter boundaries on the 122-page report), the exports, the seal's determinism and the launcher's model-integrity check. The model calls are replaced by scripted fakes where a stage needs one. CI runs it on Windows on every push to main and on pull requests. Its last three checks compare the README's two counts with this harness and with [`testdata/ARSENAL.md`](../testdata/ARSENAL.md).

## Accuracy on the synthetic reports

| Document | What it tests | Result | Source |
|---|---|---|---|
| `operat_sample.pdf` (5 pages) | text layer plus one raster page | 9 of 9 boundary points exact to the centimetre; checks PASS, judge OK | [`bench/live-series.txt`](bench/live-series.txt), ARSENAL |
| `operat_scan.pdf` (5 pages, all raster) | the whole report read through OCR | 9 of 9 points exact to the centimetre; the shoelace area equals the gold | IDEAS, row "Full scan pipeline" |
| `operat_multi.pdf` (36 points on 4 pages) | parallel extraction, 4 slots | 36 of 36 exact in both serial and parallel mode | IDEAS, row "Bulk profile -np 4"; [`bench/e20-bulk-cacheram.txt`](bench/e20-bulk-cacheram.txt) |
| `wykaz_degraded.png` | OCR on a seeded "bad photocopy" | the suite enforces at least 16 of 18 coordinates digit-exact; measured 18 of 18 | harness check `g10` |
| `operat_l2.pdf` (16 pages, heavy degradation) | skew, shadows, stains, punch holes, photocopy, JPEG 35–55 | chapter structure 5 of 5; OCR reads 7 of 9 coordinates; the checks flag the rest and the verdict is "needs correction" | [`bench/arsenal-sweep.txt`](bench/arsenal-sweep.txt) |

## The adversarial arsenal

[`testdata/ARSENAL.md`](../testdata/ARSENAL.md) lists the adversarial documents. Each one is a structural adversary at one of three severities: a clean text layer, a scan, or a heavily degraded scan. Each row records the expected behaviour, not just a score. Examples:

- A table of contents shifted by two pages, with one invented entry.
- A foreign invoice bound into chapter 3.
- No headings at all, where the right answer is to abstain.
- Blank pages and a duplicated page from a double feed.
- Two logical pages scanned onto one sheet.
- Mixed scan resolutions.
- A 122-page report, both as a text layer and as a full scan.

Four further fixtures exercise the older coordinate systems (1965, 1992 with and without a declaration, local) and sit outside the table.

## Time

These timings cover the full pipeline with the judge, on the single-model product (Qwen3-30B-A3B in both roles). They were measured on 2026-08-07 on the development machine: an AMD Ryzen 9 9950X with 16 physical cores, CPU only. Source: IDEAS, section "Wave 20".

| Document | Pages | End to end | Per page |
|---|---|---|---|
| short | 3 | 133 s | 44 s |
| golden sample | 5 | 176 s | 35 s |
| table-of-contents adversary | 16 | 252 s | 16 s |
| 122-page report | 122 | 538 s | 4.4 s |

That is a fixed cost of about two minutes (server start, digest, verdict) plus about four seconds for each additional page. A single slot reads prompts at 208–247 tokens per second and generates 15–20 tokens per second.

The ledger says it itself: the development machine is not the reference. No timing has been taken on a 64 GB office machine.

## The logs in `bench/`

| File | What it recorded |
|---|---|
| `arsenal-sweep.txt` | the code layer and OCR against four adversaries; the degraded scan reads 7 of 9 coordinates |
| `full-wired-run.txt` | the chaptered report through the full path: PASS, judge OK, 5 chapters, 4 images, 33 summarised facts, 220 s |
| `live-series.txt` | a six-document batch: five PASS/OK, and the degraded scan "needs correction" |
| `masywny-stress.txt` | the 122-page report: 6 of 6 chapters, 338 s; this log is the run **before** the G13 tokenizer fix (46 facts, not all grounded); the later 48-of-48 run is recorded in IDEAS without a saved log |
| `opisywacz-live.txt` | image descriptions without a vision model: 4 images in 26 s; one description failed its grounding check and is marked so |
| `pageocr-stress.txt` | a 16-page all-scan report, three recorded attempts: the first crashed, the second and third found 7 chapters where the gold has 5; the gold-exact result in ARSENAL came with the fix in the same commit and its run was not saved (the suite checks only that a scanned heading is found through OCR) |
| `walker-live-proof.txt` | the chapter walker's live hops, 5 hops in 38 s |
| `e17-ctx-checkpoints.txt` | prompt-cache reuse across requests (6,897 of 7,413 tokens) with save and restore intact |
| `e6c-bench.txt`, `e19-ccd-pinning.txt`, `e22-nl-tuning.txt` | tuning of the 80B model, from before the single-model decision; history, not the shipped configuration |
| `e20-bulk-cacheram.txt` | the host-RAM prompt cache in parallel mode: no gain at 4 slots (170 s against 173 s) |

## Not measured

- Accuracy on real reports, because there is no gold.
- Timing on a 64 GB machine.
- Any platform other than Windows. Starting the model engine reads the machine's memory through a Windows API.
- Whether a fresh model run reproduces the same bytes. The suite proves only that sealing the same job twice gives the same seal; the ledger notes that parallel batching breaks byte-level replay.
- The chapter map and summaries inside the interactive conversation. That flow runs four stages (classification, header, coordinate list, verdict); the chapter map comes from the batch queue and the command line.
