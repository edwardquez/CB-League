"""MAR: Maps Above Replacement.

For every player on every map:

1. Kill-equivalents (KE) = net kills + objective + playmaking. Objective and
   playmaking stats are compared with the 3v3 average for that mode; on 4v4
   maps, team-shared objective stats are compared with three-quarters of it.
2. Subtract the replacement level (20th-percentile KE for the mode).
3. Divide by kills-per-win: how many KE swing one map in that mode. 4v4 maps
   are won by bigger margins, so their kills-per-win is scaled up.

Uncalibrated titles (a new game) borrow kills-per-win and the replacement
level from the previous title and blend their own in at n / (n + 8) maps.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# stats a whole team shares (scale with team size); assists/first bloods don't
TEAM_SHARED = ("hill_time", "overloads", "carrier_kills", "bombs_planted", "kills_as_carrier")


def _fill(pm: pd.DataFrame, col: str) -> pd.Series:
    """Unknown (blank) stats -> that player's average in the mode, else 0."""
    if col not in pm:
        return pd.Series(0.0, index=pm.index)
    s = pm[col].astype(float)
    return s.fillna(pm.groupby(["player", "mode"])[col].transform("mean")).fillna(0.0)


def compute(pm: pd.DataFrame, title_cfg: dict, borrow_cfg: dict | None = None,
            borrow_pm: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return pm with columns ke, mar and the breakdown c_net/c_obj/c_play/c_repl."""
    pm = pm.copy()
    if pm.empty:
        for c in ("ke", "mar", "c_net", "c_obj", "c_play", "c_repl", "kpw"):
            pm[c] = pd.Series(dtype=float)
        return pm
    m = title_cfg["mar"]
    ast_w = float(m.get("assist", 0.25))
    a = _fill(pm, "assists")
    ck = _fill(pm, "carrier_kills")
    kac = _fill(pm, "kills_as_carrier")
    pl = pm["bombs_planted"].astype(float).fillna(0.0) if "bombs_planted" in pm else 0.0 * a
    fbn = (pm.get("first_bloods") - pm.get("first_deaths")).astype(float).fillna(0.0) if "first_bloods" in pm else 0.0 * a
    hill = pm["hill_time"].astype(float).fillna(0.0) if "hill_time" in pm else 0.0 * a
    ovl = pm["overloads"].astype(float).fillna(0.0) if "overloads" in pm else 0.0 * a
    work = pd.DataFrame({"a": a, "ck": ck, "kac": kac, "pl": pl, "fbn": fbn, "hill": hill, "ovl": ovl,
                         "mode": pm["mode"], "lob": pm["lob"]})
    f = 3.0 / pm["team_size"].astype(float)
    av3 = work[work.lob == "3v3"].groupby("mode")[["a", "ck", "kac", "pl", "fbn", "hill", "ovl"]].mean()
    if borrow_pm is not None and len(borrow_pm):  # modes with no 3v3 maps yet: borrow averages
        bw = borrow_pm
        bav = pd.DataFrame({"a": _fill(bw, "assists"), "ck": _fill(bw, "carrier_kills"), "kac": _fill(bw, "kills_as_carrier"),
                            "pl": bw["bombs_planted"].fillna(0), "fbn": (bw.first_bloods - bw.first_deaths).fillna(0),
                            "hill": bw.hill_time.fillna(0), "ovl": bw.overloads.fillna(0), "mode": bw["mode"], "lob": bw["lob"]})
        bav = bav[bav.lob == "3v3"].groupby("mode")[["a", "ck", "kac", "pl", "fbn", "hill", "ovl"]].mean()
        av3 = av3.combine_first(bav)
    b = lambda c: pm["mode"].map(av3[c]).fillna(0.0) if c in av3 else pd.Series(0.0, index=pm.index)  # noqa: E731

    # conversions can change mid-season; each map uses the values in force on its date
    versions = sorted(title_cfg.get("mar_versions") or [{"from": "1900-01-01", **m}], key=lambda v: v["from"])
    dates = pd.to_datetime(pm["date"]).fillna(pd.Timestamp("2100-01-01"))
    obj = pd.Series(0.0, index=pm.index); play = pd.Series(0.0, index=pm.index)
    for i, v in enumerate(versions):
        lo = pd.Timestamp(v["from"]); hi = pd.Timestamp(versions[i + 1]["from"]) if i + 1 < len(versions) else pd.Timestamp("2200-01-01")
        sel = (dates >= lo) & (dates < hi) if i else (dates < hi)
        if not sel.any():
            continue
        vm = v.get("modes", {}); aw = float(v.get("assist", ast_w))
        g = lambda key: pm.loc[sel, "mode"].map({mo: float((vm.get(mo) or {}).get(key) or 0) for mo in pm["mode"].unique()}).fillna(0.0)  # noqa: E731
        hs = g("hill_sec_per_kill"); ss = sel
        o = np.where(hs > 0, (hill[ss] - b("hill")[ss] * f[ss]) / hs.replace(0, np.nan), 0.0)
        o = pd.Series(np.nan_to_num(o), index=hs.index) + g("overload") * (ovl[ss] - b("ovl")[ss] * f[ss]) \
            + g("carrier_kill") * (ck[ss] - b("ck")[ss] * f[ss]) + g("plant") * (pl[ss] - b("pl")[ss] * f[ss])
        q = aw * (a[ss] - b("a")[ss]) + g("fb_margin") * (fbn[ss] - b("fbn")[ss]) + g("kill_as_carrier") * (kac[ss] - b("kac")[ss] * f[ss])
        obj[ss] = o; play[ss] = q
    conv = {mo: m["modes"].get(mo, {}) for mo in pm["mode"].unique()}
    net = (pm["kills"] - pm["deaths"]).astype(float)
    ke = net + obj + play
    pm["ke"] = ke

    # kills-per-win (3v3) and replacement level per mode
    base_kpw, base_rep = {}, {}
    prov_n = int(title_cfg.get("provisional_maps", 8))
    for mo in pm["mode"].unique():
        own = conv.get(mo, {})
        mode_cfg = title_cfg["modes"].get(mo, {})
        src_mode = mode_cfg.get("borrow_mode", mo)
        bconv = (borrow_cfg or {}).get("mar", {}).get("modes", {}).get(src_mode, {})
        own_rep = float(np.percentile(ke[pm["mode"] == mo], 20))
        if title_cfg.get("calibrated", False) and own.get("kpw"):
            base_kpw[mo] = float(own["kpw"]); base_rep[mo] = own_rep
        else:
            n = pm.loc[pm["mode"] == mo, "match_id"].nunique(); w = n / (n + prov_n)
            kpw_b = float(own.get("kpw") or bconv.get("kpw") or 60.0)
            rep_b = float(bconv.get("replacement", own_rep))
            base_kpw[mo] = kpw_b  # kills-per-win can't be fit from a handful of maps; keep borrowed value
            base_rep[mo] = w * own_rep + (1 - w) * rep_b

    # 4v4 kills-per-win: prior ratio blended with the observed margin ratio
    prior = m.get("lobby_prior", {}); k = float(m.get("lobby_k", 10))
    t = pd.DataFrame({"ke": ke, "match_id": pm.match_id, "team": pm.team}).groupby(["match_id", "team"]).ke.sum().unstack()
    t["absd"] = (t.get("A", 0) - t.get("B", 0)).abs()
    t = t.join(pm.groupby("match_id")[["mode", "lob"]].first())
    ratio = {}
    for mo in pm["mode"].unique():
        p = float(prior.get(mo, 4 / 3))
        x3 = t[(t["mode"] == mo) & (t.lob == "3v3")].absd; x4 = t[(t["mode"] == mo) & (t.lob == "4v4")].absd
        n4 = len(x4)
        if n4 and len(x3) and x3.mean() > 0:
            w = n4 / (n4 + k); ratio[mo] = w * (x4.mean() / x3.mean()) + (1 - w) * p
        else:
            ratio[mo] = p
    kpw = pm["mode"].map(base_kpw) * np.where(pm["lob"] == "4v4", pm["mode"].map(ratio), 1.0)
    rep = pm["mode"].map(base_rep)
    pm["kpw"] = kpw
    pm["mar"] = (ke - rep) / kpw
    pm["c_net"] = net / kpw
    pm["c_obj"] = obj / kpw
    pm["c_play"] = play / kpw
    pm["c_repl"] = -rep / kpw
    pm.attrs["kpw_4v4"] = {mo: base_kpw[mo] * ratio[mo] for mo in base_kpw}
    pm.attrs["replacement"] = base_rep
    pm.attrs["avg3"] = av3.to_dict()
    return pm
