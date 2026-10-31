"""Glossary: what every stat means and how MAR is calculated."""
import streamlit as st

from cbl import data
from cbl.stats import mar as marmod
from cbl.ui import page, styles as ui

page.start("Glossary")
season = page.header("Glossary", allow_all=False)
ts = data.titles()
cfg = ts.get(season, {})
MODEN = {"HP": "Hardpoint", "SND": "Search and Destroy", "OVL": "Overload", "HJ": "Hijack"}

ui.html(ui.note("What every stat on the site means and how it's calculated. The season picker changes the modes and MAR values shown, since each game has its own.", 0, 15))
jumps = [("mar", "MAR"), ("core", "Core Stats"), ("hp", "Hardpoint"), ("snd", "Search and Destroy"), ("ovl", "Overload"),
         ("radar", "Playstyle Radar"), ("proj", "Projections"), ("ocr", "Screenshot Entry"), ("other", "Other Terms")]
# jump links styled as the site's boxed buttons
ui.html(f"<style>.cb-gjump a{{color:{ui.INK} !important; text-decoration:none !important; min-height:40px; display:inline-flex; align-items:center; "
        f"padding:0 14px; border:1px solid {ui.RULE}; border-radius:2px; background:transparent; box-sizing:border-box}}"
        f".cb-gjump a:hover{{border-color:{ui.INK}; background:{ui.PANEL}}}html{{scroll-behavior:smooth}}</style>"
        f"<nav class='cb-gjump' style='display:flex; flex-wrap:wrap; gap:8px; margin-top:18px; font-size:14px'>"
        + "".join(f"<a href='#{i}' target='_self'>{l}</a>" for i, l in jumps) + "</nav>")


def note_ink(text, top=8, size=15):
    return f"<p style='margin:{top}px 0 0; font-size:{size}px; line-height:1.55; max-width:720px'>{text}</p>"


def section(id_, title, rule=False):
    return f"<section id='{id_}' style='scroll-margin-top:60px'>" + ui.h2(title, margin_top=56, rule=rule)


# ------------------------------------------------------------------ MAR
src_id = season if cfg.get("calibrated", True) else cfg.get("borrow_from")
src = ts.get(src_id, {})
ver = (src.get("mar_versions") or [{}])[-1] or src.get("mar", {})
e = data.engine(src_id) if src_id else None
attrs = {}
if e is not None and not e.empty:
    base = e.pm.drop(columns=["ke", "kpw", "mar", "c_net", "c_obj", "c_play", "c_repl"], errors="ignore")
    attrs = marmod.compute(base, src).attrs
avg = attrs.get("avg3", {})
modes = ver.get("modes", {})
steps = [("Net kills", "Kills minus deaths for the map."),
         ("Add objective and playmaking", "Objective stats (hill time, overloads, carrier kills, plants) and playmaking (assists, opening duels, kills as carrier) "
                                          "become kill-equivalents (KE), compared with the average for that mode and lobby size."),
         ("Compare to a fill-in", "Subtract what a replacement-level player produces in that mode. This is the Replacement Credit row on each Player Dashboard."),
         ("Convert to map wins", "Divide by how many KE it takes to swing one map in that mode.")]
stp = "".join(f"<div style='padding:14px 0; border-bottom:1px solid {ui.RULE}'><div style='font-size:11px; font-weight:600; letter-spacing:0.6px; color:{ui.BLUE}; "
              f"text-transform:uppercase'>Step {i + 1}</div><div style='font-size:16px; font-weight:600; margin-top:4px'>{t}</div>"
              f"<div style='font-size:14px; color:{ui.MUTED}; margin-top:4px; line-height:1.5'>{b}</div></div>" for i, (t, b) in enumerate(steps))
html = (section("mar", "MAR · Maps Above Replacement")
        + note_ink("Map wins a player added over a fill-in. A MAR of +1.0 means about one extra map won. It's the CB League version of baseball's WAR, "
                  "and the top MAR in a series is that series' MVP.", 8, 15)
        + note_ink(f"MAR combines slaying, objective play and playmaking into one number, calibrated on real {src.get('short', '')} results.", 8, 15)
        + "<div style='display:grid; grid-template-columns:repeat(auto-fit, minmax(min(100%, 180px), 1fr)); column-gap:24px; "
          f"border-top:2px solid {ui.INK}; margin-top:16px'>{stp}</div>")

if not cfg.get("calibrated", True):
    html += ui.empty_box(f"{cfg.get('name', season)} isn't calibrated yet",
                         f"MAR starts from {src.get('name', 'last season')}'s values and blends in {cfg.get('name', 'this season')}'s own as maps are played, "
                         f"reaching an even mix at {cfg.get('provisional_maps', 8)} maps per mode. A brand-new mode borrows the closest mode's values "
                         "(Overload for Hijack) and shows a Provisional tag until then. Conversions for any new mode are set in the season's settings once "
                         "its scoreboard is known. The values below are the ones being borrowed.")

if modes:
    f2 = lambda v: f"{v:.2f}"  # noqa: E731
    a = avg.get("a", {})
    conv = [("Net kill (kills − deaths)", "Base unit", "Slaying · every mode", "—")]
    if "HP" in modes:
        conv.append(("Hill time", f"{modes['HP'].get('hill_sec_per_kill', 2.5):g} sec = 1 kill", "Objective · Hardpoint", ui.mmss(avg.get("hill", {}).get("HP", 0))))
    if "OVL" in modes:
        m = modes["OVL"]
        conv += [("Overload", f"{m.get('overload', 3):g} kills", "Objective · Overload", f2(avg.get("ovl", {}).get("OVL", 0))),
                 ("Carrier kill", f"+{m.get('carrier_kill', 1.5):g} kills", "Objective · Overload", f2(avg.get("ck", {}).get("OVL", 0)))]
    if "SND" in modes:
        conv.append(("Plant", f"{modes['SND'].get('plant', 1):g} kill", "Objective · Search and Destroy", f2(avg.get("pl", {}).get("SND", 0))))
    conv.append(("Assist", f"{ver.get('assist', 0.25):g} kill", "Playmaking · every mode",
                 " · ".join(f"{a[k]:.1f} {({'HP': 'HP', 'SND': 'SnD', 'OVL': 'OVL'}).get(k, k)}" for k in ("HP", "SND", "OVL") if k in a)))
    if "SND" in modes:
        conv.append(("First-blood margin", f"{modes['SND'].get('fb_margin', 0.5):g} kill", "Playmaking · Search and Destroy", ui.sg(avg.get("fbn", {}).get("SND", 0), 2)))
    if "OVL" in modes:
        conv.append(("Kill as carrier", f"{modes['OVL'].get('kill_as_carrier', 1):g} kill", "Playmaking · Overload", f2(avg.get("kac", {}).get("OVL", 0))))
    rows = "".join(f"<div style='display:grid; grid-template-columns:minmax(0,1fr) auto; gap:2px 12px; padding:11px 0; border-bottom:1px solid {ui.RULE}'>"
                   f"<span style='font-size:14px; font-weight:600'>{s}</span><span style='font-size:14px; font-weight:600; text-align:right; color:{ui.BLUE}'>{w}</span>"
                   f"<span style='font-size:12px; color:{ui.MUTED}'>{m}</span><span style='font-size:12px; color:{ui.MUTED}; text-align:right'>3v3 avg {v}</span></div>"
                   for s, w, m, v in conv)
    rep = attrs.get("replacement", {})
    pm_rows = [[MODEN.get(k, k), f"{rep.get(k, m.get('replacement', 0)):.1f}".replace("-", "−"), f"{m.get('kpw', 0):.1f}"] for k, m in modes.items()]
    kp = {k: m.get("kpw", 0) for k, m in modes.items()}
    ratio = (kp["HP"] / kp["SND"]) if kp.get("SND") and kp.get("HP") else None
    k4 = attrs.get("kpw_4v4", {})
    four = ", ".join(f"{MODEN[k].replace('Search and Destroy', 'SnD')} {v:.1f}" for k, v in sorted(k4.items(), key=lambda x: -x[1]))
    # worked example: the season's top player, latest Hardpoint map
    ex = ""
    if e is not None and not e.empty and "HP" in modes:
        top = e.pm.groupby("player").mar.sum().idxmax()
        hp = e.pm[(e.pm.player == top) & (e.pm["mode"] == "HP") & (e.pm.team_size == 3)]
        if len(hp):
            r = hp.sort_values("seq").iloc[-1]; k = r.kpw
            ke = (r.c_net + r.c_obj + r.c_play) * k
            lines = [(f"Net kills ({int(r.kills)} − {int(r.deaths)})", ui.sg(r.c_net * k, 1), 400, ui.INK),
                     (f"Objective: hill time {ui.mmss(r.hill_time)} vs {ui.mmss(avg.get('hill', {}).get('HP', 0))} avg", ui.sg(r.c_obj * k, 1), 400, ui.INK),
                     (f"Playmaking: assists {int(r.assists) if r.assists == r.assists else '—'} vs {a.get('HP', 0):.1f} avg", ui.sg(r.c_play * k, 1), 400, ui.INK),
                     ("Kill-equivalents", f"{ke:.1f}", 500, ui.INK),
                     (f"Above replacement ({ke:.1f} + {r.c_repl * k:.1f})", f"{ke + r.c_repl * k:.1f}", 400, ui.INK),
                     (f"MAR ({ke + r.c_repl * k:.1f} ÷ {k:.1f})", ui.sg(r.mar, 2), 600, ui.BLUE)]
            ex = (f"<div style='margin-top:20px; padding:16px; background:{ui.PANEL}'><div style='font-size:11px; font-weight:600; letter-spacing:0.6px; "
                  f"text-transform:uppercase; color:{ui.MUTED}'>Worked example</div><div style='font-size:15px; font-weight:600; margin-top:4px'>"
                  f"{top} · Hardpoint on {r['map']} · Series {int(r.series_no)}</div>"
                  + "".join(f"<div style='display:flex; justify-content:space-between; gap:12px; padding:7px 0; border-bottom:1px solid {ui.RULE}; font-size:14px'>"
                            f"<span>{l}</span><span style='font-weight:{w}; color:{c}'>{v}</span></div>" for l, v, w, c in lines) + "</div>")
    html += ("<div style='display:grid; grid-template-columns:repeat(auto-fit, minmax(max(300px, 45%), 1fr)); gap:32px 48px; margin-top:32px'>"
             f"<div>{ui.label('Conversions · ' + src.get('name', ''))}<div style='border-top:2px solid {ui.INK}; margin-top:10px'>{rows}</div></div>"
             f"<div>{ui.label('Per mode · ' + src.get('name', ''))}"
             + ui.table([("Mode", "left"), ("Replacement KE", "right"), ("KE per map win", "right")], pm_rows, min_width=300)
             + (ui.note(f"A kill matters more where kills are scarce: one SnD kill is worth about {ratio:.1f} Hardpoint kills.", 8, 13) if ratio else "")
             + (f"<div style='margin-top:16px; padding:12px 14px; background:{ui.PANEL}; border-left:3px solid {ui.BLUE}'><div style='font-size:14px; font-weight:600'>4v4 maps</div>"
                + ui.note("Four players share the objective, so hill time, overloads, carrier kills, plants and kills as carrier are compared with three-quarters "
                          f"of the 3v3 average. 4v4 maps are also won by bigger margins, so a win takes more KE: {four}. These start from a simple estimate "
                          "and move toward the real 4v4 numbers as more 4v4 maps are played.", 4, 13) + "</div>" if four else "")
             + ex + "</div></div>")
ui.html(html + "</section>")

# ------------------------------------------------------------------ terms
T = lambda term, abbr, means, how="": (term, abbr, means, how)  # noqa: E731
groups = [
    ("core", "Core Stats", [
        T("K/D", "Kill/death ratio", "Kills divided by deaths.", "Always total kills over total deaths, never an average of each map’s K/D, so one huge map can’t skew it."),
        T("+/-", "Plus/minus", "Kills minus deaths.", "Positive means you got more kills than you gave up."),
        T("Non-traded kills", "NTK", "Kills the other team didn’t answer by immediately killing you back.", "Counted inside kills, so it isn’t added to MAR separately."),
        T("Damage", "Dmg", "Total damage dealt to enemies in a map.", "Mostly turns into kills, so MAR doesn’t count it separately to avoid double-counting."),
        T("Assists", "A", "Damaged an enemy that a teammate finished.", "Worth a quarter of a kill in MAR (Playmaking)."),
        T("Best streak", "Streak", "Most kills in a row without dying in a single map."),
        T("Match length", "mm:ss", "How long the map lasted, from the caster scoreboard. Recorded from Modern Warfare 4 on.",
          "Used for per-minute stats like fights per minute."),
        T("Fights per minute", "Engagements", "Kills plus deaths per minute: how often a player is in a fight.", "Needs match length, so it starts with MW4."),
        T("Fight win %", "", "Kills divided by kills plus deaths: the share of fights a player won.",
          "Carries the same information as K/D, on a 0–100% scale that pairs with fights per minute."),
        T("Finishing", "Kills above expected", "Kills per map beyond what a player’s damage usually turns into, using the league-wide damage-to-kills line for each mode.",
          "Positive means they finish their fights; negative means teammates often get the kill. Not added to MAR, since kills already count there.")]),
    ("hp", "Hardpoint", [
        T("Hill time", "Seconds on the hardpoint", "Time spent standing in the active hill. Teams score a point per second of control, first to 250.",
          "In MAR, 2.5 seconds of hill time is worth one net kill."),
        T("Objective kills", "Obj kills", "Kills on or around the active hill."),
        T("Average hill time", "Avg hill", "Average time on the hill per hill rotation, as shown on the caster scoreboard.", "Saved from the scoreboard; not part of MAR."),
        T("Contested hill time", "Contested", "Time spent on the hill while an enemy was on it too, so neither team was scoring.", "Saved from the scoreboard; not part of MAR."),
        T("Kills per hill", "K/hill", "Kills per hill rotation, as the caster scoreboard shows it.",
          "Saved exactly as shown: the game's own formula isn't simply total kills divided by hills, so the site doesn't recalculate it."),
        T("Damage per hill", "Dmg/hill", "Damage per hill rotation, as the caster scoreboard shows it.", "Saved exactly as shown, like kills per hill.")]),
    ("snd", "Search and Destroy", [
        T("First bloods", "FB", "Got the first kill of a round, opening a 4v3 (or 3v2)."),
        T("First deaths", "FD", "Died first in a round. Lower is better."),
        T("First-blood margin", "FB ±", "First bloods minus first deaths.", "In MAR (Playmaking), each net first blood is worth half a kill."),
        T("Plants", "Bomb plants", "Bombs planted.", "In MAR (Objective), each plant is worth one kill."),
        T("Defuses", "Bomb defuses", "Bombs defused.", "Saved from the scoreboard; not part of MAR."),
        T("Kills per round", "K/round", "Kills divided by rounds played (both teams' rounds won added together).",
          "The scoreboard cuts it to two decimals, so 6 kills in 7 rounds shows as 0.85."),
        T("Damage per round", "Dmg/round", "Damage divided by rounds played.")]),
    ("ovl", "Overload", [
        T("Overloads", "OVL", "Scored by carrying the device into the enemy goal.", "In MAR, each overload is worth three kills."),
        T("Carrier kills", "CK", "Kills on the enemy carrier, stopping a possible score.", "In MAR, each is worth an extra 1.5 kills on top of the kill itself."),
        T("Kills as carrier", "KAC", "Kills while carrying the device.", "In MAR (Playmaking), each is worth an extra kill.")]),
    ("radar", "Playstyle Radar", [
        T("Slaying", "Spoke", "Kills, K/D and damage per map combined."),
        T("Objective", "Spoke", "Hill time (counts double) and overloads. Carrier kills count toward Defense instead."),
        T("Playmaking", "Spoke", "Plays that create an advantage: first bloods, plants and kills while carrying the overload."),
        T("Defense", "Spoke", "Stopping the other team: carrier kills, kills that weren’t traded back, and staying alive."),
        T("Clutch", "Spoke", "How much better a player’s MAR is on pressure maps than on other maps. Pressure maps: a team can clinch the series, "
                             "or the map was close (Hardpoint by 25 or fewer, SnD 6–5, Overload by 1)."),
        T("Steadiness", "Spoke", "How rarely a player has a bad night (70%) plus how often they have a good one (30%). A bad night is a map well below your own norm "
                                 "and below the league’s typical map. A quiet night that’s still above league level doesn’t count against you.",
          "Small samples are pulled lightly toward the league average."),
        T("Archetype", "", "A one-line identity built from each player’s own strongest areas across every stat and mode, recalculated every season."),
        T("Signature chips", "", "Stats where a player ranks #1 or #2 among the regulars that season.")]),
    ("proj", "Projections", [
        T("Expected", "Projection", "The average of 20,000 simulated maps for that player on that map, built from their map history blended with their whole mode history.",
          "Map history counts more as it builds up: 1 game gives it 17%, 5 games 50%, 10 games 67%."),
        T("Likely range", "8 in 10", "Where 8 of every 10 simulated maps land. For small whole-number stats (first bloods, overloads) it is the narrowest range "
                                     "that still covers at least 8 in 10."),
        T("Chance to reach", "", "The share of simulated maps at or above a target you pick, like 40+ kills."),
        T("Confidence", "Low · Medium · High", "How many maps the player has in this mode: Low under 5, Medium 5 to 9, High 10 or more.",
          "Mode history drives most of every projection, so it sets the label rather than games on one map."),
        T("Track record", "", "Second-half maps re-projected using only earlier games, then compared with what actually happened.")]),
    ("ocr", "Screenshot Entry", [
        T("Fill From Screenshot", "Scorekeeper", "Fills in a whole map from a picture of the Codcaster scoreboard: mode, map, score, game time and every player's stats.",
          "Works for Hardpoint and Search and Destroy, 3v3 and 4v4, in Modern Warfare 4 and Black Ops 7. Hijack follows once its scoreboard is available."),
        T("OCR", "Optical character recognition", "Software that reads text from a picture. The site uses Tesseract, a free, open-source OCR engine that runs on "
                                                  "the site's own server, so screenshots never go to an outside service.",
          "Tesseract only reads characters. Finding the board, knowing which number belongs to which stat, and checking the results is done by the site."),
        T("How a board is read", "", "The site finds the scoreboard by its two colored team lines (Alpha and Bravo), then reads each column from its known "
                                     "position. Every cell is enlarged and cleaned up first, and each column may only contain the characters that fit it: "
                                     "digits for damage, a slash for kills/deaths, a colon for times.",
          "Because it's measured from the team lines, any screenshot size or crop works as long as the whole scoreboard is in the picture. A full-size PNG "
          "(1920 × 1080 or larger) reads best."),
        T("Yellow cells", "Needs a look", "A number the reader wasn't sure of. Each one shows its reason on hover, and fixing the number clears it.",
          "Reasons: faint (Tesseract reported low confidence), two readings disagree (a second pass with different image settings read something else), "
          "couldn't read it, or doesn't add up (see the next term)."),
        T("Math checks", "", "Numbers are checked against each other: non-traded kills and best streak can't exceed kills, average hill time can't exceed "
                             "hill time, and on a final scoreboard one team should be on 250 (Hardpoint) or 6 (SnD).",
          "Search and Destroy gets the strongest check: kills per round and damage per round must match kills and damage divided by the rounds played, "
          "and first bloods and first deaths must each add up to the number of rounds. A misread number almost always breaks one of these."),
        T("Who Is Who", "Matching players", "Each scoreboard row is matched to a league player by their saved gamertags. Capitals, spaces, underscores "
                                            "and special characters are ignored, so small misreads still match.",
          "Rows that don't match (bots, or a gamertag that isn't saved yet) are picked from a dropdown. Within a session the site remembers those picks, "
          "so later maps with the same names fill in by themselves. Those picks are never saved to anyone's profile."),
        T("Mid-game scoreboard", "Warning", "A scoreboard captured before the map ended. Spotted by the streak column reading Current Streak instead of "
                                            "Highest Streak, and flagged before anything is filled in."),
        T("What's saved", "", "Only the numbers, after a person checks the review and presses Save, the same as typing them in. The screenshot itself "
                              "is never stored.")]),
    ("other", "Other Terms", [
        T("Series MVP", "Top MAR", "The player with the highest MAR in a series."),
        T("Fill-in / replacement", "", "A bad-but-playable game: the 20th-percentile performance in that mode. MAR measures everyone against it."),
        T("Small sample", "Tag", "Shown when a number is built on few maps (under 10 overall, under 5 in one mode), so it can swing a lot."),
        T("Rivalry", "", "Two exact lineups that have met at least twice. Tagged small sample until the third meeting."),
        T("Pressure map", "", "A map where one team could clinch the series, or one that finished close (Hardpoint by 25 or fewer, SnD 6–5, Overload by 1)."),
        T("Ended early", "Tag", "A series that stopped before either team reached the wins needed for its best-of.",
          "The Scorekeeper records the result when it ends: the leading team by default, or no result if it was tied.")])]
if "HJ" in (cfg.get("modes") or {}):
    groups.insert(4, ("hj", "Hijack", [T("Hijack", "HJ", "A new Modern Warfare 4 mode. Its stats and MAR values are set in the season's settings once its scoreboard is known; "
                                                    "until then it borrows Overload's values and shows a Provisional tag.")]))
out = ""
for gid, title, terms in groups:
    body = "".join(f"<div class='cb-term' style='display:grid; grid-template-columns:220px minmax(0,1fr); gap:6px 24px; padding:16px 0; border-bottom:1px solid {ui.RULE}'>"
                   f"<div><div style='font-size:16px; font-weight:600'>{t}</div><div style='font-size:12px; color:{ui.MUTED}; margin-top:2px'>{ab}</div></div>"
                   f"<div><p style='margin:0; font-size:14px; line-height:1.55'>{m}</p>"
                   + (f"<p style='margin:6px 0 0; font-size:13px; color:{ui.MUTED}; line-height:1.55'>{h}</p>" if h else "") + "</div></div>"
                   for t, ab, m, h in terms)
    out += section(gid, title) + f"<div style='border-top:2px solid {ui.INK}; margin-top:12px'>{body}</div></section>"
ui.html(out + "<style>@media (max-width:640px){.cb-term{grid-template-columns:minmax(0,1fr) !important}}</style>")