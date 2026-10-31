"""Page setup shared by every page: config, theme, title row with the season picker."""
from __future__ import annotations

import streamlit as st

from cbl import data
from cbl.config import ROOT
from cbl.ui import styles as ui

ICON = str(ROOT / "assets" / "favicon.png")


def start(page_title: str) -> None:
    st.set_page_config(page_title=f"{page_title} · CB League", page_icon=ICON, layout="wide",
                       initial_sidebar_state="auto")
    ui.apply()
    # practice data only ever shows on the two pages that enter games
    st.session_state["_on_scorekeeper"] = page_title in ("Scorekeeper", "Tournaments")
    with st.sidebar:
        ui.html(f"<div style='display:flex; align-items:center; gap:6px; font-size:11px; font-weight:600; letter-spacing:2.5px; "
                f"margin:4px 0 4px 4px'><span style='border:1px solid {ui.INK}; padding:3px 6px'>CB</span><span>LEAGUE</span></div>")


def header(title: str, allow_all: bool = True, key: str = "season", show_picker: bool = True) -> str:
    """Eyebrow + big title on the left, season picker on the right. The choice is shared across pages."""
    opts = data.season_options(allow_all)
    values = [v for v, _ in opts]
    cur = st.session_state.get("season") or data.default_season()
    if cur not in values:
        cur = data.default_season() if data.default_season() in values else values[0]
    left, right = st.columns([3, 1], vertical_alignment="bottom")
    with right:
        if show_picker:
            pick = st.selectbox("Season", values, index=values.index(cur), format_func=dict(opts).get, key=f"_pick_{key}")
            st.session_state["season"] = pick
            cur = pick
    with left:
        ui.html(ui.eyebrow(data.season_label(cur)) + ui.h1(title))
    st.write("")
    return cur


def title_id(season: str) -> str | None:
    return None if season == "ALL" else season