#!/usr/bin/env python3
"""Refresh the numbers and the weekly line in assets/stats-compact-indigo.svg.

Reads the last 12 months of the contribution calendar through the GraphQL API
and rewrites only the three numbers and the two polylines. The rest of the SVG
(layout, colours, fonts, labels) is left exactly as it is.

Usage: update_stats_card.py [--dry-run]
Env:   STATS_TOKEN or GITHUB_TOKEN (required), USER_LOGIN (optional)

If the API call fails, or the total drops to under half of what the card shows
(which is what a token that cannot see private contributions would produce),
the card is left unchanged and a warning is printed.
"""
import datetime, json, os, re, sys, urllib.request
from zoneinfo import ZoneInfo

SVG = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "stats-compact-indigo.svg")
USER = os.environ.get("USER_LOGIN") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "TheProtagonist07"
QUERY = """query($login:String!){user(login:$login){contributionsCollection{contributionCalendar{
totalContributions weeks{contributionDays{date contributionCount}}}}}}"""
X0, X1, Y_BASE, Y_RANGE, WEEKS = 40.0, 960.0, 150.0, 40.0, 52


def fetch():
    token = os.environ.get("STATS_TOKEN") or os.environ.get("GITHUB_TOKEN")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": "Bearer " + (token or ""), "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        data = json.load(r)
    if data.get("errors") or not data.get("data", {}).get("user"):
        raise RuntimeError(json.dumps(data.get("errors") or data))
    cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    return cal["totalContributions"], cal["weeks"]


def streaks(days):
    """days: [(date, count)] oldest first. Today with no contributions yet does not break the streak."""
    today = datetime.datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat()
    longest = run = 0
    for _, c in days:
        run = run + 1 if c else 0
        longest = max(longest, run)
    i = len(days) - 1
    if i >= 0 and days[i][1] == 0 and days[i][0] >= today:
        i -= 1
    current = 0
    while i >= 0 and days[i][1]:
        current += 1
        i -= 1
    return current, longest


def points(weeks):
    totals = [sum(d["contributionCount"] for d in w["contributionDays"]) for w in weeks][-WEEKS:]
    peak = max(totals) or 1
    step = (X1 - X0) / (len(totals) - 1)
    return " ".join(f"{X0 + n * step:.1f},{Y_BASE - Y_RANGE * v / peak:.1f}" for n, v in enumerate(totals))


def days_label(n):
    return f"{n} day" if n == 1 else f"{n} days"


def set_text(svg, x, value):
    """Replace the text of the number at column x (the one at y=56)."""
    pat = re.compile(rf'(<text x="{x}" y="56"[^>]*>)[^<]*(</text>)')
    new, n = pat.subn(lambda m: m.group(1) + value + m.group(2), svg)
    if n != 1:
        raise RuntimeError(f"number at x={x} not found")
    return new


def main():
    old = open(SVG, encoding="utf-8").read()
    try:
        total, weeks = fetch()
    except Exception as e:  # leave the card as it is
        print(f"::warning::Could not read the contribution calendar, card unchanged: {e}")
        return
    old_total = int(re.search(r'x="190" y="56"[^>]*>([\d,]+)<', old).group(1).replace(",", ""))
    if total < old_total / 2:
        print(f"::warning::Calendar total {total} is under half of the card's {old_total}; "
              "the token may not see private contributions. Card unchanged.")
        return
    days = [(d["date"], d["contributionCount"]) for w in weeks for d in w["contributionDays"]]
    current, longest = streaks(days)
    pts = points(weeks)
    svg = set_text(old, 190, f"{total:,}")
    svg = set_text(svg, 500, days_label(current))
    svg = set_text(svg, 810, days_label(longest))
    svg, n1 = re.subn(r'(<polyline points=")[^"]*(" fill="#6366f1")',
                      lambda m: f"{m.group(1)}{X0:.0f},{Y_BASE:.0f} {pts} {X1:.0f},{Y_BASE:.0f}{m.group(2)}", svg)
    svg, n2 = re.subn(r'(<polyline points=")[^"]*(" fill="none")', lambda m: m.group(1) + pts + m.group(2), svg)
    if (n1, n2) != (1, 1):
        raise RuntimeError("polylines not found")
    print(f"total={total:,} current={current} longest={longest} weeks={len(pts.split())}")
    if svg == old:
        print("Card already up to date.")
    elif "--dry-run" in sys.argv:
        print("Would update assets/stats-compact-indigo.svg")
    else:
        open(SVG, "w", encoding="utf-8").write(svg)
        print("assets/stats-compact-indigo.svg updated.")


if __name__ == "__main__":
    main()
