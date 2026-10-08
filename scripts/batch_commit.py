#!/usr/bin/env python3
"""
batch_commit.py
===============
Rotates through ALL Kesicode repositories in batches of 5, committing a
small heartbeat file (LAST_ACTIVE.md) to each one via the GitHub Contents
API — no git clone needed. This keeps contribution activity distributed
across all projects on the heatmap.

Rotation state (current batch index) is saved to data/batch_state.json
which also creates a commit in the profile repo itself on every run.

Triggered by: .github/workflows/batch-touch.yml (4× daily)
Requires:     GH_PAT secret with repo scope stored in GitHub Secrets.
              ⚠ GITHUB_TOKEN alone will NOT work for other repos.
"""
import base64
import datetime
import json
import os
import sys
import time
import requests

# ── Config ────────────────────────────────────────────────────────────────────
USERNAME     = "Kesicode"
PROFILE_REPO = "Kesicode"          # profile repo — handled via state file commit
BATCH_SIZE   = 5                   # repos touched per run
HERE         = os.path.dirname(os.path.abspath(__file__))
STATE_FILE   = os.path.join(HERE, "..", "data", "batch_state.json")

# Try GH_PAT first, then GH_TOKEN — GITHUB_TOKEN cannot write to other repos
TOKEN = os.environ.get("GH_PAT") or os.environ.get("GH_TOKEN")
if not TOKEN:
    print("ERROR: GH_PAT secret is required (repo scope). GITHUB_TOKEN cannot "
          "write to other repositories.", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    "Authorization":        f"Bearer {TOKEN}",
    "Accept":               "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent":           "Kesicode-batch-touch/1.0",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def api_get(path: str) -> dict | list:
    resp = requests.get(f"https://api.github.com{path}", headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.json()


def get_all_owned_repos() -> list[dict]:
    """All repos owned by USERNAME (including forks, excluding archived & empty)."""
    repos, page = [], 1
    while True:
        data = api_get(
            f"/users/{USERNAME}/repos?type=owner&per_page=100&page={page}&sort=full_name"
        )
        if not data:
            break
        for r in data:
            if not r.get("archived") and r.get("size", 0) > 0:
                repos.append({
                    "name":   r["name"],
                    "branch": r.get("default_branch", "main"),
                    "fork":   r.get("fork", False),
                })
        page += 1
        if len(data) < 100:
            break
    return repos


def get_file_sha(repo: str, branch: str, path: str) -> str | None:
    """Return the SHA of an existing file, or None if it doesn't exist."""
    try:
        data = api_get(f"/repos/{USERNAME}/{repo}/contents/{path}?ref={branch}")
        return data.get("sha") if isinstance(data, dict) else None
    except Exception:
        return None


def put_file(repo: str, branch: str, path: str, content: str, message: str) -> bool:
    """Create or update a file via GitHub Contents API."""
    sha = get_file_sha(repo, branch, path)
    payload: dict = {
        "message": message,
        "content": base64.b64encode(content.encode()).decode(),
        "branch":  branch,
    }
    if sha:
        payload["sha"] = sha

    try:
        resp = requests.put(
            f"https://api.github.com/repos/{USERNAME}/{repo}/contents/{path}",
            headers=HEADERS,
            json=payload,
            timeout=25,
        )
        return resp.status_code in (200, 201)
    except Exception as exc:
        print(f"    request error: {exc}")
        return False


def load_state() -> dict:
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"batch_index": 0, "run_count": 0}


def save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


# ── Main ──────────────────────────────────────────────────────────────────────

now     = datetime.datetime.now(datetime.timezone.utc)
now_str = now.strftime("%Y-%m-%d %H:%M UTC")
msg     = f"chore: heartbeat {now.strftime('%Y-%m-%d %H:%M')} UTC [skip ci]"

print(f"\n{'='*60}")
print(f"  Kesicode batch-touch  |  {now_str}")
print(f"{'='*60}")

state     = load_state()
all_repos = get_all_owned_repos()

# Exclude the profile repo from the rotation — its commit comes from the
# batch_state.json state file that git-auto-commit-action handles.
rotation = [r for r in all_repos if r["name"] != PROFILE_REPO]

total = len(rotation)
idx   = state.get("batch_index", 0) % max(total, 1)

# Slice with wrap-around so last batch still gets BATCH_SIZE repos
doubled = rotation + rotation
batch   = doubled[idx : idx + BATCH_SIZE]

print(f"\nRotation: repos {idx+1}–{idx+len(batch)} of {total}")
print(f"This run: {[r['name'] for r in batch]}\n")

touched = skipped = errors = 0
for repo in batch:
    name   = repo["name"]
    branch = repo["branch"]
    tag    = "fork" if repo["fork"] else "own"

    content = (
        f"# Last Active\n\n"
        f"| Field | Value |\n"
        f"|-------|-------|\n"
        f"| Updated | `{now_str}` |\n"
        f"| Repo | [{name}](https://github.com/{USERNAME}/{name}) |\n\n"
        f"_Auto-synced by [Kesicode](https://github.com/{USERNAME}) profile bot._\n\n"
        f"<!-- auto-generated — do not edit manually -->\n"
    )

    ok = put_file(name, branch, "LAST_ACTIVE.md", content, msg)
    status = "✓" if ok else "✗"
    print(f"  {status}  {name} [{tag}] ({branch})")

    if ok:
        touched += 1
    else:
        errors += 1

    time.sleep(0.4)   # stay well under GitHub's 5 000 req/hr rate limit

# ── Advance state ─────────────────────────────────────────────────────────────
next_idx  = (idx + BATCH_SIZE) % max(total, 1)
run_count = state.get("run_count", 0) + 1

# How many full cycles completed
full_cycles = ((run_count * BATCH_SIZE) // max(total, 1))

state.update({
    "batch_index":  next_idx,
    "last_run":     now_str,
    "last_batch":   [r["name"] for r in batch],
    "total_repos":  total,
    "run_count":    run_count,
    "full_cycles":  full_cycles,
})
save_state(state)

print(f"\n{'─'*60}")
print(f"  Touched  : {touched}/{len(batch)} repos")
print(f"  Errors   : {errors}")
print(f"  Runs done: {run_count}  |  Full cycles: {full_cycles}")
print(f"  Next idx : {next_idx} ({rotation[next_idx % total]['name'] if rotation else '—'})")
print(f"{'─'*60}\n")
