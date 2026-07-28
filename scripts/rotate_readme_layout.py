"""
rotate_readme_layout.py

Dynamically updates README.md across 4 daily schedules (00:00, 06:00, 12:00, 18:00 UTC):
  1. Midnight (00:00 - 05:59 UTC): Heatmap top + Portrait & Info Card bottom.
  2. Morning  (06:00 - 11:59 UTC): Portrait & 3D Wordmark top + Heatmap bottom.
  3. Noon     (12:00 - 17:59 UTC): Info Card & 3D Wordmark top + Heatmap & Portrait bottom.
  4. Evening  (18:00 - 23:59 UTC): Portrait & Info Card top + 3D Wordmark & Heatmap bottom.

Usage:
  python scripts/rotate_readme_layout.py [--mode midnight|morning|noon|evening|auto]
"""

import sys
import datetime
import os

HERE = os.path.dirname(os.path.abspath(__file__))
README_PATH = os.path.join(HERE, "..", "README.md")

HEADER_LINKS = """<h3><code>kesi@github ~ $ ./links.sh</code></h3>

<p><b>Hardware · Software · AI Engineer</b></p>

[![Portfolio](https://img.shields.io/badge/Portfolio-kashinadh.com-0d1117?style=for-the-badge&logo=vercel&logoColor=white)](https://www.kashinadh.com)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-k--s--kashinadh-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/k-s-kashinadh)
[![Instagram](https://img.shields.io/badge/Instagram-kskashinadh__-E4405F?style=for-the-badge&logo=instagram&logoColor=white)](https://www.instagram.com/kskashinadh_)
[![Live Terminal](https://img.shields.io/badge/⚡_Live_Terminal-Kesicode.github.io-22d3ee?style=for-the-badge&logo=gnometerminal&logoColor=black)](https://Kesicode.github.io)"""

SECTION_WHOAMI_WORDMARK = """<h3><code>kesi@github ~ $ whoami</code></h3>

<!-- hero: monochrome ASCII portrait beside the 3D rocking wordmark -->
<table>
<tr>
<td valign="top"><img src="./kesi-ascii.svg" width="338" height="340" alt="KASHINADH — ASCII portrait" /></td>
<td valign="top"><img src="./wordmark.svg" width="488" height="340" alt="KESI — 3D ASCII wordmark" /></td>
</tr>
</table>"""

SECTION_WHOAMI_INFOCARD = """<h3><code>kesi@github ~ $ whoami --info</code></h3>

<!-- hero: monochrome ASCII portrait beside neofetch info card -->
<table>
<tr>
<td valign="top"><img src="./kesi-ascii.svg" width="338" height="340" alt="KASHINADH — ASCII portrait" /></td>
<td valign="top"><img src="./info-card.svg" width="367" height="340" alt="KASHINADH — Info Card" /></td>
</tr>
</table>"""

SECTION_INFOCARD_WORDMARK = """<h3><code>kesi@github ~ $ neofetch</code></h3>

<!-- hero: neofetch info card beside 3D wordmark -->
<table>
<tr>
<td valign="top"><img src="./info-card.svg" width="367" height="340" alt="KASHINADH — Info Card" /></td>
<td valign="top"><img src="./wordmark.svg" width="488" height="340" alt="KESI — 3D ASCII wordmark" /></td>
</tr>
</table>"""

SECTION_PORTRAIT_CENTERED = """<h3><code>kesi@github ~ $ ./portrait.sh</code></h3>

<img src="./kesi-ascii.svg" width="338" height="340" alt="KASHINADH — ASCII portrait" />"""

SECTION_WORDMARK_CENTERED = """<h3><code>kesi@github ~ $ ./wordmark.sh --3d</code></h3>

<img src="./wordmark.svg" width="488" height="340" alt="KESI — 3D ASCII wordmark" />"""

SECTION_CONTRIBUTIONS = """<h3><code>kesi@github ~ $ ./contributions.sh</code></h3>

<!-- animated contribution graph: real data -->
<img src="./contrib-heatmap.svg" width="860" alt="Kesicode's GitHub contribution graph" />"""


def build_readme(mode: str) -> str:
    if mode == "midnight":
        # 00:00 - 05:59 UTC: Heatmap top, Portrait + Info Card bottom
        content = f"""<div align="center">

{SECTION_CONTRIBUTIONS}

<br>

{SECTION_WHOAMI_INFOCARD}

<br>

{HEADER_LINKS}

</div>
"""
    elif mode == "morning":
        # 06:00 - 11:59 UTC: Portrait + 3D Wordmark top, Heatmap bottom
        content = f"""<div align="center">

{SECTION_WHOAMI_WORDMARK}

<br>

{SECTION_CONTRIBUTIONS}

<br>

{HEADER_LINKS}

</div>
"""
    elif mode == "noon":
        # 12:00 - 17:59 UTC: Info Card + Wordmark top, Heatmap & Portrait bottom
        content = f"""<div align="center">

{SECTION_INFOCARD_WORDMARK}

<br>

{SECTION_CONTRIBUTIONS}

<br>

{SECTION_PORTRAIT_CENTERED}

<br>

{HEADER_LINKS}

</div>
"""
    else:
        # evening (18:00 - 23:59 UTC): Portrait + Info Card top, 3D Wordmark & Heatmap bottom
        content = f"""<div align="center">

{SECTION_WHOAMI_INFOCARD}

<br>

{SECTION_WORDMARK_CENTERED}

<br>

{SECTION_CONTRIBUTIONS}

<br>

{HEADER_LINKS}

</div>
"""
    return content


def get_mode_from_args_or_time() -> str:
    mode = "auto"
    for i, arg in enumerate(sys.argv):
        if arg == "--mode" and i + 1 < len(sys.argv):
            mode = sys.argv[i + 1].lower()

    if mode in ("midnight", "morning", "noon", "evening"):
        return mode
    else:
        # auto based on current UTC hour
        hour = datetime.datetime.now(datetime.timezone.utc).hour
        if 0 <= hour < 6:
            return "midnight"
        elif 6 <= hour < 12:
            return "morning"
        elif 12 <= hour < 18:
            return "noon"
        else:
            return "evening"


def main():
    mode = get_mode_from_args_or_time()
    print(f"Generating README in '{mode}' mode...")
    readme_content = build_readme(mode)
    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(readme_content)
    print(f"Successfully updated {README_PATH}")


if __name__ == "__main__":
    main()

