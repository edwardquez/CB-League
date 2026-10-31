"""Rivalries (lineups that keep meeting) and Matchup Previews (pick teams, see how it stacks up)."""
from itertools import combinations

import numpy as np
import streamlit as st

from cbl import data
from cbl.stats import projections as pj
from cbl.ui import page, styles as ui

page.start("Rivalries & Matchup Previews")
season = page.header("Rivalries & Matchup Previews")
tid = page.title_id(season)
e = data.engine(tid)
ts = data.titles()
MODE = {"HP": "Hardpoint", "SND": "Search and Destroy", "OVL": "Overload", "HJ": "Hijack"}
MSHORT = {"HP": "Hardpoint", "SND": "SnD", "OVL": "Overload", "HJ": "Hijack"}
A_COL, B_COL = ui.BLUE, ui.INK
RSCALE = 130
GRID2 = "display:grid; grid-template-columns:repeat(auto-fit, minmax(max(300px, 45%), 1fr)); gap:32px 48px"
PHONE_CSS = ("<style>@media (max-width:640px){"
             ".cb-rivhead{grid-template-columns:minmax(0,1fr) !important; text-align:center; gap:6px !important}"
             ".cb-rivhead .cb-rivx{text-align:center !important}"
             ".cb-outl{grid-template-columns:48px minmax(0,1fr) 40% !important}}</style>")

ui.html(PHONE_CSS)
tab = ui.tabs("rv_tab", ["riv", "pre"], {"riv": "Rivalries", "pre": "Matchup Preview"})
tname = ts.get(season, {}).get("name", "")


def names(lineup):
    return ", ".join(lineup)


def dot(lineup):
    return " · ".join(lineup)


def label(text, top=0):
    """Small caps section label with the thin steel rule under it (as in the mockup)."""
    return (f"<div style='margin-top:{top}px; padding-bottom:8px; border-bottom:1px solid {ui.STEEL}; font-size:12px; font-weight:600; "
            f"letter-spacing:1.6px; text-transform:uppercase; color:{ui.MUTED}'>{text}</div>")


def h2_row(title, right_key=None):
    """Big section title on the left, room for a control on the right, heavy rule under both."""
    c1, c2 = st.columns([3, 1.2], vertical_alignment="bottom")
    with c1:
        ui.html(f"<div role='heading' class='cb-h2' style='font-weight:300; font-size:34px; margin-top:40px'>{title}</div>")
    return c2


# ===================================================================== Rivalries
def rivalries():
    S = e.series[e.series.maps_played > 0]
    if S.empty:
        return []
    S = S.sort_values(["title", "series_no"])
    groups = {}
    for r in S.itertuples():
        ka, kb = e.lineup_key(r.team_a), e.lineup_key(r.team_b)
        groups.setdefault(frozenset((ka, kb)), []).append(r)
    out = []
    for key, rows in groups.items():
        if len(rows) < 2 or len(key) < 2:
            continue
        first = rows[0]
        x, y = sorted(first.team_a), sorted(first.team_b)
        if e.lineup_key(y) < e.lineup_key(x):
            x, y = y, x
        kx = e.lineup_key(x)
        meet, sx, sy, mx, my = [], 0, 0, 0, 0
        for r in rows:
            xa = e.lineup_key(r.team_a) == kx
            wx, wy = (r.wins_a, r.wins_b) if xa else (r.wins_b, r.wins_a)
            win = None if r.winner not in ("A", "B") else ("x" if (r.winner == "A") == xa else "y")
            sx += win == "x"; sy += win == "y"; mx += wx; my += wy
            meet.append({"sid": S.loc[r.Index, "_id"], "no": int(r.series_no), "title": r.title, "date": r.date,
                         "win": win, "score": f"{max(wx, wy)}-{min(wx, wy)}", "sx": sx, "sy": sy, "early": bool(r.ended_early)})
        out.append({"x": x, "y": y, "kx": kx, "ky": e.lineup_key(y), "meet": meet, "sx": sx, "sy": sy, "mx": mx, "my": my,
                    "fmt": f"{len(x)}v{len(y)}", "ids": [m["sid"] for m in meet], "id": "|".join(sorted(key))})
    return sorted(out, key=lambda r: (-len(r["meet"]), -(r["mx"] + r["my"])))


def next_series(R):
    """An open series between these two lineups with no maps yet (the decider), if any."""
    nxt = e.series[(e.series.status == "open") & (e.series.maps_played == 0)]
    for r in nxt.itertuples():
        if {e.lineup_key(r.team_a), e.lineup_key(r.team_b)} == {R["kx"], R["ky"]}:
            return r
    return None


def status(R):
    sx, sy, n = R["sx"], R["sy"], len(R["meet"])
    lead = (f"Tied {sx}–{sy} in series." if sx == sy else
            f"{names(R['x']) if sx > sy else names(R['y'])} lead {max(sx, sy)}–{min(sx, sy)} in series.")
    nx = next_series(R)
    if nx is not None:
        return lead + f" Series {int(nx.series_no)}, a best of {nx.best_of}, " + ("decides it." if sx == sy else "is up next.")
    if n < 3:
        lead += " One more meeting and the small-sample tag comes off."
    return lead


def meetings(R):
    nx = next_series(R)
    cols = len(R["meet"]) + (1 if nx is not None else 0)
    tiles = tally = ""
    for m in R["meet"]:
        fill = A_COL if m["win"] == "x" else B_COL if m["win"] == "y" else ui.STEEL
        tiles += (f"<div style='background:{fill}; color:#F2F4F2; padding:10px 10px 12px; min-width:0'>"
                  f"<div style='display:flex; justify-content:space-between; gap:4px; font-size:11px; white-space:nowrap'><span>Series {m['no']}</span>"
                  f"<span>{m['date'].strftime('%b')} {m['date'].day}</span></div>"
                  f"<div style='font-weight:300; font-size:24px; margin-top:12px; letter-spacing:1px'>{m['score']}</div></div>")
        tally += f"<span style='font-size:12px; color:{ui.MUTED}'>{m['sx']}–{m['sy']}</span>"
    if nx is not None:
        tiles += (f"<div style='border:1px dashed {ui.STEEL}; padding:10px 10px 12px; color:{ui.MUTED}; min-width:0'>"
                  f"<div style='font-size:12px'>Series {int(nx.series_no)} · Bo{nx.best_of}</div>"
                  f"<div style='font-size:16px; margin-top:16px'>{'Decider' if R['sx'] == R['sy'] else 'Up next'}</div></div>")
        tally += "<span></span>"
    grid = f"display:grid; grid-template-columns:repeat({cols}, minmax(100px, 1fr)); gap:4px; min-width:{cols * 104}px"
    return (label("Every meeting", 20)
            + f"<div style='overflow-x:auto; margin-top:10px'><div style='{grid}'>{tiles}</div>"
              f"<div style='{grid}; margin-top:6px'>{tally}</div></div>"
            + ui.note(f"Tiles colored by winner. Running tally shown as {names(R['x'])} first.", 6, 12))


def momentum(R):
    n = len(R["meet"]); lead_max = max(1, *[abs(m["sx"] - m["sy"]) for m in R["meet"]])
    cols = ""
    for i, m in enumerate(R["meet"]):
        lead = m["sx"] - m["sy"]
        fill = A_COL if m["win"] == "x" else B_COL if m["win"] == "y" else ui.STEEL
        who = names(R["x"]) if m["win"] == "x" else names(R["y"]) if m["win"] == "y" else "Nobody"
        state = (f"Tied {m['sx']}–{m['sy']} after this series" if lead == 0 else
                 f"{names(R['x']) if lead > 0 else names(R['y'])} lead {max(m['sx'], m['sy'])}–{min(m['sx'], m['sy'])}")
        tp = ui.tip(f"Series {m['no']} · {m['date'].strftime('%b')} {m['date'].day} · meeting {i + 1} of {n}",
                    f"{who} won {m['score']}" + (" (ended early)" if m["early"] else ""), state,
                    align="l" if i == 0 else "r" if i == n - 1 else "")
        up = lead / lead_max * 100 if lead > 0 else 0
        dn = -lead / lead_max * 100 if lead < 0 else 0
        cols += (f"<div {ui.TAP} style='flex:1 1 0; min-width:0; display:flex; flex-direction:column; align-items:stretch'>"
                 f"<div style='height:74px; display:flex; align-items:flex-end'><div style='width:100%; height:{up:.0f}%; background:{fill}'></div></div>"
                 f"<div style='height:1px; background:{ui.STEEL}'></div>"
                 f"<div style='height:74px; display:flex; align-items:flex-start'><div style='width:100%; height:{dn:.0f}%; background:{fill}'></div></div>"
                 f"<span style='font-size:11px; color:{ui.MUTED}; margin-top:6px; text-align:center'>{m['no']}</span>{tp}</div>")
    return (label("Momentum · series lead after each meeting")
            + f"<div style='display:flex; gap:6px; margin-top:14px'>{cols}</div>"
            + ui.note(f"Height = rivalry lead (up: {names(R['x'])} ahead). Color = series winner. Hover or tap a bar for details.", 8, 12))


def mode_split(R):
    rows, xs, ys, ev = "", [], [], []
    rm = e.maps[e.maps.series_id.isin(R["ids"])]
    S = e.series.set_index("_id")
    xa = {sid: e.lineup_key(S.loc[sid, "team_a"]) == R["kx"] for sid in R["ids"]}
    for mo in [k for k in ["HP", "SND", "OVL", "HJ"] if k in set(rm["mode"])]:
        mm = rm[rm["mode"] == mo]
        wx = int(sum((w == "A") == xa[s] for s, w in zip(mm.series_id, mm.winner) if w in ("A", "B")))
        wy = int(len(mm) - wx)
        (xs if wx > wy else ys if wy > wx else ev).append(MSHORT[mo])
        rows += (f"<div style='margin-top:14px'><div style='display:grid; grid-template-columns:40px minmax(0,1fr) 40px; align-items:baseline'>"
                 f"<span style='font-size:15px; font-weight:600; color:{A_COL}'>{wx}</span>"
                 f"<span style='text-align:center; font-size:15px'>{MODE[mo]}</span>"
                 f"<span style='text-align:right; font-size:15px; font-weight:600'>{wy}</span></div>"
                 f"<div style='display:flex; gap:3px; height:10px; margin-top:6px'><div style='flex:{wx} 1 0; background:{A_COL}'></div>"
                 f"<div style='flex:{wy} 1 0; background:{B_COL}'></div></div></div>")
    parts = []
    if xs:
        parts.append(f"{names(R['x'])} own {' and '.join(xs)}")
    if ys:
        parts.append(f"{names(R['y'])} own {' and '.join(ys)}")
    txt = "; ".join(parts) + "." if parts else ""
    if ev:
        txt += f" {' and '.join(ev)} {'is' if len(ev) == 1 else 'are'} dead even."
    return label("Maps won by mode") + rows + ui.note(txt.strip(), 10, 12)


def duel(R, rp):
    tot = rp.groupby(["player"]).mar.sum()
    px = tot[tot.index.isin(R["x"])].idxmax(); py = tot[tot.index.isin(R["y"])].idxmax()
    a = rp[rp.player == px].set_index("match_id"); b = rp[rp.player == py].set_index("match_id")
    both = a.index.intersection(b.index); a, b = a.loc[both], b.loc[both]
    n = len(both)
    rows = [("Kills / map", a.kills.mean(), b.kills.mean(), 1), ("K/D", a.kills.sum() / max(a.deaths.sum(), 1), b.kills.sum() / max(b.deaths.sum(), 1), 2),
            ("MAR", a.mar.sum(), b.mar.sum(), 2 if max(abs(a.mar.sum()), abs(b.mar.sum())) < 2 else 1),
            ("Out-fragged the other", int((a.kills > b.kills).sum()), int((b.kills > a.kills).sum()), 0),
            ("Maps won", int((a.result == "W").sum()), int((b.result == "W").sum()), 0)]
    cell = f"padding:10px 0; border-bottom:1px solid {ui.RULE}"
    body = ""
    for lab, va, vb, dp in rows:
        fa = ui.sg(va, dp) if lab == "MAR" else (f"{va:.{dp}f}" if dp else str(va))
        fb = ui.sg(vb, dp) if lab == "MAR" else (f"{vb:.{dp}f}" if dp else str(vb))
        body += (f"<span style='{cell}; font-size:17px; font-weight:{600 if va > vb else 400}'>{fa}</span>"
                 f"<span style='{cell}; font-size:13px; color:{ui.MUTED}; text-align:center'>{lab}</span>"
                 f"<span style='{cell}; font-size:17px; font-weight:{600 if vb > va else 400}; text-align:right'>{fb}</span>")
    head = (f"<span style='{cell}; font-size:18px; font-weight:600; color:{A_COL}'>{px}</span><span style='{cell}'></span>"
            f"<span style='{cell}; font-size:18px; font-weight:600; text-align:right'>{py}</span>")
    return (label("Key duel · each side's best player")
            + f"<div style='display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr) minmax(0,1fr); column-gap:12px; margin-top:4px'>{head}{body}</div>"
            + ui.note(f"Across the {n} rivalry map{'s' if n != 1 else ''} they played against each other.", 10, 12))


def top_list(R, rp):
    g = rp.groupby("player").agg(mar=("mar", "sum"), k=("kills", "sum"), d=("deaths", "sum"), n=("mar", "size")).sort_values("mar", ascending=False)
    rows = ""
    for p, r in g.iterrows():
        side = A_COL if p in R["x"] else B_COL
        mv = ui.sg(r.mar, 2 if abs(r.mar) < 2 else 1)
        rows += (f"<div style='display:grid; grid-template-columns:12px minmax(0,1fr) auto 64px; align-items:center; gap:12px; min-height:40px; "
                 f"border-bottom:1px solid {ui.RULE}'>{ui.swatch(side, 10, 10)}<span style='font-size:15px'>{p}</span>"
                 f"<span style='font-size:13px; color:{ui.MUTED}'>{r.k / max(r.d, 1):.2f} K/D</span>"
                 f"<span style='text-align:right; font-size:15px; font-weight:600'>{mv}</span></div>")
    n = len(R["meet"]); nm = R["mx"] + R["my"]
    return (label("Top performers in this rivalry") + f"<div style='margin-top:4px'>{rows}</div>"
            + ui.note(f"MAR across all {n} meetings ({nm} maps each).", 10, 12))


def show_rivalries():
    rivs = rivalries()
    if not rivs:
        ui.html(ui.empty_box("No rivalries yet this season", "A matchup appears here once the same two lineups have met twice."))
        return
    ui.html(ui.note("Lineups that have met at least twice, most meetings first. A rivalry is tagged small sample until its third meeting. "
                    "Open one for the full story.", 16, 14) + f"<div style='border-top:2px solid {ui.INK}; margin-top:24px'></div>")
    opened = st.session_state.setdefault("rv_open", {})
    for R in rivs:
        n = len(R["meet"])
        small = ui.small_sample() if n < 3 else ""
        wx, wy = (600 if R["sx"] > R["sy"] else 500), (600 if R["sy"] > R["sx"] else 500)
        c1, c2 = st.columns([7, 1], vertical_alignment="center")
        with c1:
            ui.html("<div class='cb-rivhead' style='display:grid; grid-template-columns:minmax(0,1fr) auto minmax(0,1fr); align-items:center; gap:8px 24px; padding:18px 0 14px'>"
                    f"<span class='cb-rivx' style='text-align:right; font-size:17px; font-weight:{wx}'><span style='display:inline-block; width:12px; height:12px; "
                    f"background:{A_COL}; margin-right:10px'></span>{dot(R['x'])}</span>"
                    f"<div class='cb-rivscore' style='text-align:center'><div style='display:flex; justify-content:center; align-items:center; gap:14px; font-weight:300; font-size:34px; line-height:1'>"
                    f"<span style='color:{A_COL}'>{R['sx']}</span><span style='display:inline-block; width:14px; height:1px; background:{ui.MUTED}'></span>"
                    f"<span>{R['sy']}</span></div></div>"
                    f"<span style='font-size:17px; font-weight:{wy}'><span style='display:inline-block; width:12px; height:12px; background:{B_COL}; "
                    f"margin-right:10px'></span>{dot(R['y'])}</span>"
                    # own row under the names and score, so a long meta line doesn't squeeze 4v4 lineups onto two lines
                    f"<div style='grid-column:1 / -1; text-align:center; font-size:13px; color:{ui.MUTED}'>"
                    f"{n} Meetings · Map Count {R['mx']}–{R['my']} · {R['fmt']}{small}</div></div>")
        with c2:
            on = opened.get(R["id"], False)
            if st.button("Hide" if on else "Open", key=f"rv_{R['id']}", type="primary" if on else "secondary", width="stretch"):
                opened[R["id"]] = not on
                st.rerun()
        if opened.get(R["id"]):
            rp = e.pm[e.pm.series_id.isin(R["ids"])]
            ui.html(f"<p style='margin:4px 0 0; font-size:15px'>{status(R)}</p>" + meetings(R)
                    + f"<div style='{GRID2}; margin-top:36px'><section>{momentum(R)}</section><section>{mode_split(R)}</section>"
                      f"<section>{duel(R, rp)}</section><section>{top_list(R, rp)}</section></div><div style='height:28px'></div>")
        ui.html(f"<div style='border-bottom:1px solid {ui.RULE}'></div>")


# ===================================================================== Preview
TEAM_CSS = f"""<style>
.st-key-pv_pick_A, .st-key-pv_pick_B {{ gap:6px !important; }}
[class*="st-key-pvc_"] {{ position:relative; }}
[class*="st-key-pvc_"] [data-testid="stMarkdownContainer"] {{ margin-bottom:0 !important; }}
[class*="st-key-pvc_"] [data-testid="stElementContainer"]:has(button) {{ position:absolute; inset:0; z-index:3; margin:0; width:100% !important; }}
[class*="st-key-pvc_"] [data-testid="stElementContainer"]:has(button) > div, [class*="st-key-pvc_"] .stButton {{ height:100%; width:100%; }}
[class*="st-key-pvc_"] button {{ width:100%; height:100% !important; min-height:0; opacity:0; cursor:pointer; }}
.pv-card {{ position:relative; min-width:72px; min-height:46px; padding:6px 10px; box-sizing:border-box; border:1px solid #BCC5C1;
  border-radius:2px; font-size:14px; line-height:1.2; color:{ui.INK}; white-space:nowrap; }}
.pv-card .pv-s {{ font-size:12px; }}
.st-key-pv_pick_A .pv-card.on {{ background:{A_COL}; border-color:{A_COL}; color:#F2F4F2; }}
.st-key-pv_pick_B .pv-card.on {{ background:{B_COL}; border-color:{B_COL}; color:#F2F4F2; }}
.pv-card.off {{ opacity:0.45; }}
[class*="st-key-pvc_"]:hover .pv-card:not(.on):not(.off) {{ border-color:{ui.INK}; }}
[class*="st-key-pvc_"]:hover .cb-tip {{ display:block; }}
</style>"""


def show_preview():
    if e.empty:
        ui.html(ui.empty_box(f"Previews need a few {tname} series first",
                             "Until then, switch the season to Black Ops 7 to preview with last year's ratings."))
        return
    R, det = e.ratings()
    pool = [p for p in e.players if p in R]
    ss = st.session_state
    if "pv_a" not in ss:
        ss.pv_a = pool[:6:2][:3] if len(pool) >= 6 else pool[: len(pool) // 2]
        ss.pv_b = pool[1:6:2][:3] if len(pool) >= 6 else pool[len(pool) // 2:]
    ss.pv_a = [p for p in ss.pv_a if p in pool]; ss.pv_b = [p for p in ss.pv_b if p in pool]
    avg = lambda t: sum(R[p] for p in t) / len(t)  # noqa: E731
    prob = lambda a, b: 1 / (1 + 10 ** ((avg(b) - avg(a)) / RSCALE))  # noqa: E731

    ui.html(ui.note("Pick who's playing on each side to see how the matchup stacks up before you start. Use it to settle teams.", 16, 14)
            + f"<div style='border-top:2px solid {ui.INK}; margin-top:24px'></div>" + TEAM_CSS)

    def toggle(side, p):
        cur = ss.pv_a if side == "A" else ss.pv_b
        nxt = [x for x in cur if x != p] if p in cur else cur + [p]
        if side == "A":
            ss.pv_a = nxt
        else:
            ss.pv_b = nxt

    cols = st.columns(2, gap="large")
    for col, side, color in ((cols[0], "A", A_COL), (cols[1], "B", B_COL)):
        mine, other = (ss.pv_a, ss.pv_b) if side == "A" else (ss.pv_b, ss.pv_a)
        with col:
            ui.html(f"<div style='display:flex; justify-content:space-between; align-items:center; margin-top:16px'>"
                    f"<span style='display:flex; align-items:center; gap:8px; font-size:16px; font-weight:600'>{ui.swatch(color, 12, 12)}Team {side}</span>"
                    f"<span style='font-size:13px; color:{ui.MUTED}'>{len(mine)} player{'s' if len(mine) != 1 else ''}</span></div>")
            with st.container(horizontal=True, gap="small", key=f"pv_pick_{side}"):
                for p in pool:
                    taken = p in other; d = det[p]
                    sub = f"On Team {'B' if side == 'A' else 'A'}" if taken else f"Rating {R[p]}"
                    # the same hover tips as the rest of the site (plain CSS, so they close the moment the mouse leaves),
                    # with an invisible button over the card for the tap. Streamlit's own button tips stuck after a click.
                    tp = "" if taken else ui.tip(f"{p} · rating {R[p]}", f"Typical map {ui.sg(d[1], 2)}, best stretches {ui.sg(d[2], 2)} (league average 0)",
                                                 f"{d[0]} maps · {d[3]}% confidence" + (", so it can still move a lot" if d[3] < 85 else ""),
                                                 align="l" if side == "A" else "r", below=True)
                    with st.container(gap=None, width="content", key=f"pvc_{side}_{p}"):
                        ui.html(f"<div class='pv-card{' on' if p in mine else ''}{' off' if taken else ''}'><div>{p}</div>"
                                f"<div class='pv-s'>{sub}</div>{tp}</div>")
                        st.button(p, key=f"pv_{side}_{p}", disabled=taken, on_click=toggle, args=(side, p))
    TA, TB = ss.pv_a, ss.pv_b
    fc1, fc2 = st.columns([1, 4], vertical_alignment="center")
    with fc1:
        if st.button("Make fair teams", disabled=len(TA) + len(TB) < 2):
            allp = TA + TB; h = len(allp) // 2; best = None
            for a in combinations(allp, h):
                b = [p for p in allp if p not in a]
                dd = abs(prob(list(a), b) - 0.5)
                if best is None or dd < best[0]:
                    best = (dd, list(a), b)
            ss.pv_a, ss.pv_b = best[1], best[2]
            st.rerun()
    with fc2:
        ui.html(ui.note("Reshuffles everyone selected into the most even split. A player on one team is greyed out on the other.", 0, 12))
    if not TA or not TB:
        ui.html(f"<div style='margin-top:28px; padding:20px; border:1px dashed {ui.STEEL}; font-size:14px'>Pick at least one player for each team.</div>")
        return

    # ---------------- balance
    p = prob(TA, TB); pa = round(p * 100); pb = 100 - pa
    verdict = f"Even matchup, {pa}–{pb}" if abs(pa - 50) <= 5 else f"Leans Team {'A' if pa > 50 else 'B'}, {max(pa, pb)}%"
    rt = lambda x: f"{x} {R[x]}"  # noqa: E731
    ta = ui.tip(f"Team A · {pa}% to win a map", " · ".join(rt(x) for x in TA), f"Average rating {round(avg(TA))}", align="l", below=True)
    tb = ui.tip(f"Team B · {pb}% to win a map", " · ".join(rt(x) for x in TB), f"Average rating {round(avg(TB))}", align="r", below=True)
    ui.html(label("Balance", 32).replace(f"border-bottom:1px solid {ui.STEEL}", "border-bottom:0")
            + f"<div style='font-weight:300; font-size:30px; margin-top:4px'>{verdict}</div>"
            + f"<div style='display:flex; height:22px; margin-top:12px'>"
              f"<div {ui.TAP} style='flex:{pa} 1 0; background:{A_COL}; color:#F2F4F2; font-size:12px; font-weight:600; display:flex; align-items:center; padding:0 8px'>{pa}%{ta}</div>"
              f"<div {ui.TAP} style='flex:{pb} 1 0; background:{B_COL}; color:#F2F4F2; font-size:12px; font-weight:600; display:flex; align-items:center; justify-content:flex-end; padding:0 8px'>{pb}%{tb}</div></div>"
            + f"<div style='display:flex; justify-content:space-between; gap:12px; margin-top:8px; font-size:14px'>"
              f"<span>Team A · Avg Rating {round(avg(TA))}</span><span>Team B · Avg Rating {round(avg(TB))}</span></div>"
            + (ui.note("Teams are different sizes, so the meter is only a rough guide.", 8, 12) if len(TA) != len(TB) else "")
            + ui.note("Win chances come from player ratings, built from every stat (MAR, K/D, damage, objective play, assists). A player's best "
                      "stretches count extra and recent maps count a bit more. Players with fewer maps get the benefit of the doubt, pulled only "
                      "lightly toward average. Hover a side, or a player's button, for the details.", 10, 12))

    # ---------------- history, pairs, head to head
    pm = e.pm
    ka, kb = e.lineup_key(TA), e.lineup_key(TB)
    S = e.series.set_index("_id")
    lk = {sid: (e.lineup_key(r.team_a), e.lineup_key(r.team_b)) for sid, r in S.iterrows()}
    M = e.maps.copy()
    M["la"] = M.series_id.map(lambda s: lk[s][0]); M["lb"] = M.series_id.map(lambda s: lk[s][1])
    vs = M[((M.la == ka) & (M.lb == kb)) | ((M.la == kb) & (M.lb == ka))]
    vs_w = int((((vs.la == ka) & (vs.winner == "A")) | ((vs.lb == ka) & (vs.winner == "B"))).sum())

    def lineup_rec(k):
        x = M[(M.la == k) | (M.lb == k)]
        if x.empty:
            return "Never played"
        w = int((((x.la == k) & (x.winner == "A")) | ((x.lb == k) & (x.winner == "B"))).sum())
        return f"{w}–{len(x) - w} in maps"
    hist = [("These two lineups head to head", f"Team A {vs_w}–{len(vs) - vs_w} in maps" if len(vs) else "Never played"),
            ("Team A as a lineup, any opponent", lineup_rec(ka)), ("Team B as a lineup, any opponent", lineup_rec(kb))]
    row = f"display:flex; justify-content:space-between; gap:12px; padding:12px 0; border-bottom:1px solid {ui.RULE}; font-size:15px"
    hrows = "".join(f"<div style='{row}'><span>{a}</span><span style='font-weight:600'>{b}</span></div>" for a, b in hist)
    team = pm.pivot_table(index="match_id", columns="player", values="team", aggfunc="first")
    win = pm.pivot_table(index="match_id", columns="player", values="result", aggfunc="first")
    prs = ""
    for tm, col in ((TA, A_COL), (TB, B_COL)):
        for a, b in combinations(tm, 2):
            if a in team and b in team:
                same = team[a].notna() & (team[a] == team[b]); n = int(same.sum()); w = int((win.loc[same, a] == "W").sum())
            else:
                n = w = 0
            v = f"{round(w / n * 100)}% · {n} maps" if n else "Never teamed"
            prs += (f"<div style='{row}'><span style='display:inline-flex; align-items:center; gap:10px'>{ui.swatch(col, 10, 10)}{a} + {b}</span>"
                    f"<span style='font-weight:{600 if n and w / n >= 0.55 else 400}'>{v}</span></div>")
    if not prs:
        prs = f"<p style='font-size:14px; color:{ui.MUTED}'>Solo players, so no pairs.</p>"
    th = "".join(f"<th style='padding:8px; font-size:13px; color:{ui.MUTED}; font-weight:500; text-align:center'>{b}</th>" for b in TB)
    trs = ""
    for a in TA:
        tds = ""
        for b in TB:
            if a in team and b in team:
                opp = team[a].notna() & team[b].notna() & (team[a] != team[b]); n = int(opp.sum()); w = int((win.loc[opp, a] == "W").sum())
            else:
                n = w = 0
            if n:
                fr = w / n; bg, fg = ui.shade(fr, n < 5)
                tp = ui.tip(f"{a} vs {b}", f"{a} won {w} of {n} maps against {b}", "Small sample: under 5 maps" if n < 5 else "", below=True)
                tds += (f"<td {ui.TAP} style='text-align:center; padding:8px 4px; background:{bg}; color:{fg}'><span style='display:block; font-size:14px; "
                        f"font-weight:600'>{round(fr * 100)}%</span><span style='display:block; font-size:11px'>{n} maps</span>{tp}</td>")
            else:
                tds += f"<td style='text-align:center; padding:8px 4px; background:{ui.TRACK}; color:{ui.MUTED}; font-size:12px'>Never opposed</td>"
        trs += f"<tr><td style='padding:8px; font-weight:600; white-space:nowrap'>{a}</td>{tds}</tr>"
    ui.html(f"<div style='{GRID2}; margin-top:36px'>"
            f"<section>{label('History of these lineups')}{hrows}{label('Teammate pairs', 24)}{prs}</section>"
            f"<section>{label('Head to head · Team A player’s map win %')}<div style='overflow-x:auto; margin-top:8px'>"
            f"<table style='width:100%; min-width:{100 + 100 * len(TB)}px; border-collapse:separate; border-spacing:3px; font-size:14px'>"
            f"<thead><tr><th></th>{th}</tr></thead><tbody>{trs}</tbody></table></div>"
            + ui.note("Darker means the Team A player usually wins that matchup. Faded: under 5 maps. Hover or tap a cell.", 6, 12) + "</section></div>")

    # ---------------- map outlook
    cfg = ts.get(tid or pm.title.iloc[-1], {})
    modes = [k for k in ["HP", "SND", "OVL", "HJ"] if k in set(pm["mode"])]
    right = h2_row("Map Outlook")
    with right:
        mo = st.segmented_control("Outlook mode", modes, default=modes[0], format_func=MSHORT.get, key="pv_mode", label_visibility="collapsed") or modes[0]
    mcfg = (cfg.get("modes") or {}).get(mo, {})
    active = [m["name"] for m in mcfg.get("maps", []) if m.get("status") != "retired"] or sorted(pm[pm["mode"] == mo]["map"].unique())
    retired = [m["name"] for m in mcfg.get("maps", []) if m.get("status") == "retired"]
    d = pm[pm["mode"] == mo]
    outl = []
    for mp in active:
        x = d[d["map"] == mp]

        def side(t):
            vals, recs = [], []
            for pl in t:
                y = x[x.player == pl]; n = len(y); w = int((y.result == "W").sum())
                vals.append((w + 1) / (n + 2)); recs.append(f"{pl} {w}–{n - w}" if n else f"{pl} never played it")
            return float(np.mean(vals)), recs
        sa, ra = side(TA); sb, rb = side(TB)
        outl.append((mp, sa - sb, ra, rb))
    outl.sort(key=lambda r: -r[1])
    rows = ""
    for mp, dd, ra, rb in outl:
        lab = "Even" if abs(dd) < 0.04 else ("Suits Team A" if dd > 0 else "Suits Team B")
        w = min(abs(dd) / 0.3, 1) * 50
        bar = (f"<div style='position:relative; height:12px; background:{ui.TRACK}'>"
               + (f"<div style='position:absolute; top:0; bottom:0; left:50%; width:{w:.1f}%; background:{A_COL}'></div>" if dd > 0 else
                  f"<div style='position:absolute; top:0; bottom:0; right:50%; width:{w:.1f}%; background:{B_COL}'></div>") + "</div>")
        tp = ui.tip(f"{mp} · {lab}", "Team A: " + " · ".join(ra), "Team B: " + " · ".join(rb), align="l")
        rows += (f"<div {ui.TAP} class='cb-outl' style='display:grid; grid-template-columns:64px minmax(90px, 140px) minmax(0,1fr); align-items:center; gap:12px; padding:8px 0; "
                 f"border-bottom:1px solid {ui.RULE}'><div>{ui.img_tag(mp, width='64px')}</div>"
                 f"<div><div style='font-size:15px; font-weight:600'>{mp}</div><div style='font-size:12px; color:{ui.MUTED}'>{lab}</div></div>{bar}{tp}</div>")
    ui.html(f"<div style='border-top:2px solid {ui.INK}; margin-top:8px'></div>"
            + ui.note("Which maps suit each side, from how these players have done on them. Handy for picking maps. Hover or tap a map for the records behind it.", 10, 13)
            + f"<div style='margin-top:4px'>{rows}</div>"
            + f"<div style='display:flex; justify-content:space-between; font-size:12px; color:{ui.MUTED}; margin-top:8px'><span>← suits Team B</span><span>suits Team A →</span></div>")

    # ---------------- projected stat lines
    right = h2_row("Projected Stat Lines")
    opts = [r[0] for r in outl] + [m for m in retired if m not in active]
    with right:
        mp = st.selectbox(f"{MSHORT[mo]} map", opts, key=f"pv_map_{mo}", format_func=lambda m: m + (" (retired)" if m in retired else ""))
    stats = pj.stats_for(mo)
    lab = {"kills": "Kills", "damage": "Damage", "hill_time": "Hill time", "first_bloods": "First bloods", "overloads": "Overloads"}
    fe = {"kills": lambda v: f"{v:.1f}", "damage": ui.n0, "hill_time": ui.mmss, "first_bloods": lambda v: f"{v:.1f}", "overloads": lambda v: f"{v:.1f}"}
    fr = {"hill_time": ui.mmss, "damage": ui.n0}
    lg = _swings(tid, data.version())
    blocks = ""
    for tm, col, nm in ((TA, A_COL, "Team A"), (TB, B_COL, "Team B")):
        th = "".join(f"<th style='text-align:right; font-weight:600; font-size:12px; color:{ui.MUTED}; padding:8px 6px; border-bottom:1px solid {ui.RULE}; "
                     f"white-space:nowrap'>{lab[s]}</th>" for s in stats)
        trs = ""; tot = {s: 0.0 for s in stats}
        for pl in tm:
            r = _proj(tid, pl, mo, mp, lg, data.version())
            nmo = max((v["nmo"] for v in r.values()), default=0); nmap = max((v["nm"] for v in r.values()), default=0)
            conf = "Low" if nmo < 5 else "Medium" if nmo < 10 else "High"
            cells = ""
            for s in stats:
                if s in r:
                    tot[s] += r[s]["e"]; f_ = fr.get(s, lambda v: str(int(round(v))))
                    cells += (f"<td style='padding:8px 6px; border-bottom:1px solid {ui.RULE}; text-align:right; white-space:nowrap'>"
                              f"<span style='display:block; font-size:15px; font-weight:500'>{fe[s](r[s]['e'])}</span>"
                              f"<span style='display:block; font-size:11px; color:{ui.MUTED}'>{f_(r[s]['lo'])}–{f_(r[s]['hi'])}</span></td>")
                else:
                    cells += f"<td style='padding:8px 6px; border-bottom:1px solid {ui.RULE}; text-align:right'>—</td>"
            sub = f"{conf} confidence · {nmap} here" if r else "No games in this mode"
            trs += (f"<tr><td style='padding:8px 6px; border-bottom:1px solid {ui.RULE}; font-weight:600'>{pl}"
                    f"<span style='display:block; font-size:11px; font-weight:400; color:{ui.MUTED}'>{sub}</span></td>{cells}</tr>")
        trs += (f"<tr><td style='padding:8px 6px; font-size:13px; color:{ui.MUTED}'>Team total</td>"
                + "".join(f"<td style='padding:8px 6px; text-align:right; font-size:14px; font-weight:600'>{fe[s](tot[s])}</td>" for s in stats) + "</tr>")
        blocks += (f"<div style='min-width:0'><div style='display:flex; align-items:center; gap:8px; font-size:12px; font-weight:600; letter-spacing:1.6px; "
                   f"text-transform:uppercase; color:{ui.MUTED}; padding-bottom:8px; border-bottom:1px solid {ui.STEEL}'>{ui.swatch(col, 10, 10)}{nm}</div>"
                   f"<div style='overflow-x:auto'><table style='width:100%; min-width:300px; border-collapse:collapse; font-size:14px'>"
                   f"<thead><tr><th style='text-align:left; font-weight:600; font-size:12px; color:{ui.MUTED}; padding:8px 6px; border-bottom:1px solid {ui.RULE}'>Player</th>{th}</tr></thead>"
                   f"<tbody>{trs}</tbody></table></div></div>")
    ui.html(f"<div style='border-top:2px solid {ui.INK}; margin-top:8px'></div>"
            + ui.note(f"What each player is expected to put up on {mp} {MSHORT[mo]}, with the likely range underneath. Uses the mode picked in Map Outlook.", 10, 13)
            + f"<div style='{GRID2}; margin-top:14px'>{blocks}</div>")
    st.page_link("pages/5_Projections.py", label="Open the full Projections page →")


@st.cache_data(show_spinner=False, max_entries=8)
def _swings(t, v):
    return pj.league_swings(data.engine(t).pm)


@st.cache_data(show_spinner=False, max_entries=512)
def _proj(t, player, mode, mp, _lg, v):
    return pj.project(data.engine(t).pm, player, mode, mp, n=8000, lg=_lg)


if tab == "riv":
    show_rivalries()
else:
    show_preview()