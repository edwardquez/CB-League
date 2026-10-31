"""Player Dashboard: one player's value, slaying and per-mode numbers."""
import plotly.graph_objects as go
import streamlit as st

from cbl import data
from cbl.ui import page, styles as ui

page.start("Players")
opts = data.season_options(True)
values = [v for v, _ in opts]
cur = st.session_state.get("season") or data.default_season()
cur = cur if cur in values else values[0]
ePick = data.engine(page.title_id(cur))
everyone = data.engine(None).players
qp = st.query_params.get("player")
if qp in everyone and "pl_pick" not in st.session_state:
    st.session_state["pl_pick"] = qp

c0, c1, c2 = st.columns([2, 1, 1], vertical_alignment="bottom")
with c1:
    plist = ePick.players or everyone
    who = st.session_state.get("pl_pick", plist[0] if plist else None)
    if who not in plist and who not in everyone:
        who = plist[0]
    who = st.selectbox("Player", everyone if who not in plist else plist, index=(plist if who in plist else everyone).index(who), key="pl_pick")
with c2:
    season = st.selectbox("Season", values, index=values.index(cur), format_func=dict(opts).get, key="_pick_players")
    st.session_state["season"] = season
with c0:
    ui.html(ui.eyebrow(f"Player · {data.season_label(season)}") + ui.h1(who))
st.write("")
e = data.engine(page.title_id(season))
pm = e.pm[e.pm.player == who] if not e.empty else e.pm
if pm.empty:
    ui.html(ui.empty_box(f"No {data.titles().get(season, {}).get('name', 'games')} maps for {who} yet", "Switch to All time for career numbers."))
    st.stop()

n = len(pm)
if n < 10:
    ui.html(f"<p style='margin:8px 0 0; font-size:13px; color:{ui.MUTED}'>{ui.small_sample()} Only {n} maps played, so rates can swing a lot.</p>")
SEC = ["Value", "Slaying"] + [{"HP": "Hardpoint", "SND": "Search and Destroy", "OVL": "Overload", "HJ": "Hijack"}.get(m, m)
                               for m in ["HP", "SND", "OVL", "HJ"] if m in set(pm["mode"])]
ui.html(f"<style>.cb-jump a{{display:inline-flex; align-items:center; min-height:40px; padding:0 16px; border:1px solid {ui.RULE}; "
        f"margin:0 -1px -1px 0; font-size:14px; color:{ui.INK} !important; text-decoration:none !important; background:transparent}}"
        f".cb-jump a{{position:relative}} .cb-jump a:hover{{background:{ui.PANEL}; border-color:{ui.STEEL}; z-index:1}}html{{scroll-behavior:smooth}}</style>"
        "<nav aria-label='Sections' class='cb-jump' style='display:flex; flex-wrap:wrap; margin-top:12px'>"
        + "".join(f"<a href='#{s.lower().replace(' ', '-')}' target='_self'>{s}</a>" for s in SEC) + "</nav>")


def section(title, note, kpis, stats):
    k = "".join(f"<div style='padding:18px 0 14px'><div style='font-weight:300; font-size:42px; line-height:1; color:{c}'>{v}</div>"
                f"<div style='font-size:13px; color:{ui.MUTED}; margin-top:8px'>{l}</div></div>" for v, l, c in kpis)
    s = "".join(f"<div><div style='font-size:20px; font-weight:500'>{v}</div><div style='font-size:12px; color:{ui.MUTED}'>{l}</div></div>" for v, l in stats)
    ui.html(f"<section id='{title.lower().replace(' ', '-')}' style='margin-top:44px'><div style='display:flex; justify-content:space-between; align-items:baseline; "
            f"gap:12px; flex-wrap:wrap; padding-bottom:8px; border-bottom:2px solid {ui.INK}'><div role='heading' class='cb-h2' style='font-weight:300; font-size:34px'>{title}</div>"
            f"<span style='font-size:13px; color:{ui.MUTED}'>{note}</span></div>"
            f"<div style='display:grid; grid-template-columns:repeat(auto-fit, minmax(max(140px, 22%), 1fr)); column-gap:24px'>{k}</div>"
            f"<div style='display:grid; grid-template-columns:repeat(auto-fill, minmax(120px, 1fr)); gap:16px 24px; padding-top:16px; border-top:1px solid {ui.RULE}'>{s}</div></section>")


# ---------------- Value
mvps = e.series_mvps()
smar = e.series_mar(); smar = smar[smar.player == who]
ser = e.series.set_index("_id")
nmvp = sum(1 for v in mvps.values() if v[0] == who)
sw = 0
for sid in smar.series_id:
    r = ser.loc[sid]; side = "A" if who in r.team_a else "B"; sw += int(r.winner == side)
w = int((pm.result == "W").sum())
section("Value", "Map wins added over a fill-in",
        [(ui.sg(pm.mar.sum()), "MAR", ui.BLUE), (ui.sg(pm.mar.mean(), 2), "MAR per map", ui.INK), (str(nmvp), "Series MVPs", ui.INK),
         (f"{sw}-{len(smar) - sw}", "Series record", ui.INK)],
        [(n, "Maps"), (f"{w}-{n - w}", "Map record"), (ui.pct(w / n), "Map win %"), (len(smar), "Series played"), (ui.sg(pm.mar.max(), 2), "Best single-map MAR")])

# MAR by series
x, y, col, hov, tips = [], [], [], [], []
for t in smar.merge(e.series[["_id", "series_no", "date", "title", "team_a", "wins_a", "wins_b", "winner"]], left_on="series_id", right_on="_id").sort_values(["title", "series_no"]).itertuples():
    side = "A" if who in t.team_a else "B"; won = t.winner == side
    is_mvp = mvps.get(t.series_id, ("",))[0] == who
    x.append(f"{'' if season != 'ALL' else data.titles().get(t.title, {}).get('short', '') + ' '}S{int(t.series_no)}"); y.append(t.mar)
    col.append(ui.BLUE if is_mvp else (ui.STEEL if t.mar >= 0 else "#A3AEAD"))
    sc = f"{t.wins_a}-{t.wins_b}" if side == "A" else f"{t.wins_b}-{t.wins_a}"
    tips.append((f"Series {int(t.series_no)} · {t.date.strftime('%b')} {t.date.day}" + (" · Series MVP" if is_mvp else ""),
                 f"{'Won' if won else 'Lost'} {sc}", f"MAR {ui.sg(t.mar, 2)}"))
# bars sized like the mockup: height = MAR size relative to the player's biggest series, 40px wide at most
fmax = max(max((abs(v) for v in y), default=0), 0.01); nb = len(y); gap = "6px" if nb <= 20 else "2px"
bars = labs = ""
for i, (lab, v, (h1_, b1, b2)) in enumerate(zip(x, y, tips)):
    mvp_ = col[i] == ui.BLUE
    fill = ui.BLUE if mvp_ else (ui.STEEL if v >= 0 else "#EEF1EF")
    edge = f"border:1px solid {ui.RULE}; border-bottom:0;" if v < 0 else ""
    tp = ui.tip(h1_, b1, b2, align="l" if i < 3 else "r" if i > nb - 4 else "")
    bars += (f"<div {ui.TAP} style='position:relative; flex:1 1 0; min-width:0; height:100%; display:flex; align-items:flex-end; justify-content:center'>"
             f"<span style='display:block; width:100%; max-width:40px; height:{max(abs(v) / fmax * 130, 3):.0f}px; background:{fill}; box-sizing:border-box; {edge}'></span>{tp}</div>")
    labs += f"<span style='flex:1 1 0; min-width:0; text-align:center; font-size:10px; color:{ui.MUTED}; overflow:hidden'>{lab}</span>"
ui.html(ui.label("MAR by series · hover or tap a bar", margin_top=28)
        + f"<div style='display:flex; align-items:flex-end; gap:{gap}; height:150px; margin-top:12px; border-bottom:1px solid {ui.STEEL}'>{bars}</div>"
        + f"<div style='display:flex; gap:{gap}; margin-top:6px'>{labs}</div>"
        + ui.legend([(ui.swatch(ui.BLUE), "Series MVP"), (ui.swatch(ui.STEEL), "Other series"),
                     (ui.swatch("#EEF1EF", border=f"1px solid {ui.RULE}"), "Below replacement")]))

c1, c2 = st.columns(2, gap="large")
with c1:
    parts = [("Net kills", pm.c_net.sum(), "Kills minus deaths, turned into map wins. The biggest piece for most players."),
             ("Objective", pm.c_obj.sum(), "Hill time, overloads, carrier kills and SnD plants, compared with the average for that mode and lobby size."),
             ("Playmaking", pm.c_play.sum(), "Assists, SnD opening duels and kills while carrying the overload, compared with the average for that mode and lobby size."),
             ("Replacement Credit", pm.c_repl.sum(), f"Earned on every map for being better than a replacement-level fill-in, so it grows with maps played ({n} maps).")]
    bmax = max(9, max(abs(v) for _, v, _ in parts))
    rows = ""
    for lab, v, tx in parts:
        wd = min(1, abs(v) / bmax) * 50
        c = "#B3BDBB" if lab == "Replacement Credit" else (ui.BLUE if v >= 0 else ui.STEEL)
        rows += (f"<div {ui.TAP} style='display:grid; grid-template-columns:140px minmax(0,1fr) 52px; align-items:center; gap:10px; min-height:38px'>"
                 f"<span style='font-size:13px; color:{ui.MUTED if lab == 'Replacement Credit' else ui.INK}'>{lab}</span>"
                 f"<div style='position:relative; height:26px'><div style='position:absolute; left:50%; top:0; bottom:0; width:1px; background:{ui.STEEL}'></div>"
                 f"<div style='position:absolute; top:5px; height:16px; left:{(50 if v >= 0 else 50 - wd):.1f}%; width:{max(wd, 0.6):.1f}%; background:{c}'></div></div>"
                 f"<span style='text-align:right; font-size:13px'>{ui.sg(v)}</span>{ui.tip(f'{lab}: {ui.sg(v, 2)} MAR', tx, align='l')}</div>")
    ui.html(ui.label("Where the MAR comes from", margin_top=12) + f"<div style='margin-top:10px'>{rows}</div>"
            f"<div style='display:grid; grid-template-columns:140px minmax(0,1fr) 52px; gap:10px; padding-top:8px; border-top:1px solid {ui.RULE}; margin-top:4px'>"
            f"<span style='font-size:13px; font-weight:600'>Total MAR</span><span></span><span style='text-align:right; font-size:14px; font-weight:600'>{ui.sg(pm.mar.sum())}</span></div>"
            + ui.note("MAR combines slaying, objective play and playmaking into one number, calibrated on real results. The grey row is "
                      "Replacement Credit: earned on every map, so it grows with maps played. Hover a row for what's in it.", 10, 12))
with c2:
    d = pm.sort_values(["title", "seq"]).reset_index(drop=True)
    roll = d.mar.rolling(5, min_periods=3).mean()
    lab = [f"<b>Series {int(r.series_no)} · Map {int(r.map_no)} · {ui_mode} {r.map}</b><br>MAR {ui.sg(r.mar, 2)} · {int(r.kills)}-{int(r.deaths)} K-D<br>"
           + ("Average starts after 3 maps" if roll[i] != roll[i] else f"5-map average {ui.sg(roll[i], 2)}")
           for i, (r, ui_mode) in enumerate(zip(d.itertuples(), d["mode"].map({"HP": "Hardpoint", "SND": "SnD", "OVL": "Overload", "HJ": "Hijack"})))]
    fig = go.Figure()
    fig.add_hline(y=0, line_color="#A3AEAD", line_width=1)
    fig.add_hline(y=d.mar.mean(), line_color=ui.BLUE, line_dash="dash", line_width=1)
    fig.add_trace(go.Scatter(y=d.mar, mode="markers", marker=dict(color="#9AABAE", size=5), hovertext=lab, hoverinfo="text"))
    fig.add_trace(go.Scatter(y=roll, mode="lines", line=dict(color=ui.INK, width=2.5), hoverinfo="skip"))
    ui.plotly_layout(fig, 240); fig.update_xaxes(showticklabels=False, showgrid=False); fig.update_yaxes(tickformat="+.1f")
    ui.html(ui.label("Form · 5-map rolling MAR", margin_top=12))
    st.plotly_chart(fig, config=ui.PLOT_CONFIG, width="stretch")
    ui.html(ui.legend([(ui.swatch(ui.INK, 18, 3), "5-map average"), (ui.swatch("#9AABAE", 8, 8, True), "Single map"),
                       (f"<span style='width:18px; border-top:1px dashed {ui.BLUE}; display:inline-block'></span>", "Season average")])
            + ui.note("Above the dashed line means playing better than usual. Hover or tap for each map.", 6, 12))

# ---------------- Slaying
k, dd = int(pm.kills.sum()), int(pm.deaths.sum())
section("Slaying", "All modes combined",
        [(f"{k / max(dd, 1):.2f}", "K/D", ui.INK), (f"{pm.kills.mean():.1f}", "Kills per map", ui.INK), (ui.n0(pm.damage.mean()), "Damage per map", ui.INK),
         (("+" if k - dd > 0 else "") + str(k - dd), "Plus/minus", ui.INK)],
        [(f"{k:,}", "Kills"), (f"{dd:,}", "Deaths"), (f"{pm.deaths.mean():.1f}", "Deaths per map"), (f"{pm.assists.mean():.1f}", "Assists per map"),
         (f"{pm.non_traded_kills.mean():.1f}", "Non-traded kills per map"), (ui.n0(pm.highest_streak.max()), "Best streak")])

# ---------------- modes
WINBG = ui.mix(ui.BG, ui.BLUE, 0.25)




for mo in ["HP", "SND", "OVL", "HJ"]:
    m = pm[pm["mode"] == mo]
    if m.empty:
        continue
    nm = len(m); wm = int((m.result == "W").sum()); kd = m.kills.sum() / max(m.deaths.sum(), 1)
    base = [(nm, "Maps"), (f"{wm}-{nm - wm}", "Map record"), (ui.pct(wm / nm), "Win %")]
    if mo == "HP":
        kp = [(ui.sg(m.mar.sum()), "MAR", ui.BLUE), (f"{kd:.2f}", "K/D", ui.INK), (ui.mmss(m.hill_time.mean()), "Hill time per map", ui.INK),
              (f"{m.objective_kills.mean():.1f}", "Objective kills per map", ui.INK)]
        stt = base + [(f"{m.kills.mean():.1f}", "Kills per map"), (ui.n0(m.damage.mean()), "Damage per map"), (ui.n0(m.highest_streak.max()), "Best streak")]
        col = ("Hill", "hill_time", ui.mmss)
    elif mo == "SND":
        kp = [(ui.sg(m.mar.sum()), "MAR", ui.BLUE), (f"{kd:.2f}", "K/D", ui.INK), (ui.n0(m.first_bloods.sum()), "First bloods", ui.INK),
              (ui.sg(m.fbnet.mean(), 2), "First-blood margin per map", ui.INK)]
        stt = base + [(ui.n0(m.first_deaths.sum()), "First deaths"), (ui.n0(m.bombs_planted.sum()), "Bomb plants"),
                      (f"{m.kills.mean():.1f}", "Kills per map"), (ui.n0(m.damage.mean()), "Damage per map")]
        col = ("FB ±", "fbnet", lambda v: ui.sg(v, 0))
    elif mo == "OVL":
        kp = [(ui.sg(m.mar.sum()), "MAR", ui.BLUE), (f"{kd:.2f}", "K/D", ui.INK), (ui.n0(m.overloads.sum()), "Overloads", ui.INK),
              (ui.n0(m.carrier_kills.sum()), "Carrier kills", ui.INK)]
        stt = base + [(ui.n0(m.kills_as_carrier.sum()), "Kills as carrier"), (f"{m.kills.mean():.1f}", "Kills per map"),
                      (ui.n0(m.damage.mean()), "Damage per map"), (ui.n0(m.highest_streak.max()), "Best streak")]
        col = ("OVL", "overloads", lambda v: "—" if v != v else str(int(v)))
    else:
        kp = [(ui.sg(m.mar.sum()), "MAR", ui.BLUE), (f"{kd:.2f}", "K/D", ui.INK), (f"{m.kills.mean():.1f}", "Kills per map", ui.INK),
              (ui.n0(m.damage.mean()), "Damage per map", ui.INK)]
        stt = base
        col = ("Obj", "objective_kills", lambda v: "—" if v != v else str(int(v)))
    name = {"HP": "Hardpoint", "SND": "Search and Destroy", "OVL": "Overload", "HJ": "Hijack"}[mo]
    section(name, f"{nm} maps" + (" · small sample" if nm < 5 else ""), kp, stt)
    with st.expander(f"Show all {nm} maps"):
        kds = list((m.kills / m.deaths.clip(lower=1)).round(2)); mars = list(m.mar)
        rows = []
        for r in m.sort_values(["title", "seq"], ascending=False).itertuples():
            kd_ = round(r.kills / max(r.deaths, 1), 2); a = ui.tint(kd_, kds); b = ui.tint(r.mar, mars); won = r.result == "W"
            rows.append([f"Series {int(r.series_no)}", {"v": r.map, "w": 500}, {"v": "Won" if won else "Lost", "bg": WINBG if won else "transparent",
                         "fg": ui.INK if won else ui.MUTED, "w": 600 if won else 400}, f"{int(r.kills)}-{int(r.deaths)}",
                         {"v": f"{kd_:.2f}", "bg": a[0], "fg": a[1], "w": 500}, ui.n0(r.damage), col[2](getattr(r, col[1])),
                         {"v": ui.sg(r.mar, 2), "bg": b[0], "fg": b[1], "w": 600}])
        ui.html(ui.table([("Series", "left"), ("Map", "left"), ("Result", "left"), ("K-D", "right"), ("K/D", "right"), ("Dmg", "right"),
                          (col[0], "right"), ("MAR", "right")], rows, min_width=560, cell_pad="9px 6px")
                + ui.note("K/D and MAR shaded against this player's own maps in this mode: the darker the blue, the better.", 6, 12))

st.write("")
_csv = pm.drop(columns=["_id"], errors="ignore")
_num = _csv.select_dtypes("number").columns          # round the numbers only (pandas warns when asked to round dates)
_csv[_num] = _csv[_num].round(3)
st.download_button(f"Download {who}'s maps (CSV)", _csv.to_csv(index=False).encode(),
                   f"{who.lower()}_maps.csv", "text/csv")