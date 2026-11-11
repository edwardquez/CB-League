"""Scorekeeper: password-protected data entry (with the optional map veto), players and Season Settings.

Layout: a step rail (Set Up, Maps, Done), a working column, and a live series slip beside it that follows the series
from setup to the final score. League Admin (players, Season Settings, backup) sits under Set Up as tabs.
"""
from __future__ import annotations

import copy
import datetime as dt
import difflib
import hmac
import random
from html import escape

import pandas as pd
import streamlit as st

from cbl import data
from cbl import veto as V
from cbl.db import is_preview
from cbl.ui import map_entry as me, page, styles as ui

page.start("Scorekeeper")
ss = st.session_state
MODEN = me.MODEN
SHORT = me.SHORT
SIDE_LABEL = V.SIDE_LABEL
CONV = {"HP": [("hill_sec_per_kill", "Hill time: seconds per kill")],
        "SND": [("plant", "Plant (kills)"), ("fb_margin", "First-blood margin (kills)")],
        "OVL": [("overload", "Overload (kills)"), ("carrier_kill", "Carrier kill (extra kills)"), ("kill_as_carrier", "Kill as carrier (kills)")],
        "HJ": [("dunk", "Dunk (kills)"), ("remote_plant", "Remote plant (kills)"), ("interception", "Interception (kills)")]}
RSCALE = 130          # rating points per 10x odds, as on the Matchup Preview
CLOSE = 0.53          # a side rated under this is too close to call: flip a coin instead

ui.html(f"""<style>
/* Streamlit greys out the page while a tap is processed; on quick taps that reads as a stutter, so keep it at full strength */
[data-testid="stMain"] [data-stale="true"] {{ opacity: 1 !important; transition: none !important; }}
/* the step rail */
.sk-rail {{ display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); margin: 24px 0 30px !important; max-width: 620px; padding: 0 !important; }}
.sk-rs {{ display: flex; align-items: center; gap: 10px; padding-right: 12px; list-style: none; margin: 0 !important; padding-left: 0 !important; }}
.sk-rs:not(:last-child)::after {{ content: ""; flex: 1 1 auto; height: 2px; background: {ui.RULE}; margin-left: 4px; }}
.sk-rs.done:not(:last-child)::after {{ background: {ui.BLUE}; }}
.sk-dot {{ width: 28px; height: 28px; flex: none; border-radius: 50%; border: 1.5px solid {ui.STEEL}; display: inline-flex; align-items: center;
  justify-content: center; font-size: 13px; font-weight: 600; color: {ui.MUTED}; box-sizing: border-box; }}
.sk-rs.cur .sk-dot {{ background: {ui.INK}; border-color: {ui.INK}; color: {ui.BG}; }}
.sk-rs.done .sk-dot {{ background: {ui.BLUE}; border-color: {ui.BLUE}; color: {ui.on(ui.BLUE)}; }}
.sk-rl {{ font-size: 14px; color: {ui.MUTED}; white-space: nowrap; }}
.sk-rs.cur .sk-rl {{ color: {ui.INK}; font-weight: 600; }}
.sk-h {{ font-weight: 300; font-size: 30px; letter-spacing: -.4px; line-height: 1.15; }}
/* numbered setup questions */
.st-key-skqs {{ border-top: 2px solid {ui.INK}; gap: 0 !important; }}
[class*="st-key-skq_"] {{ border-bottom: 1px solid {ui.RULE}; padding: 14px 0 16px !important; gap: 10px !important; }}
[class*="st-key-skq_"] [data-testid="stMarkdownContainer"] {{ margin-bottom: 0 !important; }}
.sk-qh {{ display: grid; grid-template-columns: 48px minmax(0,1fr); gap: 2px 0; align-items: baseline; }}
.sk-qn {{ font-size: 13px; color: {ui.MUTED}; font-weight: 600; font-variant-numeric: tabular-nums; }}
.sk-ql {{ font-size: 15px; font-weight: 600; }} .sk-ql span {{ font-weight: 400; color: {ui.MUTED}; }}
.sk-qv {{ font-size: 15px; margin-top: 4px; grid-column: 2; }}
[class*="st-key-skqi_"] {{ padding-left: 48px; }}
/* phones: the two draft-board columns fold into one list that keeps the across-the-row order (most maps first) */
@media (max-width: 640px) {{
  .st-key-skqi_teams [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]) {{ flex-direction: column !important; gap: 0 !important; }}
  .st-key-skqi_teams [data-testid="stColumn"], .st-key-skqi_teams [data-testid="stColumn"] > [data-testid="stVerticalBlock"] {{ display: contents !important; }}
  .st-key-skqi_teams div:has(> [class*="st-key-skdb_"]) {{ width: 100%; }}
{' '.join(f'.st-key-skqi_teams div:has(> .st-key-skdb_{i}) {{ order: {i}; }}' for i in range(40))}
}}
.st-key-skfull_bo {{ max-width: 340px; }}
/* draft board: tap A or B beside a name */
[class*="st-key-skdb_"] {{ min-height: 48px; border-bottom: 1px solid {ui.RULE}; gap: 0 !important; }}
[data-testid="stColumn"] > [data-testid="stVerticalBlock"]:has(> div > [class*="st-key-skdb_"]),
[data-testid="stColumn"] > [data-testid="stVerticalBlock"]:has(> [class*="st-key-skdb_"]), .st-key-skroster {{ gap: 0 !important; }}
[class*="st-key-skpl_"] {{ min-height: 46px; }}
[class*="st-key-skpl_"] > div:first-child {{ min-width: 0; flex: 1 1 auto; }}
[class*="st-key-skpl_"] [data-testid="stMarkdownContainer"], [class*="st-key-skdb_"] [data-testid="stMarkdownContainer"] {{ margin-bottom: 0 !important; }}
@media (max-width: 640px) {{ .sk-plr {{ grid-template-columns: minmax(0,1fr) !important; }} .sk-plr > span:nth-child(2) {{ display: none; }} }}
[class*="st-key-skpl_"] [data-testid="stPopover"] button {{ border-color: transparent; background: transparent; min-height: 32px; padding: 0 8px; }}
[class*="st-key-skpl_"] [data-testid="stPopover"] button:hover {{ border-color: {ui.RULE}; }}
[class*="st-key-skpl_"] [data-testid="stPopover"] button p {{ font-size: 13px; }}
[class*="st-key-skdb_"] button {{ min-height: 32px !important; height: 32px; }}
[class*='st-key-skpl_'] [data-testid='stPopover'] button svg, [class*='st-key-skpl_'] [data-testid='stPopover'] button [data-testid='stIconMaterial'] {{ display: none; }}
[class*="st-key-skdb_"] button {{ min-height: 34px; width: 40px; padding: 0; border-radius: 0; }}
[class*="st-key-skdb_"] button p {{ font-size: 13px; font-weight: 600; }}
[class*="st-key-skdbB_"] {{ margin-left: 6px; }}
[class*="st-key-skdbA_"] button[data-testid^="stBaseButton-primary"] {{ background: {ui.INK}; border-color: {ui.INK}; }}
[class*="st-key-skdbA_"] button[data-testid^="stBaseButton-primary"] p {{ color: {ui.BG}; }}
[class*="st-key-skdbB_"] button[data-testid^="stBaseButton-primary"], [class*="st-key-skdbB_"] button[data-testid^="stBaseButton-primary"]:hover {{
  background: {ui.BLUE} !important; border-color: {ui.BLUE} !important; }}
[class*="st-key-skdbB_"] button[data-testid^="stBaseButton-primary"] p {{ color: {ui.on(ui.BLUE)} !important; }}
[class*="st-key-skdb_"] [data-testid="stElementContainer"]:has(button) {{ width: auto !important; }}
/* the series slip */
.st-key-sk_slip {{ background: {ui.PANEL}; border: 1px solid {ui.RULE}; gap: 0 !important; }}
.st-key-sk_slip [data-testid="stMarkdownContainer"] {{ margin-bottom: 0 !important; }}
.st-key-sk_slipfoot {{ padding: 14px 18px 18px !important; border-top: 1px dashed {ui.RULE2}; gap: 8px !important; }}
[class*="st-key-skrow_"] {{ padding: 0 18px !important; }}
[class*="st-key-skrow_"] button {{ min-height: 30px; padding: 0 10px; }}
[class*="st-key-skrow_"] button p {{ font-size: 12px; }}
.sk-sh {{ display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 14px 18px; border-bottom: 1px dashed {ui.RULE2}; }}
.sk-lab {{ font-size: 12px; font-weight: 600; letter-spacing: 1.6px; text-transform: uppercase; color: {ui.MUTED}; }}
.sk-tag {{ font-size: 12px; font-weight: 600; padding: 3px 8px; border: 1px solid {ui.STEEL}; white-space: nowrap; }}
.sk-tag.warn {{ background: {ui.AMBER}; border-color: {ui.AMBER}; color: {ui.on(ui.AMBER)}; }}
.sk-tag.dark {{ background: {ui.INK}; border-color: {ui.INK}; color: {ui.BG}; }}
.sk-det > div {{ display: flex; justify-content: space-between; align-items: center; gap: 10px; min-height: 40px; border-top: 1px solid {ui.RULE}; font-size: 14px; }}
.sk-det > div > span:first-child {{ color: {ui.MUTED}; font-size: 13px; }}
.sk-det b {{ font-weight: 500; text-align: right; }}
.sk-team {{ font-size: 18px; font-weight: 500; margin-top: 6px; display: flex; flex-wrap: wrap; }}
.sk-team span + span::before {{ content: '·'; color: {ui.STEEL}; margin: 0 10px; font-weight: 400; }}
.sk-vs {{ font-size: 12px; color: {ui.MUTED}; margin: 16px 0; display: flex; align-items: center; gap: 10px; }}
.sk-vs::before, .sk-vs::after {{ content: ""; flex: 1; border-top: 1px solid {ui.RULE}; }}
.sk-pips {{ display: inline-flex; gap: 5px; }} .sk-pip {{ width: 14px; height: 14px; border: 1.5px solid {ui.STEEL}; box-sizing: border-box; }}
.sk-row {{ display: grid; grid-template-columns: 22px minmax(0,1fr) 56px; gap: 10px; align-items: start; padding: 9px 0; border-bottom: 1px solid {ui.RULE}; }}
.sk-row.cur {{ box-shadow: inset 3px 0 0 {ui.BLUE}; padding-left: 8px; margin-left: -8px; }}
.sk-row.plan .sk-rm, .sk-row.empty .sk-rm {{ color: {ui.MUTED}; }} .sk-row.plan img {{ opacity: .55; }}
.sk-mn {{ font-size: 12px; color: {ui.MUTED}; font-weight: 600; padding-top: 2px; }}
.sk-rm {{ font-size: 14px; }} .sk-rm b {{ font-weight: 600; color: {ui.INK}; }}
.sk-rt {{ display: flex; flex-wrap: wrap; gap: 4px 12px; margin-top: 3px; }} .sk-rt:empty {{ display: none; }}
.sk-st {{ display: inline-flex; align-items: center; gap: 5px; font-size: 12px; color: {ui.INK}; }}
.sk-chg {{ font-size: 11px; font-weight: 600; padding: 1px 6px; background: {ui.AMBER}; color: {ui.on(ui.AMBER)}; margin-left: 4px; white-space: nowrap; }}
.sk-thumb {{ width: 56px; aspect-ratio: 16/9; object-fit: cover; display: block; align-self: center; }}
.sk-thumb0 {{ box-sizing: border-box; border: 1px dashed {ui.RULE2}; }}
.sk-ban {{ display: flex; flex-wrap: wrap; gap: 4px 12px; align-items: center; font-size: 13px; padding: 6px 0; }}
.sk-ban > span:first-child {{ color: {ui.MUTED}; min-width: 76px; font-size: 12px; }}
/* the veto */
.st-key-vt_card {{ background: {ui.PANEL}; border: 1px solid {ui.RULE}; padding: 20px !important; margin-top: 4px; }}
.st-key-vt_card [data-testid="stMarkdownContainer"] {{ margin-bottom: 0 !important; }}
.vt-prompt {{ font-size: 24px; font-weight: 400; line-height: 1.25; text-wrap: balance; margin-top: 6px; display: flex; align-items: center; gap: 10px; }}
.vt-note, [data-testid='stMarkdownContainer'] p.vt-note {{ font-size: 13px !important; color: {ui.MUTED}; line-height: 1.5; margin: 8px 0 0; text-wrap: pretty; }}
.vt-line, [data-testid='stMarkdownContainer'] p.vt-line {{ font-size: 15px !important; line-height: 1.5; margin: 12px 0 0; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }} .vt-line b {{ font-weight: 600; }}
.vt-msg {{ margin: 6px 0 4px; padding: 8px 12px; background: {ui.AMBER}; color: {ui.on(ui.AMBER)}; font-size: 13px; }}
.vt-bar {{ height: 3px; background: {ui.RULE}; margin: 4px 0 14px; }} .vt-bar i {{ display: block; height: 100%; background: {ui.BLUE}; }}
.vt-who {{ display: flex; align-items: center; gap: 8px; font-size: 12px; font-weight: 600; letter-spacing: 1.2px; text-transform: uppercase; color: {ui.MUTED}; }}
.vt-sub {{ font-size: 13px; color: {ui.MUTED}; margin-top: 6px; }}
.vt-last {{ margin-top: 6px; padding-top: 12px; border-top: 1px solid {ui.RULE}; font-size: 13px; color: {ui.MUTED}; }}
.vt-ok {{ display: inline-flex; width: 26px; height: 26px; align-items: center; justify-content: center; background: {ui.BLUE}; color: {ui.on(ui.BLUE)}; font-size: 14px; }}
.vt-tile {{ position: relative; border: 1px solid {ui.RULE}; background: {ui.BG}; }}
.vt-tile.used img {{ filter: grayscale(1); opacity: .35; }} .vt-tile.used .vt-n {{ color: {ui.MUTED}; }}
.vt-n {{ display: block; padding: 8px 10px 9px; font-size: 14px; font-weight: 500; }}
.vt-tag {{ position: absolute; top: 8px; left: 8px; display: inline-flex; align-items: center; gap: 6px; padding: 3px 7px; background: {ui.PANEL};
  border: 1px solid {ui.RULE}; font-size: 12px; font-weight: 600; color: {ui.INK}; }}
[class*="st-key-skmap_vt"]:has(button:disabled) .vt-tile {{ cursor: default; }}
[class*="st-key-skmap_vt"]:has(button:not(:disabled)):hover .vt-tile {{ border-color: {ui.BLUE}; box-shadow: 0 0 0 1px {ui.BLUE}; }}
.st-key-vt_sides button {{ min-height: 48px; padding: 0 20px; }}
/* phones: once maps are being entered, the score leads */
@media (max-width: 640px) {{
  .st-key-skgrid_late > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child,
  .st-key-skgrid_late > div > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child {{ order: -1; }}
  .sk-rl {{ font-size: 13px; }}
  .vt-prompt {{ font-size: 19px; }}
  .st-key-vt_card {{ padding: 16px !important; }}
}}
</style>""" + me.css())


def secret_pw():
    try:
        return st.secrets["scorekeeper"]["password"]
    except Exception:
        return None


# ===================================================================== practice mode + password
# Practice mode runs the Scorekeeper on a private in-memory copy of the data (see cbl/data.py), so test
# series never reach MongoDB. Anyone can try it without the password; leaving throws the copy away.
def reset_entry():
    for k in [k for k in ss if k.startswith(("sk_", "vt_")) and k not in ("sk_auth", "sk_admin")]:   # the admin tab stays where it was
        del ss[k]


def cb_practice(on):
    if on:
        data.start_practice()
    else:
        data.stop_practice()
    reset_entry()


PRACTICE = bool(ss.get("practice")) and "practice_db" in ss
ts = data.titles()
cur = data.current_title()
ui.html(ui.eyebrow(f"{ts.get(cur, {}).get('name', '')} · Data Entry") + ui.h1("Scorekeeper", 60))
pw = secret_pw()
if not ss.get("sk_auth") and pw is None and is_preview():
    ss.sk_auth = True
if not ss.get("sk_auth") and not PRACTICE:
    ui.html("<div style='height:40px'></div>")
    _, mid, _ = st.columns([0.0001, 1.3, 1])
    with mid:
        if pw is None:
            ui.html(ui.empty_box("Scorekeeper Is Locked", "Add a password under [scorekeeper] in the app's secrets to use this page."))
        else:
            with st.form("sk_login"):
                got = st.text_input("Password", type="password")
                if st.form_submit_button("Unlock", type="primary"):
                    if hmac.compare_digest(got.encode(), str(pw).encode()):
                        ss.sk_auth = True
                        st.rerun()
                    st.error("That password didn't match.")
        ui.html(f"<div class='cb-fig' style='margin-top:32px; padding:16px 18px; background:{ui.PANEL}; border-left:3px solid {ui.INK}'>"
                "<div style='font-size:20px'>Just Testing?</div>"
                f"<p style='margin:6px 0 0; font-size:14px; line-height:1.55; color:{ui.SLATE}'>Practice mode runs the whole Scorekeeper on a private copy "
                "of the data: set up a series, enter maps, end it, even change Season Settings. Nothing is saved to the database, "
                "and the copy is thrown away when you leave.</p></div>")
        st.button("Try Practice Mode", width="stretch", on_click=cb_practice, args=(True,))
    st.stop()

if PRACTICE:
    c1, c2 = st.columns([3, 1], vertical_alignment="center")
    with c1:
        ui.html(f"<div style='margin-top:16px; padding:10px 12px; background:{ui.mix(ui.BG, ui.BLUE, 0.15)}; border:1px solid {ui.BLUE}; font-size:14px; line-height:1.5'>"
                "<b style='font-weight:600'>Practice Mode</b> · a private copy of the data. Nothing here is saved to the database, "
                "and it's cleared when you leave.</div>")
    with c2:
        st.button("Leave Practice", width="stretch", on_click=cb_practice, args=(False,), key="practice_off")
else:
    if is_preview():
        ui.html(ui.note("Preview mode: there's no database connection, so anything entered here disappears when the app restarts.", 10, 13))
    with st.container(horizontal=True, gap="small"):
        st.button("Switch to Practice Mode", type="tertiary", on_click=cb_practice, args=(True,), key="practice_on")
        if pw is not None and st.button("Log Out", type="tertiary", key="logout"):
            ss.sk_auth = False; reset_entry(); st.rerun()


def docs():
    return data.load_docs()


def series_doc(sid):
    return next((s for s in docs()["series"] if s["_id"] == sid), None)


def series_maps(sid):
    return sorted([m for m in docs()["matches"] if m["series_id"] == sid], key=lambda m: m["map_no"])


def team_str(t):
    return " · ".join(t)


def all_players():
    n = data.engine(None).pm.groupby("player").size() if not data.engine(None).empty else pd.Series(dtype=int)
    names = [p["_id"] for p in docs()["players"] if p.get("active", True)]
    return sorted(names, key=lambda p: (-int(n.get(p, 0)), p))


def sq(side, s=10):
    return ui.swatch(ui.INK if side == "A" else ui.BLUE, s, s)


def pips(n, won, side):
    col = ui.INK if side == "A" else ui.BLUE
    return ("<span class='sk-pips'>" + "".join(f"<span class='sk-pip' style='{'background:' + col + '; border-color:' + col if j < won else ''}'></span>"
                                               for j in range(n)) + "</span>")


def thumb(m):
    src = ui.map_img(m) if m else ""
    return f"<img class='sk-thumb' src='{src}' alt=''>" if src else "<span class='sk-thumb sk-thumb0'></span>"


field = me.field


# step state
ss.setdefault("sk_step", "setup")
sid = ss.get("sk_sid")
if sid and not series_doc(sid):
    sid = ss.sk_sid = None; ss.sk_step = "setup"
step = ss.sk_step
idx = {"setup": 0, "maps": 1, "done": 2}[step]
rail = "".join(f"<li class='sk-rs {'done' if i < idx or step == 'done' and i == 2 else 'cur' if i == idx else ''}'>"
               f"<span class='sk-dot'>{'&#10003;' if i < idx or (step == 'done' and i == 2) else i + 1}</span><span class='sk-rl'>{l}</span></li>"
               for i, l in enumerate(["Set Up", "Maps", "Done"]))
ui.html(f"<ol class='sk-rail' aria-label='Progress'>{rail}</ol>")


# ===================================================================== ratings: who goes first in a veto
def favoured(A, B, title):
    """(side, chance, too close) from player ratings: this game's, falling back to all-time for anyone new."""
    R = {}
    for tid in (None, title):
        e = data.engine(tid)
        if not e.empty:
            R.update(e.ratings()[0])
    avg = lambda t: sum(R.get(p, 1500) for p in t) / max(len(t), 1)  # noqa: E731
    pa = 1 / (1 + 10 ** ((avg(B) - avg(A)) / RSCALE))
    side, p = ("A", pa) if pa >= 0.5 else ("B", 1 - pa)
    return side, p, p < CLOSE


# ===================================================================== STEP 1: setup
def setup():
    S = ss.setdefault("sk_setup", {})
    editing = S.get("edit_sid")
    open_series = [s for s in docs()["series"] if s.get("status") == "open"]
    if open_series and not editing:
        for s in open_series:
            c1, c2 = st.columns([3, 1], vertical_alignment="center")
            with c1:
                ui.html(f"<div class='cb-fig' style='padding:12px 14px; background:{ui.PANEL}; border:1px solid {ui.RULE}'><b style='font-weight:600'>"
                        f"{ts.get(s['title'], {}).get('short', s['title'])} Series {s['series_no']}</b> "
                        f"is still open · {team_str(s['team_a'])} vs {team_str(s['team_b'])}</div>")
            with c2:
                if st.button("Resume", key=f"res_{s['_id']}", width="stretch"):
                    ss.sk_sid = s["_id"]; ss.sk_step = "maps"; ss.pop("sk_draft", None); st.rerun()
        ui.html("<div style='height:16px'></div>")
    series_form(S, editing)
    if editing:
        return
    admin()


# A fragment: tapping a player, Change, Done, best of or a veto choice reruns only this section, not League Admin below.
# Start Series / Save Changes call st.rerun(scope="app"), which reloads the whole page.
@st.fragment
def series_form(S, editing):
    tids = [t for t in sorted(ts, key=lambda t: -ts[t].get("order", 0))]
    names = all_players()
    nplayed = len(series_maps(editing)) if editing else 0
    locked = nplayed > 0
    S.setdefault("title", cur); S.setdefault("date", dt.date.today()); S.setdefault("bo", 5)
    S.setdefault("a", []); S.setdefault("b", [])
    S.setdefault("maps_mode", "go")
    S.setdefault("vt", {"how": "rating", "flip": None, "first": None, "choices": [], "msg": ""})
    if "open" not in S:
        S["open"] = None if editing else ("teams" if not (S["a"] and S["b"]) else None)
    VT = S["vt"]

    def change(k):
        S["open"] = k

    def close():
        S["open"] = None

    def tap(side, p):
        mine, other = ("a", "b") if side == "A" else ("b", "a")
        if p in S[mine]:
            S[mine] = [x for x in S[mine] if x != p]
        else:
            S[mine] = S[mine] + [p]; S[other] = [x for x in S[other] if x != p]
        if VT["choices"] or VT["first"]:   # the veto names the teams, so it starts over
            VT.update(first=None, choices=[], flip=None, msg="Teams changed, so the veto started over.")

    def qhead(n, label, value=""):
        ui.html(f"<div class='sk-qh'><span class='sk-qn'>{n:02d}</span><span class='sk-ql'>{label}</span>"
                + (f"<div class='sk-qv'>{value}</div>" if value else "") + "</div>")

    def qrow_closed(n, key, label, value, can_change=True, note=None):
        with st.container(key=f"skq_{key}", horizontal=True, vertical_alignment="center", wrap=False):
            qhead(n, label, value + (f"<div style='font-size:12px; color:{ui.MUTED}; margin-top:2px'>{note}</div>" if note else ""))
            if can_change:
                st.space("stretch")
                st.button("Change", key=f"sk_chg_{key}", on_click=change, args=(key,))

    tcfg = ts[S["title"]]
    left, right = st.columns([1.4, 1], gap="large")
    with left:
        ui.html(f"<div role='heading' aria-level='2' class='sk-h'>{'Edit the Series' if editing else 'Set Up the Series'}</div><div style='height:14px'></div>")
        with st.container(key="skqs"):
            # 01 game and date
            dd0 = pd.Timestamp(S["date"])
            if S["open"] == "meta":
                with st.container(key="skq_meta_open"):
                    qhead(1, "Game and Date")
                    with st.container(key="skqi_meta"):
                        c1, c2 = st.columns(2)
                        with c1:
                            field(st.selectbox, "Game", "sk_s_title", S, "title", cur, options=tids, format_func=lambda t: ts[t]["name"], disabled=bool(editing))
                        with c2:
                            field(st.date_input, "Date", "sk_s_date", S, "date", dt.date.today(), format="YYYY-MM-DD")
                        st.button("Done", key="sk_done_meta", type="primary", on_click=close)
            else:
                qrow_closed(1, "meta", "Game and Date", f"{ts[S['title']]['name']} · {dd0.strftime('%b')} {dd0.day}, {dd0.year}")
            tcfg = ts[S["title"]]
            # 02 best of
            with st.container(key="skq_bo"):
                qhead(2, "Best of")
                with st.container(key="skqi_bo"):
                    before = S["bo"]
                    with st.container(key="skfull_bo"):
                        field(st.segmented_control, "Best of", "sk_s_bo", S, "bo", 5, options=[1, 3, 5, 7, 9], label_visibility="collapsed")
                    S["bo"] = S["bo"] or before or 5
                    if S["bo"] != before and VT["choices"]:
                        VT.update(choices=[], msg="Best of changed, so the veto started over.")
                    ui.html(ui.note(f"First to {int(S['bo']) // 2 + 1} map{'s' if int(S['bo']) > 1 else ''} wins the series.", 0, 12))
            # 03 teams
            if S["open"] == "teams" and not locked:
                with st.container(key="skq_teams_open"):
                    qhead(3, "Teams")
                    with st.container(key="skqi_teams"):
                        board = [p for p in names]
                        cols = st.columns(2, gap="medium")
                        for ci, chunk in enumerate((board[0::2], board[1::2])):   # read across: most maps first
                            with cols[ci]:
                                for j, p in enumerate(chunk):
                                    i = j * 2 + ci
                                    side = "A" if p in S["a"] else "B" if p in S["b"] else ""
                                    with st.container(key=f"skdb_{i}", horizontal=True, vertical_alignment="center", gap=None):
                                        ui.html(f"<span style='font-size:15px; font-weight:{600 if side else 400}; color:{ui.INK if side else ui.MUTED}'>{escape(p)}</span>")
                                        st.space("stretch")
                                        with st.container(key=f"skdbA_{i}", width="content"):
                                            st.button("A", key=f"sk_tA_{i}", type="primary" if side == "A" else "secondary", on_click=tap, args=("A", p))
                                        with st.container(key=f"skdbB_{i}", width="content"):
                                            st.button("B", key=f"sk_tB_{i}", type="primary" if side == "B" else "secondary", on_click=tap, args=("B", p))
                        out = len(board) - len(S["a"]) - len(S["b"])
                        ui.html(f"<div style='display:flex; gap:16px; flex-wrap:wrap; font-size:12px; color:{ui.MUTED}; margin-top:12px'>"
                                f"<span style='display:inline-flex; align-items:center; gap:6px'>{sq('A')}Team A · {len(S['a'])}</span>"
                                f"<span style='display:inline-flex; align-items:center; gap:6px'>{sq('B')}Team B · {len(S['b'])}</span>"
                                f"<span>{out} sitting out</span></div>"
                                + ui.note("Tap A or B to put someone on a team; tap it again to take them off. Nobody can be on both sides.", 6, 12))
                        st.button("Done With Teams", key="sk_done_teams", type="primary", on_click=close, disabled=not (S["a"] and S["b"]))
            else:
                tv = (f"<div style='display:grid; gap:6px'><span style='display:flex; align-items:center; gap:8px'>{sq('A')}{escape(team_str(S['a'])) or 'Pick Team A'}</span>"
                      f"<span style='display:flex; align-items:center; gap:8px'>{sq('B')}{escape(team_str(S['b'])) or 'Pick Team B'}</span></div>")
                qrow_closed(3, "teams", "Teams", tv, can_change=not locked, note="Teams are locked once maps are entered." if locked else None)
            # 04 maps: pick as you go, or plan with a veto
            X = None
            with st.container(key="skq_maps"):
                qhead(4, "Maps <span>· optional</span>")
                with st.container(key="skqi_maps"):
                    if locked:
                        ui.html(ui.note("Planned with a veto. The plan is locked once maps are entered." if S["maps_mode"] == "veto"
                                        else "Picked as you go.", 0, 13))
                        if S["maps_mode"] == "veto":
                            X = veto_state(S, tcfg)
                    else:
                        with st.container(key="skfull_maps"):
                            field(st.segmented_control, "Maps", "sk_s_maps", S, "maps_mode", "go", options=["go", "veto"], label_visibility="collapsed",
                                  format_func={"go": "Pick As We Go", "veto": "Plan With a Veto"}.get)
                        S["maps_mode"] = S["maps_mode"] or "go"
                        if S["maps_mode"] == "go":
                            ui.html("<p class='vt-note'>Maps are picked as you go. On the Maps step you can still say who picked each one.</p>")
                        elif not (S["a"] and S["b"]):
                            ui.html("<p class='vt-note'>Pick both teams first: the veto needs to know who's who.</p>")
                        else:
                            X = veto_ui(S, tcfg)
            # 05 public note
            with st.container(key="skq_note"):
                qhead(5, "Public Note <span>· optional</span>")
                with st.container(key="skqi_note"):
                    pub = field(st.text_input, "Public note", "sk_s_pub", S, "pub", "", placeholder="e.g. Series 15 decides the rivalry",
                                label_visibility="collapsed")
                    ui.html(ui.note("Shows under the series in the Series Log.", 0, 12))
        if editing and st.button("Cancel", key="sk_cancel_edit"):
            ss.pop("sk_setup", None); ss.sk_step = "maps"; st.rerun(scope="app")

    # ---- the slip
    title, date, bo = S["title"], S["date"], int(S["bo"] or 5)
    no = series_doc(editing)["series_no"] if editing else data.next_series_no(title)
    A, B = S["a"], S["b"]
    priv = S.get("priv") or None  # private notes are no longer entered here; an existing one is kept as is
    ok = len(A) > 0 and len(B) > 0
    fmt_now = f"{len(A)}v{len(B)}"
    even = len(A) == len(B)
    veto_on = S["maps_mode"] == "veto"
    ready = ok and (not veto_on or (X is not None and X["st"] is not None and X["st"].done) or (locked and veto_on))
    tshort = tcfg.get("short") or tcfg["name"]
    dd = pd.Timestamp(date)
    with right:
        ui.html("<div style='height:56px'></div>")
        with st.container(key="sk_slip"):
            head = (f"<div class='sk-sh'><span class='sk-lab'>{tshort} · Series {no} · {dd.strftime('%b')} {dd.day}</span>"
                    f"<span class='sk-tag'>Best of {bo}</span></div>")
            if veto_on and X is not None and not X.get("problem"):
                first = VT["first"]
                team = lambda side: (f"<div style='display:flex; align-items:center; gap:10px; font-size:16px; font-weight:500'>{sq(side, 12)}"  # noqa: E731
                                     f"<span style='min-width:0'>{escape(team_str(S['a' if side == 'A' else 'b'])) or 'Pick Team ' + side}</span>"
                                     + (f"<span class='sk-tag' style='margin-left:auto; font-size:11px'>Team {'A' if first == side else 'B'}</span>" if first else "")
                                     + "</div>")
                body = (f"<div style='padding:14px 18px 12px; display:grid; gap:10px; border-bottom:1px solid {ui.RULE}'>{team('A')}{team('B')}</div>"
                        f"<div style='padding:10px 18px 14px'>{plan_rows(X, tcfg, first)}</div>")
            else:
                tnames = lambda t, side: ("<div class='sk-team'>" + "".join(f"<span>{escape(p)}</span>" for p in t) + "</div>" if t  # noqa: E731
                                          else f"<div class='sk-team' style='color:{ui.MUTED}; font-weight:400'>Pick Team {side}</div>")
                size = (f"<span class='sk-tag'>{fmt_now}</span>" if even else f"<span class='sk-tag warn'>{fmt_now} · Uneven</span>") if ok else "<b>—</b>"
                body = (f"<div style='padding:18px 18px 4px'><div class='sk-lab' style='display:flex; align-items:center; gap:8px'>{sq('A')}Team A</div>{tnames(A, 'A')}"
                        f"<div class='sk-vs'>vs</div><div class='sk-lab' style='display:flex; align-items:center; gap:8px'>{sq('B')}Team B</div>{tnames(B, 'B')}</div>"
                        f"<div class='sk-det' style='padding:16px 18px 18px'><div><span>Format</span>{size}</div>"
                        f"<div><span>To Win</span><b>First to {bo // 2 + 1} map{'s' if bo > 1 else ''}</b></div>"
                        f"<div><span>Maps</span><b>Picked as you go</b></div>"
                        f"<div><span>Public Note</span><b style='{'' if S.get('pub') else 'color:' + ui.MUTED + '; font-weight:400'}'>{escape(S.get('pub') or 'None yet')}</b></div></div>")
            ui.html(head + body)
            with st.container(key="sk_slipfoot"):
                label = "Save Changes" if editing else (f"Start Series {no} · {fmt_now} · Best of {bo}" if ok else f"Start Series {no}")
                go = st.button(label, type="primary", disabled=not ready, width="stretch", key="sk_start")
                why = ("" if ready else "Pick both teams to start." if not ok else
                       "Fix the map pool first, or switch to Pick As We Go." if X is not None and X.get("problem") else
                       "Finish the veto, or switch to Pick As We Go, to start.")
                if why:
                    ui.html(ui.note(why, 0, 12))
                elif ok and not even:
                    ui.html(ui.note("Uneven teams are allowed; the tag stays on the series.", 0, 12))
    if go:
        fmt = f"{len(A)}v{len(B)}"
        saved_veto = None
        if veto_on and X is not None and X["st"] is not None and X["st"].done:
            saved_veto = {**V.to_sides(V.record(X["st"]), VT["first"]), "how": VT["how"]}
        if editing:
            data.update_series(editing, date=pd.Timestamp(date).date().isoformat(), best_of=int(bo), team_a=A, team_b=B, format=fmt,
                               public_note=pub or None, private_note=priv or None)
            if not locked:
                data.save_veto(editing, saved_veto)
            ss.sk_sid = editing
        else:
            ss.sk_sid = data.create_series(title, date, fmt, bo, A, B, pub, priv)
            if saved_veto:
                data.save_veto(ss.sk_sid, saved_veto)
        ss.pop("sk_setup", None); ss.sk_step = "maps"; ss.pop("sk_draft", None)
        for k in [k for k in ss if k.startswith("sk_s_")]:
            del ss[k]
        st.rerun(scope="app")


# ---------------------------------------------------------------- the veto
def veto_state(S, tcfg):
    """The plan and where the veto stands. A plan that no longer fits the pools starts over."""
    VT = S["vt"]; names = V.mode_names(tcfg)
    p = V.plan(int(S["bo"]), V.pools(tcfg), names)
    if p.problem:
        return {"p": p, "st": None, "problem": p.problem, "names": names}
    st_ = None
    if VT["first"]:
        try:
            st_ = V.replay(p, VT["choices"])
        except V.VetoError:
            VT.update(choices=[], msg="The map pool changed, so the veto started over.")
            st_ = V.replay(p, [])
    return {"p": p, "st": st_, "problem": None, "names": names}


def veto_ui(S, tcfg):
    VT = S["vt"]; X = veto_state(S, tcfg); MN = X["names"]
    tn = {"A": team_str(S["a"]), "B": team_str(S["b"])}
    other = lambda x: "B" if x == "A" else "A"  # noqa: E731
    role_side = lambda r: VT["first"] if r == "A" else other(VT["first"])  # noqa: E731
    msg = VT.get("msg")
    VT["msg"] = ""
    if msg:
        ui.html(f"<div class='vt-msg'>{escape(msg)}</div>")
    if X["problem"]:
        with st.container(key="vt_card"):
            ui.html(f"<div class='vt-prompt'>This Veto Can't Run</div><p class='vt-note'>{escape(X['problem'])}</p>")
        return X

    def setv(**kw):
        VT.update(**kw)

    if not VT["first"]:
        side, pct, close = favoured(S["a"], S["b"], S["title"])
        chooser = side if VT["how"] == "rating" and not close else VT["flip"] if VT["how"] == "coin" else None
        with st.container(key="vt_card"):
            ui.html("<div class='vt-prompt'>Who Goes First?</div><p class='vt-note' style='margin-top:4px'>The Higher-Rated Side, or the Coin Flip "
                    "Winner, Chooses Team A or Team B.</p>")
            with st.container(key="skfull_vthow"):
                how = st.segmented_control("How", ["rating", "coin"], default=VT["how"], key="vt_how", label_visibility="collapsed",
                                           format_func={"rating": "By Rating", "coin": "Coin Flip"}.get) or VT["how"]
            if how != VT["how"]:
                VT.update(how=how, first=None, choices=[]); st.rerun(scope="fragment")
            if VT["how"] == "rating":
                if close:
                    ui.html(f"<p class='vt-note'>Ratings Have This One Too Close to Call ({round(pct * 100)}%), So Flip a Coin.</p>")
                else:
                    ui.html(f"<p class='vt-line'>{sq(side)}<b>{escape(tn[side])}</b> Are Favoured, {round(pct * 100)}% From Player Ratings, So They Choose.</p>")
            else:
                if VT["flip"]:
                    with st.container(horizontal=True, vertical_alignment="center", gap="small"):
                        ui.html(f"<p class='vt-line' style='margin:0'>{sq(VT['flip'])}<b>{escape(tn[VT['flip']])}</b> Win the Flip, So They Choose.</p>")
                        st.button("Flip Again", type="tertiary", key="vt_reflip", on_click=lambda: setv(flip=random.choice("AB")))
                else:
                    st.button("Flip a Coin", key="vt_flip", on_click=lambda: setv(flip=random.choice("AB")))
            if chooser:
                steps = X["p"].steps; picks = {"A": sorted(s.map_no for s in steps if s.action == "pick" and s.team == "A"),
                                               "B": sorted(s.map_no for s in steps if s.action == "pick" and s.team == "B")}
                mp = lambda a: ("Maps " if len(a) > 1 else "Map ") + (a[0].__str__() if len(a) == 1 else ", ".join(map(str, a[:-1])) + f" and {a[-1]}")  # noqa: E731
                expl = (["Team A: First Ban, and Picks Map 1.", "Team B: Second Ban, and Chooses the Side."] if int(S["bo"]) == 1 else
                        [f"Team A: First Hardpoint Ban, and Picks {mp(picks['A'])}.", f"Team B: First SnD Ban, and Picks {mp(picks['B'])}."])
                ui.html(f"<div class='vt-line' style='margin-top:16px'>{sq(chooser)}<b>{escape(tn[chooser])}</b> Choose:</div>")
                with st.container(horizontal=True, gap="small", key="vt_ab"):
                    st.button("Team A", key="vt_tA", on_click=lambda: setv(first=chooser, choices=[]), width="stretch")
                    st.button("Team B", key="vt_tB", on_click=lambda: setv(first=other(chooser), choices=[]), width="stretch")
                ui.html(f"<p class='vt-note'>{expl[0]}<br>{expl[1]}</p>")
        return X

    # the chooser is settled: who is Team A in the veto
    with st.container(horizontal=True, vertical_alignment="center", gap="small"):
        ui.html(f"<div class='vt-line' style='margin:0'>{sq(VT['first'])}<b>{escape(tn[VT['first']])}</b> Are Team A · "
                f"{'By Rating' if VT['how'] == 'rating' else 'Coin Flip'}</div>")
        st.button("Change", type="tertiary", key="vt_refirst", on_click=lambda: setv(first=None, choices=[]))
    st_, p = X["st"], X["p"]

    def last_line():
        i = st_.i - 1
        while i >= 0 and i in st_.auto:
            i -= 1
        if i < 0:
            return ""
        s = p.steps[i]; c = VT["choices"][-1] if VT["choices"] else ""; T = tn[role_side(s.team)]
        t = (f"{T} Banned {c}" if s.action == "ban" else (f"{T} Skipped the Side on Map {s.map_no}" if c == V.SKIP else f"{T} Took {SIDE_LABEL[c]} on Map {s.map_no}")
             if s.action == "side" else f"{T} Picked {c} for Map {s.map_no}")
        auto = "".join(f" Map {p.steps[k].map_no} Is {st_.slots[p.steps[k].map_no].map}, the {MN[p.steps[k].mode]} Map Left Over." for k in st_.auto if k > i)
        return f"<div class='vt-last'>Last: {escape(t)}.{escape(auto)}</div>"

    def pick(v):
        VT["choices"] = VT["choices"] + [v]

    def undo():
        if VT["choices"]:
            VT["choices"] = VT["choices"][:-1]
        else:
            VT["first"] = None

    with st.container(key="vt_card"):
        if st_.done:
            ui.html(f"<div class='vt-prompt'><span class='vt-ok'>&#10003;</span><span>Veto Complete</span></div>"
                    f"<p class='vt-note' style='font-size:14px'>{int(S['bo'])} map{'s' if int(S['bo']) > 1 else ''} planned. They fill in on the Maps step, "
                    "and any map can still be changed there if plans change.</p>")
            with st.container(horizontal=True, gap="small"):
                st.button("Undo Last Step", key="vt_undo", on_click=undo)
                st.button("Redo the Veto", key="vt_restart", on_click=lambda: setv(choices=[], first=None))
            ui.html(last_line())
            return X
        s = st_.step; side = role_side(s.team); opts = st_.options(); n, tot = st_.i + 1, len(p.steps)
        with st.container(horizontal=True, vertical_alignment="center", gap="small"):
            ui.html(f"<span class='sk-lab'>Step {n} of {tot}</span>")
            st.space("stretch")
            st.button("Undo", key="vt_undo", on_click=undo)
            st.button("Start Over", key="vt_restart", on_click=lambda: setv(choices=[], first=None))
        if s.action == "ban":
            prompt, sub = f"Ban a {MN[s.mode]} Map", f"{len(opts)} Map{'s' if len(opts) != 1 else ''} Left"
        elif s.action == "pick":
            prompt, sub = f"Pick Map {s.map_no}", f"{MN[s.mode]} · {len(opts)} Map{'s' if len(opts) != 1 else ''} Left"
        elif s.action == "last":
            prompt, sub = f"Pick Map {s.map_no} From the Maps Left", f"{MN[s.mode]} · The Last {MN[s.mode]} Map"
        else:
            prompt, sub = f"Choose a Side on Map {s.map_no}", f"{MN[s.mode]} · {st_.slots[s.map_no].map}"
        notes = ""
        for x in p.notes:   # e.g. "Hijack has 3 maps, so Team B's ban is skipped." with the team's names
            if x.startswith(MN[s.mode] + " "):
                for r in "AB":
                    x = x.replace(f"Team {r}'s", f"{tn[role_side(r)]}'s")
                notes += f"<p class='vt-note'>{escape(x)}</p>"
        ui.html(f"<div class='vt-bar'><i style='width:{100 * st_.i / tot:.1f}%'></i></div>"
                f"<div class='vt-who'>{sq(side)}Team {s.team} · {escape(tn[side])}</div><div class='vt-prompt'>{prompt}</div><div class='vt-sub'>{escape(sub)}</div>{notes}")
        if s.action == "side":
            m = st_.slots[s.map_no].map
            c1, c2 = st.columns([1, 1.6], vertical_alignment="center")
            with c1:
                ui.html(ui.img_tag(m))
            with c2:
                with st.container(horizontal=True, gap="small", key="vt_sides"):
                    for o in V.SIDES[s.mode]:
                        st.button(SIDE_LABEL[o], key=f"vt_side_{o}", on_click=pick, args=(o,))
                    st.button("Skip", type="tertiary", key="vt_side_skip", on_click=pick, args=(V.SKIP,))
        else:
            pool = p.pools[s.mode]
            with st.container(horizontal=True, wrap=True, gap="small", key="sktg_vt"):
                for m in pool:
                    open_ = m in opts; tag, who = "", None
                    for team_, bm in st_.bans[s.mode]:
                        if bm == m:
                            tag, who = "Banned", role_side(team_)
                    for sl in st_.slots.values():
                        if sl.mode == s.mode and sl.map == m:
                            tag, who = f"Map {sl.map_no}", (None if sl.by == "left" else role_side(sl.by))
                    with st.container(gap=None, key=f"skmap_vt_{m.replace(' ', '_')}"):
                        ui.html(f"<div class='vt-tile{'' if open_ else ' used'}'>{ui.img_tag(m)}<span class='vt-n'>{escape(m)}</span>"
                                + (f"<span class='vt-tag'>{sq(who, 8) if who else ''}{tag}</span>" if tag else "") + "</div>")
                        st.button(m, key=f"vt_pick_{m}", on_click=pick, args=(m,), disabled=not open_, width="stretch")
        ui.html(last_line())
    return X


def plan_rows(X, tcfg, first):
    """The slip's Map Plan while the veto runs (sides are the series' own: first = the side that is the veto's Team A)."""
    MN = X["names"]; st_ = X["st"]
    role_side = lambda r: first if r == "A" else ("B" if first == "A" else "A")  # noqa: E731
    order = V.ORDER.get(X["p"].best_of, [])
    cur_ = st_.step if st_ is not None and not st_.done else None
    rows = ""
    for k, m in enumerate(order):
        sl = st_.slots[k + 1] if st_ is not None else None
        tags = ""
        if sl and sl.map:
            tags += f"<span class='sk-st'>{'Left Over' if sl.by == 'left' else sq(role_side(sl.by), 8) + 'Pick'}</span>"
        if sl and sl.side:
            tags += f"<span class='sk-st'>{sq(role_side(sl.side_by), 8)}{SIDE_LABEL[sl.side]}</span>"
        on = cur_ is not None and cur_.map_no == k + 1
        rows += (f"<div class='sk-row{' cur' if on else ''}{'' if sl and sl.map else ' empty'}'><span class='sk-mn'>{k + 1}</span><div style='min-width:0'>"
                 f"<div class='sk-rm'>{MN[m]} · {'<b>' + escape(sl.map) + '</b>' if sl and sl.map else '—'}</div><div class='sk-rt'>{tags}</div></div>"
                 f"{thumb(sl.map if sl else None)}</div>")
    bans = ""
    if st_ is not None:
        for m in (V.HP, V.SND, V.OBJ):
            b = st_.bans.get(m, [])
            if b:
                bans += (f"<div class='sk-ban'><span>{MN[m]}</span>" + "".join(f"<span style='display:inline-flex; align-items:center; gap:5px'>{sq(role_side(t), 8)}{escape(x)}</span>"
                                                                                for t, x in b) + "</div>")
    return (f"<div class='sk-lab' style='margin:4px 0 6px'>Map Plan</div>{rows}"
            + (f"<div class='sk-lab' style='margin:16px 0 4px'>Bans</div>{bans}" if bans else ""))


# ---------------------------------------------------------------- league admin: players, Season Settings, backup
def admin():
    ui.html("<div style='height:56px'></div><div role='heading' aria-level='2' class='sk-h' style='font-size:26px'>League Admin</div><div style='height:8px'></div>")
    tab = ui.tabs("sk_admin", ["players", "settings", "backup"], {"players": "Players", "settings": "Season Settings", "backup": "Backup"})
    ui.html("<div style='height:8px'></div>")
    if tab == "players":
        roster()
    elif tab == "settings":
        settings()
    else:
        ui.html(f"<p style='font-size:14px; line-height:1.55; margin:0 0 14px; max-width:520px'>Every series, map and player stat in one CSV, for safekeeping or a spreadsheet.</p>")
        st.download_button("Download Full Backup (CSV)", data.backup_csv(), f"cb_league_backup_{dt.date.today().isoformat()}.csv", "text/csv")


def roster():
    pls = {p["_id"]: p for p in docs()["players"]}
    with st.container(key="skroster", gap=None):
        for name in all_players():
            p = pls[name]; tags = [g["tag"] for g in p.get("gamertags", [])]
            tag_txt = (tags[-1] + (f" (was {', '.join(tags[:-1])})" if len(tags) > 1 else "")) if tags else "No gamertag yet"
            with st.container(key=f"skpl_{name}", horizontal=True, vertical_alignment="center", wrap=False):
                ui.html(f"<div style='display:grid; grid-template-columns:minmax(0,140px) minmax(0,1fr); gap:4px 12px; align-items:center' class='sk-plr'>"
                        f"<span style='font-size:15px; font-weight:500'>{escape(name)}</span><span {'data-sc ' if tags else ''}style='font-size:13px; color:{ui.MUTED}'>{escape(tag_txt)}</span></div>")
                st.space("stretch")
                with st.popover("Add Gamertag" if not tags else "Gamertags"):
                    for i, g in enumerate(reversed(p.get("gamertags", []))):
                        ui.html(f"<div style='display:flex; justify-content:space-between; font-size:14px; padding:4px 0'><span>{escape(g['tag'])}</span>"
                                f"<span style='color:{ui.MUTED}'>{'current' if i == 0 else 'since ' + g.get('since', '')}</span></div>")
                    nt = st.text_input("Add a New Gamertag", key=f"sk_tag_{name}", placeholder="New Gamertag")
                    if st.button("Add Gamertag", key=f"sk_tagb_{name}", disabled=not nt.strip()):
                        data.add_gamertag(name, nt); st.rerun()
                    ui.html(ui.note("Old tags stay on file so past games and scoreboard photos still match. The app always shows the name, not the tag.", 4, 12))
    ui.html(f"<style>[class*='st-key-skpl_'] {{ border-bottom: 1px solid {ui.RULE}; }}</style>" + ui.label("Add a Player", margin_top=22) + "<div style='height:8px'></div>")
    c1, c2, c3 = st.columns([1, 1, 0.6], vertical_alignment="bottom")
    with c1:
        nm = st.text_input("Name", key="sk_new_name", placeholder="Name")
    with c2:
        gt = st.text_input("Gamertag", key="sk_new_tag", placeholder="Their In-Game Name")
    nm = nm.strip()
    clash = [p for p in pls if p.lower() == nm.lower()] if nm else []
    close = difflib.get_close_matches(nm, list(pls), n=2, cutoff=0.75) if nm and not clash else []
    with c3:
        add = st.button("Add Player", disabled=not nm or bool(clash), width="stretch")
    if clash:
        st.warning(f"{clash[0]} is already on the list.")
    elif close:
        ui.html(ui.note(f"Close to {' and '.join(close)}. If that's the same person, use the existing name so their stats don't split.", 4, 13))
    if add:
        data.add_player(nm, gt or None)
        for k in ("sk_new_name", "sk_new_tag"):
            ss.pop(k, None)
        st.rerun()


def settings():
    ui.html(ui.note("Changes apply from the day you save them, so earlier maps keep the rules they were played under.", 0, 13) + "<div style='height:10px'></div>")
    tids = [t for t in sorted(ts, key=lambda t: -ts[t].get("order", 0))]
    c1, c2 = st.columns([1.4, 1], vertical_alignment="bottom")
    with c1:
        tid = st.selectbox("Title", tids, key="sk_set_title", format_func=lambda t: ts[t]["name"] + f" ({ts[t]['year']})" + (" · current" if ts[t].get("current") else ""))
    drafts = ss.setdefault("sk_set_drafts", {})
    if tid not in drafts:
        drafts[tid] = {"doc": copy.deepcopy(ts[tid]), "log": []}
    D = drafts[tid]; doc = D["doc"]; modes = doc.setdefault("modes", {})
    with c2:
        if not ts[tid].get("current"):
            if st.button(f"Make {ts[tid]['name']} the Current Title", key=f"sk_cur_{tid}", width="stretch"):
                for o in ts.values():
                    if o.get("current") and o["_id"] != tid:
                        data.save_title({**o, "current": False}, f"{ts[tid]['name']} is now the current title")
                data.save_title({**ts[tid], "current": True}, "Made the current title")
                drafts.pop(tid, None); st.rerun()
    if not ts[tid].get("current"):
        ui.html(ui.note("The current title is the one the app opens on and the Scorekeeper enters games for by default.", 4, 12))
    e = data.engine(tid)
    mc = e.maps.groupby("mode").size() if not e.empty else pd.Series(dtype=int)
    ui.html(ui.label("Modes", margin_top=22))
    for k, m in modes.items():
        off = not m.get("active", True)
        n = int(mc.get(k, 0))
        if off:
            sub = "Retired · stats kept" if n else f"Not in {doc['name']}"
        elif doc.get("calibrated", True) and not m.get("borrow_mode"):
            sub = f"{n} maps · calibrated"
        else:
            src = MODEN.get(m.get("borrow_mode", k)) if m.get("borrow_mode") else ts.get(doc.get("borrow_from"), {}).get("name", "last season")
            sub = f"{n} maps · {'borrowing ' + src if m.get('borrow_mode') else 'using ' + src} values until {doc.get('provisional_maps', 8)} maps"
        prov = (not off) and n < doc.get("provisional_maps", 8) and (not doc.get("calibrated", True) or m.get("borrow_mode"))
        c1, c2 = st.columns([4, 1], vertical_alignment="center")
        with c1:
            ui.html(f"<div style='padding:4px 0; opacity:{0.6 if off else 1}'><div style='font-size:15px; font-weight:600'>{m.get('name', k)}"
                    f"{ui.tagbox('Provisional', ui.BLUE, ui.BLUE) if prov else ''}</div><div style='font-size:12px; color:{ui.MUTED}'>{sub}</div></div>")
        with c2:
            if st.button("Bring Back" if off else "Retire", key=f"sk_mode_{tid}_{k}", width="stretch"):
                m["active"] = off
                D["log"].append(f"{'Brought back' if off else 'Retired'} {m.get('name', k)}")
                st.rerun()
    with st.popover("Add a Mode"):
        nmn = st.text_input("Mode Name", key=f"sk_nm_{tid}", placeholder="e.g. Hijack")
        code = st.text_input("Short Code", key=f"sk_nc_{tid}", placeholder="e.g. HJ", max_chars=4)
        lab = st.text_input("Score Label", key=f"sk_nl_{tid}", placeholder="e.g. Points")
        bor = st.selectbox("Borrow MAR Values From", [k for k in modes if k in CONV], key=f"sk_nb_{tid}", format_func=MODEN.get)
        if st.button("Add Mode", disabled=not (nmn.strip() and code.strip())):
            c = code.strip().upper()
            modes[c] = {"name": nmn.strip(), "short": nmn.strip(), "score_label": lab.strip() or "Score", "win_score": None, "stats": [],
                        "maps": [], "active": True, "borrow_mode": bor}
            MODEN.setdefault(c, nmn.strip()); SHORT.setdefault(c, nmn.strip())
            D["log"].append(f"Added {nmn.strip()} (Provisional, borrowing {MODEN[bor]} values)")
            st.rerun()
    ui.html(ui.note(f"A new mode borrows the closest mode's MAR values and shows a Provisional tag until it has {doc.get('provisional_maps', 8)} maps. "
                    "Retired modes keep their stats and drop out of the map pool and map entry.", 4, 12))

    active = [k for k, m in modes.items() if m.get("active", True)]
    if not active:
        return
    ui.html(ui.label("Map Pool", margin_top=24) + "<div style='height:8px'></div>")
    sm = st.segmented_control("Pool Mode", active, default=active[0], key=f"sk_pm_{tid}", label_visibility="collapsed",
                              format_func=lambda k: modes[k].get("short") or MODEN.get(k, k)) or active[0]
    maps = modes[sm].setdefault("maps", [])
    if not maps:
        ui.html(ui.note(f"No {modes[sm].get('short', sm)} maps for {doc['name']} yet. Add the first one below.", 4, 13))
    for i, mp in enumerate(maps):
        ret = mp.get("status") == "retired"
        c1, c2 = st.columns([4, 1], vertical_alignment="center")
        with c1:
            since = "Retired · stays in every stat" if ret else ("In the pool" + (f" · added {mp['since']}" if mp.get("since") else f" · {doc['name']}"))
            ui.html(f"<div style='padding:4px 0'><div style='font-size:15px; font-weight:500; color:{ui.MUTED if ret else ui.INK}'>{mp['name']}</div>"
                    f"<div style='font-size:12px; color:{ui.MUTED}'>{since}</div></div>")
        with c2:
            if st.button("Bring Back" if ret else "Retire", key=f"sk_map_{tid}_{sm}_{i}", width="stretch"):
                mp["status"] = "active" if ret else "retired"
                D["log"].append(f"{'Brought back' if ret else 'Retired'} {mp['name']} ({modes[sm].get('short', sm)})")
                st.rerun()
    c1, c2 = st.columns([4, 1], vertical_alignment="bottom")
    with c1:
        newmap = st.text_input("Add a Map to This Mode", key=f"sk_addmap_{tid}_{sm}", placeholder="Map Name")
    with c2:
        if st.button("Add Map", key=f"sk_addmapb_{tid}_{sm}", disabled=not newmap.strip(), width="stretch"):
            nmx = newmap.strip().title()
            if any(m["name"].lower() == nmx.lower() for m in maps):
                st.warning(f"{nmx} is already in the pool.")
            else:
                maps.append({"name": nmx, "status": "active", "since": dt.date.today().isoformat()})
                D["log"].append(f"Added {nmx} ({modes[sm].get('short', sm)})")
                ss.pop(f"sk_addmap_{tid}_{sm}", None)
                st.rerun()
    ui.html(ui.note("Retired maps stay in every stat and still show (marked Retired) when you enter a map, for the odd night one gets played.", 4, 12))

    ui.html(ui.label(f"MAR Values · {modes[sm].get('short', sm)}", margin_top=24))
    vers = doc.setdefault("mar_versions", [{"from": "1900-01-01", **doc.get("mar", {})}])
    latest = copy.deepcopy(vers[-1]); D.setdefault("conv", latest)
    conv = D["conv"]; cm = conv.setdefault("modes", {}).setdefault(sm, {})
    fields = CONV.get(sm, [])
    if not fields:
        ui.html(ui.note(f"{modes[sm].get('name', sm)} borrows {MODEN.get(modes[sm].get('borrow_mode', 'OVL'))} values. Its own objective stat gets a value once "
                        "the scoreboard is known.", 4, 13))
    cols = st.columns(max(len(fields) + 1, 2))
    for i, (k, lab) in enumerate(fields):
        with cols[i]:
            default = cm.get(k, (ts.get(doc.get("borrow_from"), {}).get("mar", {}).get("modes", {}).get(sm, {}) or {}).get(k, 0.0))
            cm[k] = st.number_input(lab, value=float(default), step=0.25, key=f"sk_cv_{tid}_{sm}_{k}")
    with cols[len(fields)]:
        conv["assist"] = st.number_input("Assist (Kills)", value=float(conv.get("assist", 0.25)), step=0.05, key=f"sk_cv_{tid}_assist")
    ui.html(ui.label("Team Sizes", margin_top=20) + "<div style='display:flex; gap:6px; margin-top:8px'>"
            + "".join(f"<span style='font-size:13px; padding:3px 10px; background:{ui.INK}; color:{ui.BG}'>{z}</span>" for z in doc.get("team_sizes", ["3v3"]))
            + "</div>" + ui.note("MAR adjusts objective stats and kills-per-win for 4v4 automatically.", 6, 12))
    log = sorted([x for x in docs()["settings_log"] if x["title"] == tid], key=lambda x: x["date"], reverse=True)
    rows = "".join(f"<div style='display:grid; grid-template-columns:90px minmax(0,1fr); gap:10px; padding:7px 0; border-bottom:1px solid {ui.RULE}; font-size:13px'>"
                   f"<span style='color:{ui.MUTED}'>{pd.Timestamp(x['date']).strftime('%b')} {pd.Timestamp(x['date']).day}</span><span>{x['text']}</span></div>" for x in log)
    ui.html(ui.label("Change History", margin_top=20) + f"<div style='margin-top:6px'>{rows}</div>")
    changed_conv = {k: v for k, v in conv.items() if k != "from"} != {k: v for k, v in vers[-1].items() if k != "from"}
    pending = D["log"] + (["Changed MAR conversions"] if changed_conv else [])
    if pending:
        ui.html(ui.note("Unsaved: " + "; ".join(pending) + ".", 10, 13))
    if st.button("Save Settings", type="primary", disabled=not pending, key=f"sk_save_{tid}"):
        if changed_conv:
            today = dt.date.today().isoformat()
            nv = {**conv, "from": today}
            doc["mar_versions"] = [v for v in vers if v["from"] != today] + [nv]
        data.save_title(doc, "; ".join(pending))
        drafts.pop(tid, None)
        st.success("Settings saved.")
        st.rerun()


# ===================================================================== STEP 2: maps
def wins(sid):
    ms = series_maps(sid)
    return sum(m["winner"] == "A" for m in ms), sum(m["winner"] == "B" for m in ms)


def new_draft(s, match=None, map_no=None):
    prows = [r for r in docs()["player_matches"] if match and r["match_id"] == match["_id"]]
    tcfg = ts[s["title"]]
    return me.new_draft(tcfg, match, prows, plan=None if match else V.slot_for(s.get("veto"), map_no or 1, tcfg))


def slip_live(s, final=False, editable=True):
    """The slip once maps are being entered: the score, then the map plan (with a veto) or the maps entered."""
    tcfg = ts[s["title"]]; A, B = s["team_a"], s["team_b"]
    wa, wb = wins(s["_id"]); need = s["best_of"] // 2 + 1
    d0 = pd.Timestamp(s["date"]); ms = series_maps(s["_id"])
    big = lambda v: f"<span class='cbn' style='font-weight:300; font-size:48px; line-height:1'>{v}</span>"  # noqa: E731
    side = lambda t, side_, w, won: (f"<div style='padding:12px 0'><div style='display:flex; align-items:center; gap:8px; font-size:13px; font-weight:{600 if won else 400}'>"  # noqa: E731
                                     f"{sq(side_)}{escape(team_str(t))}</div><div style='display:flex; align-items:center; justify-content:space-between; gap:10px; "
                                     f"margin-top:6px'>{big(w)}{pips(need, w, side_)}</div></div>")
    head = (f"<div class='sk-sh'><span class='sk-lab'>{tcfg.get('short', s['title'])} · Series {s['series_no']} · {d0.strftime('%b')} {d0.day}</span>"
            f"<span class='sk-tag{' dark' if final else ''}'>{'Final' if final else 'Live'}</span></div>")
    score = (f"<div style='padding:6px 18px 14px'>{side(A, 'A', wa, wa > wb)}<div style='border-top:1px solid {ui.RULE}'></div>{side(B, 'B', wb, wb > wa)}</div>")
    veto = s.get("veto")
    vnames = V.mode_names(tcfg); code_of = V.codes(tcfg); vmode = {v: k for k, v in code_of.items()}
    with st.container(key="sk_slip"):
        ui.html(head + score + f"<div style='border-top:1px dashed {ui.RULE2}; padding:14px 18px 2px'><div class='sk-lab'>{'Map Plan' if veto else 'Maps Entered'}</div></div>")
        if veto:
            cmp_ = V.compare(veto, [{"map_no": m["map_no"], "mode": m["mode"], "map": m["map"]} for m in ms], s["best_of"], vmode)
            planned = {c["map_no"]: c for c in cmp_}
            nos = sorted(set(planned) | {m["map_no"] for m in ms})
        else:
            planned = {}; nos = [m["map_no"] for m in ms]
        by_no = {m["map_no"]: m for m in ms}
        entering = len(ms) + 1
        for n in nos:
            c = planned.get(n); m = by_no.get(n)
            tags = ""
            pb = (m or {}).get("picked_by") or (c and c["by"])
            if pb == "left":
                tags += "<span class='sk-st'>Left Over</span>"
            elif pb in ("A", "B"):
                tags += f"<span class='sk-st'>{sq(pb, 8)}Pick</span>"
            elif pb in ("agreed", "caster"):
                tags += f"<span class='sk-st'>{'Agreed' if pb == 'agreed' else 'Caster Pick'}</span>"
            if c and c.get("side") and (not m or c["status"] == "as_planned"):
                tags += f"<span class='sk-st'>{sq(c['side_by'], 8)}{SIDE_LABEL[c['side']]}</span>"
            if m:
                ln = f" · {ui.mmss(m['length_sec'])}" if m.get("length_sec") else ""
                line2 = f"{m['score_a']}–{m['score_b']}{ln} · {'A' if m['winner'] == 'A' else 'B'} Won{' · Partial' if m.get('board') == 'partial' else ''}"
                chg = (f" <span class='sk-chg'>Changed · Veto Had {escape(c['map'])}</span>" if c and c["status"] == "changed" else "")
                name = f"{SHORT.get(m['mode'], m['mode'])} · <b>{escape(m['map'])}</b>{chg}"
                cls = "sk-row"; img = m["map"]
            elif n == entering and not final:
                line2, name, cls, img = "Entering Now", f"{vnames[c['mode']]} · <b>{escape(c['map'])}</b>", "sk-row cur", c["map"]
            else:
                line2, name, cls, img = "Planned" if not final else "Not Played", f"{vnames[c['mode']]} · {escape(c['map'])}", "sk-row plan", c["map"]
            row = (f"<div class='{cls}' style='border-bottom:0'><span class='sk-mn'>{n}</span><div style='min-width:0'><div class='sk-rm'>{name}</div>"
                   f"<div class='sk-rt'>{tags}<span class='sk-st' style='color:{ui.MUTED}'>{line2}</span></div></div>{thumb(img)}</div>")
            with st.container(key=f"skrow_{n}", gap=None):
                ui.html(f"<div class='cb-rise' style='border-bottom:1px solid {ui.RULE}; animation-delay:{.15 + (n - 1) * .08:.2f}s'>{row}</div>")
                if m and editable and not final:
                    with st.container(horizontal=True, gap="small", horizontal_alignment="right"):
                        if st.button("Edit", key=f"sk_ed_{m['_id']}"):
                            ss.sk_draft = new_draft(s, m); st.rerun()
                        if n == len(ms) and st.button("Delete", key=f"sk_del_{m['_id']}"):
                            ss["sk_confirm_del"] = m["_id"]
                if m and ss.get("sk_confirm_del") == m["_id"]:
                    st.warning(f"Delete map {m['map_no']} ({m['map']})? Its player stats go too.")
                    a, b = st.columns(2)
                    if a.button("Yes, Delete", type="primary", key="sk_del_yes"):
                        data.delete_map(m["_id"]); ss.pop("sk_confirm_del"); ss.pop("sk_draft", None); st.rerun()
                    if b.button("Keep It", key="sk_del_no"):
                        ss.pop("sk_confirm_del"); st.rerun()
        if not nos:
            ui.html(f"<div style='padding:6px 18px 0; font-size:13px; color:{ui.MUTED}'>None yet.</div>")
        note = ("Planned maps that aren't played never count in any stat." if veto else
                "Only the latest map can be deleted. Edit opens any map again." if ms and not final else "")
        ui.html(f"<div style='padding:10px 18px 18px'>{ui.note(note, 0, 12) if note else ''}</div>")


def maps_step():
    s = series_doc(ss.sk_sid); tcfg = ts[s["title"]]
    A, B = s["team_a"], s["team_b"]
    wa, wb = wins(s["_id"]); need = s["best_of"] // 2 + 1
    over = wa >= need or wb >= need
    d0 = pd.Timestamp(s["date"])
    D = ss.get("sk_draft")
    ms = series_maps(s["_id"])
    editing = D is not None and D.get("match_id")
    with st.container(key="skgrid_late"):
        left, right = st.columns([1.4, 1], gap="large")
    with right:
        ui.html("<div style='height:56px'></div>")
        slip_live(s)
    with left:
        map_no = next((m["map_no"] for m in ms if D and m["_id"] == D.get("match_id")), len(ms) + 1)
        with st.container(horizontal=True, vertical_alignment="center"):
            ui.html(f"<div role='heading' aria-level='2' class='sk-h'>{'Series ' + str(s['series_no']) + ' Is Decided' if over and not editing else 'Map ' + str(map_no)}"
                    f"{' · Editing' if editing else ''}</div>")
            st.space("stretch")
            if st.button("Edit Setup", key="sk_edit_setup"):
                vt = s.get("veto")
                ss.sk_setup = {"edit_sid": s["_id"], "title": s["title"], "date": d0.date(), "bo": s["best_of"], "a": A, "b": B,
                               "pub": s.get("public_note") or "", "priv": s.get("private_note") or "",
                               "maps_mode": "veto" if vt else "go",
                               "vt": {"how": (vt or {}).get("how", "rating"), "flip": None, "first": (vt or {}).get("first"),
                                      "choices": list((vt or {}).get("choices", [])), "msg": ""}}
                for k in [k for k in ss if k.startswith("sk_s_")]:
                    del ss[k]
                ss.sk_step = "setup"; st.rerun()
        ui.html(f"<div style='font-size:13px; color:{ui.MUTED}; margin-top:4px'>{tcfg['short']} Series {s['series_no']} · {d0.strftime('%b')} {d0.day} · "
                f"Best of {s['best_of']} · {s['format']}</div>")
        if over and not editing:
            win = A if wa > wb else B
            ui.html(f"<div class='cb-fig' style='margin-top:16px; padding:16px; background:{ui.PANEL}; border:1px solid {ui.RULE}'><div style='font-size:18px; font-weight:600'>"
                    f"{escape(team_str(win))} Win {max(wa, wb)}–{min(wa, wb)}</div>"
                    + ui.note("Series MVP, standings, MAR and records update as soon as you finish.", 4, 13) + "</div><div style='height:12px'></div>")
            if st.button("Finish Series", type="primary", width="stretch"):
                data.update_series(s["_id"], status="closed", result_override=None)
                ss.sk_result = None; ss.sk_step = "done"; ss.pop("sk_draft", None); st.rerun()
            return
        if D is None:
            D = ss.sk_draft = new_draft(s, map_no=len(ms) + 1)
        entry(s, D, len(ms))
        if ms and not editing:
            ui.html(f"<div style='margin-top:28px; border-top:1px solid {ui.RULE}'></div>")
            if not ss.get("sk_end"):
                with st.container(horizontal=True, vertical_alignment="center"):
                    ui.html(f"<span style='font-size:13px; color:{ui.MUTED}'>Someone has to leave?</span>")
                    st.space("stretch")
                    if st.button("End Series Early", key="sk_end_btn"):
                        ss.sk_end = True; st.rerun()
            else:
                ui.html(f"<div class='cb-fig' style='margin-top:12px; padding:14px 16px; border:1px solid {ui.STEEL}'><div style='font-size:16px; font-weight:600'>"
                        f"End Series {s['series_no']} at {wa}–{wb}?</div>" + ui.note("The series gets an Ended Early tag. Maps already entered count as normal.", 4, 13) + "</div>")
                dflt = "A" if wa > wb else "B" if wb > wa else "N"
                opts = {"A": f"{team_str(A)} · " + (f"leading {wa}–{wb}" if wa > wb else f"score {wa}–{wb}"),
                        "B": f"{team_str(B)} · " + (f"leading {wb}–{wa}" if wb > wa else f"score {wb}–{wa}"),
                        "N": "No result · neither team gets the series"}
                pick = st.radio("Who Gets the Series?", list(opts), index=list(opts).index(dflt), format_func=opts.get, key="sk_end_pick")
                a, b = st.columns(2)
                if a.button("Keep Playing"):
                    ss.sk_end = False; st.rerun()
                if b.button("End Series", type="primary"):
                    data.update_series(s["_id"], status="closed", result_override=pick)
                    ss.sk_end = False; ss.sk_result = pick; ss.sk_step = "done"; ss.pop("sk_draft", None); st.rerun()


def entry(s, D, nsaved):
    map_no = next((m["map_no"] for m in series_maps(s["_id"]) if m["_id"] == D["match_id"]), nsaved + 1)
    tcfg = ts[s["title"]]

    def on_save(mode, map_name, sa, sb, ln, board, rows, match_id, extra=None):
        data.save_map(s, mode, map_name, sa, sb, ln, board, rows, match_id=match_id, extra=extra)
        ss.pop("sk_draft", None)

    played = tuple(m["map"] for m in series_maps(s["_id"]) if m["_id"] != D["match_id"])
    picks = {"A": team_str(s["team_a"]), "B": team_str(s["team_b"]), "agreed": "Agreed", "caster": "Caster Pick"}
    me.entry(me.Ctx(tcfg=tcfg, team_a=s["team_a"], team_b=s["team_b"], map_no=map_no, prefix="sk", on_save=on_save, played=played,
                    on_cancel=lambda: ss.pop("sk_draft", None), heading=False, pick_opts=picks,
                    plan=V.slot_for(s.get("veto"), map_no, tcfg)), D)


# ===================================================================== STEP 3: done
def done():
    s = series_doc(ss.sk_sid)
    wa, wb = wins(s["_id"]); A, B = s["team_a"], s["team_b"]
    res = ss.get("sk_result")
    if res == "N":
        line = f"Series ended early at {wa}–{wb} with no result"
        final = f"{wa}–{wb}"
    elif res in ("A", "B"):
        line = f"{team_str(A if res == 'A' else B)} take the series {wa if res == 'A' else wb}–{wb if res == 'A' else wa} (ended early)"
        final = f"{max(wa, wb)}–{min(wa, wb)}"
    else:
        line = f"{team_str(A if wa > wb else B)} win {max(wa, wb)}–{min(wa, wb)}"
        final = f"{max(wa, wb)}–{min(wa, wb)}"
    mv = data.engine(s["title"]).series_mvps().get(s["_id"])
    with st.container(key="skgrid_late"):
        left, right = st.columns([1.4, 1], gap="large")
    with right:
        ui.html("<div style='height:56px'></div>")
        slip_live(s, final=True)
    with left:
        cell = lambda v, lab, col=None: (f"<div style='padding:16px 0'><div class='cb-kpi-n cbn' style='font-weight:300; font-size:42px; line-height:1; white-space:nowrap; color:{col or ui.INK}'>{v}</div>"  # noqa: E731
                                         f"<div style='font-size:13px; color:{ui.MUTED}; margin-top:8px'>{lab}</div></div>")
        ui.html(f"<div role='heading' aria-level='2' class='sk-h'>Series {s['series_no']} Saved</div>"
                f"<p style='font-size:15px; line-height:1.55; margin:10px 0 0; max-width:520px'>{escape(line)}. It's in the Series Log now, and standings, "
                "MAR, rivalries and records include it.</p>"
                f"<div class='sk-donek' style='display:grid; grid-template-columns:repeat(3, minmax(0,1fr)); gap:12px; margin-top:28px; border-top:1px solid {ui.RULE}; "
                f"border-bottom:1px solid {ui.RULE}'>{cell(final, 'Final')}{cell(escape(mv[0]) if mv else '—', 'Series MVP')}"
                f"{cell(ui.sg(mv[1], 2) if mv else '—', 'MVP’s MAR', ui.BLUE)}</div><div style='height:24px'></div>"
                "<style>@media (max-width: 640px) { .sk-donek .cb-kpi-n { font-size: 28px !important; } }</style>")
        c1, _ = st.columns([1, 1.2])
        with c1:
            if st.button("Start Another Series", type="primary", width="stretch"):
                ss.sk_sid = None; ss.sk_step = "setup"; ss.pop("sk_result", None); ss.pop("sk_setup", None)
                for k in [k for k in ss if k.startswith("sk_s_")]:
                    del ss[k]
                st.rerun()


if step == "setup":
    setup()
elif step == "maps":
    maps_step()
else:
    done()