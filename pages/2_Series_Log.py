"""Series Log: every series, newest first, with a full recap for each."""
import pandas as pd
import streamlit as st

from cbl import data
from cbl.ui import page, styles as ui

page.start("Series Log")
season = page.header("Series Log")
e = data.engine(page.title_id(season))
ts = data.titles()
if e.series.empty:
    ui.html(ui.empty_box(f"No {ts.get(season, {}).get('name', '')} series yet", "Series show up here as soon as they are entered in the Scorekeeper."))
    st.stop()

S, M, PM = e.series, e.maps, e.pm
mvps = e.series_mvps()
smar = e.series_mar().set_index(["series_id", "player"]).mar
MODE = {"HP": "Hardpoint", "SND": "SnD", "OVL": "Overload", "HJ": "Hijack"}
MS = {"HP": "HP", "SND": "SnD", "OVL": "OVL", "HJ": "HJ"}
WINBG = ui.mix(ui.BG, ui.BLUE, 0.25)


def snum(r):
    t = ts.get(r.title, {}).get("short", r.title)
    return f"Series {int(r.series_no)}" if season != "ALL" else f"{t} Series {int(r.series_no)}"


# query param ?series=BO7-S001 opens that recap (from a shared link)
qp = st.query_params.get("series")
if qp and "sl_open" not in st.session_state:
    st.session_state["sl_open"] = qp
opened = st.session_state.get("sl_open")

top = st.columns([3, 1, 1], vertical_alignment="center")
with top[0]:
    ui.html(f"<p style='margin:0; font-size:14px; color:{ui.MUTED}'>{len(S)} series · {len(M)} maps · newest first. Open any series for its recap.</p>")
with top[1]:
    st.download_button("Series CSV", S.drop(columns=["private_note"], errors="ignore").to_csv(index=False).encode(), "series.csv", "text/csv", width="stretch")
with top[2]:
    cols = ["series_id", "map_no", "mode", "map", "player", "team", "result", "kills", "deaths", "assists", "damage", "hill_time",
            "first_bloods", "first_deaths", "bombs_planted", "overloads", "carrier_kills", "kills_as_carrier", "mar"]
    st.download_button("Maps CSV", PM[cols].round(3).to_csv(index=False).encode(), "maps.csv", "text/csv", width="stretch")
ui.html(f"<div style='border-top:2px solid {ui.INK}; margin-top:14px'></div>")




for r in S.iloc[::-1].itertuples():
    sid = r._1 if hasattr(r, "_1") else r[1]
    sid = S.loc[r.Index, "_id"]
    aw = r.winner == "A"; bw = r.winner == "B"
    ca, cb = (ui.INK if aw else ui.MUTED), (ui.INK if bw else ui.MUTED)
    early = ui.tagbox("Ended early", ui.MUTED, ui.STEEL) if r.ended_early else ""
    if r.status == "open":
        early = ui.tagbox("In progress", ui.BLUE, ui.BLUE)
    mv = mvps.get(sid)
    mvp = f"Top MAR <b style='font-weight:600; color:{ui.BLUE}'>{mv[0]} {ui.sg(mv[1], 2)}</b>" if mv else ""
    d = r.date
    c1, c2 = st.columns([6, 1], vertical_alignment="center")
    with c1:
        ui.html(f"<div style='display:flex; justify-content:space-between; gap:8px 16px; flex-wrap:wrap; padding-top:14px; font-size:13px; color:{ui.MUTED}'>"
                f"<span><b style='font-weight:600; color:{ui.INK}'>{snum(r)}</b> · {d.strftime('%b')} {d.day} · {r.format} · Best of {r.best_of}{early}</span><span>{mvp}</span></div>"
                "<div style='display:grid; grid-template-columns:minmax(0,1fr) auto minmax(0,1fr); align-items:center; gap:8px 20px; padding:14px 0 12px'>"
                f"<span style='text-align:right; font-size:16px; color:{ca}; font-weight:{600 if aw else 400}'>{', '.join(r.team_a)}</span>"
                f"<span style='display:flex; align-items:center; gap:14px; font-weight:300; font-size:30px; line-height:1'><span style='color:{ca}'>{r.wins_a}</span>"
                f"<span style='display:inline-block; width:14px; height:1px; background:{ui.MUTED}'></span><span style='color:{cb}'>{r.wins_b}</span></span>"
                f"<span style='font-size:16px; color:{cb}; font-weight:{600 if bw else 400}'>{', '.join(r.team_b)}</span></div>")
    with c2:
        is_open = opened == sid
        if st.button("Hide recap" if is_open else "Recap", key=f"btn_{sid}", type="primary" if is_open else "secondary", width="stretch"):
            st.session_state["sl_open"] = None if is_open else sid
            st.rerun()
    if opened == sid:
        maps = M[M.series_id == sid].sort_values("map_no")
        lc1, lc2 = st.columns([1, 3], vertical_alignment="center")
        with lc1:
            if st.button("Copy link", key=f"lnk_{sid}"):
                st.query_params["series"] = sid
                st.session_state[f"show_link_{sid}"] = True
        if st.session_state.get(f"show_link_{sid}"):
            with lc2:
                st.code(f"?series={sid}", language=None)
                ui.html(ui.note("Add this to the end of the app's address to open this recap.", 0, 12))
        if r.public_note:
            ui.html(f"<p style='margin:6px 0 0; font-size:14px; color:{ui.MUTED}'>Notes: {r.public_note}</p>")
        cards = ""
        for mm in maps.itertuples():
            bar = ui.INK if mm.winner == "A" else ui.BLUE
            ln = f" · {ui.mmss(mm.length_sec)}" if mm.length_sec == mm.length_sec and mm.length_sec else ""
            cards += (f"<div style='background:{ui.PANEL}'>{ui.img_tag(mm.map)}<div style='padding:8px 10px 10px'>"
                      f"<div style='font-size:11px; color:{ui.MUTED}'>Map {mm.map_no} · {MODE.get(mm.mode, mm.mode)}{ln}</div>"
                      f"<div style='display:flex; justify-content:space-between; align-items:baseline; gap:6px; margin-top:2px'>"
                      f"<span style='font-size:14px; font-weight:600'>{mm.map}</span><span style='font-size:13px'>{mm.score_a}–{mm.score_b}</span></div>"
                      f"<div style='height:4px; background:{bar}; margin-top:8px'></div></div></div>")
        ui.html(ui.label("Map by map", margin_top=10)
                + f"<div style='display:grid; grid-template-columns:repeat(auto-fill, minmax(150px, 1fr)); gap:10px; margin-top:10px'>{cards}</div>"
                + ui.legend([(ui.swatch(ui.INK, 18, 4), f"{', '.join(r.team_a)} Won · {r.wins_a} Map{'s' if r.wins_a != 1 else ''}"),
                             (ui.swatch(ui.BLUE, 18, 4), f"{', '.join(r.team_b)} Won · {r.wins_b} Map{'s' if r.wins_b != 1 else ''}")]))
        # series totals per team
        sp = PM[PM.series_id == sid]
        tot = sp.groupby(["team", "player"]).agg(k=("kills", "sum"), d=("deaths", "sum"), dmg=("damage", "sum"), mar=("mar", "sum")).reset_index()
        tot["kd"] = tot.k / tot.d.clip(lower=1)
        blocks = ""
        for side, team in (("A", r.team_a), ("B", r.team_b)):
            rows = []
            for t in tot[tot.team == side].sort_values("mar", ascending=False).itertuples():
                top_ = mv and t.player == mv[0]
                bk = ui.tint(round(t.kd, 2), list(tot.kd.round(2))); bm = ui.tint(t.mar, list(tot.mar)); bd = ui.tint(t.dmg, list(tot.dmg))
                rows.append([{"v": t.player + (" · MVP" if top_ else ""), "w": 600 if top_ else 400}, str(int(t.k)), str(int(t.d)),
                             {"v": f"{t.kd:.2f}", "bg": bk[0], "fg": bk[1]}, {"v": ui.n0(t.dmg), "bg": bd[0], "fg": bd[1]},
                             {"v": ui.sg(t.mar, 2), "bg": bm[0], "fg": bm[1], "w": 600}])
            blocks += (f"<div><div style='font-size:14px; font-weight:600; padding-bottom:8px; border-bottom:2px solid {ui.INK}'>{', '.join(team)} "
                       f"<span style='font-weight:400; color:{ui.MUTED}'>· Series Totals</span></div>"
                       + ui.table([("Player", "left"), ("K", "right"), ("D", "right"), ("K/D", "right"), ("Dmg", "right"), ("MAR", "right")],
                                  rows, min_width=320, cell_pad="9px 6px") + "</div>")
        ui.html(f"<div style='display:grid; grid-template-columns:repeat(auto-fit, minmax(max(280px, 45%), 1fr)); gap:24px 32px; margin-top:28px'>{blocks}</div>"
                + ui.label("Scoreboards", margin_top=28))
        labels = {mm.map_no: f"{mm.map_no} · {MS.get(mm.mode, mm.mode)} {mm.map}" for mm in maps.itertuples()}
        pick = st.segmented_control("Map", list(labels), default=list(labels)[0], format_func=labels.get, key=f"sb_{sid}",
                                    label_visibility="collapsed") or list(labels)[0]
        mm = maps[maps.map_no == pick].iloc[0]
        rows_ = PM[PM.match_id == mm["_id"]]
        stat = {"HP": ("Hill", "hill_time", ui.mmss), "SND": ("FB ±", "fbnet", lambda v: ui.sg(v, 0) if v == v else "—"),
                "OVL": ("OVL", "overloads", lambda v: "—" if v != v else str(int(v)))}.get(mm["mode"], ("Obj", "objective_kills", lambda v: "—" if v != v else str(int(v))))
        kds = list((rows_.kills / rows_.deaths.clip(lower=1)).round(2)); mars = list(rows_.mar); ms = list(rows_[stat[1]].fillna(0))
        body = []
        for side in ("A", "B"):
            if side == "B":
                body.append("SPACER")
            for x in rows_[rows_.team == side].sort_values("mar", ascending=False).itertuples():
                kd = round(x.kills / max(x.deaths, 1), 2); a, b_, c = ui.tint(kd, kds), ui.tint(x.mar, mars), ui.tint(getattr(x, stat[1]) if getattr(x, stat[1]) == getattr(x, stat[1]) else 0, ms)
                body.append([{"v": x.player, "w": 500, "fg": ui.INK if side == mm.winner else ui.MUTED}, str(int(x.kills)), str(int(x.deaths)),
                             {"v": f"{kd:.2f}", "bg": a[0], "fg": a[1]}, "—" if x.assists != x.assists else str(int(x.assists)),
                             ui.n0(x.damage), {"v": stat[2](getattr(x, stat[1])), "bg": c[0], "fg": c[1]}, {"v": ui.sg(x.mar, 2), "bg": b_[0], "fg": b_[1], "w": 600}])
        won = r.team_a if mm.winner == "A" else r.team_b
        ln = f" · {ui.mmss(mm.length_sec)}" if mm.length_sec == mm.length_sec and mm.length_sec else ""
        ui.html(f"<p style='margin:4px 0 0; font-size:14px'>{ {'HP': 'Hardpoint', 'SND': 'Search and Destroy', 'OVL': 'Overload'}.get(mm['mode'], mm['mode'])} on {mm['map']} · "
                f"{mm.score_a}–{mm.score_b}{ln} · Won by {', '.join(won)}" + (" · partial scoreboard" if mm.get("board") == "partial" else "") + "</p>"
                + ui.legend([("".join(ui.swatch(c, 14, 12) for c in ["#EEF1EF", "#B5C5C9", "#80A0AB", "#487688", ui.BLUE]), "Lowest → Highest in This Lobby"),
                             ("", "Blank (—) Means the Stat Wasn't Recorded")])
                + ui.table([("Player", "left"), ("K", "right"), ("D", "right"), ("K/D", "right"), ("A", "right"), ("Dmg", "right"),
                            (stat[0], "right"), ("MAR", "right")], body, min_width=560, cell_pad="9px 6px")
                + "<div style='height:24px'></div>")
    ui.html(f"<div style='border-bottom:1px solid {ui.RULE}'></div>")