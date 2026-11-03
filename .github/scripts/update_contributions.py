#!/usr/bin/env python3
"""Add new open source contributions to the README table.

Included: merged pull requests by the profile owner in repositories they do
not own, plus the items listed in "allow" in .github/contributions.json
(closed pull requests or issues that a maintainer landed or fixed).
Skipped: anything in "ignore", and anything already linked in the table.
Only the rows between the START and END markers are touched.

Usage: update_contributions.py [--dry-run]   (env: GITHUB_TOKEN, optional USER_LOGIN)
"""
import json, os, re, sys, urllib.parse, urllib.request

START, END = "<!-- contributions:start -->", "<!-- contributions:end -->"
ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
README = os.path.join(ROOT, "README.md")
CONFIG = os.path.join(ROOT, ".github", "contributions.json")
USER = os.environ.get("USER_LOGIN") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "TheProtagonist07"


def api(path, **params):
    url = "https://api.github.com" + path + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    if os.environ.get("GITHUB_TOKEN"):
        req.add_header("Authorization", "Bearer " + os.environ["GITHUB_TOKEN"])
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def clean_title(title):
    t = re.sub(r"^(\[[^\]]+\]\s*)+", "", title.strip())            # "[rcore][GLFW] "
    t = re.sub(r"^\w+(\([^)]*\))?!?:\s*", "", t)                    # "fix(site): "
    t = t.rstrip(".").replace("|", "\\|")
    return t[:1].upper() + t[1:]


def fetch(config):
    """Return {key: (repo, number, kind, title, status, date)}."""
    found = {}
    page = 1
    while True:
        res = api("/search/issues", q=f"author:{USER} is:pr is:merged -user:{USER}", per_page=100, page=page)
        for i in res["items"]:
            repo = i["repository_url"].split("/repos/")[1]
            found[f"{repo}#{i['number']}"] = (repo, i["number"], "pull", i["title"], "Merged", i["pull_request"].get("merged_at") or "")
        if len(res["items"]) < 100:
            break
        page += 1
    for key in config.get("allow", []):
        repo, num = key.split("#")
        i = api(f"/repos/{repo}/issues/{num}")
        if i["user"]["login"].lower() != USER.lower() or i["state"] != "closed":
            continue
        kind = "pull" if "pull_request" in i else "issues"
        found.setdefault(key, (repo, int(num), kind, i["title"], "Closed, landed by the maintainer" if kind == "pull" else "Closed", i.get("closed_at") or ""))
    return found


def main():
    dry = "--dry-run" in sys.argv
    config = json.load(open(CONFIG))
    ignore = {k.lower() for k in config.get("ignore", [])}
    text = open(README, encoding="utf-8").read()
    if START not in text or END not in text:
        sys.exit("markers not found in README.md")
    head, rest = text.split(START, 1)
    block, tail = rest.split(END, 1)
    lines = block.strip("\n").split("\n")

    listed = {f"{m[0]}#{m[1]}".lower() for m in
              re.findall(r"github\.com/([\w.-]+/[\w.-]+)/(?:pull|issues)/(\d+)", block)}

    new, newest = {}, {}
    for key, (repo, num, kind, title, status, date) in sorted(fetch(config).items(), key=lambda kv: (kv[1][0], kv[1][1])):
        if key.lower() in listed or key.lower() in ignore or repo.split("/")[0].lower() == USER.lower():
            continue
        name = repo.split("/")[1]
        prefix = "Issue: " if kind == "issues" else ""
        new.setdefault(repo, []).append(
            f"| [{name}](https://github.com/{repo}) | {prefix}{clean_title(title)}, "
            f"[#{num}](https://github.com/{repo}/{kind}/{num}) | {status} |")
        newest[repo] = max(newest.get(repo, ""), date)

    # A project already in the table: add after that project's last row.
    # A new project: add at the top, newest first (the existing order).
    body = lines[2:]
    for repo in list(new):
        idx = [n for n, l in enumerate(body) if l.startswith(f"| [{repo.split('/')[1]}](https://github.com/{repo})")]
        if idx:
            body[idx[-1] + 1:idx[-1] + 1] = new.pop(repo)
    top = [r for repo in sorted(new, key=lambda k: newest[k], reverse=True) for r in new[repo]]
    body = top + body

    result = "\n".join(lines[:2] + body)
    out = head + START + "\n" + result + "\n" + END + tail
    if out == text:
        print("No new contributions.")
        return
    if dry:
        import difflib
        sys.stdout.writelines(difflib.unified_diff(text.splitlines(1), out.splitlines(1), "README.md", "README.md (new)"))
    else:
        open(README, "w", encoding="utf-8").write(out)
        print("README.md updated.")


if __name__ == "__main__":
    main()
