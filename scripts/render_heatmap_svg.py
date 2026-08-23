#!/usr/bin/env python3
"""
Render data/contributions.json (produced by fetch_contributions.py) as a proper
GitHub-style contribution heatmap SVG that perfectly matches the native GitHub
graph panel styling.

Run by .github/workflows/update-profile-art.yml after fetch_contributions.py.
"""
import datetime
import json
import os

HERE = os.path.dirname(__file__)
IN_PATH = os.path.join(HERE, "..", "data", "contributions.json")
OUT_PATH = os.path.join(HERE, "..", "contrib-heatmap-box.svg")

# GitHub-ish green ramp: empty -> brightest. Level 5 is a brighter neon top end.
PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"]

CELL = 11
GAP = 3
STEP = CELL + GAP
PAD = 24
LEFT_LABEL_W = 32
TOP_LABEL_H = 20
TITLEBAR_H = 0

BG = "#0d1117"
FRAME = "#30363d"
MUTED = "#7d8590"
TEXT = "#c9d1d9"

# reveal timing (one-shot)
COL_T = 0.035   # per-column delay contribution (left -> right sweep)
ROW_T = 0.080   # per-row delay contribution (top -> bottom cascade)
CELL_DUR = 0.65


def level_for(count):
    if count == 0:
        return 0
    if count <= 5:
        return 1
    if count <= 15:
        return 2
    if count <= 30:
        return 3
    if count <= 50:
        return 4
    return 5


def build_grid(days):
    first = datetime.date.fromisoformat(days[0]["date"])
    lead_pad = (first.weekday() + 1) % 7  # sunday=0
    grid = []
    col = [None] * lead_pad
    for d in days:
        date = datetime.date.fromisoformat(d["date"])
        weekday = (date.weekday() + 1) % 7
        while len(col) < weekday:
            col.append(None)
        col.append((d["date"], d["count"], level_for(d["count"])))
        if len(col) == 7:
            grid.append(col)
            col = []
    if col:
        while len(col) < 7:
            col.append(None)
        grid.append(col)
    return grid


def render(data):
    days = data["days"]
    grid = build_grid(days)
    n_cols = len(grid)
    art_w = n_cols * STEP
    art_h = 7 * STEP

    month_labels = []
    seen_months = set()
    for ci, column in enumerate(grid):
        for cell in column:
            if cell is None:
                continue
            date = datetime.date.fromisoformat(cell[0])
            key = (date.year, date.month)
            if key not in seen_months and date.day <= 7:
                seen_months.add(key)
                month_labels.append((ci, date.strftime("%b")))
            break

    canvas_w = PAD + LEFT_LABEL_W + art_w + PAD
    stats_h = 42
    canvas_h = PAD + TOP_LABEL_H + art_h + stats_h

    css = f"""
@keyframes cell {{
  0%   {{ opacity: 0; transform: translateY(-6px); }}
  100% {{ opacity: 1; transform: translateY(0); }}
}}
.c {{ opacity: 0; animation: cell {CELL_DUR:.2f}s cubic-bezier(.2,.8,.2,1) both; }}
""".strip()

    parts = [
        '<?xml version="1.0" encoding="utf-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w}" height="{canvas_h}" '
        f'viewBox="0 0 {canvas_w} {canvas_h}" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">',
        f'<style>{css}</style>',
        f'<rect width="{canvas_w}" height="{canvas_h}" rx="6" fill="transparent"/>',
    ]

    grid_top = PAD + TOP_LABEL_H
    grid_left = PAD + LEFT_LABEL_W

    for ci, label in month_labels:
        x = grid_left + ci * STEP
        parts.append(f'<text x="{x}" y="{PAD + 10}" fill="{TEXT}" font-size="12">{label}</text>')

    for wi, wname in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        y = grid_top + wi * STEP + CELL * 0.8
        parts.append(f'<text x="{PAD}" y="{y:.1f}" fill="{TEXT}" font-size="12">{wname}</text>')

    # the boxes -- each a rounded rect, diagonal slide-down reveal (once, freeze)
    for ci, column in enumerate(grid):
        gx = grid_left + ci * STEP
        for ri, cell in enumerate(column):
            if cell is None:
                continue
            date_s, count, lvl = cell
            gy = grid_top + ri * STEP
            delay = ci * COL_T + ri * ROW_T
            plural = "s" if count != 1 else ""
            parts.append(
                f'<rect class="c" x="{gx}" y="{gy}" width="{CELL}" height="{CELL}" rx="2" '
                f'fill="{PALETTE[lvl]}" style="animation-delay:{delay:.3f}s">'
                f'<title>{date_s}: {count} contribution{plural}</title></rect>'
            )

    # Total contributions footer
    leg_y = grid_top + art_h + 20
    total = data["total_contributions"]
    start_s = data.get("range", {}).get("start", "")
    end_s = data.get("range", {}).get("end", "")
    range_str = ""
    if start_s and end_s:
        s_dt = datetime.date.fromisoformat(start_s).strftime("%b %d, %Y")
        e_dt = datetime.date.fromisoformat(end_s).strftime("%b %d, %Y")
        range_str = f"{s_dt} &#8211; {e_dt}"

    parts.append(f'<text x="{PAD}" y="{leg_y + CELL*0.85:.1f}" font-size="14" fill="#ffffff" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Helvetica, Arial, sans-serif">'
                 f'<tspan font-weight="600">{total:,} contributions in the last year</tspan></text>')
    if range_str:
        parts.append(f'<text x="{canvas_w - PAD}" y="{leg_y + CELL*0.85:.1f}" font-size="12" fill="{MUTED}" text-anchor="end" font-weight="600" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Helvetica, Arial, sans-serif">{range_str}</text>')

    parts.append("</svg>")
    return "".join(parts)


if __name__ == "__main__":
    data = json.load(open(IN_PATH, encoding="utf-8"))
    svg = render(data)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"wrote {OUT_PATH} ({len(svg)} bytes)")
