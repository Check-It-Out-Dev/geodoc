# geodoc — generator ikon i brandingu instalatora (powtarzalny; commit
# artefaktów, ale ten skrypt jest źródłem prawdy). Ikona aplikacji =
# znacznik punktu osnowy z design-systemu (DESIGN-SYSTEM.md); branding
# kreatora = ten sam znacznik + nazwa produktu na panelu w kolorze
# atramentu. Uruchom: python tools/make_ikony.py
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BR = os.path.join(ROOT, "installer", "branding")
ATRAMENT = (24, 36, 48, 255)          # #182430
KARTA = (248, 250, 245, 255)          # #F8FAF5


def znacznik(size, fg=ATRAMENT, tlo=None):
    """Survey-marker mark: circle + crosshair + center dot, geometry from
    ui.html #znacznik, drawn at 4x and downsampled (crisp small sizes)."""
    S = size * 4
    im = Image.new("RGBA", (S, S), tlo or (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w = max(2, round(S * 0.055))                # stroke ~1.6/32 of viewbox
    c = S / 2
    r = S * 8.5 / 32
    d.ellipse([c - r, c - r, c + r, c + r], outline=fg, width=w)
    t0, t1 = S * 1.5 / 32, S * 8.5 / 32         # tick from edge to circle
    for a, b in [((c, t0), (c, t1)), ((c, S - t0), (c, S - t1)),
                 ((t0, c), (t1, c)), ((S - t0, c), (S - t1, c))]:
        d.line([a, b], fill=fg, width=w)
    rd = S * 1.6 / 32
    d.ellipse([c - rd, c - rd, c + rd, c + rd], fill=fg)
    return im.resize((size, size), Image.LANCZOS)


def ikona_ico():
    """Multi-size .ico: paper tile behind the mark below 48 px (legibility
    on dark taskbars), transparent above."""
    frames = []
    for s in (16, 24, 32, 48, 64, 128, 256):
        if s < 48:
            tile = Image.new("RGBA", (s, s), KARTA)
            m = znacznik(s)
            tile.alpha_composite(m)
            # 1px paper-edge rounding is noise at this size; keep square
            frames.append(tile)
        else:
            frames.append(znacznik(s))
    out = os.path.join(BR, "geodoc.ico")
    frames[-1].save(out, sizes=[(f.width, f.height) for f in frames],
                    append_images=frames[:-1])
    return out


def _font(sz, bold=False):
    for name in (("segoeuib.ttf",) if bold else ("segoeui.ttf",)):
        p = os.path.join(os.environ.get("WINDIR", r"C:\Windows"),
                         "Fonts", name)
        if os.path.isfile(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def panel_duzy(w, h, path):
    """WizardImageFile: the product's own panel — mark, wordmark, tagline on
    ink (the app's --atrament), paper-coloured strokes."""
    papier = tuple(KARTA[:3])
    im = Image.new("RGB", (w, h), tuple(ATRAMENT[:3]))
    d = ImageDraw.Draw(im)
    m = znacznik(int(w * 0.46), fg=KARTA)
    my = int(h * 0.20)
    im.paste(m, ((w - m.width) // 2, my), m)
    f1 = _font(max(14, int(w * 0.13)), bold=True)
    f2 = _font(max(9, int(w * 0.058)))
    y = my + m.height + int(h * 0.05)
    for t, f, kolor in (("geodoc", f1, papier),
                        ("kontrola operatów", f2, (176, 186, 196)),
                        ("technicznych", f2, (176, 186, 196))):
        bb = d.textbbox((0, 0), t, font=f)
        d.text(((w - (bb[2] - bb[0])) // 2, y), t, font=f, fill=kolor)
        y += (bb[3] - bb[1]) + int(h * 0.022)
    ry = int(h * 0.88)
    d.line([(int(w * 0.3), ry), (int(w * 0.7), ry)], fill=(90, 102, 114), width=1)
    im.save(path, "BMP")


def panel_maly(w, h, path):
    """WizardSmallImageFile: the geodoc mark on paper (header slot)."""
    im = Image.new("RGB", (w, h), tuple(KARTA[:3]))
    m = znacznik(min(w, h) - 8)
    im.paste(m, ((w - m.width) // 2, (h - m.height) // 2), m)
    im.save(path, "BMP")


def main():
    os.makedirs(BR, exist_ok=True)
    print("ico:", ikona_ico())
    # multi-DPI — sizes per Inno 6.6 docs (badanie 06.08: 100% = 202x386 /
    # 58x58, NIE klasyczne 164x314); wildcard w iss wybiera najblizszy
    for proc, (w, h), (sw, sh) in [
            (100, (202, 386), (58, 58)), (125, (269, 515), (77, 77)),
            (150, (336, 643), (97, 97)), (175, (403, 772), (116, 116)),
            (200, (430, 824), (124, 124)), (225, (430, 824), (143, 143)),
            (250, (534, 1022), (159, 159))]:
        panel_duzy(w, h, os.path.join(BR, f"kreator-{proc}.bmp"))
        panel_maly(sw, sh, os.path.join(BR, f"kreator-maly-{proc}.bmp"))
        print(f"panele {proc}%: {w}x{h} + {sw}x{sh}")


if __name__ == "__main__":
    main()
