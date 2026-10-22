# geodoc — układy współrzędnych (owner ask 06.08 09:48): detection of the
# systems archival operaty actually carry (PL-2000, PL-1992, układ 1965,
# układy lokalne, heights KRON86/EVRF2007) and RECALCULATION where the math
# is exact. LAWS:
#   - original coordinates are TRUTH and are never replaced — conversion adds
#     derived columns with method+accuracy provenance (pieczęć-friendly);
#   - exact math only for same-datum Gauss-Krüger pairs (1992<->2000,
#     2000 zone<->zone): inverse GK -> geodetic -> forward GK, sub-mm;
#   - 1965/local: DETECT and FLAG; parametric 1965 conversion only with the
#     accuracy caveat as a review flag (never silently exact); local systems
#     abstain until powiat profile carries parameters.
# Pure stdlib. GRS80 transverse-Mercator series (textbook Krüger expansion),
# verified by roundtrip < 1e-4 m across a Poland-wide grid in the suite.

import math

A = 6378137.0                      # GRS80 semi-major
F = 1.0 / 298.257222101
E2 = F * (2.0 - F)                 # first eccentricity squared
EP2 = E2 / (1.0 - E2)              # second eccentricity squared

# Karney/Krueger n-series (third flattening) — mm-exact far beyond the
# +/-5.5 deg PL-1992 needs; replaces the classic dl^4 series whose
# truncation cost 3.9 mm at Warszawa and metres at zone abuse
_N3 = F / (2.0 - F)
_N2 = _N3 * _N3
_N4 = _N2 * _N2
_AHAT = A / (1.0 + _N3) * (1.0 + _N2 / 4.0 + _N4 / 64.0)
_E = math.sqrt(E2)
_ALPHA = (
    _N3 / 2.0 - 2.0 * _N2 / 3.0 + 5.0 * _N3 * _N2 / 16.0
    + 41.0 * _N4 / 180.0,
    13.0 * _N2 / 48.0 - 3.0 * _N3 * _N2 / 5.0 + 557.0 * _N4 / 1440.0,
    61.0 * _N3 * _N2 / 240.0 - 103.0 * _N4 / 140.0,
    49561.0 * _N4 / 161280.0,
)
_BETA = (
    _N3 / 2.0 - 2.0 * _N2 / 3.0 + 37.0 * _N3 * _N2 / 96.0 - _N4 / 360.0,
    _N2 / 48.0 + _N3 * _N2 / 15.0 - 437.0 * _N4 / 1440.0,
    17.0 * _N3 * _N2 / 480.0 - 37.0 * _N4 / 840.0,
    4397.0 * _N4 / 161280.0,
)

PL2000 = {z: dict(k0=0.999923, lon0=math.radians(3 * z),
                  fe=z * 1_000_000 + 500_000, fn=0.0)
          for z in (5, 6, 7, 8)}
PL1992 = dict(k0=0.9993, lon0=math.radians(19.0), fe=500_000, fn=-5_300_000)


def gk_forward(phi, lam, par):
    """Geodetic (rad) -> projected (X northing, Y easting), Karney n-series."""
    t = math.tan(phi)
    sig = math.sinh(_E * math.atanh(_E * t / math.sqrt(1.0 + t * t)))
    tp = t * math.sqrt(1.0 + sig * sig) - sig * math.sqrt(1.0 + t * t)
    dl = lam - par["lon0"]
    xi_p = math.atan2(tp, math.cos(dl))
    eta_p = math.asinh(math.sin(dl)
                       / math.hypot(tp, math.cos(dl)))
    xi = xi_p + sum(a * math.sin(2 * j * xi_p) * math.cosh(2 * j * eta_p)
                    for j, a in enumerate(_ALPHA, 1))
    eta = eta_p + sum(a * math.cos(2 * j * xi_p) * math.sinh(2 * j * eta_p)
                      for j, a in enumerate(_ALPHA, 1))
    return (par["k0"] * _AHAT * xi + par["fn"],
            par["k0"] * _AHAT * eta + par["fe"])


def gk_inverse(x, y, par):
    """Projected -> geodetic (rad), Karney n-series + Newton on tau."""
    xi = (x - par["fn"]) / (par["k0"] * _AHAT)
    eta = (y - par["fe"]) / (par["k0"] * _AHAT)
    xi_p = xi - sum(b * math.sin(2 * j * xi) * math.cosh(2 * j * eta)
                    for j, b in enumerate(_BETA, 1))
    eta_p = eta - sum(b * math.cos(2 * j * xi) * math.sinh(2 * j * eta)
                      for j, b in enumerate(_BETA, 1))
    tp = math.sin(xi_p) / math.hypot(math.sinh(eta_p), math.cos(xi_p))
    # Newton: recover tau (tan phi) from conformal tau'
    tau = tp
    for _ in range(4):
        sig = math.sinh(_E * math.atanh(_E * tau / math.sqrt(1.0 + tau * tau)))
        f_tau = (tau * math.sqrt(1.0 + sig * sig)
                 - sig * math.sqrt(1.0 + tau * tau)) - tp
        d_tau = ((math.sqrt(1.0 + sig * sig) * math.sqrt(1.0 + tau * tau)
                  - sig * tau) * (1.0 - E2)
                 * math.sqrt(1.0 + tau * tau)
                 / (1.0 + (1.0 - E2) * tau * tau))
        tau -= f_tau / d_tau
    phi = math.atan(tau)
    lam = par["lon0"] + math.atan2(math.sinh(eta_p), math.cos(xi_p))
    return phi, lam


def pl2000_zone_of_y(y):
    z = int(y // 1_000_000)
    return z if z in PL2000 else None


def convert_1992_to_2000(x, y, zone=None):
    """Exact same-datum path: PL-1992 -> geodetic -> PL-2000. Zone chosen by
    longitude when not forced. Returns (x2000, y2000, zone)."""
    phi, lam = gk_inverse(x, y, PL1992)
    if zone is None:
        zone = min(PL2000, key=lambda z: abs(lam - PL2000[z]["lon0"]))
    X, Y = gk_forward(phi, lam, PL2000[zone])
    return round(X, 2), round(Y, 2), zone


def convert_2000_zone(x, y, zone_from, zone_to):
    phi, lam = gk_inverse(x, y, PL2000[zone_from])
    X, Y = gk_forward(phi, lam, PL2000[zone_to])
    return round(X, 2), round(Y, 2)


def wykryj_uklad(header_uklad, pts):
    """Detection: declared string first, coordinate-magnitude signature as
    the fallback/cross-check. Returns dict(system, strefa, zrodlo, zgodnosc).
    Magnitude signatures: PL-2000: X 5.3-6.13M, Y = strefa*1e6+~(0.29-0.71M);
    PL-1992: X ~0.13-0.91M, Y ~0.14-0.88M (both 6-digit, no zone prefix);
    lokalny: small values (<100k) or otherwise out of national ranges."""
    decl = (header_uklad or "").upper()
    sig = None
    if pts:
        xs = [p["x"] for p in pts if isinstance(p.get("x"), (int, float))]
        ys = [p["y"] for p in pts if isinstance(p.get("y"), (int, float))]
        if xs and ys:
            mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
            # signatures per GUGiK/EPSG recon (primary sources, 06.08):
            # PL-2000: 7-digit pair, Y prefix = strefa 5-8;
            # 1965 I-IV: 7-digit pair, Y prefix 3-4 (NEVER PL-2000);
            # PL-1992: 6-digit pair X 125,837-908,411 / Y 144,693-876,500;
            # 1965 strefa V (Slask) COLLIDES with 1992 magnitudes -
            # disambiguation needs region/powiat profile (flagged elsewhere)
            if 5_300_000 <= mx <= 6_130_000 and pl2000_zone_of_y(my):
                sig = ("PL-2000", pl2000_zone_of_y(my))
            elif 5_200_000 <= mx <= 6_120_000 and 3_280_000 <= my <= 4_950_000:
                sig = ("PL-1965", None)
            elif 125_000 <= mx <= 909_000 and 144_000 <= my <= 877_000:
                sig = ("PL-1992", None)
            elif mx < 100_000 and my < 100_000:
                sig = ("lokalny", None)
    system, strefa = None, None
    if "2000" in decl:
        system = "PL-2000"
        m = [ch for ch in decl if ch in "5678"]
        strefa = int(m[-1]) if m else (sig[1] if sig and sig[0] == "PL-2000"
                                       else None)
    elif "1992" in decl:
        system = "PL-1992"
    elif "1965" in decl:
        system = "PL-1965"
        romans = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}
        m = __import__("re").search(r"STREFA\s+(I{1,3}|IV|V|[1-5])", decl)
        if m:
            g = m.group(1)
            strefa = romans.get(g) or int(g)
    elif "LOKALN" in decl:
        system = "lokalny"
    elif sig:
        system, strefa = sig[0].rstrip("?"), sig[1]
    zgodnosc = None
    if system and sig:
        zgodnosc = sig[0].rstrip("?") == system
    return dict(system=system, strefa=strefa,
                sygnatura=(sig[0] if sig else None),
                zgodnosc_deklaracji_z_liczbami=zgodnosc)


def przelicz_punkty(pts, wykryty):
    """Derived PL-2000 columns for convertible systems; original values stay
    untouched. Returns (pts_with_derived, meta) — meta carries method +
    accuracy + review-flag hint. Non-convertible: abstain with reason."""
    sys_ = wykryty.get("system")
    if sys_ == "PL-2000":
        return pts, dict(przeliczenie=None, uwaga=None)
    if sys_ == "PL-1992":
        out = []
        zone = None
        for p in pts:
            X, Y, zone = convert_1992_to_2000(p["x"], p["y"], zone)
            out.append(dict(p, x_2000=X, y_2000=Y, strefa_2000=zone))
        return out, dict(
            przeliczenie="PL-1992->PL-2000 (Gauss-Kruger, ta sama elipsoida "
                         "GRS80 — matematycznie scisle)",
            dokladnosc_m=0.001, uwaga=None)
    if sys_ == "PL-1965":
        return pts, dict(
            przeliczenie=None,
            uwaga="uklad 1965 (Krasowski): drabina dokladnosci wg GUGiK — "
                  "sama matematyka+Helmert ~1.0 m; z korektami G-1.10 "
                  "3-4 cm; prog prawny EGiB 0.10/0.20 m (Dz.U. 1429/1390) "
                  "— ABSTENCJA z flaga: wgranie wymaga operatu w PL-2000 "
                  "albo transformacji G-1.10/TRANSPOL w profilu powiatu")
    if sys_ == "lokalny":
        return pts, dict(
            przeliczenie=None,
            uwaga="uklad LOKALNY: brak ogolnej transformacji — parametry "
                  "miejskie w profilu powiatu; ABSTENCJA")
    return pts, dict(przeliczenie=None,
                     uwaga="uklad nierozpoznany — recenzja obowiazkowa")
