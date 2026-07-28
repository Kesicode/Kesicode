"""
Build a neofetch-style info card SVG (Andrew6rant style) to sit to the RIGHT of
the ASCII portrait: colored key/value rows for work experience, tech stack, and
highlights -- NOT GitHub stats (the contribution graph covers those).

Static content, hand-authored below. Lines fade/slide in on a short stagger so
it feels like the panel is printing alongside the portrait. STATIC=1 emits the
frozen state for Quick Look previews.
"""
import html
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(__file__), "..", "info-card.svg")
STATIC = bool(os.environ.get("STATIC"))

W, H = 480, 445
PAD = 20
TITLEBAR_H = 30
KEY_X = PAD
VAL_X = PAD + 92
LINE_H = 20.5

BG = "#0d1117"
BG2 = "#111722"
FRAME = "#30363d"
MUTED = "#7d8590"
INK = "#c9d1d9"
KEY = "#ffa657"      # orange keys (matches Andrew)
SECTION = "#58a6ff"  # blue section headers
GREEN = "#3fb950"
ACCENT = "#22d3ee"

# content model: tuples describing each row
# ("host",)                    -> "kesi@github" + rule
# ("kv", key, value)           -> orange key + light value
# ("sec", title)               -> blue "— title —" rule
# ("bul", text)                -> green dot + light text
# ("gap",)                     -> vertical space
ROWS = [
    ("host",),
    ("kv", "Now", "B.Tech ECE @ CE Kidangoor"),
    ("kv", "Role", "Chairperson @ IEEE IAS SBC CEK"),
    ("kv", "Also", "Embedded Systems • Full-Stack Developer"),
    ("kv", "Focus", "Hardware + AI + IoT"),
    ("kv", "Portfolio", "kashinadh.com"),
    ("gap",),
    ("sec", "Stack"),
    ("kv", "Hardware", "ESP32, STM32, Arduino, PCB Design, KiCad"),
    ("kv", "Embedded", "C/C++, FreeRTOS, PlatformIO, Sensors"),
    ("kv", "Software", "React, Next.js, TypeScript, Firebase"),
    ("kv", "Backend", "Node.js, Python, Supabase, REST APIs"),
    ("kv", "AI / ML", "OpenAI, LangChain, AI Agents"),
    ("kv", "Tools", "Git, Docker, Linux, Figma"),
    ("gap",),
    ("sec", "Highlights"),
    ("bul", "Building AI-powered IoT & Embedded Systems"),
    ("bul", "Founder of VAZA"),
    ("bul", "Hardware × Software × AI Enthusiast"),
]


def esc(s):
    return html.escape(s)


def rise(inner, i):
    """wipe-in effect from left to right, staggered by row index."""
    if STATIC:
        return f"<g>{inner}</g>"
    delay = 0.15 + i * 0.12  # slightly slower stagger for typing feel
    dur = 0.4
    clip_id = f"wipe_{i}"
    return (
        f'<clipPath id="{clip_id}">'
        f'<rect x="0" y="0" height="500" width="0">'
        f'<animate attributeName="width" from="0" to="{W}" begin="{delay:.2f}s" dur="{dur}s" fill="freeze"/>'
        f'</rect>'
        f'</clipPath>'
        f'<g clip-path="url(#{clip_id})">{inner}</g>'
    )


parts = [
    '<?xml version="1.0" encoding="utf-8"?>',
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
    f'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">',
    '<defs>'
    f'<linearGradient id="ibg" x1="0" y1="0" x2="0" y2="1">'
    f'<stop offset="0" stop-color="{BG2}"/><stop offset="1" stop-color="{BG}"/></linearGradient></defs>',
    f'<rect width="{W}" height="{H}" rx="12" fill="url(#ibg)"/>',
    f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="12" fill="none" stroke="{FRAME}"/>',
    f'<line x1="0" y1="{TITLEBAR_H}" x2="{W}" y2="{TITLEBAR_H}" stroke="{FRAME}"/>',
]
for i, dotcol in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
    parts.append(f'<circle cx="{PAD + i*16}" cy="{TITLEBAR_H/2}" r="5" fill="{dotcol}"/>')
parts.append(f'<text x="{W/2}" y="{TITLEBAR_H/2 + 4}" fill="{MUTED}" font-size="12" '
             f'text-anchor="middle">kesi@github: ~$ neofetch</text>')

y = TITLEBAR_H + 30
for i, row in enumerate(ROWS):
    kind = row[0]
    if kind == "gap":
        y += LINE_H * 0.5
        continue
    if kind == "host":
        inner = (f'<text x="{KEY_X}" y="{y:.1f}" font-size="14" font-weight="700">'
                 f'<tspan fill="{GREEN}">kesi</tspan><tspan fill="{MUTED}">@</tspan>'
                 f'<tspan fill="{ACCENT}">github</tspan></text>'
                 f'<line x1="{KEY_X+96}" y1="{y-4:.1f}" x2="{W-PAD}" y2="{y-4:.1f}" '
                 f'stroke="{FRAME}" stroke-opacity="0.8"/>')
    elif kind == "sec":
        title = esc(row[1])
        inner = (f'<text x="{KEY_X}" y="{y:.1f}" fill="{SECTION}" font-size="12.5" font-weight="700">'
                 f'&#8212; {title}</text>'
                 f'<line x1="{KEY_X + 12 + len(row[1])*8}" y1="{y-4:.1f}" x2="{W-PAD}" y2="{y-4:.1f}" '
                 f'stroke="{FRAME}" stroke-opacity="0.8"/>')
    elif kind == "kv":
        key, val = esc(row[1]), esc(row[2])
        inner = (f'<text x="{KEY_X}" y="{y:.1f}" fill="{KEY}" font-size="12.5" font-weight="700">{key}</text>'
                 f'<text x="{VAL_X}" y="{y:.1f}" fill="{INK}" font-size="12.5">{val}</text>')
    elif kind == "bul":
        txt = esc(row[1])
        inner = (f'<circle cx="{KEY_X+3}" cy="{y-4:.1f}" r="2.5" fill="{GREEN}"/>'
                 f'<text x="{KEY_X+14}" y="{y:.1f}" fill="{INK}" font-size="12.5">{txt}</text>')
    else:
        continue
    parts.append(rise(inner, i))
    y += LINE_H

parts.append("</svg>")
svg = "".join(parts)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(svg)
print("wrote", OUT, len(svg), "bytes;", W, "x", H, "content_bottom", round(y))
