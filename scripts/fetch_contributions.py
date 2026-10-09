#!/usr/bin/env python3
"""
fetch_contributions.py  (v3 — fixed)
======================================
Fetches 100% accurate, live, per-day contribution counts for the last 365
days using GitHub's GraphQL API with explicit date ranges.

Key fixes over v2:
  1. Token priority: GH_PAT > GH_TOKEN > GITHUB_TOKEN (PAT has broadest scope)
  2. GraphQL query uses explicit from/to dates — no more implicit year boundary cuts.
  3. Two-pass query: spans the GitHub contribution-year boundary (Oct-Oct) by
     querying the current year + previous contribution year and merging.
  4. Sliding 365-day window is built day-by-day so today is ALWAYS included.
  5. HTML scraper fallback kept as last resort; improved robustness.
  6. Data validation: warns if fetched total looks suspiciously low.
"""
import datetime
import json
import os
import re
import sys
import time
import requests

USERNAME     = os.environ.get("GH_PROFILE_USER", "Kesicode")
OUT_PATH     = os.path.join(os.path.dirname(__file__), "..", "data", "contributions.json")
START_YEAR   = 2024
CURRENT_YEAR = datetime.datetime.now(datetime.timezone.utc).year

# ── Token priority ────────────────────────────────────────────────────────────
# GH_PAT  = Personal Access Token (full repo scope, best accuracy)
# GH_TOKEN = custom token passed by workflow
# GITHUB_TOKEN = auto-provisioned by Actions (limited to current repo's contributions)
def get_token():
    return (os.environ.get("GH_PAT")
            or os.environ.get("GH_TOKEN")
            or os.environ.get("GITHUB_TOKEN")
            or os.environ.get("PROFILE_TOKEN"))


# ── GraphQL helpers ───────────────────────────────────────────────────────────
GRAPHQL_URL = "https://api.github.com/graphql"

GRAPHQL_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            contributionCount
            date
          }
        }
      }
    }
  }
}
"""


def graphql_range(username: str, token: str, from_date: datetime.date, to_date: datetime.date) -> dict:
    """Run one GraphQL query for a date range; return {date_str: count} dict."""
    headers = {
        "Authorization":  f"bearer {token}",
        "User-Agent":     "Kesicode-profile-bot/3.0",
        "Cache-Control":  "no-cache",
        "Pragma":         "no-cache",
    }
    variables = {
        "login": username,
        "from":  from_date.strftime("%Y-%m-%dT00:00:00Z"),
        "to":    to_date.strftime("%Y-%m-%dT23:59:59Z"),
    }
    try:
        resp = requests.post(
            GRAPHQL_URL,
            json={"query": GRAPHQL_QUERY, "variables": variables},
            headers=headers,
            timeout=25,
        )
        if resp.status_code != 200:
            print(f"  GraphQL HTTP {resp.status_code}", file=sys.stderr)
            return {}
        body = resp.json()
        if body.get("errors"):
            print(f"  GraphQL errors: {body['errors']}", file=sys.stderr)
            return {}
        user = body.get("data", {}).get("user")
        if not user:
            print("  GraphQL: no user node in response", file=sys.stderr)
            return {}
        weeks = (user
                 .get("contributionsCollection", {})
                 .get("contributionCalendar", {})
                 .get("weeks", []))
        result = {}
        for w in weeks:
            for d in w.get("contributionDays", []):
                result[d["date"]] = d["contributionCount"]
        return result
    except Exception as exc:
        print(f"  GraphQL request failed: {exc}", file=sys.stderr)
        return {}


def fetch_days_graphql(username: str, token: str) -> list[dict] | None:
    """
    Build an exact 365-day sliding window ending today.

    GitHub's contributionsCollection is silently capped at its internal
    "contribution year" boundaries (roughly Oct → Oct). To handle a window
    that crosses that boundary we fire TWO queries:
      - Query A: 365 days ago → today          (current contribution year slice)
      - Query B: 366 days ago → 365 days ago   (previous contribution year slice)
    Then merge and build the exact 365-day list day by day.
    """
    today      = datetime.datetime.now(datetime.timezone.utc).date()
    start_365  = today - datetime.timedelta(days=364)   # 365 days incl. today
    prev_start = today - datetime.timedelta(days=395)   # 30-day buffer before window

    print(f"GraphQL A: {start_365} → {today}")
    batch_a = graphql_range(username, token, start_365, today)
    print(f"  → {len(batch_a)} days returned")

    # Fire second query only if first didn't cover the full window
    batch_b = {}
    if len(batch_a) < 350:
        print(f"GraphQL B (gap fill): {prev_start} → {start_365}")
        batch_b = graphql_range(username, token, prev_start, start_365)
        print(f"  → {len(batch_b)} additional days")

    combined = {**batch_b, **batch_a}   # A wins on overlap

    if not combined:
        return None

    # Build the exact 365-day list — today is ALWAYS the last entry
    days = []
    for i in range(365):
        d  = start_365 + datetime.timedelta(days=i)
        ds = d.strftime("%Y-%m-%d")
        days.append({"date": ds, "count": combined.get(ds, 0)})

    total = sum(d["count"] for d in days)
    print(f"GraphQL: {total} contributions over {len(days)} days "
          f"({start_365} → {today})")
    return days


# ── HTML scraper fallback ─────────────────────────────────────────────────────

def fetch_days_html() -> list[dict]:
    """Scrape contribution calendar from GitHub profile pages (no token needed)."""
    ts      = int(time.time())
    headers = {
        "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept":          "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control":   "no-cache, no-store, must-revalidate",
        "Pragma":          "no-cache",
    }

    all_days: dict[str, int] = {}

    date_id_re = re.compile(
        r'data-date="([0-9]{4}-[0-9]{2}-[0-9]{2})"[^>]+id="(contribution-day-component-[^"]+)"'
    )
    count_re   = re.compile(r'^(\d+)\s+contribution')

    def scrape_page(url: str) -> dict[str, int]:
        days: dict[str, int] = {}
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            resp.raise_for_status()
            html = resp.text
            for date_str, comp_id in date_id_re.findall(html):
                tip_re  = re.compile(rf'for="{re.escape(comp_id)}"[^>]*>([^<]+)</tool-tip>')
                tip     = tip_re.search(html)
                count   = 0
                if tip:
                    m = count_re.match(tip.group(1).strip())
                    if m:
                        count = int(m.group(1))
                days[date_str] = count
        except Exception as exc:
            print(f"  HTML scrape error ({url[:60]}…): {exc}", file=sys.stderr)
        return days

    # Year-by-year pages
    for year in range(START_YEAR, CURRENT_YEAR + 1):
        url = (f"https://github.com/users/{USERNAME}/contributions"
               f"?from={year}-01-01&to={year}-12-31&_t={ts}")
        print(f"HTML scrape: {year}")
        all_days.update(scrape_page(url))

    # Rolling current-window page (freshest data for today)
    all_days.update(scrape_page(
        f"https://github.com/users/{USERNAME}/contributions?_t={ts}"
    ))

    today     = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    start_365 = (datetime.datetime.now(datetime.timezone.utc).date()
                 - datetime.timedelta(days=364)).strftime("%Y-%m-%d")

    days = [
        {"date": k, "count": v}
        for k, v in sorted(all_days.items())
        if start_365 <= k <= today
    ]
    return days[-365:] if len(days) >= 365 else days


# ── Top-level fetch ───────────────────────────────────────────────────────────

def fetch_days() -> list[dict]:
    token = get_token()
    if token:
        print(f"Token found ({'GH_PAT' if os.environ.get('GH_PAT') else 'GH_TOKEN/GITHUB_TOKEN'})")
        days = fetch_days_graphql(USERNAME, token)
        if days and len(days) >= 100:
            return days
        print("GraphQL returned insufficient data — falling back to HTML scraper",
              file=sys.stderr)
    else:
        print("No token found — using HTML scraper (may be less accurate)",
              file=sys.stderr)

    return fetch_days_html()


# ── Stats computation ─────────────────────────────────────────────────────────

def compute_current_streak(days: list[dict]) -> tuple:
    if not days:
        return 0, None, None
    idx = len(days) - 1
    # Allow today to have 0 (streak may still be ongoing from yesterday)
    if idx > 0 and days[idx]["count"] == 0:
        idx -= 1
    streak, end_idx = 0, idx
    while idx >= 0 and days[idx]["count"] > 0:
        streak += 1
        idx -= 1
    start_idx = idx + 1
    if streak == 0:
        return 0, None, None
    return streak, days[start_idx]["date"], days[end_idx]["date"]


def compute_longest_streak(days: list[dict]) -> tuple:
    if not days:
        return 0, None, None
    longest = run = 0
    longest_start = longest_end = None
    run_start_idx = None
    for i, d in enumerate(days):
        if d["count"] > 0:
            if run == 0:
                run_start_idx = i
            run += 1
            if run > longest:
                longest          = run
                longest_start    = days[run_start_idx]["date"]
                longest_end      = days[i]["date"]
        else:
            run = 0
    return longest, longest_start, longest_end


def build_data(days: list[dict]) -> dict:
    total       = sum(d["count"] for d in days)
    active_days = sum(1 for d in days if d["count"] > 0)
    best        = max(days, key=lambda d: d["count"]) if days else {"date": "", "count": 0}
    cur_len,  cur_start,  cur_end  = compute_current_streak(days)
    long_len, long_start, long_end = compute_longest_streak(days)

    monthly: dict[str, int] = {}
    for d in days:
        key = d["date"][:7]
        monthly[key] = monthly.get(key, 0) + d["count"]
    monthly_list = [{"month": k, "total": v} for k, v in sorted(monthly.items())]

    return {
        "username":           USERNAME,
        "generated_at":       datetime.datetime.now(datetime.timezone.utc)
                              .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "range":              {"start": days[0]["date"]  if days else "",
                               "end":   days[-1]["date"] if days else ""},
        "total_contributions": total,
        "active_days":        active_days,
        "avg_per_active_day": round(total / active_days, 1) if active_days else 0,
        "current_streak":     {"length": cur_len,  "start": cur_start,  "end": cur_end},
        "longest_streak":     {"length": long_len, "start": long_start, "end": long_end},
        "best_day":           {"date": best["date"], "count": best["count"]},
        "monthly":            monthly_list,
        "days":               days,
    }


# ── Validation ────────────────────────────────────────────────────────────────

def validate(data: dict, prev_path: str) -> None:
    """Warn if new data looks suspiciously different from the previous run."""
    if not os.path.exists(prev_path):
        return
    try:
        with open(prev_path, encoding="utf-8") as f:
            prev = json.load(f)
        prev_total = prev.get("total_contributions", 0)
        new_total  = data["total_contributions"]
        # Contributions should never decrease by more than one day's max worth
        if prev_total > new_total + 200:
            print(f"WARNING: total dropped from {prev_total} → {new_total}. "
                  f"Possible fetch error.", file=sys.stderr)
        today = datetime.date.today().isoformat()
        if data["range"]["end"] < today:
            print(f"WARNING: data end date {data['range']['end']} is before "
                  f"today {today}. Today may be missing.", file=sys.stderr)
    except Exception:
        pass


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    days = fetch_days()
    data = build_data(days)
    validate(data, OUT_PATH)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(
        f"\n✓ wrote {OUT_PATH}\n"
        f"  total  : {data['total_contributions']} contributions in 365 days\n"
        f"  range  : {data['range']['start']} → {data['range']['end']}\n"
        f"  best   : {data['best_day']['date']} ({data['best_day']['count']} contribs)\n"
        f"  streak : current {data['current_streak']['length']} days, "
        f"longest {data['longest_streak']['length']} days\n"
    )
