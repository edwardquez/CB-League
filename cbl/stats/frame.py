"""Turn database documents into the per-map player table every stat uses."""
from __future__ import annotations

import pandas as pd

STAT_COLS = ["kills", "deaths", "assists", "non_traded_kills", "highest_streak", "damage", "hill_time",
             "objective_kills", "first_bloods", "first_deaths", "bombs_planted", "overloads",
             "carrier_kills", "kills_as_carrier", "accuracy", "avg_hill_time", "contested_hill_time", "kills_per_hill",
             "dmg_per_hill", "bombs_defused", "kills_per_round", "dmg_per_round",
             "data_uploaded", "hj_plants", "dunks", "remote_plants", "passes", "interceptions"]


def series_frame(series: list[dict], matches: list[dict]) -> pd.DataFrame:
    s = pd.DataFrame(series)
    if s.empty:
        return pd.DataFrame(columns=["_id", "title", "series_no", "date", "format", "best_of", "team_a", "team_b",
                                     "wins_a", "wins_b", "maps_played", "winner", "complete", "ended_early"])
    s["date"] = pd.to_datetime(s["date"])
    m = pd.DataFrame(matches)
    if m.empty:
        s["wins_a"] = 0; s["wins_b"] = 0
    else:
        w = m.groupby("series_id")["winner"].value_counts().unstack(fill_value=0).reindex(columns=["A", "B"], fill_value=0)
        s = s.merge(w.rename(columns={"A": "wins_a", "B": "wins_b"}), left_on="_id", right_index=True, how="left")
        s[["wins_a", "wins_b"]] = s[["wins_a", "wins_b"]].fillna(0).astype(int)
    need = s["best_of"] // 2 + 1
    s["maps_played"] = s["wins_a"] + s["wins_b"]
    s["complete"] = (s["wins_a"] >= need) | (s["wins_b"] >= need)
    # result: from the maps, unless the series was ended early (Scorekeeper records who gets it)
    s["winner"] = None
    s.loc[s.wins_a > s.wins_b, "winner"] = "A"
    s.loc[s.wins_b > s.wins_a, "winner"] = "B"
    if "result_override" in s.columns:
        ov = s["result_override"].where(s["result_override"].notna(), None)
        s.loc[ov.isin(["A", "B"]), "winner"] = ov[ov.isin(["A", "B"])]
        s.loc[ov == "N", "winner"] = None
    for c in ("public_note", "private_note", "status", "result_override"):
        if c not in s:
            s[c] = None
    s["status"] = s["status"].fillna("closed")
    s["ended_early"] = (s["status"] == "closed") & (~s["complete"]) & (s["maps_played"] > 0)
    return s.sort_values(["title", "series_no"]).reset_index(drop=True)


def map_frame(matches: list[dict], s: pd.DataFrame) -> pd.DataFrame:
    m = pd.DataFrame(matches)
    if m.empty:
        return pd.DataFrame(columns=["_id", "title", "series_id", "map_no", "mode", "map", "score_a", "score_b",
                                     "winner", "series_no", "date", "seq", "length_sec"])
    m = m.merge(s[["_id", "series_no", "date"]].rename(columns={"_id": "series_id"}), on="series_id", how="left")
    m = m.sort_values(["title", "series_no", "map_no"]).reset_index(drop=True)
    m["seq"] = m.groupby("title").cumcount()
    if "length_sec" not in m:
        m["length_sec"] = None
    return m


def player_frame(pms: list[dict], m: pd.DataFrame) -> pd.DataFrame:
    pm = pd.DataFrame(pms)
    if pm.empty:
        return pd.DataFrame(columns=["_id", "title", "series_id", "match_id", "player", "team", "mode", "map",
                                     "result"] + STAT_COLS + ["series_no", "map_no", "date", "seq", "team_size", "lob", "net"])
    for c in STAT_COLS:
        if c not in pm:
            pm[c] = None
        pm[c] = pd.to_numeric(pm[c], errors="coerce")
    pm = pm.merge(m[["_id", "series_no", "map_no", "date", "seq", "length_sec"]].rename(columns={"_id": "match_id"}),
                  on="match_id", how="left")
    pm["team_size"] = pm.groupby(["match_id", "team"]).player.transform("size")
    pm["lob"] = pm["team_size"].map(lambda n: f"{n}v{n}")
    pm["net"] = pm["kills"] - pm["deaths"]
    pm["fbnet"] = (pm["first_bloods"] - pm["first_deaths"]).fillna(0)
    return pm.sort_values(["seq", "team", "player"]).reset_index(drop=True)


def pressure_flags(s: pd.DataFrame, m: pd.DataFrame) -> dict:
    """A map is a pressure map when either team could clinch the series on it,
    or it was close (Hardpoint by 25 or fewer, SnD 6-5, Overload by 1)."""
    out = {}
    for sid, grp in m.groupby("series_id"):
        row = s[s._id == sid]
        if row.empty:
            continue
        need = int(row.iloc[0].best_of) // 2 + 1
        wa = wb = 0
        for _, r in grp.sort_values("map_no").iterrows():
            mg = abs(r.score_a - r.score_b)
            close = (r["mode"] == "HP" and mg <= 25) or (r["mode"] == "SND" and {r.score_a, r.score_b} == {6, 5}) \
                or (r["mode"] == "OVL" and mg == 1)
            out[r["_id"]] = bool((wa == need - 1 or wb == need - 1) or close)
            wa += r.winner == "A"; wb += r.winner == "B"
    return out