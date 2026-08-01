#!/usr/bin/env python3
"""Generate a styled "Linguagens mais usadas" SVG from the user's real repos.

Dynamic: aggregates language bytes across the repos the token can see, so newly
added repos appear automatically on the next run. When the token has `repo`
scope (and `read:org` for org repos), private repos are included in the totals —
only aggregate percentages are shown, never any code. A caption notes when
private repos are counted.
"""
import json
import math
import os
import urllib.request

TOKEN = os.environ["GH_TOKEN"]
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
DISPLAY = {"PLpgSQL": "PL/pgSQL"}

LIMIT = 6          # top languages shown individually; rest grouped into "Outras"
BAR_X, BAR_W = 24, 432

# No single repo may contribute more than this share of the total. Without it a
# large legacy monorepo drowns out everything else (one Vue front-end was 41% of
# the whole card), and day-to-day work can never move the numbers.
REPO_CAP = 0.10

# Languages excluded before anything else is measured. Notebooks store their
# cell output — base64 images included — inside the .ipynb, so linguist counts
# one notebook as heavily as hundreds of source files. That is file format, not
# signal about what I write.
IGNORED = {"Jupyter Notebook"}


def api(url):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "languages-card",
    })
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def all_repos():
    """Repos the token can access: owned, org repos, and ones I collaborate on.

    `collaborator` matters: side projects living under someone else's account
    are invisible without it, however much of the code is mine.
    """
    repos, page = [], 1
    while True:
        batch = api("https://api.github.com/user/repos"
                    "?per_page=100&visibility=all"
                    f"&affiliation=owner,organization_member,collaborator"
                    f"&page={page}")
        repos += batch
        if len(batch) < 100:
            return repos
        page += 1


def fmt(pct):
    return f"{pct:.1f}".replace(".", ",") + "%"


def build_segments():
    per_repo, has_private = [], False
    for repo in all_repos():
        if repo.get("fork"):
            continue
        if repo.get("private"):
            has_private = True
        langs = {lang: size
                 for lang, size in api(f"https://api.github.com/repos/"
                                       f"{repo['full_name']}/languages").items()
                 if lang not in IGNORED}
        # Dropped before sizing, so a repo made only of ignored languages does
        # not exist as far as the cap and the grand total are concerned.
        if langs:
            per_repo.append(langs)

    # Weight each repo down to at most REPO_CAP of the grand total, so the card
    # reflects the spread of what I work on rather than which repo is biggest.
    grand = sum(sum(langs.values()) for langs in per_repo)
    totals = {}
    for langs in per_repo:
        size = sum(langs.values())
        weight = min(1.0, REPO_CAP * grand / size) if grand else 1.0
        for lang, value in langs.items():
            totals[lang] = totals.get(lang, 0) + value * weight

    total = sum(totals.values())
    if total == 0:
        return [], 0, has_private
    ordered = sorted(totals.items(), key=lambda kv: -kv[1])
    segs = [[name, val, COLORS.get(name, OTHER)] for name, val in ordered[:LIMIT]]
    rest = ordered[LIMIT:]
    if rest:
        segs.append(["Outras", sum(v for _, v in rest), OTHER])
    return segs, total, has_private


def render(segs, total, has_private):
    caption = "includes private repos" if has_private else ""
    cap_h = 18 if caption else 0
    rows = 1 if total == 0 else math.ceil(len(segs) / 2)
    height = 72 + cap_h + rows * 28

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="480" height="{height}" '
        f'viewBox="0 0 480 {height}" fill="none" role="img" '
        f'aria-label="Most used languages">',
        '<style>'
        '.t{font:600 16px -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;fill:#0366d6}'
        '.c{font:400 11px -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;fill:#8b949e}'
        '.l{font:400 13px -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;fill:#24292f}'
        '.p{font:600 13px -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;fill:#57606a}'
        '</style>',
        f'<rect x="0.5" y="0.5" width="479" height="{height - 1}" rx="6" '
        f'fill="#ffffff" stroke="#e1e4e8"/>',
        '<text x="24" y="34" class="t">Most used languages</text>',
    ]
    if caption:
        parts.append(f'<text x="24" y="48" class="c">{caption}</text>')

    bar_y = 52 + cap_h
    parts.append(f'<clipPath id="bar"><rect x="24" y="{bar_y}" width="432" height="10" rx="5"/></clipPath>')

    if total == 0:
        parts.append(f'<text x="24" y="{bar_y + 28}" class="l">No language data yet.</text>')
        parts.append('</svg>')
        return "\n".join(parts)

    parts.append('<g clip-path="url(#bar)">')
    x = float(BAR_X)
    for i, (name, val, color) in enumerate(segs):
        w = (BAR_X + BAR_W - x) if i == len(segs) - 1 else BAR_W * val / total
        parts.append(f'<rect x="{x:.1f}" y="{bar_y}" width="{w:.1f}" height="10" fill="{color}"/>')
        x += w
    parts.append('</g>')

    cols = [(30, 42), (250, 262)]
    legend_y0 = bar_y + 34
    for i, (name, val, color) in enumerate(segs):
        cx, tx = cols[i % 2]
        cy = legend_y0 + (i // 2) * 28
        label = DISPLAY.get(name, name)
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="5" fill="{color}"/>')
        parts.append(f'<text x="{tx}" y="{cy + 4}" class="l">{label} '
                     f'<tspan class="p">{fmt(100 * val / total)}</tspan></text>')

    parts.append('</svg>')
    return "\n".join(parts)


def main():
    segs, total, has_private = build_segments()
    svg = render(segs, total, has_private)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(svg + "\n")
    print(f"Wrote {OUT}: {len(segs)} langs, {total:,.0f} weighted bytes "
          f"(cap {REPO_CAP:.0%}/repo), private={has_private}")


if __name__ == "__main__":
    main()
