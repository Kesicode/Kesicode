#!/usr/bin/env python3
"""
fetch_contributions.py
======================
Fetches 100% accurate per-day contribution counts across all years
directly from GitHub's public contribution graph HTML endpoints,
matching the exact logic used on Kesicode.github.io.

NO personal access tokens or secrets required!
Works directly with GitHub's public contribution view across years.
"""
import datetime
import json
import os
import re
import sys
import requests

USERNAME = os.environ.get("GH_PROFILE_USER", "Kesicode")
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "contributions.json")
START_YEAR = 2024
CURRENT_YEAR = datetime.datetime.now(datetime.timezone.utc).year


def fetch_days():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "text/html",
    }

    all_days = {}
    for year in range(START_YEAR, CURRENT_YEAR + 1):
        url = f"https://github.com/users/{USERNAME}/contributions?from={year}-01-01&to={year}-12-31"
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            html = resp.text

            td_pattern = re.compile(
                r'data-date="([0-9]{4}-[0-9]{2}-[0-9]{2})"[^>]+id="(contribution-day-component-[^"]+)"'
            )
            td_matches = td_pattern.findall(html)

            for date_str, comp_id in td_matches:
                tip_pattern = re.compile(
                    rf'for="{re.escape(comp_id)}"[^>]*>([^<]+)</tool-tip>'
                )
                tip_match = tip_pattern.search(html)
                count = 0
                if tip_match:
                    tip_text = tip_match.group(1).strip()
                    count_match = re.search(r'^(\d+)\s+contribution', tip_text)
                    if count_match:
                        count = int(count_match.group(1))

                all_days[date_str] = count

        except Exception as e:
            print(f"Error fetching contributions for {year}: {e}", file=sys.stderr)

    today_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    sorted_days = [
        {"date": k, "count": v}
        for k, v in sorted(all_days.items())
        if k <= today_str
    ]

    # Keep last 365 days for the profile README heatmap
    last_365 = sorted_days[-365:] if len(sorted_days) >= 365 else sorted_days
    return last_365


def compute_current_streak(days):
    if not days:
        return 0, None, None
    idx = len(days) - 1
    if idx > 0 and days[idx]["count"] == 0:
        idx -= 1  # today isn't over yet -- don't break streak
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
    print(f"wrote {OUT_PATH}: {data['total_contributions']} contributions in last 365 days, "
          f"best day {data['best_day']['date']} ({data['best_day']['count']} contribs), "
          f"current streak {data['current_streak']['length']}, "
          f"longest streak {data['longest_streak']['length']}")
