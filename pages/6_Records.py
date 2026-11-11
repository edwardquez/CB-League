"""Records & Awards: season awards and the record book."""
import pandas as pd
import streamlit as st

from cbl import data
from cbl.ui import page, styles as ui

page.start("Records")
season = page.header("Records & Awards")
tid = page.title_id(season)
e = data.engine(tid)
ts = data.titles()
MS = {"HP": "HP", "SND": "SnD", "OVL": "OVL", "HJ": "Hijack"}
MODEN = {"HP": "Hardpoint", "SND": "Search and Destroy", "OVL": "Overload", "HJ": "Hijack"}
MIN = 10

tab = st.segmented_control("View", ["awards", "records", "fun"], default="awards", key="ra_tab", label_visibility="collapsed",
                           format_func={"awards": "Awards", "records": "Records", "fun": "Fun Facts"}.get) or "awards"
if e.empty:
    ui.html(ui.empty_box(f"No {ts.get(season, {}).get('name', '')} records yet", "Records and awards fill in as series are entered."))
    st.stop()


def short(t):
    return ts.get(t, {}).get("short", t)


def join(names):
    names = list(names)
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " & " + names[-1]


def top2(sr: pd.Series, fmt, low=False):
    """(leaders, value, runner-up text) with ties."""
    sr = sr.dropna().sort_values(ascending=low)
    if sr.empty:
        return None
    best = sr.iloc[0]; lead = sr[(sr - best).abs() < 1e-9]
    rest = sr[~sr.index.isin(lead.index)]
    ru = f"Runner-up: {join(rest[(rest - rest.iloc[0]).abs() < 1e-9].index)} {fmt(rest.iloc[0])}" if len(rest) else ""
    return join(lead.index), fmt(best), ru


def awards_for(t):
    x = data.engine(t)
    pm = x.pm
    st_ = x.standings(); q = st_[st_.n >= MIN] if (st_.n >= MIN).any() else st_
    out = []
    a = top2(q.mar, ui.sg)
    if a:
        out.append(("Season MVP", a[0], a[1] + " MAR", a[2], True))
    for mo in [m for m in ["HP", "SND", "OVL", "HJ"] if m in set(pm["mode"])]:
        s = x.standings(mo); s = s[s.n >= 5] if (s.n >= 5).any() else s
        a = top2(s.mar, ui.sg)
        if a:
            out.append((f"Best in {MODEN[mo]}", a[0], a[1] + " MAR", a[2], False))
    mv = pd.Series([v[0] for v in x.series_mvps().values()]).value_counts()
    a = top2(mv.astype(float), lambda v: str(int(v)))
    if a:
        out.append(("Most series MVPs", a[0], a[1], a[2], False))
    a = top2(q.kd, lambda v: f"{v:.2f}")
    if a:
        out.append(("Best K/D", a[0], a[1], a[2], False))
    a = top2(q.wp, ui.pct)
    if a:
        lead = q.wp.idxmax(); r = q.loc[lead]
        out.append(("Best map win %", a[0], a[1], f"{int(r.w)}-{int(r.n - r.w)} · " + a[2].replace("Runner-up:", "runner-up"), False))
    hp = x.standings("HP")
    if not hp.empty and "hill" in hp:
        hp = hp[hp.n >= 5] if (hp.n >= 5).any() else hp
        a = top2(hp.hill, ui.mmss)
        if a:
            out.append(("Objective player", a[0], a[1], "Hill time per map · " + a[2].replace("Runner-up:", "runner-up"), False))
    return out


def improved(order):
    """Most Improved: change in MAR per map from the previous title (10+ maps in both)."""
    if len(order) < 2:
        return None
    a, b = order[-2], order[-1]
    sa, sb = data.engine(a).standings(), data.engine(b).standings()
    both = sa[sa.n >= MIN].index.intersection(sb[sb.n >= MIN].index)
    if not len(both):
        return None
    d = (sb.mpm - sa.mpm).loc[both]
    r = top2(d, lambda v: ui.sg(v, 2))
    return ("Most improved", r[0], r[1] + " MAR / map", f"vs {short(a)} · " + r[2].replace("Runner-up:", "runner-up"), False)


if tab == "awards":
    order = [t for t in sorted(ts, key=lambda t: ts[t].get("order", 0)) if not data.engine(t).empty]
    shown = order[::-1] if tid is None else [tid]
    ui.html(ui.note(f"Awards are calculated automatically from each season's games. Minimum {MIN} maps unless noted "
                    "(5 for mode awards). Most Improved joins once a second season is in.", 16, 14))
    for t in shown:
        x = data.engine(t); cfg = ts.get(t, {})
        days = (x.series.date.max() - x.series.date.min()).days if len(x.series) else 0
        early = days < 20 or len(x.maps) < 15
        if early:
            ui.html("<div style='margin-top:20px; padding:14px 16px; border-left:3px solid " + ui.BLUE + "; background:" + ui.PANEL + "'>"
                    "<div style='font-size:14px; font-weight:600'>Early season</div>"
                    + ui.note(f"Only {len(x.maps)} maps in, so awards and records can still change a lot. This note goes away once the season "
                              "is 20 days old and 15 maps have been played.", 4, 13) + "</div>")
        aw = awards_for(t)
        if t == order[-1] and t in order:
            m = improved(order[: order.index(t) + 1])
            if m:
                aw.append(m)
        cells = ""
        for name, who, val, ru, big in aw:
            tag = ui.tagbox("Early", ui.BLUE, ui.BLUE) if early else ""
            cells += (f"<div style='padding:18px 0; border-bottom:1px solid {ui.RULE}'><div style='font-size:12px; font-weight:600; letter-spacing:0.6px; "
                      f"text-transform:uppercase; color:{ui.BLUE if big else ui.MUTED}'>{name}{tag}</div>"
                      f"<div style='display:flex; justify-content:space-between; align-items:baseline; gap:12px; margin-top:8px; flex-wrap:wrap'>"
                      f"<span style='font-weight:300; font-size:{40 if big else 30}px; line-height:1.05'>{who}</span>"
                      f"<span style='font-size:19px; font-weight:500; color:{ui.BLUE}'>{val}</span></div>"
                      f"<div style='font-size:13px; color:{ui.MUTED}; margin-top:6px'>{ru}</div></div>")
        ui.html("<div style='display:flex; justify-content:space-between; align-items:baseline; gap:6px 16px; flex-wrap:wrap; margin-top:40px'>"
                f"<div role='heading' class='cb-h2' style='font-weight:400; font-size:32px; letter-spacing:-0.5px'>{cfg.get('name', t)} · {cfg.get('year', '')}</div>"
                f"<span style='font-size:13px; color:{ui.MUTED}'>{len(x.series)} series · {len(x.maps)} maps</span></div>"
                "<div style='display:grid; grid-template-columns:repeat(auto-fill, minmax(min(100%, 230px), 1fr)); column-gap:24px; "
                f"border-top:2px solid {ui.INK}; margin-top:12px'>{cells}</div>")
    st.stop()

# ------------------------------------------------------------------ fun facts
@st.cache_data(show_spinner=False, max_entries=8)
def fun_facts(t, v):
    from cbl.stats import funfacts
    d = data.load_docs()
    ser = [x for x in d["series"] if t is None or x["title"] == t]
    name = (lambda sid: f"Series {next(x['series_no'] for x in ser if x['_id'] == sid)}") if t else \
        (lambda sid: next(f"{short(x['title'])} Series {x['series_no']}" for x in ser if x["_id"] == sid))
    return funfacts.facts(d["player_matches"], d["matches"], ser, name)


if tab == "fun":
    import re
    from html import escape as E
    hero, rest = fun_facts(tid, data.version())
    if hero is None:
        ui.html(ui.empty_box("No Fun Facts yet", "They turn up once a few series are in."))
        st.stop()
    hl, roasts = [], 0
    for f in rest:
        if len(hl) == 9:
            break
        if f["tone"] == "roast":
            if roasts:
                continue
            roasts += 1
        hl.append(f)
    groups = {"Highlights": hl, **{g: [f for f in rest if f["group"] == g] for g in ["Players", "Head to Head", "Maps & Modes", "Streaks & Form", "Oddities"]}}
    groups = {k: v for k, v in groups.items() if v}
    pnames = sorted(set(e.pm.player), key=len, reverse=True)

    def who(t):   # player names stand out in the context line
        return re.sub(r"\b(" + "|".join(map(re.escape, pnames)) + r")\b", f"<b style='color:{ui.INK}; font-weight:600'>\\1</b>", E(t)) if pnames else E(t)
    tag = lambda f: (f"<span style='font-size:10px; font-weight:700; letter-spacing:.8px; text-transform:uppercase; color:{ui.on(ui.BLUE)}; "  # noqa: E731
                     f"background:{ui.BLUE}; padding:2px 6px; flex:none'>New</span>" if f["new"] else "")
    big = lambda t, size: f"<div style='font-size:{size}px; font-weight:300; line-height:1.2; letter-spacing:-.2px; text-wrap:balance'>{E(t)}</div>"  # noqa: E731
    line = lambda f, fs: f"<p style='margin:8px 0 0; font-size:{fs}px; color:{ui.MUTED}; line-height:1.5; text-wrap:pretty'>{who(f['line'])}</p>"  # noqa: E731
    ui.html(ui.note("The league's oddest numbers, updated after every series.", 16, 14)
            + f"<div class='cb-fig cb-rise' style='border-top:2px solid {ui.INK}; padding:22px 0 26px; margin-top:22px'>"
            f"<div style='display:flex; gap:10px; align-items:center'>{ui.label('Fact of the Season · ' + hero['title'])}{tag(hero)}</div>"
            f"<div style='margin-top:12px'>{big(hero['big'], 52)}</div>{line(hero, 16)}</div><div style='height:18px'></div>")
    g = ui.tabs("ff_tab", list(groups), {})
    cards = "".join(f"<div class='cb-fig cb-rise' style='border-top:2px solid {ui.INK}; padding:16px 0 20px; min-width:0; animation-delay:{.04 * min(i, 10):.2f}s'>"
                    f"<div style='display:flex; justify-content:space-between; align-items:center; gap:8px; min-height:18px'>"
                    f"<span class='cb-lab' style='font-size:11px; font-weight:600; letter-spacing:1.6px; text-transform:uppercase; color:{ui.MUTED}'>{E(f['title'])}</span>{tag(f)}</div>"
                    f"<div style='margin-top:10px'>{big(f['big'], 22)}</div>{line(f, 13)}</div>" for i, f in enumerate(groups[g]))
    last = max(e.series.series_no) if len(e.series) else 0
    ui.html(f"<div class='cb-ff' style='display:grid; grid-template-columns:repeat(auto-fill, minmax(min(100%, 250px), 1fr)); gap:4px 28px; margin-top:6px'>{cards}</div>"
            + ui.note(f"Through {'Series ' + str(last) if tid else 'the latest series'} · <b style='font-weight:600'>New</b> = changed last series", 14, 12)
            + "<style>@media (max-width:640px){.cb-ff{grid-template-columns:minmax(0,1fr) !important; row-gap:0 !important}}</style>")
    st.stop()

# ------------------------------------------------------------------ records
pm, S, M = e.pm, e.series, e.maps


def where(r):
    return f"{MS.get(r['mode'], r['mode'])} {r['map']} · {short(r['title'])} Series {int(r['series_no'])}"


def single(col, label, fmt=lambda v: f"{int(v):,}", d=None, extra=lambda r: ""):
    d = (pm if d is None else d).dropna(subset=[col])
    if d.empty:
        return None
    best = d[col].max(); hits = d[(d[col] - best).abs() < 1e-9]
    r = hits.iloc[0]
    who = join(sorted(hits.player.unique()))
    if len(hits) > 1:
        return (label, fmt(best), who, f"done {len(hits)} times · first by {r.player}, {extra(r)}{where(r)}")
    return (label, fmt(best), who, extra(r) + where(r))


pm = pm.copy(); pm["kd"] = pm.kills / pm.deaths.clip(lower=1)
g1 = [single("kills", "Most kills"), single("highest_streak", "Longest streak"), single("damage", "Most damage"),
      single("kd", "Best K/D (10+ kills)", lambda v: f"{v:.2f}", pm[pm.kills >= 10], lambda r: f"{int(r.kills)}-{int(r.deaths)} · "),
      single("mar", "Highest MAR", lambda v: ui.sg(v, 2)), single("hill_time", "Most hill time", ui.mmss),
      single("first_bloods", "Most first bloods"), single("overloads", "Most overloads"), single("carrier_kills", "Most carrier kills")]

sg_ = pm.groupby(["series_id", "player"]).agg(k=("kills", "sum"), d=("deaths", "sum"), dmg=("damage", "sum"), mar=("mar", "sum"),
                                              n=("mar", "size"), title=("title", "first"), no=("series_no", "first")).reset_index()
sg_["kd"] = sg_.k / sg_.d.clip(lower=1)


def ser(col, label, fmt, d=None):
    d = sg_ if d is None else d
    if d.empty:
        return None
    r = d.loc[d[col].idxmax()]
    return (label, fmt(r[col]), r.player, f"{short(r.title)} Series {int(r.no)} · {int(r.n)} maps")


g2 = [ser("k", "Most kills", lambda v: f"{int(v):,}"), ser("dmg", "Most damage", ui.n0), ser("mar", "Highest MAR", lambda v: ui.sg(v, 2)),
      ser("kd", "Best K/D (3+ maps)", lambda v: f"{v:.2f}", sg_[sg_.n >= 3])]

sw = S[((S.wins_a == 0) | (S.wins_b == 0)) & (S.maps_played > 0)]
g3 = []
if len(sw):
    g3.append(("Sweeps", str(len(sw)), "Series " + ", ".join(str(int(n)) for n in sw.series_no) if tid else f"{len(sw)} series",
               short(tid) if tid else "every title"))
lg = S.loc[S.maps_played.idxmax()]
g3.append(("Longest series", f"{int(lg.maps_played)} maps", f"Series {int(lg.series_no)}", f"{max(lg.wins_a, lg.wins_b)}-{min(lg.wins_a, lg.wins_b)} · {short(lg.title)}"))
for mo, nm in (("HP", "Hardpoint"), ("OVL", "Overload")):
    mm = M[M["mode"] == mo].copy()
    if mm.empty:
        continue
    mm["gap"] = (mm.score_a - mm.score_b).abs()
    c = mm.loc[mm.gap.idxmin()]; b = mm.loc[mm.gap.idxmax()]
    sc = lambda r: f"{max(r.score_a, r.score_b)}-{min(r.score_a, r.score_b)}"  # noqa: E731
    sno = S.set_index("_id").series_no
    g3.append((f"Closest {nm}", sc(c), f"Series {int(sno[c.series_id])}", f"{c['map']} · {short(c.title)}"))
    g3.append((f"Biggest {nm} blowout", sc(b), f"Series {int(sno[b.series_id])}", f"{b['map']} · {short(b.title)}"))


def car(col, label, fmt, d=None, note=lambda p, x: f"{len(x[x.player == p])} maps"):
    d = pm if d is None else d
    d = d.dropna(subset=[col])
    if d.empty:
        return None
    t = d.groupby("player")[col].sum(); best = t.max(); lead = t[(t - best).abs() < 1e-9].index
    return (label, fmt(best), join(sorted(lead)), "tied" if len(lead) > 1 else note(lead[0], d))


n = pm.groupby("player").size()
mp_lead = n[n == n.max()].index
g4 = [car("kills", "Kills", lambda v: f"{int(v):,}"), car("damage", "Damage", ui.n0),
      ("Maps played", str(int(n.max())), join(sorted(mp_lead)), "tied" if len(mp_lead) > 1 else ""),
      car("hill_time", "Time on the hill", lambda v: f"{int(v // 60)}:{int(v % 60):02d}", pm[pm["mode"] == "HP"], lambda p, x: f"{len(x[x.player == p])} Hardpoint maps"),
      car("first_bloods", "First Bloods", lambda v: str(int(v)), pm[pm["mode"] == "SND"], lambda p, x: f"{len(x[x.player == p])} SnD maps"),
      car("overloads", "Overloads", lambda v: str(int(v)), pm[pm["mode"] == "OVL"], lambda p, x: f"{len(x[x.player == p])} Overload maps")]

suffix = "" if tid is None else f" · {ts.get(tid, {}).get('name', tid)}"
groups = [("Single-map records", "Best performance in one map" + suffix, g1), ("Series records", "One player, one series" + suffix, g2),
          ("Team records", "Lineups and results" + suffix, g3),
          ("Career leaders" if tid is None else "Season leaders", "Totals across every title" if tid is None else "Season totals" + suffix, g4)]
for title, sub, rows in groups:
    body = ""
    for r in [x for x in rows if x]:
        body += (f"<div class='cb-rec' style='display:grid; grid-template-columns:minmax(0,220px) 140px minmax(0,1fr); gap:4px 16px; align-items:baseline; "
                 f"padding:14px 0; border-bottom:1px solid {ui.RULE}'><span style='font-size:14px; color:{ui.MUTED}'>{r[0]}</span>"
                 f"<span class='cb-rec-v' style='font-weight:300; font-size:28px; line-height:1; color:{ui.BLUE}'>{r[1]}</span>"
                 f"<span class='cb-rec-w' style='font-size:15px'><b style='font-weight:600'>{r[2]}</b> <span style='color:{ui.MUTED}; font-size:13px'>{r[3]}</span></span></div>")
    ui.html("<div style='display:flex; justify-content:space-between; align-items:baseline; gap:6px 16px; flex-wrap:wrap; margin-top:48px'>"
            f"<div role='heading' class='cb-h2' style='font-weight:400; font-size:32px; letter-spacing:-0.5px'>{title}</div>"
            f"<span style='font-size:13px; color:{ui.MUTED}'>{sub}</span></div><div style='border-top:2px solid {ui.INK}; margin-top:12px'>{body}</div>")
ui.html("<style>@media (max-width:640px){.cb-rec{grid-template-columns:minmax(0,1fr) auto !important}.cb-rec-v{text-align:right}"
        ".cb-rec-w{grid-column:1 / -1}}</style>")