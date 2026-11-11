"""Page setup shared by every page: config, theme, title row with the season picker."""
from __future__ import annotations

import json

import streamlit as st
import streamlit.components.v1 as components

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
        ui.theme_switch()
        motion()


_MOTION = (ROOT / "cbl" / "ui" / "motion.js").read_text(encoding="utf-8")


def motion() -> None:
    """Puts cbl/ui/motion.js into the page once: figures play when scrolled into view and again when a filter changes
    them. Streamlit doesn't run scripts placed in page text, so a zero-height component adds it to the page instead."""
    with st.container(key="cb_motion"):
        components.html("<script>(function(){var P=window.parent.document;if(P.getElementById('cb-motion'))return;"
                        "var s=P.createElement('script');s.id='cb-motion';s.textContent=" + json.dumps(_MOTION).replace("</", "<\\/")
                        + ";P.head.appendChild(s);})();</script>", height=0)


def header(title: str, allow_all: bool = True, key: str = "season", show_picker: bool = True) -> str:
    """Eyebrow + big title on the left, season picker on the right. The choice is shared across pages."""
    opts = data.season_options(allow_all)
    values = [v for v, _ in opts]
    cur = st.session_state.get("season") or data.default_season()
    if cur not in values:
        cur = data.default_season() if data.default_season() in values else values[0]
    with st.container(key="cb_head"):
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