#!/usr/bin/env python3
"""Generate an animated GitHub-streak SVG (squares light up one by one).
Works standalone; designed to run in a GitHub Action daily to stay live.
Usage: python generate_streak_svg.py [username] [output.svg]
"""
import sys, json, os, datetime, urllib.request

USER = sys.argv[1] if len(sys.argv) > 1 else "Kesicode"
OUT  = sys.argv[2] if len(sys.argv) > 2 else "contrib-heatmap.svg"

def get_data(user):
    here_dir = os.path.dirname(os.path.abspath(__file__))
    local_json = os.path.join(here_dir, "..", "data", "contributions.json")
    if os.path.exists(local_json):
        try:
            with open(local_json, "r", encoding="utf-8") as f:
                raw = json.load(f)
                days = raw.get("days", [])
                if days:
                    total = raw.get("total_contributions", sum(d["count"] for d in days))
                    contribs = []
                    for d in days:
                        c = d["count"]
                        lvl = 0 if c == 0 else (1 if c <= 3 else (2 if c <= 9 else (3 if c <= 19 else 4)))
                        contribs.append({"date": d["date"], "count": c, "level": lvl})
                    return {
                        "contributions": contribs,
                        "total": {"lastYear": total},
                        "start": days[0]["date"],
                        "end": days[-1]["date"]
                    }
        except Exception as e:
            print(f"Notice: local data/contributions.json read error: {e}")

    # Fallback to API
    url = f"https://github-contributions-api.jogruber.de/v4/{user}?y=last"
    try:
        with urllib.request.urlopen(url, timeout=25) as r:
            data = json.loads(r.read().decode())
            contribs = data.get("contributions", [])
            total = data.get("total", {}).get("lastYear", 0)
            return {
                "contributions": contribs,
                "total": {"lastYear": total},
                "start": contribs[0]["date"] if contribs else "",
                "end": contribs[-1]["date"] if contribs else ""
            }
    except Exception as e:
        print("API failed (%s)" % e)
        raise

data = get_data(USER)
contribs = data["contributions"]
total = data["total"]["lastYear"]

if not contribs:
    print("No contributions found.")
    sys.exit(1)

# ---- layout ----
CELL, GAP, RAD, LEFT, TOP = 13, 3, 2.5, 34, 24
COLORS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
FLASH = "#b4ffaa"
GRAY = "#7d8590"
MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

first_date = datetime.date.fromisoformat(contribs[0]["date"])
last_date = datetime.date.fromisoformat(contribs[-1]["date"])

# Sunday = 0, Mon = 1, ..., Sat = 6
lead_pad = (first_date.weekday() + 1) % 7
total_cells = lead_pad + len(contribs)
NW = (total_cells + 6) // 7

W = LEFT + NW * (CELL + GAP) + 6
H = TOP + 7 * (CELL + GAP) + 24

# timing (seconds)
REVEAL, DUR = 3.6, 0.55
maxorder = (NW - 1) + 6 * 0.55

rects, labels = [], []

# Day of week labels
for name, r in [("Mon", 1), ("Wed", 3), ("Fri", 5)]:
    labels.append(f'<text class="lbl" x="2" y="{TOP + r * (CELL + GAP) + CELL - 2}">{name}</text>')

# Month labels
last_m = None
last_lbl_col = -10
for i, c in enumerate(contribs):
    d = datetime.date.fromisoformat(c["date"])
    i_offset = i + lead_pad
    wk = i_offset // 7
    if d.month != last_m and d.day <= 7:
        if wk - last_lbl_col >= 2:
            last_m = d.month
            last_lbl_col = wk
            labels.append(f'<text class="lbl" x="{LEFT + wk * (CELL + GAP)}" y="{TOP - 8}">{MONTHS[d.month - 1]}</text>')

# Grid rects with interactive tooltips
for i, c in enumerate(contribs):
    i_offset = i + lead_pad
    wk = i_offset // 7
    row = i_offset % 7
    lvl = c["level"]
    cnt = c["count"]
    dt_str = c["date"]
    
    x = LEFT + wk * (CELL + GAP)
    y = TOP + row * (CELL + GAP)
    delay = round((wk + row * 0.55) / maxorder * REVEAL, 3)
    cls = "c g" if lvl >= 1 else "c e"
    plural = "s" if cnt != 1 else ""
    
    dt_fmt = datetime.date.fromisoformat(dt_str).strftime("%b %d, %Y")
    tooltip = f"{dt_fmt}: {cnt} contribution{plural}"
    
    rects.append(
        f'<rect class="{cls}" x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="{RAD}" '
        f'fill="{COLORS[lvl]}" style="animation-delay:{delay}s">'
        f'<title>{tooltip}</title>'
        f'</rect>'
    )

# Date range formatting
start_fmt = first_date.strftime("%b %d, %Y")
end_fmt = last_date.strftime("%b %d, %Y")
date_range_str = f"{start_fmt} &#8211; {end_fmt}"

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="-apple-system,Segoe UI,Helvetica,Arial,sans-serif">
<style>
  text.lbl {{ fill:{GRAY}; font-size:13px; font-weight:600; }}
  text.total {{ fill:#e6edf3; font-size:14px; font-weight:700; }}
  text.range {{ fill:{GRAY}; font-size:12px; font-weight:600; }}
  .c {{ transform-box:fill-box; transform-origin:center; opacity:0; animation:pop {DUR}s ease-out both; }}
  .g {{ animation:pop {DUR}s ease-out both, flash {DUR+0.15}s ease-out both; }}
  @keyframes pop {{ 0%{{opacity:0;transform:scale(.2)}} 60%{{opacity:1;transform:scale(1.1)}} 100%{{opacity:1;transform:scale(1)}} }}
  @keyframes flash {{ 0%{{filter:brightness(2.4)}} 45%{{filter:brightness(2.4)}} 100%{{filter:brightness(1)}} }}
  @media (prefers-reduced-motion: reduce) {{ .c {{ opacity:1 !important; animation:none !important; }} }}
</style>
<rect width="{W}" height="{H}" fill="none"/>
{''.join(labels)}
{''.join(rects)}
<text class="total" x="{LEFT}" y="{H-6}">{total:,} contributions in the last year</text>
<text class="range" x="{W-12}" y="{H-6}" text-anchor="end">{date_range_str}</text>
</svg>'''

with open(OUT, "w", encoding="utf-8") as f:
    f.write(svg)

print(f"Wrote {OUT}: {len(contribs)} days, {total:,} contributions ({date_range_str}), {len(svg)//1024} KB")
