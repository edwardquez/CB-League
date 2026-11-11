"""Shared look for every page: the two themes (Harbour Sunrise light, Pastel Night Shade dark), Hanken Grotesk,
and small HTML building blocks.

Usage on a page (page.start() calls apply() for you):

    from cbl.ui import styles as ui
    ui.html(ui.eyebrow("Black Ops 7 · 2026") + ui.h1("Standings"))

Colours are per session: ui.INK, ui.BLUE and the rest always give the colour for the theme this viewer picked
(the Dark mode switch in the sidebar), so two people on different themes never see each other's colours.
"""
from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

# ---------- Themes ---------- #
# Harbour Sunrise (light): Pastel Night's crayon texture turned to dawn, in Impression, Sunrise colours.
DAWN = dict(
    bg="#DCE3E2", panel="#E9EEEC", side="#CDD8D8", navon="#C0CDCE", ink="#1F2F37", slate="#2A3B43", blue="#1C4A5E",
    steel="#73898F", muted="#465962", rule="#BCC9CA", rule2="#A9B9BB", track="#C7D2D2", pale="#EEF2F0", rust="#B8482A",
    on="#F4F6F4", amber="#F0CBAE", hl="#FBEFC2",
    ramp=["#EEF2F0", "#C0D0D4", "#8AA7B2", "#4E7787", "#1C4A5E"],
    wash="rgba(221,226,222,.3)", feather="0 0 56px 40px", side1="rgba(205,216,216,.93)", side2="rgba(205,216,216,.88)",
    shadow="0 1px 0 rgba(255,255,255,.45)", grain=".1", blend="multiply", tip_shadow="rgba(31,47,55,.2)",
    team=["#1F2F37", "#1C4A5E", "#73898F", "#2A3B43"])
# Pastel Night Shade (dark): the sidebar's deep indigo as the page colour, subtle oil-pastel strokes, embers.
SHADE = dict(
    bg="#0D162A", panel="#121D36", side="#0A1226", navon="#18264A", ink="#EEF0EA", slate="#C9D6DF", blue="#7CC0DE",
    steel="#7F9DB3", muted="#B2C2CE", rule="#24395A", rule2="#2E4A6E", track="#16243F", pale="#14213C", rust="#EE7350",
    on="#0B1428", amber="#7A5A1C", hl="#3A3220",
    ramp=["#16243F", "#1D3C5A", "#285A7A", "#4A8DAD", "#86C4DE"],
    wash="rgba(13,22,42,.42)", feather="0 0 28px 20px", side1="rgba(6,10,24,.9)", side2="rgba(6,10,24,.86)",
    shadow="0 1px 3px rgba(4,8,22,.7)", grain=".2", blend="overlay", tip_shadow="rgba(0,0,0,.5)",
    team=["#EEF0EA", "#7CC0DE", "#7F9DB3", "#C9D6DF"])

_NAMES = {"BG": "bg", "PANEL": "panel", "INK": "ink", "SLATE": "slate", "BLUE": "blue", "STEEL": "steel", "MUTED": "muted",
          "RULE": "rule", "RULE2": "rule2", "TRACK": "track", "PALE": "pale", "RUST": "rust", "LIGHT": "on", "ON": "on",
          "NAVON": "navon", "AMBER": "amber", "HL": "hl", "SIDE": "side", "WASH": "wash"}


def is_dark() -> bool:
    try:
        return bool(st.session_state.get("_dark", False))
    except Exception:          # outside a Streamlit run (tests, scripts)
        return False


def pal() -> dict:
    return SHADE if is_dark() else DAWN


def __getattr__(name: str):
    """ui.INK, ui.BLUE ... resolve to this viewer's theme every time they're used."""
    if name in _NAMES:
        return pal()[_NAMES[name]]
    raise AttributeError(name)


FONT = "'Hanken Grotesk', system-ui, sans-serif"
_FONT_URL = "https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@200;300;400;500;600;700&display=swap"
_FX = json.loads((Path(__file__).with_name("theme_fx.json")).read_text())
_GRAIN = ("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='300' height='300'><filter id='g'>"
          "<feTurbulence type='fractalNoise' baseFrequency='.95' numOctaves='3' stitchTiles='stitch'/><feColorMatrix type='saturate' values='0'/>"
          "</filter><rect width='100%25' height='100%25' filter='url(%23g)'/></svg>")


def _shimmer(key: str) -> str:
    """Embers that pulse and drift, and light that runs along a few of the texture's spokes. The layer covers the
    window the same way the background image does (cover, centred), so the glints stay on their spokes."""
    fx = _FX[key]; a = fx["aspect"]; phone = key.endswith("phone")
    # on a desktop the sidebar covers the left edge of the picture: no embers behind it
    em = "".join(f"<i class='{c}' style='left:calc(var(--W) * {x}); top:calc(var(--H) * {y}); --c:{col}; --s:{s}px; --d:{d}s; --dl:{dl}s; --rise:{r}s'></i>"
                 for c, x, y, col, s, d, dl, r in fx["embers"] if phone or x > .14)
    sw = "".join(f"<span class='{c}' style='left:calc(var(--W) * {x}); top:calc(var(--H) * {y}); width:calc(var(--W) * {L}); transform:rotate({ang}deg); "
                 f"--len:calc(var(--W) * {L}); --sd:{sd}s; --sdur:{sdur}s; height:{hh}px; margin-top:{-hh / 2:.0f}px'><b></b></span>"
                 for c, x, y, L, ang, sd, sdur, hh in fx["sweeps"])
    return (f"<div class='cb-shim {'cb-ph' if phone else 'cb-dk'}' aria-hidden='true' style='--W:max(100vw, {a * 100:.2f}vh); "
            f"--H:max(100vh, {100 / a:.2f}vw)'>{sw}{em}</div>")


def _css(c: dict, dark: bool) -> str:
    mode = "shade" if dark else "dawn"
    v = "".join(f"--cb-{k}:{c[k]};" for k in ("bg", "panel", "side", "navon", "ink", "slate", "blue", "steel", "muted", "rule",
                                               "rule2", "track", "pale", "rust", "on", "wash"))
    tex = "app/static/theme"
    return f"""
<style>
@import url('{_FONT_URL}');
:root {{ {v} color-scheme: {'dark' if dark else 'light'}; }}
.cb {{ font-family: {FONT}; }}
/* ---- page ground: the painted texture, fixed behind everything ---- */
.stApp {{ background: url({tex}/{mode}-desk.webp) center / cover no-repeat fixed, {c['bg']}; color: {c['ink']}; }}
@media (max-width: 640px) {{ .stApp {{ background-image: url({tex}/{mode}-phone.webp); }} }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stMain"] {{ position: relative; z-index: 1; }}
[data-testid="stMainBlockContainer"] {{ max-width: 1040px; padding-top: 2rem; padding-bottom: 5rem; }}
.cb {{ line-height: normal; }}
.cb table[style*="border-spacing"] td, .cb table[style*="border-spacing"] th {{ line-height: 1.6; }}
.cb-grain {{ position: fixed; inset: 0; pointer-events: none; z-index: 999990; opacity: {c['grain']}; mix-blend-mode: {c['blend']};
  background: url("{_GRAIN}"); }}
/* ---- shimmer ---- */
.cb-shim {{ position: fixed; left: 50%; top: 50%; width: var(--W); height: var(--H); transform: translate(-50%, -50%); overflow: hidden;
  pointer-events: none; z-index: -1; }}
.cb-shim.cb-ph {{ display: none; }}
@media (max-width: 640px) {{ .cb-shim.cb-dk {{ display: none; }} .cb-shim.cb-ph {{ display: block; }} }}
.cb-shim .emb {{ position: absolute; width: var(--s); height: var(--s); margin: calc(var(--s) / -2) 0 0 calc(var(--s) / -2); border-radius: 50%;
  background: rgb(255,244,220); box-shadow: 0 0 calc(var(--s) * 2) calc(var(--s) * .6) rgba(var(--c), .75), 0 0 calc(var(--s) * 5) calc(var(--s) * 1.4) rgba(var(--c), .28);
  animation: embPulse var(--d) ease-in-out var(--dl) infinite alternate; will-change: opacity, transform; }}
.cb-shim .emb.drift {{ animation: embPulse var(--d) ease-in-out var(--dl) infinite alternate, embRise var(--rise) linear var(--dl) infinite; }}
@keyframes embPulse {{ from {{ opacity: .35; }} to {{ opacity: 1; }} }}
@keyframes embRise {{ 0% {{ transform: translate(0, 0); }} 50% {{ transform: translate(6px, -34px); }} 100% {{ transform: translate(-4px, -70px); }} }}
.cb-shim .emb.dim {{ animation-name: embPulseDim; }} .cb-shim .emb.dim.drift {{ animation-name: embPulseDim, embRise; }}
@keyframes embPulseDim {{ from {{ opacity: .2; }} to {{ opacity: .68; }} }}
.cb-shim .sweep {{ position: absolute; transform-origin: 0 50%; overflow: hidden; }}
.cb-shim .sweep b {{ position: absolute; top: 0; bottom: 0; left: 0; width: 140px; border-radius: 50%;
  background: radial-gradient(closest-side, rgba(150,200,230,.20), rgba(150,200,230,.07) 60%, rgba(150,200,230,0));
  transform: translateX(-160px); opacity: 0; animation: sweep var(--sdur) cubic-bezier(.45,0,.4,1) var(--sd) infinite; will-change: transform, opacity; }}
@keyframes sweep {{ 0% {{ transform: translateX(-160px); opacity: 0; }} 4% {{ opacity: 1; }} 22% {{ transform: translateX(var(--len)); opacity: 0; }} 100% {{ transform: translateX(var(--len)); opacity: 0; }} }}
.cb-shim .sweep.rare b {{ animation-name: sweepRare; }}
@keyframes sweepRare {{ 0% {{ transform: translateX(-160px); opacity: 0; }} 2% {{ opacity: .6; }} 10% {{ transform: translateX(var(--len)); opacity: 0; }} 100% {{ transform: translateX(var(--len)); opacity: 0; }} }}
{'' if dark else '''
.cb-shim .emb { --s2: calc(var(--s) * 1.6); width: var(--s2); height: var(--s2); background: #fff;
  box-shadow: 0 0 0 1px rgba(150,110,80,.28), 0 0 calc(var(--s) * 2) calc(var(--s) * .7) rgba(255,250,240,.95), 0 0 calc(var(--s) * 6) calc(var(--s) * 1.8) rgba(var(--c), .7); }
.cb-shim .sweep { height: 16px !important; margin-top: -8px !important; }
.cb-shim .sweep b { width: 220px; background: radial-gradient(closest-side, rgba(255,252,244,.95), rgba(255,236,214,.45) 55%, rgba(255,255,255,0)); animation-name: sweepLt; }
@keyframes sweepLt { 0% { transform: translateX(-220px); opacity: 0; } 5% { opacity: 1; } 35% { transform: translateX(var(--len)); opacity: 0; } 100% { transform: translateX(var(--len)); opacity: 0; } }
'''}
@media (prefers-reduced-motion: reduce) {{ .cb-shim .emb, .cb-shim .sweep b {{ animation: none !important; }} .cb-shim .sweep b {{ display: none; }} }}
/* ---- sidebar ---- */
[data-testid="stSidebar"] {{ background: linear-gradient(180deg, {c['side1']}, {c['side2']}) !important; border-right: 1px solid {'rgba(120,140,145,.35)' if not dark else 'rgba(54,85,122,.6)'}; }}
[data-testid="stSidebar"] > div {{ background: transparent; }}
@media (min-width: 641px) {{ [data-testid="stSidebar"][data-collapsed="false"] {{ width: 256px !important; min-width: 256px !important; max-width: 256px !important; }} }}
[data-testid="stSidebarContent"] {{ display: flex; flex-direction: column; }}
[data-testid="stSidebarHeader"] {{ order: 0; }}
[data-testid="stSidebarHeader"]::before {{ content: "CB LEAGUE"; font-family: {FONT}; font-size: 11px; font-weight: 600; letter-spacing: 2.5px;
  color: {c['ink']}; align-self: center; margin-left: 8px; margin-right: auto; }}
[data-testid="stSidebarHeader"] {{ display: flex; align-items: center; }}
[data-testid="stSidebarNav"] {{ order: 1; }}
[data-testid="stSidebarUserContent"] {{ order: 2; padding-top: 0 !important; }}
[data-testid="stSidebarNavSeparator"] {{ display: none; }}
[data-testid="stSidebarContent"] {{ padding: 12px 16px 32px !important; scrollbar-gutter: auto !important; }}
[data-testid="stSidebarHeader"] {{ padding: 8px 0 14px 0 !important; margin: 0 !important; height: auto !important; min-height: 0 !important; }}
[data-testid="stSidebarNav"], [data-testid="stSidebarNavItems"] {{ margin: 0 !important; padding: 0 !important; width: 100% !important; }}
[data-testid="stSidebarNavItems"] li {{ margin: 0 0 2px !important; }}
[data-testid="stSidebarNav"] a {{ border-radius: 2px; min-height: 36px; height: auto !important; padding: 0 10px !important; margin: 0 !important; display: flex; align-items: center; }}
[data-testid="stSidebarUserContent"] {{ padding: 0 !important; }}
[data-testid="stSidebarUserContent"] [data-testid="stVerticalBlock"] {{ gap: 0; }}
.st-key-cb_side {{ margin-top: 20px !important; }}
.st-key-cb_side [data-testid="stCheckbox"], .st-key-cb_side [data-testid="stToggle"] {{ padding-left: 10px; }}
.st-key-cb_side p {{ padding-left: 10px; }}
[data-testid="stSidebarNav"] a span {{ font-family: {FONT}; font-size: 14px; color: {c['muted']}; }}
[data-testid="stSidebarNav"] a:hover {{ background: {c['navon']}; }}
[data-testid="stSidebarNav"] a[aria-current="page"] {{ background: {c['navon']}; }}
[data-testid="stSidebarNav"] a[aria-current="page"] span {{ color: {c['ink']}; font-weight: 600; }}
.st-key-cb_side {{ border-top: 1px solid {c['rule']}; padding-top: 12px; gap: 2px; }}
[data-testid="stSidebarCollapseButton"] button, [data-testid="stSidebarCollapseButton"] svg, [data-testid="stExpandSidebarButton"],
[data-testid="stExpandSidebarButton"] svg, [data-testid="stSidebarCollapseButton"] [data-testid="stIconMaterial"],
[data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"], [data-testid="stSidebarCollapsedControl"] [data-testid="stIconMaterial"] {{ color: {c['ink']} !important; fill: {c['ink']}; }}
/* ---- type ---- */
body {{ font-variant-numeric: tabular-nums; color: {c['ink']}; }}
.stApp, .stApp p, .stApp li, .stApp label, [data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"] p,
[data-testid="stCaptionContainer"] {{ color: {c['ink']}; }}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {{ color: {c['muted']}; }}
h1, h2, h3, h4 {{ font-family: {FONT} !important; color: {c['ink']}; }}
[data-testid="stMain"] .cb-h1, [data-testid="stMain"] .cb-h2, [data-testid="stMain"] [role="heading"], [data-testid="stMain"] .cb p,
[data-testid="stMain"] .cb-lab {{ text-shadow: {c['shadow']}; }}
.cb a {{ color: {c['blue']}; text-underline-offset: 3px; }}
/* ---- figures sit on a soft wash, so the texture never runs under numbers ---- */
.cb table, .cb-fig {{ position: relative; isolation: isolate; }}
.cb table::before, .cb-fig::before {{ content: ""; position: absolute; inset: 0; z-index: -1;
  background: {c['wash']}; box-shadow: {c['feather']} {c['wash']}; pointer-events: none; }}
/* a table inside a side-scroll box: the box would clip the soft edge into a hard border, so the box carries the wash instead */
.cb div[style*="overflow-x"]:has(> table) {{ background: {c['wash']}; box-shadow: {c['feather']} {c['wash']}; }}
.cb div[style*="overflow-x"] > table::before {{ display: none; }}
.cb table {{ border: none; border-collapse: collapse; }}
.cb th, .cb td {{ border: none !important; }}
/* ---- controls: translucent, thin border, darker border on hover ---- */
div[data-testid="stSegmentedControl"] button, div[data-testid="stButton"] button {{ font-family: {FONT}; }}
button[data-testid^="stBaseButton-secondary"], [data-testid="stDownloadButton"] button, [data-testid="stPopover"] button,
button[data-testid="stBaseButton-tertiary"] {{ background: transparent; border-color: {c['rule2']}; color: {c['ink']}; }}
button[data-testid^="stBaseButton-secondary"]:hover, [data-testid="stDownloadButton"] button:hover, [data-testid="stPopover"] button:hover {{
  border-color: {c['ink']}; color: {c['ink']}; background: transparent; }}
button[data-testid^="stBaseButton-secondary"]:disabled {{ color: {c['muted']}; opacity: .55; }}
button[data-testid^="stBaseButton"] p {{ color: inherit; }}
button[data-testid^="stBaseButton-primary"]:not(:disabled), button[data-testid^="stBaseButton-primary"]:not(:disabled):focus,
button[data-testid^="stBaseButton-primary"]:not(:disabled):active {{ background: {c['ink']} !important; border-color: {c['ink']} !important; color: {c['bg']} !important; }}
button[data-testid^="stBaseButton-primary"]:not(:disabled):hover {{ background: {c['slate']} !important; border-color: {c['slate']} !important; color: {c['bg']} !important; }}
button[data-testid^="stBaseButton-primary"]:not(:disabled) p, button[data-testid^="stBaseButton-primary"]:not(:disabled) * {{ color: {c['bg']} !important; }}
button[data-testid^="stBaseButton-primary"]:disabled {{ background: transparent !important; border-color: {c['rule2']} !important; }}
button[data-testid^="stBaseButton-primary"]:disabled p {{ color: {c['muted']} !important; }}
button[data-variant="segmented_control"] {{ background: transparent; border-color: {c['rule2']}; color: {c['ink']}; min-height: 38px; }}
button[data-variant="segmented_control"] p {{ color: {c['ink']}; }}
button[data-variant="segmented_control"][aria-checked="false"]:hover {{ border-color: {c['ink']}; background: transparent; z-index: 1; }}
button[data-variant="pills"] {{ border-radius: 2px !important; background: transparent; border-color: {c['rule2']}; color: {c['ink']}; }}
button[data-variant="pills"] p {{ color: {c['ink']}; }}
button[data-variant="pills"]:not([aria-pressed="true"]):not([aria-checked="true"]):hover {{ border-color: {c['ink']}; }}
button[data-variant="pills"][aria-pressed="true"], button[data-variant="pills"][aria-checked="true"] {{ background: {c['ink']} !important; border-color: {c['ink']} !important; }}
button[data-variant="pills"][aria-pressed="true"] p, button[data-variant="pills"][aria-checked="true"] p,
button[data-variant="pills"][aria-pressed="true"] span, button[data-variant="pills"][aria-checked="true"] span {{ color: {c['bg']} !important; font-weight: 600; }}
button[data-variant="segmented_control"][aria-checked="true"] {{ background: {c['ink']} !important; border-color: {c['ink']} !important; color: {c['bg']} !important; }}
button[data-variant="segmented_control"][aria-checked="true"] p {{ color: {c['bg']} !important; font-weight: 600; }}
/* underlined tabs: segmented controls placed with ui.tabs() */
[class*="st-key-cbtabs_"] [data-testid="stElementContainer"], [class*="st-key-cbtabs_"] [data-testid="stButtonGroup"],
[class*="st-key-cbtabs_"] [data-testid="stButtonGroup"] > div {{ width: 100% !important; }}
[class*="st-key-cbtabs_"] {{ border-bottom: 1px solid {c['rule']}; margin-bottom: 8px; }}
[class*="st-key-cbtabs_"] [role="radiogroup"] {{ gap: 0 28px; flex-wrap: wrap; max-width: none !important; }}
[class*="st-key-cbtabs_"] button[data-variant="segmented_control"] {{ background: transparent !important; border: 0 !important;
  border-bottom: 2px solid transparent !important; border-radius: 0 !important; padding: 0 2px !important; min-height: 44px; margin-bottom: -1px; }}
[class*="st-key-cbtabs_"] button[data-variant="segmented_control"] p {{ color: {c['muted']} !important; font-size: 15px; font-weight: 400; }}
[class*="st-key-cbtabs_"] button[data-variant="segmented_control"][aria-checked="true"] {{ border-bottom-color: {c['ink']} !important; }}
[class*="st-key-cbtabs_"] button[data-variant="segmented_control"][aria-checked="true"] p {{ color: {c['ink']} !important; font-weight: 600; }}
/* select boxes, text fields, number fields */
[data-testid="stSelectbox"] [role="group"], [data-testid="stMultiSelect"] [role="group"], [data-testid="stTextInputRootElement"],
[data-testid="stTextInputRootElement"] > div, [data-testid="stNumberInputContainer"], [data-testid="stTextArea"] textarea,
[data-baseweb="select"] > div, [data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"] {{
  background: transparent !important; border-color: {c['rule2']} !important; }}
[data-testid="stSelectbox"] [role="group"]:hover, [data-testid="stTextInputRootElement"]:hover, [data-testid="stNumberInputContainer"]:hover {{
  border-color: {c['ink']} !important; }}
[data-testid="stSelectbox"] input, [data-testid="stTextInputRootElement"] input, [data-testid="stNumberInputContainer"] input,
[data-testid="stTextArea"] textarea, [data-baseweb="select"] *, [data-baseweb="input"] input {{
  color: {c['ink']} !important; -webkit-text-fill-color: {c['ink']}; background: transparent !important; }}
[data-testid="stSelectbox"] svg, [data-baseweb="select"] svg {{
  fill: {c['muted']} !important; color: {c['muted']} !important; }}
input::placeholder, textarea::placeholder {{ color: {c['muted']} !important; -webkit-text-fill-color: {c['muted']} !important; opacity: .8; }}
[data-testid="stNumberInputContainer"] button {{ background: transparent; color: {c['ink']}; border-color: {c['rule2']}; }}
[data-testid="stNumberInputContainer"] button:hover {{ background: {c['navon']}; }}
[data-testid="stSelectboxVirtualDropdown"], [data-testid="stSelectboxVirtualDropdown"] > div {{ background: {c['panel']} !important; }}
[data-baseweb="popover"] > div, [data-baseweb="popover"] ul, [data-baseweb="menu"], [role="listbox"] {{ background: {c['panel']} !important; }}
[data-baseweb="popover"] li, [role="option"] {{ color: {c['ink']} !important; background: {c['panel']}; }}
[data-baseweb="popover"] li:hover, [role="option"][aria-selected="true"], [role="option"]:hover {{ background: {c['navon']} !important; }}
[data-testid="stPopoverBody"] {{ background: {c['panel']} !important; border-color: {c['rule']} !important; color: {c['ink']}; }}
/* expanders, forms, uploads, alerts */
[data-testid="stExpander"] details {{ border-color: {c['rule2']}; background: transparent; }}
[data-testid="stExpander"] summary {{ color: {c['ink']}; background: transparent !important; }}
[data-testid="stExpander"] details, [data-testid="stExpander"] details > div {{ background: transparent !important; }}
[data-testid="stExpander"] summary:hover {{ color: {c['ink']}; }}
[data-testid="stExpander"] summary svg {{ color: {c['muted']}; fill: {c['muted']}; }}
[data-testid="stForm"] {{ border-color: {c['rule2']}; }}
[data-testid="stVerticalBlockBorderWrapper"], [data-testid="stLayoutWrapper"] > div[style*="border"] {{ border-color: {c['rule2']}; }}
[data-testid="stFileUploaderDropzone"] {{ background: {c['wash']}; border: 1px dashed {c['steel']}; color: {c['ink']}; }}
[data-testid="stFileUploaderDropzone"] * {{ color: {c['ink']}; }}
[data-testid="stFileUploaderDropzoneInstructions"] span, [data-testid="stFileUploaderDropzoneInstructions"] small {{ color: {c['muted']}; }}
[data-testid="stAlertContainer"] {{ background: {c['panel']}; color: {c['ink']}; border: 1px solid {c['rule2']}; }}
[data-testid="stAlertContainer"] * {{ color: {c['ink']}; }}
[data-testid="stCode"] pre, [data-testid="stCode"] code {{ background: {c['panel']} !important; color: {c['ink']} !important; }}
[data-testid="stCheckbox"] label span, [data-testid="stRadio"] label span {{ border-color: {c['steel']}; }}
[data-testid="stTooltipIcon"] svg {{ color: {c['muted']}; }}
[data-testid="stSpinner"] * {{ color: {c['muted']}; }}
/* the Dark mode switch */
[data-testid="stToggle"] label p, .st-key-cb_dark label p {{ font-size: 14px; color: {c['ink']}; }}
.st-key-cb_dark label > div:first-of-type {{ background: {c['rule2']} !important; }}
.st-key-cb_dark label[data-selected="true"] > div:first-of-type {{ background: {c['blue']} !important; }}
.st-key-cb_dark label > div:first-of-type > div {{ background: {c['bg']} !important; box-shadow: 0 1px 2px rgba(0,0,0,.25); }}
/* tooltips: hover on desktop, tap on phones */
.cb-tap {{ position: relative; cursor: pointer; outline: none; -webkit-tap-highlight-color: transparent; }}
.cb-tap:hover, .cb-tap:focus {{ z-index: 30; }}
.cb-tip {{ display: none; position: absolute; bottom: calc(100% + 8px); left: 50%; transform: translateX(-50%);
  width: max-content; max-width: 250px; padding: 8px 10px; background: {c['ink']}; color: {c['panel']}; font-size: 13px;
  font-weight: 400; line-height: 1.4; text-align: left; text-transform: none; letter-spacing: 0; white-space: normal;
  text-wrap: pretty; z-index: 40; pointer-events: none; box-shadow: 0 4px 14px {c['tip_shadow']}; text-shadow: none !important; }}
.cb-tip * {{ color: {c['panel']} !important; text-shadow: none !important; }}
.cb-tip b {{ display: block; font-weight: 600; }}
.cb-tip.l {{ left: 0; transform: none; }} .cb-tip.r {{ left: auto; right: 0; transform: none; }}
.cb-tip.below {{ bottom: auto; top: calc(100% + 8px); }}
.cb-tap:hover .cb-tip, .cb-tap:focus .cb-tip, .cb-tap:focus-within .cb-tip {{ display: block; }}
/* phones: a tapped cell's details show in a bar pinned to the bottom of the screen, so a scrolling grid can never clip them */
@media (max-width: 640px) {{
  .cb-tip, .cb-tip.l, .cb-tip.r, .cb-tip.below {{ position: fixed; top: auto; left: 12px; right: 12px;
    bottom: calc(12px + env(safe-area-inset-bottom, 0px)); transform: none; width: auto; max-width: none; z-index: 1000; }}
}}
.cb-tap:hover > .hl, .cb-tap:focus > .hl {{ background: {c['navon']}; }}
.cb-row:hover {{ background: {c['navon']}; }}
@media (max-width: 640px) {{
  [data-testid="stMainBlockContainer"] {{ padding-top: 60px; padding-left: 16px; padding-right: 16px; }}
  [data-testid="stHeader"]::after {{ content: "CB LEAGUE"; position: absolute; left: 60px; top: 0; height: 52px; display: flex; align-items: center;
    font-size: 11px; font-weight: 600; letter-spacing: 2.5px; color: {c['ink']}; pointer-events: none; }}
  .st-key-cb_head [data-testid="stColumn"]:last-child {{ margin-top: 14px; }}
  .cb-kpi {{ padding: 14px 0 10px !important; }}
  .cb-kpi-n {{ font-size: 36px !important; }}
  .cb-h1 {{ font-size: 40px !important; }}
  .cb-h2 {{ font-size: 26px !important; }}
  /* a section title with its control (mode buttons, a picker) beside it on a computer: on a phone the control drops
     under the title, so the title gets the same breathing room as any other title above what follows it */
  [data-testid="stHorizontalBlock"]:has(.cb-h2):has([data-testid="stButtonGroup"], [data-testid="stSelectbox"]):not(:has([data-testid="stHorizontalBlock"] .cb-h2)):not(:has(> [data-testid="stColumn"]:nth-child(3))) [data-testid="stMarkdownContainer"]:has(.cb-h2) {{
    margin-bottom: 0 !important; padding-bottom: 2px; }}
  .st-key-pv_outlook_row [data-testid="stMarkdownContainer"]:has(.cb-h2) {{ margin-bottom: 0 !important; padding-bottom: 10px !important; }}
}}
/* show-on-phone / show-on-computer helpers */
@media (min-width: 641px) {{ .cb-onph {{ display: none !important; }} }}
@media (max-width: 640px) {{ .cb-ondk {{ display: none !important; }} }}
/* phone-only Key Stats | All Stats switch over wide tables */
.cb-pc > input {{ position: absolute; opacity: 0; pointer-events: none; width: 1px; height: 1px; }}
.cb-pc .cb-pcseg, .cb-pc .cb-pc0 {{ display: none; }}
@media (max-width: 640px) {{
  .cb-pc .cb-pcseg {{ display: grid; grid-template-columns: 1fr 1fr; margin: 4px 0 4px; }}
  .cb-pc .cb-pcseg label {{ min-height: 36px; display: flex; align-items: center; justify-content: center; font-size: 13px; cursor: pointer;
    border: 1px solid {c['rule2']}; margin-right: -1px; color: {c['ink']}; }}
  .cb-pc > input:nth-of-type(1):checked ~ .cb-pc0 {{ display: block; }}
  .cb-pc > input:nth-of-type(1):checked ~ .cb-pc1 {{ display: none; }}
  .cb-pc > input:nth-of-type(1):checked ~ .cb-pcseg label:nth-child(1),
  .cb-pc > input:nth-of-type(2):checked ~ .cb-pcseg label:nth-child(2) {{ background: {c['ink']}; border-color: {c['ink']}; color: {c['bg']}; font-weight: 600; }}
  .cb-pc > input:focus-visible ~ .cb-pcseg {{ outline: 2px solid {c['blue']}; outline-offset: 2px; }}
}}
/* motion: a latest-results strip that scrolls, bars that grow in, blocks that rise in */
.cb-strip {{ display: flex; width: max-content; animation: cbStrip 70s linear infinite; }}
.cb-strip:hover {{ animation-play-state: paused; }}
@keyframes cbStrip {{ to {{ transform: translateX(-50%); }} }}
.cb-grow {{ transform-origin: left center; animation: cbGrow 1.4s cubic-bezier(.16,.8,.2,1) backwards; }}
@keyframes cbGrow {{ from {{ transform: scaleX(0); }} }}
.cb-rise {{ animation: cbRise .8s cubic-bezier(.16,.8,.2,1) backwards; }}
@keyframes cbRise {{ from {{ opacity: 0; transform: translateY(8px); }} }}
/* the rest of the figure motion from the design: bars sideways (gx, from the right with .fromr, from the middle with gxc),
   columns up (gy) and down (gyd), heat cells, dots that pop or slide, box-plot marks, the win-chance balance bar,
   and the tournament bracket stage by stage */
.cb-gx {{ transform-origin: left center; animation: cbGx 1s cubic-bezier(.16,.8,.2,1) backwards; }}
.cb-gx.fromr {{ transform-origin: right center; }}
.cb-gxc {{ transform-origin: center; animation: cbGx .9s cubic-bezier(.16,.8,.2,1) backwards; }}
@keyframes cbGx {{ from {{ transform: scaleX(0); }} }}
.cb-gy {{ transform-origin: bottom center; animation: cbGy 1.2s cubic-bezier(.16,.8,.2,1) backwards; }}
.cb-gy.fromt {{ transform-origin: top center; }}
@keyframes cbGy {{ from {{ transform: scaleY(0); }} }}
.cb-gyd {{ transform-origin: top center; animation: cbGy 1.1s cubic-bezier(.16,.8,.2,1) backwards; }}
.cb-cellin {{ animation: cbCellin .6s ease backwards; }}
@keyframes cbCellin {{ from {{ opacity: 0; transform: scale(.92); }} }}
.cb-pop {{ animation: cbPop .7s cubic-bezier(.2,1.4,.4,1) backwards; }}
@keyframes cbPop {{ from {{ transform: scale(0); opacity: 0; }} }}
.cb-dslide {{ animation: cbDslide 1s cubic-bezier(.16,.8,.2,1) backwards; }}
@keyframes cbDslide {{ from {{ left: var(--from); }} }}
.cb-pslide {{ animation: cbPslide 1.1s cubic-bezier(.16,.8,.2,1) backwards; }}
@keyframes cbPslide {{ from {{ left: -12px; }} }}
.cb-fadein {{ animation: cbFade .6s ease backwards; }}
@keyframes cbFade {{ from {{ opacity: 0; }} }}
.cb-bal {{ animation: cbBal 1.4s cubic-bezier(.16,.8,.2,1) backwards; }}
@keyframes cbBal {{ from {{ flex-basis: var(--from); }} }}
.cb-tnst .tn-card {{ animation: cbTnIn .6s ease calc(var(--st) * .9s) backwards; }}
@keyframes cbTnIn {{ from {{ opacity: 0; transform: translateY(8px); }} }}
.cb-tnst .tn-conn {{ animation: cbTnConn .5s ease calc(var(--st) * .9s - .15s) backwards; }}
@keyframes cbTnConn {{ from {{ clip-path: inset(0 100% 100% 0); }} }}
.cb-tnst .tnname {{ display: inline-block; animation: cbTnName .7s cubic-bezier(.16,.8,.2,1) calc(var(--st) * .9s + .1s) backwards; }}
.cb-tnst.tnl .tnname {{ animation-name: cbTnDrop; }}
@keyframes cbTnName {{ from {{ opacity: 0; transform: translateX(-16px); }} }}
@keyframes cbTnDrop {{ from {{ opacity: 0; transform: translateY(-14px); }} }}
.cb-tnst .cu {{ animation-delay: calc(var(--st) * .9s + .25s); animation-duration: .9s; }}
.cb-tnwin {{ position: relative; }}
.cb-tnwin::after {{ content: ""; position: absolute; inset: 0; background: {c['blue']}; opacity: .1; pointer-events: none; transform-origin: left;
  animation: cbGx .7s ease calc(var(--st, 0) * .9s + .5s) backwards; }}
.st-key-cb_motion {{ display: none !important; }}
/* figures wait until they are scrolled into view, and play again when a filter changes them (cbl/ui/motion.js adds
   cbm-js to the page, cbm-on to each figure as it comes into view, and cbm-reset for a moment to restart it) */
html.cbm-js .cb:not(.cbm-on) *, html.cbm-js .cb:not(.cbm-on) *::before, html.cbm-js .cb:not(.cbm-on) *::after {{ animation-play-state: paused !important; }}
html.cbm-js .cb.cbm-reset *, html.cbm-js .cb.cbm-reset *::before, html.cbm-js .cb.cbm-reset *::after {{ animation: none !important; }}
html.cbm-js .js-plotly-plot[data-cbm="wait"] .trace, html.cbm-js .js-plotly-plot[data-cbm="wait"] .heatmaplayer,
html.cbm-js .js-plotly-plot[data-cbm="wait"] .shapelayer {{ opacity: 0; }}
/* count-up numbers: the value is held in two whole-number variables (before and after the comma, point or colon) that
   animate up from 0 and are printed with CSS counters, so it needs no JavaScript. Screen readers get the real value. */
@counter-style cbpad2 {{ system: extends decimal; pad: 2 "0"; }}
@counter-style cbpad3 {{ system: extends decimal; pad: 3 "0"; }}
@property --cua {{ syntax: '<integer>'; initial-value: 0; inherits: false; }}
@property --cub {{ syntax: '<integer>'; initial-value: 0; inherits: false; }}
.cu {{ animation: cbCu 1.6s cubic-bezier(.16,.8,.2,1) backwards; counter-reset: cua var(--cua) cub var(--cub); font-variant-numeric: tabular-nums; }}
.cu::before {{ content: counter(cua); }}
.cu.d1::before {{ content: counter(cua) "." counter(cub); }}
.cu.d2::before {{ content: counter(cua) "." counter(cub, cbpad2); }}
.cu.th::before {{ content: counter(cua) "," counter(cub, cbpad3); }}
.cu.ms::before {{ content: counter(cua) ":" counter(cub, cbpad2); }}
@keyframes cbCu {{ from {{ --cua: 0; --cub: 0; }} }}
@media (prefers-reduced-motion: reduce) {{ .cb *, .cb *::before, .cb *::after {{ animation: none !important; }} }}
/* clips */
.cb-clip video {{ width: 100%; aspect-ratio: 16 / 9; object-fit: cover; display: block; background: #0B1428; }}
[class*="st-key-cbclip"] [data-testid="stVideo"] {{ outline: 1px solid {c['rule2']}; box-shadow: 0 1px 2px rgba(0,0,0,.15); }}
[class*="st-key-cbclip"] video {{ aspect-ratio: 16 / 9; object-fit: cover; background: #0B1428; }}
@media (max-width: 640px) {{   /* phones: clips scroll sideways in one row */
  [data-testid="stHorizontalBlock"]:has([class*="st-key-cbclip"]):not(:has([data-testid="stHorizontalBlock"] [class*="st-key-cbclip"])) {{ flex-direction: row !important; flex-wrap: nowrap !important; overflow-x: auto; gap: 12px !important; padding-bottom: 6px; }}
  [data-testid="stHorizontalBlock"]:has([class*="st-key-cbclip"]):not(:has([data-testid="stHorizontalBlock"] [class*="st-key-cbclip"])) > [data-testid="stColumn"] {{ flex: 0 0 240px !important; width: 240px !important; min-width: 0 !important; }}
}}
</style>
<div class="cb-grain" aria-hidden="true"></div>{_shimmer(f'{mode}-desk')}{_shimmer(f'{mode}-phone')}
"""


def apply() -> None:
    dark = is_dark()
    st.markdown(_css(pal(), dark), unsafe_allow_html=True)


def theme_switch() -> None:
    """The Dark mode switch at the bottom of the sidebar. The choice is kept for the whole visit, on every page."""
    def _flip():
        st.session_state["_dark"] = bool(st.session_state.get("cb_dark"))
    with st.container(key="cb_side"):
        st.toggle("Dark Mode", value=is_dark(), key="cb_dark", on_change=_flip)


def better(word: str = "blue") -> str:
    """How to read a shaded grid in this theme."""
    return "the lighter the shade, the better" if is_dark() else f"the darker the {word}, the better"


def tabs(key: str, options: list, labels: dict, default=None) -> str:
    """Underlined tab row (a segmented control styled as tabs). Returns the picked option."""
    with st.container(key=f"cbtabs_{key}"):
        v = st.segmented_control(key, options, default=default if default is not None else options[0], format_func=lambda o: labels.get(o, o),
                                 key=key, label_visibility="collapsed")
    return v or (default if default is not None else options[0])


def html(markup: str, sentence: bool = False) -> None:
    """Page HTML. Its words are set in Title Case (see title_html) unless sentence=True, for long reference text."""
    body = markup if sentence else title_html(markup)
    st.markdown(f"<div class='cb'>{stagger(countups(body))}</div>", unsafe_allow_html=True)


_TAG = re.compile(r"(<!--.*?-->|<[^>]+>)", re.S)


def title_html(markup: str) -> str:
    """Title Case for every caption, label and description in a block of page HTML. Left as written: hover boxes
    (they read as sentences), <style> blocks, and anything marked data-sc (gamertags, notes people typed, and other
    text that belongs to someone)."""
    out, skip = [], []          # skip: a stack of (tag, depth) for the region being left alone
    for part in _TAG.split(markup):
        if not part:
            continue
        if part.startswith("<"):
            m = re.match(r"<\s*(/)?\s*([a-zA-Z0-9]+)", part)
            if m:
                closing, tag = m.group(1), m.group(2).lower()
                void = part.endswith("/>") or tag in ("br", "img", "input", "hr", "col", "meta", "source", "wbr")
                if skip:
                    t0, d = skip[-1]
                    if tag == t0 and not void:
                        skip[-1] = (t0, d - 1 if closing else d + 1)
                        if skip[-1][1] == 0:
                            skip.pop()
                elif not closing and not void and (tag in ("style", "script") or "cb-tip" in part or "data-sc" in part):
                    skip.append((tag, 1))
            out.append(part)
        else:
            out.append(part if skip else title(part))
    return "".join(out)


# ---------- figure motion: one after another ---------- #
_STEP = {"cb-rise": .05, "cb-grow": .05, "cb-gx": .07, "cb-gxc": .07, "cb-gy": .04, "cb-gyd": .06, "cb-cellin": .035,
         "cb-pop": .08, "cb-pslide": .06, "cb-dslide": .07, "cb-fadein": .07}
_MOT = re.compile(r"<(div|span|td|b|section|a|li)\b([^>]*?\bclass=(['\"])([^'\"]*)\3[^>]*)>")


def stagger(markup: str, cap: int = 16) -> str:
    """Elements of a figure that move in (rows, bars, cells) go one after another: each moving element without its own
    animation-delay gets one by its place in the figure, so a list ripples in rather than landing at once."""
    count: dict[str, int] = {}

    def r(m):
        tag, attrs, q, cls = m.groups()
        kind = next((k for k in cls.split() if k in _STEP), None)
        if not kind or "animation-delay" in attrs:
            return m.group(0)
        i = count.get(kind, 0); count[kind] = i + 1
        d = f"animation-delay:{min(i, cap) * _STEP[kind]:.2f}s"
        sm = re.search(r"style=(['\"])(.*?)\1", attrs)
        if sm:
            attrs = attrs[:sm.start()] + f"style={sm.group(1)}{sm.group(2).rstrip('; ')}; {d}{sm.group(1)}" + attrs[sm.end():]
        else:
            attrs += f" style='{d}'"
        return f"<{tag}{attrs}>"
    return _MOT.sub(r, markup)


# ---------- count-up numbers ---------- #
_NUM = re.compile(r"^([+−\-]?)(\d{1,3}(?:,\d{3})+|\d+)(?:([.:])(\d+))?(%|K| hrs| maps| [A-Za-z/]{1,6})?$")
_EL = re.compile(r"<(div|span|b|td)\b([^>]*?)>([^<>]{1,24})</\1>")


def cu(text: str, delay: float = 0) -> str:
    """A number that counts up from 0 when it appears ("1,247", "+13.48", "2:08", "56%", "781K", "3.6 hrs").
    Text that isn't a plain number comes back unchanged."""
    t = str(text).strip()
    if re.fullmatch(r"\d+–\d+", t):                         # a score like 4–1 counts up on both sides
        a, b = t.split("–")
        return cu(a, delay) + "–" + cu(b, delay)
    m = _NUM.match(t)
    if not m:
        return t
    sign, whole, sep, frac, suf = m.groups()
    if sep and len(frac) > 2:
        return t
    if "," in whole:
        parts = whole.split(",")
        if len(parts) > 2:
            return t
        a, b, k = int(parts[0]), int(parts[1]), "th"
    elif sep == ".":
        a, b, k = int(whole), int(frac), ("d2" if len(frac) == 2 else "d1")
    elif sep == ":":
        a, b, k = int(whole), int(frac), "ms"
    else:
        a, b, k = int(whole), 0, ""
    d = f" animation-delay:{delay:.2f}s;" if delay else ""
    return (f"{sign}<span class='cu {k}' role='text' aria-label='{whole}{sep or ''}{frac or ''}' "
            f"style='--cua:{a}; --cub:{b};{d}'></span>{suf or ''}")


def countups(markup: str) -> str:
    """Turn the headline numbers in a block of page HTML into count-ups, the same ones the design animates:
    big light figures (24px and up), award figures (500 weight, 18px and up), and anything marked class='cbn'
    (an optional data-cud='0.15' staggers it)."""
    def r(m):
        tag, attrs, txt = m.groups()
        if "cb-tip" in attrs or "aria-hidden" in attrs or "data-nocu" in attrs:
            return m.group(0)
        st_ = re.search(r"style=(['\"])(.*?)\1", attrs)
        st_ = st_.group(2).replace(" ", "") if st_ else ""
        fs = re.search(r"font-size:(\d+)px", st_)
        fs = int(fs.group(1)) if fs else 0
        big = "font-weight:300" in st_ and fs >= 24
        award = "font-weight:500" in st_ and fs >= 18
        marked = re.search(r"class=(['\"])[^'\"]*\bcbn\b", attrs)
        if not (big or award or marked) or ("–" in txt and not marked):
            return m.group(0)
        dl = re.search(r"data-cud=['\"]([\d.]+)", attrs)
        out = cu(txt, float(dl.group(1)) if dl else 0)
        return m.group(0) if out == txt.strip() else f"<{tag}{attrs}>{out}</{tag}>"
    return _EL.sub(r, markup)


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


def _lum(h: str) -> float:
    def f(x):
        x /= 255
        return x / 12.92 if x <= .03928 else ((x + .055) / 1.055) ** 2.4
    r, g, b = (int(h[i:i + 2], 16) for i in (1, 3, 5))
    return .2126 * f(r) + .7152 * f(g) + .0722 * f(b)


def rgba(h: str, a: float) -> str:
    return f"rgba({int(h[1:3], 16)},{int(h[3:5], 16)},{int(h[5:7], 16)},{a})"


def contrast(a: str, b: str) -> float:
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + .05) / (min(la, lb) + .05)


def ramp(t: float) -> str:
    """A point on this theme's heat ramp: 0 = worst, 1 = best."""
    r = pal()["ramp"]; t = max(0.0, min(1.0, t)) * (len(r) - 1); i = min(int(t), len(r) - 2)
    return mix(r[i], r[i + 1], t - i)


def on(bg: str) -> str:
    """The text colour that reads best on a fill (this theme's ink or its on-fill colour)."""
    c = pal()
    return max((c["ink"], c["on"]), key=lambda x: contrast(bg, x))


def shade(rank_frac: float, faded: bool = False) -> tuple[str, str]:
    """Background/text for a heat cell: worst -> best along the theme's ramp. Text always reads at 4.5:1 or better."""
    c = pal()
    bg = ramp(rank_frac)
    if faded:   # too few maps to judge: the shade is washed out and the number is muted
        bg = mix(bg, c["bg"], 0.65)
        fg = c["muted"]
        for _ in range(20):            # still 4.5:1: muted, nudged toward ink only as far as it takes
            if contrast(bg, fg) >= 4.5:
                break
            fg = mix(fg, c["ink"], .15)
        return bg, fg
    return readable(bg)


def readable(bg: str) -> tuple[str, str]:
    """A fill and the text that goes on it, with the fill eased just enough that the text reads at 4.5:1."""
    fg = on(bg)
    if contrast(bg, fg) < 4.5:      # mid-ramp fills: ease the shade toward whichever end suits the text
        to = "#000000" if _lum(fg) > _lum(bg) else "#FFFFFF"
        for _ in range(30):
            bg = mix(bg, to, .04)
            if contrast(bg, fg) >= 4.5:
                break
    return bg, fg


# ---------- building blocks ---------- #
def eyebrow(text: str, color: str | None = None) -> str:
    return (f"<div class='cb-lab' style='font-size:12px; font-weight:600; letter-spacing:1.6px; text-transform:uppercase; "
            f"color:{color or pal()['muted']};'>{escape(text)}</div>")


def h1(text: str, size: int = 60) -> str:
    return (f"<h1 class='cb-h1' style='margin:10px 0 0; font-weight:300; font-size:{size}px; line-height:1; "
            f"letter-spacing:-1px; padding:0;'>{escape(text)}</h1>")


def h2(text: str, margin_top: int = 48, rule: bool = True, right: str = "") -> str:
    border = f"padding-bottom:8px; border-bottom:2px solid {pal()['ink']};" if rule else ""
    return (f"<div style='display:flex; justify-content:space-between; align-items:end; gap:12px; flex-wrap:wrap; "
            f"margin-top:{margin_top}px; {border}'><div role='heading' aria-level='2' class='cb-h2' "
            f"style='margin:0; font-weight:300; font-size:34px; letter-spacing:-0.5px; line-height:1.15;'>{escape(text)}</div>{right}</div>")


def label(text: str, margin_top: int = 0, rule: bool = False) -> str:
    c = pal()
    border = f"padding-bottom:8px; border-bottom:1px solid {c['steel']};" if rule else ""
    return (f"<div role='heading' aria-level='3' class='cb-lab' style='margin-top:{margin_top}px; font-size:12px; font-weight:600; "
            f"letter-spacing:1.6px; text-transform:uppercase; color:{c['muted']}; {border}'>{escape(text)}</div>")


_SMALL = {"a", "an", "the", "and", "but", "or", "nor", "for", "so", "yet", "as", "at", "by", "in", "of", "off", "on", "per",
          "to", "up", "via", "vs", "vs.", "v"}
_UNITS = {"hrs", "hr", "min", "mins", "sec", "secs", "pts", "med", "x", "s", "m"}   # units after a number stay lower
_WORD = re.compile(r"[A-Za-z][A-Za-z'’.]*")


def title(text: str) -> str:
    """Title Case for captions and labels: every main word capitalised; short joining words (a, the, and, of, to, vs...)
    stay lower unless they start a sentence. Words already styled (MAR, K/D, SnD, numbers) are left as written, and
    HTML tags and entities inside the text are untouched."""
    out, start, prev = [], True, ""

    def word(m):
        nonlocal start
        w = m.group(0); first = start; start = False
        if any(ch.isupper() for ch in w[1:]) or w[0].isupper() or w.lower() in ("e.g.", "i.e.", "etc."):
            return w
        if m.start() > 0 and m.string[m.start() - 1].isdigit():     # 2v2, 3rd, 10th: part of a number
            return w
        if w in _UNITS and re.search(r"\d$", m.string[:m.start()] or prev):
            return w
        hyph = m.start() > 0 and m.string[m.start() - 1] == "-" and not re.search(r"\d", m.string)
        if not first and not hyph and w.lower().rstrip(".") in _SMALL:
            return w
        return w[0].upper() + w[1:]

    # an escaped apostrophe is part of its word ("You&#x27;re" is "You're", not "You" + "Re"), so it goes back to a plain
    # apostrophe in the text between tags before the words are found (safe there: only attributes need it escaped)
    text = "".join(t if t.startswith("<") else re.sub(r"&#(?:x27|39);", "'", t) for t in re.split(r"(<[^>]*>)", str(text)))
    for part in re.split(r"(<[^>]*>|&[#\w]+;)", text):
        if not part or part.startswith("<") or (part.startswith("&") and part.endswith(";")):
            out.append(part); continue
        seg = []
        for tok in re.split(r"(\s+)", part):
            if not tok or tok.isspace():
                seg.append(tok); continue
            # each piece of a hyphenated word gets its own capital ("Fill-In"); numbers and symbols pass through
            seg.append(re.sub(r"[A-Za-z][A-Za-z'’.]*", word, tok))
            prev = tok
            if (re.search(r"[.!?:·—]$", tok) and tok.lower() not in ("e.g.", "i.e.", "vs.")) or tok in ("·", "—", "–"):
                start = True
        out.append("".join(seg))
    return "".join(out)


def note(text: str, margin_top: int = 8, size: int = 13, max_width: int = 680) -> str:
    return (f"<p style='margin:{margin_top}px 0 0; font-size:{size}px; color:{pal()['muted']}; line-height:1.5; "
            f"max-width:{max_width}px;'>{title(text)}</p>")


def tagbox(text: str, color: str | None = None, border: str | None = None) -> str:
    c = pal()
    return (f"<span style='display:inline-block; margin-left:8px; font-size:9px; font-weight:600; letter-spacing:0.6px; "
            f"color:{color or c['muted']}; border:1px solid {border or c['rule2']}; padding:1px 5px; vertical-align:middle; white-space:nowrap;'>"
            f"{escape(text.upper())}</span>")


def small_sample() -> str:
    return tagbox("Small sample")


def tip(title: str, *lines: str, align: str = "", below: bool = False) -> str:
    body = "".join(f"<span style='display:block'>{x}</span>" for x in lines if x)
    cls = " ".join(c for c in [align, "below" if below else ""] if c)
    return f"<span role='tooltip' class='cb-tip {cls}'><b>{title}</b>{body}</span>"


TAP = "class='cb-tap' tabindex='0'"


def kpis(items: list[tuple[str, str]], size: int = 44, min_w: int = 140) -> str:
    c = pal()
    cells = "".join(f"<div class='cb-kpi cb-rise' style='padding:20px 0 16px'><div class='cb-kpi-n' style='font-weight:300; font-size:{size}px; line-height:1'>{escape(str(v))}</div>"
                    f"<div style='font-size:13px; color:{c['muted']}; margin-top:8px'>{title(escape(str(l)))}</div></div>" for v, l in items)
    return (f"<div style='display:grid; grid-template-columns:repeat(auto-fit, minmax(max({min_w}px, 22%), 1fr)); "
            f"column-gap:24px; border-top:2px solid {c['ink']}; margin-top:12px'>{cells}</div>")


def table_pc(cols: list[tuple[str, str]], rows: list[list], keep: list[int], uid: str, **kw) -> str:
    """A wide table with a phone-only 'Key Stats | All Stats' switch. Key Stats keeps the columns in `keep` and fits the
    screen; All Stats is the full table, scrolling sideways. On a computer only the full table shows."""
    full = table(cols, rows, **kw)
    small_rows = [r if r == "SPACER" else [r[i] for i in keep] for r in rows]
    small = table([cols[i] for i in keep], small_rows, **{**kw, "min_width": 0})
    return (f"<div class='cb-pc'><input type='radio' name='{uid}' id='{uid}-0' checked aria-label='Key Stats'>"
            f"<input type='radio' name='{uid}' id='{uid}-1' aria-label='All Stats'>"
            f"<div class='cb-pcseg'><label for='{uid}-0'>Key Stats</label><label for='{uid}-1'>All Stats</label></div>"
            f"<div class='cb-pc0'>{small}</div><div class='cb-pc1'>{full}</div></div>")


def bar_row(name: str, value: str, frac: float, color: str | None = None, tipbox: str = "", bold: bool = False,
            name_w: int = 120, val_w: int = 64, extra: str = "") -> str:
    c = pal()
    w = max(frac * 100, 1.0)
    return (f"<div {TAP} style='display:grid; grid-template-columns:{name_w}px minmax(0,1fr) {val_w}px; align-items:center; "
            f"gap:10px; min-height:34px'><span style='font-size:14px; font-weight:{600 if bold else 400}'>{name}{extra}</span>"
            f"<div style='height:12px; background:{c['track']}'><div class='cb-gx' style='height:12px; width:{w:.1f}%; background:{color or c['steel']}'></div></div>"
            f"<span class='cbn' style='text-align:right; font-size:14px; font-weight:{600 if bold else 400}'>{value}</span>{tipbox}</div>")


def table(cols: list[tuple], rows: list[list], min_width: int = 600, cell_pad: str = "10px 8px",
          header_border: str | None = None, cls: str = "") -> str:
    """cols: [(label, align)] or [(label, align, css_class)]; rows: lists of cell dicts {v, bg, fg, w, title, cls} or plain strings."""
    c = pal()
    cols = [(x[0], x[1], x[2] if len(x) > 2 else "") for x in cols]
    th = "".join(f"<th class='{k}' style='text-align:{a}; font-weight:600; font-size:12px; color:{c['muted']}; padding:10px 8px; "
                 f"border-bottom:1px solid {header_border or c['steel']} !important; white-space:nowrap'>{escape(col)}</th>" for col, a, k in cols)
    trs = []
    for r in rows:
        if r == "SPACER":  # breathing room between two groups of rows (e.g. the two teams)
            trs.append(f"<tr><td colspan='{len(cols)}' style='height:16px; padding:0; border:0 !important; background:transparent'></td></tr>")
            continue
        tds = []
        for (col, a, k), cell in zip(cols, r):
            if not isinstance(cell, dict):
                cell = {"v": cell}
            tds.append(f"<td class='{cell.get('cls', k)}' style='text-align:{a}; padding:{cell_pad}; border-bottom:1px solid {c['rule']} !important; "
                       f"white-space:nowrap; font-weight:{cell.get('w', 400)}; background:{cell.get('bg', 'transparent')}; "
                       f"color:{cell.get('fg', c['ink'])}'" + (f" title='{escape(cell['title'])}'" if cell.get("title") else "") + f">{cell['v']}</td>")
        trs.append("<tr>" + "".join(tds) + "</tr>")
    return (f"<div class='{cls}' style='overflow-x:auto; margin-top:8px'><table style='width:100%; min-width:{min_width}px; font-size:14px'>"
            f"<thead><tr>{th}</tr></thead><tbody>{''.join(trs)}</tbody></table></div>")


def empty_box(title: str, body: str, margin_top: int = 28) -> str:
    c = pal()
    return (f"<div class='cb-fig' style='margin-top:{margin_top}px; padding:24px; border:1px dashed {c['steel']}'><div style='font-size:18px; "
            f"font-weight:500'>{escape(title)}</div><p style='margin:8px 0 0; font-size:14px; color:{c['muted']}; line-height:1.5'>{body}</p></div>")


def legend(items: list[tuple[str, str]]) -> str:
    return ("<div style='display:flex; flex-wrap:wrap; gap:6px 18px; margin-top:10px; font-size:12px; color:" + pal()["muted"] + "'>"
            + "".join(f"<span style='display:inline-flex; align-items:center; gap:6px'>{sw}{escape(t)}</span>" for sw, t in items) + "</div>")


def ramp_legend(label_text: str = "Lowest → highest", faded: str = "") -> list[tuple[str, str]]:
    """Legend items for a heat grid: the five ramp steps, then (optionally) the faded cell."""
    r = pal()["ramp"]
    sw = "<span style='display:inline-flex; gap:2px'>" + "".join(swatch(x, border=f"1px solid {pal()['rule2']}" if i == 0 else "") for i, x in enumerate(r)) + "</span>"
    out = [(sw, label_text)]
    if faded:
        out.append((swatch(mix(ramp(.5), pal()["bg"], .65)), faded))
    return out


def swatch(color: str, w: int = 12, h: int = 12, round_: bool = False, border: str = "") -> str:
    r = "border-radius:50%;" if round_ else ""
    b = f"border:{border};" if border else ""
    return f"<span style='display:inline-block; width:{w}px; height:{h}px; background:{color}; {r} {b} box-sizing:border-box'></span>"


def plotly_layout(fig, height: int = 320, legend: bool = False):
    c = pal()
    fig.update_layout(height=height, margin=dict(l=8, r=8, t=8, b=8), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Hanken Grotesk, sans-serif", color=c["ink"], size=12),
                      showlegend=legend, hoverlabel=dict(bgcolor=c["ink"], font_color=c["panel"], font_family="Hanken Grotesk", bordercolor=c["ink"]),
                      legend=dict(orientation="h", y=-0.2))
    fig.update_xaxes(gridcolor=c["track"], linecolor=c["steel"], zeroline=False, tickfont=dict(color=c["muted"]), title_font=dict(color=c["muted"]))
    fig.update_yaxes(gridcolor=c["track"], linecolor=c["steel"], zeroline=False, tickfont=dict(color=c["muted"]), title_font=dict(color=c["muted"]))
    return fig


PLOT_CONFIG = {"displayModeBar": False, "responsive": True}


def map_img(name: str, kind: str = "thumb") -> str:
    """URL of a map picture served from static/maps (blank tile if we don't have one)."""
    from cbl.config import ROOT
    f = f"{name.lower().replace(' ', '-')}-{kind}.webp"
    return f"app/static/maps/{f}" if (ROOT / "static" / "maps" / f).exists() else ""


def img_tag(name: str, kind: str = "thumb", width: str = "100%") -> str:
    c = pal()
    src = map_img(name, kind)
    if not src:
        return (f"<div style='width:{width}; aspect-ratio:16/9; background:{c['rule']}; display:flex; align-items:center; "
                f"justify-content:center; font-size:11px; font-weight:600; letter-spacing:1px; color:{c['muted']}'>{escape(name.upper())}</div>")
    return f"<img src='{src}' alt='' style='display:block; width:{width}; aspect-ratio:16/9; object-fit:cover'>"


def tint(v, arr, low: bool = False, faded: bool = False) -> tuple[str, str]:
    """Heat colors for v among arr (average rank for ties)."""
    vals = [x for x in arr if x == x]
    if len(vals) < 2 or v is None or v != v:
        return "transparent", pal()["ink"]
    lt = sum(1 for x in vals if x < v - 1e-9); eq = sum(1 for x in vals if abs(x - v) <= 1e-9)
    r = (lt + (max(eq, 1) - 1) / 2) / (len(vals) - 1)
    return shade(1 - r if low else r, faded)