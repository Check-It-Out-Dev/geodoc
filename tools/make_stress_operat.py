# geodoc stress fixtures — the CHAPTERED long document family (owner spec
# 06.08): a 16-page operat with a real chapter structure, TOC page, embedded
# raster MAPS (JPG) and photos, plus two adversarial twins:
#   operat_chaptered.pdf  — TOC + 5 numbered chapters + 2 maps + 2 photos
#   operat_incomplete.pdf — NO TOC and chapter 4 MISSING (numbering jumps 3->5)
#   operat_pageocr.pdf    — the chaptered doc rendered page-per-page at 200 dpi
#                           (every page is a scan; the heavy-OCR reality)
# Gold: testdata/gold_stress.json — chapter boundaries, names, media pages,
# wykaz counts per variant. Seeded; the referee is code.
#
# Usage: python tools/make_stress_operat.py

import io
import json
import os
import random

import fitz

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "testdata")
SEED = 20260806
TERYT = "146301_1.0012.AR_3.152/4"


def gen_points(rng, n=9, cx=5_571_240.0, cy=6_553_180.0):
    import math
    pts = []
    for i in range(n):
        ang = 2 * math.pi * i / n
        r = rng.uniform(38, 62)
        pts.append((f"152.4-{i + 1:02d}",
                    round(cx + r * math.sin(ang), 2),
                    round(cy + r * math.cos(ang), 2),
                    "nowy" if i < 3 else "bez_zmian"))
    return pts


def make_map_jpg(rng, label):
    """A synthetic surveying map as JPG bytes (PIL via rapidocr's Pillow):
    parcel polygon, point marks, north arrow, scale bar, label."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (900, 620), "white")
    d = ImageDraw.Draw(img)
    poly = [(rng.randint(140, 760), rng.randint(120, 500)) for _ in range(5)]
    cx = sum(p[0] for p in poly) // 5
    cy = sum(p[1] for p in poly) // 5
    import math
    poly.sort(key=lambda p: math.atan2(p[1] - cy, p[0] - cx))
    d.polygon(poly, outline="black", width=3)
    for i, (x, y) in enumerate(poly, 1):
        d.ellipse((x - 5, y - 5, x + 5, y + 5), fill="black")
        d.text((x + 8, y - 6), f"{i}", fill="black")
    d.line((830, 80, 830, 30), fill="black", width=3)
    d.polygon([(830, 20), (822, 40), (838, 40)], fill="black")
    d.text((846, 24), "N", fill="black")
    d.line((60, 580, 260, 580), fill="black", width=4)
    d.text((60, 556), "0        50       100 m", fill="black")
    d.text((60, 30), label, fill="black")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return buf.getvalue()


def make_photo_jpg(rng, caption):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (640, 420),
                    (rng.randint(90, 140), rng.randint(110, 150),
                     rng.randint(90, 120)))
    d = ImageDraw.Draw(img)
    d.rectangle((250, 210, 300, 330), fill=(200, 200, 190))   # the marker post
    d.polygon([(0, 420), (640, 420), (640, 330), (0, 360)],
              fill=(70, 90, 60))
    d.text((16, 12), caption, fill="white")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


CHAPTERS = [
    ("1. SPRAWOZDANIE TECHNICZNE", 3, 5),
    ("2. SZKICE I MAPY", 6, 8),
    ("3. WYKAZ WSPOLRZEDNYCH PUNKTOW GRANICZNYCH", 9, 11),
    ("4. PROTOKOLY GRANICZNE", 12, 13),
    ("5. DOKUMENTY KONCOWE", 14, 16),
]


def build(doc_path, with_toc=True, drop_chapter4=False, rng=None,
          toc_shift=0, toc_rogue=False, foreign_after=None, chapters_def=None,
          pages_per=None):
    rng = rng or random.Random(SEED)
    doc = fitz.open()
    W, H = fitz.paper_size("a4")
    media = {"mapy": [], "zdjecia": []}
    folio = [0]

    def page(heading=None, hsize=16):
        p = doc.new_page(width=W, height=H)
        folio[0] += 1
        p.insert_text((W / 2 - 14, H - 30), f"str. {folio[0]}", fontsize=9)
        if heading:
            p.insert_text((56, 64), heading, fontsize=hsize, fontname="hebo")
        return p

    def body(p, lines, y=110):
        for i, ln in enumerate(lines):
            p.insert_text((56, y + 16 * i), ln, fontsize=10)

    chapters = [c for c in (chapters_def or CHAPTERS)
                if not (drop_chapter4 and c[0].startswith("4."))]
    if pages_per:          # masywny: stretch every chapter to N pages
        stretched, cur = [], 3
        for name, _, _ in chapters:
            stretched.append((name, cur, cur + pages_per - 1))
            cur += pages_per
        chapters = stretched
    placed = []            # ACTUAL (name, od, do) as generation lays pages out
    foreign_page = [None]
    pts_extra = []         # masywny: additional wykaz sheets beyond the first

    # page 1 — title
    p = page()
    p.insert_text((56, 96), "OPERAT TECHNICZNY", fontsize=22, fontname="hebo")
    body(p, ["Cel pracy: podzial nieruchomosci",
             "Identyfikator zgloszenia: GK.6640.7777.2026",
             "Dzialka ewidencyjna: " + TERYT,
             "Uklad wspolrzednych: PL-2000/6",
             "Wykonawca: GEO-PRO Sp. z o.o., upr. 21987",
             "Data pomiaru: 2026-06-11",
             "Data sporzadzenia: 2026-07-30"], y=140)

    # page 2 — TOC (or filler page when the TOC is deliberately absent).
    # toc_shift simulates a STALE spis (uniform page drift after re-scan);
    # toc_rogue corrupts one entry against the shift (breaks monotonicity)
    p = page("SPIS TRESCI" if with_toc else None, hsize=16)
    if with_toc:
        rows = []
        for i, (name, a, b) in enumerate(chapters):
            declared = a - toc_shift
            if toc_rogue and i == 2:
                declared = 2          # rogue: points into the front matter
            rows.append(f"{name}  .....................  str. {declared}")
        body(p, rows, y=120)
    else:
        body(p, ["(strona informacyjna — dokument bez spisu tresci)"], y=120)

    pts = gen_points(rng)

    for name, a, b in chapters:
        n_pages = b - a + 1
        start = folio[0] + 1
        hidden = name.startswith("_")     # krotki: content WITHOUT a heading
        bname = name.lstrip("_")
        for k in range(n_pages):
            if k == 0 and not hidden:
                p = page(bname, hsize=15)
            else:
                p = page()
            name = bname
            if name.startswith("1."):
                body(p, [f"Sprawozdanie — czesc {k + 1}.",
                         "Prace wykonano zgodnie ze zgloszeniem.",
                         "Osnowe nawiazano do punktow panstwowych.",
                         "Pomiar RTK, sredni blad 0.02 m."], y=120)
            elif name.startswith("2."):
                if k < 2:
                    jpg = make_map_jpg(rng, f"MAPA {k + 1} — szkic granic "
                                            f"dzialki {TERYT}")
                    p.insert_image(fitz.Rect(56, 110, 540, 440), stream=jpg)
                    p.insert_text((56, 460), f"Mapa {k + 1}: szkic przebiegu "
                                             "granic (zalacznik graficzny)",
                                  fontsize=9)
                    media["mapy"].append(folio[0])
                elif k > 2:
                    body(p, [f"Opis szkicow — czesc {k - 1}."], y=120)
                else:
                    jpg = make_photo_jpg(rng, "Fot. 1 — znak graniczny")
                    p.insert_image(fitz.Rect(120, 110, 470, 350), stream=jpg)
                    jpg2 = make_photo_jpg(rng, "Fot. 2 — stabilizacja")
                    p.insert_image(fitz.Rect(120, 380, 470, 620), stream=jpg2)
                    p.insert_text((120, 360), "Fot. 1 — znak graniczny nr 152.4-01",
                                  fontsize=9)
                    p.insert_text((120, 630), "Fot. 2 — stabilizacja punktu",
                                  fontsize=9)
                    media["zdjecia"].append(folio[0])
            elif name.startswith("3."):
                n_tables = 4 if pages_per else 1
                if k < n_tables:
                    pts_k = pts if k == 0 else gen_points(
                        rng, 9, cx=5_571_240.0 + 300 * k,
                        cy=6_553_180.0 + 300 * k)
                    if k > 0:
                        pts_k = [(f"15{k}.4-{i + 1:02d}", x, y, st)
                                 for i, (_, x, y, st) in enumerate(pts_k)]
                        pts_extra.extend(pts_k)
                    body(p, ["Wykaz wspolrzednych punktow granicznych"
                             + (f" — arkusz {k + 1}" if n_tables > 1 else ""),
                             "Uklad: PL-2000 strefa 6. Liczba punktow: 9"],
                         y=100)
                    hdr = "ID punktu      X [m]         Y [m]        ZRD BPP STB RZG  Status"
                    p.insert_text((56, 150), hdr, fontsize=9, fontname="cobo")
                    for i, (pid, x, y, st) in enumerate(pts_k):
                        row = (f"{pid}   {x:.2f}   {y:.2f}    1   1   3   1   {st}")
                        p.insert_text((56, 168 + 14 * i), row, fontsize=9,
                                      fontname="cobo")
                else:
                    body(p, [f"Wykaz — kontynuacja, czesc {k + 1} (uwagi)."],
                         y=120)
            elif name.startswith("4."):
                body(p, [f"Protokol graniczny nr {k + 1}/2026.",
                         "Strony zawiadomiono skutecznie.",
                         "Granice okazano bez sporu."], y=120)
            else:
                body(p, [f"Dokumenty koncowe — czesc {k + 1}.",
                         "Operat sklada sie do PZGiK.",
                         "Zawiadomienie o zakonczeniu prac."], y=120)
            if foreign_after and folio[0] == foreign_after:
                # CONTAMINATION: a stray page from another document world
                fp = page("FAKTURA VAT 113/2026", hsize=14)
                body(fp, ["Sprzedawca: Hurtownia Materialow Sp. z o.o.",
                          "Nabywca: (strona obca wpieta do operatu)",
                          "Pozycja 1: paliki drewniane, 500 szt.",
                          "Razem brutto: 1 845,00 zl"], y=120)
                foreign_page[0] = folio[0]
        placed.append(dict(nazwa=name, od=start, do=folio[0]))

    doc.save(doc_path)
    doc.close()
    return dict(chapters=placed, media=media,
                punkty=len(pts) + len(pts_extra), toc=with_toc,
                pages=folio[0], toc_shift=toc_shift,
                strona_obca=foreign_page[0])


def main():
    os.makedirs(OUT, exist_ok=True)
    rng = random.Random(SEED)

    gold = {}
    gold["operat_chaptered"] = build(
        os.path.join(OUT, "operat_chaptered.pdf"), with_toc=True, rng=rng)
    gold["operat_incomplete"] = build(
        os.path.join(OUT, "operat_incomplete.pdf"), with_toc=False,
        drop_chapter4=True, rng=random.Random(SEED + 1))

    # heavy-OCR twin: every page of the chaptered doc becomes a 200 dpi scan
    src = fitz.open(os.path.join(OUT, "operat_chaptered.pdf"))
    scan = fitz.open()
    for pg in src:
        # JPEG stream, not raw pixmap — raw inflated the fixture to 185 MB
        jpg = pg.get_pixmap(dpi=200).tobytes("jpeg", jpg_quality=80)
        p = scan.new_page(width=pg.rect.width, height=pg.rect.height)
        p.insert_image(pg.rect, stream=jpg)
    scan.save(os.path.join(OUT, "operat_pageocr.pdf"))
    scan.close()
    src.close()
    gold["operat_pageocr"] = dict(gold["operat_chaptered"], all_scan=True)

    # LYING TOC: stale spis (uniform -2 drift) + one rogue entry
    gold["operat_toc_klamie"] = build(
        os.path.join(OUT, "operat_toc_klamie.pdf"), with_toc=True,
        toc_shift=2, toc_rogue=True, rng=random.Random(SEED + 2))

    # CONTAMINATION: a foreign invoice page inside chapter 3
    gold["operat_obcy"] = build(
        os.path.join(OUT, "operat_obcy.pdf"), with_toc=True,
        foreign_after=10, rng=random.Random(SEED + 3))

    # KROTKI degenerate: 3 pages, zero headings — the no-anchor path
    gold["operat_krotki"] = build(
        os.path.join(OUT, "operat_krotki.pdf"), with_toc=False,
        chapters_def=[("_3. WYKAZ", 3, 3)], rng=random.Random(SEED + 4))

    # MASYWNY: 6 chapters x 20 pages = 122 pages, 4 wykaz sheets (36 pts)
    gold["operat_masywny"] = build(
        os.path.join(OUT, "operat_masywny.pdf"), with_toc=True,
        chapters_def=CHAPTERS + [("6. ZALACZNIKI I KOPIE", 0, 0)],
        pages_per=20, rng=random.Random(SEED + 5))

    # MASYWNY-SCAN: first 40 pages of masywny at 150 dpi
    src = fitz.open(os.path.join(OUT, "operat_masywny.pdf"))
    scan = fitz.open()
    for pg in list(src)[:40]:
        jpg = pg.get_pixmap(dpi=150).tobytes("jpeg", jpg_quality=75)
        p = scan.new_page(width=pg.rect.width, height=pg.rect.height)
        p.insert_image(pg.rect, stream=jpg)
    scan.save(os.path.join(OUT, "operat_masywny_scan.pdf"))
    scan.close()
    src.close()
    gold["operat_masywny_scan"] = dict(pages=40, all_scan=True,
                                       zrodlo="operat_masywny s. 1-40")

    # SPLIT: each logical page as TWO pdf pages (top/bottom half-scans);
    # folio 'str. N' lives at the bottom -> only bottom halves carry it
    src = fitz.open(os.path.join(OUT, "operat_chaptered.pdf"))
    split = fitz.open()
    for pg in src:
        w, h = pg.rect.width, pg.rect.height
        halves = (fitz.Rect(0, 0, w, h / 2), fitz.Rect(0, h / 2, w, h))
        for clip in halves:
            jpg = pg.get_pixmap(dpi=150, clip=clip).tobytes(
                "jpeg", jpg_quality=75)
            p = split.new_page(width=w, height=h / 2)
            p.insert_image(fitz.Rect(0, 0, w, h / 2), stream=jpg)
    split.save(os.path.join(OUT, "operat_split.pdf"))
    split.close()
    src.close()
    gold["operat_split"] = dict(pages=32, all_scan=True,
                                logiczne_strony=16,
                                zrodlo="operat_chaptered, polowki gora/dol")

    with open(os.path.join(OUT, "gold_stress.json"), "w",
              encoding="utf-8") as f:
        json.dump(gold, f, ensure_ascii=False, indent=1)
    for k, v in gold.items():
        print(k, "->", v["pages"], "pages,",
              len(v.get("chapters") or []), "chapters, toc:", v.get("toc"))


if __name__ == "__main__":
    main()
