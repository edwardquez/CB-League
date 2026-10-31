"""Tournaments: set one up, run the bracket, enter maps, and see 2v2 stats.

Tournament games live in their own collections (cbl/db.py), so they never reach the Series Log or any
regular stat. Viewing is open to everyone; creating a tournament and entering results needs the
Scorekeeper password (or practice mode, which works on a private copy just like the Scorekeeper's).
"""
from __future__ import annotations

import datetime as dt
import hmac
import math
import random
from html import escape

import pandas as pd
import streamlit as st

from cbl import data, tourney as T
from cbl.db import is_preview
from cbl.config import STAT_LABELS
from cbl.ui import map_entry as me, page, styles as ui

STAT_KEYS = list(STAT_LABELS)

page.start("Tournaments")
ss = st.session_state
TEAMC = [ui.BLUE, "#8C5A3C", "#4F6B3A", "#6B4E71", "#2E6F6A", "#9A7B3C", "#7A4450", "#3F5A7A",
         "#5A6B2E", "#7B5A8C", "#2F5D50", "#8A6A2F", "#5C4A3F", "#3E6B7A", "#6E3F55", "#4A4F7A"]
MINMAPS = 3                          # fewer maps than this: shown in grey, not shaded or ranked
CARD_H, GAP = 90, 22                 # bracket card height and the space between two first-round cards
MODEN, SHORT = me.MODEN, me.SHORT

ui.html(f"""<style>
[class*="st-key-tncard_"] {{ position: relative; gap: 0 !important; }}
[class*="st-key-tncard_"] [data-testid="stElementContainer"]:has(button) {{ position: absolute; inset: 0; z-index: 3; margin: 0; }}
[class*="st-key-tncard_"] [data-testid="stElementContainer"]:has(button) > div, [class*="st-key-tncard_"] .stButton {{ height: 100%; }}
[class*="st-key-tncard_"] button {{ width: 100%; height: 100% !important; min-height: 0; opacity: 0; cursor: pointer; }}
[class*="st-key-tncard_"]:hover .tn-card {{ border-color: {ui.INK}; }}
[class*="st-key-tnbr_"] [data-testid="stHorizontalBlock"] {{ gap: 32px !important; }}
[class*="st-key-tnbr_"] [data-testid="stVerticalBlock"] {{ gap: 0 !important; }}
.st-key-tn_head {{ background: {ui.PANEL}; padding: 16px 18px 20px !important; }}
.st-key-tn_head [data-testid="stMarkdownContainer"] {{ margin-bottom: 0 !important; }}
[class*="st-key-tnbr_"] [data-testid="stMarkdownContainer"], [class*="st-key-tncard_"] [data-testid="stMarkdownContainer"],
[class*="st-key-tnfmt_"] [data-testid="stMarkdownContainer"] {{ margin-bottom: 0 !important; }}
.tn-conn {{ position: absolute; background: {ui.STEEL}; pointer-events: none; }}
[class*="st-key-tnfmt_"] {{ position: relative; gap: 0 !important; }}
[class*="st-key-tnfmt_"] [data-testid="stElementContainer"]:has(button) {{ position: absolute; inset: 0; z-index: 3; margin: 0; }}
[class*="st-key-tnfmt_"] [data-testid="stElementContainer"]:has(button) > div, [class*="st-key-tnfmt_"] .stButton {{ height: 100%; }}
[class*="st-key-tnfmt_"] [data-testid="stElementContainer"]:has(button), [class*="st-key-tncard_"] [data-testid="stElementContainer"]:has(button) {{ width: 100% !important; }}
[class*="st-key-tnfmt_"] button {{ width: 100%; height: 100% !important; opacity: 0; }}
.st-key-tn_roster {{ gap: 6px !important; }}
.st-key-tn_roster button {{ min-height: 44px; padding: 0 14px; }}
[class*="st-key-tn_seedrow_"] button {{ min-height: 36px; padding: 0 10px; }}
@media (max-width: 640px) {{
  .tn-sp, .tn-conn {{ display: none !important; }}
  [class*="st-key-tncard_"] {{ margin-bottom: 10px; }}
  .tn-roundlab {{ margin-top: 14px; }}
  .tn-right {{ text-align: left !important; }}
}}
</style>""" + me.css())


# ===================================================================== access
def secret_pw():
    try:
        return st.secrets["scorekeeper"]["password"]
    except Exception:
        return None


def cb_practice(on):
    if on:
        data.start_practice()
    else:
        data.stop_practice()
    keep_top = ss.get("tn_top")
    for k in [k for k in ss if k.startswith("tn_") and k not in ("tn_cur",)]:
        del ss[k]
    if keep_top:
        ss.tn_top_goto = keep_top  # stay on the same tab


PRACTICE = bool(ss.get("practice")) and "practice_db" in ss
PW = secret_pw()
if not ss.get("sk_auth") and PW is None and is_preview():
    ss.sk_auth = True
CAN_EDIT = bool(ss.get("sk_auth")) or PRACTICE


def unlock_box(why: str = "enter results"):
    """Password form (shared with the Scorekeeper) plus the practice-mode way in."""
    with st.container(border=True):
        ui.html(f"<div style='font-size:16px; font-weight:600'>Unlock to {why}</div>"
                + ui.note("Uses the Scorekeeper password. Just testing? Practice mode works on a private copy, so nothing is saved.", 4, 13)
                + "<div style='height:12px'></div>")
        if PW is not None:
            with st.form(f"tn_login_{why.replace(' ', '_')}"):
                got = st.text_input("Password", type="password")
                if st.form_submit_button("Unlock", type="primary"):
                    if hmac.compare_digest(got.encode(), str(PW).encode()):
                        ss.sk_auth = True
                        st.rerun()
                    st.error("That password didn't match.")
        st.button("Try Practice Mode", on_click=cb_practice, args=(True,), key=f"tn_try_{why.replace(' ', '_')}")


# ===================================================================== data
ts = data.titles()
cur_title = data.current_title()
TD = data.load_tdocs()
TOURS = sorted(TD["tournaments"], key=lambda x: (x.get("date") or "", x.get("created") or ""), reverse=True)


def tmaps(tid):
    return [m for m in TD["t_matches"] if m["tournament_id"] == tid]


def tpms(tid=None):
    return [r for r in TD["t_player_matches"] if tid is None or r["tournament_id"] == tid]


def team_kd(tid):
    k, d = {}, {}
    for r in tpms(tid):
        k[r["team_id"]] = k.get(r["team_id"], 0) + (r.get("kills") or 0)
        d[r["team_id"]] = d.get(r["team_id"], 0) + (r.get("deaths") or 0)
    return {x: k[x] / max(d.get(x, 0), 1) for x in k}


@st.cache_data(ttl=600, show_spinner=False)
def _ratings(title, version):  # noqa: D401
    """This game's ratings; anyone without one here falls back to their all-time rating."""
    out = {}
    for tid in (None, title):
        e = data.engine(tid)
        if not e.empty:
            out.update(e.ratings()[0])
    return out


def ratings(title=None):
    return _ratings(title or cur_title, data.version())


def fmt_date(s):
    try:
        d = pd.Timestamp(s)
        return f"{d.strftime('%b')} {d.day}"
    except Exception:
        return s or ""


# ===================================================================== header
view = ss.get("tn_view", "main")
ids = [x["_id"] for x in TOURS]


def _finished(d):
    mp = tmaps(d["_id"]); kd = team_kd(d["_id"])
    return T.champion(d, T.resolve(d, mp, kd), mp, kd) is not None


FIN = {x["_id"]: _finished(x) for x in TOURS}  # worked out from the bracket, never a stored flag
# picker labels must be unique, or the picker can't tell two "Winter Cup · Jan 16" apart
_lab = {x["_id"]: f"{x['name']} · {fmt_date(x.get('date'))}" for x in TOURS}
_seen = {}
for _x in reversed(TOURS):
    _l = _lab[_x["_id"]]; _seen[_l] = _seen.get(_l, 0) + 1
    if _seen[_l] > 1:
        _lab[_x["_id"]] = f"{_l} ({_seen[_l]})"
cur_id = ss.pop("tn_goto", None) or ss.get("tn_cur")
if cur_id not in ids:
    cur_id = ids[0] if ids else None
ss.tn_cur = cur_id
SEL = next((x for x in TOURS if x["_id"] == cur_id), None)
if "tn_top_goto" in ss:
    ss["tn_top"] = ss.pop("tn_top_goto")
top = ss.get("tn_top") or "view"
form_open = top == "setup" and CAN_EDIT and ss.get("tn_form")
# the eyebrow names the game of what's on screen: the tournament being viewed, or the one being set up
if view == "entry":
    game = next((x["title"] for x in TOURS if x["_id"] == (ss.get("tn_entry") or {}).get("tid")), cur_title)
elif form_open:
    game = ss.get("tn_s_title") or (ss.get("tn_setup") or {}).get("title") or cur_title
else:
    game = SEL["title"] if SEL else cur_title
left, right = st.columns([2.4, 1.2], vertical_alignment="bottom")
with left:
    ui.html(ui.eyebrow(f"{ts.get(game, {}).get('name', '')} · {ts.get(game, {}).get('year', '')}") + ui.h1("Tournaments"))
with right:
    if view == "main" and top == "view" and TOURS:
        if ss.get("tn_pick") != cur_id:
            ss.pop("tn_pick", None)
        st.selectbox("Tournament", ids, index=ids.index(cur_id), key="tn_pick", on_change=lambda: ss.__setitem__("tn_cur", ss.tn_pick),
                     format_func=_lab.get)
if PRACTICE:
    c1, c2 = st.columns([4, 1], vertical_alignment="center")
    with c1:
        ui.html(f"<div style='margin-top:14px; padding:10px 12px; background:{ui.mix(ui.BG, ui.BLUE, 0.15)}; border:1px solid {ui.BLUE}; font-size:14px; line-height:1.5'>"
                "<b style='font-weight:600'>Practice mode</b> · a private copy of the data. Tournaments made here aren't saved, "
                "and they're cleared when you leave. The Simulate buttons fill in results so you can test quickly.</div>")
    with c2:
        ui.html("<div style='height:14px'></div>")
        st.button("Leave Practice", on_click=cb_practice, args=(False,), key="tn_practice_off", width="stretch")
ui.html("<div style='height:18px'></div>")


# ===================================================================== helpers for one tournament
class Tour:
    def __init__(self, doc):
        for m in doc["matches"]:  # older tournaments were saved with lower-case labels
            m["label"] = T.title_label(m["label"])
        self.t = doc
        self.maps = tmaps(doc["_id"])
        self.kd = team_kd(doc["_id"])
        self.R = T.resolve(doc, self.maps, self.kd)
        self.teams = {x["id"]: x for x in doc["teams"]}
        self.ms = {m["id"]: m for m in doc["matches"]}
        self.color = {x["id"]: TEAMC[i % len(TEAMC)] for i, x in enumerate(doc["teams"])}

    def name(self, tid):
        if tid == T.BYE:
            return "Bye"
        return self.teams[tid]["name"] if tid in self.teams else "TBD"

    def src_text(self, src):
        if "seed" in src:
            return f"Seed {src['seed']}"
        if "win" in src:
            return f"Winner of {self.ms[src['win']]['label']}"
        if "lose" in src:
            return f"Loser of {self.ms[src['lose']]['label']}"
        if "rank" in src:
            stage = "the regular season" if self.t["format"] == "rrp" else "the Swiss rounds"
            return f"#{src['rank']} after {stage}"
        return "TBD"

    def side_name(self, m, side):
        tid = self.R[m["id"]][side]
        return self.name(tid) if tid else self.src_text(m[side])

    def seed_of(self, tid):
        return self.teams[tid]["seed"] if tid in self.teams else ""


def is_pool(m):
    return m["stage"] in ("RR", "SW")


# ---------------------------------------------------------------- one match card (HTML) with a clickable overlay
def card_html(tour, m, sel, h=CARD_H, extra=""):
    r = tour.R[m["id"]]
    st_ = r["status"]
    live = st_ == "live"
    rows = []
    for i, side in enumerate(("a", "b")):
        tid = r[side]
        known = tid not in (None,)
        won = st_ == "done" and r["winner"] == tid
        lost = st_ == "done" and r["loser"] == tid
        sc = ""
        if r["manual"]:
            sc = "W" if won else ""
        elif st_ in ("done", "live"):
            sc = str(r["wa"] if side == "a" else r["wb"])
        nm = tour.side_name(m, side)
        seed = tour.seed_of(tid) if known and tid in tour.teams else ""
        fg = ui.MUTED if (lost or not known or tid == T.BYE) else ui.INK
        fs = 14 if known else 13
        sw = f"<span style='width:4px; align-self:stretch; background:{tour.color.get(tid, 'transparent')}'></span>"
        rows.append(f"<div style='display:grid; grid-template-columns:4px 20px minmax(0,1fr) 26px; align-items:center; gap:6px; height:33px; "
                    f"padding:0 10px 0 0; border-top:{'1px solid ' + ui.RULE if i else '0'}'>{sw}<span style='font-size:11px; color:{ui.MUTED}'>{seed}</span>"
                    f"<span title='{escape(nm)}' style='font-size:{fs}px; font-weight:{600 if won else 400}; color:{fg}; white-space:nowrap; overflow:hidden; text-overflow:ellipsis'>{escape(nm)}</span>"
                    f"<span style='text-align:right; font-size:15px; font-weight:{600 if won else 400}; color:{fg}'>{sc}</span></div>")
    foot_l = {"live": f"LIVE · map {r['wa'] + r['wb'] + 1} next", "done": "Final" + (" · winner only" if r["manual"] else ""), "ready": "Ready",
              "waiting": "Waiting", "bye": "Bye", "skipped": "Not Needed"}[st_]
    if m.get("if_needed") and st_ in ("waiting", "ready"):
        foot_l = "If Needed"
    dashed = m.get("if_needed") or st_ in ("bye", "skipped")
    edge = ui.BLUE if live else ui.RULE
    ring = f"outline:2px solid {ui.INK}; outline-offset:2px;" if sel else ""
    fb, ff = (ui.BLUE, ui.LIGHT) if live else ("transparent", ui.MUTED)
    return (f"<div class='tn-card' style='position:relative; height:{h}px; box-sizing:border-box; border:1px {'dashed' if dashed else 'solid'} {edge}; {ring}"
            f"background:{'transparent' if dashed else ui.PANEL}; font-family:{ui.FONT}'>{''.join(rows)}"
            f"<div style='display:flex; justify-content:space-between; align-items:center; height:{h - 68}px; padding:0 10px; background:{fb}; "
            f"font-size:11px; color:{ff}; font-weight:{600 if live else 400}'><span>{foot_l}</span><span>Bo{m['bo']}</span></div>{extra}</div>")


def card(tour, m, extra=""):
    sel = ss.get(f"tn_sel_{tour.t['_id']}") == m["id"]
    with st.container(key=f"tncard_{m['id']}", gap=None):
        ui.html(card_html(tour, m, sel, extra=extra))
        if st.button("Open", key=f"tnb_{m['id']}", width="stretch"):
            ss[f"tn_sel_{tour.t['_id']}"] = m["id"]; st.rerun()


def bracket_section(tour, ms, title, note=""):
    """Rounds side by side, each card lined up between the two matches that feed it."""
    if not ms:
        return
    ids = {m["id"] for m in ms}
    rounds = sorted({m["round"] for m in ms})
    by = {r: [m for m in ms if m["round"] == r] for r in rounds}
    U = CARD_H + GAP
    y = {}
    for ri, r in enumerate(rounds):
        for i, m in enumerate(by[r]):
            f = [s["win"] for s in (m["a"], m["b"]) if s.get("win") in ids and s["win"] in y]
            if ri == 0 or not f:
                y[m["id"]] = U * (i + 0.5)
            else:
                y[m["id"]] = sum(y[x] for x in f) / len(f)
    ui.html(ui.label(title, margin_top=26, rule=True) if not note else
            f"<div style='display:flex; justify-content:space-between; align-items:baseline; margin-top:26px; padding-bottom:8px; border-bottom:1px solid {ui.STEEL}'>"
            f"<span style='font-size:12px; font-weight:600; letter-spacing:1.6px; text-transform:uppercase; color:{ui.MUTED}'>{escape(title)}</span>"
            f"<span style='font-size:12px; color:{ui.MUTED}'>{escape(note)}</span></div>")
    with st.container(key=f"tnbr_{title.replace(' ', '_')}"):
        cols = st.columns(len(rounds))
        for ri, r in enumerate(rounds):
            with cols[ri]:
                lab = by[r][0]["label"]
                ui.html(f"<div class='tn-roundlab' style='font-size:11px; line-height:16px; color:{ui.MUTED}; height:32px; box-sizing:border-box; "
                        f"padding:10px 0 6px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis'>{escape(lab)}</div>")
                bottom = 0
                for m in by[r]:
                    top = y[m["id"]] - CARD_H / 2
                    ui.html(f"<div class='tn-sp' style='height:{max(top - bottom, 0):.0f}px'></div>")
                    conn = ""
                    if ri < len(rounds) - 1 and any(s.get("win") == m["id"] for n in ms for s in (n["a"], n["b"])):
                        conn += f"<span class='tn-conn' style='right:-16px; top:{CARD_H / 2 - 0.75}px; width:16px; height:1.5px'></span>"
                    f = [s["win"] for s in (m["a"], m["b"]) if s.get("win") in ids]
                    if ri > 0 and f:
                        conn += f"<span class='tn-conn' style='left:-16px; top:{CARD_H / 2 - 0.75}px; width:16px; height:1.5px'></span>"
                        if len(f) == 2:
                            span = abs(y[f[0]] - y[f[1]])
                            conn += f"<span class='tn-conn' style='left:-16px; top:{CARD_H / 2 - span / 2}px; width:1.5px; height:{span}px'></span>"
                    card(tour, m, extra=conn)
                    bottom = top + CARD_H


def finals_column(tour, ms):
    for m in ms:
        r = tour.R[m["id"]]
        ui.html(f"<div style='font-size:11px; color:{ui.MUTED}; margin:14px 0 4px'>{escape(m['label'])}{' · If Needed' if m.get('if_needed') else ''}</div>")
        card(tour, m)


def champ_box(tour):
    ch = T.champion(tour.t, tour.R, tour.maps, tour.kd)
    if ch:
        ui.html(f"<div style='margin-top:22px; padding:16px; background:{ui.INK}; color:{ui.PANEL}'>"
                f"<div style='font-size:11px; font-weight:600; letter-spacing:1.4px; text-transform:uppercase; color:{ui.RULE}'>Champions</div>"
                f"<div style='font-size:26px; font-weight:300; margin-top:4px'>{escape(tour.name(ch))}</div></div>")
    else:
        ui.html(f"<div style='margin-top:22px; padding:14px 16px; border:1px solid {ui.RULE}'>"
                f"<div style='font-size:11px; font-weight:600; letter-spacing:1.4px; text-transform:uppercase; color:{ui.MUTED}'>Champion</div>"
                f"<div style='font-size:22px; font-weight:300; margin-top:6px; color:{ui.MUTED}'>To be decided</div></div>")


def elim_view(tour, prefix, heading=None):
    ms = [m for m in tour.t["matches"] if m["stage"].startswith(prefix) and m["stage"][len(prefix):] in ("W", "L", "GF", "GR", "3P")]
    wb = [m for m in ms if m["stage"] == prefix + "W"]
    lb = [m for m in ms if m["stage"] == prefix + "L"]
    fin = [m for m in ms if m["stage"] in (prefix + "GF", prefix + "GR")]
    third = [m for m in ms if m["stage"] == prefix + "3P"]
    if heading:
        ui.html(ui.h2(heading, margin_top=36))
    if fin:  # double elimination: brackets on the left, finals on the right
        a, b = st.columns([2.2, 1], gap="large")
        with a:
            bracket_section(tour, wb, "Winners bracket", f"Bo{wb[0]['bo']}")
            if lb:
                bracket_section(tour, lb, "Losers bracket", f"Bo{lb[0]['bo']}")
        with b:
            ui.html(ui.label("Grand final", margin_top=26, rule=True))
            finals_column(tour, fin)
            champ_box(tour)
    else:
        a, b = st.columns([2.5, 1], gap="large")
        with a:
            bracket_section(tour, wb, "Bracket", f"Bo{wb[0]['bo']} · final Bo{wb[-1]['bo']}")
        with b:
            if third:
                ui.html(ui.label("Third place", margin_top=26, rule=True))
                finals_column(tour, third)
            champ_box(tour)


def standings_table(tour):
    rows = T.standings(tour.t, tour.R, tour.maps, tour.kd)
    done = T.pool_complete(tour.t, tour.R)
    fmt = tour.t["format"]
    k = int(tour.t["opts"].get("k", 0)) if fmt == "rrp" else (2 if tour.t["opts"].get("after") == "top2" else 4 if tour.t["opts"].get("after") == "top4" else 0)
    body = []
    for x in rows:
        tag = ""
        if k:
            tag = ui.tagbox("Playoffs", ui.BLUE, ui.BLUE) if x["rank"] <= k else (ui.tagbox("Out") if done else "")
        body.append([{"v": str(x["rank"]), "fg": ui.MUTED}, {"v": f"{ui.swatch(tour.color[x['team']], 10, 10)} {escape(tour.name(x['team']))}{tag}", "w": 600},
                     f"{x['w']}-{x['l']}", f"{x['mw']}-{x['ml']}"])
    ui.html(ui.h2("Standings", margin_top=32, right=f"<span style='font-size:12px; color:{ui.MUTED}'>{'Final' if done else 'So far'}</span>")
            + ui.table([("#", "left"), ("Team", "left"), ("Series W-L", "right"), ("Maps W-L", "right")], body, min_width=320)
            + ui.note("Same record? " + ("Head to head decides it, then map difference." if tour.t["opts"].get("tiebreak", "h2h") == "h2h" else "K/D decides it, then map difference."), 8, 12))


def pool_view(tour):
    pm = [m for m in tour.t["matches"] if is_pool(m)]
    standings_table(tour)
    rounds = sorted({m["round"] for m in pm})
    ui.html(ui.h2("Schedule" if tour.t["format"] != "sw" else "Rounds", margin_top=36))
    for r in rounds:
        games = [m for m in pm if m["round"] == r and not m["b"].get("bye")]
        byes = [m for m in pm if m["round"] == r and m["b"].get("bye")]
        ui.html(f"<div style='font-size:12px; color:{ui.MUTED}; margin:16px 0 6px'>Round {r}"
                + (f" · {escape(tour.name(byes[0]['a']['team']))} has a bye" if byes else "") + "</div>")
        for i in range(0, len(games), 3):
            cols = st.columns(3)
            for c, m in zip(cols, games[i:i + 3]):
                with c:
                    card(tour, m)
    if tour.t["format"] == "sw" and max(rounds) < int(tour.t["opts"].get("rounds", 3)):
        ui.html(ui.note(f"Round {max(rounds) + 1} is drawn as soon as round {max(rounds)} is finished: teams on the same record play each other, no rematches.", 10, 12))


# ---------------------------------------------------------------- practice-only: simulate results
SIM_STATS = {"HP": ["hill_time", "objective_kills"], "SND": ["first_bloods", "first_deaths", "bombs_planted"],
             "OVL": ["overloads", "carrier_kills", "kills_as_carrier"]}


def sim_map(doc, mid, rng):
    """One made-up map for a bracket match (practice mode only): plausible scores and stat lines."""
    fresh = data.load_tdocs()
    maps = [x for x in fresh["t_matches"] if x["tournament_id"] == doc["_id"]]
    R = T.resolve(doc, maps)
    r = R[mid]
    if r["status"] not in ("ready", "live"):
        return False
    teams = {x["id"]: x for x in doc["teams"]}
    A, B = teams[r["a"]], teams[r["b"]]
    tcfg = ts[doc["title"]]
    modes = [k for k, mm in tcfg["modes"].items() if mm.get("active", True)] or ["HP"]
    n = r["wa"] + r["wb"]
    mode = modes[n % len(modes)]
    pool = [x["name"] for x in tcfg["modes"].get(mode, {}).get("maps", []) if x.get("status") != "retired"] or ["Practice Map"]
    played = {x["map"] for x in r["maps"]}
    mp = rng.choice([x for x in pool if x not in played] or pool)
    ra = A.get("rating") or 1500; rb = B.get("rating") or 1500
    win_a = rng.random() < 1 / (1 + 10 ** ((rb - ra) / 400))
    ws = tcfg["modes"].get(mode, {}).get("win_score") or {"HP": 250, "SND": 6, "OVL": 8}.get(mode, 100)
    lose = rng.randint(int(ws * 0.4), ws - 1)
    sa, sb = (ws, lose) if win_a else (lose, ws)
    lo, hi = {"HP": (14, 32), "SND": (3, 11)}.get(mode, (10, 26))
    rows = []
    kills = {"A": [], "B": []}
    for side, team in (("A", A), ("B", B)):
        won = (side == "A") == win_a
        for p in team["players"]:
            kills[side].append(rng.randint(lo, hi) + (3 if won else 0))
    for side, team, other in (("A", A, "B"), ("B", B, "A")):
        total_d = sum(kills[other]) + rng.randint(0, 2)
        k_ = len(team["players"])
        cuts = sorted(rng.sample(range(1, total_d), k_ - 1)) if k_ > 1 and total_d > k_ else []
        deaths = [b - a for a, b in zip([0] + cuts, cuts + [total_d])] if cuts else [total_d] + [0] * (k_ - 1)
        for i, p in enumerate(team["players"]):
            k = kills[side][i]
            row = {f: None for f in STAT_KEYS}
            row.update(kills=k, deaths=max(deaths[i], 1), assists=rng.randint(1, 8), damage=k * rng.randint(100, 130) + rng.randint(0, 400),
                       non_traded_kills=int(k * rng.uniform(0.55, 0.8)), highest_streak=rng.randint(2, 9))
            for f in SIM_STATS.get(mode, []):
                row[f] = {"hill_time": rng.randint(30, 160), "objective_kills": rng.randint(2, 12), "first_bloods": rng.randint(0, 3),
                          "first_deaths": rng.randint(0, 3), "bombs_planted": rng.randint(0, 2), "overloads": rng.randint(0, 2),
                          "carrier_kills": rng.randint(0, 4), "kills_as_carrier": rng.randint(0, 3)}[f]
            rows.append({"player": p, "team": side, **row})
    data.save_tmap(doc, mid, r["a"], r["b"], mode, mp, sa, sb, rng.randint(300, 720), "full", rows)
    return True


def sim_series(doc, mid, rng):
    for _ in range(12):
        fresh = data.load_tdocs()
        R = T.resolve(doc, [x for x in fresh["t_matches"] if x["tournament_id"] == doc["_id"]])
        if R[mid]["status"] not in ("ready", "live"):
            break
        sim_map(doc, mid, rng)
    after_save(doc)


def after_save(doc):
    fresh = data.load_tdocs()
    if T.advance(doc, [x for x in fresh["t_matches"] if x["tournament_id"] == doc["_id"]]):
        data.save_tournament(doc)


def sim_rest(doc, rng):
    for _ in range(300):
        fresh = data.load_tdocs()
        R = T.resolve(doc, [x for x in fresh["t_matches"] if x["tournament_id"] == doc["_id"]])
        up = T.next_up(doc, R)
        if not up:
            break
        sim_series(doc, up[0], rng)


def practice_tools(tour, mid=None):
    """Simulate buttons, shown only in practice mode."""
    if not PRACTICE:
        return
    rng = random.Random()
    with st.container(horizontal=True, gap="small", key=f"tn_sim_{mid or 'all'}"):
        if mid:
            if st.button("Simulate a Map", key="tn_sim_map"):
                sim_map(tour.t, mid, rng); after_save(tour.t); st.rerun()
            if st.button("Simulate This Series", key="tn_sim_series"):
                sim_series(tour.t, mid, rng); ss[f"tn_sel_{tour.t['_id']}"] = None; st.rerun()
        elif T.next_up(tour.t, tour.R):
            if st.button("Simulate the Rest of the Tournament", key="tn_sim_rest"):
                with st.spinner("Simulating..."):
                    sim_rest(tour.t, rng)
                st.rerun()


# ---------------------------------------------------------------- selected match panel
def match_panel(tour):
    t = tour.t; tid = t["_id"]
    key = f"tn_sel_{tid}"
    if ss.get(key) not in tour.R or tour.R[ss.get(key)]["status"] in ("bye", "skipped"):
        up = T.next_up(t, tour.R)
        done = [m["id"] for m in t["matches"] if tour.R[m["id"]]["status"] == "done"]
        ss[key] = up[0] if up else (done[-1] if done else t["matches"][0]["id"])
    m = tour.ms[ss[key]]; r = tour.R[m["id"]]
    st_ = r["status"]
    A, B = tour.side_name(m, "a"), tour.side_name(m, "b")
    state = {"live": ("LIVE", ui.BLUE), "done": ("FINAL", ui.MUTED), "ready": ("READY", ui.INK), "waiting": ("WAITING", ui.MUTED),
             "bye": ("BYE", ui.MUTED), "skipped": ("NOT NEEDED", ui.MUTED)}[st_]
    has_score = st_ in ("live", "done") and not r["manual"]
    score = (f"<span style='font-weight:300; font-size:36px; line-height:1; white-space:nowrap'>{r['wa']} – {r['wb']}</span>" if has_score
             else f"<span style='font-size:15px; color:{ui.MUTED}'>vs</span>")
    need = m["bo"] // 2 + 1
    box = st.container(border=True, key="tn_panel")
    with box:
        ui.html(f"<div style='display:flex; flex-wrap:wrap; justify-content:space-between; align-items:baseline; gap:6px 16px'>"
                f"<span style='font-size:12px; font-weight:600; letter-spacing:1.6px; text-transform:uppercase; color:{ui.MUTED}'>{escape(m['label'])} · Bo{m['bo']}</span>"
                f"<span style='font-size:12px; font-weight:600; letter-spacing:0.6px; color:{state[1]}'>{state[0]}</span></div>"
                "<div style='display:grid; grid-template-columns:minmax(0,1fr) auto minmax(0,1fr); align-items:center; gap:8px 20px; margin:14px 0 14px'>"
                f"<span style='text-align:right; font-size:17px; color:{tour.color.get(r['a'], ui.INK)}; font-weight:{600 if st_ == 'done' and r['winner'] == r['a'] else 500}'>{escape(A)}</span>"
                f"{score}"
                f"<span style='font-size:17px; color:{tour.color.get(r['b'], ui.INK)}; font-weight:{600 if st_ == 'done' and r['winner'] == r['b'] else 500}'>{escape(B)}</span></div>")
        lock0 = T.locked(t, tour.R, m["id"])
        for xi, x in enumerate(r["maps"]):
            won = A if x["winner"] == "A" else B
            c1, c2, c3 = st.columns([5, 1, 1], vertical_alignment="center")
            with c1:
                ui.html(f"<div style='display:grid; grid-template-columns:64px minmax(0,1fr) auto; align-items:center; gap:14px; padding:8px 0; border-top:1px solid {ui.RULE}'>"
                        f"<div>{ui.img_tag(x['map'])}</div><div><div style='font-size:14px; font-weight:500'>Map {x['map_no']} · {SHORT.get(x['mode'], x['mode'])} on {escape(x['map'])}</div>"
                        f"<div style='font-size:12px; color:{ui.MUTED}'>Won by {escape(won)}</div></div>"
                        f"<span style='font-size:15px; font-weight:500'>{x['score_a']}–{x['score_b']}</span></div>")
            with c2:
                if CAN_EDIT and st.button("Edit", key=f"tn_edm_{x['_id']}", width="stretch"):
                    prows = [p for p in tpms(tid) if p["map_id"] == x["_id"]]
                    ss.tn_entry = {"tid": tid, "mid": m["id"], "draft": me.new_draft(ts[t["title"]], x, prows)}
                    ss.tn_view = "entry"; st.rerun()
            with c3:
                if CAN_EDIT and xi == len(r["maps"]) - 1 and not lock0 and st.button("Delete", key=f"tn_delm_{x['_id']}", width="stretch"):
                    ss.tn_confirm_delm = x["_id"]
            if ss.get("tn_confirm_delm") == x["_id"]:
                st.warning(f"Delete map {x['map_no']} ({x['map']})? Its player stats go too.")
                d1, d2 = st.columns(2)
                if d1.button("Yes, Delete", type="primary", key="tn_delm_yes"):
                    data.delete_tmap(x["_id"]); ss.pop("tn_confirm_delm", None)
                    if T.redraw_after(t, tour.R, m["id"]):
                        data.save_tournament(t)
                    st.rerun()
                if d2.button("Keep It", key="tn_delm_no"):
                    ss.pop("tn_confirm_delm", None); st.rerun()
        if r["manual"]:
            ui.html(ui.note(f"Winner recorded without stats: {escape(tour.name(r['winner']))}.", 8, 13))
        if not r["manual"] and (max(r["wa"], r["wb"]) > need or min(r["wa"], r["wb"]) >= need):
            ui.html(f"<div style='margin-top:10px; padding:10px 12px; border-left:3px solid {ui.RUST}; background:{ui.LIGHT}; font-size:13px'>"
                    f"<b style='font-weight:600'>Check the results:</b> {r['wa']}–{r['wb']} is more maps than a Bo{m['bo']} needs (first to {need}). "
                    "This can happen after editing a map. Edit or delete the extra map so the score is right.</div>")
        lock = T.locked(t, tour.R, m["id"])
        nxt = [d for d in T.dependents(t, m["id"]) if tour.R[d]["status"] != "skipped" and any(s.get("win") == m["id"] for s in (tour.ms[d]["a"], tour.ms[d]["b"]))]
        if st_ == "live":
            lead = "first to " + str(need) + " maps"
            ui.html(ui.note(f"Bo{m['bo']}: {lead}." + (f" The winner goes to the {tour.ms[nxt[0]]['label']}." if nxt else ""), 10, 13)
                    + "<div style='height:8px'></div>")
        elif st_ == "done":
            wa, wb = (r["wa"], r["wb"]) if r["winner"] == r["a"] else (r["wb"], r["wa"])
            line = f"{escape(tour.name(r['winner']))} won" + ("" if r["manual"] else f" {wa}–{wb}") + "."
            if nxt:
                line += f" They go on to the {escape(tour.ms[nxt[0]]['label'])}."
            ui.html(ui.note(line, 10, 13))
        elif st_ == "waiting":
            ui.html(ui.note("Waiting on " + " and ".join(escape(tour.src_text(s)[:1].lower() + tour.src_text(s)[1:]) for s, sd in ((m["a"], "a"), (m["b"], "b")) if r[sd] is None) + ".", 10, 13))
        elif st_ == "ready":
            ui.html(ui.note(f"Ready to play. Bo{m['bo']}: first to {need} maps.", 10, 13) + "<div style='height:8px'></div>")
        if st_ in ("ready", "live"):
            if not CAN_EDIT:
                unlock_box()
            else:
                with st.container(horizontal=True, gap="small"):
                    n = r["wa"] + r["wb"] + 1
                    if st.button(f"Enter Map {n}", type="primary", key="tn_enter"):
                        ss.tn_entry = {"tid": tid, "mid": m["id"], "draft": me.new_draft(ts[t["title"]])}
                        ss.tn_view = "entry"; st.rerun()
                    with st.popover("Record the Winner Only, No Stats"):
                        ui.html(ui.note("For a series you don't want to enter stats for. Any maps already entered for it are kept.", 0, 13))
                        for side, nm in (("a", A), ("b", B)):
                            if st.button(f"{nm} won", key=f"tn_man_{side}", width="stretch"):
                                t.setdefault("manual", {})[m["id"]] = side
                                data.save_tournament(t)
                                ss[key] = None  # show the next match to play
                                st.rerun()
                practice_tools(tour, m["id"])
        if st_ in ("done", "live") and CAN_EDIT:
            if lock:
                ui.html(ui.note("Locked: a match that depends on this result has already started. Undo that one first.", 10, 12))
            elif st.button("Undo Result" if st_ == "done" else "Clear This Series", key="tn_undo"):
                ss.tn_confirm_undo = m["id"]
            if ss.get("tn_confirm_undo") == m["id"]:
                st.warning(f"Clear {m['label']}? Its maps and player stats are deleted and the bracket goes back to before it was played.")
                a, b = st.columns(2)
                if a.button("Yes, Clear It", type="primary", key="tn_undo_yes"):
                    # a Swiss round drawn from this result goes too
                    later = [d for d in T.dependents(t, m["id"]) if tour.ms[d]["stage"] == "SW"]
                    if later:
                        t["matches"] = [x for x in t["matches"] if x["id"] not in later]
                    t.get("manual", {}).pop(m["id"], None)
                    data.save_tournament(t)
                    data.clear_tmatch(tid, m["id"])
                    ss.pop("tn_confirm_undo", None); st.rerun()
                if b.button("Keep It", key="tn_undo_no"):
                    ss.pop("tn_confirm_undo", None); st.rerun()


# ===================================================================== tabs
def summary(tour):
    t = tour.t; R = tour.R
    ch = T.champion(t, R, tour.maps, tour.kd)
    fname = T.FORMATS[t["format"]][0]
    sub = f"{fmt_date(t.get('date'))} · {t['size']}v{t['size']} · {fname} · {len(t['teams'])} teams"
    if ch:
        tag = ui.tagbox("Finished", ui.MUTED, ui.RULE)
        right = (f"<div class='tn-right' style='text-align:right'><div style='font-size:11px; font-weight:600; letter-spacing:1.4px; text-transform:uppercase; color:{ui.BLUE}'>Champions</div>"
                 f"<div style='font-size:24px; font-weight:300; margin-top:2px'>{escape(tour.name(ch))}</div></div>")
    else:
        tag = f"<span style='margin-left:10px; font-size:10px; font-weight:600; letter-spacing:0.8px; padding:2px 7px; color:{ui.LIGHT}; background:{ui.BLUE}'>IN PROGRESS</span>"
        up = T.next_up(t, R)
        txt = "—"
        if up:
            m = tour.ms[up[0]]; r = R[up[0]]
            txt = f"{m['label']} · {tour.side_name(m, 'a')} vs {tour.side_name(m, 'b')}" + (f" · {r['wa']}–{r['wb']}" if r["status"] == "live" else "")
        right = (f"<div class='tn-right' style='text-align:right'><div style='font-size:11px; font-weight:600; letter-spacing:1.4px; text-transform:uppercase; color:{ui.MUTED}'>"
                 f"{'Up now' if up and R[up[0]]['status'] == 'live' else 'Up next'}</div><div style='font-size:16px; font-weight:500; margin-top:4px'>{escape(txt)}</div></div>")
    ui.html(f"<div style='display:flex; flex-wrap:wrap; justify-content:space-between; align-items:flex-end; gap:12px 24px; margin-top:28px; padding-bottom:16px; border-bottom:2px solid {ui.INK}'>"
            f"<div><div style='display:flex; align-items:center; flex-wrap:wrap; gap:8px'><span style='font-size:26px'>{escape(t['name'])}</span>{tag}</div>"
            f"<div style='font-size:14px; color:{ui.MUTED}; margin-top:6px'>{escape(sub)}</div></div>{right}</div>")


def bracket_tab(tour):
    t = tour.t; fmt = t["format"]
    flash = ss.pop("tn_flash", None)
    if flash and flash.get("tid") == t["_id"]:
        m = tour.ms.get(flash["mid"]); r = tour.R.get(flash["mid"])
        if m and r:
            msg = f"Map saved. {m['label']}: {tour.side_name(m, 'a')} {r['wa']}–{r['wb']} {tour.side_name(m, 'b')}."
            if r["status"] == "done":
                up = T.next_up(t, tour.R)
                if up:  # the series is decided: show the next one to play
                    ss[f"tn_sel_{t['_id']}"] = up[0]
                nxt = [d for d in T.dependents(t, m["id"]) if tour.R[d]["status"] != "skipped" and any(s.get("win") == m["id"] for s in (tour.ms[d]["a"], tour.ms[d]["b"]))]
                msg = f"Map saved. {tour.name(r['winner'])} win the {m['label']}" + (f" and move on to the {tour.ms[nxt[0]]['label']}." if nxt else ".")
            ui.html(f"<div style='margin-top:18px; padding:12px 16px; background:{ui.BLUE}; color:{ui.LIGHT}; font-size:14px'>{escape(msg)}</div>")
    blurb = {"se": "Single elimination: lose once and you're out.",
             "de": "Double elimination: lose twice and you're out. A team that drops from the winners bracket gets a second life in the losers bracket.",
             "rr": "Round robin: every team plays every other team. Best record wins.",
             "rrp": f"Round robin, then playoffs: the top {min(int(t['opts'].get('k', 3)), len(t['teams']))} go through. Top seeds get byes when the numbers are uneven.",
             "sw": "Swiss: each round pairs teams with the same record."}[fmt]
    ui.html(ui.note(blurb + " Tap a match for its maps and results.", 18, 14, 760))
    if fmt in ("se", "de"):
        elim_view(tour, "")
    elif fmt == "rr":
        pool_view(tour)
        champ_box(tour)
    elif fmt == "rrp":
        pool_view(tour)
        elim_view(tour, "P", "Playoffs")
    else:
        pool_view(tour)
        if t["opts"].get("after") == "top2":
            ui.html(ui.h2("Final", margin_top=36))
            a, b = st.columns([1, 1])
            with a:
                card(tour, tour.ms["SF"])
            with b:
                champ_box(tour)
        elif t["opts"].get("after") == "top4":
            elim_view(tour, "P", "Playoffs")
        else:
            champ_box(tour)
    ui.html("<div style='height:56px'></div>")
    # any match whose two teams are known can be played, in any order
    up = T.next_up(t, tour.R)
    if up:
        ui.html(ui.label("Ready to Play", margin_top=0)
                + ui.note("Any of these can go next, in whatever order suits who's around. Tap one to open it below.", 4, 12))
        selk = f"tn_sel_{t['_id']}"
        with st.container(horizontal=True, gap="small", key="tn_ready"):
            for mid in up:
                m = tour.ms[mid]; r = tour.R[mid]
                lab = f"{m['label']} · {tour.name(r['a'])} vs {tour.name(r['b'])}" + (f" · live {r['wa']}–{r['wb']}" if r["status"] == "live" else "")
                st.button(lab, key=f"tn_go_{mid}", type="primary" if ss.get(selk) == mid else "secondary",
                          on_click=lambda mid=mid: ss.__setitem__(selk, mid))
        practice_tools(tour)
        ui.html("<div style='height:14px'></div>")
    match_panel(tour)


def scoreboard(tour, x):
    rows = [p for p in tpms(tour.t["_id"]) if p["map_id"] == x["_id"]]
    mode = x["mode"]
    obj = {"HP": ("hill_time", "Hill"), "SND": ("bombs_planted", "Plants"), "OVL": ("overloads", "Overloads")}.get(mode, (None, ""))
    kds = [(p.get("kills") or 0) / max(p.get("deaths") or 0, 1) for p in rows]
    objs = [p.get(obj[0]) for p in rows if obj[0] and p.get(obj[0]) is not None]
    body = []
    for side in ("A", "B"):
        if side == "B":
            body.append("SPACER")
        for p in [p for p in rows if p["team"] == side]:
            kd = (p.get("kills") or 0) / max(p.get("deaths") or 0, 1)
            bg, fg = ui.tint(kd, kds)
            ov = p.get(obj[0]) if obj[0] else None
            obg, ofg = ui.tint(ov, objs) if ov is not None else ("transparent", ui.INK)
            won = p["result"] == "W"
            body.append([{"v": escape(p["player"]), "w": 600 if won else 400, "fg": ui.INK if won else ui.MUTED}, str(p.get("kills")), str(p.get("deaths")),
                         {"v": f"{kd:.2f}", "bg": bg, "fg": fg, "w": 500}, "—" if p.get("assists") is None else str(p["assists"]), ui.n0(p.get("damage")),
                         {"v": "—" if ov is None else (ui.mmss(ov) if mode == "HP" else str(ov)), "bg": obg, "fg": ofg, "w": 500}])
    cols = [("Player", "left"), ("K", "right"), ("D", "right"), ("K/D", "right"), ("A", "right"), ("Dmg", "right"), (obj[1] or "Obj", "right")]
    ui.html(ui.table(cols, body, min_width=520, cell_pad="9px 6px")
            + "<div style='display:flex; flex-wrap:wrap; gap:6px 18px; margin-top:10px; font-size:12px; color:" + ui.MUTED + "'>"
            "<span>Shaded: lowest → highest in this lobby</span><span>Bold: won the map</span></div>")


def series_board(tour, m, r):
    """Every map of the series added up, per player."""
    ids = {x["_id"] for x in r["maps"]}
    rows = [p for p in tpms(tour.t["_id"]) if p["map_id"] in ids]
    modes = {x["mode"] for x in r["maps"]}
    extra = [(f, lab) for f, lab, mo in (("hill_time", "Hill", "HP"), ("bombs_planted", "Plants", "SND"), ("overloads", "Overloads", "OVL")) if mo in modes]
    agg = {}
    for p in rows:
        a = agg.setdefault(p["player"], {"team": p["team"], "maps": 0, "kills": 0, "deaths": 0, "assists": None, "damage": None, **{f: None for f, _ in extra}})
        a["maps"] += 1; a["kills"] += p.get("kills") or 0; a["deaths"] += p.get("deaths") or 0
        for f in ["assists", "damage"] + [f for f, _ in extra]:
            if p.get(f) is not None:
                a[f] = (a[f] or 0) + p[f]
    kds = [a["kills"] / max(a["deaths"], 1) for a in agg.values()]
    ws = sum(1 for x in r["maps"] if x["winner"] == "A"), sum(1 for x in r["maps"] if x["winner"] == "B")
    body = []
    for side in ("A", "B"):
        if side == "B":
            body.append("SPACER")
        tid = r["a"] if side == "A" else r["b"]
        for name, a in sorted(((n, a) for n, a in agg.items() if a["team"] == side), key=lambda z: -z[1]["kills"]):
            kd = a["kills"] / max(a["deaths"], 1)
            bg, fg = ui.tint(kd, kds)
            won = tid == r["winner"]
            body.append([{"v": escape(name), "w": 600 if won else 400, "fg": tour.color.get(tid, ui.INK)}, str(a["maps"]), str(a["kills"]), str(a["deaths"]),
                         {"v": f"{kd:.2f}", "bg": bg, "fg": fg, "w": 500}, "—" if a["assists"] is None else str(a["assists"]), ui.n0(a["damage"])]
                        + ["—" if a[f] is None else (ui.mmss(a[f]) if f == "hill_time" else str(a[f])) for f, _ in extra])
    cols = [("Player", "left"), ("Maps", "right"), ("K", "right"), ("D", "right"), ("K/D", "right"), ("A", "right"), ("Dmg", "right")] + [(lab, "right") for _, lab in extra]
    ui.html(f"<div style='font-size:14px; margin-top:6px'>Series totals · {len(r['maps'])} map{'s' if len(r['maps']) != 1 else ''} · "
            f"{escape(tour.name(r['a']))} {ws[0]}–{ws[1]} {escape(tour.name(r['b']))}</div>"
            + ui.table(cols, body, min_width=560, cell_pad="9px 6px")
            + f"<div style='display:flex; flex-wrap:wrap; gap:6px 18px; margin-top:10px; font-size:12px; color:{ui.MUTED}'>"
            "<span>Every map added up</span><span>Shaded: lowest → highest K/D</span><span>Bold: won the series</span></div>")


def matches_tab(tour):
    t = tour.t; R = tour.R
    ui.html(ui.note("Every series in this tournament. These stay here: they don't show up in the Series Log or count toward regular stats.", 18, 14, 760))
    todo = [m for m in t["matches"] if R[m["id"]]["status"] in ("live", "ready", "waiting")]
    if todo:
        ui.html(ui.label("Still to play", margin_top=22, rule=True))
        rows = ""
        for m in todo:
            r = R[m["id"]]
            note = {"live": f"Live · {r['wa']}–{r['wb']}", "ready": "Ready to Start", "waiting": "Waiting"}[r["status"]]
            if m.get("if_needed"):
                note = "If Needed"
            a_ = tour.name(r["a"]) if r["a"] else "TBD"
            b_ = tour.name(r["b"]) if r["b"] else "TBD"
            rows += (f"<div class='cb-uprow' style='display:grid; grid-template-columns:200px minmax(0, 1fr) 120px; gap:4px 16px; align-items:center; "
                     f"padding:11px 0; border-bottom:1px solid {ui.RULE}'><span style='font-size:14px; font-weight:600'>{escape(m['label'])} · Bo{m['bo']}</span>"
                     f"<span style='font-size:14px'>{escape(a_)} vs {escape(b_)}</span>"
                     f"<span style='font-size:12px; text-align:right; color:{ui.BLUE if r['status'] == 'live' else ui.MUTED}'>{note}</span></div>")
        ui.html(f"<style>@media (max-width:640px) {{ .cb-uprow {{ grid-template-columns: minmax(0,1fr) !important; }} .cb-uprow span {{ text-align: left !important; }} }}</style>{rows}")
    played = [m for m in t["matches"] if R[m["id"]]["status"] == "done"]
    ui.html(ui.label("Played", margin_top=30) + f"<div style='border-top:2px solid {ui.INK}; margin-top:10px'></div>")
    if not played:
        ui.html(ui.note("Nothing finished yet.", 12, 14))
    key = f"tn_open_{t['_id']}"
    for m in reversed(played):
        r = R[m["id"]]
        open_ = ss.get(key) == m["id"]
        aw = r["winner"] == r["a"]
        sc = "W – L" if r["manual"] and aw else "L – W" if r["manual"] else f"{r['wa']} – {r['wb']}"
        c1, c2 = st.columns([5, 1], vertical_alignment="center")
        with c1:
            ui.html(f"<div style='padding:14px 0 6px'><div style='font-size:13px; color:{ui.MUTED}'><b style='font-weight:600; color:{ui.INK}'>{escape(m['label'])}</b>"
                    f" · {fmt_date(t.get('date'))} · Bo{m['bo']}</div>"
                    "<div style='display:grid; grid-template-columns:minmax(0,1fr) auto minmax(0,1fr); align-items:center; gap:8px 18px; margin-top:10px'>"
                    f"<span style='text-align:right; font-size:16px; font-weight:{600 if aw else 400}; color:{tour.color.get(r['a'], ui.INK)}'>{escape(tour.name(r['a']))}</span>"
                    f"<span style='font-weight:300; font-size:28px; line-height:1; color:{ui.INK}'>{sc}</span>"
                    f"<span style='font-size:16px; font-weight:{400 if aw else 600}; color:{tour.color.get(r['b'], ui.INK)}'>{escape(tour.name(r['b']))}</span></div></div>")
        with c2:
            if r["maps"] and st.button("Hide Recap" if open_ else "Recap", key=f"tn_rc_{m['id']}", type="primary" if open_ else "secondary", width="stretch"):
                ss[key] = None if open_ else m["id"]; st.rerun()
        if open_ and r["maps"]:
            ui.html("<div style='height:16px'></div>")
            labels = {"__all": "Series Totals", **{x["_id"]: f"Map {x['map_no']} · {x['map']}" for x in r["maps"]}}
            pick = st.segmented_control("Map", list(labels), format_func=labels.get, default="__all", key=f"tn_rcm_{m['id']}",
                                        label_visibility="collapsed") or "__all"
            ui.html("<div style='height:6px'></div>")
            if pick == "__all":
                series_board(tour, m, r)
                ui.html(f"<div style='border-bottom:1px solid {ui.RULE}; margin-top:8px'></div>")
                continue
            x = next(x for x in r["maps"] if x["_id"] == pick)
            won = tour.name(r["a"]) if x["winner"] == "A" else tour.name(r["b"])
            ui.html(f"<div style='font-size:14px; margin-top:6px'>Map {x['map_no']} · {MODEN.get(x['mode'], x['mode'])} on {escape(x['map'])} · "
                    f"{x['score_a']}–{x['score_b']}{' · ' + ui.mmss(x['length_sec']) if x.get('length_sec') else ''} · won by {escape(won)}</div>")
            scoreboard(tour, x)
        ui.html(f"<div style='border-bottom:1px solid {ui.RULE}; margin-top:8px'></div>")


def tour_engine():
    """Tournament games as an Engine (pseudo series), for Provisional MAR once there are enough maps."""
    from cbl.engine import Engine
    series, matches, pms = [], [], []
    no = 0
    for tdoc in sorted(TD["tournaments"], key=lambda x: x.get("date") or ""):
        teams = {x["id"]: x for x in tdoc["teams"]}
        for mm in tdoc["matches"]:
            ms = [x for x in TD["t_matches"] if x["tournament_id"] == tdoc["_id"] and x["bmatch"] == mm["id"]]
            if not ms:
                continue
            no += 1; sid = f"{tdoc['_id']}:{mm['id']}"
            series.append({"_id": sid, "title": tdoc["title"], "series_no": no, "date": tdoc.get("date"), "format": f"{tdoc['size']}v{tdoc['size']}",
                           "best_of": mm["bo"], "team_a": teams.get(ms[0]["team_a"], {}).get("players", []),
                           "team_b": teams.get(ms[0]["team_b"], {}).get("players", []), "status": "closed", "result_override": None})
            for x in ms:
                matches.append({**{k: v for k, v in x.items() if k not in ("tournament_id", "bmatch", "team_a", "team_b", "date")}, "series_id": sid})
            for p in TD["t_player_matches"]:
                if p["tournament_id"] == tdoc["_id"] and p["bmatch"] == mm["id"]:
                    pms.append({**{k: v for k, v in p.items() if k not in ("tournament_id", "bmatch", "team_id", "map_id")},
                                "series_id": sid, "match_id": p["map_id"]})
    return Engine({"titles": list(ts.values()), "series": series, "matches": matches, "player_matches": pms}, None)


def stats_tab(tour):
    t = tour.t
    scope = st.segmented_control("Scope", ["this", "all"], default="this", key="tn_scope", label_visibility="collapsed",
                                 format_func={"this": "This tournament", "all": "All tournaments"}.get) or "this"
    ui.html(ui.note("Tournament stats, kept apart from the regular league numbers.", 8, 14))
    docs = [t] if scope == "this" else TD["tournaments"]
    tids = {d["_id"] for d in docs}
    pm = pd.DataFrame([p for p in TD["t_player_matches"] if p["tournament_id"] in tids])
    tnames = {(d["_id"], x["id"]): x["name"] for d in docs for x in d["teams"]}
    nmaps_all = len(TD["t_matches"])
    if pm.empty:
        ui.html(ui.empty_box("No stats yet", "Stats show up here once maps are entered with player stats. Winner-only results count in the bracket but have no stats."))
        return
    for c in ("kills", "deaths", "assists", "damage", "hill_time", "first_bloods", "bombs_planted", "overloads"):
        if c not in pm:
            pm[c] = None
    pm["teamname"] = [tnames.get((a, b), "") for a, b in zip(pm.tournament_id, pm.team_id)]
    g = pm.groupby("player")
    P = pd.DataFrame({"maps": g.size(), "w": g.result.apply(lambda s: int((s == "W").sum())), "k": g.kills.sum(), "d": g.deaths.sum(),
                      "kpm": g.kills.mean(), "dmg": g.damage.mean(), "fb": g.first_bloods.sum(min_count=1),
                      "teams": g.teamname.apply(lambda s: ", ".join(dict.fromkeys(s)))})
    hp = pm[pm["mode"] == "HP"].groupby("player").hill_time.mean()
    P["hill"] = hp
    P["kd"] = P.k / P.d.clip(lower=1)
    P = P.sort_values("kd", ascending=False)
    q = P[P.maps >= MINMAPS] if (P.maps >= MINMAPS).any() else P
    mar = None
    if nmaps_all >= 30:
        try:
            e = tour_engine()
            sub = e.pm[e.pm.series_id.str.split(":").str[0].isin(tids)]
            mar = sub.groupby("player").mar.mean()
        except Exception:
            mar = None
    # KPIs
    maps_here = len([x for x in TD["t_matches"] if x["tournament_id"] in tids])
    best_kd = q.kd.idxmax(); best_k = q.kpm.idxmax()
    if scope == "this":
        hillp = q.hill.dropna(); dmgp = q.dmg.dropna()
        k4 = ((ui.mmss(hillp.max()), "Hill time per map", hillp.idxmax()) if len(hillp) else
              (f"{dmgp.max():,.0f}", "Damage per map", dmgp.idxmax()) if len(dmgp) else (str(int(q.maps.max())), "Most maps", q.maps.idxmax()))
        kp = [(str(maps_here), "Maps played", f"{len([m for m in t['matches'] if tour.R[m['id']]['status'] == 'done'])} series finished"),
              (f"{q.kd.max():.2f}", "Best K/D", best_kd), (f"{q.kpm.max():.1f}", "Kills per map", best_k), k4]
    else:
        champs = {}
        for d in TD["tournaments"]:
            tt = Tour(d); ch = T.champion(d, tt.R, tt.maps, tt.kd)
            for p in (tt.teams[ch]["players"] if ch and ch in tt.teams else []):
                champs[p] = champs.get(p, 0) + 1
        fin = sum(1 for d in TD["tournaments"] if FIN.get(d["_id"]))
        top = max(champs.values()) if champs else 0
        kp = [(str(len(TD["tournaments"])), "Tournaments", f"{fin} finished · {len(TD['tournaments']) - fin} live"), (str(maps_here), "Maps played", "All tournaments"),
              (f"{q.kd.max():.2f}", "Best K/D", best_kd), (str(top), "Most titles", ", ".join(p for p, n in champs.items() if n == top) if top else "—")]
    cells = "".join(f"<div style='padding:18px 0 14px'><div style='font-weight:300; font-size:38px; line-height:1'>{escape(v)}</div>"
                    f"<div style='font-size:13px; color:{ui.MUTED}; margin-top:6px'>{escape(l)}</div><div style='font-size:14px; font-weight:600; margin-top:6px'>{escape(str(w))}</div></div>"
                    for v, l, w in kp)
    ui.html(f"<div style='display:grid; grid-template-columns:repeat(auto-fit, minmax(max(140px, 22%), 1fr)); column-gap:24px; border-top:2px solid {ui.INK}; margin-top:14px'>{cells}</div>")
    # players
    qual = P[P.maps >= MINMAPS]
    body = []
    for name, x in P.iterrows():
        ok = x.maps >= MINMAPS

        def sh(v, col, low=False):
            if not ok:
                return {"v": v, "bg": "#C9D1CC", "fg": ui.MUTED}
            bg, fg = ui.tint(x[col], list(qual[col]), low)
            return {"v": v, "bg": bg, "fg": fg, "w": 500}
        row = [{"v": escape(name), "w": 600}, {"v": escape(x.teams), "fg": ui.MUTED}, str(int(x.maps)), f"{int(x.w)}-{int(x.maps - x.w)}",
               sh(f"{x.kd:.2f}", "kd"), sh(f"{x.kpm:.1f}", "kpm"), sh(ui.n0(x.dmg), "dmg"), ui.mmss(x.hill), "—" if pd.isna(x.fb) else str(int(x.fb))]
        if mar is not None:
            row.append(ui.sg(mar.get(name), 2))
        body.append(row)
    cols = [("Player", "left"), ("Team", "left"), ("Maps", "right"), ("Maps W-L", "right"), ("K/D", "right"), ("Kills / map", "right"),
            ("Damage / map", "right"), ("Hill / map", "right"), ("First bloods", "right")] + ([("MAR / map", "right")] if mar is not None else [])
    ui.html(ui.h2("Players", margin_top=36, right=f"<span style='font-size:12px; color:{ui.MUTED}'>{escape(t['name'] if scope == 'this' else 'All tournaments')}</span>")
            + ui.table(cols, body, min_width=760)
            + f"<div style='display:flex; flex-wrap:wrap; gap:6px 18px; margin-top:10px; font-size:12px; color:{ui.MUTED}'>"
            + f"<span>Shaded: lowest → highest</span><span>Grey: under {MINMAPS} maps, not shaded</span></div>")
    if mar is not None:
        ui.html(ui.note(f"MAR is Provisional here: it's calibrated on 3v3 and 4v4 games, and these are {t['size']}v{t['size']}.", 10, 12))
    # teams
    trows = []
    for d in docs:
        tt = Tour(d)
        plc = T.placements(d, tt.R, tt.maps, tt.kd)
        for x in d["teams"]:
            sw = sl = 0
            for m in d["matches"]:
                r = tt.R[m["id"]]
                if r["status"] == "done" and x["id"] in (r["a"], r["b"]):
                    sw += r["winner"] == x["id"]; sl += r["loser"] == x["id"]
            mw = sum(1 for mm in tt.maps if (mm["team_a"] == x["id"] and mm["winner"] == "A") or (mm["team_b"] == x["id"] and mm["winner"] == "B"))
            ml = sum(1 for mm in tt.maps if x["id"] in (mm["team_a"], mm["team_b"])) - mw
            mine = pm[(pm.tournament_id == d["_id"]) & (pm.team_id == x["id"])]
            nm = mine.map_id.nunique()
            kd = mine.kills.sum() / max(mine.deaths.sum(), 1) if nm else None
            kpm = mine.kills.sum() / nm if nm else None
            fin = plc.get(x["id"]) or ("Still in" if not FIN.get(d["_id"]) else "")
            trows.append((sw, mw - ml, [{"v": f"{ui.swatch(tt.color[x['id']], 10, 10)} {escape(x['name'])}", "w": 600},
                                        f"{sw}-{sl}", f"{mw}-{ml}", "—" if kd is None else f"{kd:.2f}", "—" if kpm is None else f"{kpm:.1f}",
                                        {"v": escape(fin + ('' if scope == 'this' else ' · ' + d['name'])), "fg": ui.MUTED}]))
    trows.sort(key=lambda z: (-z[0], -z[1]))
    ui.html(ui.h2("Teams", margin_top=36) + ui.table([("Team", "left"), ("Series W-L", "right"), ("Maps W-L", "right"), ("K/D", "right"),
                                                      ("Kills / map", "right"), ("Finish", "right")], [z[2] for z in trows], min_width=560))


# ===================================================================== map entry view
def entry_view():
    E = ss.get("tn_entry")
    doc = next((x for x in TOURS if x["_id"] == (E or {}).get("tid")), None)
    if not E or not doc or not CAN_EDIT:
        ss.tn_view = "main"; st.rerun()
    tour = Tour(doc)
    if E["mid"] not in tour.ms or tour.R[E["mid"]]["a"] in (None, T.BYE) or tour.R[E["mid"]]["b"] in (None, T.BYE):
        # the match changed under us (e.g. undone on another phone): back to the bracket
        ss.pop("tn_entry", None); ss.tn_view = "main"; st.rerun()
    m = tour.ms[E["mid"]]; r = tour.R[m["id"]]
    A, B = tour.teams[r["a"]], tour.teams[r["b"]]
    D = E["draft"]
    nsaved = len(r["maps"])
    map_no = next((x["map_no"] for x in r["maps"] if x["_id"] == D["match_id"]), nsaved + 1)

    def back():
        ss.pop("tn_entry", None); ss.tn_view = "main"

    def on_save(mode, map_name, sa, sb, ln, board, rows, match_id):
        data.save_tmap(doc, m["id"], r["a"], r["b"], mode, map_name, sa, sb, ln, board, rows, map_id=match_id)
        fresh = data.load_tdocs()
        if match_id and T.redraw_after(doc, T.resolve(doc, [x for x in fresh["t_matches"] if x["tournament_id"] == doc["_id"]]), m["id"]):
            data.save_tournament(doc)  # an edited Swiss result: later rounds not yet played get drawn again
        if T.advance(doc, [x for x in fresh["t_matches"] if x["tournament_id"] == doc["_id"]]):
            data.save_tournament(doc)
        ss.tn_flash = {"tid": doc["_id"], "mid": m["id"]}
        back()

    ui.html("<style>[data-testid='stMainBlockContainer'] { max-width: 760px; }</style>")
    if st.button("‹ Back to the bracket", type="tertiary", key="tn_back"):
        back(); st.rerun()
    so_far = " · ".join(f"Map {x['map_no']}: {SHORT.get(x['mode'], x['mode'])} on {escape(x['map'])}, won by {escape(A['name'] if x['winner'] == 'A' else B['name'])}" for x in r["maps"])
    with st.container(key="tn_head"):
        ui.html(f"<div style='font-size:12px; font-weight:600; letter-spacing:1.6px; text-transform:uppercase; color:{ui.MUTED}'>{escape(doc['name'])} · {escape(m['label'])} · Bo{m['bo']}</div>"
                "<div style='display:grid; grid-template-columns:minmax(0,1fr) auto minmax(0,1fr); align-items:center; gap:8px 18px; margin-top:10px'>"
                f"<span style='text-align:right; font-size:17px; font-weight:500; color:{tour.color.get(r['a'], ui.INK)}'>{escape(A['name'])}</span>"
                f"<span style='font-weight:300; font-size:34px; line-height:1'>{r['wa']} – {r['wb']}</span>"
                f"<span style='font-size:17px; font-weight:500; color:{tour.color.get(r['b'], ui.INK)}'>{escape(B['name'])}</span></div>"
                + (f"<div style='font-size:12px; color:{ui.MUTED}; margin-top:10px; text-align:center'>{so_far}</div>" if so_far else ""))
    me.entry(me.Ctx(tcfg=ts[doc["title"]], team_a=A["players"], team_b=B["players"], map_no=map_no, prefix="tn", on_save=on_save,
                    label_a=A["name"], label_b=B["name"], played=tuple(x["map"] for x in r["maps"] if x["_id"] != D["match_id"]),
                    on_cancel=back, show_cancel=True, color_a=tour.color.get(r["a"]), color_b=tour.color.get(r["b"])), D)
    ui.html(ui.note("The teams, series and map number come from the bracket, so there's no setup step. Nothing here reaches the Series Log.", 14, 12))


# ===================================================================== setup view
def snake(order, n_teams, size):
    """Snake draft: 1-2-3-4, then 4-3-2-1, so every team ends up close in rating."""
    groups = [[] for _ in range(n_teams)]
    for k, p in enumerate(order[:n_teams * size]):
        r, i = divmod(k, n_teams)
        groups[i if r % 2 == 0 else n_teams - 1 - i].append(p)
    return groups


def setup_tab():
    if not CAN_EDIT:
        ui.html("<div style='height:10px'></div>")
        unlock_box("set up a tournament")
        return
    if not ss.get("tn_form"):
        ui.html(ui.note("Set up a new tournament: pick the game, the format, the players and the match lengths, and the bracket is drawn for you.", 18, 14))
        ui.html("<div style='height:12px'></div>")
        with st.container(horizontal=True, gap="small", vertical_alignment="center"):
            if st.button("New Tournament", type="primary", key="tn_new"):
                ss.tn_form = True; st.rerun()
            if not PRACTICE:
                st.button("Switch to Practice Mode", type="tertiary", on_click=cb_practice, args=(True,), key="tn_practice_on")
                if PW is not None and st.button("Log Out", type="tertiary", key="tn_logout"):
                    ss.sk_auth = False; st.rerun()
        return
    setup_view()


def setup_view():
    S = ss.setdefault("tn_setup", {"name": "", "date": dt.date.today(), "size": 2, "fmt": "de", "opts": {}, "len": dict(T.DEFAULT_LEN),
                                   "picked": [], "build": "hand", "hand": {}, "shuffle": 0, "seed": "rating", "order": None, "seed_shuffle": 0,
                                   "names": {}, "ver": 0})
    tids = sorted(ts, key=lambda x: (x != cur_title, -ts[x].get("order", 0)))
    S.setdefault("title", cur_title)
    if S["title"] not in ts:
        S["title"] = cur_title
    R8 = ratings(S["title"])
    names_all = [p["_id"] for p in data.load_docs()["players"] if p.get("active", True)]
    names_all = sorted(names_all, key=lambda p: (-R8.get(p, 0), p))
    rating = lambda p: R8.get(p, 1500)  # noqa: E731  (no games yet: the 1500 average)

    ui.html("<style>[data-testid='stMainBlockContainer'] { max-width: 820px; }</style>")
    a, b = st.columns([4, 1], vertical_alignment="bottom")
    with a:
        ui.html(ui.h2("New Tournament", margin_top=12, rule=False))
    with b:
        if st.button("Cancel", type="tertiary", key="tn_cancel"):
            ss.tn_form = False; st.rerun()
    ui.html(f"<div style='border-top:2px solid {ui.INK}; margin-top:10px'></div>"
            + ui.note("Practice mode works here too, so a test bracket never gets saved." if not PRACTICE else "Practice mode: this tournament stays on the private copy.", 12, 14))

    # 1. basics
    ui.html("<div style='font-weight:300; font-size:24px; margin-top:28px'>1. Basics</div>")
    c1, c2 = st.columns([2, 1])
    with c1:
        S["name"] = me.field(st.text_input, "Name", "tn_s_name", S, "name", "", placeholder="e.g. Winter 2v2 Cup").strip()
    with c2:
        S["date"] = me.field(st.date_input, "Date", "tn_s_date", S, "date", dt.date.today(), format="YYYY-MM-DD")
    S["title"] = me.field(st.selectbox, "Game", "tn_s_title", S, "title", cur_title, options=tids,
                          format_func=lambda x: f"{ts[x]['name']} ({ts[x].get('year', '')})" + (" · current" if x == cur_title else ""))
    ui.html(ui.note("The game sets the map pool for map entry and the ratings used for seeding.", 0, 12))
    with st.container(key="skfull_tnsize"):
        size = me.field(st.segmented_control, "Team Size", "tn_s_size", S, "size", 2, options=[1, 2, 3, 4], format_func=lambda z: f"{z}v{z}") or 2
    if size != S.get("_size_prev"):
        if S.get("_size_prev") is not None:
            S["hand"] = {}; S["ver"] += 1; S["order"] = None
        S["_size_prev"] = size
    S["size"] = size

    # 2. format
    ui.html("<div style='font-weight:300; font-size:24px; margin-top:32px'>2. Format</div>")
    fl = list(T.FORMATS)
    for i in range(0, len(fl), 2):
        cols = st.columns(2)
        for c, f in zip(cols, fl[i:i + 2]):
            on = S["fmt"] == f
            with c:
                with st.container(key=f"tnfmt_{f}", gap=None):
                    ui.html(f"<div style='padding:14px 14px 16px; min-height:96px; box-sizing:border-box; background:{ui.INK if on else ui.PANEL}; "
                            f"color:{ui.PANEL if on else ui.INK}; border:1px solid {ui.INK if on else ui.RULE}'>"
                            f"<div style='font-size:15px; font-weight:600'>{escape(T.FORMATS[f][0])}</div>"
                            f"<div style='font-size:12px; line-height:1.45; margin-top:6px; color:{ui.RULE if on else ui.MUTED}'>{escape(T.FORMATS[f][1])}</div></div>")
                    if st.button(T.FORMATS[f][0], key=f"tn_fmtb_{f}", width="stretch"):
                        S["fmt"] = f; st.rerun()
    fmt = S["fmt"]
    O = S["opts"].setdefault(fmt, T.default_opts(fmt))
    box = st.container(border=True)
    with box:
        ui.html(ui.label(f"Rules · {T.FORMATS[fmt][0]}"))
        for k, lab, help_, choices in T.OPTIONS[fmt]:
            vals = [v for v, _ in choices]; labs = dict(choices)
            ui.html(f"<div style='padding:10px 0 6px'><div style='font-size:14px'>{escape(lab)}</div><div style='font-size:12px; color:{ui.MUTED}'>{escape(help_)}</div></div>")
            cur = O.get(k, vals[0])
            v = st.segmented_control(lab, vals, default=cur if cur in vals else vals[0], format_func=labs.get, key=f"tn_o_{fmt}_{k}",
                                     label_visibility="collapsed")
            O[k] = vals[0] if v is None else v

    # 3. teams
    ui.html("<div style='font-weight:300; font-size:24px; margin-top:32px'>3. Teams</div>")
    picked = [p for p in names_all if p in S["picked"]]
    n_teams = len(picked) // size
    # teams (as lists of players) for the current build
    build = S["build"]
    if build == "hand":
        groups = [[p for p in picked if S["hand"].get(p) == i][:size] for i in range(n_teams)]
    elif build == "random":
        order = picked[:]; random.Random(1000 + S["shuffle"]).shuffle(order)
        groups = [order[i * size:(i + 1) * size] for i in range(n_teams)]
    else:
        order = sorted(picked, key=lambda p: -rating(p))
        groups = snake(order, n_teams, size) if n_teams else []
    placed = {p for g in groups for p in g}
    pool = [p for p in picked if p not in placed]
    tcol = {p: TEAMC[i % len(TEAMC)] for i, g in enumerate(groups) for p in g}

    ui.html(f"<div style='font-size:13px; margin-top:12px'>Who's Playing · {len(picked)} players</div>")
    css = ""
    with st.container(horizontal=True, gap="small", key="tn_roster"):
        for i, p in enumerate(names_all):
            on = p in S["picked"]

            def tog(p=p, on=on):
                S["picked"] = [x for x in S["picked"] if x != p] if on else S["picked"] + [p]
                S["hand"].pop(p, None); S["ver"] += 1
            st.button(p + (f" · {groups.index(next(g for g in groups if p in g)) + 1}" if p in tcol else ""), key=f"tn_rp_{i}",
                      type="primary" if on else "secondary", on_click=tog)
            if on:
                bg = tcol.get(p)
                css += (f".st-key-tn_rp_{i} button {{ background:{bg or ui.PANEL} !important; border-color:{bg or ui.INK} !important; color:{ui.LIGHT if bg else ui.INK} !important; }}")
            else:
                css += f".st-key-tn_rp_{i} button {{ color:{ui.MUTED}; }}"
    ui.html(f"<style>{css}</style>" + ui.note("Tap to add or take someone out. Once they're on a team, they take that team's color and number.", 6, 12))

    ui.html("<div style='font-size:13px; margin-top:18px'>Make the Teams</div>")
    with st.container(key="skfull_tnbuild"):
        nb = st.segmented_control("Make the teams", ["hand", "random", "balanced"], default=build, key="tn_s_build", label_visibility="collapsed",
                                  format_func={"hand": "By hand", "random": "Random draw", "balanced": "Balanced by rating"}.get) or build
    if nb != build:
        S["build"] = nb; S["order"] = None; st.rerun()
    ui.html(ui.note({"hand": "Drag players onto a team. On a phone, press and hold for a moment, then drag. Or use Tap instead below.",
                     "random": "Teams are drawn at random. Draw Again until you like them.",
                     "balanced": "A snake draft by rating, so every team ends up close in average rating."}[build], 6, 12))

    unrated = [p for p in picked if p not in R8]
    if unrated and build != "random":
        ui.html(ui.note(f"No games yet for {', '.join(unrated)}, so they count as 1500 (the league average) "
                        "for balancing and seeding. Adjust by hand if you know better.", 6, 12))
    if build == "hand" and n_teams:
        from streamlit_sortables import sort_items
        heads = ["Not on a team yet"] + [f"Team {i + 1}" for i in range(n_teams)]
        items = [{"header": heads[0], "items": pool}] + [{"header": heads[i + 1], "items": g} for i, g in enumerate(groups)]
        # fixed heights: a box that grows or shrinks mid-drag makes the drop target flip back and forth,
        # which is what trips React's "maximum update depth" error (#185)
        pool_h = 44 + 46 * math.ceil(max(len(picked), 1) / 3)
        team_h = 44 + 46 * math.ceil((size + 1) / 2)
        sty = (f"@import url('https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@400;600&display=swap');"
               f".sortable-component {{ border:0; background:transparent; padding:0; font-family:'Hanken Grotesk', sans-serif; display:grid; "
               f"grid-template-columns:repeat(auto-fill, minmax(200px, 1fr)); gap:10px; }}"
               f".sortable-container {{ background:{ui.PANEL}; border:1px solid {ui.RULE}; border-radius:0; margin:0; height:{team_h}px; box-sizing:border-box; "
               f"padding:10px 12px; overflow:hidden; }}"
               f".sortable-container:nth-child(2) {{ grid-column:1 / -1; border:1px dashed {ui.STEEL}; height:{pool_h}px; }}"
               f".sortable-container-header {{ background:transparent; color:{ui.MUTED}; font-size:12px; font-weight:600; letter-spacing:1.4px; text-transform:uppercase; padding:0 0 8px; }}"
               f".sortable-container-body {{ background:transparent; display:flex; flex-wrap:wrap; gap:6px; min-height:40px; padding:0; }}"
               f".sortable-item, .sortable-item:hover {{ margin:0; border-radius:0; font-size:14px; padding:9px 14px; touch-action:manipulation; user-select:none; "
               f"background:#F2F4F2; color:{ui.INK}; border:1px solid {ui.INK}; }}"
               f".sortable-item.dragging {{ opacity:.9; }}"
               # the add-on puts a <style> first, so the "Not on a team yet" box is child 2 and team i is child i + 3
               + "".join(f".sortable-container:nth-child({i + 3}) .sortable-container-header {{ color:{TEAMC[i % len(TEAMC)]}; }}"
                         f".sortable-container:nth-child({i + 3}) {{ border-left:6px solid {TEAMC[i % len(TEAMC)]}; }}"
                         f".sortable-container:nth-child({i + 3}) .sortable-item {{ background:{TEAMC[i % len(TEAMC)]}; color:{ui.LIGHT}; border-color:{TEAMC[i % len(TEAMC)]}; }}"
                         for i in range(n_teams)))
        out = sort_items(items, multi_containers=True, direction="horizontal", custom_style=sty, key=f"tn_drag_{S['ver']}_{len(picked)}_{size}")
        new_hand = {}
        for i, cont in enumerate(out[1:]):
            for p in cont["items"]:
                new_hand[p] = i
        if new_hand != {p: i for i, g in enumerate(groups) for p in g}:
            S["hand"] = new_hand; st.rerun()
        over = [i + 1 for i, cont in enumerate(out[1:]) if len(cont["items"]) > size]
        if over:
            st.warning(f"Team {', '.join(map(str, over))} has more than {size} player{'s' if size > 1 else ''}. Drag someone back to the box.")
        if st.button("Reset Drag Boxes", type="tertiary", key="tn_drag_reset",
                     help="If the drag boxes ever show an error, this reloads them. Your teams are kept."):
            S["ver"] += 1; st.rerun()
        with st.expander("Tap instead"):
            act = st.segmented_control("Add to", list(range(n_teams)), default=0, format_func=lambda i: f"Team {i + 1}", key="tn_tap_team") or 0
            ui.html(ui.note(f"Tap a player to put them on Team {act + 1}; tap again to take them off.", 0, 12))
            tcss = "".join(f".st-key-tn_tap_{i} button {{ background:{TEAMC[S['hand'][p] % len(TEAMC)]} !important; border-color:{TEAMC[S['hand'][p] % len(TEAMC)]} !important; color:{ui.LIGHT} !important; }}"
                           for i, p in enumerate(picked) if S["hand"].get(p) is not None)
            ui.html(f"<style>{tcss}</style>")
            with st.container(horizontal=True, gap="small"):
                for pi, p in enumerate(picked):
                    on_t = S["hand"].get(p)

                    def tap(p=p, on_t=on_t, act=act):
                        if on_t is not None:
                            S["hand"].pop(p, None)
                        elif len([x for x in S["hand"].values() if x == act]) < size:
                            S["hand"][p] = act
                        S["ver"] += 1
                    st.button(p + (f" · Team {on_t + 1}" if on_t is not None else ""), key=f"tn_tap_{pi}", on_click=tap,
                              type="primary" if on_t is not None else "secondary")
    elif n_teams:
        cards = "".join(f"<div style='position:relative; padding:12px 14px 12px 20px; background:{ui.PANEL}; border:1px solid {ui.RULE}'>"
                        f"<span style='position:absolute; left:0; top:0; bottom:0; width:6px; background:{TEAMC[i % len(TEAMC)]}'></span>"
                        f"<div style='font-size:12px; font-weight:600; letter-spacing:1.2px; text-transform:uppercase; color:{TEAMC[i % len(TEAMC)]}'>Team {i + 1}</div>"
                        f"<div style='display:flex; flex-wrap:wrap; gap:6px; margin-top:8px'>"
                        + "".join(f"<span style='padding:7px 12px; background:{TEAMC[i % len(TEAMC)]}; color:{ui.LIGHT}; font-size:14px'>{escape(p)}</span>" for p in g)
                        + f"</div><div style='font-size:12px; color:{ui.MUTED}; margin-top:8px'>Avg rating {round(sum(rating(p) for p in g) / len(g))}</div></div>"
                        for i, g in enumerate(groups))
        ui.html(f"<div style='display:grid; grid-template-columns:repeat(auto-fill, minmax(220px, 1fr)); gap:10px; margin-top:12px'>{cards}</div>")
        if build == "random":
            ui.html("<div style='height:14px'></div>")
            if st.button("Draw Again", key="tn_redraw"):
                S["shuffle"] += 1; S["order"] = None; st.rerun()
            ui.html("<div style='height:10px'></div>")
    if not n_teams:
        ui.html(ui.note(f"Pick at least {2 * size} players to make two teams of {size}.", 12, 13))

    full = [g for g in groups if len(g) == size]
    tname = lambda i: (S["names"].get(i) or " / ".join(groups[i])) if groups[i] else f"Team {i + 1}"  # noqa: E731
    if full and len(full) == n_teams:
        with st.expander("Team Names (Optional)"):
            ui.html(ui.note("Each team can pick its own name. Leave it blank to go by the players' names.", 0, 12))
            for i in range(n_teams):
                S["names"][i] = st.text_input(f"Team {i + 1}", value=S["names"].get(i, ""), placeholder=" / ".join(groups[i]), key=f"tn_rn_{i}_{'-'.join(groups[i])}").strip()

    # 4. seeding
    ui.html("<div style='font-weight:300; font-size:24px; margin-top:32px'>4. Seeding</div>")
    with st.container(key="skfull_tnseed"):
        sm = st.segmented_control("Seeding", ["rating", "random", "manual"], default=S["seed"], key="tn_s_seed", label_visibility="collapsed",
                                  format_func={"rating": "By rating", "random": "Random", "manual": "Set by hand"}.get) or S["seed"]
    if sm != S["seed"]:
        S["seed"] = sm
        if sm == "random":
            S["seed_shuffle"] += 1
        st.rerun()
    avg = [round(sum(rating(p) for p in g) / len(g)) if g else 0 for g in groups]
    by_r = sorted(range(n_teams), key=lambda i: -avg[i])
    if sm == "random":
        order = by_r[:]; random.Random(77 + S["seed_shuffle"]).shuffle(order)
    elif sm == "manual":
        order = S["order"] if S["order"] and sorted(S["order"]) == list(range(n_teams)) else by_r
        S["order"] = order
    else:
        order = by_r
    ui.html(ui.note({"rating": "Highest average rating is the #1 seed. Seeds decide who plays who first and who gets byes.",
                     "random": "Seeds are drawn at random. Pick Random again to redraw.", "manual": "Use the arrows to put the teams in order."}[sm], 6, 12))
    if sm == "random" and st.button("Redraw seeds", type="tertiary", key="tn_reseed"):
        S["seed_shuffle"] += 1; st.rerun()
    for j, i in enumerate(order):
        with st.container(key=f"tn_seedrow_{j}"):
            c1, c2 = st.columns([5, 1], vertical_alignment="center")
            with c1:
                ui.html(f"<div style='display:grid; grid-template-columns:30px 12px minmax(0,1fr) auto; gap:12px; align-items:center; padding:6px 0; border-bottom:1px solid {ui.RULE}'>"
                        f"<span style='font-size:13px; color:{ui.MUTED}'>#{j + 1}</span>{ui.swatch(TEAMC[i % len(TEAMC)], 12, 12)}"
                        f"<span style='font-size:15px; font-weight:600'>{escape(tname(i))}</span><span style='font-size:13px; color:{ui.MUTED}'>{avg[i] or '—'}</span></div>")
            if sm == "manual":
                with c2:
                    def mv(j=j, dd=-1):
                        o = S["order"][:]; k = j + dd
                        if 0 <= k < len(o):
                            o[j], o[k] = o[k], o[j]; S["order"] = o
                    with st.container(horizontal=True, gap="small"):
                        st.button("↑", key=f"tn_up_{j}", on_click=mv, kwargs={"j": j, "dd": -1}, disabled=j == 0)
                        st.button("↓", key=f"tn_dn_{j}", on_click=mv, kwargs={"j": j, "dd": 1}, disabled=j == len(order) - 1)

    # 5. match length
    ui.html("<div style='font-weight:300; font-size:24px; margin-top:32px'>5. Match Length</div>")
    L = S["len"]
    for k, lab in T.STAGES[fmt]:
        c1, c2 = st.columns([1, 1.6], vertical_alignment="center")
        with c1:
            ui.html(f"<div style='font-size:14px; padding:6px 0'>{escape(lab)}</div>")
        with c2:
            v = st.segmented_control(lab, [1, 3, 5, 7, 9], default=L.get(k, T.DEFAULT_LEN[k]), format_func=lambda z: f"Bo{z}", key=f"tn_len_{fmt}_{k}",
                                     label_visibility="collapsed")
            L[k] = v or L.get(k, T.DEFAULT_LEN[k])

    # summary + create
    teams = [{"id": f"t{i + 1}", "name": tname(i), "players": groups[i], "rating": avg[i], "seed": order.index(i) + 1} for i in range(n_teams)]
    o = dict(O)
    if fmt == "rrp":
        o["k"] = min(int(o["k"]), n_teams)
    if fmt == "sw" and o.get("after") == "top4" and n_teams < 4:
        o["after"] = "top2"
    lo, hi = T.series_count(fmt, n_teams, o)
    preview = []
    round_lab = "First Round"
    if n_teams >= 2:
        tmp = {"_id": "preview", "format": fmt, "opts": o, "lengths": {**T.DEFAULT_LEN, **L}, "teams": teams, "manual": {}}
        tmp["matches"] = T.build(tmp)
        R0 = T.resolve(tmp, [])
        tm = {x["id"]: (x["seed"], x["name"], TEAMC[(int(x["id"][1:]) - 1) % len(TEAMC)]) for x in teams}
        first = [m for m in tmp["matches"] if m["round"] == 1 and m["stage"] in ("W", "RR", "SW")]
        if fmt in ("rr", "rrp", "sw"):
            round_lab = "Round 1"
        for m in first:
            r = R0[m["id"]]
            if r["status"] == "bye" and r["winner"] not in (None, T.BYE):
                preview.append((tm[r["winner"]], None))
            elif r["a"] in tm and r["b"] in tm:
                preview.append((tm[r["a"]], tm[r["b"]]))
    names_ok = len({x["name"].lower() for x in teams}) == len(teams)
    if S["name"] and any(x["name"].strip().lower() == S["name"].lower() for x in TOURS):
        st.warning(f"There's already a tournament called {S['name']}. You can still use it, but a different name is easier to find later.")
    ok = n_teams >= 2 and not pool and all(len(g) == size for g in groups) and S["name"] and names_ok
    why = ("Give the tournament a name" if not S["name"] else "Need at least 2 teams" if n_teams < 2
           else f"Put every player on a team first ({', '.join(pool)})" if pool else "Every team needs " + str(size) + " players" if not all(len(g) == size for g in groups)
           else "Two teams have the same name" if not names_ok else "")
    extra = len(picked) % size if size > 1 else 0

    def row(t, line=False):
        seed, name, col = t
        return (f"<div style='display:grid; grid-template-columns:4px 22px minmax(0,1fr); align-items:center; gap:8px; height:34px; padding-right:10px; "
                f"border-top:{'1px solid ' + ui.RULE if line else '0'}'><span style='align-self:stretch; background:{col}'></span>"
                f"<span style='font-size:11px; color:{ui.MUTED}'>{seed}</span><span style='font-size:14px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis'>{escape(name)}</span></div>")
    cards = ""
    for a_, b_ in preview:
        if b_ is None:
            cards += (f"<div style='border:1px dashed {ui.STEEL}'>{row(a_)}<div style='height:34px; display:flex; align-items:center; padding:0 10px 0 34px; "
                      f"border-top:1px dashed {ui.RULE}; font-size:13px; color:{ui.MUTED}'>Bye to Round 2</div></div>")
        else:
            cards += f"<div style='background:{ui.LIGHT}; border:1px solid {ui.RULE}'>{row(a_)}{row(b_, True)}</div>"
    tiles = [("Game", ts[S["title"]]["name"]), ("Teams", str(n_teams)), ("Team Size", f"{size}v{size}"),
             ("Format", T.FORMATS[fmt][0]), ("Series", f"{lo}–{hi}" if hi != lo else str(lo))]
    tile_html = "".join(f"<div style='padding:12px; background:{ui.LIGHT}; border:1px solid {ui.RULE}'>"
                        f"<div style='font-size:11px; font-weight:600; letter-spacing:1.2px; text-transform:uppercase; color:{ui.MUTED}'>{lab}</div>"
                        f"<div style='font-size:16px; font-weight:400; margin-top:6px; line-height:1.25'>{escape(v)}</div></div>" for lab, v in tiles)
    status = (f"<div style='margin-top:16px; padding:10px 12px; border-left:3px solid {ui.RUST}; background:{ui.LIGHT}; font-size:13px'>"
              + escape(why) + (f". {extra} player{'s' if extra > 1 else ''} left over: add or remove someone to even out the teams." if extra else ".") + "</div>"
              if why else ui.note("Ready to go. Results stay on this page, never the Series Log or regular stats.", 16, 13))
    ui.html(f"<div style='margin-top:28px; padding:18px; background:{ui.PANEL}; border:1px solid {ui.RULE}'>"
            + ui.label("Summary")
            + f"<div style='display:grid; grid-template-columns:repeat(auto-fit, minmax(96px, 1fr)); gap:8px; margin-top:10px'>{tile_html}</div>"
            + (ui.label(round_lab, margin_top=20) + f"<div style='display:grid; grid-template-columns:repeat(auto-fill, minmax(220px, 1fr)); gap:8px; margin-top:10px'>{cards}</div>"
               if cards else "")
            + status + "</div>")
    if st.button("Create tournament · draw the bracket", type="primary", width="stretch", disabled=not ok, key="tn_create"):
        doc = {"_id": data.next_tournament_id(), "name": S["name"], "date": pd.Timestamp(S["date"]).date().isoformat(), "title": S["title"],
               "size": size, "format": fmt, "opts": o, "lengths": {**T.DEFAULT_LEN, **L}, "teams": teams, "manual": {},
               "created": dt.datetime.now().isoformat(timespec="seconds"), "finished": False}
        doc["matches"] = T.build(doc)
        data.save_tournament(doc)
        ss.pop("tn_setup", None)
        for k in [k for k in ss if k.startswith("tn_s_") or k.startswith("tn_o_") or k.startswith("tn_len_")]:
            del ss[k]
        ss.tn_goto = doc["_id"]; ss.tn_view = "main"; ss.tn_form = False; ss.tn_top_goto = "view"; st.rerun()


# ===================================================================== route
if view == "entry":
    entry_view()
    st.stop()
top = ui.tabs("tn_top", ["view", "setup"], {"view": "Tournaments", "setup": "Setup"})
if top == "setup":
    setup_tab()
    st.stop()
if not TOURS:
    ui.html(ui.empty_box("No tournaments yet", "Head to Setup to start one: pick the players, the format and the match lengths, and the bracket is drawn for you."))
    st.stop()
doc = SEL or TOURS[0]
if T.advance(doc, tmaps(doc["_id"]), team_kd(doc["_id"])):
    data.save_tournament(doc); st.rerun()
tour = Tour(doc)
summary(tour)
tab = ui.tabs("tn_tab", ["bracket", "matches", "stats"], {"bracket": "Bracket", "matches": "Matches", "stats": "Stats"})
if tab == "bracket":
    bracket_tab(tour)
elif tab == "matches":
    matches_tab(tour)
else:
    stats_tab(tour)
if CAN_EDIT:
    ui.html("<div style='height:40px'></div>")
    with st.expander("Delete this tournament"):
        ui.html(ui.note(f"Deletes {escape(doc['name'])}, its bracket and every map and stat entered for it. This can't be undone.", 0, 13))
        if st.button(f"Delete {doc['name']}", key="tn_delete"):
            data.delete_tournament(doc["_id"])
            ss.tn_goto = None; st.rerun()