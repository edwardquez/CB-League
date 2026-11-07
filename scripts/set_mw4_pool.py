"""MW4 version 1 setup (one time): the official map pools, Hijack's target score (300) and Hijack's MAR values.

    python scripts/set_mw4_pool.py            # shows what would change, changes nothing
    python scripts/set_mw4_pool.py --apply    # makes the change

Hardpoint: Lithium, Lotus, Munition, Reactor U92, Rooftops, Sentry
Search and Destroy: Coal, Lotus, Munition, Reactor U92, Rooftops, Silkworm
Hijack: Lithium, Lotus, Munition · first to 300 · MAR: dunk 3 kills, remote plant 2.5, interception 1.5

Maps in the set are made active (added if missing). Every other map in a pool is retired, never deleted: maps
already played keep all their stats, and a retired map can be brought back under Scorekeeper > Season Settings.
The change is recorded in Season Settings' change history. Safe to run again: it only changes what differs.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TITLE = "MW4"
POOLS = {
    "HP": ["Lithium", "Lotus", "Munition", "Reactor U92", "Rooftops", "Sentry"],
    "SND": ["Coal", "Lotus", "Munition", "Reactor U92", "Rooftops", "Silkworm"],
    "HJ": ["Lithium", "Lotus", "Munition"],
}
NAMES = {"HP": "Hardpoint", "SND": "SnD", "HJ": "Hijack"}
WIN = {"HJ": 300}   # first to 300 over two rounds (or the higher score when time runs out)
# Hijack MAR, in kills: a dunk like an overload, a remote plant a little less, an interception like a carrier kill.
# Only filled in where Hijack has no values yet, so anything set later in Season Settings is never overwritten.
HJ_MAR = {"dunk": 3.0, "remote_plant": 2.5, "interception": 1.5}


def mar_todo(doc: dict) -> bool:
    blocks = [doc.get("mar", {})] + list(doc.get("mar_versions") or [])
    return any(not (b.get("modes", {}).get("HJ") or {}) for b in blocks)


def plan(doc: dict) -> dict:
    """mode -> {"add": [...], "back": [...], "retire": [...]} (only modes with something to change)."""
    out = {}
    for mode, want in POOLS.items():
        maps = doc.get("modes", {}).get(mode, {}).get("maps", [])
        have = {m["name"].lower(): m for m in maps}
        wl = {w.lower() for w in want}
        ch = {"add": [w for w in want if w.lower() not in have],
              "back": [m["name"] for m in maps if m["name"].lower() in wl and m.get("status") == "retired"],
              "retire": [m["name"] for m in maps if m["name"].lower() not in wl and m.get("status") != "retired"]}
        if WIN.get(mode) and doc.get("modes", {}).get(mode, {}).get("win_score") != WIN[mode]:
            ch["win"] = WIN[mode]
        if any(ch.values()):
            out[mode] = ch
    return out


def apply(db, today: str | None = None) -> dict:
    today = today or dt.date.today().isoformat()
    doc = db.titles.find_one({"_id": TITLE})
    if doc is None:
        raise SystemExit(f"No {TITLE} title in the database.")
    todo = plan(doc)
    mar = mar_todo(doc)
    if not todo and not mar:
        return {}
    notes = []
    if mar:
        for blk in [doc.setdefault("mar", {})] + list(doc.get("mar_versions") or []):
            if not (blk.setdefault("modes", {}).get("HJ") or {}):
                blk["modes"]["HJ"] = dict(HJ_MAR)
        notes.append("Hijack MAR: dunk 3 kills, remote plant 2.5, interception 1.5")
    for mode, ch in todo.items():
        maps = doc["modes"].setdefault(mode, {}).setdefault("maps", [])
        for m in maps:
            if m["name"] in ch["back"]:
                m["status"] = "active"
            elif m["name"] in ch["retire"]:
                m["status"] = "retired"
        maps.extend({"name": x, "status": "active", "since": today} for x in ch["add"])
        if ch.get("win"):
            doc["modes"][mode]["win_score"] = ch["win"]
        bits = [f"added {', '.join(ch['add'])}" if ch["add"] else "", f"brought back {', '.join(ch['back'])}" if ch["back"] else "",
                f"retired {', '.join(ch['retire'])}" if ch["retire"] else "", f"first to {ch['win']}" if ch.get("win") else ""]
        notes.append(f"{NAMES.get(mode, mode)}: " + "; ".join(b for b in bits if b))
    db.titles.replace_one({"_id": TITLE}, doc)
    db.settings_log.insert_one({"_id": f"{TITLE}-{dt.datetime.now().strftime('%Y%m%d%H%M%S%f')}", "title": TITLE, "date": today,
                                "text": "Official version 1 map set. " + " · ".join(notes)})
    return todo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="make the change (without it, just show what would change)")
    args = ap.parse_args()
    sec = ROOT / ".streamlit" / "secrets.toml"
    cfg = tomllib.loads(sec.read_text(encoding="utf-8")).get("mongo", {}) if sec.exists() else {}
    if not cfg.get("uri"):
        raise SystemExit("No [mongo] uri in .streamlit/secrets.toml, so there's no database to change.")
    from pymongo import MongoClient
    db = MongoClient(cfg["uri"], serverSelectionTimeoutMS=15000)[cfg.get("db", "cb_league")]
    doc = db.titles.find_one({"_id": TITLE})
    if doc is None:
        raise SystemExit(f"No {TITLE} title in the database.")
    todo = plan(doc)
    mar = mar_todo(doc)
    if not todo and not mar:
        print("Nothing to do: everything already matches.")
        return
    for mode, ch in todo.items():
        for what, label in (("add", "add"), ("back", "bring back"), ("retire", "retire")):
            if ch[what]:
                print(f"  {NAMES.get(mode, mode)}: {label} {', '.join(ch[what])}")
        if ch.get("win"):
            print(f"  {NAMES.get(mode, mode)}: set the target score to {ch['win']}")
    if mar:
        print("  Hijack MAR: dunk 3 kills, remote plant 2.5 kills, interception 1.5 kills")
    if not args.apply:
        print("\nThat's a preview. Run again with --apply to make the change.")
        return
    apply(db)
    print("\nDone. Restart the app (or reboot it on Streamlit Cloud) to see the new pools.")


if __name__ == "__main__":
    sys.exit(main())