"""Load the Black Ops 7 season from the workbook into MongoDB.

    python scripts/migrate_bo7.py

Reads data/source/BumLeague_BO7.xlsx, applies data/source/corrections.yaml,
checks everything, writes a snapshot to data/bo7_seed.json and, if
.streamlit/secrets.toml has a [mongo] uri, loads it into the database.

Safe to re-run: documents are replaced by ID (BO7-S001, BO7-M001,
BO7-M001-Sal), so nothing is duplicated. Title settings and players are only
created if they don't exist yet, so changes you've made in the app are kept.
Use --reset-settings to overwrite title settings from the YAML templates.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import sys
import tomllib
import warnings
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from cbl.config import templates  # noqa: E402

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")
XLSX = ROOT / "data" / "source" / "BumLeague_BO7.xlsx"
CORR = ROOT / "data" / "source" / "corrections.yaml"
SEED = ROOT / "data" / "bo7_seed.json"
TITLE = "BO7"
MODE = {"hp": "HP", "hardpoint": "HP", "snd": "SND", "s&d": "SND", "search and destroy": "SND", "overload": "OVL", "ovl": "OVL"}
COLS = {"Kills": "kills", "Deaths": "deaths", "Assists": "assists", "Non_Traded_Kills": "non_traded_kills",
        "Highest_Streak": "highest_streak", "Damage": "damage", "Hill_Time_Seconds": "hill_time",
        "Objective_Kills": "objective_kills", "First_Bloods": "first_bloods", "First_Deaths": "first_deaths",
        "Bombs_Planted": "bombs_planted", "Overloads": "overloads", "Carrier_Kills": "carrier_kills",
        "Kills_As_Carrier": "kills_as_carrier", "Accuracy": "accuracy"}


def clean(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def title_doc(tid: str) -> dict:
    t = templates()[tid]
    modes = {}
    for code, m in t["modes"].items():
        modes[code] = {k: v for k, v in m.items() if k not in ("maps", "retired_maps")}
        modes[code]["active"] = m.get("active", True)
        modes[code]["maps"] = [{"name": x, "status": "active"} for x in m.get("maps") or []] + \
                              [{"name": x, "status": "retired"} for x in m.get("retired_maps") or []]
    doc = {k: v for k, v in t.items() if k != "modes"}
    doc.update({"_id": tid, "modes": modes, "mar_versions": [{"from": "1900-01-01", **t["mar"]}]})
    return doc


def build() -> tuple[dict, list[str]]:
    corr = yaml.safe_load(CORR.read_text(encoding="utf-8"))
    issues: list[str] = []
    series = pd.read_excel(XLSX, "Series").dropna(subset=["Series_ID"])
    matches = pd.read_excel(XLSX, "Matches").dropna(subset=["Match_ID"])
    stats = pd.read_excel(XLSX, "Player_Stats").dropna(subset=["Match_ID"])
    sid = lambda raw: f"{TITLE}-{raw}"  # noqa: E731

    s_docs = []
    for r in series.itertuples(index=False):
        date = pd.Timestamp(r.Date).date()
        fix = (corr.get("series") or {}).get(r.Series_ID, {})
        if "date" in fix:
            date = pd.Timestamp(fix["date"]).date()
        note = clean(r.Notes)
        s_docs.append({"_id": sid(r.Series_ID), "title": TITLE, "series_no": int(str(r.Series_ID).lstrip("S")),
                       "date": date.isoformat(), "format": r.Format, "best_of": int(fix.get("best_of", r.Best_Of)),
                       "team_a": [p.strip() for p in str(r.Team_A_Players).split(",") if p.strip()],
                       "team_b": [p.strip() for p in str(r.Team_B_Players).split(",") if p.strip()],
                       "public_note": None if corr.get("notes_private") else note,
                       "private_note": note if corr.get("notes_private") else None,
                       "status": "closed", "result_override": None})
    by_s = {d["_id"]: d for d in s_docs}

    m_docs, counter = [], {}
    for r in matches.itertuples(index=False):
        s_id = sid(r.Series_ID); counter[s_id] = counter.get(s_id, 0) + 1
        mode = MODE[str(r.Mode).strip().lower()]
        w = "A" if r.Team_A_Score > r.Team_B_Score else "B"
        if str(r.Winning_Team).strip() != w:
            issues.append(f"{r.Match_ID}: winner column says {r.Winning_Team}, score says {w}")
        m_docs.append({"_id": sid(r.Match_ID), "title": TITLE, "series_id": s_id, "map_no": counter[s_id], "mode": mode,
                       "map": r.Map, "score_a": int(r.Team_A_Score), "score_b": int(r.Team_B_Score), "winner": w,
                       "length_sec": None, "board": "full"})
    by_m = {d["_id"]: d for d in m_docs}

    fixes = {(f["match"], f["player"]): f for f in corr.get("player_stats") or []}
    p_docs = []
    for r in stats.to_dict("records"):
        m_id = sid(r["Match_ID"]); mt = by_m[m_id]
        doc = {"_id": f"{m_id}-{r['Player']}", "title": TITLE, "series_id": mt["series_id"], "match_id": m_id,
               "player": r["Player"], "team": r["Team"], "mode": mt["mode"], "map": mt["map"],
               "result": "W" if mt["winner"] == r["Team"] else "L"}
        for col, key in COLS.items():
            doc[key] = clean(r.get(col))
        f = fixes.get((r["Match_ID"], r["Player"]))
        if f:
            doc.update({k: v for k, v in f.items() if k not in ("match", "player")})
        roster = by_s[mt["series_id"]]["team_a" if r["Team"] == "A" else "team_b"]
        if r["Player"] not in roster:
            issues.append(f"{r['Match_ID']}: {r['Player']} not on team {r['Team']}'s roster")
        p_docs.append(doc)
    for m in m_docs:  # any map left with no partial info is a full scoreboard
        rows = [p for p in p_docs if p["match_id"] == m["_id"]]
        if any(p.get("damage") is None for p in rows):
            m["board"] = "partial"

    players = sorted({p["player"] for p in p_docs})
    data = {"titles": [title_doc(t) for t in templates()],
            "settings_log": [{"_id": f"{t}-seed", "title": t, "date": dt.date.today().isoformat(),
                              "text": "Started from the " + ("workbook" if t == TITLE else "Black Ops 7 template")}
                             for t in templates()],
            "players": [{"_id": p, "gamertags": [], "active": True} for p in players],
            "series": s_docs, "matches": m_docs, "player_matches": p_docs}
    return data, issues


def verify(data: dict) -> list[str]:
    """Recompute the headline numbers and compare with the verified values."""
    from cbl.engine import Engine

    eng = Engine(data, TITLE)
    pm = eng.pm
    tot = pm.groupby("player").mar.sum().round(2)
    expect = {"Arath": 13.48, "Carl": 12.60, "Vera": 6.47, "Miguel": 6.34, "Sal": 5.06, "Jason": 3.89, "Ed": 2.67, "Fonz": -0.32}
    out = []
    for p, v in expect.items():
        ok = abs(tot.get(p, 99) - v) < 0.011
        out.append(f"{'ok ' if ok else 'XX '} MAR {p:<7} {tot.get(p):+.2f} (expected {v:+.2f})")
    mvp = eng.series_mvps()
    counts = pd.Series([v[0] for v in mvp.values()]).value_counts().to_dict()
    out.append(f"{'ok ' if counts == {'Arath': 6, 'Carl': 6, 'Ed': 2} else 'XX '} Series MVPs {counts} (expected Arath 6, Carl 6, Ed 2)")
    kd = pm[pm.player == "Arath"]; kd = kd.kills.sum() / kd.deaths.sum()
    out.append(f"{'ok ' if round(kd, 2) == 1.44 else 'XX '} Arath K/D {kd:.2f} (expected 1.44)")
    riv = eng.rivalry_record(["Arath", "Jason", "Miguel"], ["Carl", "Sal", "Vera"])
    out.append(f"{'ok ' if riv[:2] == (4, 4) else 'XX '} Main rivalry {riv[0]}-{riv[1]} in series (expected 4-4)")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset-settings", action="store_true", help="overwrite title settings from config/titles")
    ap.add_argument("--no-db", action="store_true", help="only build, check and write the snapshot")
    args = ap.parse_args()

    data, issues = build()
    print(f"BO7: {len(data['series'])} series, {len(data['matches'])} maps, {len(data['player_matches'])} player rows, "
          f"{len(data['players'])} players")
    print("Corrections applied: Series 2 date -> May 21, Series 14 best of 9 (ended early), Series 1 Overload Den deaths (4 players), BO7 notes private")
    if issues:
        print(f"\n{len(issues)} things to look at:")
        for i in issues:
            print("  -", i)
    print("\nChecking the numbers:")
    for line in verify(data):
        print("  " + line)
    SEED.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"\nWrote snapshot {SEED.relative_to(ROOT)}")

    if args.no_db:
        return
    sec = ROOT / ".streamlit" / "secrets.toml"
    if not sec.exists():
        print("\nNo .streamlit/secrets.toml found, so nothing was loaded into MongoDB.")
        return
    cfg = tomllib.loads(sec.read_text(encoding="utf-8")).get("mongo", {})
    if not cfg.get("uri"):
        print("\nNo [mongo] uri in secrets.toml, so nothing was loaded into MongoDB.")
        return
    from pymongo import MongoClient, ReplaceOne

    db = MongoClient(cfg["uri"], serverSelectionTimeoutMS=15000)[cfg.get("db", "cb_league")]
    print(f"\nLoading into MongoDB database '{db.name}'...")
    for name, docs in data.items():
        if name in ("titles", "players", "settings_log") and not args.reset_settings:
            new = [d for d in docs if db[name].count_documents({"_id": d["_id"]}) == 0]
            if new:
                db[name].insert_many(new)
            print(f"  {name}: {len(new)} added ({len(docs) - len(new)} already there, kept)")
            continue
        res = db[name].bulk_write([ReplaceOne({"_id": d["_id"]}, d, upsert=True) for d in docs])
        print(f"  {name}: {res.upserted_count} added, {res.modified_count} updated")
    print("Done. Start the app with:  streamlit run Home.py")


if __name__ == "__main__":
    main()
