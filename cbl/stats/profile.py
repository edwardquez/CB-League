"""Playstyle radar, signature chips, archetypes, clutch, ratings, Finishing, fight profile."""
from __future__ import annotations

import numpy as np
import pandas as pd

SPOKES = ["Slaying", "Objective", "Playmaking", "Defense", "Clutch", "Steadiness"]
SPOKE_HELP = ["Kills, K/D and damage combined.", "Hill time (counts double) and overloads.",
              "First bloods, plants, kills while carrying.", "Carrier kills, untraded kills, staying alive.",
              "How much better on pressure maps than other maps.", "Mostly avoiding bad nights (70%), plus good maps (30%)."]


def pr(s: pd.Series, low: bool = False) -> pd.Series:
    """Rank as 0-100 among players who have the stat."""
    s = s.dropna()
    if len(s) < 2:
        return s * 0 + 50
    r = s.rank(ascending=not low)
    return (r - 1) / (len(s) - 1) * 100


def _fill(d, col):
    return d[col].fillna(d.groupby(["player", "mode"])[col].transform("mean")).fillna(0)


def spokes(d: pd.DataFrame, players: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    d = d.copy()
    d["ck"] = _fill(d, "carrier_kills"); d["kac"] = _fill(d, "kills_as_carrier"); d["pl"] = d.bombs_planted.fillna(0)
    gg = d.groupby("player"); kd = gg.kills.sum() / gg.deaths.sum().clip(lower=1)
    sl = pr((pr(gg.kills.mean()) + pr(kd) + pr(gg.damage.mean())) / 3)
    hp = d[d["mode"] == "HP"].groupby("player").hill_time.mean()
    ovl = d[d["mode"] == "OVL"].groupby("player").overloads.mean()
    ckk = d[d["mode"] == "OVL"].groupby("player").ck.mean()
    if len(hp) and len(ovl):
        ob = pr((2 * pr(hp) + pr(ovl)) / 3)
    else:
        ob = pr(hp) if len(hp) else (pr(ovl) if len(ovl) else pd.Series(dtype=float))
    sn = d[d["mode"] == "SND"].groupby("player"); kacs = d[d["mode"] == "OVL"].groupby("player").kac.mean()
    pmk = pr((pr(sn.first_bloods.mean()) + pr(sn.pl.mean()) + pr(kacs)) / 3)
    nts = gg.non_traded_kills.sum() / gg.kills.sum().clip(lower=1)
    de = pr((pr(ckk) + pr(nts) + pr(gg.deaths.mean(), True)) / 3)
    stepup = d.groupby(["player", "press"]).mar.mean().unstack()
    for c in (True, False):
        if c not in stepup:
            stepup[c] = np.nan
    cl = pr(stepup[True] - stepup[False])
    med = d.groupby("mode").mar.transform("median")
    dd = d.assign(good=(d.mar > med).astype(int), norm=d.groupby("player").mar.transform("mean"))
    dd["dud"] = (((dd.norm - dd.mar) > 0.7 * d.mar.std()) & (dd.mar < med)).astype(int)
    st = dd.groupby("player").agg(n=("dud", "size"), dud=("dud", "mean"), good=("good", "mean"))
    raw = 0.7 * (100 - st.dud * 100) + 0.3 * (st.good * 100)
    avg = (raw * st.n).sum() / st.n.sum()
    stdy = (raw * st.n + avg * 4) / (st.n + 4)
    sp = pd.DataFrame({"Slaying": sl, "Objective": ob, "Playmaking": pmk, "Defense": de, "Clutch": cl,
                       "Steadiness": stdy}).reindex(players).fillna(50).round().astype(int)
    det = pd.DataFrame({"kpm": gg.kills.mean(), "kd": kd, "dmg": gg.damage.mean(), "hill": hp, "ovl": ovl, "ck": ckk,
                        "fb": sn.first_bloods.mean(), "pl": sn.pl.mean(), "kac": kacs, "nts": nts, "dpm": gg.deaths.mean(),
                        "cp": stepup[True], "co": stepup[False], "npress": d[d.press].groupby("player").size(),
                        "dud": st.dud * 100, "good": st.good * 100, "n": st.n}).reindex(players)
    return sp, det


def raw_lines(det: pd.DataFrame) -> dict:
    fm = lambda v, f: "—" if pd.isna(v) else f(v)  # noqa: E731
    mmss = lambda v: f"{int(v) // 60}:{int(v) % 60:02d}"  # noqa: E731
    out = {}
    for p, r in det.iterrows():
        out[p] = [f"{r.kpm:.1f} kills/map · {r.kd:.2f} K/D · {r.dmg:,.0f} damage/map",
                  f"Hill {fm(r.hill, mmss)}/map · {fm(r.ovl, lambda v: f'{v:.2f}')} overloads/map",
                  f"{fm(r.fb, lambda v: f'{v:.2f}')} first bloods · {fm(r.pl, lambda v: f'{v:.2f}')} plants · {fm(r.kac, lambda v: f'{v:.2f}')} kills as carrier",
                  f"{fm(r.ck, lambda v: f'{v:.1f}')} carrier kills · {r.nts * 100:.0f}% kills untraded · {r.dpm:.1f} deaths/map",
                  f"Pressure maps {fm(r.cp, lambda v: f'{v:+.2f}')} vs other maps {fm(r.co, lambda v: f'{v:+.2f}')} MAR/map ({0 if pd.isna(r.npress) else int(r.npress)} pressure maps)",
                  f"Bad nights {r.dud:.0f}% · Good maps {r.good:.0f}% ({int(r.n)} maps)"]
    return out


def chip_stats(d: pd.DataFrame, det: pd.DataFrame, players: list[str]) -> dict:
    d = d.copy(); d["ck"] = _fill(d, "carrier_kills"); d["kac"] = _fill(d, "kills_as_carrier"); d["pl"] = d.bombs_planted.fillna(0)
    gg = d.groupby("player"); kd = gg.kills.sum() / gg.deaths.sum().clip(lower=1)
    sn = d[d["mode"] == "SND"].groupby("player"); ovg = d[d["mode"] == "OVL"].groupby("player"); hpg = d[d["mode"] == "HP"].groupby("player")
    med = d.groupby("mode").mar.transform("median"); good = d.assign(g=(d.mar > med)).groupby("player").g.mean()

    def modekd(mo):
        x = d[d["mode"] == mo]
        return x.groupby("player").kills.sum() / x.groupby("player").deaths.sum().clip(lower=1)

    def modewin(mo):
        x = d[d["mode"] == mo]
        return x.groupby("player").result.apply(lambda s: (s == "W").mean())
    return {"Kills/map": gg.kills.mean(), "K/D": kd, "Damage/map": gg.damage.mean(), "MAR/map": gg.mar.mean(),
            "Win %": gg.result.apply(lambda s: (s == "W").mean()), "HP K/D": modekd("HP"), "SnD K/D": modekd("SND"),
            "Overload K/D": modekd("OVL"), "SnD win %": modewin("SND"), "Overload win %": modewin("OVL"),
            "Hardpoint win %": modewin("HP"), "Hill time": hpg.hill_time.mean(), "Overloads": ovg.overloads.mean(),
            "Carrier kills": ovg.ck.mean(), "Kills as carrier": ovg.kac.mean(), "Plants": sn.pl.mean(),
            "First bloods": sn.first_bloods.mean(), "Fewest first deaths": -sn.first_deaths.mean(),
            "Assists/map": gg.assists.mean(), "Good-map rate": good,
            "Clutch step-up": pd.Series({p: det.loc[p, "cp"] - det.loc[p, "co"] for p in players})}


def chips(d: pd.DataFrame, det: pd.DataFrame, players: list[str], regulars: list[str]) -> dict:
    """#1 / #2 among the regulars (plus the player themself)."""
    stats = chip_stats(d, det, players)
    out = {}
    for p in players:
        pool = list(dict.fromkeys(regulars + [p])); got = []
        for k, s in stats.items():
            s = s.reindex(pool)
            if pd.isna(s.get(p)):
                continue
            rk = int(s.rank(ascending=False, method="min")[p])
            if rk <= 2:
                got.append((rk, k))
        got.sort(key=lambda t: t[0])
        out[p] = [f"#{r} {k}" for r, k in got]
    return out


def archetype(sp: pd.Series, n: int) -> tuple[str, str]:
    """Generated label for titles without hand-written archetypes."""
    top = sp.sort_values(ascending=False)
    a, b = top.index[0], top.index[1]
    if n < 10 and top.iloc[0] < 60:
        return "Developing", "Still building a profile. Small sample."
    names = {("Slaying", "Defense"): "Two-Way Star", ("Slaying", "Playmaking"): "Franchise Player",
             ("Slaying", "Clutch"): "Ace", ("Objective", "Steadiness"): "Objective Grinder",
             ("Objective", "Playmaking"): "Anchor", ("Playmaking", "Slaying"): "Spearhead",
             ("Defense", "Clutch"): "Enforcer"}
    label = names.get((a, b)) or names.get((b, a)) or {"Slaying": "Slayer", "Objective": "Anchor", "Playmaking": "Spearhead",
                                                       "Defense": "Enforcer", "Clutch": "Closer", "Steadiness": "Steady Hand"}[a]
    return label, f"Strongest at {a.lower()} and {b.lower()} this season."


def ratings(d: pd.DataFrame, players: list[str]) -> tuple[dict, dict]:
    """Matchup rating: every stat, best stretches count extra, recent maps a bit more."""
    d = d.copy()

    def z(col):
        g = d.groupby("mode")[col]
        return ((d[col] - g.transform("mean")) / g.transform("std")).fillna(0)
    d["a"] = d.assists.fillna(d.groupby(["player", "mode"]).assists.transform("mean"))
    d["obj"] = np.where(d["mode"] == "HP", d.hill_time, np.where(d["mode"] == "OVL", d.overloads,
                        d.fbnet.fillna(0) + d.bombs_planted.fillna(0) * 0.6))
    d["comp"] = 0.45 * z("mar") + 0.2 * z("net") + 0.15 * z("damage") + 0.15 * z("obj") + 0.05 * z("a")
    R, det = {}, {}
    for p in players:
        x = d[d.player == p].sort_values("seq"); n = len(x)
        if not n:
            continue
        w = np.linspace(0.6, 1.0, n)
        avg = np.average(x.comp, weights=w); peak = np.percentile(x.comp, 75)
        sc = (0.65 * avg + 0.35 * peak) * n / (n + 4)
        R[p] = int(round(1500 + 300 * sc)); det[p] = [n, round(avg, 2), round(peak, 2), round(n / (n + 4) * 100)]
    return R, det


def clutch(d: pd.DataFrame, players: list[str]) -> dict:
    out = {}
    for p in players:
        x = d[d.player == p]; a = x[x.press]; b = x[~x.press]
        kd = lambda y: round(y.kills.sum() / max(y.deaths.sum(), 1), 2)  # noqa: E731
        out[p] = [round(a.mar.mean(), 3) if len(a) else None, int(len(a)), round((a.result == "W").mean() * 100) if len(a) else None, kd(a),
                  round(b.mar.mean(), 3) if len(b) else None, int(len(b)), round((b.result == "W").mean() * 100) if len(b) else None, kd(b)]
    return out


def finishing(d: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Kills above expected: the league's damage-to-kills line per mode."""
    d = d[d.damage.notna()].copy()
    fits = {}
    for mo in d["mode"].unique():
        x = d[d["mode"] == mo]
        if len(x) < 5 or x.damage.std() == 0:
            continue
        b = np.polyfit(x.damage, x.kills, 1); fits[mo] = (float(b[0]), float(b[1]))
        d.loc[x.index, "xk"] = np.polyval(b, x.damage)
        d.loc[x.index, "dix"] = x.damage / x.damage.mean() - 1
    d = d[d.xk.notna()] if "xk" in d else d.iloc[0:0]
    if len(d):
        d["fin"] = d.kills - d.xk
    return d, fits


def fight(d: pd.DataFrame, players: list[str]) -> dict:
    """Fight win % overall and on pressure vs other maps (needs no match length).
    Fights per minute is only filled when match length was recorded."""
    out = {}
    fw = lambda y: y.kills.sum() / max((y.kills + y.deaths).sum(), 1) * 100  # noqa: E731
    for p in players:
        x = d[d.player == p]; a = x[x.press]; b = x[~x.press]
        L = x.length_sec.astype(float) / 60 if "length_sec" in x else pd.Series(dtype=float)
        epm = ((x.kills + x.deaths) / L).dropna() if len(L.dropna()) else pd.Series(dtype=float)
        out[p] = {"n": len(x), "fw": round(fw(x), 1), "pfw": round(fw(a), 1) if len(a) else None, "ofw": round(fw(b), 1) if len(b) else None,
                  "pn": len(a), "on": len(b), "epm": round(epm.mean(), 2) if len(epm) else None, "nlen": int(len(epm))}
    return out
