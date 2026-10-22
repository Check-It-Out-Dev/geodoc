# geodoc test data — a SYNTHETIC operat techniczny with a seeded gold.
# The referee is code: every number in testdata/gold.json is the number the
# pipeline must reproduce, to the centimetre. Layout mimics the real thing
# (rozp. Dz.U. 2020 poz. 1429): title page -> sprawozdanie -> wykaz współrzędnych
# (the load-bearing table) -> wykaz zmian -> szkic page (DRAWN, no text layer —
# exercises the raster/OCR branch detection).
#
# Coordinates: PL-2000 zone 6 (EPSG:2177-ish ranges): X (northing) ~5.57M,
# Y (easting, zone prefix 6) ~6.55M. Parcel = closed polygon, area via shoelace.
#
# Usage: python tools/make_test_operat.py   -> testdata/operat_sample.pdf + gold.json

import json
import os
import random

import fitz

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "testdata")

SEED = 20260729
TERYT = "146301_1.0012.AR_3.152/4"  # jedn.ewid TERYT . obręb . arkusz . nr działki
TERYT_NEW = ["146301_1.0012.AR_3.152/7", "146301_1.0012.AR_3.152/8"]
ZRD, STB, RZG = "1", "3", "1"  # urzędowe słowniki (ZRD 1-9, STB 1-4, RZG 1-7)
BPP = "1"


def gen_points(rng, n=9):
    """Closed-ish parcel ring around a centre; returns [(id, X, Y, 'nowy'|...)]."""
    cx, cy = 5_571_240.0, 6_553_180.0
    pts = []
    import math
    for i in range(n):
        ang = 2 * math.pi * i / n
        r = rng.uniform(38, 62)
        x = round(cx + r * math.sin(ang), 2)
        y = round(cy + r * math.cos(ang), 2)
        status = "nowy" if i in (2, 3, 4) else ("zmieniony" if i == 5 else "bez_zmian")
        pts.append((f"152.4-{i + 1:02d}", x, y, status))
    return pts


def shoelace(pts):
    n = len(pts)
    s = 0.0
    for i in range(n):
        x1, y1 = pts[i][1], pts[i][2]
        x2, y2 = pts[(i + 1) % n][1], pts[(i + 1) % n][2]
        s += x1 * y2 - x2 * y1
    return round(abs(s) / 2.0, 1)


def main():
    rng = random.Random(SEED)
    pts = gen_points(rng)
    area = shoelace(pts)
    os.makedirs(OUT, exist_ok=True)

    doc = fitz.open()
    W, H = fitz.paper_size("a4")

    folio = [0]  # printed page number (folio) — feeds the gap detector

    def page(title=None):
        p = doc.new_page(width=W, height=H)
        if title:
            p.insert_text((56, 60), title, fontsize=14, fontname="hebo")
        folio[0] += 1
        p.insert_text((W / 2 - 14, H - 30), f"str. {folio[0]}", fontsize=9)
        return p

    # 1 — strona tytułowa
    p = page()
    p.insert_text((56, 90), "OPERAT TECHNICZNY", fontsize=22, fontname="hebo")
    for i, ln in enumerate([
        "Cel pracy: podzial nieruchomosci",
        "Identyfikator zgloszenia: GK.6640.1234.2026",
        "Dzialka ewidencyjna: " + TERYT,
        "Obreb: 0012 Jazgarzew, jedn. ewid.: 146301_1",
        "Uklad wspolrzednych: PL-2000 strefa 6 (poludnik 18E)",
        "Wykonawca: GEO-PRO Sp. z o.o.",
        "Kierownik pracy: mgr inz. Jan Przyklad, upr. nr 21987",
        "Data pomiaru: 2026-06-11    Data sporzadzenia: 2026-06-30",
    ]):
        p.insert_text((56, 150 + 22 * i), ln, fontsize=11)

    # 2 — sprawozdanie techniczne
    p = page("SPRAWOZDANIE TECHNICZNE")
    for i, ln in enumerate([
        "Pomiar wykonano metoda RTK GNSS w nawiazaniu do ASG-EUPOS.",
        "Podzial dzialki 152/4 na dzialki 152/7 oraz 152/8.",
        "Wspolrzedne punktow granicznych wyznaczono w ukladzie PL-2000/6.",
        "Bledy srednie polozenia punktow nie przekraczaja 0.10 m (BPP=1).",
        "Punkty 03-05 zastabilizowano znakami naziemnymi (STB=3).",
        "Wykaz wspolrzednych zamieszczono na str. 3, szkic na str. 5.",
    ]):
        p.insert_text((56, 100 + 20 * i), ln, fontsize=11)

    # 3 — WYKAZ WSPOLRZEDNYCH (the table the pipeline must reproduce exactly)
    p = page("WYKAZ WSPOLRZEDNYCH PUNKTOW GRANICZNYCH")
    p.insert_text((56, 92), "Uklad: PL-2000 strefa 6    Dzialka: " + TERYT, fontsize=10)
    hdr = f"{'Nr punktu':<12}{'X [m]':>14}{'Y [m]':>14}  ZRD BPP STB RZG  Status"
    p.insert_text((56, 120), hdr, fontsize=10, fontname="cour")
    for i, (pid, x, y, st) in enumerate(pts):
        row = f"{pid:<12}{x:>14.2f}{y:>14.2f}  {ZRD:>3} {BPP:>3} {STB:>3} {RZG:>3}  {st}"
        p.insert_text((56, 140 + 16 * i), row, fontsize=10, fontname="cour")
    p.insert_text((56, 140 + 16 * len(pts) + 12),
                  f"Liczba punktow: {len(pts)}    Pole obliczone: {area} m2",
                  fontsize=10, fontname="cour")

    # 4 — wykaz zmian danych ewidencyjnych
    p = page("WYKAZ ZMIAN DANYCH EWIDENCYJNYCH")
    for i, ln in enumerate([
        "Stan dotychczasowy: dzialka 152/4, pole 0.4306 ha",
        f"Stan nowy: dzialka 152/7 (pole {area / 2 / 10000:.4f} ha),",
        f"           dzialka 152/8 (pole {area / 2 / 10000:.4f} ha)",
        "Rodzaj aktu: decyzja zatwierdzajaca podzial",
    ]):
        p.insert_text((56, 100 + 22 * i), ln, fontsize=11)

    # 5 — szkic as a TRUE RASTER page (image-only, like a scan): drawn on a
    # scratch page, rasterized, re-inserted as a full-page image. No text layer
    # AND real image coverage — exercises both detectors of the document map.
    scratch = fitz.open()
    sp = scratch.new_page(width=W, height=H)
    cx, cy, k = 300, 420, 2.2
    ring = [fitz.Point(cx + (pt[2] - 6_553_180.0) * k, cy - (pt[1] - 5_571_240.0) * k)
            for pt in pts]
    for a, b in zip(ring, ring[1:] + ring[:1]):
        sp.draw_line(a, b, color=(0, 0, 0), width=1.2)
    for pt_geo, pt_pix in zip(pts, ring):
        sp.draw_circle(pt_pix, 3, color=(0.8, 0.1, 0.1), fill=(0.8, 0.1, 0.1))
    pix = sp.get_pixmap(dpi=150)
    scratch.close()
    p = doc.new_page(width=W, height=H)
    p.insert_image(p.rect, pixmap=pix)

    pdf_path = os.path.join(OUT, "operat_sample.pdf")
    doc.save(pdf_path)

    # the SCAN twin: every page rasterized (200 dpi) — zero text layer, same
    # gold; exercises the full OCR->LLM->gates path ("operat = plik skanów")
    scan = fitz.open()
    src = fitz.open(pdf_path)
    for page in src:
        pix = page.get_pixmap(dpi=200)
        sp = scan.new_page(width=W, height=H)
        sp.insert_image(sp.rect, pixmap=pix)
    src.close()
    scan_path = os.path.join(OUT, "operat_scan.pdf")
    scan.save(scan_path)
    scan.close()
    doc.close()

    gold = dict(
        seed=SEED,
        cel_pracy="podzial nieruchomosci",
        id_zgloszenia="GK.6640.1234.2026",
        dzialka=TERYT, dzialki_nowe=TERYT_NEW,
        uklad="PL-2000/6",
        wykonawca="GEO-PRO Sp. z o.o.", nr_uprawnien="21987",
        data_pomiaru="2026-06-11", data_sporzadzenia="2026-06-30",
        strona_wykazu=3, strona_szkicu=5,
        atrybuty=dict(ZRD=ZRD, BPP=BPP, STB=STB, RZG=RZG),
        punkty=[dict(id=pid, x=x, y=y, status=st) for pid, x, y, st in pts],
        liczba_punktow=len(pts), pole_m2=area,
        rodzaj_aktu="decyzja zatwierdzajaca podzial",
        strony_bez_tekstu=[5],
    )
    with open(os.path.join(OUT, "gold.json"), "w", encoding="utf-8") as f:
        json.dump(gold, f, ensure_ascii=False, indent=1)
    # the MULTI twin: 36 points split over FOUR wykaz pages — the bulk-
    # extraction fixture (parallel-slots throughput measurement, E13 design)
    rng2 = random.Random(SEED + 1)
    pts36 = gen_points(rng2, n=36)
    multi = fitz.open()
    mp = multi.new_page(width=W, height=H)
    mp.insert_text((56, 90), "OPERAT TECHNICZNY (MULTI)", fontsize=20,
                   fontname="hebo")
    for i, ln in enumerate([
        "Cel pracy: podzial nieruchomosci",
        "Identyfikator zgloszenia: GK.6640.9999.2026",
        "Dzialka ewidencyjna: " + TERYT,
        "Uklad wspolrzednych: PL-2000 strefa 6 (poludnik 18E)",
        "Wykonawca: GEO-PRO Sp. z o.o.",
    ]):
        mp.insert_text((56, 150 + 22 * i), ln, fontsize=11)
    for pg in range(4):
        p = multi.new_page(width=W, height=H)
        p.insert_text((56, 60), "WYKAZ WSPOLRZEDNYCH PUNKTOW GRANICZNYCH "
                      f"(czesc {pg + 1}/4)", fontsize=13, fontname="hebo")
        p.insert_text((56, 96), hdr, fontsize=10, fontname="cour")
        for i, (pid, x, y, st) in enumerate(pts36[pg * 9:(pg + 1) * 9]):
            row = (f"{pid:<12}{x:>14.2f}{y:>14.2f}  {ZRD:>3} {BPP:>3} "
                   f"{STB:>3} {RZG:>3}  {st}")
            p.insert_text((56, 120 + 16 * i), row, fontsize=10, fontname="cour")
    multi.save(os.path.join(OUT, "operat_multi.pdf"))
    multi.close()
    with open(os.path.join(OUT, "gold_multi.json"), "w", encoding="utf-8") as f:
        json.dump(dict(liczba_punktow=36,
                       punkty=[dict(id=pid, x=x, y=y)
                               for pid, x, y, _ in pts36]), f, indent=1)

    print(f"operat_sample.pdf + operat_scan.pdf + operat_multi.pdf: "
          f"{len(pts)} pts (+36 multi), area {area} m2; golds written")


if __name__ == "__main__":
    main()
