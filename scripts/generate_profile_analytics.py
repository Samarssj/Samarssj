"""Generate self-hosted GitHub profile analytics SVGs."""

from __future__ import annotations

import html
import json
import os
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

USERNAME = "Samarssj"
ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()


PALETTE = {
    "ink": "#0b1020",
    "panel": "#111936",
    "panel_2": "#172044",
    "text": "#f8fafc",
    "muted": "#94a3b8",
    "line": "#26345c",
    "purple": "#a78bfa",
    "cyan": "#22d3ee",
    "pink": "#f472b6",
    "orange": "#fb923c",
}

LANGUAGE_COLORS = {
    "Python": "#3776ab",
    "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6",
    "Java": "#b07219",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "Jupyter Notebook": "#da5b0b",
    "Shell": "#89e051",
    "C++": "#f34b7d",
    "Go": "#00add8",
    "Kotlin": "#a97bff",
}


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


def text(
    x: int | float,
    y: int | float,
    value: object,
    size: int = 16,
    color: str = PALETTE["text"],
    weight: str = "400",
    anchor: str = "start",
    letter_spacing: int = 0,
) -> str:
    spacing = f' letter-spacing="{letter_spacing}px"' if letter_spacing else ""
    return f'<text x="{x}" y="{y}" fill="{color}" font-family="Arial, Helvetica, sans-serif" font-size="{size}px" font-weight="{weight}" text-anchor="{anchor}"{spacing}>{esc(value)}</text>'


def svg_document(width: int, height: int, body: str, title: str) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">{esc(title)}</title>
  <desc id="desc">Live GitHub analytics for {USERNAME}, generated from GitHub API data.</desc>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0b1020"/>
      <stop offset="52%" stop-color="#111936"/>
      <stop offset="100%" stop-color="#17102f"/>
    </linearGradient>
    <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#a78bfa"/>
      <stop offset="52%" stop-color="#22d3ee"/>
      <stop offset="100%" stop-color="#f472b6"/>
    </linearGradient>
    <linearGradient id="bar" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#a78bfa"/>
      <stop offset="100%" stop-color="#22d3ee"/>
    </linearGradient>
    <filter id="glow" x="-80%" y="-80%" width="260%" height="260%">
      <feGaussianBlur stdDeviation="3" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <pattern id="grid" width="28" height="28" patternUnits="userSpaceOnUse">
      <path d="M 28 0 L 0 0 0 28" fill="none" stroke="#94a3b8" stroke-opacity="0.045" stroke-width="1"/>
    </pattern>
  </defs>
  <rect width="100%" height="100%" rx="22" fill="url(#bg)"/>
  <rect width="100%" height="100%" rx="22" fill="url(#grid)"/>
  <rect x="0" y="0" width="100%" height="5" rx="3" fill="url(#accent)"/>
  {body}
</svg>
'''


def fmt(value: int) -> str:
    return f"{value:,}"


def card(x: int, y: int, width: int, height: int, label: str, value: int, accent: str) -> list[str]:
    return [
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="16" fill="{PALETTE["panel"]}" fill-opacity="0.84" stroke="{PALETTE["line"]}"/>',
        f'<rect x="{x}" y="{y}" width="5" height="{height}" rx="3" fill="{accent}"/>',
        f'<circle cx="{x + 26}" cy="{y + 25}" r="5" fill="{accent}" filter="url(#glow)"/>',
        text(x + 42, y + 30, label.upper(), 11, PALETTE["muted"], "700", letter_spacing=1),
        text(x + 24, y + 56, fmt(value), 24, PALETTE["text"], "700"),
    ]


def generate_stats(repos: list[dict], contributions: dict) -> None:
    stars = sum(repo.get("stargazers_count", 0) for repo in repos)
    forks = sum(repo.get("forks_count", 0) for repo in repos)
    metrics = [
        ("Repositories", len(repos), PALETTE["purple"]),
        ("Total stars", stars, PALETTE["orange"]),
        ("Total forks", forks, PALETTE["cyan"]),
        ("Commits · 1 year", contributions["totalCommitContributions"], PALETTE["pink"]),
        ("Pull requests", contributions["totalPullRequestContributions"], PALETTE["cyan"]),
        ("Code reviews", contributions["totalPullRequestReviewContributions"], PALETTE["purple"]),
    ]
    body = [
        text(28, 42, "GitHub Pulse", 25, PALETTE["text"], "700"),
        text(28, 67, f"{USERNAME}  /  live profile snapshot", 13, PALETTE["muted"]),
        '<rect x="548" y="28" width="144" height="28" rx="14" fill="#12363d" stroke="#1e6b73"/>',
        '<circle cx="566" cy="42" r="4" fill="#22d3ee" filter="url(#glow)"/>',
        text(578, 47, "SYNCED", 11, PALETTE["cyan"], "700", letter_spacing=1),
    ]
    for index, (label, value, accent) in enumerate(metrics):
        col = index % 3
        row = index // 3
        body.extend(card(28 + col * 228, 94 + row * 78, 210, 64, label, value, accent))
    updated = datetime.now(timezone.utc).strftime("%d %b %Y  ·  %H:%M UTC")
    body.extend([
        text(28, 270, f"LAST SYNC  {updated}", 10, PALETTE["muted"], "700", letter_spacing=1),
        text(692, 270, "AUTO-REFRESH  /  EVERY 6 HOURS", 10, PALETTE["muted"], "700", "end", 1),
    ])
    (ASSETS / "github-stats.svg").write_text(svg_document(720, 292, "\n  ".join(body), "GitHub Pulse statistics for Samar Singh"), encoding="utf-8")


def generate_languages(repos: list[dict]) -> None:
    counts = Counter(repo.get("language") for repo in repos if repo.get("language"))
    items = counts.most_common(5)
    total = max(sum(count for _, count in items), 1)
    body = [
        text(28, 42, "Repository DNA", 25, PALETTE["text"], "700"),
        text(28, 67, "Language mix across active repositories", 13, PALETTE["muted"]),
        text(690, 48, fmt(len(repos)), 25, PALETTE["cyan"], "700", "end"),
        text(690, 68, "PUBLIC REPOS", 10, PALETTE["muted"], "700", "end", 1),
    ]
    if not items:
        body.append(text(28, 130, "No language data available yet.", 16, PALETTE["muted"]))
    for index, (language, count) in enumerate(items):
        y = 104 + index * 34
        percent = count / total
        width = max(12, round(percent * 430))
        color = LANGUAGE_COLORS.get(language, PALETTE["purple"])
        body.extend([
            f'<circle cx="36" cy="{y - 5}" r="6" fill="{color}"/>',
            text(54, y, language, 14, PALETTE["text"], "600"),
            text(690, y, f"{count} repo{'s' if count != 1 else ''}  ·  {percent:.0%}", 12, PALETTE["muted"], "600", "end"),
            f'<rect x="54" y="{y + 8}" width="590" height="7" rx="4" fill="#202b4c"/>',
            f'<rect x="54" y="{y + 8}" width="{width}" height="7" rx="4" fill="{color}" filter="url(#glow)"/>',
        ])
    body.extend([
        f'<rect x="28" y="272" width="664" height="1" fill="{PALETTE["line"]}"/>',
        text(28, 288, "Ranked by repository count  ·  refreshed with GitHub", 10, PALETTE["muted"], "600"),
    ])
    (ASSETS / "github-languages.svg").write_text(svg_document(720, 300, "\n  ".join(body), "Repository language mix for Samar Singh"), encoding="utf-8")


def contribution_level(count: int, maximum: int) -> int:
    if count <= 0:
        return 0
    if maximum <= 4:
        return min(count, 4)
    ratio = count / maximum
    if ratio <= 0.2:
        return 1
    if ratio <= 0.5:
        return 2
    if ratio <= 0.8:
        return 3
    return 4


def generate_contributions(contribution_data: dict) -> None:
    calendar = contribution_data["contributionCalendar"]
    weeks = calendar["weeks"][-53:]
    days = [day for week in weeks for day in week["contributionDays"]]
    maximum = max((day["contributionCount"] for day in days), default=0)
    total = calendar["totalContributions"]
    busiest = max(days, key=lambda day: day["contributionCount"], default={"date": "n/a", "contributionCount": 0})
    palette = ["#18203a", "#36215f", "#63318c", "#a855f7", "#22d3ee"]
    cell = 16
    gap = 5
    left = 64
    top = 112
    width = 1200
    height = 334
    body = [
        text(28, 42, "Contribution Constellation", 25, PALETTE["text"], "700"),
        text(28, 68, "A year of momentum, rendered from your live activity calendar", 13, PALETTE["muted"]),
        f'<rect x="818" y="26" width="354" height="45" rx="14" fill="{PALETTE["panel"]}" stroke="{PALETTE["line"]}"/>',
        text(842, 45, "TOTAL", 10, PALETTE["muted"], "700", letter_spacing=1),
        text(842, 63, fmt(total), 17, PALETTE["cyan"], "700"),
        text(954, 45, "PEAK DAY", 10, PALETTE["muted"], "700", letter_spacing=1),
        text(954, 63, fmt(busiest["contributionCount"]), 17, PALETTE["pink"], "700"),
        text(1060, 45, "LAST 365 DAYS", 10, PALETTE["muted"], "700", letter_spacing=1),
        text(1060, 63, "LIVE", 17, PALETTE["purple"], "700"),
        f'<rect x="{left - 16}" y="{top - 24}" width="1108" height="176" rx="18" fill="#0a0f21" fill-opacity="0.72" stroke="{PALETTE["line"]}"/>',
    ]
    month_seen: set[str] = set()
    for week_index, week in enumerate(weeks):
        x = left + week_index * (cell + gap)
        for day_index, day in enumerate(week["contributionDays"]):
            y = top + day_index * (cell + gap)
            count = day["contributionCount"]
            level = contribution_level(count, maximum)
            color = palette[level]
            body.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="5" fill="{color}" stroke="#0b1020" stroke-width="1"><title>{esc(day["date"])}  ·  {count} contribution{'s' if count != 1 else ''}</title></rect>')
            month = day["date"][:7]
            if day_index == 0 and month not in month_seen:
                body.append(text(x, 92, datetime.strptime(day["date"], "%Y-%m-%d").strftime("%b"), 11, PALETTE["muted"], "600"))
                month_seen.add(month)
    body.extend([
        text(12, top + 12, "Mon", 10, PALETTE["muted"], "600"),
        text(12, top + 52, "Wed", 10, PALETTE["muted"], "600"),
        text(12, top + 92, "Fri", 10, PALETTE["muted"], "600"),
    ])
    legend_x = 64
    legend_y = 302
    body.append(text(64, legend_y + 12, "QUIET", 10, PALETTE["muted"], "700", letter_spacing=1))
    for index, color in enumerate(palette):
        body.append(f'<rect x="{legend_x + 58 + index * 23}" y="{legend_y}" width="14" height="14" rx="4" fill="{color}"/>')
    body.extend([
        text(legend_x + 190, legend_y + 12, "ACTIVE", 10, PALETTE["muted"], "700", letter_spacing=1),
        text(1172, legend_y + 12, f"Peak: {busiest['date']}", 10, PALETTE["muted"], "600", "end"),
    ])
    (ASSETS / "github-contributions.svg").write_text(svg_document(width, height, "\n  ".join(body), "GitHub contribution constellation for Samar Singh"), encoding="utf-8")


def main() -> None:
    if not TOKEN:
        raise SystemExit("GITHUB_TOKEN is required")
    repos = github_request(f"/users/{USERNAME}/repos?per_page=100&type=owner&sort=updated")
    repos = [repo for repo in repos if not repo.get("fork") and not repo.get("archived")]
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          totalCommitContributions
          totalPullRequestContributions
          totalIssueContributions
          totalPullRequestReviewContributions
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
    ASSETS.mkdir(parents=True, exist_ok=True)
    generate_stats(repos, contribution_data)
    generate_languages(repos)
    generate_contributions(contribution_data)
    print(f"Generated analytics for {USERNAME}: {contribution_data['contributionCalendar']['totalContributions']} contributions, {len(repos)} repositories")


if __name__ == "__main__":
    main()
