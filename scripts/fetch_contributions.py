#!/usr/bin/env python3
"""
Scrape or query real daily contribution counts from GitHub and write
data/contributions.json with the raw days plus derived stats
(current streak, longest streak, best day, monthly totals).

Supports:
1. GitHub GraphQL API if GH_TOKEN or GITHUB_TOKEN environment variable is set
   (includes private contributions and exact daily counts).
2. Public HTML web scraping fallback (if no token is available).

Run daily by .github/workflows/update-profile-art.yml.
"""
import datetime
import json
import os
import re
import sys
import requests
from bs4 import BeautifulSoup

USERNAME = os.environ.get("GH_PROFILE_USER", "Kesicode")
URL = f"https://github.com/users/{USERNAME}/contributions"
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "contributions.json")


def fetch_days_graphql(username, token):
    """Fetch accurate contribution calendar via GitHub GraphQL API."""
    url = "https://api.github.com/graphql"
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                contributionCount
                date
                color
              }
            }
          }
        }
      }
    }
    """
    headers = {
        "Authorization": f"bearer {token}",
        "User-Agent": "profile-readme-bot/1.0"
    }
    try:
        resp = requests.post(url, json={"query": query, "variables": {"login": username}}, headers=headers, timeout=30)
        if resp.status_code == 200:
            res_json = resp.json()
            user_data = res_json.get("data", {}).get("user")
            if user_data:
                calendar = user_data.get("contributionsCollection", {}).get("contributionCalendar", {})
                weeks = calendar.get("weeks", [])
                days = []
                for w in weeks:
                    for d in w.get("contributionDays", []):
                        days.append({"date": d["date"], "count": d["contributionCount"]})
                if days:
                    days.sort(key=lambda x: x["date"])
                    print(f"Successfully fetched {len(days)} days via GitHub GraphQL API.")
                    return days
        else:
            print(f"GraphQL request returned HTTP {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
    except Exception as e:
        print(f"GraphQL request failed: {e}", file=sys.stderr)
    return None


def fetch_days_html():
    """Fallback: Scrape public contribution calendar HTML."""
    resp = requests.get(URL, headers={"User-Agent": "profile-readme-bot/1.0"}, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    cells = soup.select("td.ContributionCalendar-day")
    if not cells:
        print("no calendar cells found -- github markup may have changed", file=sys.stderr)
        sys.exit(1)

    days = []
    for td in cells:
        date = td.get("data-date")
        if not date:
            continue
        td_id = td.get("id")
        tooltip_el = soup.find("tool-tip", attrs={"for": td_id}) if td_id else None
        text = tooltip_el.get_text(strip=True) if tooltip_el else ""
        if re.search(r"no contributions", text, re.I):
            count = 0
        else:
            m = re.match(r"(\d+)", text)
            count = int(m.group(1)) if m else 0
        days.append({"date": date, "count": count})

    days.sort(key=lambda d: d["date"])
    print(f"Successfully scraped {len(days)} days via public HTML.")
    return days


def fetch_days():
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or os.environ.get("PROFILE_TOKEN")
    if token:
        days = fetch_days_graphql(USERNAME, token)
        if days:
            return days
    return fetch_days_html()


def compute_current_streak(days):
    if not days:
        return 0, None, None
    idx = len(days) - 1
    if idx > 0 and days[idx]["count"] == 0:
        idx -= 1  # today isn't over yet -- don't break the streak on it
    streak = 0
    end_idx = idx
    while idx >= 0 and days[idx]["count"] > 0:
        streak += 1
        idx -= 1
    start_idx = idx + 1
    if streak == 0:
        return 0, None, None
    return streak, days[start_idx]["date"], days[end_idx]["date"]


def compute_longest_streak(days):
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
                longest = run
                longest_start = days[run_start_idx]["date"]
                longest_end = days[i]["date"]
        else:
            run = 0
    return longest, longest_start, longest_end


def build_data(days):
    total = sum(d["count"] for d in days)
    active_days = sum(1 for d in days if d["count"] > 0)
    best = max(days, key=lambda d: d["count"]) if days else {"date": "", "count": 0}
    cur_len, cur_start, cur_end = compute_current_streak(days)
    long_len, long_start, long_end = compute_longest_streak(days)

    monthly = {}
    for d in days:
        key = d["date"][:7]
        monthly[key] = monthly.get(key, 0) + d["count"]
    monthly_list = [{"month": k, "total": v} for k, v in sorted(monthly.items())]

    return {
        "username": USERNAME,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "range": {"start": days[0]["date"] if days else "", "end": days[-1]["date"] if days else ""},
        "total_contributions": total,
        "active_days": active_days,
        "avg_per_active_day": round(total / active_days, 1) if active_days else 0,
        "current_streak": {"length": cur_len, "start": cur_start, "end": cur_end},
        "longest_streak": {"length": long_len, "start": long_start, "end": long_end},
        "best_day": {"date": best["date"], "count": best["count"]},
        "monthly": monthly_list,
        "days": days,
    }


if __name__ == "__main__":
    days = fetch_days()
    data = build_data(days)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"wrote {OUT_PATH}: {data['total_contributions']} contributions, "
          f"best day {data['best_day']['date']} ({data['best_day']['count']} contribs), "
          f"current streak {data['current_streak']['length']}, "
          f"longest streak {data['longest_streak']['length']}")
