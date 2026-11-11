"""Map veto: bans, picks and side choices for a series, worked out from the series' best-of and the title's map pools.

Pure Python, no Streamlit and no database, so it can be tested on its own and shared by the Scorekeeper.
A veto is replayed from the list of choices made so far, which makes Undo (drop the last choice) always safe.

Rules: the Black Ops 7 era CDL veto (Hardpoint, Search and Destroy, then the third mode: Overload in Black Ops 7,
Hijack in Modern Warfare 4). Best of 9 follows the same pattern (it isn't published officially).
When a mode's pool is too small for every step, bans are dropped from the last one back until the picks fit.
"""
from __future__ import annotations

from dataclasses import dataclass, field

HP, SND, OBJ = "HP", "SND", "OBJ"          # OBJ: the title's third mode (OVL or HJ)

# map order for each best-of
ORDER = {
    1: [HP],
    3: [HP, SND, OBJ],
    5: [HP, SND, OBJ, HP, SND],
    7: [HP, SND, OBJ, HP, SND, OBJ, SND],
    9: [HP, SND, OBJ, HP, SND, OBJ, SND, HP, SND],
}

# (team, action, map number). Actions: ban, pick (team picks that map), last (the map left over becomes that map;
# if more than one is left, the team named picks it), side (team chooses the side on that map).
_HP3 = [("A", "ban", None), ("B", "ban", None), ("A", "pick", 1), ("B", "side", 1)]
_HP5 = _HP3 + [("B", "pick", 4), ("A", "side", 4)]
_SND3 = [("B", "ban", None), ("A", "ban", None), ("B", "pick", 2), ("A", "side", 2)]
_SND5 = _SND3 + [("A", "pick", 5), ("B", "side", 5)]
_OBJ3 = [("A", "ban", None), ("B", "ban", None), ("A", "pick", 3), ("B", "side", 3)]
STEPS = {
    1: {HP: _HP3},
    3: {HP: _HP3, SND: _SND3, OBJ: _OBJ3},
    5: {HP: _HP5, SND: _SND5, OBJ: _OBJ3},
    7: {HP: _HP5, SND: _SND5 + [("A", "pick", 7), ("A", "side", 7)], OBJ: _OBJ3 + [("A", "last", 6), ("A", "side", 6)]},
    9: {HP: _HP5 + [("A", "pick", 8), ("B", "side", 8)],
        SND: _SND5 + [("B", "pick", 7), ("A", "side", 7), ("A", "last", 9), ("A", "side", 9)],
        OBJ: _OBJ3 + [("A", "last", 6), ("A", "side", 6)]},
}
SIDES = {HP: ("good", "bad"), OBJ: ("good", "bad"), SND: ("attack", "defend")}
SIDE_LABEL = {"good": "Good Side", "bad": "Bad Side", "attack": "Attack First", "defend": "Defend First"}
SKIP = "skip"


def _modes(best_of: int) -> list[str]:
    """The modes a best-of plays, always in the same order (Hardpoint, SnD, then the third mode)."""
    return [m for m in (HP, SND, OBJ) if m in ORDER[best_of]]


@dataclass(frozen=True)
class Step:
    team: str            # "A" or "B"
    action: str          # ban | pick | last | side
    mode: str            # HP | SND | OBJ
    map_no: int | None


@dataclass
class Plan:
    best_of: int
    steps: list[Step]
    notes: list[str]                      # plain-language notes about dropped bans
    pools: dict[str, list[str]]
    problem: str | None = None            # set when a veto can't be run with these pools


def plan(best_of: int, pools: dict[str, list[str]], names: dict[str, str] | None = None) -> Plan:
    """The steps for this best-of, fitted to the pools. pools: {HP|SND|OBJ: active maps, in display order}."""
    names = names or {HP: "Hardpoint", SND: "SnD", OBJ: "Objective"}
    if best_of not in ORDER:
        return Plan(best_of, [], [], pools, f"There's no veto for a best of {best_of}.")
    pools = {m: list(dict.fromkeys(pools.get(m, []))) for m in _modes(best_of)}   # no duplicates inside a pool
    steps, notes = [], []
    for mode in (HP, SND, OBJ):
        if mode not in STEPS[best_of]:
            continue
        raw = list(STEPS[best_of][mode])
        need = sum(1 for _, a, _ in raw if a in ("pick", "last"))
        have = len(pools[mode])
        if have < need:
            return Plan(best_of, [], [], pools, f"{names[mode]} has {have} map{'s' if have != 1 else ''} in the pool, but a best of "
                        f"{best_of} plays {need}. Add maps under Season Settings, or pick as you go.")
        bans = [i for i, s in enumerate(raw) if s[1] == "ban"]
        dropped = []
        while bans and have - len(bans) < need:
            dropped.append(raw[bans[-1]][0]); bans.pop()
        if dropped:
            keep = set(bans)
            raw = [s for i, s in enumerate(raw) if s[1] != "ban" or i in keep]
            who = " and ".join(f"Team {t}'s" for t in reversed(dropped))
            notes.append(f"{names[mode]} has {have} maps, so {who} ban{'s are' if len(dropped) > 1 else ' is'} skipped.")
        steps += [Step(t, a, mode, n) for t, a, n in raw]
    return Plan(best_of, steps, notes, pools)


@dataclass
class Slot:
    map_no: int
    mode: str
    map: str | None = None
    by: str | None = None                 # "A", "B", or "left" (the map left over)
    side: str | None = None               # good | bad | attack | defend | None (skipped)
    side_by: str | None = None


@dataclass
class State:
    plan: Plan
    choices: list[str]
    slots: dict[int, Slot] = field(default_factory=dict)
    bans: dict[str, list[tuple[str, str]]] = field(default_factory=dict)   # mode -> [(team, map)]
    left: dict[str, list[str]] = field(default_factory=dict)              # mode -> maps still available
    i: int = 0                                                             # index of the next step
    auto: list[int] = field(default_factory=list)                          # steps filled in without a choice

    @property
    def done(self) -> bool:
        return self.i >= len(self.plan.steps)

    @property
    def step(self) -> Step | None:
        return None if self.done else self.plan.steps[self.i]

    def options(self) -> list[str]:
        s = self.step
        if s is None:
            return []
        if s.action == "side":
            return list(SIDES[s.mode]) + [SKIP]
        return list(self.left[s.mode])


class VetoError(ValueError):
    pass


def replay(p: Plan, choices: list[str]) -> State:
    """Apply the choices in order. Steps with only one possible answer (the last map left) fill in by themselves."""
    if p.problem:
        raise VetoError(p.problem)
    order = ORDER[p.best_of]
    st = State(p, list(choices), {n + 1: Slot(n + 1, m) for n, m in enumerate(order)},
               {m: [] for m in _modes(p.best_of)}, {m: list(p.pools[m]) for m in _modes(p.best_of)})
    it = iter(choices)

    def settle():   # fill in steps that need no choice
        while not st.done and st.step.action == "last" and len(st.left[st.step.mode]) == 1:
            s = st.step
            _take(st, s, st.left[s.mode][0], "left"); st.auto.append(st.i); st.i += 1
    settle()
    for c in it:
        if st.done:
            raise VetoError("The veto is already complete.")
        s = st.step
        if c not in st.options():
            raise VetoError(f"{c!r} isn't a choice at this step.")
        if s.action == "ban":
            st.bans[s.mode].append((s.team, c)); st.left[s.mode].remove(c)
        elif s.action in ("pick", "last"):
            _take(st, s, c, s.team if s.action == "pick" else "left")
        else:
            slot = st.slots[s.map_no]
            slot.side, slot.side_by = (None, None) if c == SKIP else (c, s.team)
        st.i += 1
        settle()
    return st


def _take(st: State, s: Step, m: str, by: str):
    slot = st.slots[s.map_no]
    assert slot.mode == s.mode and slot.map is None
    slot.map, slot.by = m, by
    st.left[s.mode].remove(m)


def prompt(st: State, names: dict[str, str]) -> str:
    """One plain sentence for the current step, e.g. 'Team A Bans a Hardpoint Map'."""
    s = st.step
    if s is None:
        return "Veto Complete"
    mode = names[s.mode]
    if s.action == "ban":
        return f"Team {s.team} Bans a {mode} Map"
    if s.action == "pick":
        return f"Team {s.team} Picks Map {s.map_no} · {mode}"
    if s.action == "last":
        return f"Team {s.team} Picks Map {s.map_no} From the Maps Left · {mode}"
    m = st.slots[s.map_no].map
    return f"Team {s.team} Chooses a Side on Map {s.map_no} · {m}"


# ------------------------------------------------------------------ after the veto: plan vs what was played
def record(st: State) -> dict:
    """What gets saved on the series once the veto is complete."""
    if not st.done:
        raise VetoError("The veto isn't complete yet.")
    return {"best_of": st.plan.best_of, "choices": list(st.choices),
            "slots": [{"map_no": s.map_no, "mode": s.mode, "map": s.map, "by": s.by, "side": s.side, "side_by": s.side_by}
                      for s in st.slots.values()],
            "bans": [{"mode": m, "team": t, "map": x} for m, b in st.bans.items() for t, x in b],
            "notes": list(st.plan.notes)}


def compare(rec: dict, played: list[dict], best_of: int, mode_of: dict[str, str]) -> list[dict]:
    """Each planned map next to what was actually played. played: [{map_no, mode, map}] (real mode codes);
    mode_of maps real codes to HP/SND/OBJ. Status: as_planned | changed | not_played. A plan made for a different
    best-of is flagged on every slot."""
    by_no = {m["map_no"]: m for m in played}
    out = []
    for s in rec["slots"]:
        m = by_no.get(s["map_no"])
        if m is None:
            status = "not_played"
        elif mode_of.get(m["mode"]) == s["mode"] and m["map"] == s["map"]:
            status = "as_planned"
        else:
            status = "changed"
        out.append({**s, "status": status, "played": m and {"mode": m["mode"], "map": m["map"]},
                    "stale": rec["best_of"] != best_of})
    return out


# ------------------------------------------------------------------ the app's side of it: title config in, saved record out
def obj_code(tcfg: dict) -> str | None:
    """The title's third mode (Overload in Black Ops 7, Hijack in Modern Warfare 4): the first active mode that isn't
    Hardpoint or SnD."""
    act = [k for k, m in tcfg.get("modes", {}).items() if m.get("active", True) and k not in (HP, SND)]
    for pref in ("OVL", "HJ"):
        if pref in act:
            return pref
    return act[0] if act else None


def codes(tcfg: dict) -> dict[str, str]:
    """Veto mode -> the title's own mode code."""
    return {HP: HP, SND: SND, OBJ: obj_code(tcfg) or "OBJ"}


def pools(tcfg: dict) -> dict[str, list[str]]:
    """Active maps for each veto mode, in the order Season Settings lists them."""
    out = {}
    for vm, code in codes(tcfg).items():
        m = tcfg.get("modes", {}).get(code, {})
        out[vm] = [x["name"] for x in m.get("maps", []) if x.get("status") != "retired"] if m.get("active", True) else []
    return out


def mode_names(tcfg: dict) -> dict[str, str]:
    short = {"HP": "Hardpoint", "SND": "SnD", "OVL": "Overload", "HJ": "Hijack"}
    return {vm: tcfg.get("modes", {}).get(code, {}).get("short") or short.get(code, code) for vm, code in codes(tcfg).items()}


def to_sides(rec: dict, first: str) -> dict:
    """A finished veto, with the veto's Team A / Team B turned into the series' own sides (first = the series side that
    went first, i.e. was the veto's Team A). This is what's saved on the series."""
    side = (lambda r: r if r in (None, "left") else (first if r == "A" else ("B" if first == "A" else "A")))
    return {**rec, "first": first,
            "slots": [{**s, "by": side(s["by"]), "side_by": side(s["side_by"])} for s in rec["slots"]],
            "bans": [{**b, "team": side(b["team"])} for b in rec["bans"]]}


def slot_for(saved: dict | None, map_no: int, tcfg: dict) -> dict | None:
    """The planned slot for a map number, with the title's real mode code (None without a plan)."""
    if not saved:
        return None
    s = next((x for x in saved.get("slots", []) if x["map_no"] == map_no), None)
    return {**s, "code": codes(tcfg)[s["mode"]]} if s else None