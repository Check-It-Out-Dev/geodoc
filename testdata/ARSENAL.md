# BATTLE ARSENAL — the full list of fixtures and measured behaviours (06.08)

Grid design per the recon (RoDLA 12×3, Real5, olmOCR-2 behavioral gold):
**structural adversaries × severity levels** (L0 text / L1 scan /
L2 heavy Augraphy degradation). Every fixture carries an expected BEHAVIOUR
(not just a metric) — seeded, sizes disciplined (JPEG streams).
Run evidence: `docs/bench/arsenal-sweep.txt`, `pageocr-stress.txt`,
`masywny-stress.txt`, the suite `tests/test_core.py`.

| Fixture | Adversary | Tier | Measured behaviour | Verdict |
|---|---|---|---|---|
| operat_sample (5 pp.) | base + 1 raster page, folio | L0 | 9/9 pts to-the-cm, PASS/OK 93–98 s | ✅ |
| operat_scan (5 pp.) | full scan of the base | L1 | 9/9 via OCR, PASS/DO_POPRAWY (honest scan flags) | ✅ |
| operat_multi (5 pp./36 pts) | 4 coordinate-list pages → bulk profile -np 4 | L0 | 36/36 to-the-cm, 1.39× wall; caught a routing bug (fixed b7cac79) | ✅ |
| operat_chaptered (16 pp.) | 5 chapters + table of contents + 2 maps + 2 photos | L0 | boundaries gold-exact; full wired run 220 s PASS/OK/33 facts | ✅ |
| operat_incomplete (14 pp.) | NO table of contents, chapter 4 REMOVED | L0 | 4 real chapters, numbering jump FLAGGED, nothing invented | ✅ |
| operat_pageocr (16 pp.) | EVERY page a scan | L1 | 5 chapters GOLD-EXACT with pure OCR (after the height-primary law + the anchor spine) | ✅ |
| operat_toc_klamie (16 pp.) | table of contents shifted −2 + a rogue entry | L0 | boundaries untouched; the rogue killed by monotonic legality, drift recovered spis_przesuniecie=2 | ✅ |
| operat_obcy (17 pp.) | a foreign invoice bound into chapter 3 | L0 | absorbed without breaking G11 tiling | ✅ |
| operat_krotki (3 pp.) | zero headings (degenerate) | L0 | zero chapters, everything unlabelled — abstention (taught a law: style without an anchor does not create structure) | ✅ |
| operat_masywny (122 pp.) | scale: 6 chapters × 20 pp., 4 coordinate-list sheets | L0 | 6/6 gold-exact; e2e 338 s; 48/48 facts grounded (the saved log `docs/bench/masywny-stress.txt` is a run from before the G13 tokenizer fix: 46 facts, ungrounded) | ✅ |
| operat_masywny_scan (40 pp.) | scale + 150 dpi scan | L1 | material for night-shift (batch queue) runs | ✅ (fixture) |
| operat_masywny_skan_pelny (122 pp.) | the WHOLE document scanned (4.4 MB) | L1 | arsenal for full OCR stress — for night batch runs | ✅ (fixture) |
| operat_split (32 pp.) | 1 logical page = 2 PDF pages (halves) | L1 | goes through the heavy page-by-page OCR path; pair reconstruction = a v1.1 row | ✅ (limit documented) |
| **operat_spread (8 pp.)** | **2 logical pages on 1 PDF page (2-up scan)** | L1 | chapters detected at PDF-page granularity (a heading on the right half folds into the neighbour); gutter splitter per the recon recipe = v1.1 | ✅ (limit documented) |
| **operat_bez_naglowkow (40 pp.)** | **zero headings and table of contents AT SCALE** | L0 | 0 candidates → 0 chapters → unlabelled [[1,40]], G11 green — abstention at scale works | ✅ |
| **operat_puste_dublety (19 pp.)** | **blank pages + a duplicate from a double feed** | L0 | found a gap: a duplicate of a heading page made a phantom chapter → DEFENCE page_pathologies (blank [5,12], duplicate [8→7], 5 real chapters) | ✅ (defence built) |
| **operat_mapy (12 pp.)** | **a document dominated by drawings (8 maps)** | L0 | 3 chapters matching the layout, 8/8 maps found by find_media | ✅ |
| **operat_mixed_dpi (16 pp.)** | **DPI 120/200/300 + different JPEG per page** | L1 | code-only: the heading on the 120 dpi page is lost (merge) → **THE CHAPTER WALKER RECOVERS: 5/5 gold-exact** — proof of the fusion's recovery layer | ✅ (recovery proven) |
| **operat_l2 (16 pp.)** | **Augraphy L2: skew, shadows, stains, hole punch, rollers, photocopy, moiré, JPEG 35–55** | **L2** | **structure survives: 5/5 chapters exact**; digits degrade to 7/9 in OCR — exactly the work for the G4 gates/review flags | ✅ (robustness measured) |

**Smoke subset** (fast regression): sample, chaptered, incomplete, krotki,
puste_dublety, mapy — all in the suite (`python tests/test_core.py`).
**Full LLM runs**: chaptered/pageocr/masywny/mixed_dpi — evidence in
docs/bench/. **Tools**: `tools/make_test_operat.py`,
`tools/make_stress_operat.py`, `tools/make_arsenal.py` (Augraphy: we use
Geometric, BindingsAndFasteners, Stains, DirtyRollers, ShadowCast,
BadPhotoCopy, SubtleNoise, Jpeg out of ~50 available; a catalogue of the relevant classes
per RoDLA in the recon).
