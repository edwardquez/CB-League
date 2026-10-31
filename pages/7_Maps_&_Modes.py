"""Maps & Modes: every map in the pool, how close it plays, and who plays it best."""
from collections import Counter

import streamlit as st

from cbl import data
from cbl.ui import page, styles as ui

page.start("Maps & Modes")
season = page.header("Maps & Modes")
tid = page.title_id(season)
e = data.engine(tid)
ts = data.titles()
NAMES = {"HP": "Hardpoint", "SND": "Search and Destroy", "OVL": "Overload", "HJ": "Hijack"}
SHORT = {"HP": "Hardpoint", "SND": "SnD", "OVL": "Overload", "HJ": "Hijack"}
COLS = {"HP": ui.INK, "SND": ui.BLUE, "OVL": ui.STEEL, "HJ": ui.SLATE}

if e.empty:
    ui.html(ui.empty_box(f"No {ts.get(season, {}).get('name', '')} maps yet",
                         "The map pool appears here once the season's settings are filled in and the first series is played."))
    st.stop()

M, pm, S = e.maps, e.pm, e.series
mc = M.groupby("mode").size()
modes = [k for k in ["HP", "SND", "OVL", "HJ"] if k in mc.index]
bar = "".join(f"<div style='flex:{mc[k]} 1 0; background:{COLS[k]}'></div>" for k in modes)
lab = "".join(f"<span>{NAMES[k]} {mc[k]}</span>" for k in modes)
ui.html(ui.label("Maps played by mode", margin_top=8) + f"<div role='img' style='display:flex; gap:3px; height:14px; margin-top:10px'>{bar}</div>"
        f"<div style='display:flex; justify-content:space-between; gap:8px; flex-wrap:wrap; margin-top:8px; font-size:13px'>{lab}</div><div style='height:28px'></div>")

mode = st.segmented_control("Mode", modes, default=modes[0], format_func=SHORT.get, key="mm_mode", label_visibility="collapsed") or modes[0]

# retired maps: retired in every title shown (or the selected title)
tids = [tid] if tid else list(M.title.unique())
retired = set()
for t in tids:
    mcfg = (ts.get(t, {}).get("modes") or {}).get(mode, {})
    retired |= {m["name"] for m in mcfg.get("maps", []) if m.get("status") == "retired"}
active_any = set()
for t in tids:
    mcfg = (ts.get(t, {}).get("modes") or {}).get(mode, {})
    active_any |= {m["name"] for m in mcfg.get("maps", []) if m.get("status") != "retired"}
retired -= active_any

mm = M[M["mode"] == mode].copy()
mm["gap"] = (mm.score_a - mm.score_b).abs()
g = mm.groupby("map").agg(n=("gap", "size"), margin=("gap", "mean")).sort_values("n", ascending=False)
d = pm[pm["mode"] == mode]
cfg = (ts.get(tids[-1], {}).get("modes") or {}).get(mode, {})
unit = (cfg.get("score_label") or "points").lower()
note = f"First to {cfg['win_score']} {unit}" if cfg.get("win_score") else f"Most {unit}"


def best_here(mp):
    x = d[d["map"] == mp].groupby("player").agg(n=("mar", "size"), m=("mar", "mean"))
    y = x[x.n >= 2] if (x.n >= 2).any() else x
    p = y.m.idxmax()
    return p, y.loc[p, "m"]


cards = ""
for mp, r in g.iterrows():
    p, v = best_here(mp)
    ret = mp in retired
    tag = (f"<span style='position:absolute; top:8px; left:8px; font-size:10px; font-weight:600; letter-spacing:0.8px; background:{ui.INK}; "
           f"color:{ui.BG}; padding:2px 6px'>RETIRED</span>") if ret else ""
    cards += (f"<div style='background:{ui.PANEL}; '><div style='position:relative'>{ui.img_tag(mp, 'card')}{tag}</div>"
              f"<div style='padding:12px 14px 14px'><div style='display:flex; justify-content:space-between; align-items:baseline; gap:8px; padding-bottom:8px; border-bottom:1px solid {ui.RULE}'>"
              f"<span style='font-size:18px; font-weight:600'>{mp}</span><span style='font-size:13px; color:{ui.MUTED}'>{int(r.n)} played</span></div>"
              f"<div style='display:grid; grid-template-columns:auto minmax(0,1fr); gap:10px 18px; margin-top:12px'>"
              f"<div><div style='font-size:11px; color:{ui.MUTED}'>Avg margin</div><div style='font-size:17px; margin-top:4px'>{r.margin:.1f}</div></div>"
              f"<div><div style='font-size:11px; color:{ui.MUTED}'>Best here</div><div style='font-size:16px; margin-top:4px; white-space:nowrap'><b style='font-weight:600'>{p}</b> "
              f"<span style='color:{ui.BLUE}; font-size:13px; font-weight:600'>{ui.sg(v, 2)}</span></div></div></div></div></div>")
ui.html(f"<div style='display:flex; justify-content:space-between; align-items:baseline; gap:6px 16px; flex-wrap:wrap; margin-top:32px; padding-bottom:8px; border-bottom:2px solid {ui.INK}'>"
        f"<div role='heading' class='cb-h2' style='font-weight:300; font-size:34px'>{NAMES[mode]} Maps</div>"
        f"<span style='font-size:13px; color:{ui.MUTED}'>{note}</span></div>"
        f"<div style='display:grid; grid-template-columns:repeat(auto-fill, minmax(min(200px, 100%), 1fr)); gap:14px; margin-top:16px'>{cards}</div>"
        + ui.note(f"Avg margin: average {unit} between the two teams. Best here: highest MAR per map among players with 2+ maps on it.", 10, 12))

# ---------------------------------------------------------------- main rivalry by map
cnt = Counter()
for r in S[S.maps_played > 0].itertuples():
    cnt[tuple(sorted((e.lineup_key(r.team_a), e.lineup_key(r.team_b))))] += 1
top = [k for k, v in cnt.most_common(1) if v >= 2]
if top:
    kx, ky = top[0]
    X, Y = kx.split("|"), ky.split("|")
    lk = {S.loc[r.Index, "_id"]: (e.lineup_key(r.team_a), e.lineup_key(r.team_b)) for r in S.itertuples()}
    rows = []
    for mp, r in g.iterrows():
        x = mm[mm["map"] == mp]
        wx = wy = 0
        for s, w in zip(x.series_id, x.winner):
            a, b = lk[s]
            if {a, b} != {kx, ky} or w not in ("A", "B"):
                continue
            if (w == "A") == (a == kx):
                wx += 1
            else:
                wy += 1
        played = wx + wy > 0
        ret = ui.tagbox("Retired") if mp in retired else ""
        cell = (f"<div style='display:grid; grid-template-columns:24px minmax(80px,1fr) 24px; gap:8px; align-items:center'>"
                f"<span style='text-align:right; color:{ui.BLUE}; font-weight:600'>{wx if played else '—'}</span>"
                f"<div style='display:flex; gap:2px; height:10px; background:{'transparent' if played else ui.TRACK}'>"
                f"<div style='flex:{wx} 1 0; background:{ui.BLUE}'></div><div style='flex:{wy} 1 0; background:{ui.INK}'></div></div>"
                f"<span style='font-weight:600'>{wy if played else '—'}</span></div>")
        rows.append([{"v": mp + ret, "w": 600}, str(int(r.n)), f"{r.margin:.1f}", cell])
    ui.html("<div style='display:flex; justify-content:space-between; align-items:baseline; gap:6px 16px; flex-wrap:wrap; margin-top:56px'>"
            "<div role='heading' class='cb-h2' style='font-weight:300; font-size:34px'>Rivalry Record by Map</div>"
            f"<span style='font-size:13px; color:{ui.MUTED}'>{NAMES[mode]}</span></div>"
            f"<div style='border-top:2px solid {ui.INK}; margin-top:12px'>"
            + ui.table([("Map", "left"), ("Played", "right"), ("Avg margin", "right"), (f"Rivalry record · {', '.join(X)} vs {', '.join(Y)}", "left")],
                       rows, min_width=620) + "</div>"
            + ui.note(f"Map wins for each side of the season's main rivalry (teal: {', '.join(X)} · dark: {', '.join(Y)}). "
                      "A dash means the rivalry hasn't played that map.", 8, 12))

# ---------------------------------------------------------------- heat grid
h1, h2 = st.columns([3, 1.3], vertical_alignment="bottom")
with h1:
    ui.html("<div role='heading' class='cb-h2' style='font-weight:300; font-size:34px; margin-top:56px'>Who Plays Each Map Best</div>")
with h2:
    metric = st.segmented_control("Stat", ["kd", "mar", "win"], default="kd", key="mm_metric", label_visibility="collapsed",
                                  format_func={"kd": "K/D", "mar": "MAR / map", "win": "Win %"}.get) or "kd"
agg = d.groupby(["map", "player"]).agg(k=("kills", "sum"), dd=("deaths", "sum"), n=("mar", "size"), m=("mar", "mean"),
                                        w=("result", lambda s: int((s == "W").sum())))
agg["kd"] = agg.k / agg.dd.clip(lower=1); agg["win"] = agg.w / agg.n; agg["mar"] = agg.m
maps = list(g.index)
vals = agg[agg.n >= 2][metric]
lo, hi = (vals.min(), vals.max()) if len(vals) else (0, 1)
fmt = {"kd": lambda v: f"{v:.2f}", "mar": lambda v: ui.sg(v, 2), "win": ui.pct}[metric]
th = "".join(f"<th style='padding:8px 4px; font-size:12px; color:{ui.MUTED}; font-weight:600; text-align:center'>{m}</th>" for m in maps)
trs = ""
players = [p for p in e.players if p in set(d.player)]
for ri, p in enumerate(players):
    tds = ""
    for ci, mp in enumerate(maps):
        al = "l" if ci == 0 else "r" if ci == len(maps) - 1 else ""
        if (mp, p) not in agg.index:
            tp = ui.tip(f"{p} · {mp}", f"Hasn't played this map in {NAMES[mode]}.", align=al, below=ri == 0)
            tds += (f"<td {ui.TAP} style='text-align:center; padding:10px 4px; background:{ui.TRACK}; color:{ui.MUTED}'>—{tp}</td>")
            continue
        c = agg.loc[(mp, p)]
        t = (c[metric] - lo) / max(hi - lo, 0.01); t = min(max(t, 0), 1)
        bg = ui.mix("#EEF1EF", ui.BLUE, t); fg = "#F2F4F2" if t >= 0.55 else ui.INK
        if c.n < 2:
            bg = ui.mix(bg, ui.BG, 0.6); fg = ui.INK
        tp = ui.tip(f"{p} · {NAMES[mode]} on {mp}", f"K/D {c.kd:.2f} · MAR/map {ui.sg(c.mar, 2)}",
                    f"{int(c.w)}–{int(c.n - c.w)} in {int(c.n)} " + ("map (small sample)" if c.n == 1 else "maps"), align=al, below=ri == 0)
        tds += (f"<td {ui.TAP} style='text-align:center; padding:8px 4px; background:{bg}; color:{fg}'><span style='display:block; font-size:14px; "
                f"font-weight:600'>{fmt(c[metric])}</span><span style='display:block; font-size:10px; opacity:0.8'>{int(c.n)} map{'s' if c.n != 1 else ''}</span>{tp}</td>")
    trs += f"<tr><th style='text-align:left; padding:8px; font-size:14px; font-weight:600; white-space:nowrap'>{p}</th>{tds}</tr>"
ui.html(f"<div style='border-top:2px solid {ui.INK}; margin-top:4px'></div>"
        + ui.note("Every player, every map in this mode. The darker the cell, the better. Faded cells come from a single map. Hover or tap a cell for details.", 10, 13)
        + f"<div style='overflow-x:auto; margin-top:12px'><table style='width:100%; min-width:{70 + len(maps) * 64}px; "
          f"border-collapse:separate; border-spacing:3px'><thead><tr><th></th>{th}</tr></thead><tbody>{trs}</tbody></table></div>"
        + ui.legend([("".join(ui.swatch(ui.mix("#EEF1EF", ui.BLUE, t), 14, 12) for t in (0, .25, .5, .75, 1)),
                      f"Lowest → highest {({'kd': 'K/D', 'mar': 'MAR per map', 'win': 'win %'})[metric]} on that map"),
                     (ui.swatch(ui.TRACK, 14, 12), "— hasn't played it")]))