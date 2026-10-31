"""CB League: Home (all-time league overview)."""
import pandas as pd
import streamlit as st

from cbl import data
from cbl.ui import page, styles as ui

page.start("Home")
e = data.engine(None)
ts = data.titles()

ui.html(ui.eyebrow("All time · every title") + ui.h1("CB League Overview"))

if e.empty:
    ui.html(ui.empty_box("No games yet", "Stats appear after the first series is entered in the Scorekeeper."))
    st.stop()

pm, s, m = e.pm, e.series, e.maps
MIN = 10
sweeps = int(((s.wins_a == 0) | (s.wins_b == 0)).sum())
st_ = e.standings()
q = st_[st_.n >= MIN]
mvps = pd.Series([v[0] for v in e.series_mvps().values()]).value_counts()
top_mvp = mvps[mvps == mvps.max()].index.tolist()

ui.html(ui.label("League at a glance", margin_top=40) + ui.kpis([
    (str(s.title.nunique()), "Titles tracked"), (str(len(s)), "Series played"), (str(len(m)), "Maps played"),
    (str(pm.player.nunique()), "Players"), (f"{int(pm.kills.sum()):,}", "Kills"),
    (f"{pm.damage.sum() / 1000:,.0f}K", "Damage dealt"), (f"{pm.hill_time.sum() / 3600:.1f} hrs", "Time on the hill"),
    (str(sweeps), "Sweeps")]))


def lead(col, fmt, label, src=None, color=ui.INK):
    t = (src if src is not None else q)
    if t.empty or col not in t or t[col].dropna().empty:
        return ""
    p = t[col].idxmax()
    return (f"<div style='padding:18px 0; border-bottom:1px solid {ui.RULE}'><div style='font-weight:300; font-size:34px; "
            f"line-height:1; color:{color}'>{fmt(t.loc[p, col])}</div><div style='font-size:13px; color:{ui.MUTED}; margin-top:6px'>"
            f"{label}</div><div style='font-size:15px; font-weight:600; margin-top:8px'>{p}</div></div>")


hp = e.standings("HP"); hp = hp[hp.n >= 5]
snd = e.standings("SND"); ovl = e.standings("OVL")
cells = [lead("mar", ui.sg, "MAR", color=ui.BLUE), lead("kd", lambda v: f"{v:.2f}", "K/D"), lead("wp", ui.pct, "Win %"),
         lead("dmg", ui.n0, "Damage per map"), lead("hill", ui.mmss, "Hill time per map", hp),
         lead("fb", lambda v: f"{int(v)}", "First bloods", snd), lead("ovl", lambda v: f"{int(v)}", "Overloads", ovl)]
cells.append(f"<div style='padding:18px 0; border-bottom:1px solid {ui.RULE}'><div style='font-weight:300; font-size:34px; line-height:1'>"
             f"{int(mvps.max())}</div><div style='font-size:13px; color:{ui.MUTED}; margin-top:6px'>Series MVPs</div>"
             f"<div style='font-size:15px; font-weight:600; margin-top:8px'>{' &amp; '.join(top_mvp)}</div></div>")
ui.html("<div style='margin-top:40px; display:flex; justify-content:space-between; align-items:baseline; gap:4px 12px; flex-wrap:wrap'>"
        + ui.label("League leaders") + f"<span style='font-size:12px; color:{ui.MUTED}'>Career · min. {MIN} maps</span></div>"
        + "<div style='display:grid; grid-template-columns:repeat(auto-fit, minmax(max(200px, 22%), 1fr)); column-gap:24px; "
        f"border-top:2px solid {ui.INK}; margin-top:12px'>{''.join(cells)}</div>")

MS = {"HP": "HP", "SND": "SnD", "OVL": "OVL", "HJ": "Hijack"}


def rec(col, label, fmt=lambda v: f"{int(v):,}"):
    d = pm.dropna(subset=[col])
    if d.empty:
        return ""
    r = d.loc[d[col].idxmax()]
    t = ts.get(r.title, {}).get("short", r.title)
    return (f"<div style='display:grid; grid-template-columns:minmax(0,1fr) auto; gap:2px 12px; padding:14px 0; border-bottom:1px solid {ui.RULE}'>"
            f"<span style='font-size:13px; color:{ui.MUTED}'>{label}</span><span style='font-weight:300; font-size:28px; grid-row:span 2; align-self:center'>"
            f"{fmt(r[col])}</span><span style='font-size:15px'><b style='font-weight:600'>{r.player}</b> <span style='color:{ui.MUTED}; font-size:13px'>"
            f"{MS.get(r['mode'], r['mode'])} {r['map']} · {t} Series {int(r.series_no)}</span></span></div>")


seasons = ""
for tid in sorted(ts, key=lambda t: -ts[t].get("order", 0)):
    t = ts[tid]; ss = s[s.title == tid]
    if ss.empty:
        right = f"<span style='color:{ui.MUTED}'>Starting soon</span>" if t.get("current") else "<span>—</span>"
    else:
        sm = pd.Series([v[0] for k, v in e.series_mvps().items() if k.startswith(tid + "-")])
        right = (f"{len(ss)} series <span style='color:{ui.MUTED}'>· MVP {e.pm[e.pm.title == tid].groupby('player').mar.sum().idxmax()}</span>")
    seasons += (f"<span style='padding:14px 0; border-bottom:1px solid {ui.RULE}'>{t['name']} <span style='color:{ui.MUTED}; font-size:13px'>{t['year']}</span></span>"
                f"<span style='padding:14px 0; border-bottom:1px solid {ui.RULE}; text-align:right'>{right}</span>")
mc = m.groupby("mode").size()
mc = mc.reindex([k for k in ["HP", "SND", "OVL", "HJ"] if k in mc.index] + [k for k in mc.index if k not in ("HP", "SND", "OVL", "HJ")])
cols = {"HP": ui.INK, "SND": ui.BLUE, "OVL": ui.STEEL, "HJ": ui.SLATE}
bar = "".join(f"<div style='flex:{mc[k]} 1 0; background:{cols.get(k, ui.STEEL)}'></div>" for k in mc.index)
lab = "".join(f"<span>{ {'HP': 'Hardpoint', 'SND': 'SnD', 'OVL': 'Overload', 'HJ': 'Hijack'}.get(k, k)} {mc[k]}</span>" for k in mc.index)
ui.html("<div style='display:grid; grid-template-columns:repeat(auto-fit, minmax(max(280px, 45%), 1fr)); gap:40px 48px; margin-top:40px'>"
        f"<section>{ui.label('Single-map records', rule=False)}<div style='border-top:2px solid {ui.INK}; margin-top:12px'>"
        + rec("kills", "Most kills") + rec("highest_streak", "Longest streak") + rec("damage", "Most damage") + "</div></section>"
        f"<section>{ui.label('Seasons')}<div style='display:grid; grid-template-columns:minmax(0,1fr) auto; gap:0 16px; font-size:15px; "
        f"border-top:2px solid {ui.INK}; margin-top:12px'>{seasons}</div>"
        f"<div style='margin-top:24px; font-size:13px; color:{ui.MUTED}'>Maps by mode</div>"
        f"<div role='img' style='display:flex; gap:3px; height:14px; margin-top:8px'>{bar}</div>"
        f"<div style='display:flex; justify-content:space-between; margin-top:8px; font-size:13px'>{lab}</div></section></div>")

last = s.date.max()
ui.html(f"<footer style='margin-top:56px; padding-top:18px; border-top:1px solid {ui.RULE}; display:flex; gap:14px; align-items:flex-start; max-width:640px'>"
        f"<span style='flex:none; display:inline-flex; align-items:center; justify-content:center; width:30px; height:30px; background:{ui.INK}; "
        f"color:{ui.BG}; font-size:11px; font-weight:600; letter-spacing:1px'>CB</span><p style='margin:0; font-size:13px; color:{ui.MUTED}; line-height:1.55'>"
        "CB League tracks every series our group plays, one Call of Duty at a time. Each season keeps its own modes, maps and stats, "
        f"and the all-time view ties them together. Last updated {last.strftime('%b')} {last.day}, {last.year}.</p></footer>")