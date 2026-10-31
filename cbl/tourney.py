"""Tournament brackets: building them, and working out who plays whom from the results so far.

A tournament document holds the teams and a list of bracket matches. Each side of a match says where its
team comes from: a seed, the winner or loser of an earlier match, a final standing in the round robin /
Swiss stage, or a fixed team. Nothing about the results is stored on the matches themselves; results come
from the tournament's map documents (and "winner only" results), so editing or deleting a map
re-flows the whole bracket.

Tournament maps live in their own collections (see cbl/db.py), so none of this reaches the Series Log
or any regular stat.
"""
from __future__ import annotations

import math
from collections import defaultdict

BYE = "__bye__"
FORMATS = {
    "se": ("Single Elimination", "Lose once and you're out. Quickest."),
    "de": ("Double Elimination", "Lose twice and you're out. Winners and losers brackets, then a grand final."),
    "rr": ("Round Robin", "Everyone plays everyone. Best record wins."),
    "rrp": ("Round Robin → Playoffs", "A regular season, then the top teams go to a bracket. Top seeds get byes when the numbers are uneven."),
    "sw": ("Swiss", "A set number of rounds; each round pairs teams with the same record."),
}
# options per format: key, label, help, choices (value, label); the first choice is the default
OPTIONS = {
    "se": [("third", "Third-Place Match", "Semifinal losers play for third", [(False, "Off"), (True, "On")])],
    "de": [("reset", "Grand Final Reset", "If the losers-bracket team wins the grand final, play once more", [(True, "On"), (False, "Off")])],
    "rr": [("legs", "Each Pair Plays", "Once, or home and away", [(1, "Once"), (2, "Twice")]),
           ("tiebreak", "Tiebreaker", "When teams finish on the same record", [("h2h", "Head to head"), ("kd", "K/D")])],
    "rrp": [("legs", "Each Pair Plays", "In the regular season", [(1, "Once"), (2, "Twice")]),
            ("k", "Teams to Playoffs", "The rest are out after the regular season", [(3, "Top 3"), (2, "Top 2"), (4, "Top 4"), (6, "Top 6"), (8, "Top 8")]),
            ("playoff", "Playoff Bracket", "How the playoffs run", [("se", "Single elim"), ("de", "Double elim")]),
            ("tiebreak", "Tiebreaker", "When teams finish on the same record", [("h2h", "Head to head"), ("kd", "K/D")])],
    "sw": [("rounds", "Rounds", "Each round pairs teams with the same record", [(3, "3"), (4, "4"), (5, "5")]),
           ("after", "After the Swiss Rounds", "Optional playoff for the top teams", [("top2", "Top 2 final"), ("none", "Nothing"), ("top4", "Top 4 playoff")])],
}
# best-of per stage; the keys each format uses
STAGES = {"se": [("bracket", "Bracket Rounds"), ("final", "Final")],
          "de": [("bracket", "Winners Bracket"), ("losers", "Losers Bracket"), ("final", "Grand Final")],
          "rr": [("pools", "Every Game")],
          "rrp": [("pools", "Regular Season"), ("bracket", "Playoffs"), ("final", "Final")],
          "sw": [("pools", "Swiss Rounds"), ("final", "Final")]}
DEFAULT_LEN = {"pools": 1, "bracket": 3, "losers": 3, "final": 5}


def default_opts(fmt: str) -> dict:
    return {k: ch[0][0] for k, _, _, ch in OPTIONS[fmt]}


# ======================================================================= building
def seed_order(p: int) -> list[int]:
    """Standard bracket order for a power of two: 1, 8, 4, 5, 2, 7, 3, 6 for 8."""
    order = [1]
    while len(order) < p:
        m = len(order) * 2 + 1
        order = [x for s in order for x in (s, m - s)]
    return order


def title_label(label: str) -> str:
    """Bracket labels in title case ("Winners Round 1"), also for tournaments made before labels were capitalized."""
    small = {"of", "the", "a", "vs"}
    return " ".join(w if (i and w in small) else w[:1].upper() + w[1:] for i, w in enumerate((label or "").split(" ")))


def _round_name(r: int, rounds: int) -> str:
    left = rounds - r
    return {0: "Final", 1: "Semifinal", 2: "Quarterfinal"}.get(left, f"Round {r}")


def elim(prefix: str, entrants: list[dict], double: bool, bo: int, bo_l: int, bo_final: int,
         third: bool = False, reset: bool = True, label: str = "") -> list[dict]:
    """Single or double elimination for the given entrant sources (best seed first)."""
    k = len(entrants)
    p = 1
    while p < k:
        p *= 2
    p = max(p, 2)
    src = {i + 1: entrants[i] for i in range(k)}
    kr = int(math.log2(p))
    out, wb = [], {}
    order = seed_order(p)
    for r in range(1, kr + 1):
        ids = []
        n = p // 2 ** r
        for i in range(n):
            mid = f"{prefix}W{r}-{i + 1}"
            if r == 1:
                a, b = order[2 * i], order[2 * i + 1]
                sa = src.get(a, {"bye": True}); sb = src.get(b, {"bye": True})
            else:
                sa = {"win": wb[r - 1][2 * i]}; sb = {"win": wb[r - 1][2 * i + 1]}
            final = r == kr and not double
            if double:
                nm = "Winners Final" if r == kr else f"Winners Round {r}"
            else:
                nm = _round_name(r, kr)
            out.append({"id": mid, "stage": prefix + "W", "round": r, "label": (label + nm).strip(), "bo": bo_final if final else bo, "a": sa, "b": sb})
            ids.append(mid)
        wb[r] = ids
    if not double:
        if third and kr >= 2:
            s1, s2 = wb[kr - 1]
            out.append({"id": f"{prefix}3P", "stage": prefix + "3P", "round": kr, "label": (label + "Third-Place Match").strip(), "bo": bo,
                        "a": {"lose": s1}, "b": {"lose": s2}})
        return out
    # losers bracket
    cur = []
    lr = 0
    if kr >= 2:
        lr = 1
        firsts = wb[1]
        for i in range(0, len(firsts), 2):
            mid = f"{prefix}L1-{i // 2 + 1}"
            out.append({"id": mid, "stage": prefix + "L", "round": 1, "label": "", "bo": bo_l, "a": {"lose": firsts[i]}, "b": {"lose": firsts[i + 1]}})
            cur.append(mid)
        for r in range(2, kr + 1):
            drops = wb[r] if r % 2 else list(reversed(wb[r]))
            lr += 1
            nxt = []
            for i, (c, d) in enumerate(zip(cur, drops)):
                mid = f"{prefix}L{lr}-{i + 1}"
                out.append({"id": mid, "stage": prefix + "L", "round": lr, "label": "", "bo": bo_l, "a": {"win": c}, "b": {"lose": d}})
                nxt.append(mid)
            cur = nxt
            if r < kr:
                lr += 1
                nxt = []
                for i in range(0, len(cur), 2):
                    mid = f"{prefix}L{lr}-{i // 2 + 1}"
                    out.append({"id": mid, "stage": prefix + "L", "round": lr, "label": "", "bo": bo_l, "a": {"win": cur[i]}, "b": {"win": cur[i + 1]}})
                    nxt.append(mid)
                cur = nxt
        lb_winner = {"win": cur[0]}
    else:
        lb_winner = {"lose": wb[1][0]}
    for m in out:
        if m["stage"] == prefix + "L":
            m["label"] = (label + ("Losers Final" if m["round"] == lr else f"Losers Round {m['round']}")).strip()
    out.append({"id": f"{prefix}GF", "stage": prefix + "GF", "round": 1, "label": (label + "Grand Final").strip(), "bo": bo_final,
                "a": {"win": wb[kr][0]}, "b": lb_winner})
    if reset:
        out.append({"id": f"{prefix}GR", "stage": prefix + "GR", "round": 1, "label": (label + "Bracket Reset").strip(), "bo": bo_final,
                    "a": {"win": f"{prefix}GF"}, "b": {"lose": f"{prefix}GF"}, "if_needed": f"{prefix}GF"})
    return out


def round_robin(team_ids: list[str], legs: int, bo: int) -> list[dict]:
    ids = list(team_ids)
    if len(ids) % 2:
        ids.append(BYE)
    n = len(ids)
    out = []
    rnd = 0
    for leg in range(legs):
        arr = ids[:]
        for r in range(n - 1):
            rnd += 1
            g = 0
            for i in range(n // 2):
                a, b = arr[i], arr[n - 1 - i]
                if BYE in (a, b):
                    continue
                if leg % 2:
                    a, b = b, a
                g += 1
                out.append({"id": f"RR{rnd}-{g}", "stage": "RR", "round": rnd, "label": f"Round {rnd}", "bo": bo, "a": {"team": a}, "b": {"team": b}})
            arr = [arr[0]] + [arr[-1]] + arr[1:-1]
    return out


def _pair(ids: list, played: set):
    """Pair ids in order (best first) with no rematches; None if that's impossible."""
    if not ids:
        return []
    a = ids[0]
    for j in range(1, len(ids)):
        b = ids[j]
        if frozenset((a, b)) in played:
            continue
        rest = _pair(ids[1:j] + ids[j + 1:], played)
        if rest is not None:
            return [(a, b)] + rest
    return None


def swiss_round(t: dict, r: int, standings_rows: list[dict] | None, played: set) -> list[dict]:
    """Pairings for Swiss round r. Round 1 goes by seed (top half vs bottom half)."""
    bo = t["lengths"]["pools"]
    if r == 1:
        ids = [x["id"] for x in sorted(t["teams"], key=lambda x: x["seed"])]
    else:
        ids = [x["team"] for x in standings_rows]
    out = []
    bye = None
    had = {m["a"].get("team") for m in t["matches"] if m["stage"] == "SW" and m["b"].get("bye")}
    # the bye goes to the lowest-ranked team that hasn't had one yet
    bye_order = ([x for x in reversed(ids) if x not in had] + [x for x in reversed(ids) if x in had]) if len(ids) % 2 else [None]
    if r == 1:
        bye = bye_order[0]
        rest = [x for x in ids if x != bye]
        h = len(rest) // 2
        pairs = list(zip(rest[:h], rest[h:]))
    else:
        # teams on the same record meet, top down, with no rematches whenever any pairing allows it
        pairs = None
        for cand in bye_order:
            rest = [x for x in ids if x != cand]
            pairs = _pair(rest, played)
            if pairs is not None:
                bye = cand
                break
        if pairs is None:  # every pairing needs a rematch: fall back to the fewest, top down
            bye = bye_order[0]
            left = [x for x in ids if x != bye]
            pairs = []
            while left:
                a = left.pop(0)
                j = next((i for i, b in enumerate(left) if frozenset((a, b)) not in played), 0)
                pairs.append((a, left.pop(j)))
    for g, (a, b) in enumerate(pairs, 1):
        out.append({"id": f"SW{r}-{g}", "stage": "SW", "round": r, "label": f"Round {r}", "bo": bo, "a": {"team": a}, "b": {"team": b}})
    if bye:
        out.append({"id": f"SW{r}-bye", "stage": "SW", "round": r, "label": f"Round {r}", "bo": bo, "a": {"team": bye}, "b": {"bye": True}})
    return out


def build(t: dict) -> list[dict]:
    """All the matches a new tournament starts with (Swiss adds rounds as it goes)."""
    fmt, o, L = t["format"], t["opts"], t["lengths"]
    teams = sorted(t["teams"], key=lambda x: x["seed"])
    n = len(teams)
    if fmt in ("se", "de"):
        ents = [{"seed": i + 1} for i in range(n)]
        return elim("", ents, fmt == "de", L["bracket"], L.get("losers", L["bracket"]), L["final"],
                    third=bool(o.get("third")), reset=bool(o.get("reset", True)))
    if fmt == "rr":
        return round_robin([x["id"] for x in teams], int(o.get("legs", 1)), L["pools"])
    if fmt == "rrp":
        k = min(int(o.get("k", 3)), n)
        ms = round_robin([x["id"] for x in teams], int(o.get("legs", 1)), L["pools"])
        return ms + elim("P", [{"rank": i + 1} for i in range(k)], o.get("playoff") == "de", L["bracket"], L["bracket"], L["final"],
                         label="", reset=True)
    if fmt == "sw":
        ms = swiss_round({**t, "matches": []}, 1, None, set())
        after = o.get("after", "top2")
        if after == "top2":
            ms += [{"id": "SF", "stage": "SF", "round": 1, "label": "Final", "bo": L["final"], "a": {"rank": 1}, "b": {"rank": 2}}]
        elif after == "top4" and n >= 4:
            ms += elim("P", [{"rank": i + 1} for i in range(4)], False, L["final"], L["final"], L["final"])
        return ms
    raise ValueError(fmt)


def series_count(fmt: str, n: int, o: dict) -> tuple[int, int]:
    """(fewest, most) series a format needs, for the setup summary."""
    if n < 2:
        return 0, 0
    if fmt == "se":
        c = n - 1 + (1 if o.get("third") and n >= 4 else 0)
        return c, c
    if fmt == "de":
        return 2 * n - 2, 2 * n - 2 + (1 if o.get("reset", True) else 0)
    rr = n * (n - 1) // 2 * int(o.get("legs", 1))
    if fmt == "rr":
        return rr, rr
    if fmt == "rrp":
        k = min(int(o.get("k", 3)), n)
        if o.get("playoff") == "de":
            return rr + 2 * k - 2, rr + 2 * k - 1
        return rr + k - 1, rr + k - 1
    sw = int(o.get("rounds", 3)) * (n // 2) + {"none": 0, "top2": 1, "top4": 3}[o.get("after", "top2")]
    return sw, sw


# ======================================================================= resolving
def _team_maps(t_maps: list[dict]) -> dict:
    by = defaultdict(list)
    for m in t_maps:
        by[m["bmatch"]].append(m)
    for v in by.values():
        v.sort(key=lambda m: m["map_no"])
    return by


def pool_ids(t: dict) -> set:
    return {m["id"] for m in t["matches"] if m["stage"] in ("RR", "SW")}


def resolve(t: dict, t_maps: list[dict], kd: dict | None = None) -> dict:
    """Work out every match: its two teams, map wins, status and winner.

    status: waiting (a team still unknown) · ready · live (maps entered, not decided) · done · bye · skipped
    """
    maps = _team_maps(t_maps)
    manual = t.get("manual", {})
    seeds = {x["seed"]: x["id"] for x in t["teams"]}
    R: dict[str, dict] = {}
    pool_done = None

    def side(src):
        nonlocal pool_done
        if "seed" in src:
            return seeds.get(src["seed"], BYE)
        if src.get("bye"):
            return BYE
        if "team" in src:
            return src["team"]
        if "win" in src:
            return R[src["win"]]["winner"]
        if "lose" in src:
            return R[src["lose"]]["loser"]
        if "rank" in src:
            if pool_done is None:
                pool_done = pool_complete(t, R)
            if not pool_done:
                return None
            rows = standings(t, R, t_maps, kd)
            return rows[src["rank"] - 1]["team"] if src["rank"] <= len(rows) else BYE
        return None

    for m in t["matches"]:
        a, b = side(m["a"]), side(m["b"])
        ms = maps.get(m["id"], [])
        r = {"id": m["id"], "a": a, "b": b, "wa": sum(x["winner"] == "A" for x in ms), "wb": sum(x["winner"] == "B" for x in ms),
             "maps": ms, "winner": None, "loser": None, "status": "waiting", "manual": manual.get(m["id"])}
        need = m["bo"] // 2 + 1
        if m.get("if_needed"):
            gf = R[m["if_needed"]]
            if gf["status"] == "done" and gf["winner"] == gf["a"]:
                r.update(status="skipped", winner=gf["winner"], loser=gf["loser"])
                R[m["id"]] = r
                continue
        if a is None or b is None:
            pass
        elif a == BYE and b == BYE:
            r.update(status="bye", winner=BYE, loser=BYE)
        elif a == BYE or b == BYE:
            w = b if a == BYE else a
            r.update(status="bye", winner=w, loser=BYE)
        elif r["manual"] in ("a", "b"):
            w = a if r["manual"] == "a" else b
            r.update(status="done", winner=w, loser=b if w == a else a)
        elif r["wa"] >= need or r["wb"] >= need:
            w = a if r["wa"] > r["wb"] else b
            r.update(status="done", winner=w, loser=b if w == a else a)
        elif ms:
            r["status"] = "live"
        else:
            r["status"] = "ready"
        R[m["id"]] = r
    return R


def pool_complete(t: dict, R: dict) -> bool:
    pm = [m for m in t["matches"] if m["stage"] in ("RR", "SW")]
    if not pm:
        return False
    if t["format"] == "sw":
        rounds = max(m["round"] for m in pm)
        if rounds < int(t["opts"].get("rounds", 3)):
            return False
    return all(R.get(m["id"], {}).get("status") in ("done", "bye") for m in pm)


def standings(t: dict, R: dict, t_maps: list[dict], kd: dict | None = None) -> list[dict]:
    """Round robin / Swiss table: wins, then head to head (or K/D), then map difference, then seed."""
    pm = [m for m in t["matches"] if m["stage"] in ("RR", "SW")]
    rows = {x["id"]: {"team": x["id"], "w": 0, "l": 0, "mw": 0, "ml": 0, "seed": x["seed"], "played": 0} for x in t["teams"]}
    h2h = defaultdict(int)
    for m in pm:
        r = R.get(m["id"])
        if not r or r["status"] not in ("done", "bye"):
            continue
        if r["status"] == "bye":
            if r["winner"] in rows:
                rows[r["winner"]]["w"] += 1
            continue
        a, b = r["a"], r["b"]
        rows[r["winner"]]["w"] += 1; rows[r["loser"]]["l"] += 1
        rows[a]["mw"] += r["wa"]; rows[a]["ml"] += r["wb"]; rows[b]["mw"] += r["wb"]; rows[b]["ml"] += r["wa"]
        rows[a]["played"] += 1; rows[b]["played"] += 1
        h2h[(r["winner"], r["loser"])] += 1
    tb = t["opts"].get("tiebreak", "h2h")
    out = list(rows.values())
    kd = kd or {}

    def key(x):
        return (-x["w"], -(kd.get(x["team"], 0) if tb == "kd" else 0), -(x["mw"] - x["ml"]), x["seed"])
    out.sort(key=key)
    if tb == "h2h":  # two teams level on wins: the head-to-head winner goes first
        i = 0
        while i < len(out) - 1:
            a, b = out[i], out[i + 1]
            same = a["w"] == b["w"] and (i + 2 >= len(out) or out[i + 2]["w"] != a["w"]) and (i == 0 or out[i - 1]["w"] != a["w"])
            if same and h2h[(b["team"], a["team"])] > h2h[(a["team"], b["team"])]:
                out[i], out[i + 1] = b, a
            i += 1
    for i, x in enumerate(out, 1):
        x["rank"] = i
    return out


def advance(t: dict, t_maps: list[dict], kd: dict | None = None) -> bool:
    """Swiss: add the next round once the current one is finished. Returns True if the doc changed."""
    if t["format"] != "sw":
        return False
    R = resolve(t, t_maps, kd)
    sw = [m for m in t["matches"] if m["stage"] == "SW"]
    last = max(m["round"] for m in sw)
    if last >= int(t["opts"].get("rounds", 3)):
        return False
    if not all(R[m["id"]]["status"] in ("done", "bye") for m in sw if m["round"] == last):
        return False
    played = {frozenset((R[m["id"]]["a"], R[m["id"]]["b"])) for m in sw}
    rows = standings(t, R, t_maps, kd)
    new = swiss_round(t, last + 1, rows, played)
    tail = [m for m in t["matches"] if m["stage"] != "SW"]
    t["matches"] = sw + new + tail
    return True


def redraw_after(t: dict, R: dict, mid: str) -> bool:
    """Swiss: a result changed in an earlier round, so drop later rounds nobody has played yet
    (advance() draws them again from the new standings). Returns True if the doc changed."""
    m0 = next((m for m in t["matches"] if m["id"] == mid), None)
    if not m0 or m0["stage"] != "SW":
        return False
    later = [m for m in t["matches"] if m["stage"] == "SW" and m["round"] > m0["round"]]
    if not later or any(R.get(m["id"], {}).get("maps") or R.get(m["id"], {}).get("manual") for m in later):
        return False
    ids = {m["id"] for m in later}
    t["matches"] = [m for m in t["matches"] if m["id"] not in ids]
    return True


def dependents(t: dict, mid: str) -> list[str]:
    """Matches whose teams depend on this one's result."""
    out = []
    is_pool = mid in pool_ids(t)
    m0 = next(m for m in t["matches"] if m["id"] == mid)
    for m in t["matches"]:
        for s in (m["a"], m["b"]):
            if s.get("win") == mid or s.get("lose") == mid or (is_pool and "rank" in s):
                out.append(m["id"])
        if m.get("if_needed") == mid:
            out.append(m["id"])
        if is_pool and m["stage"] == "SW" and m0["stage"] == "SW" and m["round"] > m0["round"]:
            out.append(m["id"])
    return list(dict.fromkeys(out))


def locked(t: dict, R: dict, mid: str) -> bool:
    """A result can't change once a match that depends on it has started."""
    return any(R[d]["maps"] or R[d]["manual"] for d in dependents(t, mid) if d in R)


def champion(t: dict, R: dict, t_maps: list[dict], kd: dict | None = None) -> str | None:
    fmt = t["format"]
    ms = t["matches"]
    if fmt == "rr":
        return standings(t, R, t_maps, kd)[0]["team"] if pool_complete(t, R) else None
    if fmt == "sw" and t["opts"].get("after") == "none":
        return standings(t, R, t_maps, kd)[0]["team"] if pool_complete(t, R) else None
    last = [m for m in ms if m["stage"] not in ("RR", "SW") and not m["stage"].endswith("3P")]
    if not last:
        return None
    gr = next((m for m in last if m.get("if_needed")), None)
    if gr:
        r = R[gr["id"]]
        return r["winner"] if r["status"] in ("done", "skipped") else None
    fin = last[-1]
    r = R[fin["id"]]
    return r["winner"] if r["status"] in ("done", "bye") else None


def placements(t: dict, R: dict, t_maps: list[dict], kd: dict | None = None) -> dict:
    """team id -> short finish text."""
    out = {}
    champ = champion(t, R, t_maps, kd)
    fmt = t["format"]
    if fmt in ("rr",) or (fmt == "sw" and t["opts"].get("after") == "none"):
        if pool_complete(t, R):
            for x in standings(t, R, t_maps, kd):
                out[x["team"]] = "Champions" if x["rank"] == 1 else _ord(x["rank"])
        return out
    elim_ms = [m for m in t["matches"] if m["stage"] not in ("RR", "SW")]
    last = {}  # each team's latest match: in double elimination a first loss isn't the end
    for m in elim_ms:
        r = R[m["id"]]
        if r["status"] in ("skipped", "bye"):
            continue
        for side in ("a", "b"):
            if r[side] and r[side] != BYE:
                last[r[side]] = (m, r)
    for tid, (m, r) in last.items():
        if r["status"] == "done" and r["loser"] == tid:
            out[tid] = "Out · " + (m["label"] or "")
    if fmt in ("rrp", "sw") and pool_complete(t, R):
        inn = {R[m["id"]][s] for m in elim_ms for s in ("a", "b")}
        for x in standings(t, R, t_maps, kd):
            if x["team"] not in inn:
                out[x["team"]] = "Out · " + ("Regular season" if fmt == "rrp" else "Swiss rounds")
    for m in elim_ms:  # third-place match
        r = R[m["id"]]
        if m["stage"].endswith("3P") and r["status"] == "done":
            out[r["winner"]] = "3rd"; out[r["loser"]] = "4th"
    if champ:
        out[champ] = "Champions"
        last = [m for m in elim_ms if not m["stage"].endswith("3P")]
        for m in reversed(last):
            r = R[m["id"]]
            if r["status"] == "done" and r["winner"] == champ:
                out[r["loser"]] = "Runners-up"
                break
    return out


def _ord(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def next_up(t: dict, R: dict) -> list[str]:
    """Matches being played or ready to play, in bracket order."""
    live = [m["id"] for m in t["matches"] if R[m["id"]]["status"] == "live"]
    ready = [m["id"] for m in t["matches"] if R[m["id"]]["status"] == "ready"]
    return live + ready