"""Database connection.

The connection string lives in .streamlit/secrets.toml (never committed):

    [mongo]
    uri = "mongodb+srv://..."
    db = "cb_league"

Collections
-----------
titles          one document per Call of Duty title: modes, map pools, MAR values
settings_log    every Season Settings change, dated
players         {_id: "Arath", gamertags: [{tag, since}], active}
series          {_id: "BO7-S001", title, series_no, date, format, best_of, team_a, team_b,
                 public_note, private_note, status: open|closed, result_override: A|B|N}
matches         {_id: "BO7-M001", title, series_id, map_no, mode, map, score_a, score_b, winner,
                 length_sec, board: full|partial}
player_matches  {_id: "BO7-M001-Sal", title, series_id, match_id, player, team, mode, map, result,
                 kills, deaths, ... (blank = unknown)}

Tournaments (kept apart: nothing here reaches the Series Log or any regular stat)
tournaments       {_id: "T001", name, date, title, size, format, opts, lengths, teams: [{id, name, players, seed, rating}],
                   matches: [bracket matches, see cbl/tourney.py], manual: {match id: "a"|"b"}, created}
t_matches         {_id: "T001-W1-1-1", tournament_id, bmatch, map_no, team_a, team_b, mode, map, score_a, score_b, winner, ...}
t_player_matches  {_id: "T001-W1-1-1-Sal", tournament_id, map_id, bmatch, player, team, team_id, mode, map, result, kills, ...}

Preview mode: with no [mongo] uri, the app runs on an in-memory copy of
data/bo7_seed.json (written by the migration script). Nothing is saved.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import streamlit as st

from cbl.config import ROOT

COLLECTIONS = ("titles", "settings_log", "players", "series", "matches", "player_matches")
T_COLLECTIONS = ("tournaments", "t_matches", "t_player_matches")
SEED = ROOT / "data" / "bo7_seed.json"


def _secret(section: str, key: str, default=None):
    try:
        return st.secrets[section][key]
    except Exception:
        return default


def ensure_indexes(db) -> None:
    db.series.create_index([("title", 1), ("series_no", 1)])
    db.matches.create_index([("title", 1), ("series_id", 1), ("map_no", 1)])
    db.player_matches.create_index([("title", 1), ("player", 1)])
    db.player_matches.create_index("match_id")
    db.t_matches.create_index([("tournament_id", 1), ("bmatch", 1), ("map_no", 1)])
    db.t_player_matches.create_index([("tournament_id", 1), ("player", 1)])


@st.cache_resource(show_spinner=False)
def get_db():
    uri = _secret("mongo", "uri") or os.environ.get("MONGO_URI")
    if uri:
        from pymongo import MongoClient

        client = MongoClient(uri, serverSelectionTimeoutMS=10000)
        db = client[_secret("mongo", "db") or os.environ.get("MONGO_DB", "cb_league")]
        ensure_indexes(db)
        return db
    import mongomock

    db = mongomock.MongoClient()["cb_league"]
    if SEED.exists():
        data = json.loads(SEED.read_text(encoding="utf-8"))
        for name in COLLECTIONS:
            if data.get(name):
                db[name].insert_many(data[name])
    return db


def is_preview() -> bool:
    return not (_secret("mongo", "uri") or os.environ.get("MONGO_URI"))