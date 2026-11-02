"""Read a CDL caster scoreboard (Codcaster) screenshot with Tesseract.

    from cbl import ocr
    if ocr.available():
        board = ocr.read(image_bytes, known_maps=["Silkworm", ...])

The board is found by its two team lines (cyan under Alpha, orange under Bravo), so the screenshot can be any size
or crop as long as the whole scoreboard is in it. Every number is checked: its shape (a time has a colon, damage is
digits), Tesseract's own confidence (a second reading with different image settings when it's unsure), and the math
between columns (non-traded kills can't exceed kills; in SnD kills/round must equal kills / rounds). Anything that
fails is returned in the row's `flags`, with the reason, so the app can highlight it for a person to check.
Hardpoint and Search and Destroy are supported; Hijack waits until Codcaster shows its scoreboard.
"""
from __future__ import annotations

import difflib
import math
import os
import re
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

# board column -> app stat. "kd" becomes kills + deaths; times become seconds.
COLUMNS = {
    "HP": ["kd", "assists", "non_traded_kills", "highest_streak", "damage", "hill_time", "avg_hill_time", "objective_kills",
           "contested_hill_time", "kills_per_hill", "dmg_per_hill"],
    "SND": ["kd", "assists", "non_traded_kills", "highest_streak", "damage", "bombs_planted", "bombs_defused", "first_bloods",
            "first_deaths", "kills_per_round", "dmg_per_round"],
}
TIMES = {"hill_time", "avg_hill_time", "contested_hill_time"}
RATIOS = {"kills_per_hill", "dmg_per_hill", "kills_per_round", "dmg_per_round"}
SUPPORTED = set(COLUMNS)

# Layout, measured on a 1920x1080 frame. Positions are stored relative to the team line, so other sizes scale.
_L0, _L1 = 196, 1826                                   # left / right end of the team lines
_XC = [723, 829, 935, 1041, 1147, 1276, 1376, 1476, 1576, 1676, 1776]   # column centres
_ROW0, _PITCH, _HALF = 34, 60, 24                      # first row centre below the line, row spacing, half row height
_CONF_OK = 80                                          # Tesseract confidence at or above this needs no second reading

# Each Tesseract run is a separate program using about 35 MB. The free Streamlit server has about 1 GB, so the whole
# app runs at most this many at once, however many people upload together; extra uploads wait their turn.
_SLOTS = threading.BoundedSemaphore(4)
os.environ.setdefault("OMP_THREAD_LIMIT", "1")   # one CPU thread per run, so runs don't fight over the server's CPUs

_TESS_PLACES = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
    "/usr/bin/tesseract", "/usr/local/bin/tesseract", "/opt/homebrew/bin/tesseract",
]


@lru_cache(maxsize=1)
def tesseract_cmd() -> str | None:
    found = shutil.which("tesseract")
    if found:
        return found
    return next((p for p in _TESS_PLACES if os.path.isfile(p)), None)


@lru_cache(maxsize=1)
def available() -> bool:
    """True when Tesseract and the Python packages are installed. The app hides the feature otherwise."""
    try:
        import cv2  # noqa: F401
        import numpy  # noqa: F401
        import pytesseract
    except Exception:
        return False
    cmd = tesseract_cmd()
    if not cmd:
        return False
    pytesseract.pytesseract.tesseract_cmd = cmd
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- low-level reading
def _prep(c, scale, mode="otsu"):
    import cv2
    g = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY) if c.ndim == 3 else c
    g = cv2.resize(g, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC if scale > 1 else cv2.INTER_AREA)
    if scale > 1:
        g = cv2.GaussianBlur(g, (3, 3), 0)
    if mode == "otsu":
        _, t = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    else:
        _, t = cv2.threshold(g, 120, 255, cv2.THRESH_BINARY_INV)
    return cv2.copyMakeBorder(t, 24, 24, 24, 24, cv2.BORDER_CONSTANT, value=255)


def _text(img, cfg) -> str:
    import pytesseract
    with _SLOTS:
        return pytesseract.image_to_string(img, config=cfg).strip()


def _text_conf(img, cfg) -> tuple[str, float]:
    import pytesseract
    with _SLOTS:
        d = pytesseract.image_to_data(img, config=cfg, output_type=pytesseract.Output.DICT)
    words = [(w, float(c)) for w, c in zip(d["text"], d["conf"]) if str(w).strip()]
    if not words:
        return "", 0.0
    return "".join(w for w, _ in words), min(c for _, c in words)


_WL = {"kd": "0123456789/", "time": "0123456789:", "ratio": "0123456789.", "int": "0123456789"}
_SHAPE = {"kd": r"\d{1,3}/\d{1,3}", "time": r"\d{1,2}:[0-5]\d", "ratio": r"\d{1,4}\.\d\d", "int": r"\d{1,5}"}


def _kind(col):
    return "kd" if col == "kd" else "time" if col in TIMES else "ratio" if col in RATIOS else "int"


def _cell(c, kind, scale):
    """Read one cell. Returns (text, problem or None)."""
    cfg = f"--psm 7 -c tessedit_char_whitelist={_WL[kind]}"
    t1, conf = _text_conf(_prep(c, scale), cfg)
    ok1 = re.fullmatch(_SHAPE[kind], t1) is not None
    if ok1 and conf >= _CONF_OK:
        return t1, None
    t2 = _text(_prep(c, scale * 1.5, "fixed"), cfg)
    ok2 = re.fullmatch(_SHAPE[kind], t2) is not None
    if ok1 and t1 == t2:
        return t1, None
    if ok1 and ok2:
        return t1, f"two readings disagree ({t1} or {t2})"
    if ok1:
        return t1, "faint, worth a look"
    if ok2:
        return t2, "faint, worth a look"
    return None, "couldn't read it"


# ---------------------------------------------------------------- the board
def _find_line(img, colour):
    import cv2
    import numpy as np
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, sat, val = (hsv[:, :, i].astype(int) for i in range(3))
    hue = (h >= 80) & (h <= 112) if colour == "cyan" else (h <= 15) | (h >= 172)    # cyan or blue (BO7) / orange or red (BO7)
    mask = hue & (sat > 110) & (val > 110)
    per_row = mask.sum(axis=1)
    y = int(np.argmax(per_row))
    if per_row[y] < img.shape[1] * 0.3:
        return None
    xs = np.where(mask[y])[0]
    return y, int(xs.min()), int(xs.max())


def _secs(t):
    m = re.fullmatch(r"(\d+):(\d\d)", t or "")
    return int(m[1]) * 60 + int(m[2]) if m else None


def _match_map(raw: str, known: list[str]) -> str:
    if not raw:
        return ""
    by = {k.lower(): k for k in known}
    if raw.lower() in by:
        return by[raw.lower()]
    close = difflib.get_close_matches(raw.lower(), list(by), n=1, cutoff=0.6)
    return by[close[0]] if close else raw.title()


def read(image: bytes, known_maps: list[str] | tuple = ()) -> dict:
    """Read a scoreboard. Returns a dict (all plain types, safe for session state):

    ok, error, mode (HP/SND/HJ/?), map, score [a, b] (Alpha, Bravo; None if unreadable), game_time (sec),
    final (False on a mid-game board), warnings [str], header_flags {field: reason},
    rows [{team: alpha|bravo, slot, name, stats {app stat: value}, flags {app stat: reason}, crop (png bytes)}]
    """
    import cv2
    import numpy as np
    if not available():
        return {"ok": False, "error": "Tesseract isn't installed on this computer."}
    img = cv2.imdecode(np.frombuffer(image, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return {"ok": False, "error": "That file isn't an image the reader can open. Use a PNG or JPG."}
    a, b = _find_line(img, "cyan"), _find_line(img, "orange")
    if not a or not b or b[0] <= a[0]:
        return {"ok": False, "error": "Couldn't find the scoreboard in this picture. Use a screenshot of the full Codcaster "
                                      "scoreboard (the Alpha and Bravo tables, with the map name above them)."}
    ya, yb = a[0], b[0]
    x0, x1 = min(a[1], b[1]), max(a[2], b[2])          # the line ends; take the wider of the two (a skull icon can clip one)
    s = (x1 - x0) / (_L1 - _L0)                      # size compared with a 1920x1080 frame
    cs = 2 / s                                       # upscale so small text is read at the same size

    def X(x):
        return int(x0 + (x - _L0) / (_L1 - _L0) * (x1 - x0))

    def crop(y0, y1, xl, xr):
        return img[max(int(y0), 0):max(int(y1), 1), max(X(xl), 0):max(X(xr), 1)]

    # header: mode / map / total game time, the two big scores, and the streak label (Highest = final, Current = mid-game)
    hdr = _text(_prep(crop(ya - 260 * s, ya - 130 * s, 222, 700), cs), "--psm 6")
    up = hdr.upper()
    mode = "SND" if "SEARCH" in up else "HP" if "HARD" in up else "HJ" if "HIJACK" in up else "?"
    lines = [ln.strip() for ln in hdr.splitlines() if ln.strip()]
    raw_map = re.sub(r"[^A-Za-z0-9 ]", "", lines[1]).strip() if len(lines) > 1 else ""
    gt = re.search(r"(\d{1,2}:\d\d)\s*$", lines[2] if len(lines) > 2 else hdr)
    out = {"ok": True, "error": None, "mode": mode, "map": _match_map(raw_map, list(known_maps)),
           "game_time": _secs(gt.group(1)) if gt else None, "warnings": [], "header_flags": {}, "rows": []}
    big_cfg = "--psm 7 -c tessedit_char_whitelist=0123456789"
    score, score_note = [], None
    for xc in (852, 1067):   # big thin digits: read twice with different settings; a disagreement gets flagged
        c = crop(ya - 270 * s, ya - 202 * s, xc - 60, xc + 60)
        t1, t2 = _text(_prep(c, 0.5 / s, "fixed"), big_cfg), _text(_prep(c, 0.75 / s), big_cfg)
        score.append(int(t1) if t1.isdigit() else int(t2) if t2.isdigit() else None)
        if t1.isdigit() and t2.isdigit() and t1 != t2:
            score_note = f"two readings disagree ({t1} or {t2})"
    out["score"] = score
    lbl = _text(_prep(crop(ya - 45 * s, ya - 5 * s, 990, 1095), cs), "--psm 6").upper()
    out["final"] = "CURRENT" not in lbl
    if mode == "?":   # header unreadable: the column headings still tell Hardpoint (Hill Time) from SnD (Bombs Planted)
        col6 = _text(_prep(crop(ya - 45 * s, ya - 5 * s, 1215, 1340), cs), "--psm 6").upper()
        mode = out["mode"] = "HP" if "HILL" in col6 else "SND" if "BOMB" in col6 or "PLANT" in col6 else "?"
    if s < 0.6:
        out["warnings"].append("This picture is small or low quality, so misreads are more likely. Check every number, "
                               "or use a full-size screenshot (VLC's Take Snapshot).")
    if mode not in SUPPORTED:
        out["ok"] = False
        out["error"] = ("Hijack scoreboards aren't supported yet." if mode == "HJ"
                        else "Couldn't tell which mode this is. The reader knows Hardpoint and Search and Destroy.")
        return out
    if None in score:
        out["header_flags"]["score"] = "couldn't read the score"
    elif score_note:
        out["header_flags"]["score"] = score_note
    if out["game_time"] is None:
        out["header_flags"]["game_time"] = "couldn't read the total game time"
    if not out["final"]:
        out["warnings"].append("This looks like a mid-game scoreboard (the streak column says Current Streak). "
                               "Use the one from the end of the map.")
    cols = COLUMNS[mode]

    def team_rows(yline, team):
        found = []
        for k in range(4):
            yc = yline + (_ROW0 + k * _PITCH) * s
            strip = crop(yc - _HALF * s, yc + _HALF * s, 700, 1820)
            if strip.size == 0 or (cv2.cvtColor(strip, cv2.COLOR_BGR2GRAY) > 170).sum() < 40 * s:
                break
            found.append((k, yc))

        def one(arg):
            k, yc = arg
            y0, y1 = yc - _HALF * s, yc + _HALF * s
            name = re.sub(r"\s+", " ", _text(_prep(crop(y0, y1, 318, 668), cs), "--psm 7")).strip()   # BO7 names can have spaces
            stats, flags, raw = {}, {}, {}
            for col, xc in zip(cols, _XC):
                t, prob = _cell(crop(y0, y1, xc - 52, xc + 52), _kind(col), cs)
                raw[col] = t
                if col == "kd":
                    kd = re.fullmatch(r"(\d+)/(\d+)", t or "")
                    stats["kills"], stats["deaths"] = (int(kd[1]), int(kd[2])) if kd else (None, None)
                    if prob:
                        flags["kills"] = flags["deaths"] = prob
                    continue
                if t is None:
                    stats[col] = None
                elif col in TIMES:
                    stats[col] = _secs(t)
                elif col in RATIOS:
                    stats[col] = float(t)
                else:
                    stats[col] = int(t)
                if prob:
                    flags[col] = prob
            # the row as two stacked halves (name to damage, then the mode stats), so it stays readable on a phone
            ys0, ys1 = max(int(yc - 28 * s), 0), int(yc + 28 * s)
            left, right = img[ys0:ys1, max(X(312), 0):X(1205)], img[ys0:ys1, X(1205):x1]
            pad = np.zeros((right.shape[0], max(left.shape[1] - right.shape[1], 0), 3), np.uint8)
            right = np.hstack([right, pad])[:, :left.shape[1]]
            ok, png = cv2.imencode(".png", np.vstack([left, right]))
            return {"team": team, "slot": k + 1, "name": name, "stats": stats, "flags": flags, "raw": raw,
                    "crop": png.tobytes() if ok else None}

        with ThreadPoolExecutor(6) as ex:
            return list(ex.map(one, found))

    out["rows"] = team_rows(ya, "alpha") + team_rows(yb, "bravo")
    _check(out)
    return out


def _trunc_ok(value, num, den):
    """The game shows ratios cut to 2 decimals (6/7 shows 0.85, and 737/10 can show 73.69); accept cut or rounded."""
    if value is None or num is None or not den:
        return True
    x = num / den
    return x - 0.0101 <= value <= x + 0.0051


def _check(b: dict) -> None:
    """Math checks between columns. Adds flags to the cells that don't add up."""
    def flag(r, col, why):
        r["flags"].setdefault(col, why)

    sa, sb = b["score"]
    rounds = sa + sb if b["mode"] == "SND" and None not in (sa, sb) else None
    for r in b["rows"]:
        st = r["stats"]; k = st.get("kills")
        if k is not None:
            if st.get("non_traded_kills") is not None and st["non_traded_kills"] > k:
                flag(r, "non_traded_kills", "more than their kills"); flag(r, "kills", "fewer than their non-traded kills")
            if b["final"] and st.get("highest_streak") is not None and st["highest_streak"] > k:
                flag(r, "highest_streak", "longer than their kills")
        if b["mode"] == "HP":
            if None not in (st.get("avg_hill_time"), st.get("hill_time")) and st["avg_hill_time"] > st["hill_time"]:
                flag(r, "avg_hill_time", "more than their total hill time")
        if rounds:
            if not _trunc_ok(st.get("kills_per_round"), k, rounds):
                flag(r, "kills_per_round", f"doesn't match kills / {rounds} rounds"); flag(r, "kills", f"doesn't match kills/round x {rounds}")
            if not _trunc_ok(st.get("dmg_per_round"), st.get("damage"), rounds):
                flag(r, "dmg_per_round", f"doesn't match damage / {rounds} rounds"); flag(r, "damage", f"doesn't match damage/round x {rounds}")
            if st.get("bombs_planted") is not None and st["bombs_planted"] > rounds:
                flag(r, "bombs_planted", "more plants than rounds")
    if rounds:
        for col, label in (("first_bloods", "first bloods"), ("first_deaths", "first deaths")):
            vals = [r["stats"].get(col) for r in b["rows"]]
            if None not in vals and sum(vals) != rounds:
                b["warnings"].append(f"The {label} add up to {sum(vals)}, but {rounds} rounds were played. One of them is probably misread.")
                for r in b["rows"]:
                    flag(r, col, f"{label} don't add up to the {rounds} rounds")
    if b["final"] and None not in (sa, sb):
        win = {"HP": 250, "SND": 6}[b["mode"]]
        if max(sa, sb) != win:
            b["warnings"].append(f"Neither team is on {win}. Fine if the map was ended early{' or on time' if win == 250 else ''}; "
                                 "otherwise check the score.")
            b["header_flags"].setdefault("score", f"no team on {win}")
        if sa == sb:
            b["header_flags"]["score"] = "the score is tied"
    na, nb = (sum(1 for r in b["rows"] if r["team"] == t) for t in ("alpha", "bravo"))
    if na != nb:
        b["warnings"].append(f"Found {na} Alpha players and {nb} Bravo players. Check that the whole scoreboard is in the picture.")


def flag_count(b: dict) -> int:
    return len(b.get("header_flags", {})) + sum(len(r["flags"]) for r in b.get("rows", []))


# ---------------------------------------------------------------- matching gamertags to players
def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def match_players(names: list[str], tags: dict[str, list[str]], remembered: dict[str, str] | None = None,
                  cutoff: float = 0.8) -> list[str | None]:
    """Guess which player each board row is. tags: player -> gamertags (newest last). remembered: board name -> player
    from earlier maps this session (bot names that stay the same between maps). Underscores and case are ignored,
    because the reader drops long runs of underscores. Each player is used at most once."""
    remembered = remembered or {}
    flat = [(_norm(t), p) for p, ts in tags.items() for t in ts + [p] if _norm(t)]
    out: list[str | None] = [None] * len(names)
    used: set[str] = set()
    scored = []
    for i, n in enumerate(names):
        if n in remembered and remembered[n] in tags:
            scored.append((2.0, i, remembered[n]))
        nn = _norm(n)
        for t, p in flat:
            if nn and t:
                scored.append((1.0 if nn == t else difflib.SequenceMatcher(None, nn, t).ratio(), i, p))
    for sc, i, p in sorted(scored, reverse=True):
        if sc < cutoff:
            break
        if out[i] is None and p not in used:
            out[i] = p; used.add(p)
    return out