"""Checks the stats engine against numbers verified by hand from the BO7 workbook.

    python -m pytest tests        (or: python tests/test_stats.py)
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cbl.engine import Engine  # noqa: E402
from cbl.stats import profile, projections  # noqa: E402

DATA = json.loads((ROOT / "data" / "bo7_seed.json").read_text(encoding="utf-8"))
E = Engine(DATA, "BO7")


def test_mar_totals():
    tot = E.pm.groupby("player").mar.sum()
    expect = {"Arath": 13.48, "Carl": 12.60, "Vera": 6.47, "Miguel": 6.34, "Sal": 5.06, "Jason": 3.89, "Ed": 2.67, "Fonz": -0.32}
    for p, v in expect.items():
        assert abs(tot[p] - v) < 0.011, (p, tot[p], v)


def test_series_mvps():
    counts = pd.Series([v[0] for v in E.series_mvps().values()]).value_counts().to_dict()
    assert counts == {"Arath": 6, "Carl": 6, "Ed": 2}


def test_kd_and_rivalry():
    a = E.pm[E.pm.player == "Arath"]
    assert round(a.kills.sum() / a.deaths.sum(), 2) == 1.44
    assert E.rivalry_record(["Arath", "Jason", "Miguel"], ["Carl", "Sal", "Vera"])[:2] == (4, 4)


def test_ratings():
    r, _ = E.ratings()
    assert r == {"Arath": 1704, "Carl": 1676, "Miguel": 1497, "Sal": 1458, "Jason": 1412, "Vera": 1519, "Fonz": 1296, "Ed": 1760}


def test_radar():
    sp = E.profile()["sp"]
    assert list(sp.loc["Arath"]) == [86, 64, 86, 86, 29, 81]
    assert list(sp.loc["Ed"]) == [100, 14, 71, 100, 100, 82]


def test_finishing():
    fin = E.finishing_frame().groupby("player").fin.mean()
    for p, v in {"Arath": 0.36, "Carl": 0.13, "Miguel": -1.24, "Ed": 1.53}.items():
        assert abs(fin[p] - v) < 0.011, (p, fin[p], v)


def test_projection():
    r = projections.project(E.pm, "Arath", "HP", "Den")
    assert abs(r["kills"]["e"] - 37.3) < 0.3
    assert r["kills"]["lo"] <= 30 and r["kills"]["hi"] >= 44


def test_pressure_maps():
    assert int(E.maps.press.sum()) == 30


def test_clutch_shape():
    c = profile.clutch(E.pm, E.players)
    assert c["Arath"][1] == 30 and c["Arath"][5] == 24


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
