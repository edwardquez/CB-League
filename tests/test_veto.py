"""Exhaustive and random tests for the map veto (cbl/veto.py). Run: python3 tests/test_veto.py"""
import itertools, random, sys, time
from collections import Counter
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from cbl import veto as V

POOL = [f"M{i}" for i in range(1, 11)]
NAMES = {V.HP: "Hardpoint", V.SND: "SnD", V.OBJ: "Hijack"}
stats = Counter()

def check_state(st, p):
    """Invariants that must hold at every point of every veto."""
    order = V.ORDER[p.best_of]
    for mode in set(order):
        used = [s.map for s in st.slots.values() if s.mode == mode and s.map] + [m for _, m in st.bans[mode]]
        assert len(used) == len(set(used)), f"map used twice in {mode}: {used}"
        assert set(used) | set(st.left[mode]) == set(p.pools[mode]), "maps lost or invented"
        assert not (set(used) & set(st.left[mode]))
    for n, s in st.slots.items():
        assert s.mode == order[n - 1]
        if s.side is not None:
            assert s.map is not None and s.side in V.SIDES[s.mode] and s.side_by in ("A", "B")
    if not st.done:
        s = st.step
        opts = st.options()
        assert opts, f"no options at step {st.i}: {s}"
        if s.action == "side":
            assert st.slots[s.map_no].map is not None, "side chosen before the map is known"
        else:
            assert s.mode in st.left
        stats["states"] += 1
    else:
        for s in st.slots.values():
            assert s.map is not None, f"map {s.map_no} never filled"
            assert s.by in ("A", "B", "left")
        # the step that picks a map is made by the team the rules name
        for i, s in enumerate(p.steps):
            if s.action == "pick":
                assert st.slots[s.map_no].by == s.team

def walk(p, choices, side_all):
    st = V.replay(p, choices)
    check_state(st, p)
    # undo from here always gives back the previous state exactly
    if choices:
        prev = V.replay(p, choices[:-1])
        assert prev.i < st.i or prev.i == st.i - 0
    if st.done:
        stats["complete"] += 1
        rec = V.record(st)
        assert len(rec["slots"]) == p.best_of
        return
    opts = st.options()
    if st.step.action == "side" and not side_all:
        opts = [opts[stats["complete"] % len(opts)]]        # rotate through side answers without multiplying paths
    for c in opts:
        walk(p, choices + [c], side_all)
    # anything not offered is refused
    try:
        V.replay(p, choices + ["NotAMap"]); raise AssertionError("bad choice accepted")
    except V.VetoError:
        pass

def need_of(bo, mode):
    return sum(1 for _, a, _ in V.STEPS[bo][mode] if a in ("pick", "last"))

t0 = time.time()
# 1. every best-of, every pool size per mode (others at 6), every map choice; sides exhaustively on small pools
for bo in V.ORDER:
    modes = sorted(set(V.ORDER[bo]))
    for mode in modes:
        for n in range(0, 9):
            pools = {m: POOL[:6] for m in modes}; pools[mode] = POOL[:n]
            p = V.plan(bo, pools, NAMES)
            nd = need_of(bo, mode)
            if n < nd:
                assert p.problem and NAMES[mode] in p.problem, (bo, mode, n, p.problem); stats["refused_small_pool"] += 1
                continue
            assert not p.problem
            nb_full = sum(1 for _, a, _ in V.STEPS[bo][mode] if a == "ban")
            nb = sum(1 for s in p.steps if s.mode == mode and s.action == "ban")
            assert nb == min(nb_full, n - nd), (bo, mode, n, nb)        # bans dropped exactly when needed, and only as many
            if nb < nb_full:
                assert any(NAMES[mode] in x for x in p.notes)
            else:
                assert not any(NAMES[mode] in x for x in p.notes)
            # walk only this mode exhaustively: other modes take their first option
            def walk_mode(choices):
                st = V.replay(p, choices); check_state(st, p)
                if st.done:
                    stats["complete"] += 1; return
                opts = st.options()
                if st.step.mode != mode:
                    opts = opts[:1]
                elif st.step.action == "side" and n > 6:
                    opts = opts[:1]
                for c in opts:
                    walk_mode(choices + [c])
            walk_mode([])
            stats["configs"] += 1
print("exhaustive per mode:", dict(stats), f"{time.time() - t0:.1f}s")

# 2. random full series across mixed pool sizes, with undo and redo along the way
rng = random.Random(7)
for k in range(20000):
    bo = rng.choice(list(V.ORDER)); modes = sorted(set(V.ORDER[bo]))
    pools = {m: rng.sample(POOL, rng.randint(1, 8)) for m in modes}
    p = V.plan(bo, pools, NAMES)
    if p.problem:
        stats["random_refused"] += 1; continue
    ch = []
    while True:
        st = V.replay(p, ch); check_state(st, p)
        if st.done:
            break
        if ch and rng.random() < .15:   # undo, then carry on
            ch = ch[:-1]; stats["undos"] += 1; continue
        ch.append(rng.choice(st.options()))
    rec = V.record(st); stats["random_complete"] += 1
    # same choices always give the same result
    assert V.record(V.replay(p, ch)) == rec
print("random:", {k: v for k, v in stats.items() if k.startswith("random") or k == "undos"})

# 3. specific rules, written out by hand
def run(bo, pools, ch):
    return V.replay(V.plan(bo, pools, NAMES), ch)
MW4 = {V.HP: ["Lithium", "Lotus", "Munition", "Reactor U92", "Rooftops", "Sentry"],
       V.SND: ["Coal", "Lotus", "Munition", "Reactor U92", "Rooftops", "Silkworm"],
       V.OBJ: ["Lithium", "Lotus", "Munition"]}
p = V.plan(7, MW4, NAMES)
assert p.notes == ["Hijack has 3 maps, so Team B's ban is skipped."], p.notes
assert [(s.team, s.action, s.map_no) for s in p.steps if s.mode == V.OBJ] == [("A", "ban", None), ("A", "pick", 3), ("B", "side", 3), ("A", "last", 6), ("A", "side", 6)]
# Lotus banned in Hardpoint is still there in SnD and Hijack
st = run(7, MW4, ["Lotus"])
assert "Lotus" in st.left[V.SND] and "Lotus" in st.left[V.OBJ] and "Lotus" not in st.left[V.HP]
# a full MW4 best of 7
ch = ["Lotus", "Sentry", "Rooftops", "good", "Munition", "bad",          # HP: A ban, B ban, A pick 1, B side, B pick 4, A side
      "Coal", "Silkworm", "Lotus", "attack", "Rooftops", "defend", "Munition", "attack",   # SnD
      "Lithium", "Lotus", "good", "skip"]                                     # Hijack: A ban, A pick 3, B side, (Munition left), A side
st = run(7, MW4, ch)
assert st.done, st.i
got = [(s.map_no, s.mode, s.map, s.by, s.side, s.side_by) for s in st.slots.values()]
assert got == [(1, "HP", "Rooftops", "A", "good", "B"), (2, "SND", "Lotus", "B", "attack", "A"), (3, "OBJ", "Lotus", "A", "good", "B"),
               (4, "HP", "Munition", "B", "bad", "A"), (5, "SND", "Rooftops", "A", "defend", "B"), (6, "OBJ", "Munition", "left", None, None),
               (7, "SND", "Munition", "A", "attack", "A")], got
assert st.auto == [17], st.auto   # Map 6 filled in by itself
# best of 9: SnD decider is the one map left after 2 bans and 3 picks of 6
st = run(9, {V.HP: POOL[:6], V.SND: POOL[:6], V.OBJ: POOL[:4]}, [])
p9 = st.plan
assert [s.map_no for s in p9.steps if s.mode == V.SND and s.action in ("pick", "last")] == [2, 5, 7, 9]
assert [s.map_no for s in p9.steps if s.mode == V.HP and s.action == "pick"] == [1, 4, 8]
assert V.ORDER[9] == ["HP", "SND", "OBJ", "HP", "SND", "OBJ", "SND", "HP", "SND"]
# 'last' with more than one map left: Team A chooses (SnD Bo9 with 8 maps)
p = V.plan(9, {V.HP: POOL[:6], V.SND: POOL[:8], V.OBJ: POOL[:4]}, NAMES)
st = V.replay(p, [])
while not st.done and not (st.step.action == "last" and st.step.mode == V.SND):
    st = V.replay(p, st.choices + [st.options()[0]])
assert st.step.team == "A" and len(st.options()) == 3 and "From the Maps Left" in V.prompt(st, NAMES)
# undo past an automatic step goes back to the last real choice
p = V.plan(7, MW4, NAMES); st = V.replay(p, ch); prev = V.replay(p, ch[:-1])
assert prev.step.action == "side" and prev.step.map_no == 6 and prev.slots[6].map == "Munition"
# plan vs played
rec = V.record(V.replay(V.plan(7, MW4, NAMES), ch))
mode_of = {"HP": "HP", "SND": "SND", "HJ": "OBJ"}
played = [{"map_no": 1, "mode": "HP", "map": "Rooftops"}, {"map_no": 2, "mode": "SND", "map": "Coal"}, {"map_no": 3, "mode": "HJ", "map": "Lotus"},
          {"map_no": 4, "mode": "HP", "map": "Munition"}]
c = V.compare(rec, played, 7, mode_of)
assert [x["status"] for x in c] == ["as_planned", "changed", "as_planned", "as_planned", "not_played", "not_played", "not_played"]
assert c[1]["by"] == "B"                     # pick credit stays with the slot when the map changes
assert not any(x["stale"] for x in c) and all(x["stale"] for x in V.compare(rec, played, 9, mode_of))
# record refuses an unfinished veto; replay refuses extra choices
for bad in (lambda: V.record(V.replay(V.plan(7, MW4, NAMES), ch[:5])), lambda: V.replay(V.plan(7, MW4, NAMES), ch + ["good"])):
    try: bad(); raise AssertionError
    except V.VetoError: pass
# duplicate names in a pool are ignored; best of 1 is Hardpoint only
assert V.plan(3, {V.HP: ["A", "A", "B", "C"], V.SND: POOL[:3], V.OBJ: POOL[:3]}, NAMES).pools[V.HP] == ["A", "B", "C"]
assert [s.mode for s in V.plan(1, {V.HP: POOL[:6]}, NAMES).steps] == ["HP"] * 4
assert V.plan(2, MW4, NAMES).problem
print("hand-written rules: ok")
print("ALL PASSED", f"{time.time() - t0:.1f}s")