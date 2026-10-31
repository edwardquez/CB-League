"""Add the opening Modern Warfare 4 map pool to the database (one time).

    python scripts/add_mw4_maps.py            # shows what would change, changes nothing
    python scripts/add_mw4_maps.py --apply    # makes the change

Adds Coal, Lotus, Mumbai, Munition, Reactor U92, Rooftops and Silkworm to the Hardpoint, Search and Destroy
and Hijack pools for MW4, plus Lithium and Sentry to all three,, and records it in Season Settings' change history. Safe to run again: maps already
in a pool are skipped. Later changes to the pool are made in the app (Scorekeeper > Season Settings).

The map pictures live in static/maps/ (coal-card.webp, coal-thumb.webp, ...).
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TITLE = "MW4"
MAPS = ["Coal", "Lotus", "Mumbai", "Munition", "Reactor U92", "Rooftops", "Silkworm"]
# Lithium and Sentry were added on Oct 30 to all three modes. Safe to run again: maps already in a pool are skipped.
POOLS = {"HP": MAPS + ["Lithium", "Sentry"], "SND": MAPS + ["Lithium", "Sentry"], "HJ": MAPS + ["Lithium", "Sentry"]}


def plan(doc: dict) -> dict:
    """mode -> maps to add (those not already in the pool, active or retired)."""
    out = {}
    for mode, maps in POOLS.items():
        have = {m["name"].lower() for m in doc.get("modes", {}).get(mode, {}).get("maps", [])}
        add = [m for m in maps if m.lower() not in have]
        if add:
            out[mode] = add
    return out


def apply(db, today: str | None = None) -> dict:
    today = today or dt.date.today().isoformat()
    doc = db.titles.find_one({"_id": TITLE})
    if doc is None:
        raise SystemExit(f"No {TITLE} title in the database. Run the app once, or the migration, so it exists.")
    todo = plan(doc)
    if not todo:
        return {}
    for mode, add in todo.items():
        m = doc["modes"].setdefault(mode, {})
        m.setdefault("maps", []).extend({"name": x, "status": "active", "since": today} for x in add)
    db.titles.replace_one({"_id": TITLE}, doc)
    names = {"HP": "Hardpoint", "SND": "SnD", "HJ": "Hijack"}
    text = "Added to the map pool: " + "; ".join(f"{names.get(k, k)}: {', '.join(v)}" for k, v in todo.items())
    db.settings_log.insert_one({"_id": f"{TITLE}-{dt.datetime.now().strftime('%Y%m%d%H%M%S%f')}", "title": TITLE, "date": today, "text": text})
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
    if not todo:
        print("Nothing to do: every map is already in its pool.")
        return
    for mode, add in todo.items():
        print(f"  {mode}: add {', '.join(add)}")
    if not args.apply:
        print("\nThat's a preview. Run again with --apply to make the change.")
        return
    apply(db)
    print("\nDone. Restart the app to see the maps.")


if __name__ == "__main__":
    sys.exit(main())