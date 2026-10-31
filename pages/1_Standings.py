"""Standings: rankings by stat, overall and per mode."""
import streamlit as st

from cbl import data
from cbl.ui import page, styles as ui

page.start("Standings")
season = page.header("Standings")
e = data.engine(page.title_id(season))
if e.empty:
    ui.html(ui.empty_box(f"No {data.titles().get(season, {}).get('name', '')} games yet",
                         "Standings fill in after the first series is entered."))
    st.stop()

MODES = [m for m in ["HP", "SND", "OVL", "HJ"] if m in set(e.pm["mode"])]
NAMES = {"ALL": "Overall", "HP": "Hardpoint", "SND": "SnD", "OVL": "Overload", "HJ": "Hijack"}
LONG = {"ALL": "All modes", "HP": "Hardpoint", "SND": "Search and Destroy", "OVL": "Overload", "HJ": "Hijack"}
scope = st.segmented_control("Mode", ["ALL"] + MODES, default="ALL", format_func=NAMES.get, key="st_scope",
                             label_visibility="collapsed") or "ALL"
t = e.standings(None if scope == "ALL" else scope)

si = lambda v: ("+" if v > 0 else "−" if v < 0 else "") + f"{abs(int(v))}"  # noqa: E731
BASE = [("mar", "MAR", "Maps Above Replacement", "Map wins a player added over a fill-in, summed across every map in this view.", ui.sg),
        ("mpm", "MAR / map", "MAR per Map", "Average map wins added per map played. Fairer for players with fewer maps.", lambda v: ui.sg(v, 2)),
        ("kd", "K/D", "Kill/Death Ratio", "Total kills divided by total deaths.", lambda v: f"{v:.2f}"),
        ("pm", "+/-", "Plus/Minus", "Total kills minus total deaths.", si),
        ("kpm", "Kills / map", "Kills per Map", "Average kills per map.", lambda v: f"{v:.1f}"),
        ("dmg", "Damage / map", "Damage per Map", "Average damage dealt per map.", ui.n0),
        ("wp", "Win %", "Map Win Percentage", "Share of maps won.", ui.pct),
        ("stk", "Best streak", "Longest Streak", "Highest kill streak in a single map.", lambda v: f"{int(v)}")]
EXTRA = {"HP": [("hill", "Hill time", "Hill Time per Map", "Average seconds spent in the hardpoint per map.", ui.mmss),
                ("obj", "Obj kills", "Objective Kills per Map", "Average kills on or around the hill per map.", lambda v: f"{v:.1f}")],
         "SND": [("fb", "First bloods", "First Bloods", "Times this player got the first kill of a round.", lambda v: f"{int(v)}"),
                 ("fd", "First deaths", "First Deaths", "Times this player died first in a round. Lower is better.", lambda v: f"{int(v)}", True),
                 ("pl", "Plants", "Bomb Plants", "Bombs planted.", lambda v: f"{int(v)}")],
         "OVL": [("ovl", "Overloads", "Overloads", "Overloads scored.", lambda v: f"{int(v)}"),
                 ("ck", "Carrier kills", "Carrier Kills", "Kills on the enemy carrier.", lambda v: f"{int(v)}")]}
FIN = [("fin", "Finishing", "Finishing · Kills Above Expected", "Kills per map beyond what the player’s damage usually turns "
        "into. Positive means they finish their fights; negative means teammates often get the kill. A tendency more than a fixed trait.",
        lambda v: ui.sg(v, 2))]
defs = BASE + EXTRA.get(scope, []) + (FIN if "fin" in t else [])
keys = [d[0] for d in defs]
stat = st.pills("Stat", keys, default="mar", format_func=lambda k: next(d[1] for d in defs if d[0] == k), key="st_stat",
                label_visibility="collapsed") or "mar"
if stat not in keys:
    stat = "mar"
d = next(x for x in defs if x[0] == stat)
low = len(d) > 5 and d[5]
min_maps = 10 if scope == "ALL" else 5

rows = t.dropna(subset=[stat]).sort_values(stat, ascending=low)
vals = rows[stat]; hi = max(vals.abs().max(), 1e-4)
html = ""
prev, prank = None, 0
for i, (p, r) in enumerate(rows.iterrows()):
    v = r[stat]; rank = prank if v == prev else i + 1; prev, prank = v, rank
    tied = (vals == v).sum() > 1
    frac = (vals.min() / max(v, 1e-4)) if low else max(v, 0) / hi
    color = ui.BLUE if i == 0 else (ui.RULE if (v < 0 and not low) else ui.STEEL)
    small = ui.small_sample() if r.n < min_maps else ""
    tp = ui.tip(f"{p}: {d[4](v)}", f"{'T' if tied else '#'}{rank} of {len(rows)} · {int(r.n)} maps",
                "Small sample" if r.n < min_maps else "", align="l")
    html += (f"<div class='cb-tap cb-row' tabindex='0' style='display:grid; grid-template-columns:44px minmax(0,220px) minmax(0,1fr) 80px; "
             f"align-items:center; gap:12px; min-height:52px; border-bottom:1px solid {ui.RULE}'>"
             f"<span style='font-size:13px; color:{ui.MUTED}'>{'T' if tied else '#'}{rank}</span>"
             f"<span style='font-size:16px; font-weight:600'>{p}{small}</span>"
             f"<div style='height:4px; background:{ui.TRACK}'><div style='height:4px; width:{max(frac * 100, 1):.1f}%; background:{color}'></div></div>"
             f"<span style='text-align:right; font-size:16px; font-weight:500; color:{ui.BLUE if i == 0 else ui.INK}'>{d[4](v)}</span>{tp}</div>")
ui.html("<div style='margin-top:28px; display:flex; align-items:baseline; gap:10px; flex-wrap:wrap'>"
        f"<div role='heading' class='cb-h2' style='margin:0; font-weight:400; font-size:34px; letter-spacing:-0.5px'>{d[2]}</div>"
        f"<span style='font-size:14px; color:{ui.MUTED}'>· {LONG[scope]}</span></div>" + ui.note(d[3])
        + f"<div style='border-top:2px solid {ui.INK}; margin-top:18px'>{html}</div>")

# full table
cols = [("Player", "left"), ("Maps", "right"), ("W-L", "right"), ("MAR", "right"), ("MAR/map", "right"), ("K/D", "right"),
        ("+/-", "right"), ("K/map", "right"), ("Dmg/map", "right")] + [(x[1], "right") for x in EXTRA.get(scope, [])]
src = [("p", None), ("n", None), ("wl", "wp"), ("mar", "mar"), ("mpm", "mpm"), ("kd", "kd"), ("pm", "pm"), ("kpm", "kpm"), ("dmg", "dmg")] + \
      [(x[0], x[0]) for x in EXTRA.get(scope, [])]
fmt = {"mar": ui.sg, "mpm": lambda v: ui.sg(v, 2), "kd": lambda v: f"{v:.2f}", "pm": si, "kpm": lambda v: f"{v:.1f}", "dmg": ui.n0}
fmt.update({x[0]: x[4] for x in EXTRA.get(scope, [])})
lows = {x[0] for x in EXTRA.get(scope, []) if len(x) > 5 and x[5]}
body = []
for p, r in t.sort_values("mar", ascending=False).iterrows():
    faded = r.n < min_maps; row = []
    for (k, heat), (lab, al) in zip(src, cols):
        if k == "p":
            row.append({"v": p, "w": 600}); continue
        if k == "n":
            row.append(str(int(r.n))); continue
        v = f"{int(r.w)}-{int(r.n - r.w)}" if k == "wl" else fmt[k](r[k]) if not (r[k] != r[k]) else "—"
        cell = {"v": v, "w": 600 if k == "mar" else 400}
        if heat and r[heat] == r[heat]:
            col = t[heat].dropna(); fr = (col.rank(method="average")[p] - 1) / max(len(col) - 1, 1)
            if heat in lows:
                fr = 1 - fr
            cell["bg"], cell["fg"] = ui.shade(fr, faded)
        row.append(cell)
    body.append(row)
c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
with c1:
    ui.html(ui.label(f"Full table · {LONG[scope]}", margin_top=40))
with c2:
    st.download_button("Download CSV", t.round(3).to_csv().encode(), file_name=f"standings_{season}_{scope}.csv", mime="text/csv",
                       width="stretch")
ui.html(f"<div style='border-top:2px solid {ui.INK}; margin-top:8px'>" + ui.table(cols, body, min_width=760, cell_pad="11px 8px") + "</div>"
        + ui.legend([("".join(ui.swatch(c, 14, 12) for c in ["#EEF1EF", "#B5C5C9", "#80A0AB", "#487688", ui.BLUE]), "Lowest → highest"),
                     (ui.swatch("#B9C6C6"), f"Faded: fewer than {min_maps} maps")])
        + ui.note("Each column is shaded by where the player ranks in this view: the darker the blue, the better. Lower is better for First deaths.", 6, 12))