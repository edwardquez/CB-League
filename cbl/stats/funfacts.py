"""Fun Facts: fact finders run over the league's games. Every fact is computed (nothing typed in by hand), must clear a
minimum sample, is scored by how unlikely it is, and ranked so no one player crowds the list. The Fact of the Season is
always a compliment. Used by the Records page (Fun Facts tab)."""
from __future__ import annotations

import datetime as dt
import itertools
import math
from collections import Counter, defaultdict

MODE = {"HP": "Hardpoint", "SND": "SnD", "OVL": "Overload", "HJ": "Hijack"}
GROUPS = ["Highlights", "Players", "Head to Head", "Maps & Modes", "Streaks & Form", "Oddities"]
HIGHLIGHTS = 9


def lg(p):
    return -math.log10(max(p, 1e-12))


def tail(k, n, p):
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))


def mmss(s):
    return f"{s // 60}:{s % 60:02d}"


def num(v):
    if v is None or v in ("None", ""):
        return None
    try:
        if v != v:            # NaN
            return None
    except Exception:
        pass
    return int(v)


def facts(player_matches: list[dict], matches: list[dict], series: list[dict], name=None):
    """(hero, rest) for these games; name(series_id) -> how a series is named ("Series 6", or "BO7 Series 6" across titles).
    Returns (None, []) when there's too little to say."""
    PM = [r for r in player_matches if r.get("series_id") in {s["_id"] for s in series}]
    MT = {m["_id"]: m for m in matches}; SER = {s["_id"]: s for s in series}
    PM = [r for r in PM if r.get("match_id") in MT]
    if len(PM) < 20:
        return None, []
    order_of = {sid: i for i, sid in enumerate(sorted(SER, key=lambda k: (SER[k]["date"], SER[k]["series_no"])))}
    SNO = lambda sid: order_of[sid]  # noqa: E731
    NAME = name or (lambda sid: f"Series {SER[sid]['series_no']}")
    DATE = lambda sid: dt.date.fromisoformat(str(SER[sid]["date"])[:10])  # noqa: E731
    LATEST = max(SER, key=SNO)
    MODE_ = lambda m: MODE.get(m, m)  # noqa: E731
    out = []

    def add(group, title, big, line, score, who="", tone="neu", ev=()):
        out.append(dict(group=group, title=title, big=big, line=line, score=score, who=who, tone=tone, ev=list(ev)))
    players = sorted({r["player"] for r in PM})
    maps_of = Counter(r["player"] for r in PM)
    regulars = [p for p in players if maps_of[p] >= 20]
    bym = defaultdict(list)
    for r in PM: bym[r["match_id"]].append(r)
    full = [r for r in PM if num(r["kills"]) is not None]
    def total(p, k, mode=None):
        v = [num(r[k]) for r in PM if r["player"] == p and (mode is None or r["mode"] == mode) and num(r[k]) is not None]
        return sum(v), len(v)
    kd_of = lambda rs: sum(num(r["kills"]) or 0 for r in rs) / max(sum(num(r["deaths"]) or 0 for r in rs), 1)
    career = {p: kd_of([r for r in PM if r["player"] == p]) for p in players}

    # ================= Players
    try:
        tot = defaultdict(lambda: defaultdict(lambda: [0, 0, None]))
        for r in PM:
            t = tot[r["series_id"]][r["player"]]; t[0] += num(r["kills"]) or 0; t[1] += num(r["deaths"]) or 0; t[2] = r["team"]
        pos = lambda s, p: tot[s][p][0] > tot[s][p][1]
        base_pos = sum(pos(s, p) for s in tot for p in tot[s]) / sum(len(tot[s]) for s in tot)
        nomate = [not any(pos(s, q) for q in tot[s] if q != p and tot[s][q][2] == tot[s][p][2]) for s in tot for p in tot[s]]
        base_nomate = sum(nomate) / len(nomate)
        for p in players:
            ss = sorted((s for s in tot if p in tot[s]), key=SNO); n = len(ss)
            if n < 3: continue
            if not any(any(pos(s, q) for q in tot[s] if q != p and tot[s][q][2] == tot[s][p][2]) for s in ss):
                add("Players", "Carrying Every Time", f"{n} of {n} Series", f"{p} finished positive in all {n}. Not one teammate ever did.", n * lg(base_nomate), p, "pos", ss)
            if all(pos(s, p) for s in ss) and n >= 5:
                w = min(ss, key=lambda s: tot[s][p][0] - tot[s][p][1])
                add("Players", "Never a Negative Series", f"{n} for {n} Positive Series", f"{p} has more kills than deaths in every series. Closest call: {tot[w][p][0]}–{tot[w][p][1]}.", n * lg(base_pos), p, "pos", ss)
            if not any(pos(s, p) for s in ss) and n >= 5:
                c = max(ss, key=lambda s: tot[s][p][0] - tot[s][p][1])
                add("Players", "Still Chasing a Positive Series", f"0 for {n}", f"{p} came closest in {NAME(c)}, at {tot[c][p][0]}–{tot[c][p][1]}.", n * lg(1 - base_pos) * .7, p, "roast", ss)
        lead, last, played = Counter(), Counter(), Counter()
        for m, rs in bym.items():
            rs = [r for r in rs if num(r["kills"]) is not None]
            if len(rs) < 4: continue
            mx = max(num(r["kills"]) for r in rs); mn = min(num(r["kills"]) for r in rs)
            for r in rs: played[r["player"]] += 1; lead[r["player"]] += num(r["kills"]) == mx; last[r["player"]] += num(r["kills"]) == mn
        for p in regulars:
            if last[p] == 0:
                add("Players", "Never Bottom of the Lobby", f"0 Last Places in {played[p]} Maps", f"{p} has never had the fewest kills, and had the most on {lead[p]} of them.", played[p] * lg(5 / 6), p, "pos")
        hill = {p: (lambda s, n: s / n if n >= 8 else None)(*total(p, "hill_time", "HP")) for p in regulars}
        hill = {p: v for p, v in hill.items() if v}
        if hill:
            p = max(hill, key=hill.get); nxt = sorted(hill.values())[-2]
            add("Players", "Hill King", f"{mmss(round(hill[p]))} Per Hardpoint", f"{p} holds the hill longer than anyone. Next best is {mmss(round(nxt))}.", 2.2 + (hill[p] - nxt) / 15, p, "pos")
        ast = {p: total(p, "assists")[0] / max(total(p, "kills")[0], 1) for p in regulars}; p = max(ast, key=ast.get)
        add("Players", "The Setup Man", f"{ast[p]:.2f} Assists Per Kill", f"{p} sets up teammates more than any regular. League average: {sum(ast.values()) / len(ast):.2f}.", 1.9, p, "pos")
        pl = {p: total(p, "bombs_planted", "SND")[0] for p in regulars}; p = max(pl, key=pl.get)
        add("Players", "Bomb Carrier", f"{pl[p]} Bomb Plants", f"The most SnD plants in the league. {p} gets the bomb down.", 1.7, p, "pos")
        ov = {p: total(p, "overloads", "OVL")[0] for p in regulars}; p = max(ov, key=ov.get)
        add("Players", "Overload Specialist", f"{ov[p]} Overloads", f"The most in the league. {p} finishes the job.", 1.6, p, "pos")
        best = max(((v[0] / sum(tot[s][q][0] for q in tot[s] if tot[s][q][2] == v[2]), p, s, sum(1 for q in tot[s] if tot[s][q][2] == v[2]))
                    for s in tot for p, v in tot[s].items()), key=lambda x: x[0])
        if best[0] >= .45:
            add("Players", "Half the Team's Kills", f"{round(best[0] * 100)}% of Team Kills", f"{best[1]} in {NAME(best[2])}, a {best[3]}v{best[3]}. An even share is {round(100 / best[3])}%.", 2.6, best[1], "pos", [best[2]])
        fb = defaultdict(lambda: [0, 0])
        for r in PM:
            if r["mode"] == "SND" and num(r["first_bloods"]) is not None:
                fb[r["player"]][0] += num(r["first_bloods"]); fb[r["player"]][1] += num(r["first_deaths"]) or 0
        cand = [(v[0] / sum(v), p, v) for p, v in fb.items() if sum(v) >= 30]
        if cand:
            r_, p, (a, b) = max(cand)
            add("Players", "First Blood Specialist", f"{round(r_ * 100)}% of Opening Duels Won", f"{p} wins the first fight of an SnD round: {a} first bloods, {b} first deaths.", lg(tail(a, a + b, .5)), p, "pos")
            r_, p, (a, b) = min(cand)
            add("Players", "First In, First Out", f"{b} First Deaths, {a} First Bloods", f"{p} loses the opening SnD fight {round((1 - r_) * 100)}% of the time.", lg(1 - tail(a + 1, a + b, .5)) * .7, p, "roast")

    except (ValueError, IndexError, KeyError, ZeroDivisionError, StopIteration, TypeError):   # too little data for this group
        pass

    # ================= Head to Head
    try:
        duel = defaultdict(lambda: [0, 0, 0])
        for m, rs in bym.items():
            for a, b in itertools.permutations(rs, 2):
                if a["team"] != b["team"] and num(a["kills"]) is not None and num(b["kills"]) is not None:
                    duel[(a["player"], b["player"])][0 if num(a["kills"]) > num(b["kills"]) else 1 if num(a["kills"]) < num(b["kills"]) else 2] += 1
        rate = {p: (lambda W, L: W / max(W + L, 1))(sum(v[0] for (x, _), v in duel.items() if x == p), sum(v[1] for (x, _), v in duel.items() if x == p)) for p in players}
        for (a, b), (w, l, t) in duel.items():
            if (l == 0 and w + l >= 10) or (l == 1 and w + l >= 25):
                add("Head to Head", "One-Sided Rivalry", f"{w}–{l} in Kills vs {b}", f"On opposite teams, {a} has out-killed {b} on {w} of {w + l + t} maps.", lg(tail(w, w + l, rate[a])), a, "pos")
        res = defaultdict(list)
        for m, rs in bym.items():
            for r in rs:
                mates = {q["player"] for q in rs if q["team"] == r["team"] and q["player"] != r["player"]}
                for q in players:
                    if q != r["player"]: res[(r["player"], q, q in mates)].append(r["result"] == "W")
        gaps = [((sum(a) / len(a) - sum(b) / len(b)) / math.sqrt(.25 / len(a) + .25 / len(b)), p, q, a, b)
                for p in players for q in players if p != q for a, b in [(res[(p, q, True)], res[(p, q, False)])] if len(a) >= 8 and len(b) >= 8]
        if gaps:
            z, p, q, a, b = max(gaps)
            add("Head to Head", "Better Together", f"{sum(a)}–{len(a) - sum(a)} With {q}", f"{p}'s map record with {q} on the team. Without: {sum(b)}–{len(b) - sum(b)}.", z * 1.1, p, "pos")
        pair = defaultdict(lambda: [0, 0])
        for m, rs in bym.items():
            for side in "AB":
                team = sorted(r["player"] for r in rs if r["team"] == side)
                if team:
                    rr = [r["result"] for r in rs if r["team"] == side][0]
                    for a, b in itertools.combinations(team, 2): pair[(a, b)][0 if rr == "W" else 1] += 1
        ok = [(w / (w + l), a, b, w, l) for (a, b), (w, l) in pair.items() if w + l >= 10]
        hi = max(ok)
        add("Head to Head", "Best Duo", f"{hi[1]} + {hi[2]}: {hi[3]}–{hi[4]}", f"Wins {round(hi[0] * 100)}% of maps together, the best of any pair with 10+ maps.", abs(hi[0] - .5) / math.sqrt(.25 / (hi[3] + hi[4])) * 1.2, hi[1], "pos")
        # player vs player map record (on opposite sides)
        vs = defaultdict(lambda: [0, 0])
        for m, rs in bym.items():
            for a, b in itertools.permutations(rs, 2):
                if a["team"] != b["team"]: vs[(a["player"], b["player"])][0 if a["result"] == "W" else 1] += 1
        nem = [(w / (w + l), a, b, w, l) for (a, b), (w, l) in vs.items() if w + l >= 10]
        hi = max(nem)
        add("Head to Head", "Has Their Number", f"{hi[3]}–{hi[4]} vs {hi[2]}", f"{hi[1]}'s map record with {hi[2]} on the other side.", abs(hi[0] - .5) / math.sqrt(.25 / (hi[3] + hi[4])), hi[1], "pos")

    except (ValueError, IndexError, KeyError, ZeroDivisionError, StopIteration, TypeError):   # too little data for this group
        pass

    # ================= Maps & Modes
    try:
        rec = defaultdict(lambda: [0, 0, []])
        for r in PM: x = rec[(r["player"], r["mode"], r["map"])]; x[0 if r["result"] == "W" else 1] += 1; x[2].append(r)
        for (p, mo, mp), (w, l, rs) in rec.items():
            if l == 0 and w >= 3:
                k = kd_of(rs)
                if w >= 4 or k >= 2:
                    add("Maps & Modes", f"Owns {MODE_(mo)} {mp}", f"{w}–0 on {mp}" + (f", {k:.1f} K/D" if k >= 1.5 else ""), f"{p} has never lost {MODE_(mo)} there" + (f", going {sum(num(r['kills']) or 0 for r in rs)}–{sum(num(r['deaths']) or 0 for r in rs)}." if k >= 1.5 else "."), w * lg(.5) + max(k - 1.5, 0), p, "pos")
        for (p, mo, mp), (w, l, rs) in rec.items():
            if l == 0 and w >= 3:
                for (q, mo2, mp2), (w2, l2, _) in rec.items():
                    if (mo2, mp2) == (mo, mp) and q != p and w2 == 0 and l2 >= 3:
                        add("Maps & Modes", f"Opposites on {MODE_(mo)} {mp}", f"{p} {w}–0, {q} 0–{l2}", f"One has never lost there; the other has never won.", (w + l2) * lg(.5) * .7, p, "neu")
        # kills don't win it: strong K/D, poor record on a map
        puzzles = [(w / (w + l), kd_of(rs), p, mo, mp, w, l) for (p, mo, mp), (w, l, rs) in rec.items() if w + l >= 5 and kd_of(rs) >= 1.3 and w / (w + l) <= .25]
        if puzzles:
            _, k, p, mo, mp, w, l = min(puzzles)
            add("Maps & Modes", f"The {mp} Puzzle", f"{w}–{l} on {MODE_(mo)} {mp}", f"{p} goes {k:.2f} K/D there and still keeps losing it.", 2.0, p, "neu")
        # best mode by win %
        mrec = defaultdict(lambda: [0, 0])
        for r in PM: mrec[(r["player"], r["mode"])][0 if r["result"] == "W" else 1] += 1
        mb = [(lg(tail(w, w + l, .5)), p, mo, w, l) for (p, mo), (w, l) in mrec.items() if w + l >= 15]
        if mb:
            sc, p, mo, w, l = max(mb)
            add("Maps & Modes", f"{MODE_(mo)} Specialist", f"{w}–{l} in {MODE_(mo)}", f"{p}'s best mode by far. Every other mode: " + (lambda o: f"{o[0]}–{o[1]}.")([sum(v[0] for (q, m_), v in mrec.items() if q == p and m_ != mo), sum(v[1] for (q, m_), v in mrec.items() if q == p and m_ != mo)]), sc, p, "pos")

    except (ValueError, IndexError, KeyError, ZeroDivisionError, StopIteration, TypeError):   # too little data for this group
        pass

    # ================= Streaks & Form
    try:
        order = sorted(PM, key=lambda r: (SNO(r["series_id"]), int(MT[r["match_id"]]["map_no"])))
        runs = {}
        for p in players:
            cur, cl, bw, bl = [], [], [], []
            for r in (x for x in order if x["player"] == p):
                if r["result"] == "W": cur.append(r); cl = []
                else: cl.append(r); cur = []
                bw = max(bw, list(cur), key=len); bl = max(bl, list(cl), key=len)
            runs[p] = (bw, bl)
        top = max(len(v[0]) for v in runs.values()); who = [p for p, v in runs.items() if len(v[0]) == top]
        add("Streaks & Form", "Longest Winning Run", f"{top}-Map Winning Streak", ("Shared by " + ", ".join(who[:-1]) + f" and {who[-1]}." if len(who) > 1 else f"Held by {who[0]}."), top * .4, who[0], "pos")
        p, (bw, bl) = max(runs.items(), key=lambda kv: len(kv[1][1]))
        add("Streaks & Form", "Longest Losing Run", f"{len(bl)}-Map Losing Streak", f"{p}, from {NAME(bl[0]['series_id'])} to {NAME(bl[-1]['series_id'])}.", len(bl) * .35, p, "roast")
        # monthly form
        mon = defaultdict(list)
        for r in PM: mon[(r["player"], DATE(r["series_id"]).strftime("%Y-%m"))].append(r)
        months = sorted({k[1] for k in mon})
        for p in regulars:
            ks = [(m, kd_of(mon[(p, m)])) for m in months if len(mon[(p, m)]) >= 4]
            if len(ks) >= 3 and all(b[1] > a[1] for a, b in zip(ks, ks[1:])):
                add("Streaks & Form", "Trending Up", f"Better Every Month", f"{p}'s K/D has climbed each month: " + " → ".join(f"{k:.2f}" for _, k in ks) + ".", 2.4 + (ks[-1][1] - ks[0][1]) * 2, p, "pos")
        hot = []
        for (p, m), rs in mon.items():
            w = sum(r["result"] == "W" for r in rs); n = len(rs)
            if n >= 10: hot.append((lg(tail(w, n, .5)), p, m, w, n - w))
        if hot:
            sc, p, m, w, l = max(hot)
            mname = dt.date.fromisoformat(m + "-01").strftime("%B")
            add("Streaks & Form", "Hottest Month", f"{w}–{l} in {mname}", f"{p}'s best month. The rest of the season: " + (lambda o: f"{o[0]}–{o[1]}.")([sum(r["result"] == "W" for (q, mm), rs in mon.items() if q == p and mm != m for r in rs), sum(r["result"] != "W" for (q, mm), rs in mon.items() if q == p and mm != m for r in rs)]), sc, p, "pos")
        # back from a long break
        back = []
        for p in regulars:
            ss = sorted({r["series_id"] for r in PM if r["player"] == p}, key=DATE)
            for a, b in zip(ss, ss[1:]):
                g = (DATE(b) - DATE(a)).days
                if g >= 30:
                    rs = [r for r in PM if r["player"] == p and r["series_id"] == b]; k = kd_of(rs)
                    back.append((k - career[p], p, g, b, k, sum(num(r["kills"]) or 0 for r in rs), sum(num(r["deaths"]) or 0 for r in rs)))
        if back:
            d_, p, g, s, k, K, Dd = max(back)
            if d_ > .15:
                add("Streaks & Form", "Back From the Break", f"{k:.2f} K/D After {g} Days Off", f"{p} came back from the summer break above a {career[p]:.2f} career K/D ({K}–{Dd}).", 2.0 + d_ * 2, p, "pos", [s])
        dow = defaultdict(lambda: [0, 0])
        for r in PM: dow[(r["player"], DATE(r["series_id"]).strftime("%A"))][0 if r["result"] == "W" else 1] += 1
        days = [(lg(tail(w, w + l, .5)), p, wd, w, l) for (p, wd), (w, l) in dow.items() if w + l >= 10]
        if days:
            sc, p, wd, w, l = max(days)
            o = [sum(v[i] for (pp, dd), v in dow.items() if pp == p and dd != wd) for i in (0, 1)]
            add("Streaks & Form", f"{wd} {p}", f"{w}–{l} on {wd}s", f"{p} is {o[0]}–{o[1]} on every other day of the week.", sc, p, "pos")
        lows = [(lg(tail(l, w + l, .5)), p, wd, w, l) for (p, wd), (w, l) in dow.items() if w + l >= 10]
        if lows:
            sc, p, wd, w, l = max(lows)
            add("Streaks & Form", f"{p}'s {wd} Curse", f"{w}–{l} on {wd}s", f"Every other day is fine. {wd}s, not so much.", sc * .8, p, "roast")

    except (ValueError, IndexError, KeyError, ZeroDivisionError, StopIteration, TypeError):   # too little data for this group
        pass

    # ================= Oddities
    try:
        odd = [m for m, rs in bym.items()
               if (lambda ka, kb, wn: (wn == "A" and ka < kb) or (wn == "B" and kb < ka))(
                   sum(num(r["kills"]) or 0 for r in rs if r["team"] == "A"), sum(num(r["kills"]) or 0 for r in rs if r["team"] == "B"), MT[m]["winner"])]
        if odd:
            add("Oddities", "Outkilled and Still Won", f"{len(odd)} Maps", f"Won by the team with fewer kills. {Counter(MODE_(MT[m]['mode']) for m in odd).most_common(1)[0][0]} has the most.", 2.0, "", "neu", [MT[m]["series_id"] for m in odd])
        l = max((r for r in full if r["result"] == "L"), key=lambda r: num(r["kills"]))
        add("Oddities", "Most Kills in a Loss", f"{num(l['kills'])} Kills in a Loss", f"{l['player']} on {MODE_(l['mode'])} {l['map']}, {NAME(l['series_id'])}. Deserved better.", 2.3, l["player"], "pos", [l["series_id"]])
        w = max((r for r in full if r["result"] == "W"), key=lambda r: num(r["deaths"]))
        add("Oddities", "Most Deaths in a Win", f"{num(w['deaths'])} Deaths in a Win", f"{w['player']} on {MODE_(w['mode'])} {w['map']}. The team covered for it.", 1.6, w["player"], "roast", [w["series_id"]])
        even = Counter(r["player"] for r in full if num(r["kills"]) == num(r["deaths"]))
        if even:
            top = max(even.values()); who = sorted(p for p, v in even.items() if v == top)
            add("Oddities", "Perfectly Balanced", f"{top} Maps Dead Even", f"{' and '.join(who)} each have {top} maps where kills exactly equalled deaths.", 1.5, who[0], "neu")
        hp = [m for m in MT.values() if m["mode"] == "HP" and num(m["score_a"]) is not None]
        c = min(hp, key=lambda m: abs(num(m["score_a"]) - num(m["score_b"])))
        add("Oddities", "Closest Hardpoint", f"{max(num(c['score_a']), num(c['score_b']))}–{min(num(c['score_a']), num(c['score_b']))} on {c['map']}", f"{NAME(c['series_id'])}, decided by {abs(num(c['score_a']) - num(c['score_b']))} points.", 1.4, "", "neu", [c["series_id"]])

    except (ValueError, IndexError, KeyError, ZeroDivisionError, StopIteration, TypeError):   # too little data for this group
        pass

    # ---- rank
    for f in out:
        f["new"] = LATEST in f["ev"]
    out.sort(key=lambda f: -f["score"]); seen = Counter()
    for f in out:
        f["adj"] = f["score"] * (.75 ** seen[f["who"]]) if f["who"] else f["score"]; seen[f["who"]] += 1
    out.sort(key=lambda f: -f["adj"])
    hero = next((f for f in out if f["tone"] == "pos"), None)
    return hero, [f for f in out if f is not hero]