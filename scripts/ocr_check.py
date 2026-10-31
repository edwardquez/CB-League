"""Read every scoreboard screenshot in a folder and print what the reader saw. Changes nothing.

    python scripts/ocr_check.py path\\to\\screenshots

For each picture: mode, map, score, game time, then one line per player. Numbers the reader wasn't sure of are
marked with * and listed underneath with the reason; those are the ones the app highlights in yellow.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cbl import ocr  # noqa: E402


def mmss(v):
    return "?" if v is None else f"{v // 60}:{v % 60:02d}"


def show(v, col):
    if v is None:
        return "?"
    return mmss(v) if col in ocr.TIMES else f"{v:.2f}" if col in ocr.RATIOS else str(v)


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python scripts/ocr_check.py <folder of screenshots>")
    if not ocr.available():
        raise SystemExit("Tesseract isn't installed (or pytesseract / opencv aren't). See the README for setup.")
    files = sorted(p for p in Path(sys.argv[1]).iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"))
    if not files:
        raise SystemExit("No .png / .jpg pictures in that folder.")
    total_flags = 0
    for f in files:
        t = time.time()
        b = ocr.read(f.read_bytes())
        print(f"\n=== {f.name}  ({time.time() - t:.1f}s)")
        if not b.get("ok"):
            print("   could not read:", b.get("error"))
            continue
        sa, sb = b["score"]
        print(f"   {b['mode']} on {b['map'] or '?'} · Alpha {sa} - {sb} Bravo · {mmss(b['game_time'])} · "
              f"{'final' if b['final'] else 'MID-GAME'}")
        cols = ["kills", "deaths"] + ocr.COLUMNS[b["mode"]][1:]
        notes = []
        for r in b["rows"]:
            cells = [show(r["stats"].get(c), c) + ("*" if c in r["flags"] else "") for c in cols]
            print(f"   {r['team'][0].upper()}{r['slot']} {(r['name'] or '?'):<18} " + " ".join(cells))
            notes += [f"{r['team'].title()} {r['slot']} {c}: {w}" for c, w in r["flags"].items()]
        notes += [f"{k}: {w}" for k, w in b["header_flags"].items()] + b["warnings"]
        total_flags += ocr.flag_count(b)
        for n in notes:
            print("   !", n)
    print(f"\n{len(files)} picture(s), {total_flags} number(s) to check.")


if __name__ == "__main__":
    main()