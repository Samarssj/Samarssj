#!/usr/bin/env python3
"""Generate self-hosted GitHub profile analytics SVGs."""

from __future__ import annotations

import json
import os
import html
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path

USERNAME = "Samarssj"
ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()


def github_request(path: str, payload: dict | None = None) -> dict:
    body = None
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Samarssj-profile-analytics",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
        request = urllib.request.Request(f"{API}{path}", data=body, headers=headers, method="POST")
    else:
        request = urllib.request.Request(f"{API}{path}", headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def text(x: int, y: int, value: object, size: int = 16, color: str = "#c9d1d9", weight: str = "400", anchor: str = "start") -> str:
    return f'<text x="{x}" y="{y}" fill="{color}" font-family="Arial, Helvetica, sans-serif" font-size="{size}px" font-weight="{weight}" text-anchor="{anchor}">{esc(value)}</text>'


def svg_document(width: int, height: int, body: str) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">
  <title>Samar Singh GitHub analytics</title>
  <rect width="100%" height="100%" rx="14" fill="#0d1117"/>
  {body}
</svg>
'''


def generate_stats(repos: list[dict], contributions: int, pulls: int, issues: int) -> None:
    stars = sum(repo.get("stargazers_count", 0) for repo in repos)
    forks = sum(repo.get("forks_count", 0) for repo in repos)
    metrics = [
        ("Repositories", len(repos)),
        ("Total Stars", stars),
        ("Total Forks", forks),
        ("Contributions", contributions),
        ("Pull Requests", pulls),
        ("Issues", issues),
    ]
    body = [
        text(28, 40, "GitHub Statistics", 24, "#70a5fd", "700"),
        text(28, 65, "Live data generated from GitHub", 12, "#8b949e"),
    ]
    for index, (label, value) in enumerate(metrics):
        col = index % 2
        row = index // 2
        x = 35 + col * 245
        y = 105 + row * 42
        body.append(text(x, y, label, 14, "#8b949e"))
        body.append(text(x + 205, y, value, 18, "#c9d1d9", "700", "end"))
        body.append(f'<line x1="{x}" y1="{y + 12}" x2="{x + 205}" y2="{y + 12}" stroke="#30363d"/>')
    body.append(text(250, 220, f"Updated {datetime.utcnow().strftime('%Y-%m-%d')} UTC", 11, "#8b949e", anchor="middle"))
    (ASSETS / "github-stats.svg").write_text(svg_document(520, 245, "\n  ".join(body)), encoding="utf-8")


def generate_languages(repos: list[dict]) -> None:
    counts = Counter(repo.get("language") for repo in repos if repo.get("language"))
    items = counts.most_common(6)
    colors = ["#3776ab", "#f34b7d", "#f1e05a", "#3178c6", "#e34c26", "#563d7c"]
    total = max(sum(count for _, count in items), 1)
    cx, cy, radius = 130, 135, 78
    circumference = 2 * 3.141592653589793 * radius
    body = [
        text(28, 38, "Top Languages by Repository", 22, "#70a5fd", "700"),
        f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="#161b22" stroke-width="34"/>',
    ]
    offset = 0.0
    for index, (language, count) in enumerate(items):
        length = circumference * count / total
        color = colors[index % len(colors)]
        body.append(f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="{color}" stroke-width="34" stroke-dasharray="{length:.2f} {circumference - length:.2f}" stroke-dashoffset="{-offset:.2f}" transform="rotate(-90 {cx} {cy})"/>')
        offset += length
    body.append(text(cx, cy - 4, len(repos), 24, "#c9d1d9", "700", "middle"))
    body.append(text(cx, cy + 18, "repos", 12, "#8b949e", anchor="middle"))
    for index, (language, count) in enumerate(items):
        y = 76 + index * 27
        percentage = round(count * 100 / total)
        body.append(f'<circle cx="290" cy="{y - 5}" r="6" fill="{colors[index % len(colors)]}"/>')
        body.append(text(305, y, f"{language}  {percentage}%", 14, "#c9d1d9"))
    (ASSETS / "github-languages.svg").write_text(svg_document(520, 245, "\\n  ".join(body)), encoding="utf-8")


def generate_contributions(calendar: dict) -> None:
    weeks = calendar["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    total = calendar["data"]["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]
    cell = 14
    gap = 4
    left = 42
    top = 65
    width = 1200
    height = 245
    palette = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
    body = [
        text(left, 32, "Contribution Activity", 24, "#70a5fd", "700"),
        text(width - 24, 32, f"{total} contributions in the last year", 13, "#8b949e", anchor="end"),
    ]
    month_labels: dict[int, str] = {}
    for week_index, week in enumerate(weeks[-53:]):
        x = left + week_index * (cell + gap)
        for day_index, day in enumerate(week["contributionDays"]):
            y = top + day_index * (cell + gap)
            count = day["contributionCount"]
            level = min(count, 4)
            body.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3" fill="{palette[level]}"><title>{esc(day["date"])}: {count} contributions</title></rect>')
            if day_index == 0:
                month = day["date"][5:7]
                if month not in month_labels:
                    month_labels[month] = x
        if week_index % 4 == 0:
            body.append(text(x, 235, weeks[-53:][week_index]["contributionDays"][0]["date"][:4], 10, "#8b949e"))
    body.append(text(8, top + 12, "Mon", 10, "#8b949e"))
    body.append(text(8, top + 40, "Wed", 10, "#8b949e"))
    body.append(text(8, top + 68, "Fri", 10, "#8b949e"))
    body.append(text(width - 24, 235, "Less  ▪ ▪ ▪ ▪  More", 10, "#8b949e", anchor="end"))
    (ASSETS / "github-contributions.svg").write_text(svg_document(width, height, "\n  ".join(body)), encoding="utf-8")


def main() -> None:
    if not TOKEN:
        raise SystemExit("GITHUB_TOKEN is required")
    repos = github_request(f"/users/{USERNAME}/repos?per_page=100&type=owner&sort=updated")
    repos = [repo for repo in repos if not repo.get("fork")]
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          totalCommitContributions
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays { contributionCount date }
            }
          }
        }
      }
    }
    """
    calendar = github_request("/graphql", {"query": query, "variables": {"login": USERNAME}})
    contribution_data = calendar["data"]["user"]["contributionsCollection"]
    contributions = contribution_data["contributionCalendar"]["totalContributions"]
    pulls = github_request(f"/search/issues?q=author:{USERNAME}+type:pr&per_page=1").get("total_count", 0)
    issues = github_request(f"/search/issues?q=author:{USERNAME}+type:issue&per_page=1").get("total_count", 0)
    ASSETS.mkdir(parents=True, exist_ok=True)
    generate_stats(repos, contributions, pulls, issues)
    generate_languages(repos)
    generate_contributions({"data": {"user": {"contributionsCollection": contribution_data}}})
    print(f"Generated analytics for {USERNAME}: {contributions} contributions, {len(repos)} repositories")


if __name__ == "__main__":
    main()
