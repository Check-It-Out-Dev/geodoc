# DESIGN-SYSTEM — geodoc UI (06.08, "archaism in a modern design")

Method: 2 research reconnaissances (world trends + branding psychology) →
a panel of 3 Fable agents, each with a FULL system for a different direction →
the judge's verdict (the main agent) → one merged system → implementation.
The prompting recipe is preserved as a separate design agent.

## 1. Research — what was established (CONFIRMED, sources in the task transcripts)

- **A light paper theme wins for data screens.** NN/g: positive
  polarity (dark-on-light) gives better sharpness and proofreading, and the advantage
  GROWS the smaller the text — small coordinate tables are the worst
  case for dark mode. The current dark shell is additionally the default "AI look
  #2" (near-black + one garish accent), which we are escaping.
- **2025-26 currents aligned with the owner's direction**: blueprint/technical-
  drawing revival; "heritage etch" (engraving); skeuomorphic minimalism
  (tactility as a counter to AI smoothness); B2B editorial à la Mercury
  (monochrome + one accent). Archaism = a concrete cultural anchor,
  not adjectives.
- **Typography**: Półtawski Nowy (OFL, on Google Fonts since 2023) — a revival
  of Antykwa Półtawskiego from 1928, the FIRST complete Polish typeface;
  national heritage as a functional choice. IBM Plex Sans (OFL,
  IBM's drafting lineage, full Polish diacritics) for UI/data. JetBrains Mono for
  coordinates. Everything self-hosted WOFF2 latin+latin-ext (the offline law).
- **How to prompt Fable for UI** (Anthropic frontend-aesthetics cookbook +
  the frontend-design skill): name the default looks and FORBID them; tokens BEFORE
  screens; 4 axes separately (typography/colour/motion/backgrounds); demand extremes
  (100↔800, jumps of 3×+, display+mono); a named cultural anchor; one
  dominant colour + a sharp accent; motion = one orchestrated moment;
  an anti-default self-critique loop. Full recipe: the `FableUIDesigner` agent.

## 2. The panel — three directions and the verdict

| Direction | Thesis | Best contribution (adopted) |
|---|---|---|
| SEAL (bureau editorial) | the screen = an official form | **The seal-rarity law**: a round seal ONLY where verification was reproduced; its absence = a message. Chat as protocol, log as tape on paper |
| GRID (cadastre) | UI in the grammar of the base map | **A hierarchy of line weights** (0.13/0.25/0.50 → 1/2/3 px) as the border system; the real PL-2000 extent as an ornament-instrument; confidence hatching (redundant encoding) |
| REGISTER (tactile document) | the *operat* (surveying report filed with the county) as a physical object | **STAMP IMPRESSION**: one shared SVG filter (feTurbulence+displacement) wobbles the stamp ring — text is NEVER filtered; "stamps mark verdicts, never affordances"; letterpress press-down |

Independent convergences (high confidence): cool light paper ×3 rejected
warm cream; Półtawski display + Plex body ×3 with THE SAME argument
("Półtawski owns the serif voice"); tables without zebra stripes — ledger
lines; square chips, not pills; red EXCLUSIVELY for KRYTYCZNE (critical);
a light log; the stamp as the only moment of motion.

**The merge verdict** (courage spent in ONE place): the signature is the
seal — SEAL's rarity × REGISTER's IMPRESSION rendering × the stamp's motion; around it
the calm line-weight grid of GRID on the paper of a field computation book.
The accent ink is **violet** — the historically true Polish stamp-pad
ink (not the "B2B-safe" blue); this is the one risky aesthetic
decision taken.

## 3. Tokens (law — implementation exclusively through these variables)

| Token | Hex | Role | Contrast (computed) |
|---|---|---|---|
| `--blat` | `#E8ECE2` | application background — cool field-book paper | — |
| `--karta` | `#F8FAF5` | sheets/cards/tables | — |
| `--atrament` | `#182430` | ALL content and data text | 14.98:1 on card |
| `--olowek` | `#49585F` | labels, secondary | 7.03:1 |
| `--tusz` | `#4B3A86` | seal, links, active, buttons | 8.89:1 |
| `--karmin` | `#A0182B` | EXCLUSIVELY KRYTYCZNE/FAIL/errors | 6.3:1 on tint |
| `--linia` | `#C6CFBE` | lines, never text | — |

Confidence (text on tint, computed): PEWNE (certain) `#1E6B40`/`#E3EEE3` (5.45:1) ·
SPRAWDŹ (check) `#7A5000`/`#F4EAD2` (5.90:1) · KRYTYCZNE (critical) `#A0182B`/`#F7E4E0`
(6.29:1). Excel stays at C6EFCE/FFEB9C/FFC7CE (operator habit).

Typography: Półtawski Nowy 700 — screen title 2.75rem, card titles
1.0625rem; Plex Sans 400 body 0.9375rem, 600 caps labels 0.6875rem
(+0.08em); JetBrains Mono 400 data 0.8125rem (slashed zero, tabular),
800 counters 2.5rem; Plex 100 ghost digits 8rem (empty state). Extremes:
weights 100↔800, jump 11→44 px. `tabular-nums` on Plex digits.

Lines: `--w1:1px` (rows, card edges) · `--w2:2px` (table headers,
secondary accent) · `--w3:3px` (active edge, selection). Radius 2-3 px.
Shadow only on overlays. No textures under data text.

## 4. Signature — seal/stamp impression

- **Round seal** (SVG, double ring, text around the circle „ZWERYFIKOWANO ·
  GEODOC" (verified · geodoc), the seal's short sha in the centre), rotated −3°, ink 0.88, ring
  through a feTurbulence(0.9)+feDisplacementMap(1.6) filter. It appears ONLY on:
  the *operat* header with KONTROLE:PASS (64 px) · supervised-mode acceptance ·
  the morning-report footer. NEVER on: pending/FAIL states (a flat carmine
  badge — the absence of the seal is the message), buttons, rows.
- **Rectangular stamp impression** (the same filter, chip with 2 px radius, wobbling
  1.5 px ring, flat tint, text unfiltered): the verdict class — confidence,
  point lineage =/ZM/N, PASS/FAIL, queue statuses. Affordances flat.
- **Motion** (the only orchestrated one): stamp 90 ms scale 1.15→1 + 40 ms +
  160 ms tint bloom, once per verdict. Evidence in the lightbox: the rect draws
  itself once in 240 ms and holds (the end of the eternal pulse). Hover ≤120 ms.
  `prefers-reduced-motion`: everything instant.

## 5. Components (laws in brief)

Tables: 1 px horizontal lines instead of zebra stripes; a double vertical line after
the ID column (ledger convention); header under a 2 px line; flat hover
`#EFF3EA`; evidence cells with a dotted underline; above the coordinate list
a marginal extent line with REAL PL-2000 coordinates (GRID's ornament-
instrument). Cards: a card on the desk, 1 px line, title as a
folder tab overlapping the top edge. Left drawer `#DFE4D8`,
active job = 3 px ink edge. Chat: correspondence blocks with a
speaker rubric (OPERATOR in tusz / GEODOC in atrament), not bubbles. Log: paper tape,
mono 12 px, perforated left edge, pencil timestamps, carmine errors.
Buttons: primary flat ink; secondary outlined; press-down 1 px.
Overlays: tracing paper — atrament 55%.

## 6. The logotype law (brand-psychology research, sources in the task)

**The product carries the maker's mark; the documents carry the user's mark.** Resolved
against white-label: the user's ownership effect is served by the profile + „Pracownia:
[firma]" (Office: [firm]) in the chrome (without forking the product); source credibility and the referral
loop (the Calendly pattern, ~25% of sign-ups from the badge; the printer's mark/colophon)
require a visible tool brand; the vertical-industry norm (C-GEO: a branded tool,
templates with room for the FIRM's logo) and **the law** (regulation of 18.08.2020:
the *operat* carries the contractor's identity) settle the outgoing artefacts.

| Surface | Mark |
|---|---|
| Chrome/tray/header | geodoc seal (brand = verification semantics) |
| Header, right corner | „Pracownia: [firma]" (Office: [firm]) from `profiles/firma.json` |
| Excel/reports | print footer: the user's firm on the left (dominant), „wygenerowano w geodoc" (generated in geodoc) small on the right |
| Upload CSV | NO branding (data = data, the operator's format law) |

## 7. Technical substrate

Fonts: `app/czcionki/` — 22 WOFF2 (latin+latin-ext, Polish diacritics tested),
683 KB, OFL; route `/czcionki/` (path-scoped like `/file/`). `fonty.css`
with unicode-range — the browser picks the subset per glyph. Zero CDN.
Test contract: every `data-testid` preserved to the character. The suite does not
assert ui.html content — the restyle does not touch the JS logic.
