"""Scorekeeper: password-protected data entry, players and Season Settings."""
from __future__ import annotations

import copy
import datetime as dt
import difflib
import hmac

import pandas as pd
import streamlit as st

from cbl import data
from cbl.db import is_preview
from cbl.ui import map_entry as me, page, styles as ui

page.start("Scorekeeper")
# data entry lives in a narrow column (as in the mockup), with full-width controls that are easy to tap
ui.html(f"""<style>
[data-testid="stMainBlockContainer"] {{ max-width: 680px; }}
.st-key-sk_pick_A, .st-key-sk_pick_B {{ gap: 6px !important; }}
.st-key-sk_pick_A button, .st-key-sk_pick_B button {{ min-height: 44px; padding: 0 14px; }}
.st-key-sk_pick_A button[kind="primary"] {{ background: {ui.INK}; border-color: {ui.INK}; color: #F2F4F2; }}
.st-key-sk_pick_B button[kind="primary"] {{ background: {ui.BLUE}; border-color: {ui.BLUE}; color: #F2F4F2; }}
/* Streamlit greys out the page while a tap is processed; on quick taps that reads as a stutter, so keep it at full strength */
[data-testid="stMain"] [data-stale="true"] {{ opacity: 1 !important; transition: none !important; }}
.st-key-sk_ticket {{ background: {ui.PANEL}; border: 1px solid {ui.RULE}; padding: 20px 26px 22px !important; margin-top: 16px; }}
.st-key-sk_ticket [data-testid="stMarkdownContainer"] {{ margin-bottom: 0 !important; }}
@media (max-width: 640px) {{
  .st-key-sk_ticket {{ padding: 16px 16px 18px !important; }}
  .sk-tk-teams {{ grid-template-columns: minmax(0,1fr) !important; text-align: left !important; }}
  .sk-tk-teams > div {{ justify-content: flex-start !important; text-align: left !important; }}
  .sk-tk-teams .sk-tk-a {{ flex-direction: row-reverse; justify-content: flex-end !important; }}  /* square first on a phone; reversed, flex-end is the left edge */
}}
.st-key-skfull_bo button[data-variant="segmented_control"] {{ min-height: 40px !important; height: 40px; padding: 0 4px; }}
[class*="st-key-sk_step_"] {{ border-bottom: 1px solid {ui.RULE}; padding: 10px 0 !important; }}
[class*="st-key-sk_step_open_"] {{ padding: 16px 0 18px !important; border-bottom: 1px solid {ui.RULE}; }}
[class*="st-key-sk_step_"] [data-testid="stMarkdownContainer"], [class*="st-key-sk_step_"] [data-testid="stHtml"] {{ margin-bottom: 0 !important; }}
@media (max-width: 640px) {{
  [class*="st-key-sk_step_"]:not([class*="st-key-sk_step_open_"]) [data-testid="stHorizontalBlock"] {{ flex-wrap: nowrap !important; gap: 8px !important; }}
  [class*="st-key-sk_step_"]:not([class*="st-key-sk_step_open_"]) [data-testid="stColumn"] {{ min-width: 0 !important; width: auto !important; flex: 1 1 auto !important; }}
  [class*="st-key-sk_step_"]:not([class*="st-key-sk_step_open_"]) [data-testid="stColumn"]:first-child {{ flex: 0 0 auto !important; }}
  [class*="st-key-sk_step_"]:not([class*="st-key-sk_step_open_"]) [data-testid="stColumn"]:last-child {{ flex: 0 0 84px !important; }}
}}
</style>""" + me.css())
ss = st.session_state
MODEN = me.MODEN
SHORT = me.SHORT
CONV = {"HP": [("hill_sec_per_kill", "Hill time: seconds per kill")],
        "SND": [("plant", "Plant (kills)"), ("fb_margin", "First-blood margin (kills)")],
        "OVL": [("overload", "Overload (kills)"), ("carrier_kill", "Carrier kill (extra kills)"), ("kill_as_carrier", "Kill as carrier (kills)")]}


def secret_pw():
    try:
        return st.secrets["scorekeeper"]["password"]
    except Exception:
        return None


# ===================================================================== practice mode + password
# Practice mode runs the Scorekeeper on a private in-memory copy of the data (see cbl/data.py), so test
# series never reach MongoDB. Anyone can try it without the password; leaving throws the copy away.
def reset_entry():
    for k in [k for k in ss if k.startswith("sk_") and k != "sk_auth"]:
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
ui.html(ui.eyebrow(f"{ts.get(cur, {}).get('name', '')} · data entry") + ui.h1("Scorekeeper", 52))
pw = secret_pw()
if not ss.get("sk_auth") and pw is None and is_preview():
    ss.sk_auth = True
if not ss.get("sk_auth") and not PRACTICE:
    ui.html("<div style='height:48px'></div>")
    if pw is None:
        ui.html(ui.empty_box("Scorekeeper is locked", "Add a password under [scorekeeper] in the app's secrets to use this page."))
    else:
        with st.form("sk_login"):
            got = st.text_input("Password", type="password")
            if st.form_submit_button("Unlock", type="primary"):
                if hmac.compare_digest(got.encode(), str(pw).encode()):
                    ss.sk_auth = True
                    st.rerun()
                st.error("That password didn't match.")
    ui.html(f"<div style='margin-top:32px; padding:16px 18px; background:{ui.PANEL}; border-left:3px solid {ui.INK}'>"
            "<div style='font-size:20px'>Just testing?</div>"
            f"<p style='margin:6px 0 0; font-size:14px; line-height:1.55; color:{ui.SLATE}'>Practice mode runs the whole Scorekeeper on a private copy "
            "of the data: set up a series, enter maps, end it, even change Season Settings. Nothing is saved to the database, "
            "and the copy is thrown away when you leave.</p></div>")
    st.button("Try practice mode", width="stretch", on_click=cb_practice, args=(True,))
    st.stop()

ui.html("<div style='height:28px'></div>")
if PRACTICE:
    c1, c2 = st.columns([3, 1], vertical_alignment="center")
    with c1:
        ui.html(f"<div style='padding:10px 12px; background:{ui.mix(ui.BG, ui.BLUE, 0.15)}; border:1px solid {ui.BLUE}; font-size:14px; line-height:1.5'>"
                "<b style='font-weight:600'>Practice mode</b> · a private copy of the data. Nothing here is saved to the database, "
                "and it's cleared when you leave.</div>")
    with c2:
        st.button("Leave practice", width="stretch", on_click=cb_practice, args=(False,), key="practice_off")
else:
    if is_preview():
        ui.html(ui.note("Preview mode: there's no database connection, so anything entered here disappears when the app restarts.", 4, 13))
    with st.container(horizontal=True, gap="small"):
        st.button("Switch to practice mode", type="tertiary", on_click=cb_practice, args=(True,), key="practice_on")
        if pw is not None and st.button("Log out", type="tertiary", key="logout"):
            ss.sk_auth = False; reset_entry(); st.rerun()


def docs():
    return data.load_docs()


def series_doc(sid):
    return next((s for s in docs()["series"] if s["_id"] == sid), None)


def series_maps(sid):
    return sorted([m for m in docs()["matches"] if m["series_id"] == sid], key=lambda m: m["map_no"])


def team_str(t):
    return ", ".join(t)


def all_players():
    n = data.engine(None).pm.groupby("player").size() if not data.engine(None).empty else pd.Series(dtype=int)
    names = [p["_id"] for p in docs()["players"] if p.get("active", True)]
    return sorted(names, key=lambda p: (-int(n.get(p, 0)), p))


field = me.field


# step state
ss.setdefault("sk_step", "setup")
sid = ss.get("sk_sid")
if sid and not series_doc(sid):
    sid = ss.sk_sid = None; ss.sk_step = "setup"
step = ss.sk_step
idx = {"setup": 0, "maps": 1, "done": 2}[step]
bars = "".join(f"<li style='flex:1 1 0; list-style:none; border-top:3px solid {ui.INK if i <= idx else ui.RULE}; padding-top:8px; font-size:13px; "
               f"color:{ui.INK if i == idx else ui.MUTED}; font-weight:{600 if i == idx else 400}'>{i + 1}. {l}</li>"
               for i, l in enumerate(["Series setup", "Maps", "Done"]))
ui.html(f"<ol aria-label='Progress' style='display:flex; gap:8px; padding:0; margin:20px 0 8px'>{bars}</ol>")


# ===================================================================== STEP 1: setup
def setup():
    S = ss.setdefault("sk_setup", {})
    editing = S.get("edit_sid")
    open_series = [s for s in docs()["series"] if s.get("status") == "open"]
    if open_series and not editing:
        for s in open_series:
            c1, c2 = st.columns([3, 1], vertical_alignment="center")
            with c1:
                ui.html(f"<div style='padding:12px 14px; background:{ui.PANEL}'><b style='font-weight:600'>{ts.get(s['title'], {}).get('short', s['title'])} Series {s['series_no']}</b> "
                        f"is still open · {team_str(s['team_a'])} vs {team_str(s['team_b'])}</div>")
            with c2:
                if st.button("Resume", key=f"res_{s['_id']}", width="stretch"):
                    ss.sk_sid = s["_id"]; ss.sk_step = "maps"; ss.pop("sk_draft", None); st.rerun()
    series_form(S, editing)
    if editing and st.button("Cancel"):
        ss.pop("sk_setup", None); ss.sk_step = "maps"; st.rerun()
    if editing:
        return
    roster()
    settings()
    ui.html(f"<div style='border-top:1px solid {ui.RULE}; margin-top:32px; padding-top:16px; font-size:16px; font-weight:500'>Backup</div>")
    ui.html("<div style='height:8px'></div>")
    st.download_button("Download Full Backup (CSV)", data.backup_csv(), f"cb_league_backup_{dt.date.today().isoformat()}.csv", "text/csv")


# A fragment: tapping a player, Change, Done or best of reruns only this section, not the Players list, Season Settings
# or the backup file below it. Start Series / Save Changes call st.rerun(), which reloads the whole page as before.
@st.fragment
def series_form(S, editing):
    ui.html(ui.h2("Edit the Series" if editing else "Set Up the Series", margin_top=24, rule=False))
    # the matchup ticket: a live preview of the series, filled in after the controls below have run
    ticket = st.empty()
    tids = [t for t in sorted(ts, key=lambda t: -ts[t].get("order", 0))]
    names = all_players()
    locked = editing and len(series_maps(editing)) > 0
    S.setdefault("title", cur); S.setdefault("date", dt.date.today()); S.setdefault("bo", 5)
    S.setdefault("a", []); S.setdefault("b", [])
    # one question at a time: game and date, best of, Team A, Team B. Answered steps fold into a summary line with
    # Change. A new series starts on Team A (the first two come pre-answered); editing starts with everything folded.
    ORDER = ["meta", "bo", "a", "b"]
    if "open" not in S:
        S["open"] = None if editing else ("a" if not S["a"] else "b" if not S["b"] else None)

    def answered(k):
        return bool(S["a"]) if k == "a" else bool(S["b"]) if k == "b" else True

    def done(k):   # fold this step and open the next one still unanswered
        nxt = [x for x in ORDER[ORDER.index(k) + 1:] if not answered(x)]
        S["open"] = nxt[0] if nxt else None

    def change(k):
        S["open"] = k

    def tap(side, p):
        mine, other = ("a", "b") if side == "A" else ("b", "a")
        if p in S[mine]:
            S[mine] = [x for x in S[mine] if x != p]
        else:
            S[mine] = S[mine] + [p]; S[other] = [x for x in S[other] if x != p]

    LABEL = {"meta": "Game and Date", "bo": "Best Of", "a": "Team A", "b": "Team B"}

    def summary(k, value, can_change=True, note=None):
        with st.container(key=f"sk_step_{k}"):
            c1, c2, c3 = st.columns([1.45, 3, 0.9], vertical_alignment="center")
            ok_ = answered(k)
            mark = (f"<span style='display:inline-flex; width:18px; height:18px; align-items:center; justify-content:center; background:{ui.INK}; color:#F2F4F2; "
                    f"font-size:11px'>&#10003;</span>" if ok_ else f"<span style='display:inline-block; width:16px; height:16px; border:1px solid {ui.STEEL}'></span>")
            c1.html(f"<div style='display:flex; align-items:center; gap:10px; font-size:14px; font-weight:600'>{mark}{LABEL[k]}</div>")
            c2.html(f"<div style='font-size:15px; color:{ui.INK if ok_ else ui.MUTED}'>{value}</div>"
                    + (f"<div style='font-size:12px; color:{ui.MUTED}; margin-top:2px'>{note}</div>" if note else ""))
            if can_change:
                c3.button("Change" if ok_ else "Pick", key=f"sk_chg_{k}", on_click=change, args=(k,), width="stretch")

    def open_head(k, right=""):
        ui.html(f"<div style='display:flex; justify-content:space-between; align-items:baseline; margin-top:6px'>"
                f"<span style='display:inline-flex; align-items:center; gap:10px; font-size:15px; font-weight:600'>"
                f"<span style='display:inline-block; width:16px; height:16px; background:{ui.BLUE}'></span>{LABEL[k]}</span>"
                f"<span style='font-size:13px; color:{ui.MUTED}'>{right}</span></div>")

    for k in ORDER:
        is_open = S["open"] == k and not (locked and k in ("a", "b"))
        if k == "meta":
            dd0 = pd.Timestamp(S["date"])
            if is_open:
                with st.container(key="sk_step_open_meta"):
                    open_head(k)
                    c1, c2 = st.columns(2)
                    with c1:
                        field(st.selectbox, "Game", "sk_s_title", S, "title", cur, options=tids, format_func=lambda t: ts[t]["name"], disabled=bool(editing))
                    with c2:
                        field(st.date_input, "Date", "sk_s_date", S, "date", dt.date.today(), format="YYYY-MM-DD")
                    st.button("Done", key="sk_done_meta", type="primary", on_click=done, args=(k,))
            else:
                summary(k, f"{ts[S['title']]['name']} · {dd0.strftime('%b')} {dd0.day}, {dd0.year}")
        elif k == "bo":
            if is_open:
                with st.container(key="sk_step_open_bo"):
                    open_head(k, "maps needed to win: " + str(int(S["bo"] or 5) // 2 + 1))
                    with st.container(key="skfull_bo"):
                        field(st.segmented_control, "Best of", "sk_s_bo", S, "bo", 5, options=[1, 3, 5, 7, 9], label_visibility="collapsed")
                    S["bo"] = S["bo"] or 5
                    st.button("Done", key="sk_done_bo", type="primary", on_click=done, args=(k,))
            else:
                summary(k, f"Best of {S['bo']} · first to {int(S['bo']) // 2 + 1} maps")
        else:
            side, mine, other = ("A", "a", "b") if k == "a" else ("B", "b", "a")
            if is_open:
                with st.container(key=f"sk_step_open_{k}"):
                    n = len(S[mine])
                    open_head(k, f"{n} player{'s' if n != 1 else ''}")
                    with st.container(horizontal=True, gap="small", key=f"sk_pick_{side}"):
                        for i, p in enumerate(names):
                            if p in S[other]:   # on the other team: not offered here
                                continue
                            st.button(p, key=f"sk_t{side}_{i}", type="primary" if p in S[mine] else "secondary", on_click=tap, args=(side, p),
                                      width="content")
                    if S[other]:
                        ui.html(ui.note(f"{', '.join(S[other])} {'is' if len(S[other]) == 1 else 'are'} on Team {'B' if side == 'A' else 'A'}, so not shown. "
                                        f"Change Team {'B' if side == 'A' else 'A'} to move someone.", 8, 12))
                    st.button(f"Done with Team {side}", key=f"sk_done_{k}", type="primary", on_click=done, args=(k,), disabled=not S[mine])
            else:
                summary(k, ", ".join(S[mine]) if S[mine] else "Not picked yet", can_change=not locked,
                        note="Teams are locked once maps are entered." if locked else None)
    title, date, bo = S["title"], S["date"], int(S["bo"] or 5)
    no = series_doc(editing)["series_no"] if editing else data.next_series_no(title)
    A, B = S["a"], S["b"]
    ui.html("<div style='height:14px'></div>")
    with st.expander("Add a Public Note (shows in the Series Log)", expanded=bool(S.get("pub"))):
        pub = field(st.text_input, "Public note", "sk_s_pub", S, "pub", "", placeholder="e.g. Series 15 decides the rivalry",
                    label_visibility="collapsed")
    priv = S.get("priv") or None  # private notes are no longer entered here; an existing one is kept as is
    ok = len(A) > 0 and len(B) > 0
    fmt_now = f"{len(A)}v{len(B)}"

    # fill the ticket now that every choice above is known
    tshort = ts[title].get("short") or ts[title]["name"]
    dd = pd.Timestamp(date)
    even = len(A) == len(B)
    tag = lambda txt, bg, fg, bd: (f"<span style='font-size:12px; font-weight:600; padding:3px 8px; background:{bg}; color:{fg}; "  # noqa: E731
                                   f"border:1px solid {bd}; white-space:nowrap'>{txt}</span>")
    size = (tag(fmt_now, ui.INK, "#F2F4F2", ui.INK) if even else tag(f"{fmt_now} · uneven", me.YELLOW, ui.INK, me.YELLOW)) if ok else ""
    def team_html(t, side):
        col = ui.INK if side == "A" else ui.BLUE
        names = " · ".join(t) if t else f"<span style='color:{ui.MUTED}; font-weight:400'>Pick Team {side}</span>"
        sq = ui.swatch(col, 12, 12)
        # Team A reads toward the middle (names, then its square); Team B starts with its square
        inner = f"{names}{sq}" if side == "A" else f"{sq}{names}"
        align = "flex-end" if side == "A" else "flex-start"
        return (f"<div class='sk-tk-{side.lower()}' style='display:flex; align-items:center; justify-content:{align}; gap:10px; font-size:18px; "
                f"font-weight:500; min-width:0; text-align:{'right' if side == 'A' else 'left'}'>{inner}</div>")
    with ticket.container(key="sk_ticket"):
        ui.html(f"<div style='display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap'>"
                f"<span style='font-size:12px; font-weight:600; letter-spacing:1.6px; text-transform:uppercase; color:{ui.MUTED}'>"
                f"{tshort} · Series {no} · {dd.strftime('%b')} {dd.day}</span>"
                f"<span style='display:inline-flex; gap:6px'>{tag(f'Best of {bo}', 'transparent', ui.INK, ui.STEEL)}{size}</span></div>"
                f"<div class='sk-tk-teams' style='display:grid; grid-template-columns:minmax(0,1fr) auto minmax(0,1fr); align-items:center; "
                f"gap:8px 20px; margin-top:14px'>{team_html(A, 'A')}<div style='font-size:13px; color:{ui.MUTED}'>vs</div>{team_html(B, 'B')}</div>")
    label = "Save Changes" if editing else (f"Start Series {no} · {fmt_now} · Best of {bo}" if ok else f"Start Series {no}")
    if st.button(label, type="primary", disabled=not ok, width="stretch"):
        fmt = f"{len(A)}v{len(B)}"
        if editing:
            data.update_series(editing, date=pd.Timestamp(date).date().isoformat(), best_of=int(bo), team_a=A, team_b=B, format=fmt,
                               public_note=pub or None, private_note=priv or None)
            ss.sk_sid = editing
        else:
            ss.sk_sid = data.create_series(title, date, fmt, bo, A, B, pub, priv)
        ss.pop("sk_setup", None); ss.sk_step = "maps"; ss.pop("sk_draft", None)
        st.rerun(scope="app")


# ---------------------------------------------------------------- players
def roster():
    ui.html(f"<div style='border-top:2px solid {ui.INK}; margin-top:40px; padding-top:16px; font-size:20px; font-weight:400'>Players</div>"
            "<div style='height:12px'></div>")
    pls = {p["_id"]: p for p in docs()["players"]}
    e = data.engine(None)
    with st.expander(f"Show all {len(pls)}"):
        for name in all_players():
            p = pls[name]; tags = [g["tag"] for g in p.get("gamertags", [])]
            tag_txt = (tags[-1] + (f" (was {', '.join(tags[:-1])})" if len(tags) > 1 else "")) if tags else "No gamertag yet"
            c1, c2 = st.columns([3, 2], vertical_alignment="center")
            with c1:
                ui.html(f"<div style='padding:6px 0'><div style='font-size:15px; font-weight:600'>{name}</div>"
                        f"<div style='font-size:12px; color:{ui.MUTED}'>{tag_txt} · {e.nmaps(name) if not e.empty else 0} maps</div></div>")
            with c2:
                with st.popover("Gamertags", width="stretch"):
                    for i, g in enumerate(reversed(p.get("gamertags", []))):
                        ui.html(f"<div style='display:flex; justify-content:space-between; font-size:14px; padding:4px 0'><span>{g['tag']}</span>"
                                f"<span style='color:{ui.MUTED}'>{'current' if i == 0 else 'since ' + g.get('since', '')}</span></div>")
                    nt = st.text_input("Add a new gamertag", key=f"sk_tag_{name}", placeholder="New gamertag")
                    if st.button("Add gamertag", key=f"sk_tagb_{name}", disabled=not nt.strip()):
                        data.add_gamertag(name, nt); st.rerun()
                    ui.html(ui.note("Old tags stay on file so past games and scoreboard photos still match. The app always shows the name, not the tag.", 4, 12))
    with st.expander("Add a Player"):
        c1, c2, c3 = st.columns([1, 1, 0.6], vertical_alignment="bottom")
        with c1:
            nm = st.text_input("Name", key="sk_new_name", placeholder="Name")
        with c2:
            gt = st.text_input("Gamertag", key="sk_new_tag", placeholder="Their in-game name")
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


# ---------------------------------------------------------------- season settings
def settings():
    ui.html(f"<div style='border-top:2px solid {ui.INK}; margin-top:40px; padding-top:16px; font-size:20px; font-weight:400'>Season Settings</div>"
            + ui.note("Changes apply from the day you save them, so earlier maps keep the rules they were played under.", 4, 13))
    with st.expander("Show settings"):
        tids = [t for t in sorted(ts, key=lambda t: -ts[t].get("order", 0))]
        tid = st.selectbox("Title", tids, key="sk_set_title", format_func=lambda t: ts[t]["name"] + f" ({ts[t]['year']})" + (" · current" if ts[t].get("current") else ""))
        drafts = ss.setdefault("sk_set_drafts", {})
        if tid not in drafts:
            drafts[tid] = {"doc": copy.deepcopy(ts[tid]), "log": []}
        D = drafts[tid]; doc = D["doc"]; modes = doc.setdefault("modes", {})
        if not ts[tid].get("current"):
            if st.button(f"Make {ts[tid]['name']} the current title", key=f"sk_cur_{tid}"):
                for o in ts.values():
                    if o.get("current") and o["_id"] != tid:
                        data.save_title({**o, "current": False}, f"{ts[tid]['name']} is now the current title")
                data.save_title({**ts[tid], "current": True}, "Made the current title")
                drafts.pop(tid, None); st.rerun()
            ui.html(ui.note("The current title is the one the app opens on and the Scorekeeper enters games for by default.", 0, 12))
        e = data.engine(tid)
        mc = e.maps.groupby("mode").size() if not e.empty else pd.Series(dtype=int)
        ui.html(ui.label("Modes", margin_top=12))
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
                if st.button("Bring back" if off else "Retire", key=f"sk_mode_{tid}_{k}", width="stretch"):
                    m["active"] = off
                    D["log"].append(f"{'Brought back' if off else 'Retired'} {m.get('name', k)}")
                    st.rerun()
        with st.popover("Add a mode"):
            nmn = st.text_input("Mode name", key=f"sk_nm_{tid}", placeholder="e.g. Hijack")
            code = st.text_input("Short code", key=f"sk_nc_{tid}", placeholder="e.g. HJ", max_chars=4)
            lab = st.text_input("Score label", key=f"sk_nl_{tid}", placeholder="e.g. Points")
            bor = st.selectbox("Borrow MAR values from", [k for k in modes if k in CONV], key=f"sk_nb_{tid}", format_func=MODEN.get)
            if st.button("Add mode", disabled=not (nmn.strip() and code.strip())):
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
        ui.html(ui.label("Map pool", margin_top=24))
        sm = st.segmented_control("Pool mode", active, default=active[0], key=f"sk_pm_{tid}", label_visibility="collapsed",
                                  format_func=lambda k: modes[k].get("short") or MODEN.get(k, k)) or active[0]
        maps = modes[sm].setdefault("maps", [])
        if not maps:
            ui.html(ui.note(f"No {modes[sm].get('short', sm)} maps for {doc['name']} yet. Add the first one below.", 4, 13))
        for i, mp in enumerate(maps):
            ret = mp.get("status") == "retired"
            c1, c2 = st.columns([4, 1], vertical_alignment="center")
            with c1:
                since = "Retired · stays in every stat" if ret else ("In rotation" + (f" · added {mp['since']}" if mp.get("since") else f" · {doc['name']}"))
                ui.html(f"<div style='padding:4px 0'><div style='font-size:15px; font-weight:500; color:{ui.MUTED if ret else ui.INK}'>{mp['name']}</div>"
                        f"<div style='font-size:12px; color:{ui.MUTED}'>{since}</div></div>")
            with c2:
                if st.button("Bring back" if ret else "Retire", key=f"sk_map_{tid}_{sm}_{i}", width="stretch"):
                    mp["status"] = "active" if ret else "retired"
                    D["log"].append(f"{'Brought back' if ret else 'Retired'} {mp['name']} ({modes[sm].get('short', sm)})")
                    st.rerun()
        c1, c2 = st.columns([4, 1], vertical_alignment="bottom")
        with c1:
            newmap = st.text_input("Add a map to this mode", key=f"sk_addmap_{tid}_{sm}", placeholder="Map name")
        with c2:
            if st.button("Add map", key=f"sk_addmapb_{tid}_{sm}", disabled=not newmap.strip(), width="stretch"):
                nmx = newmap.strip().title()
                if any(m["name"].lower() == nmx.lower() for m in maps):
                    st.warning(f"{nmx} is already in the pool.")
                else:
                    maps.append({"name": nmx, "status": "active", "since": dt.date.today().isoformat()})
                    D["log"].append(f"Added {nmx} ({modes[sm].get('short', sm)})")
                    ss.pop(f"sk_addmap_{tid}_{sm}", None)
                    st.rerun()
        ui.html(ui.note("Retired maps stay in every stat and still show (marked Retired) when you enter a map, for the odd night one gets played.", 4, 12))

        ui.html(ui.label(f"MAR conversions · {modes[sm].get('short', sm)}", margin_top=24))
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
            conv["assist"] = st.number_input("Assist (kills)", value=float(conv.get("assist", 0.25)), step=0.05, key=f"sk_cv_{tid}_assist")
        ui.html(ui.label("Team sizes", margin_top=20) + "<div style='display:flex; gap:6px; margin-top:8px'>"
                + "".join(f"<span style='font-size:13px; padding:3px 10px; background:{ui.INK}; color:{ui.BG}'>{z}</span>" for z in doc.get("team_sizes", ["3v3"]))
                + "</div>" + ui.note("MAR adjusts objective stats and kills-per-win for 4v4 automatically.", 6, 12))
        log = sorted([x for x in docs()["settings_log"] if x["title"] == tid], key=lambda x: x["date"], reverse=True)
        rows = "".join(f"<div style='display:grid; grid-template-columns:90px minmax(0,1fr); gap:10px; padding:7px 0; border-bottom:1px solid {ui.RULE}; font-size:13px'>"
                       f"<span style='color:{ui.MUTED}'>{pd.Timestamp(x['date']).strftime('%b')} {pd.Timestamp(x['date']).day}</span><span>{x['text']}</span></div>" for x in log)
        ui.html(ui.label("Change history", margin_top=20) + f"<div style='margin-top:6px'>{rows}</div>")
        changed_conv = {k: v for k, v in conv.items() if k != "from"} != {k: v for k, v in vers[-1].items() if k != "from"}
        pending = D["log"] + (["Changed MAR conversions"] if changed_conv else [])
        if pending:
            ui.html(ui.note("Unsaved: " + "; ".join(pending) + ".", 10, 13))
        if st.button("Save settings", type="primary", disabled=not pending, key=f"sk_save_{tid}"):
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


def new_draft(s, match=None):
    prows = [r for r in docs()["player_matches"] if match and r["match_id"] == match["_id"]]
    return me.new_draft(ts[s["title"]], match, prows)


def maps_step():
    s = series_doc(ss.sk_sid); tcfg = ts[s["title"]]
    A, B = s["team_a"], s["team_b"]
    wa, wb = wins(s["_id"]); need = s["best_of"] // 2 + 1
    over = wa >= need or wb >= need
    d0 = pd.Timestamp(s["date"])
    c1, c2 = st.columns([4, 1], vertical_alignment="center")
    with c1:
        ui.html(f"<div style='font-size:13px; color:{ui.MUTED}'>{tcfg['short']} Series {s['series_no']} · {d0.strftime('%b')} {d0.day} · Best of {s['best_of']} · {s['format']}</div>")
    with c2:
        if st.button("Edit Setup", key="sk_edit_setup", width="stretch"):
            ss.sk_setup = {"edit_sid": s["_id"], "title": s["title"], "date": d0.date(), "bo": s["best_of"], "a": A, "b": B,
                           "pub": s.get("public_note") or "", "priv": s.get("private_note") or ""}
            for k in [k for k in ss if k.startswith("sk_s_")]:
                del ss[k]
            ss.sk_step = "setup"; st.rerun()
    ui.html("<div style='height:4px'></div>")
    with st.container(key="sk_head"):
        ui.html("<div style='display:grid; grid-template-columns:minmax(0,1fr) auto minmax(0,1fr); align-items:center; gap:8px 20px; padding:4px 0'>"
            f"<span style='font-size:15px; font-weight:{600 if wa > wb else 400}'>{team_str(A)}</span>"
            f"<span style='font-weight:300; font-size:34px; line-height:1'>{wa} – {wb}</span>"
            f"<span style='text-align:right; font-size:15px; font-weight:{600 if wb > wa else 400}'>{team_str(B)}</span></div>")
    D = ss.get("sk_draft")
    ms = series_maps(s["_id"])
    if ms:
        ui.html(ui.label("Maps entered", margin_top=16))
        for i, m in enumerate(ms):
            c1, c2 = st.columns([3, 2], vertical_alignment="center")
            with c1:
                won = A if m["winner"] == "A" else B
                ln = f" · {ui.mmss(m['length_sec'])}" if m.get("length_sec") else ""
                ui.html(f"<div style='padding:4px 0'><div style='font-size:15px; font-weight:500'>{m['map_no']}. {SHORT.get(m['mode'], m['mode'])} on {m['map']} · "
                        f"{m['score_a']}–{m['score_b']}{ln}</div><div style='font-size:12px; color:{ui.MUTED}; margin-top:5px'>Won by {team_str(won)}"
                        f"{' · partial scoreboard' if m.get('board') == 'partial' else ''}</div></div>")
            with c2:
                with st.container(horizontal=True, gap="small", horizontal_alignment="right"):
                    if st.button("Edit", key=f"sk_ed_{m['_id']}"):
                        ss.sk_draft = new_draft(s, m); st.rerun()
                    if i == len(ms) - 1 and st.button("Delete", key=f"sk_del_{m['_id']}"):
                        ss[f"sk_confirm_del"] = m["_id"]
            if ss.get("sk_confirm_del") == m["_id"]:
                st.warning(f"Delete map {m['map_no']} ({m['map']})? Its player stats go too.")
                a, b = st.columns(2)
                if a.button("Yes, delete", type="primary", key="sk_del_yes"):
                    data.delete_map(m["_id"]); ss.pop("sk_confirm_del"); ss.pop("sk_draft", None); st.rerun()
                if b.button("Keep it", key="sk_del_no"):
                    ss.pop("sk_confirm_del"); st.rerun()
    editing = D is not None and D.get("match_id")
    if ms and not over and not editing:
        if not ss.get("sk_end"):
            if st.button("End series early"):
                ss.sk_end = True; st.rerun()
        else:
            ui.html(f"<div style='margin-top:12px; padding:14px 16px; border:1px solid {ui.STEEL}'><div style='font-size:16px; font-weight:600'>"
                    f"End Series {s['series_no']} at {wa}–{wb}?</div>" + ui.note("The series gets an Ended early tag. Maps already entered count as normal.", 4, 13) + "</div>")
            dflt = "A" if wa > wb else "B" if wb > wa else "N"
            opts = {"A": f"{team_str(A)} · " + (f"leading {wa}–{wb}" if wa > wb else f"score {wa}–{wb}"),
                    "B": f"{team_str(B)} · " + (f"leading {wb}–{wa}" if wb > wa else f"score {wb}–{wa}"),
                    "N": "No result · neither team gets the series"}
            pick = st.radio("Who gets the series?", list(opts), index=list(opts).index(dflt), format_func=opts.get, key="sk_end_pick")
            a, b = st.columns(2)
            if a.button("Keep playing"):
                ss.sk_end = False; st.rerun()
            if b.button("End series", type="primary"):
                data.update_series(s["_id"], status="closed", result_override=pick)
                ss.sk_end = False; ss.sk_result = pick; ss.sk_step = "done"; ss.pop("sk_draft", None); st.rerun()
    if over and not editing:
        win = A if wa > wb else B
        ui.html(f"<div style='margin-top:16px; padding:16px; background:{ui.PANEL}'><div style='font-size:18px; font-weight:600'>{team_str(win)} win {max(wa, wb)}–{min(wa, wb)}</div>"
                + ui.note("Series MVP, standings, MAR and records update as soon as you finish.", 4, 13) + "</div>")
        if st.button("Finish series", type="primary", width="stretch"):
            data.update_series(s["_id"], status="closed", result_override=None)
            ss.sk_result = None; ss.sk_step = "done"; ss.pop("sk_draft", None); st.rerun()
        return
    if D is None:
        D = ss.sk_draft = new_draft(s)
    entry(s, D, len(ms))


def entry(s, D, nsaved):
    map_no = next((m["map_no"] for m in series_maps(s["_id"]) if m["_id"] == D["match_id"]), nsaved + 1)

    def on_save(mode, map_name, sa, sb, ln, board, rows, match_id):
        data.save_map(s, mode, map_name, sa, sb, ln, board, rows, match_id=match_id)
        ss.pop("sk_draft", None)

    played = tuple(m["map"] for m in series_maps(s["_id"]) if m["_id"] != D["match_id"])
    me.entry(me.Ctx(tcfg=ts[s["title"]], team_a=s["team_a"], team_b=s["team_b"], map_no=map_no, prefix="sk", on_save=on_save, played=played,
                    on_cancel=lambda: ss.pop("sk_draft", None)), D)


# ===================================================================== STEP 3: done
def done():
    s = series_doc(ss.sk_sid)
    wa, wb = wins(s["_id"]); A, B = s["team_a"], s["team_b"]
    res = ss.get("sk_result")
    if res == "N":
        line = f"Series ended early at {wa}–{wb} with no result"
    elif res in ("A", "B"):
        line = f"{team_str(A if res == 'A' else B)} take the series {wa if res == 'A' else wb}–{wb if res == 'A' else wa} (ended early)"
    else:
        line = f"{team_str(A if wa > wb else B)} win {max(wa, wb)}–{min(wa, wb)}"
    mv = data.engine(s["title"]).series_mvps().get(s["_id"])
    ui.html(ui.h2(f"Series {s['series_no']} Saved", margin_top=24, rule=False)
            + ui.note(f"{line}. It's now in the Series Log, and standings, MAR, rivalries and records include it."
                      + (f" Series MVP: {mv[0]} ({ui.sg(mv[1], 2)})." if mv else ""), 6, 15))
    if st.button("Start another series", type="primary", width="stretch"):
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