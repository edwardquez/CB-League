"""Projections: what each player is likely to put up on a map, and how well the model has done."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from cbl import data
from cbl.stats import projections as pj
from cbl.ui import page, styles as ui

page.start("Projections")
season = page.header("Projections", allow_all=False)
tid = page.title_id(season)
e = data.engine(tid)
ts = data.titles()
cfg = ts.get(season, {})
V = data.version()

ui.html(ui.note("What each player is likely to put up on a given map, based on how they have played there and in that mode. "
                "Every projection comes from 20,000 simulated maps.", 0, 15))
if e.empty:
    ui.html(ui.empty_box(f"Projections start after the first {cfg.get('name', '')} series",
                         "Early on they lean on each player's mode averages, marked Low confidence until more maps are played."))
    st.stop()

LBL = {"kills": "Kills", "damage": "Damage", "hill_time": "Hill time", "first_bloods": "First bloods", "overloads": "Overloads"}
MODEN = {"HP": "Hardpoint", "SND": "Search and Destroy", "OVL": "Overload", "HJ": "Hijack"}
MODES = {"HP": "Hardpoint", "SND": "SnD", "OVL": "Overload", "HJ": "Hijack"}
STEP = {"kills": 1, "first_bloods": 1, "overloads": 1, "damage": 100, "hill_time": 5}
NICE = {"kills": 5, "first_bloods": 1, "overloads": 1, "damage": 500, "hill_time": 30}


def fmt_v(s, v):
    return ui.mmss(v) if s == "hill_time" else ui.n0(v) if s == "damage" else str(int(round(v)))


def fmt_e(s, v):
    return f"{v:.1f}" if s in pj.COUNT else fmt_v(s, v)


def conf_of(n):
    return "Low" if n < 5 else "Medium" if n < 10 else "High"


def pct(p):
    return ">99%" if p >= 0.995 else "<1%" if p <= 0.005 else f"{round(p * 100)}%"


@st.cache_data(show_spinner=False)
def swings(t, v):
    return pj.league_swings(data.engine(t).pm)


@st.cache_data(show_spinner=False, max_entries=1024)
def proj(t, player, mode, mp, v):
    return pj.project(data.engine(t).pm, player, mode, mp, lg=swings(t, v))


@st.cache_data(show_spinner="Replaying the season…")
def backtest(t, v):
    return pj.backtest(data.engine(t).pm)


pm = e.pm
modes = [m for m in ["HP", "SND", "OVL", "HJ"] if m in set(pm["mode"])]
players = e.players
c1, c2, c3 = st.columns([1, 1.4, 1], vertical_alignment="bottom")
with c1:
    pl = st.selectbox("Player", players, key="pj_player")
with c2:
    mode = st.segmented_control("Mode", modes, default=modes[0], format_func=MODES.get, key="pj_mode") or modes[0]
mc = (cfg.get("modes") or {}).get(mode, {})
active = [m["name"] for m in mc.get("maps", []) if m.get("status") != "retired"]
retired = [m["name"] for m in mc.get("maps", []) if m.get("status") == "retired"]
played = sorted(pm[pm["mode"] == mode]["map"].unique())
active = active or [m for m in played if m not in retired]
retired = retired + [m for m in played if m not in active and m not in retired]
with c3:
    mp = st.selectbox("Map", active + retired + ["ALL"], key=f"pj_map_{mode}",
                      format_func=lambda m: "Any map (mode average)" if m == "ALL" else m + (" (retired)" if m in retired else ""))
any_map = mp == "ALL"
R = proj(tid, pl, mode, None if any_map else mp, V)
scope = MODEN[mode] if any_map else f"{mp} {MODES[mode]}"

img = (f"<div style='width:100%; aspect-ratio:16/9; background:{ui.INK}; color:{ui.BG}; display:flex; align-items:center; justify-content:center; "
       f"font-size:11px; font-weight:600; letter-spacing:1.5px'>ANY MAP</div>" if any_map else ui.img_tag(mp))
ui.html("<div class='cb-pjhead' style='display:grid; grid-template-columns:160px minmax(0,1fr); gap:20px; align-items:center; margin-top:40px; "
        f"padding-bottom:16px; border-bottom:2px solid {ui.INK}'>"
        f"<div>{img}</div><div role='heading' class='cb-h2' style='font-weight:300; font-size:34px'>{pl} · {scope}</div></div>"
        "<style>@media (max-width:640px){.cb-pjhead{grid-template-columns:96px minmax(0,1fr) !important}}"
        f"[class*='st-key-pjcard_']{{background:{ui.PANEL}; border-color:{ui.RULE} !important; padding:18px 18px 26px !important; min-height:330px}}"
        f"[class*='st-key-pjstep_'] button{{min-width:36px; min-height:36px; padding:0; background:transparent}}</style>")


def step_target(key, delta):
    st.session_state[key] = max(st.session_state[key] + delta, delta if delta > 0 else -delta)


if not R:
    ui.html(ui.empty_box(f"{pl} has no {MODEN[mode]} maps yet", "Pick another mode or player."))
else:
    ui.html("<div style='height:12px'></div>")
    cols = st.columns(3)
    for i, (s, r) in enumerate(R.items()):
        with cols[i % 3]:
            c = r["cdf"]
            d0, d1 = (0, len(c) - 1) if s in pj.COUNT else (c[0], c[-1])
            span = max(d1 - d0, 1)
            P = lambda v: max(0, min(1, (v - d0) / span)) * 100  # noqa: E731
            conf = conf_of(r["nmo"])
            chip_bg, chip_fg, chip_b = {"High": (ui.BLUE, "#F2F4F2", ui.BLUE), "Medium": (ui.STEEL, "#F2F4F2", ui.STEEL),
                                        "Low": ("transparent", ui.SLATE, ui.STEEL)}[conf]
            if any_map:
                basis = f"From {pl}’s {r['nmo']} {MODEN[mode]} map{'s' if r['nmo'] != 1 else ''}."
            elif r["nm"] == 0:
                basis = f"No {mp} games yet, so this uses all {r['nmo']} {MODEN[mode]} maps."
            else:
                basis = (f"{r['nm']} map{'s' if r['nm'] != 1 else ''} on {mp} plus {r['nmo']} {MODEN[mode]} maps. "
                         f"{mp} counts for {round(r['w'] * 100)}%.")
            ns = 1 if (s == "kills" and r["e"] < 15) else NICE[s]
            key = f"pj_t_{pl}_{mode}_{mp}_{s}"
            st.session_state.setdefault(key, max(STEP[s], int(np.floor(r["e"] / ns) * ns + ns)))
            tgt = st.session_state[key]
            tp = ui.tip(f"Likely {fmt_v(s, r['lo'])} to {fmt_v(s, r['hi'])}", "8 in 10 simulated maps landed in this range.",
                        "1 in 10 went lower and 1 in 10 higher.", align="l" if i == 0 else "r" if i == len(R) - 1 else "")
            with st.container(border=True, key=f"pjcard_{s}"):
                ui.html(f"<div style='display:flex; justify-content:space-between; align-items:center; gap:8px'>"
                        f"<span style='font-size:12px; font-weight:600; letter-spacing:1.6px; text-transform:uppercase; color:{ui.MUTED}'>{LBL[s]}</span>"
                        f"<span style='font-size:11px; font-weight:600; padding:2px 7px; background:{chip_bg}; color:{chip_fg}; border:1px solid {chip_b}'>"
                        f"{conf} confidence</span></div>"
                        f"<div style='font-weight:300; font-size:44px; line-height:1; margin-top:14px'>{fmt_e(s, r['e'])}</div>"
                        f"<div style='font-size:13px; color:{ui.MUTED}; margin-top:6px'>Expected · likely {fmt_v(s, r['lo'])}–{fmt_v(s, r['hi'])}</div>"
                        f"<div {ui.TAP} style='margin-top:16px'><div style='position:relative; height:14px; background:{ui.TRACK}'>"
                        f"<div style='position:absolute; top:0; bottom:0; left:{P(r['lo']):.1f}%; width:{max(P(r['hi']) - P(r['lo']), 0.8):.1f}%; background:{ui.STEEL}'></div>"
                        f"<div style='position:absolute; top:-3px; bottom:-3px; left:calc({P(r['e']):.1f}% - 1px); width:2px; background:{ui.INK}'></div>"
                        f"<div style='position:absolute; top:-3px; bottom:-3px; left:calc({P(tgt):.1f}% - 1px); width:0; border-left:2px dashed {ui.BLUE}'></div></div>"
                        f"<div style='display:flex; justify-content:space-between; font-size:11px; color:{ui.MUTED}; margin-top:4px'>"
                        f"<span>{fmt_v(s, d0)}</span><span>{fmt_v(s, d1)}</span></div>{tp}</div>"
                        f"<div style='border-top:1px solid {ui.RULE}; margin-top:12px; padding-top:10px; font-size:13px; color:{ui.MUTED}'>Chance to reach a target</div>")
                with st.container(horizontal=True, vertical_alignment="center", gap="small", key=f"pjstep_{s}"):
                    st.button("−", key=f"{key}_dn", on_click=step_target, args=(key, -STEP[s]), width="content")
                    ui.html(f"<div style='min-width:64px; text-align:center; font-size:16px; font-weight:500; padding:4px 0; "
                            f"border-bottom:2px dashed {ui.STEEL}'>{fmt_v(s, tgt)}+</div>")
                    st.button("+", key=f"{key}_up", on_click=step_target, args=(key, STEP[s]), width="content")
                    ui.html(f"<div style='font-size:24px; font-weight:500; color:{ui.BLUE}; padding-left:4px'>{pct(pj.reach(r, s, tgt))}</div>")
                ui.html(ui.note(basis, 4, 12))
    ui.html(ui.legend([(ui.swatch(ui.STEEL, 18, 10), "Likely range (middle 80%)"), (ui.swatch(ui.INK, 2, 14), "Expected"),
                       (f"<span style='display:inline-block; height:14px; border-left:2px dashed {ui.BLUE}'></span>", "Your target")]))

# ------------------------------------------------------------- everyone
stats = pj.stats_for(mode)
rows = []
for p in players:
    r = proj(tid, p, mode, None if any_map else mp, V)
    if "kills" in r:
        rows.append((p, r))
rows.sort(key=lambda x: -x[1]["kills"]["e"])
body = []
for p, r in rows:
    n = r["kills"]["nmo"]; c = conf_of(n)
    cells = [{"v": p, "w": 600 if p == pl else 500, "bg": ui.PANEL if p == pl else "transparent"}]
    for s in stats:
        if s in r:
            cells.append({"v": f"{fmt_e(s, r[s]['e'])}<br><span style='font-size:11px; color:{ui.MUTED}'>{fmt_v(s, r[s]['lo'])}–{fmt_v(s, r[s]['hi'])}</span>",
                          "bg": ui.PANEL if p == pl else "transparent"})
        else:
            cells.append("—")
    cells.append({"v": f"{c} · " + (f"{n} maps" if any_map else f"{r['kills']['nm']} here, {n} total"),
                  "fg": ui.MUTED if c == "Low" else ui.INK, "w": 600 if c == "High" else 400, "bg": ui.PANEL if p == pl else "transparent"})
    body.append(cells)
h1, h2 = st.columns([3, 1], vertical_alignment="bottom")
with h1:
    ui.html(f"<div role='heading' class='cb-h2' style='font-weight:300; font-size:34px; margin-top:64px'>Everyone on {scope}</div>")
with h2:
    csv = pd.DataFrame([{"player": p, **{f"{s}_{k}": round(r[s][k], 2) for s in stats if s in r for k in ("e", "lo", "hi")}} for p, r in rows])
    st.download_button("Download CSV", csv.to_csv(index=False).encode(), f"projections_{season}_{mode}_{mp}.csv", "text/csv")
ui.html(f"<div style='border-top:2px solid {ui.INK}; margin-top:4px'></div>"
        + ui.note("Expected value with the likely range underneath. Sorted by expected kills. Your selected player is highlighted.", 10, 13)
        + "<div style='margin-top:4px'>"
        + ui.table([("Player", "left")] + [(LBL[s], "right") for s in stats] + [("Confidence", "right")], body, min_width=560, cell_pad="10px 8px") + "</div>")

# ------------------------------------------------------------- track record
bt = backtest(tid, V)
ui.html(f"<div role='heading' class='cb-h2' style='font-weight:300; font-size:34px; margin-top:72px; padding-bottom:8px; border-bottom:2px solid {ui.INK}'>Track Record</div>")
if bt.empty:
    ui.html(ui.empty_box("Not enough maps to test yet", "The track record replays the second half of the season, so it needs a few series first."))
    st.stop()
ONLY = {"hill_time": "HP", "first_bloods": "SND", "overloads": "OVL"}
bstats = [s for s in LBL if s in set(bt.stat)]
intro = st.empty()
bts = ui.tabs("bt_stat", bstats, LBL)
c1, c2, c3 = st.columns([1.3, 1, 1.3], vertical_alignment="bottom")
with c1:
    mopts = [ONLY[bts]] if bts in ONLY else ["ALL"] + [m for m in modes if m in set(bt["mode"])]
    btm = st.segmented_control("Mode", mopts, default=mopts[0], format_func=lambda m: "All" if m == "ALL" else MODES[m], key=f"bt_mode_{bts}") or mopts[0]
with c2:
    btp = st.selectbox("Player", ["ALL"] + players, format_func=lambda p: "Everyone" if p == "ALL" else p, key="bt_player",
                       index=(["ALL"] + players).index(pl))
with c3:
    btv = st.segmented_control("View", ["pt", "rng"], default="pt", key="bt_view",
                               format_func={"pt": "Projected vs actual", "rng": "Show ranges"}.get) or "pt"
is_pt = btv == "pt"
with intro:
    ui.html(ui.note("We replayed the second half of the season. Before each map the model only saw earlier games. "
                    + ("Each hollow dot is what the model projected for that map, and the solid dot is what really happened. The line between them is the miss."
                       if is_pt else "Each bar is the likely range the model gave for that map, and the dot is what really happened. About 8 in 10 dots should land on their bar."), 10, 14)
            + "<div style='height:8px'></div>")
r = bt[bt.stat == bts]
if btp != "ALL":
    r = r[r.player == btp]
if btm != "ALL":
    r = r[r["mode"] == btm]
r = r.sort_values("e") if btp == "ALL" else r.sort_values(["series"]).reset_index(drop=True)
r = r.reset_index(drop=True)
if r.empty:
    ui.html(ui.empty_box(("No " if btp == "ALL" else f"{btp} has no ") + LBL[bts].lower() + ("" if btm == "ALL" else f" {MODES[btm]}") +
                         " maps in the tested stretch yet.", "Try another player or mode."))
else:
    inr = (r.act >= r.lo) & (r.act <= r.hi)
    miss = (r.act - r.e).abs(); mae = miss.mean()
    fm = (lambda v: f"{round(v)} sec") if bts == "hill_time" else (lambda v: ui.n0(v)) if bts == "damage" else (lambda v: f"{v:.1f}")
    small = bts in ("first_bloods", "overloads")
    tol = np.where(small, 1, np.maximum(0.2 * r.e, 2 if bts == "kills" else 0))
    close = int((miss <= tol + 1e-9).sum()); n = len(r)
    cl = "Within 1 of the projection" if small else "Within 20% or 2 kills of the projection" if bts == "kills" else "Within 20% of the projection"
    k = ([(str(n), "Maps tested"), (fm(mae), "Average miss from the projection"), (f"{close} of {n}", f"{cl} ({round(close / n * 100)}%)")] if is_pt else
         [(str(n), "Maps tested"), (f"{int(inr.sum())} of {n}", f"Landed in range ({round(inr.mean() * 100)}%)"), (fm(mae), "Average miss from the projection")])
    ui.html("<div style='display:flex; flex-wrap:wrap; gap:12px 40px; margin-top:18px'>"
            + "".join(f"<div><div style='font-weight:300; font-size:28px; line-height:1'>{v}</div><div style='font-size:12px; color:{ui.MUTED}; margin-top:4px'>{l}</div></div>"
                      for v, l in k) + "</div>")
    hov = [f"{x.player} · {x.map} {MODES[x.mode]} · Series {x.series}<br>" +
           (f"Projected {fmt_e(bts, x.e)}<br>Actual {fmt_v(bts, x.act)} · off by {fm(abs(x.act - x.e))} ({round(abs(x.act - x.e) / max(x.e, 0.1) * 100)}%)" if is_pt else
            f"Projected {fmt_e(bts, x.e)}, likely {fmt_v(bts, x.lo)}–{fmt_v(bts, x.hi)}<br>Actual {fmt_v(bts, x.act)} · "
            + ("in range" if x.lo <= x.act <= x.hi else "above range" if x.act > x.hi else "below range")) for x in r.itertuples()]
    xs = list(range(n)); fig = go.Figure()
    if is_pt:
        lx, ly = [], []
        for i, x in enumerate(r.itertuples()):
            lx += [i, i, None]; ly += [x.e, x.act, None]
        fig.add_scatter(x=lx, y=ly, mode="lines", line=dict(color=ui.STEEL, width=1.5), hoverinfo="skip")
        fig.add_scatter(x=xs, y=r.e, mode="markers", marker=dict(size=8, color="rgba(0,0,0,0)", line=dict(color=ui.INK, width=1.5)),
                        hovertext=hov, hoverinfo="text", name="Projected")
        fig.add_scatter(x=xs, y=r.act, mode="markers", marker=dict(size=8, color=ui.BLUE), hovertext=hov, hoverinfo="text", name="Actual")
    else:
        fig.add_bar(x=xs, y=r.hi - r.lo, base=r.lo, marker_color=ui.mix(ui.BG, ui.STEEL, 0.7), width=0.6, hoverinfo="skip")
        fig.add_scatter(x=xs, y=r.act, mode="markers", marker=dict(size=8, color=np.where(inr, ui.BLUE, ui.RUST)), hovertext=hov, hoverinfo="text")
    ui.plotly_layout(fig, height=340)
    fig.update_xaxes(showticklabels=False, showgrid=False)
    if bts == "hill_time":
        tv = np.linspace(max(0, min(r.act.min(), r.lo.min())), max(r.act.max(), r.hi.max()), 4)
        fig.update_yaxes(tickvals=tv, ticktext=[ui.mmss(v) for v in tv])
    st.plotly_chart(fig, config=ui.PLOT_CONFIG, width="stretch")
    x0 = "Lowest projection" if btp == "ALL" else f"Series {r.series.iloc[0]}"
    x1 = "Highest projection" if btp == "ALL" else f"Series {r.series.iloc[-1]}"
    ui.html(f"<div style='display:flex; justify-content:space-between; font-size:12px; color:{ui.MUTED}; margin-top:-8px'><span>{x0}</span><span>{x1}</span></div>"
            + (ui.legend([(f"<span style='display:inline-block; width:9px; height:9px; border-radius:50%; border:1.5px solid {ui.INK}'></span>", "Projected"),
                          (ui.swatch(ui.BLUE, 9, 9, True), "Actual"), (ui.swatch(ui.STEEL, 2, 14), "Miss: the longer the line, the further off")]) if is_pt else
               ui.legend([(ui.swatch(ui.mix(ui.BG, ui.STEEL, 0.7), 10, 14), "Likely range"), (ui.swatch(ui.BLUE, 9, 9, True), "Actual, in range"),
                          (ui.swatch(ui.RUST, 9, 9, True), "Actual, outside")])))

# summary bars (every player, every mode)
rows = ""
for s in bstats:
    x = bt[bt.stat == s]; v = round(((x.act >= x.lo) & (x.act <= x.hi)).mean() * 100)
    rows += (f"<div style='display:grid; grid-template-columns:110px minmax(0,1fr) 44px; align-items:center; gap:10px; min-height:32px'>"
             f"<span style='font-size:14px'>{LBL[s]}</span><div style='position:relative; height:10px; background:{ui.TRACK}'>"
             f"<div style='height:10px; width:{v}%; background:{ui.BLUE}'></div><div style='position:absolute; top:-3px; bottom:-3px; left:80%; width:2px; "
             f"background:{ui.INK}'></div></div><span style='text-align:right; font-size:14px; font-weight:500'>{v}%</span></div>")
ui.html(ui.label("Landed in the likely range · every player", margin_top=36) + f"<div style='margin-top:10px; max-width:640px'>{rows}</div>"
        + ui.note("The black tick marks 8 in 10. First bloods and overloads sit a bit above it because whole-number ranges can't stop at exactly 8 in 10.", 6, 12))

steps = [("Measure the average", "The player’s past maps are resampled 20,000 times. That shows both their typical number and how far it could drift with this few games."),
         ("Blend this map with the mode", "Map history counts more as it builds up: 1 game gives it 17%, 5 games 50%, 10 games 67%. The rest comes from all their maps in the mode."),
         ("Simulate the map", "Kills, first bloods and overloads are drawn as counts around that average. Damage and hill time use the player’s own real swings from map to map, which run much wider."),
         ("Read off the results", "Expected is the average of the simulations. The likely range is the middle 80%. Chance to reach is the share of simulations at or above your target.")]
cells = "".join(f"<div style='display:grid; grid-template-columns:32px minmax(0,1fr); gap:12px; padding:16px 0; border-bottom:1px solid {ui.RULE}'>"
                f"<span style='font-size:14px; font-weight:600; color:{ui.BLUE}'>{i + 1}</span><div><div style='font-size:15px; font-weight:600'>{t}</div>"
                f"<p style='margin:6px 0 0; font-size:14px; color:{ui.MUTED}; line-height:1.5'>{b}</p></div></div>" for i, (t, b) in enumerate(steps))
ui.html(f"<div role='heading' class='cb-h2' style='font-weight:300; font-size:34px; margin-top:72px; padding-bottom:8px; border-bottom:2px solid {ui.INK}'>How Projections Work</div>"
        + f"<div style='display:grid; grid-template-columns:repeat(auto-fit, minmax(max(280px, 45%), 1fr)); column-gap:40px; margin-top:4px'>{cells}</div>"
        + ui.note("Confidence follows how many maps the player has in this mode, since that history drives most of every projection: Low under 5, "
                  "Medium 5 to 9, High 10 or more. In testing, Low lines missed by about twice as much as High ones.", 14, 13))