# geodoc — the BATTLE ARSENAL (owner goal 06.08 09:25: "full arsenal of
# various PDFs, focus only on this"). Extends the stress family with the
# adversaries the field actually produces:
#   operat_spread.pdf        — book-spread scan: TWO logical pages per ONE
#                              landscape PDF page (inverse of operat_split);
#                              both printed folios visible on each PDF page
#   operat_bez_naglowkow.pdf — 40 pages of continuous content, ZERO headings,
#                              ZERO TOC (abstention-at-scale probe)
#   operat_masywny_skan_pelny.pdf — ALL 122 masywny pages as 150 dpi scans
#   operat_puste_dublety.pdf — scanner pathologies: blank pages + double-feed
#                              duplicates injected into the chaptered doc
# Gold entries appended to testdata/gold_stress.json (arsenal section).
# Seeded; sizes disciplined (JPEG streams, never raw pixmaps).
#
# Usage: python tools/make_arsenal.py

import json
import os
import random

import fitz

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "testdata")
SEED = 20260806
TERYT = "146301_1.0012.AR_3.152/4"


def spread(src_path, dst_path, dpi=150, q=75):
    """Book-spread: pages (1,2), (3,4)... rendered side-by-side on ONE
    landscape PDF page each. Odd leftover page sits alone on the left."""
    src = fitz.open(src_path)
    dst = fitz.open()
    pairs = [(i, i + 1 if i + 1 < len(src) else None)
             for i in range(0, len(src), 2)]
    for a, b in pairs:
        pa = src[a]
        w, h = pa.rect.width, pa.rect.height
        page = dst.new_page(width=w * 2, height=h)
        page.insert_image(fitz.Rect(0, 0, w, h),
                          stream=pa.get_pixmap(dpi=dpi).tobytes(
                              "jpeg", jpg_quality=q))
        if b is not None:
            page.insert_image(fitz.Rect(w, 0, w * 2, h),
                              stream=src[b].get_pixmap(dpi=dpi).tobytes(
                                  "jpeg", jpg_quality=q))
    dst.save(dst_path)
    n_logical, n_pdf = len(src), len(dst)
    dst.close()
    src.close()
    return dict(pages=n_pdf, logiczne_strony=n_logical,
                zrodlo=os.path.basename(src_path),
                wlasciwosc="2 strony logiczne na 1 stronie PDF (skan 2-up)")


def bez_naglowkow(dst_path, n_pages=40, rng=None):
    """Continuous document with NO headings and NO TOC: prose paragraphs and
    small tables in one visual register (single font size). The honest
    expected output downstream: zero chapters, everything nieoznaczone."""
    rng = rng or random.Random(SEED)
    doc = fitz.open()
    W, H = fitz.paper_size("a4")
    for n in range(1, n_pages + 1):
        p = doc.new_page(width=W, height=H)
        y = 70
        for _ in range(rng.randint(3, 5)):
            for k in range(rng.randint(3, 6)):
                p.insert_text(
                    (56, y),
                    f"Czynnosci polowe kontynuowano dnia 2026-0{rng.randint(1,6)}-"
                    f"{rng.randint(10,28)}; pomierzono {rng.randint(2,9)} "
                    f"punktow osnowy, blad {rng.uniform(0.01,0.05):.3f} m.",
                    fontsize=10)
                y += 15
            y += 12
        p.insert_text((W / 2 - 14, H - 30), f"str. {n}", fontsize=9)
    doc.save(dst_path)
    doc.close()
    return dict(pages=n_pages, toc=False, naglowki=0,
                wlasciwosc="zero naglowkow i spisu — proba abstencji w skali")


def full_scan(src_path, dst_path, dpi=150, q=72):
    src = fitz.open(src_path)
    dst = fitz.open()
    for pg in src:
        p = dst.new_page(width=pg.rect.width, height=pg.rect.height)
        p.insert_image(pg.rect, stream=pg.get_pixmap(dpi=dpi).tobytes(
            "jpeg", jpg_quality=q))
    dst.save(dst_path)
    n = len(dst)
    dst.close()
    src.close()
    return dict(pages=n, all_scan=True, zrodlo=os.path.basename(src_path))


def puste_dublety(src_path, dst_path, rng=None):
    """Scanner pathologies: two blank pages injected + one double-feed
    duplicate (page scanned twice) — folio consensus must survive both."""
    rng = rng or random.Random(SEED + 7)
    src = fitz.open(src_path)
    dst = fitz.open()
    blank_after = {4, 9}
    dup_after = 6
    log = []
    for i, pg in enumerate(src, 1):
        dst.insert_pdf(src, from_page=i - 1, to_page=i - 1)
        if i == dup_after:
            dst.insert_pdf(src, from_page=i - 1, to_page=i - 1)
            log.append(f"dublet strony {i} po pozycji {len(dst)}")
        if i in blank_after:
            dst.new_page(width=pg.rect.width, height=pg.rect.height)
            log.append(f"pusta strona po logicznej {i}")
    dst.save(dst_path)
    n = len(dst)
    dst.close()
    src.close()
    return dict(pages=n, wstawki=log,
                wlasciwosc="puste strony + dublet z podwojnego poboru")


def mapy_heavy(dst_path, rng=None):
    """Map-heavy operat: 12 pages, 8 varied generated maps (grid styles,
    dashed boundaries, hatching, dense labels) + a wykaz page — the drawing-
    dominant document class (szkice polowe, mapy porownania)."""
    import io
    from PIL import Image, ImageDraw
    rng = rng or random.Random(SEED + 11)
    doc = fitz.open()
    W, H = fitz.paper_size("a4")

    def draw_map(style, label):
        img = Image.new("RGB", (900, 640), "white")
        d = ImageDraw.Draw(img)
        if style % 3 == 0:                     # siatka krzyzowa
            for x in range(60, 900, 120):
                for y in range(60, 640, 120):
                    d.line((x - 8, y, x + 8, y), fill="black")
                    d.line((x, y - 8, x, y + 8), fill="black")
        poly = [(rng.randint(120, 780), rng.randint(100, 540))
                for _ in range(rng.randint(4, 7))]
        cx = sum(p[0] for p in poly) // len(poly)
        cy = sum(p[1] for p in poly) // len(poly)
        import math
        poly.sort(key=lambda p: math.atan2(p[1] - cy, p[0] - cx))
        if style % 2 == 0:
            d.polygon(poly, outline="black", width=3)
        else:                                   # granica kreskowana
            pts = poly + [poly[0]]
            for a, b in zip(pts, pts[1:]):
                steps = 12
                for s in range(0, steps, 2):
                    x1 = a[0] + (b[0] - a[0]) * s / steps
                    y1 = a[1] + (b[1] - a[1]) * s / steps
                    x2 = a[0] + (b[0] - a[0]) * (s + 1) / steps
                    y2 = a[1] + (b[1] - a[1]) * (s + 1) / steps
                    d.line((x1, y1, x2, y2), fill="black", width=3)
        for i, (x, y) in enumerate(poly, 1):
            d.ellipse((x - 4, y - 4, x + 4, y + 4), fill="black")
            d.text((x + 6, y - 8), f"{100 + i}", fill="black")
        d.text((40, 20), label, fill="black")
        d.line((760, 90, 760, 40), fill="black", width=3)
        d.text((772, 44), "N", fill="black")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=86)
        return buf.getvalue()

    p = doc.new_page(width=W, height=H)
    p.insert_text((56, 90), "OPERAT TECHNICZNY — MAPY I SZKICE",
                  fontsize=20, fontname="hebo")
    p.insert_text((56, 130), "Identyfikator: GK.6640.8888.2026", fontsize=10)
    p.insert_text((W / 2 - 14, H - 30), "str. 1", fontsize=9)
    for i in range(8):
        p = doc.new_page(width=W, height=H)
        if i == 0:
            p.insert_text((56, 64), "1. SZKICE I MAPY", fontsize=15,
                          fontname="hebo")
        jpg = draw_map(i, f"SZKIC {i + 1} — obr. 0012, sekcja {i + 1}")
        p.insert_image(fitz.Rect(48, 100, 548, 460), stream=jpg)
        p.insert_text((48, 480), f"Szkic {i + 1}: pomiar sytuacyjny "
                                 f"granic, sekcja {i + 1}", fontsize=9)
        p.insert_text((W / 2 - 14, H - 30), f"str. {i + 2}", fontsize=9)
    p = doc.new_page(width=W, height=H)
    p.insert_text((56, 64), "2. WYKAZ WSPOLRZEDNYCH", fontsize=15,
                  fontname="hebo")
    p.insert_text((56, 100), "Uklad: PL-2000 strefa 6. Liczba punktow: 5",
                  fontsize=10)
    for i in range(5):
        p.insert_text((56, 140 + 14 * i),
                      f"200.{i + 1}   {5571000.00 + i * 25:.2f}   "
                      f"{6553000.00 + i * 25:.2f}    1   1   3   1   nowy",
                      fontsize=9, fontname="cobo")
    p.insert_text((W / 2 - 14, H - 30), "str. 10", fontsize=9)
    for extra in range(2):
        p = doc.new_page(width=W, height=H)
        p.insert_text((56, 64), "3. DOKUMENTY" if extra == 0 else None or "",
                      fontsize=15, fontname="hebo")
        p.insert_text((56, 110), "Zawiadomienia i zwrotki.", fontsize=10)
        p.insert_text((W / 2 - 14, H - 30), f"str. {11 + extra}", fontsize=9)
    doc.save(dst_path)
    n = len(doc)
    doc.close()
    return dict(pages=n, mapy=8,
                wlasciwosc="dokument zdominowany rysunkami (szkice)")


def mixed_dpi(src_path, dst_path, rng=None):
    """Scan twin with MIXED DPI per page (120/200/300) + varied JPEG quality
    — the municipal-archive reality of many scanning sessions."""
    rng = rng or random.Random(SEED + 13)
    src = fitz.open(src_path)
    dst = fitz.open()
    plan = []
    for pg in src:
        dpi = rng.choice([120, 200, 300])
        q = rng.choice([55, 72, 85])
        plan.append((dpi, q))
        p = dst.new_page(width=pg.rect.width, height=pg.rect.height)
        p.insert_image(pg.rect, stream=pg.get_pixmap(dpi=dpi).tobytes(
            "jpeg", jpg_quality=q))
    dst.save(dst_path)
    n = len(dst)
    dst.close()
    src.close()
    return dict(pages=n, all_scan=True, plan_dpi_q=plan[:6],
                wlasciwosc="mieszane DPI 120/200/300 + rozne jakosci JPEG")


def l2_degraded(src_path, dst_path, rng_seed=SEED + 17, pages_limit=None):
    """L2-HEAVY tier (RoDLA-informed): Augraphy stack per page — geometric
    skew, shadow, stains, punch holes, dirty rollers, bad photocopy, moire,
    jpeg — applied to rendered pages; the municipal-archive nightmare."""
    import numpy as np
    import cv2
    from augraphy import (AugraphyPipeline, Geometric, ShadowCast, Stains,
                          BindingsAndFasteners, DirtyRollers, BadPhotoCopy,
                          SubtleNoise, Jpeg)
    pipe = AugraphyPipeline(
        ink_phase=[],
        paper_phase=[
            Geometric(rotate_range=(-3, 3), p=1.0),
            BindingsAndFasteners(effect_type="punch_holes", ntimes=(2, 4),
                                 p=0.7),
            Stains(stains_type="severe_stains", p=0.6),
            DirtyRollers(line_width_range=(6, 12), p=0.5),
        ],
        post_phase=[
            ShadowCast(shadow_side="random", p=0.7),
            BadPhotoCopy(noise_type=2, p=0.5),
            SubtleNoise(subtle_range=25, p=1.0),
            Jpeg(quality_range=(35, 55), p=1.0),
        ])
    np.random.seed(rng_seed % (2 ** 31))
    src = fitz.open(src_path)
    dst = fitz.open()
    pages = list(src)[:pages_limit] if pages_limit else list(src)
    for pg in pages:
        pix = pg.get_pixmap(dpi=150)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, pix.n)
        if pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
        out = pipe(img)
        ok, enc = cv2.imencode(".jpg", out,
                               [cv2.IMWRITE_JPEG_QUALITY, 70])
        p = dst.new_page(width=pg.rect.width, height=pg.rect.height)
        p.insert_image(pg.rect, stream=enc.tobytes())
    dst.save(dst_path)
    n = len(dst)
    dst.close()
    src.close()
    return dict(pages=n, all_scan=True,
                wlasciwosc="L2-heavy: skos, cienie, plamy, dziurkacz, "
                           "walki, ksero, moire, jpeg 35-55")


def uklad_fixture(dst_path, uklad, cx, cy, decl=True, rng=None):
    """Mini-operat (4 pages) in a NON-PL-2000 coordinate system: title page
    declaring (or not) the uklad, a wykaz with 6 points at the system's
    coordinate magnitudes, filler. Probes detection + honest conversion or
    abstention downstream."""
    rng = rng or random.Random(SEED + 21)
    import math
    doc = fitz.open()
    W, H = fitz.paper_size("a4")
    p = doc.new_page(width=W, height=H)
    p.insert_text((56, 90), "OPERAT TECHNICZNY", fontsize=20, fontname="hebo")
    lines = ["Cel pracy: podzial nieruchomosci",
             "Identyfikator zgloszenia: GK.6640.9999.2026",
             "Dzialka ewidencyjna: " + TERYT]
    if decl:
        lines.append(f"Uklad wspolrzednych: {uklad}")
    lines += ["Wykonawca: GEO-PRO Sp. z o.o., upr. 21987",
              "Data pomiaru: 2000-05-11", "Data sporzadzenia: 2000-06-30"]
    for i, ln in enumerate(lines):
        p.insert_text((56, 140 + 16 * i), ln, fontsize=10)
    p.insert_text((W / 2 - 14, H - 30), "str. 1", fontsize=9)
    p = doc.new_page(width=W, height=H)
    p.insert_text((56, 64), "1. WYKAZ WSPOLRZEDNYCH", fontsize=15,
                  fontname="hebo")
    p.insert_text((56, 100), f"Uklad: {uklad if decl else '(nie podano)'}. "
                             "Liczba punktow: 6", fontsize=10)
    pts = []
    for i in range(6):
        ang = 2 * math.pi * i / 6
        r = rng.uniform(30, 55)
        x = round(cx + r * math.sin(ang), 2)
        y = round(cy + r * math.cos(ang), 2)
        pts.append((f"9.{i + 1}", x, y))
        p.insert_text((56, 140 + 14 * i),
                      f"9.{i + 1}   {x:.2f}   {y:.2f}    1   1   3   1   nowy",
                      fontsize=9, fontname="cobo")
    p.insert_text((W / 2 - 14, H - 30), "str. 2", fontsize=9)
    for n in (3, 4):
        p = doc.new_page(width=W, height=H)
        p.insert_text((56, 64), "2. DOKUMENTY" if n == 3 else "", fontsize=15,
                      fontname="hebo")
        p.insert_text((56, 110), "Zawiadomienia.", fontsize=10)
        p.insert_text((W / 2 - 14, H - 30), f"str. {n}", fontsize=9)
    doc.save(dst_path)
    doc.close()
    return dict(pages=4, uklad=uklad, deklarowany=decl,
                punkty=[dict(id=i, x=x, y=y) for i, x, y in pts])


def main():
    os.makedirs(OUT, exist_ok=True)
    gold_p = os.path.join(OUT, "gold_stress.json")
    gold = json.load(open(gold_p, encoding="utf-8")) \
        if os.path.isfile(gold_p) else {}

    gold["operat_spread"] = spread(
        os.path.join(OUT, "operat_chaptered.pdf"),
        os.path.join(OUT, "operat_spread.pdf"))
    gold["operat_bez_naglowkow"] = bez_naglowkow(
        os.path.join(OUT, "operat_bez_naglowkow.pdf"))
    gold["operat_masywny_skan_pelny"] = full_scan(
        os.path.join(OUT, "operat_masywny.pdf"),
        os.path.join(OUT, "operat_masywny_skan_pelny.pdf"))
    gold["operat_puste_dublety"] = puste_dublety(
        os.path.join(OUT, "operat_chaptered.pdf"),
        os.path.join(OUT, "operat_puste_dublety.pdf"))
    gold["operat_mapy"] = mapy_heavy(os.path.join(OUT, "operat_mapy.pdf"))
    gold["operat_mixed_dpi"] = mixed_dpi(
        os.path.join(OUT, "operat_chaptered.pdf"),
        os.path.join(OUT, "operat_mixed_dpi.pdf"))
    try:
        gold["operat_l2"] = l2_degraded(
            os.path.join(OUT, "operat_chaptered.pdf"),
            os.path.join(OUT, "operat_l2.pdf"))
    except Exception as e:                     # Augraphy API drift tolerated
        gold["operat_l2"] = dict(blad=str(e)[:200])
        print("L2 degradation failed:", e)

    # coordinate-system adversaries: 1992 (convertible, exact math),
    # 1965 strefa IV (detect + abstain), lokalny (detect + abstain),
    # 1992 UNDECLARED (magnitude-only detection)
    gold["operat_1992"] = uklad_fixture(
        os.path.join(OUT, "operat_1992.pdf"), "PUWG 1992",
        cx=486_757.0, cy=637_382.0)
    gold["operat_1965"] = uklad_fixture(
        os.path.join(OUT, "operat_1965.pdf"), "uklad 1965 strefa IV",
        cx=5_606_000.0, cy=3_706_000.0)
    gold["operat_lokalny"] = uklad_fixture(
        os.path.join(OUT, "operat_lokalny.pdf"),
        "uklad lokalny m. Przykladowo", cx=5_432.0, cy=8_765.0)
    gold["operat_1992_bez_deklaracji"] = uklad_fixture(
        os.path.join(OUT, "operat_1992_bez_deklaracji.pdf"), "PUWG 1992",
        cx=486_757.0, cy=637_382.0, decl=False)

    with open(gold_p, "w", encoding="utf-8") as f:
        json.dump(gold, f, ensure_ascii=False, indent=1)
    for k in ("operat_spread", "operat_bez_naglowkow",
              "operat_masywny_skan_pelny", "operat_puste_dublety"):
        print(k, "->", gold[k])


if __name__ == "__main__":
    main()
