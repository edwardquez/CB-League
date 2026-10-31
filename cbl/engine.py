"""One place that turns the raw documents into every number the pages show.

Engine(data, title) where title is a title id ("BO7") or None for all time.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property

import numpy as np
import pandas as pd

from cbl.stats import frame, mar as marmod


@dataclass
class Engine:
    data: dict
    title: str | None
    _cache: dict = field(default_factory=dict, repr=False)

    # ------------------------------------------------------------ base
    @cached_property
    def titles(self) -> dict:
        return {t["_id"]: t for t in self.data.get("titles", [])}

    @cached_property
    def _all(self):
        s = frame.series_frame(self.data.get("series", []), self.data.get("matches", []))
        m = frame.map_frame(self.data.get("matches", []), s)
        pm = frame.player_frame(self.data.get("player_matches", []), m)
        parts = []
        for tid in sorted(pm["title"].unique(), key=lambda t: self.titles.get(t, {}).get("order", 0)) if len(pm) else []:
            cfg = self.titles.get(tid) or {}
            sub = pm[pm.title == tid]
            borrow = self.titles.get(cfg.get("borrow_from")) if cfg.get("borrow_from") else None
            bpm = pm[pm.title == cfg.get("borrow_from")] if borrow else None
            if bpm is not None and len(bpm):
                bpm = bpm.copy()
            parts.append(marmod.compute(sub, cfg, borrow, bpm))
        pm = pd.concat(parts) if parts else marmod.compute(pm, {"mar": {"modes": {}}})
        press = frame.pressure_flags(s, m)
        pm["press"] = pm["match_id"].map(press).fillna(False).astype(bool)
        m["press"] = m["_id"].map(press).fillna(False).astype(bool)
        return s, m, pm

    @cached_property
    def series(self) -> pd.DataFrame:
        s = self._all[0]
        return s if self.title is None else s[s.title == self.title].reset_index(drop=True)

    @cached_property
    def maps(self) -> pd.DataFrame:
        m = self._all[1]
        return m if self.title is None else m[m.title == self.title].reset_index(drop=True)

    @cached_property
    def pm(self) -> pd.DataFrame:
        pm = self._all[2]
        pm = pm if self.title is None else pm[pm.title == self.title]
        return pm.sort_values(["title", "seq", "team", "player"]).reset_index(drop=True)

    @property
    def empty(self) -> bool:
        return self.pm.empty

    @cached_property
    def players(self) -> list[str]:
        """Players ordered by maps played, then name."""
        if self.empty:
            return []
        n = self.pm.groupby("player").size()
        return sorted(n.index, key=lambda p: (-n[p], p))

    def nmaps(self, p: str) -> int:
        return int((self.pm.player == p).sum())

    # ------------------------------------------------------------ series
    def series_mar(self) -> pd.DataFrame:
        return self.pm.groupby(["series_id", "player"]).mar.sum().reset_index()

    def series_mvps(self) -> dict:
        sm = self.series_mar()
        if sm.empty:
            return {}
        top = sm.sort_values("mar", ascending=False).groupby("series_id").head(1)
        return {r.series_id: (r.player, float(r.mar)) for r in top.itertuples()}

    def lineup_key(self, players) -> str:
        return "|".join(sorted(players))

    def rivalry_record(self, x: list[str], y: list[str]) -> tuple[int, int, int, int]:
        """(series won by x, by y, maps won by x, by y) for two exact lineups."""
        kx, ky = self.lineup_key(x), self.lineup_key(y)
        sx = sy = mx = my = 0
        for r in self.series.itertuples():
            a, b = self.lineup_key(r.team_a), self.lineup_key(r.team_b)
            if {a, b} != {kx, ky}:
                continue
            xa = a == kx
            if r.winner == ("A" if xa else "B"):
                sx += 1
            elif r.winner in ("A", "B"):
                sy += 1
            mx += r.wins_a if xa else r.wins_b
            my += r.wins_b if xa else r.wins_a
        return sx, sy, mx, my

    # ------------------------------------------------------------ tables
    def scope(self, mode: str | None = None) -> pd.DataFrame:
        return self.pm if mode in (None, "ALL") else self.pm[self.pm["mode"] == mode]

    def standings(self, mode: str | None = None) -> pd.DataFrame:
        d = self.scope(mode)
        if d.empty:
            return pd.DataFrame()
        g = d.groupby("player")
        t = pd.DataFrame({"n": g.size(), "w": g.result.apply(lambda s: int((s == "W").sum())), "mar": g.mar.sum(),
                          "mpm": g.mar.mean(), "k": g.kills.sum(), "d": g.deaths.sum(), "kpm": g.kills.mean(),
                          "dpm": g.deaths.mean(), "dmg": g.damage.mean(), "stk": g.highest_streak.max(),
                          "apm": g.assists.mean(), "ntk": g.non_traded_kills.mean()})
        t["kd"] = t.k / t.d.clip(lower=1); t["pm"] = t.k - t.d; t["wp"] = t.w / t.n
        if mode == "HP":
            t["hill"] = g.hill_time.mean(); t["obj"] = g.objective_kills.mean()
        if mode == "SND":
            t["fb"] = g.first_bloods.sum(); t["fd"] = g.first_deaths.sum(); t["pl"] = g.bombs_planted.sum()
        if mode == "OVL":
            t["ovl"] = g.overloads.sum(); t["ck"] = g.carrier_kills.sum(); t["kac"] = g.kills_as_carrier.sum()
        fin = self.finishing_frame()
        if len(fin):
            f = fin if mode in (None, "ALL") else fin[fin["mode"] == mode]
            t["fin"] = f.groupby("player").fin.mean()
        return t

    def finishing_frame(self) -> pd.DataFrame:
        if "fin" not in self._cache:
            from cbl.stats import profile
            parts, fits = [], {}
            for tid, sub in self.pm.groupby("title"):
                fd, ft = profile.finishing(sub); parts.append(fd); fits.update({(tid, k): v for k, v in ft.items()})
            self._cache["fin"] = pd.concat(parts) if parts else pd.DataFrame()
            self._cache["fits"] = fits
        return self._cache["fin"]

    @cached_property
    def regulars(self) -> list[str]:
        """Players with at least half the most maps anyone played."""
        if self.empty:
            return []
        n = self.pm.groupby("player").size()
        return [p for p in self.players if n[p] >= 0.5 * n.max()]

    def profile(self):
        if "profile" not in self._cache:
            from cbl.stats import profile as pf
            d = self.pm
            sp, det = pf.spokes(d, self.players)
            ch = pf.chips(d, det, self.players, self.regulars)
            half = d.series_no.max() // 2
            h1, _ = pf.spokes(d[d.series_no <= half], self.players)
            h2, _ = pf.spokes(d[d.series_no > half], self.players)
            self._cache["profile"] = {"sp": sp, "det": det, "raw": pf.raw_lines(det), "chips": ch, "h1": h1, "h2": h2,
                                      "n1": d[d.series_no <= half].groupby("player").size().to_dict(),
                                      "n2": d[d.series_no > half].groupby("player").size().to_dict()}
        return self._cache["profile"]

    def ratings(self):
        if "ratings" not in self._cache:
            from cbl.stats import profile as pf
            self._cache["ratings"] = pf.ratings(self.pm, self.players)
        return self._cache["ratings"]
