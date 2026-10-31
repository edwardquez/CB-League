"""Shared look for every page: Mist palette, Hanken Grotesk, and small HTML building blocks.

Usage on a page (right after st.set_page_config):

    from cbl.ui import styles as ui
    ui.apply()
    ui.html(ui.eyebrow("Black Ops 7 · 2026") + ui.h1("Standings"))
"""
from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

# ---------- Colors (Mist) ---------- #
BG = "#D3D9D4"        # page background
PANEL = "#E2E7E3"     # cards, sidebar
INK = "#212A31"       # text, rules
SLATE = "#2E3944"
BLUE = "#124E66"      # accent / best
STEEL = "#748D92"
MUTED = "#4A5C62"     # secondary text
RULE = "#BCC5C1"      # hairlines
TRACK = "#C5CDC9"     # empty part of a bar
PALE = "#EEF1EF"
RUST = "#A8543C"      # misses / warnings (used sparingly)
LIGHT = "#F2F4F2"

FONT = "'Hanken Grotesk', system-ui, sans-serif"
_FONT_URL = "https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@200;300;400;500;600&display=swap"

_CSS = f"""
<style>
@import url('{_FONT_URL}');
.cb {{ font-family: {FONT}; }}
.stApp {{ background: {BG}; }}
[data-testid="stMainBlockContainer"] {{ max-width: 1040px; padding-top: 3rem; padding-bottom: 5rem; }}
[data-testid="stSidebar"] {{ background: {PANEL}; border-right: 1px solid {RULE}; }}
[data-testid="stSidebarContent"] {{ display: flex; flex-direction: column; }}
[data-testid="stSidebarHeader"] {{ order: 0; }}
[data-testid="stSidebarUserContent"] {{ order: 1; padding-top: 0 !important; padding-bottom: 36px !important; flex: 0 0 auto;
  margin-top: -62px; position: relative; z-index: 1; pointer-events: none; }}
[data-testid="stSidebarNav"] {{ order: 2; }}
[data-testid="stSidebarNavSeparator"] {{ display: none; }}
[data-testid="stSidebarNav"] a span {{ font-family: {FONT}; font-size: 14px; color: {MUTED}; }}
[data-testid="stSidebarNav"] a[aria-current="page"] {{ background: #C9D1CC; }}
[data-testid="stSidebarNav"] a[aria-current="page"] span {{ color: {INK}; font-weight: 600; }}
body {{ font-variant-numeric: tabular-nums; color: {INK}; }}
h1, h2, h3 {{ font-family: {FONT} !important; color: {INK}; }}
.cb table {{ border: none; border-collapse: collapse; }}
.cb th, .cb td {{ border: none !important; }}
.cb a {{ color: {BLUE}; text-underline-offset: 3px; }}
div[data-testid="stSegmentedControl"] button, div[data-testid="stButton"] button {{ font-family: {FONT}; }}
/* segmented controls: filled ink when picked (as in the mockups) */
button[data-variant="segmented_control"] {{ background: transparent; border-color: {STEEL}; color: {INK}; min-height: 38px; }}
button[data-variant="segmented_control"][aria-checked="true"] {{ background: {INK} !important; border-color: {INK} !important; color: {BG} !important; }}
button[data-variant="segmented_control"][aria-checked="true"] p {{ color: {BG} !important; font-weight: 600; }}
/* underlined tabs: segmented controls placed with ui.tabs() */
[class*="st-key-cbtabs_"] [data-testid="stElementContainer"], [class*="st-key-cbtabs_"] [data-testid="stButtonGroup"],
[class*="st-key-cbtabs_"] [data-testid="stButtonGroup"] > div {{ width: 100% !important; }}
[class*="st-key-cbtabs_"] {{ border-bottom: 1px solid {RULE}; margin-bottom: 8px; }}
[class*="st-key-cbtabs_"] [role="radiogroup"] {{ gap: 0 28px; flex-wrap: wrap; max-width: none !important; }}
[class*="st-key-cbtabs_"] button[data-variant="segmented_control"] {{ background: transparent !important; border: 0 !important;
  border-bottom: 2px solid transparent !important; border-radius: 0 !important; padding: 0 2px !important; min-height: 44px; margin-bottom: -1px; }}
[class*="st-key-cbtabs_"] button[data-variant="segmented_control"] p {{ color: {MUTED} !important; font-size: 15px; font-weight: 400; }}
[class*="st-key-cbtabs_"] button[data-variant="segmented_control"][aria-checked="true"] {{ border-bottom-color: {INK} !important; }}
[class*="st-key-cbtabs_"] button[data-variant="segmented_control"][aria-checked="true"] p {{ color: {INK} !important; font-weight: 600; }}
/* tooltips: hover on desktop, tap on phones */
.cb-tap {{ position: relative; cursor: pointer; outline: none; -webkit-tap-highlight-color: transparent; }}
.cb-tap:hover, .cb-tap:focus {{ z-index: 30; }}
.cb-tip {{ display: none; position: absolute; bottom: calc(100% + 8px); left: 50%; transform: translateX(-50%);
  width: max-content; max-width: 250px; padding: 8px 10px; background: {INK}; color: {PANEL}; font-size: 13px;
  font-weight: 400; line-height: 1.4; text-align: left; text-transform: none; letter-spacing: 0; white-space: normal;
  text-wrap: pretty; z-index: 40; pointer-events: none; box-shadow: 0 4px 14px rgba(33,42,49,0.2); }}
.cb-tip b {{ display: block; font-weight: 600; }}
.cb-tip.l {{ left: 0; transform: none; }} .cb-tip.r {{ left: auto; right: 0; transform: none; }}
.cb-tip.below {{ bottom: auto; top: calc(100% + 8px); }}
.cb-tap:hover .cb-tip, .cb-tap:focus .cb-tip, .cb-tap:focus-within .cb-tip {{ display: block; }}
.cb-tap:hover > .hl, .cb-tap:focus > .hl {{ background: {PANEL}; }}
.cb-row:hover {{ background: {PANEL}; }}
@media (max-width: 640px) {{
  [data-testid="stMainBlockContainer"] {{ padding-top: 1.5rem; padding-left: 16px; padding-right: 16px; }}
  .cb-h1 {{ font-size: 40px !important; }}
  .cb-h2 {{ font-size: 26px !important; }}
}}
</style>
"""


def apply() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def tabs(key: str, options: list, labels: dict, default=None) -> str:
    """Underlined tab row (a segmented control styled as tabs). Returns the picked option."""
    import streamlit as _st
    with _st.container(key=f"cbtabs_{key}"):
        v = _st.segmented_control(key, options, default=default if default is not None else options[0], format_func=lambda o: labels.get(o, o),
                                  key=key, label_visibility="collapsed")
    return v or (default if default is not None else options[0])


def html(markup: str) -> None:
    st.markdown(f"<div class='cb'>{markup}</div>", unsafe_allow_html=True)


# ---------- formatting ---------- #
def sg(v, d=1) -> str:
    if v is None or pd.isna(v):
        return "—"
    return ("+" if v >= 0 else "−") + f"{abs(v):.{d}f}"


def mmss(v) -> str:
    if v is None or pd.isna(v):
        return "—"
    v = int(round(v))
    return f"{v // 60}:{v % 60:02d}"


def n0(v) -> str:
    return "—" if v is None or pd.isna(v) else f"{v:,.0f}"


def pct(v) -> str:
    return "—" if v is None or pd.isna(v) else f"{round(v * 100)}%"


def mix(a: str, b: str, t: float) -> str:
    t = max(0.0, min(1.0, t))
    A = [int(a[i:i + 2], 16) for i in (1, 3, 5)]; B = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(A, B))


def shade(rank_frac: float, faded: bool = False) -> tuple[str, str]:
    """Background/text for a heat cell: pale (worst) -> deep blue (best)."""
    bg = mix(PALE, BLUE, rank_frac); fg = LIGHT if rank_frac >= 0.6 else INK
    if faded:
        bg = mix(bg, BG, 0.65); fg = INK
    return bg, fg


# ---------- building blocks ---------- #
def eyebrow(text: str, color: str = MUTED) -> str:
    return (f"<div style='font-size:12px; font-weight:600; letter-spacing:1.6px; text-transform:uppercase; "
            f"color:{color};'>{escape(text)}</div>")


def h1(text: str, size: int = 60) -> str:
    return (f"<h1 class='cb-h1' style='margin:10px 0 0; font-weight:300; font-size:{size}px; line-height:1; "
            f"letter-spacing:-1px; padding:0;'>{escape(text)}</h1>")


def h2(text: str, margin_top: int = 48, rule: bool = True, right: str = "") -> str:
    border = f"padding-bottom:8px; border-bottom:2px solid {INK};" if rule else ""
    return (f"<div style='display:flex; justify-content:space-between; align-items:end; gap:12px; flex-wrap:wrap; "
            f"margin-top:{margin_top}px; {border}'><div role='heading' aria-level='2' class='cb-h2' "
            f"style='margin:0; font-weight:300; font-size:34px; letter-spacing:-0.5px; line-height:1.15;'>{escape(text)}</div>{right}</div>")


def label(text: str, margin_top: int = 0, rule: bool = False) -> str:
    border = f"padding-bottom:8px; border-bottom:1px solid {STEEL};" if rule else ""
    return (f"<div role='heading' aria-level='3' style='margin-top:{margin_top}px; font-size:12px; font-weight:600; "
            f"letter-spacing:1.6px; text-transform:uppercase; color:{MUTED}; {border}'>{escape(text)}</div>")


def note(text: str, margin_top: int = 8, size: int = 13, max_width: int = 680) -> str:
    return (f"<p style='margin:{margin_top}px 0 0; font-size:{size}px; color:{MUTED}; line-height:1.5; "
            f"max-width:{max_width}px;'>{text}</p>")


def tagbox(text: str, color: str = MUTED, border: str = RULE) -> str:
    return (f"<span style='display:inline-block; margin-left:8px; font-size:9px; font-weight:600; letter-spacing:0.6px; "
            f"color:{color}; border:1px solid {border}; padding:1px 5px; vertical-align:middle; white-space:nowrap;'>"
            f"{escape(text.upper())}</span>")


def small_sample() -> str:
    return tagbox("Small sample")


def tip(title: str, *lines: str, align: str = "", below: bool = False) -> str:
    body = "".join(f"<span style='display:block'>{x}</span>" for x in lines if x)
    cls = " ".join(c for c in [align, "below" if below else ""] if c)
    return f"<span role='tooltip' class='cb-tip {cls}'><b>{title}</b>{body}</span>"


TAP = "class='cb-tap' tabindex='0'"


def kpis(items: list[tuple[str, str]], size: int = 44, min_w: int = 140) -> str:
    cells = "".join(f"<div style='padding:20px 0 16px'><div style='font-weight:300; font-size:{size}px; line-height:1'>{escape(str(v))}</div>"
                    f"<div style='font-size:13px; color:{MUTED}; margin-top:8px'>{escape(str(l))}</div></div>" for v, l in items)
    return (f"<div style='display:grid; grid-template-columns:repeat(auto-fit, minmax(max({min_w}px, 22%), 1fr)); "
            f"column-gap:24px; border-top:2px solid {INK}; margin-top:12px'>{cells}</div>")


def bar_row(name: str, value: str, frac: float, color: str = STEEL, tipbox: str = "", bold: bool = False,
            name_w: int = 120, val_w: int = 64, extra: str = "") -> str:
    w = max(frac * 100, 1.0)
    return (f"<div {TAP} style='display:grid; grid-template-columns:{name_w}px minmax(0,1fr) {val_w}px; align-items:center; "
            f"gap:10px; min-height:34px'><span style='font-size:14px; font-weight:{600 if bold else 400}'>{name}{extra}</span>"
            f"<div style='height:12px; background:{TRACK}'><div style='height:12px; width:{w:.1f}%; background:{color}'></div></div>"
            f"<span style='text-align:right; font-size:14px; font-weight:{600 if bold else 400}'>{value}</span>{tipbox}</div>")


def table(cols: list[tuple[str, str]], rows: list[list], min_width: int = 600, cell_pad: str = "10px 8px",
          header_border: str = STEEL) -> str:
    """cols: [(label, align)]; rows: lists of cell dicts {v, bg, fg, w, title} or plain strings."""
    th = "".join(f"<th style='text-align:{a}; font-weight:600; font-size:12px; color:{MUTED}; padding:10px 8px; "
                 f"border-bottom:1px solid {header_border} !important; white-space:nowrap'>{escape(c)}</th>" for c, a in cols)
    trs = []
    for r in rows:
        if r == "SPACER":  # breathing room between two groups of rows (e.g. the two teams)
            trs.append(f"<tr><td colspan='{len(cols)}' style='height:16px; padding:0; border:0 !important; background:transparent'></td></tr>")
            continue
        tds = []
        for (c, a), cell in zip(cols, r):
            if not isinstance(cell, dict):
                cell = {"v": cell}
            tds.append(f"<td style='text-align:{a}; padding:{cell_pad}; border-bottom:1px solid {RULE} !important; "
                       f"white-space:nowrap; font-weight:{cell.get('w', 400)}; background:{cell.get('bg', 'transparent')}; "
                       f"color:{cell.get('fg', INK)}'" + (f" title='{escape(cell['title'])}'" if cell.get("title") else "") + f">{cell['v']}</td>")
        trs.append("<tr>" + "".join(tds) + "</tr>")
    return (f"<div style='overflow-x:auto; margin-top:8px'><table style='width:100%; min-width:{min_width}px; font-size:14px'>"
            f"<thead><tr>{th}</tr></thead><tbody>{''.join(trs)}</tbody></table></div>")


def empty_box(title: str, body: str, margin_top: int = 28) -> str:
    return (f"<div style='margin-top:{margin_top}px; padding:24px; border:1px dashed {STEEL}'><div style='font-size:18px; "
            f"font-weight:500'>{escape(title)}</div><p style='margin:8px 0 0; font-size:14px; color:{MUTED}; line-height:1.5'>{body}</p></div>")


def legend(items: list[tuple[str, str]]) -> str:
    return ("<div style='display:flex; flex-wrap:wrap; gap:6px 18px; margin-top:10px; font-size:12px; color:" + MUTED + "'>"
            + "".join(f"<span style='display:inline-flex; align-items:center; gap:6px'>{sw}{escape(t)}</span>" for sw, t in items) + "</div>")


def swatch(color: str, w: int = 12, h: int = 12, round_: bool = False, border: str = "") -> str:
    r = "border-radius:50%;" if round_ else ""
    b = f"border:{border};" if border else ""
    return f"<span style='display:inline-block; width:{w}px; height:{h}px; background:{color}; {r} {b} box-sizing:border-box'></span>"


def plotly_layout(fig, height: int = 320, legend: bool = False):
    fig.update_layout(height=height, margin=dict(l=8, r=8, t=8, b=8), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Hanken Grotesk, sans-serif", color=INK, size=12),
                      showlegend=legend, hoverlabel=dict(bgcolor=INK, font_color=PANEL, font_family="Hanken Grotesk"),
                      legend=dict(orientation="h", y=-0.2))
    fig.update_xaxes(gridcolor=TRACK, linecolor=STEEL, zeroline=False)
    fig.update_yaxes(gridcolor=TRACK, linecolor=STEEL, zeroline=False)
    return fig


PLOT_CONFIG = {"displayModeBar": False, "responsive": True}


def map_img(name: str, kind: str = "thumb") -> str:
    """URL of a map picture served from static/maps (blank tile if we don't have one)."""
    from cbl.config import ROOT
    f = f"{name.lower().replace(' ', '-')}-{kind}.webp"
    return f"app/static/maps/{f}" if (ROOT / "static" / "maps" / f).exists() else ""


def img_tag(name: str, kind: str = "thumb", width: str = "100%") -> str:
    src = map_img(name, kind)
    if not src:
        return (f"<div style='width:{width}; aspect-ratio:16/9; background:{RULE}; display:flex; align-items:center; "
                f"justify-content:center; font-size:11px; font-weight:600; letter-spacing:1px; color:{MUTED}'>{escape(name.upper())}</div>")
    return f"<img src='{src}' alt='' style='display:block; width:{width}; aspect-ratio:16/9; object-fit:cover'>"


def tint(v, arr, low: bool = False, faded: bool = False) -> tuple[str, str]:
    """Heat colors for v among arr (average rank for ties)."""
    vals = [x for x in arr if x == x]
    if len(vals) < 2 or v is None or v != v:
        return "transparent", INK
    lt = sum(1 for x in vals if x < v - 1e-9); eq = sum(1 for x in vals if abs(x - v) <= 1e-9)
    r = (lt + (max(eq, 1) - 1) / 2) / (len(vals) - 1)
    return shade(1 - r if low else r, faded)