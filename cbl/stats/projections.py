"""Stat projections (Edward's props model, without the betting framing).

For a player, mode and map:
1. Bootstrap the player's average from their past maps (20,000 resamples).
2. Blend map history with mode history: the map counts n / (n + 5).
3. Simulate the map: kills, first bloods and overloads as Poisson counts;
   damage and hill time with the player's own real map-to-map swings
   (borrowing league swings, fading out, while they have under 8 maps).
4. Expected = mean of the simulations; likely range = middle 80% (for small
   whole-number stats, the narrowest whole-number range covering 80%).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

K = 5
COUNT = {"kills", "first_bloods", "overloads"}
SMALL = {"first_bloods", "overloads"}
STATS = {"HP": ["kills", "damage", "hill_time"], "SND": ["kills", "damage", "first_bloods"],
         "OVL": ["kills", "damage", "overloads"], "HJ": ["kills", "damage"]}


def stats_for(mode: str) -> list[str]:
    return STATS.get(mode, ["kills", "damage"])


def hdi_int(d: np.ndarray, p: float = 0.8) -> tuple[float, float]:
    vals, cnt = np.unique(d, return_counts=True); pr = cnt / cnt.sum(); best = None
    for i in range(len(vals)):
        c = 0
        for j in range(i, len(vals)):
            c += pr[j]
            if c >= p:
                if best is None or vals[j] - vals[i] < best[1] - best[0] or (vals[j] - vals[i] == best[1] - best[0] and c > best[2]):
                    best = (vals[i], vals[j], c)
                break
    return float(best[0]), float(best[1])


def league_swings(pm: pd.DataFrame) -> dict:
    out = {}
    for mo in pm["mode"].unique():
        for st in ("damage", "hill_time"):
            d = pm[pm["mode"] == mo].dropna(subset=[st])
            if len(d):
                out[(mo, st)] = ((d[st] - d.groupby("player")[st].transform("mean")).values, float(d[st].mean()))
    return out


def simulate(map_vals, mode_vals, stat, lg, rng, n=20000):
    map_vals = np.asarray(map_vals, float); mode_vals = np.asarray(mode_vals, float)
    w = len(map_vals) / (len(map_vals) + K)
    mr = rng.choice(mode_vals, size=(n, len(mode_vals))).mean(1)
    mp = rng.choice(map_vals, size=(n, len(map_vals))).mean(1) if len(map_vals) else mr
    rate = np.where((rng.random(n) < w) & (len(map_vals) > 0), mp, mr).clip(0.01)
    if stat in COUNT:
        return rng.poisson(rate), w
    own = rng.choice(mode_vals - mode_vals.mean(), size=n)
    if len(mode_vals) < 8 and lg is not None and lg[1] > 0:
        borrow = rng.random(n) < (8 - len(mode_vals)) / 8
        own = np.where(borrow, rng.choice(lg[0], size=n) * mode_vals.mean() / lg[1], own)
    return np.clip(rate + own, 0, None), w


def summarize(d: np.ndarray, stat: str, w: float, nmap: int, nmode: int) -> dict:
    lo, hi = hdi_int(d) if stat in SMALL else tuple(np.percentile(d, [10, 90]))
    if stat in COUNT:
        top = int(np.percentile(d, 99.5)) + 1
        cdf = [float((d >= k).mean()) for k in range(0, top + 1)]
    else:
        cdf = [float(x) for x in np.percentile(d, np.arange(0, 101, 5))]
    return {"e": float(d.mean()), "lo": float(lo), "hi": float(hi), "nm": nmap, "nmo": nmode, "w": w, "cdf": cdf}


def project(pm: pd.DataFrame, player: str, mode: str, map_name: str | None, stats=None, seed=42, n=20000, lg=None) -> dict:
    rng = np.random.default_rng(seed)
    lg = league_swings(pm) if lg is None else lg
    out = {}
    for st in stats or stats_for(mode):
        mv = pm[(pm.player == player) & (pm["mode"] == mode)][st].dropna().values
        if len(mv) == 0:
            continue
        mapv = np.array([]) if not map_name else pm[(pm.player == player) & (pm["mode"] == mode) & (pm["map"] == map_name)][st].dropna().values
        d, w = simulate(mapv, mv, st, lg.get((mode, st)), rng, n)
        out[st] = summarize(d, st, w, len(mapv), len(mv))
    return out


def reach(r: dict, stat: str, x: float) -> float:
    c = r["cdf"]
    if stat in COUNT:
        k = max(0, int(round(x)))
        return c[k] if k < len(c) else 0.0
    if x <= c[0]:
        return 1.0
    if x >= c[-1]:
        return 0.0
    for i in range(20):
        if x <= c[i + 1]:
            f = 0 if c[i + 1] == c[i] else (x - c[i]) / (c[i + 1] - c[i])
            return 1 - (i + f) * 0.05
    return 0.0


def backtest(pm: pd.DataFrame, seed=7, n=4000) -> pd.DataFrame:
    """Re-project every second-half map using only earlier maps."""
    rng = np.random.default_rng(seed)
    pm = pm.copy(); pm["ord"] = pm.seq * 100 + pm.map_no
    if pm.empty:
        return pd.DataFrame()
    cut = pm.ord.quantile(0.5); lg = league_swings(pm)
    rows = []
    for _, r in pm[pm.ord > cut].iterrows():
        hist = pm[(pm.player == r.player) & (pm.ord < r.ord)]
        for st in stats_for(r["mode"]):
            if pd.isna(r[st]):
                continue
            mv = hist[hist["mode"] == r["mode"]][st].dropna().values
            if len(mv) < 1:
                continue
            mapv = hist[(hist["mode"] == r["mode"]) & (hist["map"] == r["map"])][st].dropna().values
            d, _ = simulate(mapv, mv, st, lg.get((r["mode"], st)), rng, n)
            lo, hi = hdi_int(d) if st in SMALL else np.percentile(d, [10, 90])
            rows.append({"player": r.player, "series": int(r.series_no), "map": r["map"], "mode": r["mode"], "stat": st,
                         "e": float(d.mean()), "lo": float(lo), "hi": float(hi), "act": float(r[st])})
    return pd.DataFrame(rows)
