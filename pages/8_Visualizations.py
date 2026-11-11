"""Visualizations: charts by theme (Value, Slaying, Objective, Form & Clutch, Head to Head)."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from cbl import data
from cbl.stats import profile as pf
from cbl.ui import page, styles as ui

page.start("Visualizations")
season = page.header("Visualizations")
tid = page.title_id(season)
e = data.engine(tid)
ts = data.titles()
MN = {"HP": "Hardpoint", "SND": "SnD", "OVL": "Overload", "HJ": "Hijack"}
RAMP = lambda t: ui.ramp(max(0, min(1, t)))  # noqa: E731
BEST, WORST = ui.mix(ui.BG, ui.BLUE, 0.55), ui.ramp(0)
MIDQ, MIDW = ui.mix(ui.BG, ui.STEEL, 0.6), ui.ramp(0.2)

if e.empty:
    ui.html(ui.empty_box(f"No {ts.get(season, {}).get('name', '')} games yet", "Charts appear once series are entered."))
    st.stop()

pm = e.pm
P = e.players
INI = {p: p[:2].upper() for p in P}
tab = ui.tabs("vz_tab", ["value", "slaying", "objective", "form", "h2h"],
              {"value": "Value", "slaying": "Slaying", "objective": "Objective", "form": "Form & Clutch", "h2h": "Head to Head"})
RULE = f"<div style='border-top:2px solid {ui.INK}; margin-top:4px'></div>"


def h2(t, right="", rule=True):
    edge = f"padding-bottom:8px; border-bottom:2px solid {ui.INK};" if rule else ""
    return (f"<div style='display:flex; justify-content:space-between; align-items:baseline; gap:6px 16px; flex-wrap:wrap; margin-top:48px; {edge}'>"
            f"<div role='heading' class='cb-h2' style='font-weight:300; font-size:30px'>{t}</div>{right}</div>")


def head(t, label=None):
    """Title on the left, a control (label collapsed) on the right, both on one line.
    Call ui.html(RULE) after filling the control."""
    ui.html("<div style='height:56px'></div>")
    cols = st.columns([2.2, 0.7, 1.3] if label else [3, 1.3], vertical_alignment="center")
    with cols[0]:
        ui.html(f"<div role='heading' class='cb-h2' style='font-weight:300; font-size:30px; line-height:1.2'>{t}</div>")
    if label:
        with cols[1]:
            ui.html(f"<div style='text-align:right; font-size:14px; color:{ui.SLATE}'>{label}</div>")
    return cols[-1]


def pctile(s: pd.Series, low=False):
    s = s.dropna()
    if len(s) < 2:
        return s * 0 + 50
    r = s.rank(method="average", ascending=not low)
    return ((r - 1) / (len(s) - 1) * 100).round().astype(int)


def dumbbell(rows, lo, hi, ticks, legend_items, name_w=74):
    """rows: [(name, open_v, filled_v, right_text, bold, tip_html)]"""
    sx = lambda v: (max(lo, min(hi, v)) - lo) / (hi - lo) * 100  # noqa: E731
    out = ""
    for ri, (name, a, b, txt, bold, tp) in enumerate(rows):
        xa, xb = sx(a), sx(b); d = .15 + min(ri, 16) * .06
        out += (f"<div {ui.TAP} style='display:grid; grid-template-columns:{name_w}px minmax(0,1fr) 56px; align-items:center; gap:10px; min-height:34px'>"
                f"<span style='font-size:14px'>{name}</span><div style='position:relative; height:14px'>"
                f"<div style='position:absolute; top:6px; left:0; right:0; height:2px; background:{ui.RULE2}'></div>"
                f"<div class='{'cb-gx' if xb >= xa else 'cb-gx fromr'}' style='position:absolute; top:6px; left:{min(xa, xb):.1f}%; width:{abs(xb - xa):.1f}%; height:2px; "
                f"background:{ui.STEEL}; animation-delay:{d + .25:.2f}s'></div>"
                f"<div class='cb-pop' style='position:absolute; top:2px; left:calc({xa:.1f}% - 5px); width:10px; height:10px; border-radius:50%; border:1.5px solid {ui.INK}; "
                f"background:{ui.BG}; box-sizing:border-box; animation-delay:{d:.2f}s'></div>"
                f"<div class='cb-dslide' style='--from:calc({xa:.1f}% - 5px); position:absolute; top:2px; left:calc({xb:.1f}% - 5px); width:10px; height:10px; "
                f"border-radius:50%; background:{ui.BLUE}; animation-delay:{d + .2:.2f}s'></div></div>"
                f"<span class='cbn' data-cud='{d:.2f}' style='text-align:right; font-size:14px; font-weight:{600 if bold else 400}'>{txt}</span>{tp}</div>")
    tk = "".join(f"<span>{t}</span>" for t in ticks)
    return (out + f"<div style='display:grid; grid-template-columns:{name_w}px minmax(0,1fr) 56px; gap:10px; margin-top:4px'><span></span>"
            f"<div style='display:flex; justify-content:space-between; font-size:11px; color:{ui.MUTED}'>{tk}</div><span></span></div>"
            + ui.legend(legend_items))


OPEN = f"<span style='display:inline-block; width:10px; height:10px; border-radius:50%; border:1.5px solid {ui.INK}'></span>"
FILL = ui.swatch(ui.BLUE, 10, 10, True)


def quad(df, x, y, n, xl, yl, fx, fy, best, labels, fixed=None, height=380):
    """Quadrant scatter. df indexed by player with columns x, y, n."""
    d = df.dropna(subset=[x, y]); d = d[d[n] > 0]
    if d.empty:
        return None
    xs, ys = d[x], d[y]
    pad = lambda a: (a.min() - ((a.max() - a.min()) * .15 or 1), a.max() + ((a.max() - a.min()) * .15 or 1))  # noqa: E731
    x0, x1 = pad(pd.concat([xs, pd.Series([0])]) if fixed else xs); y0, y1 = pad(pd.concat([ys, pd.Series([0])]) if fixed else ys)
    mx, my = (0, 0) if fixed else (xs.mean(), ys.mean())
    opp = {"tl": "br", "tr": "bl", "bl": "tr", "br": "tl"}
    mixed = [k for k in ["tl", "tr", "bl", "br"] if k not in (best, opp[best])]
    col = {best: BEST, opp[best]: WORST, mixed[0]: MIDW, mixed[1]: MIDQ}
    rect = {"tl": (x0, mx, my, y1), "tr": (mx, x1, my, y1), "bl": (x0, mx, y0, my), "br": (mx, x1, y0, my)}
    fig = go.Figure()
    for k, (a, b, c, dd) in rect.items():
        fig.add_shape(type="rect", x0=a, x1=b, y0=c, y1=dd, fillcolor=col[k], line_width=0, layer="below")
    fig.add_shape(type="line", x0=mx, x1=mx, y0=y0, y1=y1, line=dict(color=ui.INK, width=1, dash="dash"))
    fig.add_shape(type="line", x0=x0, x1=x1, y0=my, y1=my, line=dict(color=ui.INK, width=1, dash="dash"))
    nn = d[n]; sz = 24 + (nn - nn.min()) / max(nn.max() - nn.min(), 1) * 12
    fig.add_scatter(x=xs, y=ys, mode="markers+text", text=[INI[p] for p in d.index], textfont=dict(color=ui.BG, size=10),
                    marker=dict(size=sz, color=ui.INK, line=dict(color=ui.BG, width=1.5)),
                    hovertext=[f"<b>{p} · {int(d.loc[p, n])} maps</b><br>{xl}: {fx(d.loc[p, x])}<br>{yl}: {fy(d.loc[p, y])}" for p in d.index],
                    hoverinfo="text")
    ui.plotly_layout(fig, height=height)
    fig.update_xaxes(range=[x0, x1], title=dict(text=xl, font=dict(size=12, color=ui.MUTED)), showgrid=False, showticklabels=False, ticks="")
    fig.update_yaxes(range=[y0, y1], title=dict(text=yl, font=dict(size=12, color=ui.MUTED)), showgrid=False, showticklabels=False, ticks="")
    key = ui.legend([(ui.swatch(col[k], 12, 12), labels[k]) for k in ["tl", "tr", "bl", "br"]])
    return fig, key


# ============================================================================ VALUE
if tab == "value":
    st_ = e.standings(); hp = e.standings("HP"); snd = e.standings("SND"); ovl = e.standings("OVL")
    with head("Percentile Rankings", "Player"):
        pp = st.selectbox("Player", P, key="vz_pp", label_visibility="collapsed")
    ui.html(RULE)
    groups = {"Value": [("MAR", st_.mar, lambda v: ui.sg(v, 1)), ("MAR / Map", st_.mpm, lambda v: ui.sg(v, 2))],
              "Slaying": [("K/D", st_.kd, lambda v: f"{v:.2f}"), ("Kills / Map", st_.kpm, lambda v: f"{v:.1f}"),
                          ("Damage / Map", st_.dmg, ui.n0), ("Non-Traded Kills / Map", st_.ntk, lambda v: f"{v:.1f}"),
                          ("Assists / Map", st_.apm, lambda v: f"{v:.1f}")],
              "Objective": []}
    if "hill" in hp:
        groups["Objective"].append(("Hill time / map", hp.hill, ui.mmss))
    if len(snd):
        groups["Objective"].append(("First-blood margin / map", (snd.fb - snd.fd) / snd.n, lambda v: ui.sg(v, 2)))
    if "ovl" in ovl:
        groups["Objective"].append(("Overloads / Map", ovl.ovl / ovl.n, lambda v: f"{v:.2f}"))
    blocks = ""
    for g, rows in groups.items():
        if not rows:
            continue
        rr = ""
        for lab, ser, fmt in rows:
            if pp not in ser.dropna().index:
                continue
            d = .2 + min(rr.count("cb-pslide"), 14) * .06      # rows ripple in one after another
            pc = int(pctile(ser)[pp]); v = ser[pp]; n = int(ser.notna().sum())
            tp = ui.tip(f"{lab}: {fmt(v)}", "Best in the league" if pc == 100 else "Lowest in the league" if pc == 0 else f"Better than {pc}% of the league",
                        f"{n} players with this stat this season", align="l")
            col, colfg = ui.readable(RAMP(0.35 + pc / 100 * 0.65))
            rr += (f"<div {ui.TAP} style='display:grid; grid-template-columns:minmax(90px,120px) minmax(60px,1fr) 52px; align-items:center; gap:10px; min-height:38px'>"
                   f"<span style='font-size:14px; line-height:1.25'>{lab}</span><div style='position:relative; height:24px; margin-right:12px'>"
                   f"<div style='position:absolute; top:11px; left:0; right:0; height:3px; background:{ui.TRACK}'></div>"
                   f"<div class='cb-gx' style='position:absolute; top:11px; left:0; width:{pc}%; height:3px; background:{col}; animation-delay:{d:.2f}s'></div>"
                   f"<div style='position:absolute; top:6px; left:50%; width:1px; height:13px; background:{ui.STEEL}'></div>"
                   f"<span class='cbn cb-pslide' data-cud='{d:.2f}' style='animation-delay:{d:.2f}s; position:absolute; top:0; left:calc({pc}% - 12px); width:24px; height:24px; border-radius:50%; background:{col}; "
                   f"color:{colfg}; font-size:11px; font-weight:600; display:flex; align-items:center; justify-content:center; box-shadow:0 0 0 2px {ui.BG}'>{pc}</span></div>"
                   f"<span class='cbn' data-cud='{d:.2f}' style='text-align:right; font-size:14px'>{fmt(v)}</span>{tp}</div>")
        blocks += f"<div>{ui.label(g)}<div style='margin-top:8px'>{rr}</div></div>"
    ui.html(ui.note("Rank among every player this season: 100 is the best in the league, 0 the worst. Hover or tap a row for the number behind it.", 10, 13)
            + f"<div style='display:grid; grid-template-columns:repeat(auto-fit, minmax(min(100%, 240px), 1fr)); gap:20px 32px; margin-top:16px'>{blocks}</div>")

    # ---------------- playstyle radar
    prof = e.profile(); sp, det, raw, chips = prof["sp"], prof["det"], prof["raw"], prof["chips"]
    AX = list(sp.columns)
    order = [t for t in sorted(ts, key=lambda t: ts[t].get("order", 0)) if not data.engine(t).empty]
    prev = None
    if tid and tid in order and order.index(tid) > 0:
        prev = order[order.index(tid) - 1]
    with head("Playstyle", "Compare With"):
        opts = ["AVG", "GHOST"] + [p for p in P if p != pp]
        cmp = st.selectbox("Compare With", opts, key="vz_cmp", label_visibility="collapsed",
                           format_func=lambda o: "League Average" if o == "AVG" else
                           (f"Last Season ({ts[prev]['short']})" if prev else "First Half of the Season") if o == "GHOST" else o)
    ui.html(RULE)
    ghost = cmp == "GHOST"
    if ghost and prev:
        psp, _ = pf.spokes(data.engine(prev).pm, data.engine(prev).players)
        rA = sp.loc[pp]; rB = psp.loc[pp] if pp in psp.index else None
        nameA, nameB = f"{pp} · {ts[tid]['short']}", f"{pp} · {ts[prev]['short']}"
    elif ghost:
        rA = prof["h2"].loc[pp]; rB = prof["h1"].loc[pp]
        half = int(pm.series_no.max() // 2)
        nameA, nameB = f"{pp} · Series {half + 1}–{int(pm.series_no.max())}", f"{pp} · Series 1–{half}"
    else:
        rA = sp.loc[pp]; rB = pd.Series(50, index=AX) if cmp == "AVG" else sp.loc[cmp]
        nameA, nameB = pp, "League Average" if cmp == "AVG" else cmp
    SPOKEX = ["Kills, K/D and damage combined.", "Hill time (counts double) and overloads.", "First Bloods, plants, kills while carrying.",
              "Carrier kills, untraded kills, staying alive.", "How much better on pressure maps than other maps.",
              "Mostly avoiding bad nights (70%), plus good maps (30%)."]
    pt = lambda v, i: "score " + str(v) + " of 100" if i == 5 else "best in the league" if v >= 100 else "lowest in the league" if v <= 0 else f"better than {v}% of the league"  # noqa: E731
    th = [f"<b>{a}</b><br><span style='color:{ui.BLUE}'>{int(rA[a])}</span>" for a in AX]; th = th + [th[0]]
    fig = go.Figure()
    fig.add_scatterpolar(r=[75] * 7, theta=th, mode="lines", fill="toself", fillcolor=ui.PANEL, line=dict(width=0), hoverinfo="skip")
    fig.add_scatterpolar(r=[25] * 7, theta=th, mode="lines", fill="toself", fillcolor=ui.BG, line=dict(width=0), hoverinfo="skip")
    if rB is not None:
        bc = ui.STEEL if cmp == "AVG" else ui.INK
        fig.add_scatterpolar(r=[max(v, 4) for v in list(rB) + [rB.iloc[0]]], theta=th, mode="lines", fill="toself", fillcolor=ui.rgba(ui.INK, 0.12),
                             line=dict(color=bc, width=1.5, dash="dash"), hovertext=[f"{nameB} · {a}: {pt(int(v), i)}" for i, (a, v) in enumerate(zip(AX, rB))] + [""],
                             hoverinfo="text")
    fig.add_scatterpolar(r=[max(v, 4) for v in list(rA) + [rA.iloc[0]]], theta=th, fill="toself", fillcolor=ui.rgba(ui.BLUE, 0.35),
                         line=dict(color=ui.BLUE, width=2.5), marker=dict(size=7, color=ui.BLUE),
                         hovertext=[f"<b>{a}: {pt(int(v), i)}</b><br>{raw[pp][i] if not ghost else nameA}<br>{SPOKEX[i] if cmp == 'AVG' else nameB + ': ' + (pt(int(rB.iloc[i]), i) if rB is not None else '—')}"
                                    for i, (a, v) in enumerate(zip(AX, rA))] + [""], hoverinfo="text")
    fig.update_layout(polar=dict(bgcolor="rgba(0,0,0,0)", radialaxis=dict(range=[0, 100], showticklabels=False, showline=False, ticks="", gridcolor=ui.RULE, linecolor=ui.RULE, tickvals=[25, 50, 75, 100]),
                                 angularaxis=dict(gridcolor=ui.RULE, linecolor=ui.RULE, rotation=90, direction="clockwise",
                                                  tickfont=dict(size=12, color=ui.INK))))
    ui.plotly_layout(fig, height=430)
    fig.update_layout(margin=dict(l=70, r=70, t=56, b=56))
    cfg = ts.get(tid or pm.title.iloc[-1], {})
    arch = (cfg.get("archetypes") or {}).get(pp) if tid else None
    if not arch:
        arch = pf.archetype(sp.loc[pp], e.nmaps(pp))
    ch = chips.get(pp, [])
    chip = lambda c: (f"<span style='display:inline-block; font-size:12px; font-weight:600; padding:3px 8px; margin:0 6px 6px 0; "  # noqa: E731
                      + (f"border:1px solid {ui.BLUE}; color:{ui.BLUE}'>" if c.startswith("#1") else f"border:1px solid {ui.STEEL}; color:{ui.SLATE}'>") + c + "</span>")
    more = (f"<span {ui.TAP} style='display:inline-block; font-size:12px; padding:3px 8px; border:1px dashed {ui.STEEL}; color:{ui.MUTED}'>+{len(ch) - 4} more"
            + ui.tip("More", " · ".join(ch[4:]), below=True) + "</span>") if len(ch) > 4 else ""
    small = ui.small_sample() if e.nmaps(pp) < 20 else ""
    lst = "".join(f"<div style='display:grid; grid-template-columns:minmax(0,1fr) 44px 44px; padding:7px 0; border-bottom:1px solid {ui.RULE}; font-size:14px'>"
                  f"<span>{a}</span><span style='text-align:right; font-weight:600; color:{ui.BLUE}'>{int(rA[a])}</span>"
                  f"<span style='text-align:right; color:{ui.MUTED}'>{'—' if rB is None else int(rB[a])}</span></div>" for a in AX)
    c1, c2 = st.columns(2)
    sub = (f"{pp}'s profile, {nameA.split(' · ')[1]} against {nameB.split(' · ')[1]}." if ghost else f"{pp}'s profile this season.")
    with c1:
        ui.html(ui.note(sub + " Each spoke is a percentile (Steadiness is a 0–100 score): the edge is best in the league, the centre the lowest. "
                        "The shaded ring is the middle half of the league. Hover or tap a point for the number behind it.", 4, 13))
        st.plotly_chart(fig, config=ui.PLOT_CONFIG, width="stretch")
    with c2:
        gnote = ""
        if ghost and rB is None:
            gnote = ui.note(f"{pp} didn't play last season.", 8, 12)
        elif ghost and not prev:
            n1, n2 = prof["n1"].get(pp, 0), prof["n2"].get(pp, 0)
            gnote = ui.note(f"With only one season in, this compares the first half ({n1} maps, dashed) with the second half ({n2} maps, filled). "
                            "Once next season has games, the dashed shape becomes the full previous season."
                            + (f" Small sample for {pp}." if min(n1, n2) < 5 else ""), 8, 12)
        ui.html(f"<div style='margin-top:12px; font-size:12px; font-weight:600; letter-spacing:0.6px; color:{ui.MUTED}; text-transform:uppercase'>Archetype</div>"
                f"<div style='font-weight:300; font-size:36px; line-height:1.1; margin-top:6px'>{arch[0]}</div>"
                + ui.note(arch[1], 6, 14)
                + f"<div style='margin-top:12px'>{''.join(chip(c) for c in ch[:4])}{more}{small}</div>"
                + f"<div style='margin-top:8px'>{lst}</div>"
                + ui.legend([(ui.swatch(ui.BLUE, 14, 4), nameA), (ui.swatch(ui.STEEL if cmp == 'AVG' else ui.INK, 14, 2), nameB)]) + gnote)

    # ---------------- MAR race
    ui.html(h2("MAR Race") + ui.note("Running MAR total after each series. Pick up to 3 players to highlight. Hover anywhere on the chart to see where everyone stood.", 10, 13) + "<div style='height:12px'></div>")
    st.session_state.setdefault("vz_race_keep", P[:3])

    def _race():
        new = st.session_state.vz_race or []
        old = st.session_state.vz_race_keep
        if len(new) > 3:  # keep the newest pick plus the two most recent before it
            added = [p for p in new if p not in old]
            new = [p for p in old if p in new][-2:] + added[-1:]
        st.session_state.vz_race = new; st.session_state.vz_race_keep = new
    st.session_state.setdefault("vz_race", st.session_state.vz_race_keep)
    sel = st.pills("Highlight", P, selection_mode="multi", key="vz_race", on_change=_race, label_visibility="collapsed") or []
    ordr = {t: ts.get(t, {}).get("order", 0) for t in pm.title.unique()}
    sk = pm.assign(k=pm.title.map(ordr) * 10000 + pm.series_no)
    smar = sk.groupby(["k", "player"]).mar.sum().unstack().sort_index()
    snos = sk.groupby("k").agg(t=("title", "first"), n=("series_no", "first")).sort_index()
    run = smar.fillna(0).cumsum().where(smar.notna().cumsum() > 0)
    xl = [f"{ts.get(r.t, {}).get('short', r.t)} {int(r.n)}" if tid is None else str(int(r.n)) for r in snos.itertuples()]
    LC = [(ui.BLUE, "solid"), (ui.INK, "solid"), (ui.BLUE, "dash")]
    fig = go.Figure()
    for p in [p for p in P if p not in sel] + sel:
        on = p in sel; c = LC[sel.index(p)] if on else (ui.mix(ui.BG, ui.STEEL, 0.7), "solid")
        fig.add_scatter(x=xl, y=run[p], mode="lines", name=p, line=dict(color=c[0], width=2.5 if on else 1.2, dash=c[1]),
                        hovertemplate=f"{p} %{{y:+.1f}}<extra></extra>", connectgaps=True)
        if on:
            last = run[p].dropna()
            fig.add_annotation(x=xl[run.index.get_loc(last.index[-1])], y=last.iloc[-1], text=f"<b>{p} {last.iloc[-1]:+.1f}</b>", showarrow=False,
                               xanchor="left", xshift=8, font=dict(size=12, color=ui.INK))
    fig.add_hline(y=0, line=dict(color=ui.STEEL, width=1, dash="dot"))
    ui.plotly_layout(fig, height=420)
    fig.update_layout(hovermode="x unified", margin=dict(l=8, r=120, t=8, b=8))
    fig.update_xaxes(title=dict(text="Series", font=dict(size=12, color=ui.MUTED)), showgrid=False, type="category")
    st.plotly_chart(fig, config=ui.PLOT_CONFIG, width="stretch")

# ============================================================================ SLAYING
elif tab == "slaying":
    st_ = e.standings()
    c1, c2 = st.columns(2, gap="large")
    with c1:
        k = st_.sort_values("kpm", ascending=False); km = k.kpm.max()
        rows = ""
        for i, (p, r) in enumerate(k.iterrows()):
            tp = ui.tip(f"{p}: {r.kpm:.1f} kills per map", f"#{i + 1} of {len(k)} · {int(r.n)} maps played", "Small sample" if r.n < 20 else "", align="l")
            rows += ui.bar_row(p, f"{r.kpm:.1f}", r.kpm / km, ui.BLUE if i == 0 else ui.STEEL, tp, bold=i == 0, name_w=74)
        ui.html(h2("Kills per Map") + ui.note("Most to fewest, all modes.", 4, 13) + f"<div style='margin-top:12px'>{rows}</div>")
    with c2:
        g = pm.groupby(["player", "result"]).agg(k=("kills", "sum"), d=("deaths", "sum"), n=("kills", "size")).reset_index()
        g["kd"] = g.k / g.d.clip(lower=1)
        w = g[g.result == "W"].set_index("player"); l = g[g.result == "L"].set_index("player")
        both = w.index.intersection(l.index)
        gap = (w.kd - l.kd).loc[both].sort_values(ascending=False)
        hi = max(w.kd.max(), l.kd.max()) * 1.1
        rows = [(p, l.kd[p], w.kd[p], f"+{gap[p]:.2f}" if gap[p] >= 0 else f"−{abs(gap[p]):.2f}", False,
                 ui.tip(p, f"In wins: {w.kd[p]:.2f} K/D ({int(w.n[p])} maps)", f"In losses: {l.kd[p]:.2f} K/D ({int(l.n[p])} maps)", align="l")) for p in gap.index]
        ui.html(h2("K/D in Wins vs Losses") + ui.note("Open dot: losses. Filled dot: wins. Biggest gap first. Hover or tap a row for the numbers.", 4, 13)
                + "<div style='margin-top:12px'>" + dumbbell(rows, 0, hi, ["0", f"{hi / 2:.1f}", f"{hi:.1f}"], [(OPEN, "Losses"), (FILL, "Wins")]) + "</div>")

    # consistency
    modes = [m for m in ["HP", "SND", "OVL", "HJ"] if m in set(pm["mode"])]
    with head("Consistency · Kills per Map"):
        spm = st.segmented_control("Mode", modes, default=modes[0], format_func=MN.get, key="vz_spm", label_visibility="collapsed") or modes[0]
    ui.html(RULE)
    d = pm[pm["mode"] == spm]
    med = d.groupby("player").kills.median().sort_values(ascending=False)
    top = max(10, int(np.ceil(d.kills.max() / 10) * 10)) if len(d) else 10
    X = lambda v: f"{v / top * 100:.1f}%"  # noqa: E731
    rows = ""
    for bi, p in enumerate(med.index):
        x = d[d.player == p].kills; dl = .15 + min(bi, 16) * .06
        q1, q2, q3 = x.quantile(.25), x.median(), x.quantile(.75)
        dots = "".join(f"<span class='cb-fadein' style='animation-delay:{dl + .35:.2f}s; position:absolute; top:9px; left:calc({X(v)} - 2px); width:4px; height:4px; border-radius:50%; background:{ui.SLATE}'></span>" for v in x)
        tp = ui.tip(f"{p} · {MN[spm]} · {len(x)} maps", f"Typical night: {q1:g}–{q3:g} kills (median {q2:g})",
                    f"Worst {x.min():.0f} · best {x.max():.0f} · average {x.mean():.1f}" + (" · small sample" if len(x) < 5 else ""), align="l")
        rows += (f"<div {ui.TAP} style='display:grid; grid-template-columns:74px minmax(0,1fr) 70px; align-items:center; gap:12px; min-height:34px'>"
                 f"<span style='font-size:14px'>{p}</span><div style='position:relative; height:22px'>"
                 f"<div class='cb-gxc' style='animation-delay:{dl + .1:.2f}s; position:absolute; top:10px; left:{X(x.min())}; width:calc({X(x.max())} - {X(x.min())}); height:1px; background:{ui.SLATE}'></div>"
                 f"<div class='cb-gxc' style='animation-delay:{dl:.2f}s; position:absolute; top:3px; left:{X(q1)}; width:calc({X(q3)} - {X(q1)}); min-width:3px; height:16px; background:{ui.mix(ui.BG, ui.STEEL, 0.45)}; "
                 f"border:1px solid {ui.SLATE}; box-sizing:border-box'></div>"
                 f"<div class='cb-fadein' style='animation-delay:{dl + .35:.2f}s; position:absolute; top:1px; left:calc({X(q2)} - 1px); width:2px; height:20px; background:{ui.BLUE}'></div>{dots}</div>"
                 f"<span style='text-align:right; font-size:14px'>{q2:g} <span style='font-size:11px; color:{ui.MUTED}'>med</span></span>{tp}</div>")
    ticks = "".join(f"<span>{round(top * f)}</span>" for f in (0, .25, .5, .75, 1))
    ui.html(ui.note("Each dot is one map. The box is a player's typical night (middle half of their maps), the line inside is the median, and the whiskers "
                    "run from worst to best. A narrow box means you know what you're getting.", 10, 13)
            + f"<div style='margin-top:12px'>{rows}</div><div style='display:grid; grid-template-columns:74px minmax(0,1fr) 70px; gap:12px; margin-top:6px'>"
              f"<span></span><div style='display:flex; justify-content:space-between; font-size:11px; color:{ui.MUTED}'>{ticks}</div><span></span></div>")

    # finishing
    fin = e.finishing_frame()
    fits = e._cache.get("fits", {})
    fmodes = [m for m in modes if not fin.empty and m in set(fin["mode"])]
    if fmodes:
        with head("Finishing · Kills vs Damage"):
            fmo = st.segmented_control("Finishing Mode", fmodes, default=fmodes[0], format_func=MN.get, key="vz_fmo", label_visibility="collapsed") or fmodes[0]
        ui.html(RULE)
        c1, c2 = st.columns([1.1, 1], gap="large")
        fd = fin[fin["mode"] == fmo]
        fit = next((v for (t, m), v in fits.items() if m == fmo and (tid is None or t == tid)), None)
        with c1:
            fpl = st.selectbox("Highlight", [p for p in P if p in set(fd.player)], key="vz_fpl")
            sel = fd[fd.player == fpl]
            rate = f"about {round(1 / fit[0])} damage per kill in {MN[fmo]}" if fit else ""
            ui.html(f"<div style='font-size:12px; font-weight:600; letter-spacing:0.6px; text-transform:uppercase; color:{ui.MUTED}; margin-top:8px'>Map by Map</div>"
                    + ui.note(f"Each dot is one map. The dashed line is how many kills a map's damage usually turns into ({rate}). Above the line, a player finished "
                              "more fights than expected; below it, teammates got the kills.", 4, 13)
                    + f"<p style='margin:10px 0 0; font-size:14px'><b style='font-weight:600'>{fpl} {ui.sg(sel.fin.mean(), 2)}</b> "
                      f"<span style='color:{ui.MUTED}'>kills vs expected per {MN[fmo]} map · {len(sel)} maps</span></p>")
            fig = go.Figure()
            oth = fd[fd.player != fpl]
            ht = lambda r: f"<b>{r.player} · {r.map} {MN[fmo]} · Series {int(r.series_no)}</b><br>{int(r.kills)} kills from {r.damage:,.0f} damage<br>Expected {r.xk:.1f} · {ui.sg(r.kills - r.xk, 1)} kills"  # noqa: E731
            fig.add_scatter(x=oth.damage, y=oth.kills, mode="markers", marker=dict(size=7, color=ui.mix(ui.BG, ui.STEEL, 0.8), opacity=0.8),
                            hovertext=[ht(r) for r in oth.itertuples()], hoverinfo="text")
            if fit:
                xx = np.array([max(0, -fit[1] / fit[0]), fd.damage.max() * 1.05])
                fig.add_scatter(x=xx, y=fit[0] * xx + fit[1], mode="lines", line=dict(color=ui.INK, dash="dash", width=2), hoverinfo="skip")
            fig.add_scatter(x=sel.damage, y=sel.kills, mode="markers", marker=dict(size=10, color=ui.BLUE, line=dict(color=ui.BG, width=1.5)),
                            hovertext=[ht(r) for r in sel.itertuples()], hoverinfo="text")
            ui.plotly_layout(fig, height=340)
            fig.update_xaxes(rangemode="tozero", title=dict(text="Damage in the map", font=dict(size=12, color=ui.MUTED)))
            fig.update_yaxes(rangemode="tozero", title=dict(text="Kills", font=dict(size=12, color=ui.MUTED)))
            st.plotly_chart(fig, config=ui.PLOT_CONFIG, width="stretch")
            ui.html(ui.legend([(ui.swatch(ui.BLUE, 10, 10, True), f"{fpl}'s maps"), (ui.swatch(ui.mix(ui.BG, ui.STEEL, 0.8), 10, 10, True), "Everyone else"),
                               (ui.swatch(ui.INK, 16, 2), "Expected kills")]))
        with c2:
            fa = fin.copy()
            fa["dvl"] = (fa.damage / fa.groupby("mode").damage.transform("mean") - 1) * 100
            q = fa.groupby("player").agg(n=("fin", "size"), fin=("fin", "mean"), dvl=("dvl", "mean"))
            r = quad(q, "dvl", "fin", "n", "Damage vs league", "Kills above expected",
                     lambda v: f"{v:+.0f}% damage".replace("-", "−"), lambda v: ui.sg(v, 2) + " kills per map", "tr",
                     {"tl": "Opportunist: less damage, finishes kills", "tr": "Finisher: big damage, finishes kills",
                      "bl": "Quiet: less damage, fewer kills", "br": "Softener: big damage, kills go to teammates"}, fixed=True, height=360)
            ui.html(f"<div style='font-size:12px; font-weight:600; letter-spacing:0.6px; text-transform:uppercase; color:{ui.MUTED}; margin-top:8px'>Finishing Styles</div>"
                    + ui.note("Whole season, all modes. Across: damage per map compared with the league. Up: kills above expected per map.", 4, 13) + (r[1] if r else ""))
            if r:
                st.plotly_chart(r[0], config=ui.PLOT_CONFIG, width="stretch")
            ui.html(ui.note("Dashed lines mark the league average (0). Hover or tap a dot for the numbers.", 0, 12))
        # steadiness of finishing between halves
        half = pm.seq.median()
        h1 = fin[fin.seq <= half].groupby("player").fin.mean(); h2_ = fin[fin.seq > half].groupby("player").fin.mean()
        bb = h1.index.intersection(h2_.index)
        smalls = [p for p in P if e.nmaps(p) < 20]
        if len(bb) >= 4:
            rr = float(np.corrcoef(h1[bb], h2_[bb])[0, 1])
            word = "very steady" if rr >= 0.7 else "moderately steady" if rr >= 0.4 else "not very steady"
            ui.html(ui.note(f"Finishing is {word}: a player's first-half and second-half numbers line up {'strongly' if rr >= 0.7 else 'about halfway' if rr >= 0.4 else 'only loosely'} "
                            f"({rr:.2f}), so read it as a tendency, not a fixed trait." + (f" {' and '.join(smalls)} {'is a small sample' if len(smalls) == 1 else 'are small samples'}." if smalls else ""), 14, 13))

    # fight profile
    fight = pf.fight(pm, P)
    has_len = sum(v["nlen"] for v in fight.values()) > 0
    nxt = next((t for t in sorted(ts, key=lambda t: ts[t].get("order", 0)) if ts[t].get("current")), None)
    tag = "" if has_len else ui.tagbox(f"Starts with {ts.get(nxt, {}).get('short', 'next season')}", ui.BLUE, ui.BLUE)
    ui.html(h2("Fight Profile", right=tag) + ui.note("How often a player gets into fights, and how often they win them. Fights per minute needs match length, "
                                                "which is recorded from " + ts.get(nxt, {}).get("name", "the next season") + " on.", 4, 13))
    c1, c2 = st.columns(2, gap="large")
    with c1:
        ui.html(f"<div style='font-size:12px; font-weight:600; letter-spacing:0.6px; text-transform:uppercase; color:{ui.MUTED}; margin-top:8px'>Fights vs Fight Win %</div>")
        fq = pd.DataFrame(fight).T
        fq = fq[fq.epm.notna()] if has_len else fq.iloc[0:0]
        if fq.empty:
            ui.html(ui.empty_box(f"Appears with {ts.get(nxt, {}).get('name', 'next season')} data",
                                 "Fights per minute needs match length, which wasn’t recorded for these games. This chart fills in after a few series with match lengths.", 12))
        else:
            fq = fq.astype({"epm": float, "fw": float, "nlen": int})
            r = quad(fq, "epm", "fw", "nlen", "Fights per minute", "Fight win %", lambda v: f"{v:.2f}", lambda v: f"{v:.1f}%", "tr",
                     {"tl": "Picker: picks fights, wins them", "tr": "Duelist: fights a lot, wins", "bl": "Passive: few fights, loses more",
                      "br": "Frontliner: fights a lot, trades even"})
            ui.html(ui.note("Across: fights per minute (kills + deaths). Up: share of those fights won.", 4, 13) + r[1])
            st.plotly_chart(r[0], config=ui.PLOT_CONFIG, width="stretch")
            ui.html(ui.note("Dashed lines mark the league average. Only maps with a recorded match length count here.", 0, 12))
    with c2:
        fr = {p: v for p, v in fight.items() if v["pfw"] is not None and v["ofw"] is not None}
        order = sorted(fr, key=lambda p: -(fr[p]["pfw"] - fr[p]["ofw"]))
        vals = [fr[p][k] for p in fr for k in ("pfw", "ofw")]
        lo, hi = (np.floor(min(vals) / 5) * 5 - 5, np.ceil(max(vals) / 5) * 5 + 5) if vals else (0, 100)
        rows = []
        for p in order:
            x = fr[p]; dd = x["pfw"] - x["ofw"]
            rows.append((p, x["ofw"], x["pfw"], ui.sg(dd, 1), abs(dd) >= 2,
                         ui.tip(p, f"Pressure maps: {x['pfw']:.1f}% of fights won ({x['pn']} maps)", f"Other maps: {x['ofw']:.1f}% ({x['on']} maps)", align="l")))
        top = order[0] if order else None
        ui.html(f"<div style='font-size:12px; font-weight:600; letter-spacing:0.6px; text-transform:uppercase; color:{ui.MUTED}; margin-top:8px'>Under Pressure</div>"
                + ui.note("Fight win % (kills out of kills plus deaths) on pressure maps (a team can clinch, or the map was close) vs other maps. "
                          "Open dot: other maps. Filled dot: pressure maps.", 4, 13)
                + "<div style='margin-top:10px'>" + dumbbell(rows, lo, hi, [f"{lo:.0f}%", f"{(lo + hi) / 2:.0f}%", f"{hi:.0f}%"], [(OPEN, "Other maps"), (FILL, "Pressure maps")]) + "</div>"
                + (ui.note(f"Biggest riser: {top} ({ui.sg(fr[top]['pfw'] - fr[top]['ofw'], 1)} points, on {fr[top]['pn']} pressure maps). "
                           "With match lengths, this adds fights per minute on pressure maps, showing who gets more aggressive or more careful when it counts.", 10, 12) if top else ""))

    # kills vs deaths
    st_ = e.standings()
    r = quad(st_, "kpm", "dpm", "n", "Kills per map", "Deaths per map", lambda v: f"{v:.1f}", lambda v: f"{v:.1f}", "br",
             {"tl": "Few kills, many deaths", "tr": "Many kills, many deaths", "bl": "Few kills, few deaths", "br": "Many kills, few deaths"})
    ui.html(h2("Kills vs Deaths") + ui.note("Per map, all modes · dot size = maps played", 4, 13) + r[1])
    st.plotly_chart(r[0], config=ui.PLOT_CONFIG, width="stretch")
    ui.html(ui.note("Dots are player initials, sized by maps played. Dashed lines are the league average. Hover or tap a dot for the numbers.", 0, 12))

# ============================================================================ OBJECTIVE
elif tab == "objective":
    defs = []
    hp = e.standings("HP")
    if "hill" in hp:
        defs.append(("Hill Time vs K/D", "Hardpoint · objective vs slaying", hp.assign(x=hp.hill, y=hp.kd), "Hill time per map", "K/D", ui.mmss,
                     lambda v: f"{v:.2f}", "tr", {"tl": "Slayer, little hill", "tr": "Does both", "bl": "Neither", "br": "Lives on the hill"}))
    snd = e.standings("SND")
    if "fb" in snd:
        defs.append(("Opening Duels", "Search and Destroy · first bloods vs first deaths per map", snd.assign(x=snd.fb / snd.n, y=snd.fd / snd.n),
                     "First Bloods per map", "First deaths per map", lambda v: f"{v:.2f}", lambda v: f"{v:.2f}", "br",
                     {"tl": "Loses openings", "tr": "Aggressive, trades evenly", "bl": "Passive", "br": "Wins openings"}))
    ovl = e.standings("OVL")
    if "ovl" in ovl:
        defs.append(("Scoring vs Stopping", "Overload · overloads vs carrier kills per map", ovl.assign(x=ovl.ovl / ovl.n, y=ovl.ck / ovl.n),
                     "Overloads per map", "Carrier kills per map", lambda v: f"{v:.2f}", lambda v: f"{v:.2f}", "tr",
                     {"tl": "Stops carriers", "tr": "Does both", "bl": "Neither", "br": "Scores"}))
    if not defs:
        ui.html(ui.empty_box("No objective modes yet", "These charts fill in once Hardpoint, SnD or Overload maps are played."))
    cols = st.columns(2, gap="large")
    for i, (t, sub, df, xl, yl, fx, fy, best, labs) in enumerate(defs):
        with cols[i % 2]:
            r = quad(df, "x", "y", "n", xl, yl, fx, fy, best, labs, height=340)
            if fx is ui.mmss:
                tv = np.linspace(*r[0].layout.xaxis.range, 5)[1:-1]
                r[0].update_xaxes(tickvals=tv, ticktext=[ui.mmss(v) for v in tv])
            ui.html(h2(t) + ui.note(sub, 4, 13) + r[1])
            st.plotly_chart(r[0], config=ui.PLOT_CONFIG, width="stretch")
    ui.html(ui.note("Dots are player initials, sized by maps played. Dashed lines are the league average. Hover or tap a dot for the numbers.", 8, 12))

# ============================================================================ FORM & CLUTCH
elif tab == "form":
    d = pm.copy(); d["mo"] = d.date.dt.to_period("M")
    months = pd.period_range(d.mo.min(), d.mo.max(), freq="M")
    g = d.groupby(["player", "mo"]).mar.agg(["mean", "size"])
    avg = d.groupby("player").mar.mean()
    ok = g[g["size"] >= 3]["mean"]
    lo, hi = (ok.min(), ok.max()) if len(ok) else (g["mean"].min(), g["mean"].max())
    played_months = set(d.mo)
    many = len(set(d.date.dt.year)) > 1
    mlabel = lambda m: m.strftime("%b %Y") if many else m.strftime("%b")  # noqa: E731
    th = "".join(f"<th style='padding:8px 4px; font-size:12px; color:{ui.MUTED}; font-weight:600; text-align:center'>{mlabel(m)}</th>" for m in months)
    trs = ""
    for ri, p in enumerate(P):
        tds = ""
        for ci, m in enumerate(months):
            al = "l" if ci == 0 else "r" if ci == len(months) - 1 else ""
            if (p, m) not in g.index:
                none = m not in played_months
                tp = ui.tip(f"{p} · {mlabel(m)}", f"No games were played in {mlabel(m)}." if none else f"{p} didn’t play this month.", align=al, below=ri < 2)
                tds += (f"<td class='cb-tap cb-cellin' tabindex='0' style='animation-delay:{.1 + (ri + ci) * .035:.2f}s; text-align:center; padding:8px 4px; background:{ui.TRACK}; color:{ui.MUTED}; font-size:12px'>"
                        f"{'no games' if none else '—'}{tp}</td>")
                continue
            v, n = g.loc[(p, m)]
            t = (v - lo) / max(hi - lo, 0.01); bg, fg = ui.shade(t)
            if n < 3:
                bg = ui.mix(bg, ui.BG, 0.35)
            dl = v - avg[p]; arrow = "↑" if dl > 0.03 else "↓" if dl < -0.03 else "→"
            tp = ui.tip(f"{p} · {mlabel(m)}", f"MAR per map {ui.sg(v, 2)} over {int(n)} maps",
                        f"{'Above' if dl >= 0 else 'Below'} season average by {abs(dl):.2f}" + (f" · small sample ({int(n)} maps)" if n < 5 else ""), align=al, below=ri < 2)
            tds += (f"<td class='cb-tap cb-cellin' tabindex='0' style='animation-delay:{.1 + (ri + ci) * .035:.2f}s; text-align:center; padding:8px 4px; background:{bg}; color:{fg}'><span style='display:block; font-size:14px; font-weight:500'>"
                    f"{arrow} {ui.sg(v, 2)}</span><span style='display:block; font-size:10px; opacity:0.8'>{int(n)} maps</span>{tp}</td>")
        trs += (f"<tr><th style='text-align:left; padding:8px; font-size:14px; font-weight:600'>{p}</th>{tds}"
                f"<td style='text-align:right; padding:8px; font-size:14px; font-weight:600'>{ui.sg(avg[p], 2)}</td></tr>")
    gaps = [mlabel(m) for m in months if m not in played_months]
    ui.html(h2("Form by Month") + ui.note("MAR per map each month. Darker is better. Arrows compare with the player's own season average, so you can see who heated up, "
                                          "who cooled off and who held steady. Hover or tap a cell.", 4, 13)
            + f"<div style='overflow-x:auto; margin-top:12px'><table style='width:100%; min-width:{160 + 90 * len(months)}px; "
              f"border-collapse:separate; border-spacing:3px'><thead><tr><th></th>{th}<th style='padding:8px; font-size:12px; color:{ui.MUTED}; text-align:right'>Season</th></tr></thead>"
              f"<tbody>{trs}</tbody></table></div>"
            + ui.note((f"No games were played in {', '.join(gaps)}. " if gaps else "") + "Cells under 3 maps are lightly faded; anything under 5 maps is flagged as a "
                      "small sample in its hover box.", 8, 12))

    cl = pf.clutch(pm, P)
    rows = [(p, c) for p, c in cl.items() if c[0] is not None and c[4] is not None]
    rows.sort(key=lambda x: -(x[1][0] - x[1][4]))
    vals = [v for _, c in rows for v in (c[0], c[4])]
    lo, hi = (min(vals) - 0.05, max(vals) + 0.05) if vals else (-0.15, 0.45)
    dr = [(p, c[4], c[0], ui.sg(c[0] - c[4], 2), c[0] - c[4] > 0.03,
           ui.tip(p + (" · small sample" if c[1] < 10 else ""), f"Pressure maps ({c[1]}): {ui.sg(c[0], 2)} MAR/map · {c[3]:.2f} K/D · {c[2]}% won",
                  f"Other maps ({c[5]}): {ui.sg(c[4], 2)} MAR/map · {c[7]:.2f} K/D · {c[6]}% won", align="l")) for p, c in rows]
    npress = int(e.maps.press.sum())
    smalls = [p for p, c in rows if c[1] < 10]
    ui.html(h2("Who Steps Up") + ui.note("MAR per map on pressure maps against every other map. A pressure map is either a <b>deciding map</b> (one team can clinch the series) "
                                         f"or a <b>close map</b> (Hardpoint by 25 or fewer, SnD 6–5, Overload by 1). {npress} of {len(e.maps)} maps were pressure maps.", 4, 13)
            + "<div style='margin-top:12px'>" + dumbbell(dr, lo, hi, [ui.sg(lo, 2), ui.sg((lo + hi) / 2, 2), ui.sg(hi, 2)], [(OPEN, "Other maps"), (FILL, "Pressure maps")]) + "</div>"
            + ui.note("Right column: pressure minus other maps. Biggest step-up first." + (f" Small samples ({', '.join(smalls)}) are tagged in the hover box." if smalls else ""), 8, 12))

# ============================================================================ HEAD TO HEAD
else:
    team = pm.pivot_table(index="match_id", columns="player", values="team", aggfunc="first")
    res = pm.pivot_table(index="match_id", columns="player", values="result", aggfunc="first")

    def grid(title, sub, same):
        th = "".join(f"<th style='padding:6px 2px; font-size:12px; color:{ui.MUTED}; font-weight:600; text-align:center'>{INI[p]}</th>" for p in P)
        trs = ""
        for ri, a in enumerate(P):
            tds = ""
            for ci, b in enumerate(P):
                al = "l" if ci == 0 else "r" if ci == len(P) - 1 else ""
                own = a == b
                if own and same:
                    n = int(team[a].notna().sum()); w = int((res[a] == "W").sum())
                elif own:
                    n = w = 0
                else:
                    m = team[a].notna() & team[b].notna() & ((team[a] == team[b]) if same else (team[a] != team[b]))
                    n = int(m.sum()); w = int((res.loc[m, a] == "W").sum())
                if not n:
                    msg = "" if own else ("Never teammates" if same else "Never on opposite teams")
                    tp = ui.tip(a if own else f"{a} {'with' if same else 'vs'} {b}", msg, align=al, below=ri == 0) if msg else ""
                    tds += f"<td {ui.TAP if msg else ''} style='background:{ui.TRACK}; padding:8px 2px'>{tp}</td>"
                    continue
                wr = w / n; bg, fg = ui.shade((wr - 0.25) / 0.5)
                if n < 5:
                    bg = ui.mix(bg, ui.BG, 0.6); fg = ui.INK
                edge = f"box-shadow:inset 0 0 0 2px {ui.INK};" if own else ""
                head = f"{a} overall" if own else (f"{a} and {b} as teammates" if same else f"{a} against {b}")
                tp = ui.tip(head, f"{w}–{n - w} in maps ({round(wr * 100)}%)", "Small sample: under 5 maps" if n < 5 else "", align=al, below=ri == 0)
                tds += (f"<td class='cb-tap cb-cellin' tabindex='0' style='animation-delay:{.1 + (ri + ci) * .035:.2f}s; text-align:center; padding:6px 2px; background:{bg}; color:{fg}; {edge}'><span style='display:block; font-size:13px; "
                        f"font-weight:500'>{round(wr * 100)}%</span><span style='display:block; font-size:10px; opacity:0.8'>{n}</span>{tp}</td>")
            trs += f"<tr><th style='text-align:left; padding:6px 8px; font-size:14px; font-weight:600; white-space:nowrap'>{a}</th>{tds}</tr>"
        return (h2(title) + ui.note(sub, 4, 13) + f"<div style='overflow-x:auto; margin-top:12px'>"
                f"<table style='width:100%; min-width:{90 + 54 * len(P)}px; border-collapse:separate; border-spacing:3px'><thead><tr><th></th>{th}</tr></thead>"
                f"<tbody>{trs}</tbody></table></div>")
    ui.html(grid("Teammate Chemistry", "Map win % when two players are on the same team. Small number: maps together. Hover or tap a cell.", True)
            + grid("Player vs Player", "Row player’s map win % when on the opposite team from the column player. Hover or tap a cell.", False)
            + ui.legend([("".join(ui.swatch(RAMP(t), 14, 12) for t in (0, .25, .5, .75, 1)), "Lose more → win more"),
                         (ui.swatch(ui.mix(RAMP(0.5), ui.BG, 0.6), 14, 12), "Faded: under 5 maps"),
                         (ui.swatch("transparent", 14, 12, border=f"2px solid {ui.INK}"), "Outlined: the player's own win %")]))