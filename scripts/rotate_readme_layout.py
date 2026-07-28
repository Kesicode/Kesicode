"""
rotate_readme_layout.py

Dynamically updates README.md based on time of day or mode argument:
  - Day mode (06:00 - 17:59 UTC):
      Contribution graph on top, ASCII Portrait + Neofetch Info Card on bottom.
  - Night mode (18:00 - 05:59 UTC):
      ASCII Portrait + 3D Wordmark on top, Contribution graph on bottom.

Usage:
  python scripts/rotate_readme_layout.py [--mode day|night|auto]
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

SECTION_CONTRIBUTIONS = """<h3><code>kesi@github ~ $ ./contributions.sh</code></h3>

<!-- animated contribution graph: real data -->
<img src="./contrib-heatmap.svg" width="860" alt="Kesicode's GitHub contribution graph" />"""


def build_readme(mode: str) -> str:
    if mode == "day":
        # Day mode: Heatmap on top, Portrait + Info Card on bottom
        content = f"""<div align="center">

{SECTION_CONTRIBUTIONS}

<br>

{SECTION_WHOAMI_INFOCARD}

<br>

{HEADER_LINKS}

</div>
"""
    else:
        # Night mode: Portrait + Wordmark on top, Heatmap on bottom
        content = f"""<div align="center">

{SECTION_WHOAMI_WORDMARK}

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

    if mode in ("day", "night"):
        return mode
    else:
        # auto based on current UTC hour
        hour = datetime.datetime.now(datetime.timezone.utc).hour
        # Day hours: 06:00 to 17:59 UTC
        if 6 <= hour < 18:
            return "day"
        else:
            return "night"


def main():
    mode = get_mode_from_args_or_time()
    print(f"Generating README in '{mode}' mode...")
    readme_content = build_readme(mode)
    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(readme_content)
    print(f"Successfully updated {README_PATH}")


if __name__ == "__main__":
    main()
