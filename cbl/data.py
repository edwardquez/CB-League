"""Reads (cached) and the writes the Scorekeeper makes."""
from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from cbl.db import COLLECTIONS, T_COLLECTIONS, get_db
from cbl.engine import Engine


@st.cache_data(ttl=600, show_spinner=False)
def _load_docs_cached() -> dict:
    db = get_db()
    return {name: list(db[name].find()) for name in COLLECTIONS}


@st.cache_data(ttl=600, show_spinner=False)
def _load_tdocs_cached() -> dict:
    db = get_db()
    return {name: list(db[name].find()) for name in T_COLLECTIONS}


# ---------------------------------------------------------------- practice mode
# The Scorekeeper and Tournaments pages can run against a private in-memory copy of the data (mongomock)
# that lives only in this browser session. Reads and writes on those pages then go to that copy, so test
# series and test brackets never reach MongoDB, and every other page keeps showing the real data.
def practice_db():
    ss = st.session_state
    if ss.get("practice") and ss.get("_on_scorekeeper") and "practice_db" in ss:
        return ss["practice_db"]
    return None


def start_practice() -> None:
    import copy
    import mongomock
    sandbox = mongomock.MongoClient()["practice"]
    real = {**_load_docs_cached(), **_load_tdocs_cached()}
    for name in COLLECTIONS + T_COLLECTIONS:
        if real.get(name):
            sandbox[name].insert_many(copy.deepcopy(real[name]))
    st.session_state["practice_db"] = sandbox
    st.session_state["practice"] = True
    st.session_state.pop("_practice_engines", None)


def stop_practice() -> None:
    st.session_state["practice"] = False
    st.session_state.pop("practice_db", None)
    st.session_state.pop("_practice_engines", None)


def load_docs() -> dict:
    pdb = practice_db()
    if pdb is not None:
        return {name: list(pdb[name].find()) for name in COLLECTIONS}
    return _load_docs_cached()


@st.cache_resource(show_spinner=False, max_entries=8)
def _engine(title, version: str) -> Engine:
    return Engine(load_docs(), title)


@st.cache_resource(show_spinner=False)
def _rev() -> dict:
    return {"n": 0}  # shared by every session: bumped on each write


def version() -> str:
    d = load_docs()
    return "|".join(f"{k}:{len(v)}" for k, v in d.items()) + "|" + str(_rev()["n"])


def engine(title: str | None) -> Engine:
    if practice_db() is not None:
        # practice data is private to this browser session, so its engines are cached here (not shared),
        # and dropped whenever something is saved in practice (see refresh)
        cache = st.session_state.setdefault("_practice_engines", {})
        key = (title, st.session_state.get("_practice_rev", 0))
        if key not in cache:
            cache.clear() if len(cache) > 6 else None
            cache[key] = Engine(load_docs(), title)
        return cache[key]
    return _engine(title, version())


def refresh() -> None:
    if practice_db() is not None:
        # a practice save: only this session's practice engines go stale
        st.session_state["_practice_rev"] = st.session_state.get("_practice_rev", 0) + 1
        st.session_state.pop("_practice_engines", None)
        return
    _load_docs_cached.clear()
    _load_tdocs_cached.clear()
    _rev()["n"] += 1


# ---------------------------------------------------------------- titles / seasons
def titles() -> dict:
    return {t["_id"]: t for t in sorted(load_docs()["titles"], key=lambda t: t.get("order", 0))}


def titles_with_data() -> list[str]:
    have = {s["title"] for s in load_docs()["series"]}
    return [t for t in titles() if t in have]


def current_title() -> str:
    ts = titles()
    for t, d in ts.items():
        if d.get("current"):
            return t
    return list(ts)[-1] if ts else "BO7"


def season_options(allow_all: bool = True) -> list[tuple[str, str]]:
    """(value, label): current title first, then older ones, then All time."""
    ts = titles(); opts = []
    for tid in sorted(ts, key=lambda t: -ts[t].get("order", 0)):
        opts.append((tid, f"{ts[tid]['name']} ({ts[tid]['year']})"))
    if allow_all:
        opts.append(("ALL", "All time"))
    return opts


def default_season() -> str:
    cur = current_title()
    have = titles_with_data()
    return cur if cur in have else (have[-1] if have else cur)


def season_label(value: str) -> str:
    if value == "ALL":
        return "All time · every title"
    t = titles().get(value, {})
    return f"{t.get('name', value)} · {t.get('year', '')}"


# ---------------------------------------------------------------- writes
def _db():
    pdb = practice_db()
    return pdb if pdb is not None else get_db()


def add_player(name: str, gamertag: str | None) -> None:
    tags = [{"tag": gamertag.strip(), "since": dt.date.today().isoformat()}] if gamertag else []
    _db().players.update_one({"_id": name.strip()}, {"$setOnInsert": {"gamertags": tags, "active": True}}, upsert=True)
    refresh()


def add_gamertag(name: str, tag: str) -> None:
    _db().players.update_one({"_id": name}, {"$push": {"gamertags": {"tag": tag.strip(), "since": dt.date.today().isoformat()}}})
    refresh()


def next_series_no(title: str) -> int:
    nums = [s["series_no"] for s in load_docs()["series"] if s["title"] == title]
    return (max(nums) + 1) if nums else 1


def create_series(title: str, date, fmt: str, best_of: int, team_a: list[str], team_b: list[str],
                  public_note: str | None, private_note: str | None) -> str:
    no = next_series_no(title); sid = f"{title}-S{no:03d}"
    _db().series.insert_one({"_id": sid, "title": title, "series_no": no, "date": pd.Timestamp(date).date().isoformat(),
                             "format": fmt, "best_of": int(best_of), "team_a": team_a, "team_b": team_b,
                             "public_note": public_note or None, "private_note": private_note or None,
                             "status": "open", "result_override": None})
    refresh()
    return sid


def save_veto(sid: str, veto: dict | None) -> None:
    """The finished map veto for a series (cbl/veto.py), or None to clear it."""
    _db().series.update_one({"_id": sid}, {"$set": {"veto": veto}}); refresh()


def update_series(sid: str, **fields) -> None:
    _db().series.update_one({"_id": sid}, {"$set": fields}); refresh()


def next_match_no(title: str) -> int:
    nums = [int(m["_id"].split("-M")[-1]) for m in load_docs()["matches"] if m["title"] == title]
    return (max(nums) + 1) if nums else 1


def save_map(series: dict, mode: str, map_name: str, score_a: int, score_b: int, length_sec, board: str,
             rows: list[dict], match_id: str | None = None, extra: dict | None = None) -> str:
    """extra: optional map facts kept on the match, e.g. {"picked_by": "A", "side": "good", "side_by": "B"} from the veto."""
    db = _db(); title = series["title"]
    if match_id is None:
        match_id = f"{title}-M{next_match_no(title):03d}"
        map_no = 1 + sum(1 for m in load_docs()["matches"] if m["series_id"] == series["_id"])
    else:
        map_no = next(m["map_no"] for m in load_docs()["matches"] if m["_id"] == match_id)
    winner = "A" if score_a > score_b else "B"
    db.matches.replace_one({"_id": match_id}, {"_id": match_id, "title": title, "series_id": series["_id"], "map_no": map_no,
                                               "mode": mode, "map": map_name, "score_a": int(score_a), "score_b": int(score_b),
                                               "winner": winner, "length_sec": length_sec, "board": board, **(extra or {})}, upsert=True)
    db.player_matches.delete_many({"match_id": match_id})
    docs = []
    for r in rows:
        d = {"_id": f"{match_id}-{r['player']}", "title": title, "series_id": series["_id"], "match_id": match_id,
             "player": r["player"], "team": r["team"], "mode": mode, "map": map_name, "result": "W" if r["team"] == winner else "L"}
        d.update({k: v for k, v in r.items() if k not in ("player", "team")})
        docs.append(d)
    if docs:
        db.player_matches.insert_many(docs)
    refresh()
    return match_id


def delete_map(match_id: str) -> None:
    db = _db(); db.matches.delete_one({"_id": match_id}); db.player_matches.delete_many({"match_id": match_id}); refresh()


def save_title(doc: dict, log_text: str) -> None:
    db = _db(); db.titles.replace_one({"_id": doc["_id"]}, doc, upsert=True)
    db.settings_log.insert_one({"_id": f"{doc['_id']}-{dt.datetime.now().strftime('%Y%m%d%H%M%S%f')}", "title": doc["_id"],
                                "date": dt.date.today().isoformat(), "text": log_text})
    refresh()


def backup_csv() -> bytes:
    """Every series, map and player stat in one CSV (one row per player per map)."""
    d = load_docs()
    pm = pd.DataFrame(d["player_matches"]); m = pd.DataFrame(d["matches"]); s = pd.DataFrame(d["series"])
    if pm.empty:
        return b""
    m = m.rename(columns={"_id": "match_id"}).drop(columns=["title", "mode", "map", "series_id"], errors="ignore")
    s = s.rename(columns={"_id": "series_id"})[["series_id", "series_no", "date", "format", "best_of", "public_note", "private_note"]]
    out = pm.merge(m, on="match_id", how="left").merge(s, on="series_id", how="left")
    return out.to_csv(index=False).encode("utf-8")


# ---------------------------------------------------------------- tournaments
# Separate collections: none of this is read by load_docs(), so tournament games never reach the Series
# Log, standings, MAR, records or any other page.
def load_tdocs() -> dict:
    pdb = practice_db()
    if pdb is not None:
        return {name: list(pdb[name].find()) for name in T_COLLECTIONS}
    return _load_tdocs_cached()


def next_tournament_id() -> str:
    nums = [int(t["_id"][1:]) for t in load_tdocs()["tournaments"] if str(t["_id"])[1:].isdigit()]
    return f"T{(max(nums) + 1) if nums else 1:03d}"


def save_tournament(doc: dict) -> None:
    _db().tournaments.replace_one({"_id": doc["_id"]}, doc, upsert=True)
    refresh()


def delete_tournament(tid: str) -> None:
    db = _db()
    db.tournaments.delete_one({"_id": tid}); db.t_matches.delete_many({"tournament_id": tid})
    db.t_player_matches.delete_many({"tournament_id": tid})
    refresh()


def save_tmap(t: dict, bmatch: str, team_a: str, team_b: str, mode: str, map_name: str, score_a: int, score_b: int,
              length_sec, board: str, rows: list[dict], map_id: str | None = None) -> str:
    """One tournament map. rows: {player, team: A|B, stats...}. team_a / team_b are tournament team ids."""
    db = _db(); tid = t["_id"]
    mine = [m for m in load_tdocs()["t_matches"] if m["tournament_id"] == tid and m["bmatch"] == bmatch]
    if map_id is None:
        map_no = 1 + max([m["map_no"] for m in mine], default=0)
        map_id = f"{tid}-{bmatch}-{map_no}"
    else:
        map_no = next(m["map_no"] for m in mine if m["_id"] == map_id)
    winner = "A" if score_a > score_b else "B"
    db.t_matches.replace_one({"_id": map_id}, {"_id": map_id, "tournament_id": tid, "title": t.get("title"), "bmatch": bmatch, "map_no": map_no,
                                               "team_a": team_a, "team_b": team_b, "mode": mode, "map": map_name, "score_a": int(score_a),
                                               "score_b": int(score_b), "winner": winner, "length_sec": length_sec, "board": board,
                                               "date": t.get("date")}, upsert=True)
    db.t_player_matches.delete_many({"map_id": map_id})
    docs = []
    for r in rows:
        d = {"_id": f"{map_id}-{r['player']}", "tournament_id": tid, "title": t.get("title"), "map_id": map_id, "bmatch": bmatch,
             "player": r["player"], "team": r["team"], "team_id": team_a if r["team"] == "A" else team_b, "mode": mode, "map": map_name,
             "result": "W" if r["team"] == winner else "L"}
        d.update({k: v for k, v in r.items() if k not in ("player", "team")})
        docs.append(d)
    if docs:
        db.t_player_matches.insert_many(docs)
    refresh()
    return map_id


def delete_tmap(map_id: str) -> None:
    db = _db(); db.t_matches.delete_one({"_id": map_id}); db.t_player_matches.delete_many({"map_id": map_id}); refresh()


def clear_tmatch(tid: str, bmatch: str) -> None:
    """Undo a bracket match: its maps, player stats and any winner-only result."""
    db = _db()
    db.t_matches.delete_many({"tournament_id": tid, "bmatch": bmatch})
    db.t_player_matches.delete_many({"tournament_id": tid, "bmatch": bmatch})
    db.tournaments.update_one({"_id": tid}, {"$unset": {f"manual.{bmatch}": ""}})
    refresh()