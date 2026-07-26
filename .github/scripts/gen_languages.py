#!/usr/bin/env python3
"""Generate a styled "Linguagens mais usadas" SVG from the user's real public repos.

Dynamic: aggregates language bytes across all owned, non-fork public repos via the
GitHub API, so newly added repos show up automatically on the next run.
"""
import json
import math
import os
import urllib.request

TOKEN = os.environ["GH_TOKEN"]
USER = os.environ.get("GH_USER", "rodrigob-dev")
OUT = os.environ.get("OUT", "profile/languages.svg")

# GitHub linguist colors for common languages (fallback = grey).
COLORS = {
    "Python": "#3572A5", "TypeScript": "#3178c6", "JavaScript": "#f1e05a",
    "HTML": "#e34c26", "CSS": "#563d7c", "SCSS": "#c6538c", "C": "#555555",
    "C++": "#f34b7d", "C#": "#178600", "Java": "#b07219", "Go": "#00ADD8",
    "Rust": "#dea584", "Ruby": "#701516", "PHP": "#4F5D95", "Shell": "#89e051",
    "PLpgSQL": "#336790", "TSQL": "#e38c00", "Jupyter Notebook": "#DA5B0B",
    "Dockerfile": "#384d54", "Vue": "#41b883", "Svelte": "#ff3e00",
    "Kotlin": "#A97BFF", "Swift": "#F05138", "MDX": "#fcb32c",
}
OTHER = "#8b949e"
# Nicer display names for a few languages.
DISPLAY = {"PLpgSQL": "PL/pgSQL"}

LIMIT = 6          # top languages shown individually; rest grouped into "Outras"
BAR_X, BAR_W = 24, 432


def api(url):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "languages-card",
    })
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def all_repos():
    repos, page = [], 1
    while True:
        batch = api(f"https://api.github.com/users/{USER}/repos"
                    f"?per_page=100&type=owner&page={page}")
        repos += batch
        if len(batch) < 100:
            return repos
        page += 1


def fmt(pct):
    return f"{pct:.1f}".replace(".", ",") + "%"


def build_segments():
    totals = {}
    for repo in all_repos():
        if repo.get("fork"):
            continue
        for lang, size in api(f"https://api.github.com/repos/"
                              f"{repo['full_name']}/languages").items():
            totals[lang] = totals.get(lang, 0) + size

    total = sum(totals.values())
    if total == 0:
        return [], 0
    ordered = sorted(totals.items(), key=lambda kv: -kv[1])
    segs = [[name, val, COLORS.get(name, OTHER)] for name, val in ordered[:LIMIT]]
    rest = ordered[LIMIT:]
    if rest:
        segs.append(["Outras", sum(v for _, v in rest), OTHER])
    return segs, total


def render(segs, total):
    if total == 0:
        rows = 1
    else:
        rows = math.ceil(len(segs) / 2)
    height = 72 + rows * 28

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="480" height="{height}" '
        f'viewBox="0 0 480 {height}" fill="none" role="img" '
        f'aria-label="Linguagens mais usadas">',
        '<style>'
        '.t{font:600 16px -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;fill:#0366d6}'
        '.l{font:400 13px -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;fill:#24292f}'
        '.p{font:600 13px -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;fill:#57606a}'
        '</style>',
        f'<rect x="0.5" y="0.5" width="479" height="{height - 1}" rx="6" '
        f'fill="#ffffff" stroke="#e1e4e8"/>',
        '<text x="24" y="34" class="t">Linguagens mais usadas</text>',
        '<clipPath id="bar"><rect x="24" y="52" width="432" height="10" rx="5"/></clipPath>',
    ]

    if total == 0:
        parts.append('<text x="24" y="80" class="l">Sem dados de linguagem ainda.</text>')
        parts.append('</svg>')
        return "\n".join(parts)

    # segmented bar
    parts.append('<g clip-path="url(#bar)">')
    x = float(BAR_X)
    for i, (name, val, color) in enumerate(segs):
        w = BAR_W * val / total
        # avoid sub-pixel gaps: last segment fills to the end
        w = (BAR_X + BAR_W - x) if i == len(segs) - 1 else w
        parts.append(f'<rect x="{x:.1f}" y="52" width="{w:.1f}" height="10" fill="{color}"/>')
        x += w
    parts.append('</g>')

    # legend (two columns)
    cols = [(30, 42), (250, 262)]
    for i, (name, val, color) in enumerate(segs):
        cx, tx = cols[i % 2]
        cy = 86 + (i // 2) * 28
        label = DISPLAY.get(name, name)
        pct = fmt(100 * val / total)
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="5" fill="{color}"/>')
        parts.append(f'<text x="{tx}" y="{cy + 4}" class="l">{label} '
                     f'<tspan class="p">{pct}</tspan></text>')

    parts.append('</svg>')
    return "\n".join(parts)


def main():
    segs, total = build_segments()
    svg = render(segs, total)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(svg + "\n")
    print(f"Wrote {OUT} ({len(segs)} languages, {total} bytes total)")


if __name__ == "__main__":
    main()
