# geodoc — domain graph (slice 9): SQLite record of every point measurement
# across operaty, with bi-temporal supersession (Zep/Graphiti pattern from the
# dossier § 5): a later measurement of the same point NEVER deletes the older
# row — it stamps t_invalid and the chain stays queryable as the point's
# rodowód. The nowy/zmieniony/bez_zmian flag is COMPUTED from this history
# (measured-law: aggregation by code), never taken from the operat's own claim;
# an imported archive of past operaty backfills through the same ingest.
#
# domain/graph.db (cross-job, next to jobs/) — stdlib sqlite3 only.

import json
import math
import os
import sqlite3
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "domain", "graph.db")

TOL_M = 0.01                 # coordinate identity tolerance: 1 cm
ATTRS = ("zrd", "bpp", "stb", "rzg")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS operat(
  id TEXT PRIMARY KEY, data_pomiaru TEXT, data_sporzadzenia TEXT,
  wykonawca TEXT, dzialka TEXT, job TEXT, t_created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS pomiar(
  pk INTEGER PRIMARY KEY,
  punkt TEXT NOT NULL, operat TEXT NOT NULL,
  x REAL, y REAL, h REAL, zrd TEXT, bpp TEXT, stb TEXT, rzg TEXT,
  status TEXT, page INTEGER, data TEXT,
  flaga TEXT, delta_m REAL,
  t_created TEXT NOT NULL, t_invalid TEXT);
CREATE INDEX IF NOT EXISTS idx_pomiar_punkt ON pomiar(punkt);
CREATE INDEX IF NOT EXISTS idx_pomiar_operat ON pomiar(operat);
"""


def connect(db=None):
    path = db or DB
    os.makedirs(os.path.dirname(path), exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(_SCHEMA)
    return con


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _differs(a, b):
    """True when b is a CHANGED measurement relative to a (coords beyond 1 cm
    or any legal attribute flipped)."""
    if math.dist((a["x"] or 0, a["y"] or 0), (b["x"] or 0, b["y"] or 0)) > TOL_M:
        return True
    return any((a[k] or None) != (b[k] or None) for k in ATTRS)


def _rechain(con, punkt):
    """Recompute the supersession chain of one point from scratch: order by
    measurement date (transaction time breaks ties), first sight = nowy, each
    later row compared to its predecessor. Idempotent — corrections and
    backdated archive ingests land in the right place of history."""
    rows = con.execute(
        "SELECT * FROM pomiar WHERE punkt=? ORDER BY data, t_created",
        (punkt,)).fetchall()
    now = _now()
    prev = None
    for row in rows:
        if prev is None:
            flaga, delta = "nowy", None
        else:
            delta = round(math.dist((prev["x"] or 0, prev["y"] or 0),
                                    (row["x"] or 0, row["y"] or 0)), 3)
            flaga = "zmieniony" if _differs(prev, row) else "bez_zmian"
        con.execute("UPDATE pomiar SET flaga=?, delta_m=?, t_invalid=? "
                    "WHERE pk=?", (flaga, delta, None, row["pk"]))
        if prev is not None:
            con.execute("UPDATE pomiar SET t_invalid=COALESCE(t_invalid,?) "
                        "WHERE pk=?", (now, prev["pk"]))
        prev = row


def ingest(operat_id, header, punkty, job=None, db=None):
    """Idempotent ingest of one operat's wykaz: re-running the same operat id
    replaces its own rows (a re-run corrects the same source document — it is
    not new history), then every touched point gets its chain recomputed."""
    con = connect(db)
    try:
        return _ingest_locked(con, operat_id, header, punkty, job)
    finally:
        con.close()


def _ingest_locked(con, operat_id, header, punkty, job):
    now = _now()
    data = (header.get("data_pomiaru") or header.get("data_sporzadzenia")
            or now[:10])
    with con:
        touched = {r["punkt"] for r in con.execute(
            "SELECT DISTINCT punkt FROM pomiar WHERE operat=?", (operat_id,))}
        con.execute("DELETE FROM pomiar WHERE operat=?", (operat_id,))
        con.execute("DELETE FROM operat WHERE id=?", (operat_id,))
        con.execute(
            "INSERT INTO operat VALUES (?,?,?,?,?,?,?)",
            (operat_id, header.get("data_pomiaru"),
             header.get("data_sporzadzenia"), header.get("wykonawca"),
             header.get("dzialka"), job, now))
        for p in punkty:
            con.execute(
                "INSERT INTO pomiar(punkt, operat, x, y, h, zrd, bpp, stb,"
                " rzg, status, page, data, t_created) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (str(p.get("id")), operat_id, p.get("x"), p.get("y"),
                 p.get("h"), p.get("zrd"), p.get("bpp"), p.get("stb"),
                 p.get("rzg"), p.get("status"), p.get("page"), data, now))
            touched.add(str(p.get("id")))
        for punkt in touched:
            _rechain(con, punkt)
        flags = {r["punkt"]: {"flaga": r["flaga"], "delta_m": r["delta_m"]}
                 for r in con.execute(
                     "SELECT punkt, flaga, delta_m FROM pomiar WHERE operat=?",
                     (operat_id,))}
    return flags


def ingest_job(job_name, db=None):
    """Pipeline hook: ingest a finished job's extracted artifacts."""
    job_dir = os.path.join(ROOT, "jobs", job_name)
    hdr = json.load(open(os.path.join(job_dir, "extracted", "header.json"),
                         encoding="utf-8"))
    wyk = json.load(open(os.path.join(job_dir, "extracted", "wykaz.json"),
                         encoding="utf-8"))
    operat_id = hdr.get("id_zgloszenia") or job_name
    return ingest(operat_id, hdr, wyk.get("punkty") or [], job=job_name, db=db)


def rodowod(punkt, db=None):
    """The pedigree of a point: every measurement ever recorded, oldest first;
    the row with t_invalid IS NULL is the current belief."""
    con = connect(db)
    try:
        return [dict(r) for r in con.execute(
            "SELECT p.*, o.wykonawca, o.dzialka FROM pomiar p "
            "LEFT JOIN operat o ON o.id = p.operat "
            "WHERE p.punkt=? ORDER BY p.data, p.t_created", (str(punkt),))]
    finally:
        con.close()


def summary(db=None):
    con = connect(db)
    try:
        return _summary_locked(con)
    finally:
        con.close()


def _summary_locked(con):
    out = {
        "operaty": con.execute("SELECT COUNT(*) c FROM operat").fetchone()["c"],
        "punkty": con.execute(
            "SELECT COUNT(DISTINCT punkt) c FROM pomiar").fetchone()["c"],
        "pomiary": con.execute("SELECT COUNT(*) c FROM pomiar").fetchone()["c"],
        "flagi": {r["flaga"]: r["c"] for r in con.execute(
            "SELECT flaga, COUNT(*) c FROM pomiar WHERE t_invalid IS NULL "
            "GROUP BY flaga")},
    }
    return out
