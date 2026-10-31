"""Title templates (config/titles/*.yaml) and stat labels."""
from __future__ import annotations

import copy
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
TITLES_DIR = ROOT / "config" / "titles"

STAT_LABELS = {
    "kills": "Kills", "deaths": "Deaths", "assists": "Assists", "non_traded_kills": "NTK",
    "highest_streak": "Streak", "damage": "Damage", "hill_time": "Hill time (sec)", "objective_kills": "Obj kills",
    "first_bloods": "First bloods", "first_deaths": "First deaths", "bombs_planted": "Plants",
    "overloads": "Overloads", "carrier_kills": "Carrier kills", "kills_as_carrier": "Kills as carrier",
    "accuracy": "Accuracy %",
    # read off the caster scoreboard; optional, kept under More Stats when typing by hand
    "avg_hill_time": "Avg hill time (sec)", "contested_hill_time": "Contested hill (sec)", "kills_per_hill": "Kills/hill",
    "dmg_per_hill": "Dmg/hill", "bombs_defused": "Defuses", "kills_per_round": "Kills/round", "dmg_per_round": "Dmg/round",
}
# extra scoreboard stats per mode (not used by MAR; saved as the board shows them)
EXTRA_STATS = {"HP": ["avg_hill_time", "contested_hill_time", "kills_per_hill", "dmg_per_hill"],
               "SND": ["bombs_defused", "kills_per_round", "dmg_per_round"]}
FLOAT_STATS = {"accuracy", "kills_per_hill", "dmg_per_hill", "kills_per_round", "dmg_per_round"}
CORE_STATS = ["kills", "deaths", "assists", "damage", "non_traded_kills", "highest_streak"]


@lru_cache(maxsize=None)
def templates() -> dict[str, dict]:
    out = {}
    for p in sorted(TITLES_DIR.glob("*.yaml")):
        d = yaml.safe_load(p.read_text(encoding="utf-8"))
        out[d["id"]] = d
    return dict(sorted(out.items(), key=lambda kv: kv[1].get("order", 0)))


def template(title_id: str) -> dict:
    return copy.deepcopy(templates()[title_id])