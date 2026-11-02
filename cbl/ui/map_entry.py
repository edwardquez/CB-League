"""Map entry (mode, map, score, then player by player, then review), shared by the Scorekeeper and the
Tournaments page. The caller says who is playing and what happens on save."""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from typing import Callable

import streamlit as st

from cbl import ocr
from cbl.config import CORE_STATS, EXTRA_STATS, FLOAT_STATS, STAT_LABELS
from cbl.ui import styles as ui

MODEN = {"HP": "Hardpoint", "SND": "Search and Destroy", "OVL": "Overload", "HJ": "Hijack"}
SHORT = {"HP": "Hardpoint", "SND": "SnD", "OVL": "Overload", "HJ": "Hijack"}


def css() -> str:
    """Full-width controls that are easy to tap, map tiles, player card. Both entry pages add this."""
    return f"""<style>
[class*="st-key-skfull_"] [data-testid="stElementContainer"], [class*="st-key-skfull_"] [data-testid="stButtonGroup"],
[class*="st-key-skfull_"] [role="radiogroup"] {{ width: 100% !important; max-width: none !important; flex-wrap: nowrap; }}
[class*="st-key-skfull_"] button[data-variant="segmented_control"] p {{ white-space: nowrap; }}
[class*="st-key-skfull_"] button[data-variant="segmented_control"] {{ flex: 1 1 0; min-height: 46px; }}
/* map tiles: picture + name are one card; an invisible button covers the whole card */
[class*="st-key-skmap_"] {{ position: relative; gap: 0 !important; }}
[class*="st-key-skmap_"] [data-testid="stMarkdownContainer"] {{ margin-bottom: 0 !important; }}
[class*="st-key-skmap_"] [data-testid="stElementContainer"]:has(button) {{ position: absolute; inset: 0; z-index: 3; margin: 0; width: 100% !important; }}
[class*="st-key-skmap_"] [data-testid="stElementContainer"]:has(button) > div, [class*="st-key-skmap_"] .stButton {{ height: 100%; width: 100%; }}
[class*="st-key-skmap_"] button {{ width: 100%; height: 100% !important; opacity: 0; cursor: pointer; }}
[class*="st-key-skmap_"]:hover .sk-tile {{ border-color: {ui.INK} !important; }}
.st-key-sk_pcard {{ background: {ui.PANEL}; }}
.st-key-sk_head {{ background: {ui.PANEL}; padding: 16px 18px 20px !important; }}
.st-key-sk_head [data-testid="stMarkdownContainer"] {{ margin-bottom: 0 !important; }}
[class*="st-key-skocr_"] {{ background: {ui.PANEL}; }}
</style>"""

YELLOW = "#FBEFC2"   # a cell read off the screenshot that needs a look


def field(fn, label, key, store, name, default=None, **kw):
    """A widget whose value survives being hidden (copied into `store`)."""
    ss = st.session_state
    if key not in ss:
        v0 = store.get(name)
        ss[key] = default if v0 is None else v0
    v = fn(label, key=key, **kw)
    store[name] = v
    return v


def new_draft(tcfg: dict, match: dict | None = None, prows: list[dict] | None = None) -> dict:
    active = [k for k, m in tcfg["modes"].items() if m.get("active", True)]
    d = {"id": uuid.uuid4().hex[:8], "sub": "info", "p": 0, "rows": {}, "match_id": None,
         "mode": active[0] if active else "HP", "map": None, "sa": None, "sb": None, "lm": None, "ls": None, "board": "full"}
    if match:
        d.update({"match_id": match["_id"], "mode": match["mode"], "map": match["map"], "sa": match["score_a"], "sb": match["score_b"],
                  "board": match.get("board") or "full"})
        if match.get("length_sec"):
            d["lm"], d["ls"] = int(match["length_sec"]) // 60, int(match["length_sec"]) % 60
        for r in prows or []:
            d["rows"][r["player"]] = {k: (None if v is None or (isinstance(v, float) and v != v) else v) for k, v in r.items()}
    return d


def stat_fields(tcfg: dict, mode: str):
    st_ = list(tcfg["modes"].get(mode, {}).get("stats", []))
    return ["kills", "deaths"], [s for s in CORE_STATS if s not in ("kills", "deaths")] + st_


def extra_fields(mode: str) -> list[str]:
    """Scoreboard-only stats (More Stats): optional, filled by the screenshot reader."""
    return list(EXTRA_STATS.get(mode, []))


def _to_num(f, v):
    if v is None:
        return None
    return float(v) if f in FLOAT_STATS else int(v)


def needs_look(D: dict, p: str, f: str) -> str | None:
    """Reason a field is highlighted: flagged by the reader and not changed since."""
    why = D.get("flags", {}).get(p, {}).get(f)
    if not why or D.get("ocr_vals", {}).get(p, {}).get(f) != D["rows"].get(p, {}).get(f):
        return None
    if why.startswith("doesn't match") and D.get("mode") == "SND" and None not in (D.get("sa"), D.get("sb")):
        # SnD math flag: look again with the numbers as they are now (fixing damage clears damage/round too)
        r, n = D["rows"].get(p, {}), D["sa"] + D["sb"]
        pair = {"kills": ("kills_per_round", "kills"), "kills_per_round": ("kills_per_round", "kills"),
                "damage": ("dmg_per_round", "damage"), "dmg_per_round": ("dmg_per_round", "damage")}.get(f)
        if pair and ocr._trunc_ok(r.get(pair[0]), r.get(pair[1]), n):
            return None
    return why


def checks(tcfg: dict, d: dict, lineup, rows, names=("Team A", "Team B")):
    """Warnings for the review step. Never blocking."""
    out = []
    mcfg = tcfg["modes"].get(d["mode"], {})
    if d["sa"] is not None and d["sb"] is not None and d["sa"] == d["sb"]:
        out.append(("Check this one:", "the score is tied. A map needs a winner; re-check the scores."))
    ws = mcfg.get("win_score")
    if ws and d["sa"] is not None and d["sb"] is not None and max(d["sa"], d["sb"]) != ws:
        out.append(("Heads up:", f"the winning score is {max(d['sa'], d['sb'])}, not {ws}. Fine if the map ended early; otherwise re-check."))
    nm = {"A": names[0], "B": names[1]}
    # read cleanly off the scoreboard (nothing flagged or changed): a kills/deaths gap is real, not a typo
    clean = bool(d.get("ocr_vals")) and all(
        not needs_look(d, p, f) and d["ocr_vals"].get(p, {}).get(f) == rows[p].get(f) for p, _ in lineup for f in ("kills", "deaths"))
    for side, other in (("A", "B"), ("B", "A")):
        k = sum((rows[p].get("kills") or 0) for p, t in lineup if t == side)
        dd = sum((rows[p].get("deaths") or 0) for p, t in lineup if t == other)
        name = nm[side]
        if clean and k < dd:
            out.append(("Heads up:", f"{name} has {dd - k} fewer kill{'s' if dd - k != 1 else ''} than {nm[other]} has deaths, as on the scoreboard. "
                                     "Falls, self-kills and team kills count as deaths."))
        elif k > dd:
            out.append(("Must re-check:", f"{name} has {k - dd} more kill{'s' if k - dd != 1 else ''} than {nm[other]} has deaths. That can't happen, so a number is off."))
        elif dd - k >= 5:
            out.append(("Likely a typo:", f"{name} has {dd - k} fewer kills than {nm[other]} has deaths. Falls and self-kills don't usually add up to that many."))
        elif dd - k >= 1:
            out.append(("Heads up:", f"{name} has {dd - k} fewer kill{'s' if dd - k != 1 else ''} than {nm[other]} has deaths. Falls, self-kills and team kills cause this, "
                                     "so you can save as is."))
        team = [p for p, t in lineup if t == side]
        if len(team) > 1 and all(rows[p].get("kills") is not None and rows[p].get("kills") == rows[p].get("deaths") for p in team):
            out.append(("Check this one:", f"every {name} player has the same kills and deaths. That usually means a column was copied by mistake."))
    seen = {}
    for p, _ in lineup:
        key = tuple(rows[p].get(f) for f in ("kills", "deaths", "assists", "damage"))
        if None not in key[:2] and key in seen:
            out.append(("Check this one:", f"{seen[key]} and {p} have identical lines. Make sure one wasn't entered twice."))
        seen.setdefault(key, p)
    if d["board"] == "full":
        _, opt = stat_fields(tcfg, d["mode"])
        blanks = sum(1 for p, _ in lineup for f in opt if f != "accuracy" and rows[p].get(f) is None)
        if blanks:
            out.append(("Heads up:", f"{blanks} blank stat{'s' if blanks != 1 else ''} on a full scoreboard. Blanks are saved as unknown, not zero."))
    return out


@dataclass
class Ctx:
    tcfg: dict
    team_a: list[str]
    team_b: list[str]
    map_no: int
    prefix: str                       # session-state key prefix, e.g. "sk" or "tn"
    on_save: Callable                 # (mode, map, sa, sb, length_sec, board, rows, match_id) -> None
    label_a: str | None = None        # how each team is named on the review step
    label_b: str | None = None
    played: tuple = ()                # maps already played in this series (marked on the tiles)
    on_cancel: Callable | None = None  # called by "Cancel editing" (and the first step's Cancel button if show_cancel)
    show_cancel: bool = False
    color_a: str | None = None        # team colors (the Tournaments page passes its bracket colors)
    color_b: str | None = None

    @property
    def lineup(self):
        return [(p, "A") for p in self.team_a] + [(p, "B") for p in self.team_b]


def team_str(t):
    return ", ".join(t)


def entry(c: Ctx, D: dict) -> None:
    tcfg = c.tcfg
    lineup = c.lineup
    la, lb = c.label_a or team_str(c.team_a), c.label_b or team_str(c.team_b)
    sub = D["sub"]; k = D["id"]; px = c.prefix
    ui.html("<div style='display:flex; justify-content:space-between; align-items:baseline; gap:12px; margin-top:28px'>"
            f"<div role='heading' class='cb-h2' style='font-weight:400; font-size:28px'>Map {c.map_no}</div>"
            f"<span style='font-size:13px; color:{ui.MUTED}'>{({'info': 'Map details', 'players': 'Player stats', 'review': 'Review'})[sub]}"
            f"{' · editing' if D['match_id'] else ''}</span></div><div style='border-top:2px solid {ui.INK}; margin-top:10px'></div>")
    modes = {kk: m for kk, m in tcfg["modes"].items() if m.get("active", True) or kk == D["mode"]}
    if sub == "info":
        if ocr.available():
            screenshot(c, D, modes)
        # with the screenshot reader on, typing it in is the fallback: tucked away unless something is already entered
        shot = ocr.available()
        open_ = not shot or bool(D["map"] or D["match_id"] or D["sa"] is not None or D["sb"] is not None)
        with (st.expander("Manual Input", expanded=open_) if shot else st.container()):
            with st.container(key=f"skfull_mode_{px}"):
                mode = field(st.segmented_control, "Mode", f"{px}_{k}_mode", D, "mode", D["mode"], options=list(modes),
                             format_func=lambda x: modes[x].get("short") or SHORT.get(x, x)) or D["mode"]
            D["mode"] = mode
            pool = modes[mode].get("maps", [])
            act = [m["name"] for m in pool if m.get("status") != "retired"]
            ret = [m["name"] for m in pool if m.get("status") == "retired"]
            opts = act + ret
            if D["map"] and D["map"] not in opts:
                opts.append(D["map"])
            if opts:
                if D["map"] not in opts:
                    D["map"] = None
                ui.html("<div style='font-size:14px; margin:6px 0 4px'>Map</div>")

                def pick_map(m):
                    D["map"] = m
                for r0 in range(0, len(opts), 5):
                    cols = st.columns(5, gap="small")
                    for col, m in zip(cols, opts[r0:r0 + 5]):
                        with col:
                            with st.container(gap=None, key=f"skmap_{px}_{k}_{m.replace(' ', '_')}"):
                                on = D["map"] == m
                                tag = "Retired" if m in ret else ("Played" if m in c.played else "")
                                # fixed two-line name area, so a long name (Reactor U92) keeps every tile the same height
                                ui.html(f"<div class='sk-tile' style='box-sizing:border-box; border:{'2px solid ' + ui.BLUE if on else '1px solid ' + ui.RULE}; "
                                        f"background:{ui.PANEL}'>{ui.img_tag(m)}<div style='height:44px; padding:5px 8px; box-sizing:border-box; overflow:hidden; "
                                        f"font-size:13px; line-height:1.25; color:{ui.INK}; font-weight:{600 if on else 400}'>{m}"
                                        + (f"<div style='font-size:11px; font-weight:400; color:{ui.MUTED}'>{tag}</div>" if tag else "") + "</div></div>")
                                st.button(m, key=f"{px}m_{k}_{m}", on_click=pick_map, args=(m,), width="stretch")
            else:
                D["map"] = field(st.text_input, "Map", f"{px}_{k}_mapt", D, "map", D["map"] or "", placeholder="Map name").strip().title() or None
                ui.html(ui.note(f"No {modes[mode].get('short', mode)} maps in {tcfg['name']}'s pool yet. Type it here, and add it under Season Settings so it shows next time.", 0, 12))
            c1, c2 = st.columns(2)
            with c1:
                field(st.number_input, la, f"{px}_{k}_sa", D, "sa", None, min_value=0, step=1, placeholder="0")
            with c2:
                field(st.number_input, lb, f"{px}_{k}_sb", D, "sb", None, min_value=0, step=1, placeholder="0")
            lab = modes[mode].get("score_label", "Score"); ws = modes[mode].get("win_score")
            ui.html(ui.label("Match length", margin_top=16))
            c1, c2, _ = st.columns([1, 1, 2])
            with c1:
                field(st.number_input, "Minutes", f"{px}_{k}_lm", D, "lm", None, min_value=0, max_value=59, step=1, placeholder="10")
            with c2:
                field(st.number_input, "Seconds", f"{px}_{k}_ls", D, "ls", None, min_value=0, max_value=59, step=1, placeholder="00")
            ui.html(ui.note("Shown on the caster scoreboard. Optional, but it powers per-minute stats. Leave it blank if you missed it.", 0, 12)
                    + ui.label("Scoreboard for this map", margin_top=16))
            with st.container(key=f"skfull_board_{px}"):
                field(st.segmented_control, "Scoreboard", f"{px}_{k}_board", D, "board", "full", options=["full", "partial"], label_visibility="collapsed",
                      format_func={"full": "Full scoreboard · every stat", "partial": "Partial · only what we could see"}.get)
            D["board"] = D["board"] or "full"
            ready = D["map"] and D["sa"] is not None and D["sb"] is not None
            if st.button("Next · player stats", type="primary", disabled=not ready, width="stretch", key=f"{px}_next_{k}"):
                D["sub"] = "players"; D["p"] = 0; st.rerun()
            if not ready:
                ui.html(ui.note("Pick a map and enter both scores to continue.", 0, 12))
        if c.on_cancel and c.show_cancel:
            if st.button("Cancel", width="stretch", key=f"{px}_cancel_{k}"):
                c.on_cancel(); st.rerun()
    elif sub == "players":
        i = min(D["p"], len(lineup) - 1); p, side = lineup[i]
        row = D["rows"].setdefault(p, {})
        dots = "".join(f"<span style='flex:1 1 0; height:4px; background:{ui.BLUE if j < i else ui.INK if j == i else ui.RULE}'></span>" for j in range(len(lineup)))
        col = (c.color_a or ui.INK) if side == "A" else (c.color_b or ui.BLUE)
        ui.html(f"<div style='display:flex; gap:4px; margin-top:8px'>{dots}</div>")
        card = st.container(border=True, key="sk_pcard")
        with card:
            ui.html(f"<div>"
                f"<div style='display:flex; justify-content:space-between; align-items:baseline; gap:12px'><span style='font-weight:400; font-size:28px'>{p}</span>"
                f"<span style='display:inline-flex; align-items:center; gap:6px; font-size:13px'>{ui.swatch(col, 10, 10)}{la if side == 'A' else lb}</span></div>"
                f"<div style='font-size:13px; color:{ui.MUTED}'>Player {i + 1} of {len(lineup)} · {SHORT.get(D['mode'], D['mode'])} on {D['map']}</div></div>")
        with card:
            req, opt = stat_fields(tcfg, D["mode"])
            ext = extra_fields(D["mode"])
            if D.get("crops", {}).get(p):
                st.image(D["crops"][p], width="stretch")
            looks = [(f, needs_look(D, p, f)) for f in req + opt + ext]
            looks = [(f, w) for f, w in looks if w]
            if looks:
                sel = ", ".join(f'[class*="st-key-{px}_{k}_{p}_{f}"] input' for f, _ in looks).replace("\\", "")
                ui.html(f"<style>{sel} {{ background:{YELLOW} !important; }}</style>"
                        f"<div style='margin:4px 0 6px; padding:10px 12px; background:{YELLOW}; font-size:13px; line-height:1.5'>"
                        "<b style='font-weight:600'>Check against the picture:</b> "
                        + "; ".join(f"{STAT_LABELS[f].replace(' (sec)', '')}: {w}" for f, w in looks) + "</div>")
            cc = st.columns(2)
            for j, f in enumerate(req):
                with cc[j]:
                    field(st.number_input, STAT_LABELS[f], f"{px}_{k}_{p}_{f}", row, f, None, min_value=0, step=1, placeholder="0")
            partial = D["board"] == "partial"
            ui.html(ui.label("Anything else you saw (optional, leave blank if unknown)" if partial else "Everything else", margin_top=12))
            for j, f in enumerate(opt):
                if j % 3 == 0:
                    cc = st.columns(3)
                with cc[j % 3]:
                    if f == "accuracy":
                        field(st.number_input, STAT_LABELS[f], f"{px}_{k}_{p}_{f}", row, f, None, min_value=0.0, max_value=100.0, step=0.1, placeholder="—")
                    else:
                        field(st.number_input, STAT_LABELS[f], f"{px}_{k}_{p}_{f}", row, f, None, min_value=0, step=1, placeholder="—" if partial else "0")
            if ext:
                open_ = any(row.get(f) is not None for f in ext) or any(f in dict(looks) for f in ext)
                with st.expander("More Stats (optional, from the scoreboard)", expanded=open_):
                    cc = st.columns(len(ext))
                    for j, f in enumerate(ext):
                        with cc[j]:
                            if f in FLOAT_STATS:
                                field(st.number_input, STAT_LABELS[f], f"{px}_{k}_{p}_{f}", row, f, None, min_value=0.0, step=0.01, format="%.2f", placeholder="—")
                            else:
                                field(st.number_input, STAT_LABELS[f], f"{px}_{k}_{p}_{f}", row, f, None, min_value=0, step=1, placeholder="—")
        a, b = st.columns([1, 2])
        if a.button("Back to map" if i == 0 else "Back", width="stretch", key=f"{px}_pback_{k}"):
            if i == 0:
                D["sub"] = "info"
            else:
                D["p"] = i - 1
            st.rerun()
        last = i == len(lineup) - 1
        ok = row.get("kills") is not None and row.get("deaths") is not None
        if b.button("Review map" if last else f"Next · {lineup[i + 1][0]}", type="primary", width="stretch", disabled=not ok, key=f"{px}_pnext_{k}"):
            if last:
                D["sub"] = "review"
            else:
                D["p"] = i + 1
            st.rerun()
        if not ok:
            ui.html(ui.note("Kills and deaths are needed for every player.", 0, 12))
    else:
        rows = D["rows"]
        missing = [p for p, _ in lineup if rows.get(p, {}).get("kills") is None or rows.get(p, {}).get("deaths") is None]
        if missing:
            ui.html(ui.empty_box("Some players are missing kills or deaths", ", ".join(missing)))
            if st.button("Back to player stats", key=f"{px}_miss_{k}"):
                D["sub"] = "players"; D["p"] = [p for p, _ in lineup].index(missing[0]); st.rerun()
            return
        from_shot = bool(D.get("ocr_vals"))
        hdr_warn = []
        if from_shot:
            # score and game time can be fixed right here; yellow while they still match a reading the reader wasn't sure of
            for nm in ("sa", "sb", "lm", "ls"):      # pick up an edit made on the last run before deciding what's still yellow
                if f"{px}_{k}_{nm}" in st.session_state:
                    D[nm] = st.session_state[f"{px}_{k}_{nm}"]
            hf, h0 = D.get("hdr_flags", {}), D.get("ocr_hdr", {})
            score_look = "score" in hf and (D["sa"], D["sb"]) == (h0.get("sa"), h0.get("sb"))
            time_look = "game_time" in hf and (D["lm"], D["ls"]) == (h0.get("lm"), h0.get("ls"))
            yl = ([f"{px}_{k}_sa", f"{px}_{k}_sb"] if score_look else []) + ([f"{px}_{k}_lm", f"{px}_{k}_ls"] if time_look else [])
            if yl:
                ui.html("<style>" + ", ".join(f'[class*="st-key-{x}"] input' for x in yl) + f" {{ background:{YELLOW} !important; }}</style>")
            ui.html(ui.label("Score and Game Time", margin_top=14))
            c1, c2, c3, c4 = st.columns([1, 1, 0.7, 0.7])
            with c1:
                field(st.number_input, f"{c.label_a or 'Team A'} score", f"{px}_{k}_sa", D, "sa", None, min_value=0, step=1)
            with c2:
                field(st.number_input, f"{c.label_b or 'Team B'} score", f"{px}_{k}_sb", D, "sb", None, min_value=0, step=1)
            with c3:
                field(st.number_input, "Minutes", f"{px}_{k}_lm", D, "lm", None, min_value=0, max_value=59, step=1, placeholder="—")
            with c4:
                field(st.number_input, "Seconds", f"{px}_{k}_ls", D, "ls", None, min_value=0, max_value=59, step=1, placeholder="—")
            if score_look:
                hdr_warn.append(("Check this one:", f"the score ({hf['score']}). Compare it with the picture and fix it above if needed."))
            if time_look:
                hdr_warn.append(("Check this one:", f"the total game time ({hf['game_time']}). Fix it above if needed."))
            if D["sa"] is None or D["sb"] is None or D["sa"] == D["sb"]:
                ui.html(ui.note("Enter both scores (a map needs a winner) to save.", 4, 12))
        if D["sa"] is None or D["sb"] is None:
            return
        win = "A" if D["sa"] > D["sb"] else "B"
        ln = (D["lm"] or 0) * 60 + (D["ls"] or 0) if (D["lm"] is not None or D["ls"] is not None) else None
        ui.html("<div style='display:grid; grid-template-columns:120px minmax(0,1fr); gap:14px; align-items:center; margin-top:14px'>"
                f"<div>{ui.img_tag(D['map'])}</div><div><div style='font-size:17px; font-weight:600'>{MODEN.get(D['mode'], D['mode'])} on {D['map']}</div>"
                f"<div style='font-size:13px; color:{ui.MUTED}'>{la} {D['sa']} – {D['sb']} {lb} · "
                f"{ui.mmss(ln) if ln else 'no match length'} · {'Partial' if D['board'] == 'partial' else 'Full'} scoreboard</div></div></div>")
        req, opt = stat_fields(tcfg, D["mode"])
        ext = extra_fields(D["mode"])
        if from_shot:   # every column, so each number can be checked against the picture
            show = [f for f in opt + ext if f != "accuracy"]
        else:
            show = [f for f in opt if f in ("damage", "assists") or f in tcfg["modes"].get(D["mode"], {}).get("stats", [])][:4]

        def cell(p, f):
            v = rows[p].get(f)
            txt = "—" if v is None else ui.mmss(v) if f.endswith("hill_time") else ui.n0(v) if f == "damage" else f"{v:.2f}" if f in FLOAT_STATS else str(v)
            why = needs_look(D, p, f)
            return {"v": txt, "bg": YELLOW, "title": why} if why else txt
        body = []
        for p, side in lineup:
            r = rows[p]; kd = r["kills"] / max(r["deaths"], 1)
            body.append([{"v": p, "w": 500, "fg": ui.INK if side == win else ui.MUTED}, cell(p, "kills"), cell(p, "deaths"), {"v": f"{kd:.2f}", "w": 500}]
                        + [cell(p, f) for f in show])
        short = {"non_traded_kills": "NTK", "highest_streak": "Streak", "objective_kills": "Obj", "avg_hill_time": "Avg hill", "contested_hill_time": "Contested",
                 "kills_per_hill": "K/hill", "dmg_per_hill": "Dmg/hill", "kills_per_round": "K/round", "dmg_per_round": "Dmg/round", "first_bloods": "FB",
                 "first_deaths": "FD", "bombs_planted": "Plants", "bombs_defused": "Defuses", "hill_time": "Hill"} if from_shot else {}
        ui.html(ui.table([("Player", "left"), ("K", "right"), ("D", "right"), ("K/D", "right")]
                         + [(short.get(f) or STAT_LABELS[f].replace(" (sec)", ""), "right") for f in show],
                         body, min_width=420 + (40 * len(show) if from_shot else 0), cell_pad="9px 6px"))
        if from_shot:
            looks = [(j, p, f, needs_look(D, p, f)) for j, (p, _) in enumerate(lineup) for f in req + opt + ext if needs_look(D, p, f)]
            n_look = len(looks)
            ui.html(ui.note((f"{n_look} number{'s' if n_look != 1 else ''} in yellow: the reader wasn't sure. Check {'them' if n_look != 1 else 'it'} "
                             "against the picture, and use Fix to jump straight to one. Hover a yellow cell for the reason." if n_look
                             else "Read from the screenshot; the reader was sure of every number."), 6, 12))
            if looks:
                def go_fix(j):
                    D["sub"] = "players"; D["p"] = j
                with st.container(horizontal=True, gap="small", key=f"{px}_fixes_{k}"):
                    for n, (j, p, f, why) in enumerate(looks[:12]):
                        st.button(f"Fix {p} · {STAT_LABELS[f].replace(' (sec)', '')}", key=f"{px}_fix_{k}_{n}", on_click=go_fix, args=(j,),
                                  width="content")
                if n_look > 12:
                    ui.html(ui.note(f"And {n_look - 12} more: use Edit for those players.", 4, 12))
            if D.get("ocr_img"):
                with st.expander("Show the Screenshot"):
                    st.image(D["ocr_img"], width="stretch")
        ec = st.columns(min(len(lineup), 4))
        for j, (p, _) in enumerate(lineup):
            if ec[j % len(ec)].button(f"Edit {p}", key=f"{px}_rev_{k}_{p}", width="stretch"):
                D["sub"] = "players"; D["p"] = j; st.rerun()
        warns = checks(tcfg, D, lineup, rows, (la, lb) if c.label_a else ("Team A", "Team B"))
        warns = hdr_warn + [("Check this one:", w) for w in D.get("ocr_warn", [])] + warns
        if D["board"] == "partial":
            ui.html(ui.note("Partial scoreboard: blanks are saved as unknown, not zero, so they don’t drag down anyone’s averages.", 10, 13))
        if not warns:
            ui.html(f"<div style='margin-top:12px; padding:12px 14px; background:{ui.PANEL}; font-size:14px'>Checks passed: team kills line up with the other team's deaths, "
                    "and the score fits the mode.</div>")
        for t, b in warns:
            strong = t.startswith("Must")
            ui.html(f"<div style='margin-top:8px; padding:12px 14px; border-left:3px solid {ui.RUST if strong else ui.STEEL}; background:{ui.PANEL}; font-size:14px'>"
                    f"<b style='font-weight:600'>{t}</b> {b}</div>")
        if warns:
            ui.html(ui.note("You can still save; warnings never block.", 6, 12))
        if st.button(f"Save map {c.map_no}", type="primary", width="stretch", key=f"{px}_save_{k}"):
            out = []
            fields = req + opt + ext
            for p, side in lineup:
                r = {f: rows[p].get(f) if f in fields else None for f in STAT_LABELS}
                r = {f: _to_num(f, v) for f, v in r.items()}
                out.append({"player": p, "team": side, **r})
            c.on_save(D["mode"], D["map"], int(D["sa"]), int(D["sb"]), ln, D["board"], out, D["match_id"])
            st.rerun()
        if D["match_id"] and st.button("Cancel editing", key=f"{px}_canced_{k}"):
            if c.on_cancel:
                c.on_cancel()
            st.rerun()


# ---------------------------------------------------------------- Fill From Screenshot
def _gamertags(names) -> dict[str, list[str]]:
    from cbl import data
    docs = {p["_id"]: p for p in data.load_docs().get("players", [])}
    return {n: [g["tag"] for g in docs.get(n, {}).get("gamertags", []) if g.get("tag")] for n in names}


@st.cache_data(show_spinner=False, max_entries=24)
def _read_cached(digest: str, img: bytes, maps: tuple) -> dict:
    return ocr.read(img, maps)


def screenshot(c: Ctx, D: dict, modes: dict) -> None:
    """Upload a Codcaster scoreboard, say which board row is which player, and fill the whole map in."""
    ss = st.session_state
    px, k = c.prefix, D["id"]
    lineup = c.lineup
    la, lb = c.label_a or team_str(c.team_a), c.label_b or team_str(c.team_b)
    with st.container(border=True, key=f"skocr_{px}"):
        ui.html("<div style='font-size:17px; font-weight:600'>Fill From Screenshot</div>"
                f"<div style='font-size:13px; color:{ui.MUTED}; margin-top:2px'>The Codcaster scoreboard from the end of the map, read with Tesseract OCR. "
                "Best: a PNG at 1920 × 1080 or larger, with both team tables and the map name in the picture.</div>")
        up = st.file_uploader("Scoreboard screenshot", type=["png", "jpg", "jpeg", "webp"], key=f"{px}_up_{D.get('up_n', 0)}",
                              label_visibility="collapsed")
        if up is None:
            if D.get("ocr_board") and not D.get("ocr_vals"):
                D.pop("ocr_board", None)
            return
        img = up.getvalue()
        if len(img) > 10 * 1024 * 1024:
            ui.html(f"<div style='margin-top:8px; padding:10px 12px; border-left:3px solid {ui.RUST}; font-size:14px'>That file is over 10 MB. "
                    "A full-size scoreboard screenshot is usually under 1 MB; use the PNG from VLC's Take Snapshot.</div>")
            return
        digest = hashlib.sha1(img).hexdigest()
        if D.get("ocr_hash") != digest:
            maps = tuple(sorted({m["name"] for md in modes.values() for m in md.get("maps", [])}))
            with st.spinner("Reading the scoreboard. This takes about 10 seconds, longer if others are uploading at the same time."):
                D["ocr_board"] = _read_cached(digest, img, maps)
            D["ocr_hash"] = digest
            D["ocr_img"] = img
        B = D.get("ocr_board") or {}
        if not B.get("ok"):
            ui.html(f"<div style='margin-top:8px; padding:10px 12px; border-left:3px solid {ui.RUST}; font-size:14px'>"
                    f"{B.get('error') or 'Couldn’t read that picture.'}</div>")
            return
        mode = B["mode"]
        mname = modes.get(mode, {}).get("name") or MODEN.get(mode, mode)
        hf = B.get("header_flags", {})

        def hdr(txt, key):
            return f"<span style='background:{YELLOW}; padding:0 4px' title='{hf[key]}'>{txt}</span>" if key in hf else txt
        sa, sb = B["score"]
        score = hdr(f"{'?' if sa is None else sa} – {'?' if sb is None else sb}", "score")
        gtime = hdr(ui.mmss(B["game_time"]) if B["game_time"] else "no game time", "game_time")
        n_a = sum(1 for r in B["rows"] if r["team"] == "alpha"); n_b = len(B["rows"]) - n_a
        ui.html(f"<div style='margin-top:10px; font-size:15px'><b style='font-weight:600'>{mname} on {B['map'] or '?'}</b> · Alpha {score} Bravo · "
                f"{gtime} · {n_a}v{n_b}</div>")
        notes = list(B.get("warnings", []))
        if mode not in modes:
            notes.append(f"{mname} isn't a mode in {c.tcfg['name']}.")
        pool = {m["name"] for m in modes.get(mode, {}).get("maps", [])}
        if B["map"] and pool and B["map"] not in pool:
            notes.append(f"{B['map']} isn't in the {mname} pool. It will be saved as read; add it under Season Settings if it should be there.")
        if n_a + n_b != len(lineup):
            notes.append(f"The board has {n_a + n_b} players but this map's lineup has {len(lineup)}. Leave any extra rows on No One.")
        for n in notes:
            ui.html(f"<div style='margin-top:8px; padding:10px 12px; border-left:3px solid {ui.STEEL}; font-size:13px'>{n}</div>")

        with st.expander("See Everything It Read"):
            cols_ = ["kills", "deaths"] + ocr.COLUMNS[mode][1:]
            short = {"kills": "K", "deaths": "D", "assists": "A", "non_traded_kills": "NTK", "highest_streak": "Streak", "damage": "Dmg",
                     "hill_time": "Hill", "avg_hill_time": "Avg hill", "objective_kills": "Obj", "contested_hill_time": "Contested",
                     "kills_per_hill": "K/hill", "dmg_per_hill": "Dmg/hill", "bombs_planted": "Plants", "bombs_defused": "Defuses",
                     "first_bloods": "FB", "first_deaths": "FD", "kills_per_round": "K/round", "dmg_per_round": "Dmg/round"}

            def fmt(r, f):
                v = r["stats"].get(f)
                t = "?" if v is None else ui.mmss(v) if f in ocr.TIMES else f"{v:.2f}" if f in ocr.RATIOS else ui.n0(v) if f == "damage" else str(v)
                return {"v": t, "bg": YELLOW, "title": r["flags"][f]} if f in r["flags"] else t
            body = []
            for i, r in enumerate(B["rows"]):
                if i and r["team"] != B["rows"][i - 1]["team"]:
                    body.append("SPACER")
                body.append([{"v": r["name"] or "?", "w": 500}] + [fmt(r, f) for f in cols_])
            ui.html(ui.table([("Board name", "left")] + [(short.get(f, f), "right") for f in cols_], body, min_width=900, cell_pad="8px 6px")
                    + ui.note("Nothing is saved yet. Yellow means the reader wasn't sure (hover for why).", 6, 12))
        # which row is which player
        ui.html(ui.label("Who Is Who", margin_top=14) + ui.note("Matched by gamertag where possible. Bot names usually stay the same from map to map, "
                                                               "so after the first map these fill in by themselves.", 0, 12))
        mem = ss.setdefault(f"ocr_mem_{px}", {})
        names = [r["name"] for r in B["rows"]]
        match_guess = ocr.match_players(names, _gamertags([p for p, _ in lineup]), mem)
        opts = ["—"] + [p for p, _ in lineup]
        side_of = dict(lineup)
        picks = []
        for i, r in enumerate(B["rows"]):
            key = f"{px}_{k}_as_{D['ocr_hash'][:6]}_{i}"
            if key not in ss:
                ss[key] = match_guess[i] or "—"
            st_ = r["stats"]
            col = ui.BLUE if r["team"] == "alpha" else ui.RUST
            a1, a2 = st.columns([3, 2], vertical_alignment="center")
            with a1:
                line = (f"{st_.get('kills', '?')}/{st_.get('deaths', '?')} · {ui.n0(st_['damage']) if st_.get('damage') is not None else '?'} dmg")
                ui.html(f"<div style='display:flex; gap:10px; align-items:center; font-size:14px'>{ui.swatch(col, 4, 30)}"
                        f"<div><div style='font-weight:500'>{r['name'] or '(name not read)'}</div>"
                        f"<div style='font-size:12px; color:{ui.MUTED}'>{'Alpha' if r['team'] == 'alpha' else 'Bravo'} {r['slot']} · {line}</div></div></div>")
            with a2:
                pk = st.selectbox(f"Player for {r['team']} row {r['slot']}", opts, key=key, label_visibility="collapsed",
                                  format_func=lambda x: "No One" if x == "—" else (f"{x} ({la if side_of[x] == 'A' else lb})" if c.label_a else x))
            picks.append(None if pk == "—" else pk)
        chosen = [p for p in picks if p]
        dup = sorted({p for p in chosen if chosen.count(p) > 1})
        missing = [p for p, _ in lineup if p not in chosen]
        alpha_sides = {side_of[p] for p, r in zip(picks, B["rows"]) if p and r["team"] == "alpha"}
        bravo_sides = {side_of[p] for p, r in zip(picks, B["rows"]) if p and r["team"] == "bravo"}
        problem = None
        if dup:
            problem = f"{', '.join(dup)} {'is' if len(dup) == 1 else 'are'} picked twice."
        elif missing:
            problem = f"Still to pick: {', '.join(missing)}."
        elif len(alpha_sides) > 1 or len(bravo_sides) > 1 or alpha_sides & bravo_sides:
            problem = "Each board team should be one of your teams: Alpha's rows all from one team, Bravo's all from the other."
        if problem:
            ui.html(ui.note(problem, 8, 12))
        if mode not in modes:
            return
        if st.button(f"Fill In Map {c.map_no}", type="primary", width="stretch", disabled=bool(problem), key=f"{px}_ocrgo_{k}"):
            alpha_is = next(iter(alpha_sides)) if alpha_sides else "A"
            req, opt = stat_fields(c.tcfg, mode)
            fields = req + opt + extra_fields(mode)
            D["mode"], D["map"] = mode, B["map"] or D["map"]
            D["sa"], D["sb"] = (sa, sb) if alpha_is == "A" else (sb, sa)
            gt = B["game_time"]
            D["lm"], D["ls"] = (gt // 60, gt % 60) if gt else (None, None)
            D["board"] = "full"
            D["rows"], D["flags"], D["ocr_vals"], D["crops"] = {}, {}, {}, {}
            for p, r in zip(picks, B["rows"]):
                if not p:
                    continue
                D["rows"][p] = {f: r["stats"].get(f) for f in fields}
                D["flags"][p] = dict(r["flags"])
                D["ocr_vals"][p] = dict(D["rows"][p])
                D["crops"][p] = r.get("crop")
                if r["name"]:
                    mem[r["name"]] = p
            # board-level notes; score notes are worked out on the review step, so fixing the score clears them
            D["ocr_warn"] = [w for w in B.get("warnings", []) if not w.startswith("Neither team is on")]
            D["hdr_flags"] = dict(hf)
            D["ocr_hdr"] = {"sa": D["sa"], "sb": D["sb"], "lm": D["lm"], "ls": D["ls"]}
            D["id"] = uuid.uuid4().hex[:8]       # fresh widgets, so every field shows the filled-in value
            D["up_n"] = D.get("up_n", 0) + 1
            D["sub"] = "review" if D["map"] and D["sa"] is not None and D["sb"] is not None else "info"
            st.rerun()