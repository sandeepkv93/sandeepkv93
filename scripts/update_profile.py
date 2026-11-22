#!/usr/bin/env python3
"""
Generate dark/light theme-aware animated SVGs for sandeepkv93's GitHub Profile README.
Uses only the Python standard library.
"""
from __future__ import annotations
import datetime as dt
import json
import os
import subprocess
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any
USERNAME = "sandeepkv93"
CAREER_START = dt.date(2015, 7, 1)
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
GRAPHQL_QUERY = """
query($login: String!, $cursor: String) {
  user(login: $login) {
    repositories(first: 100, after: $cursor, ownerAffiliations: OWNER, isFork: false, orderBy: {field: PUSHED_AT, direction: DESC}) {
      totalCount
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        name
        isPrivate
        stargazerCount
        primaryLanguage {
          name
          color
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
      }
    }
    pullRequests {
      totalCount
    }
    followers {
      totalCount
    }
  }
}
"""
LANG_FALLBACK_COLORS = {
    "Go": "#00ADD8",
    "Python": "#3572A5",
    "Java": "#B07219",
    "TypeScript": "#3178C6",
    "JavaScript": "#F1E05A",
    "Shell": "#89E051",
    "C": "#555555",
    "C#": "#178600",
    "Kotlin": "#A97BFF",
    "Dockerfile": "#384D54",
}
THEMES = {
    "dark": {
        "bg": "#0D1117",
        "surface": "#161B22",
        "surface2": "#1C2330",
        "border": "#30363D",
        "text": "#E6EDF3",
        "muted": "#8B949E",
        "subtle": "#6E7681",
        "accent": "#29B5E8",
        "accent2": "#58A6FF",
        "accent3": "#3FB950",
        "accent4": "#D2A8FF",
        "warn": "#FFA657",
        "bar_bg": "#21262D",
        "glow": "0.35",
        "grid": "#1F2937",
    },
    "light": {
        "bg": "#FFFFFF",
        "surface": "#F6F8FA",
        "surface2": "#EEF2F7",
        "border": "#D0D7DE",
        "text": "#1F2328",
        "muted": "#59636E",
        "subtle": "#6E7781",
        "accent": "#0B86B8",
        "accent2": "#0969DA",
        "accent3": "#1A7F37",
        "accent4": "#8250DF",
        "warn": "#BC4C00",
        "bar_bg": "#E6ECF2",
        "glow": "0.18",
        "grid": "#E5EBF1",
    },
}
def run_graphql(token: str | None, cursor: str | None) -> dict[str, Any]:
    variables: dict[str, Any] = {"login": USERNAME, "cursor": cursor}
    if token:
        payload = json.dumps({"query": GRAPHQL_QUERY, "variables": variables}).encode("utf-8")
        req = urllib.request.Request(
            "https://api.github.com/graphql",
            data=payload,
            headers={
                "Authorization": f"bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": "sandeepkv93-profile-updater",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    cmd = ["gh", "api", "graphql", "-F", f"login={USERNAME}", "-f", f"query={GRAPHQL_QUERY}"]
    if cursor:
        cmd.extend(["-F", f"cursor={cursor}"])
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(proc.stdout)
def fetch_github_stats() -> dict[str, Any]:
    token = os.environ.get("GH_STATS_TOKEN") or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    repo_nodes: list[dict[str, Any]] = []
    cursor: str | None = None
    user: dict[str, Any] = {}
    while True:
        data = run_graphql(token, cursor)
        user = data["data"]["user"]
        repos = user["repositories"]
        repo_nodes.extend(repos["nodes"])
        if not repos["pageInfo"]["hasNextPage"]:
            break
        cursor = repos["pageInfo"]["endCursor"]
    public_repos = [r for r in repo_nodes if not r["isPrivate"]]
    total_stars = sum(r["stargazerCount"] for r in repo_nodes)
    lang_counts: Counter[str] = Counter()
    lang_colors: dict[str, str] = {}
    for r in public_repos:
        if r["name"].lower() == USERNAME.lower():
            continue
        pl = r.get("primaryLanguage")
        if pl and pl.get("name"):
            name = pl["name"]
            lang_counts[name] += 1
            lang_colors[name] = pl.get("color") or LANG_FALLBACK_COLORS.get(name, "#29B5E8")
    top_langs = []
    top_items = lang_counts.most_common(5)
    if top_items:
        total_lang_repos = sum(c for _, c in top_items)
        exact_tenths = [(name, count, (count * 1000) / total_lang_repos) for name, count in top_items]
        floored = [int(t) for _, _, t in exact_tenths]
        remainder = 1000 - sum(floored)
        order = sorted(
            range(len(exact_tenths)),
            key=lambda i: (exact_tenths[i][2] - floored[i], exact_tenths[i][1]),
            reverse=True,
        )
        for idx in order[:remainder]:
            floored[idx] += 1
        for (name, count, _), tenths in zip(exact_tenths, floored):
            pct = tenths / 10.0
            top_langs.append({"name": name, "count": count, "pct": pct, "color": lang_colors[name]})
    contrib = user["contributionsCollection"]
    today = dt.date.today()
    years_exp = (today - CAREER_START).days / 365.25
    return {
        "public_repos": len(public_repos),
        "total_repos": user["repositories"]["totalCount"],
        "total_stars": total_stars,
        "contributions_yr": contrib["contributionCalendar"]["totalContributions"],
        "commits_yr": contrib["totalCommitContributions"],
        "pull_requests": user["pullRequests"]["totalCount"],
        "followers": user["followers"]["totalCount"],
        "top_langs": top_langs,
        "years_exp": f"{int(years_exp)}+ yrs",
        "updated_date": today.strftime("%Y-%m-%d"),
    }
def esc(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
def render_banner_svg(mode: str) -> str:
    t = THEMES[mode]
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 920 190" width="920" height="190" role="img" aria-label="Sandeep Vishnu - Senior Software Engineer at Snowflake">
  <defs>
    <linearGradient id="bgGrad-{mode}" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{t['bg']}"/>
      <stop offset="55%" stop-color="{t['surface']}"/>
      <stop offset="100%" stop-color="{t['surface2']}"/>
    </linearGradient>
    <linearGradient id="accentGrad-{mode}" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{t['accent']}"/>
      <stop offset="50%" stop-color="{t['accent2']}"/>
      <stop offset="100%" stop-color="{t['accent4']}"/>
    </linearGradient>
    <radialGradient id="orb1-{mode}" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="{t['accent']}" stop-opacity="{t['glow']}"/>
      <stop offset="100%" stop-color="{t['accent']}" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="orb2-{mode}" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="{t['accent4']}" stop-opacity="0.22"/>
      <stop offset="100%" stop-color="{t['accent4']}" stop-opacity="0"/>
    </radialGradient>
    <pattern id="dotGrid-{mode}" width="24" height="24" patternUnits="userSpaceOnUse">
      <circle cx="2" cy="2" r="1" fill="{t['grid']}"/>
    </pattern>
    <clipPath id="cardClip-{mode}">
      <rect x="1" y="1" width="918" height="188" rx="16"/>
    </clipPath>
  </defs>
  <style>
    .title {{ font: 800 34px -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; fill: {t['text']}; letter-spacing: -0.5px; }}
    .sub {{ font: 600 15px -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; fill: {t['accent']}; }}
    .tagline {{ font: 400 13.5px -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; fill: {t['muted']}; }}
    .badge-txt {{ font: 600 11.5px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; fill: {t['text']}; }}
    .mono-small {{ font: 500 11px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; fill: {t['muted']}; }}
    @keyframes pulse {{ 0%, 100% {{ opacity: 0.45; }} 50% {{ opacity: 1; }} }}
    @keyframes floatSlow {{ 0%, 100% {{ transform: translateY(0px); }} 50% {{ transform: translateY(-4px); }} }}
    @keyframes dashFlow {{ to {{ stroke-dashoffset: -36; }} }}
    .node-pulse {{ animation: pulse 3.2s ease-in-out infinite; }}
    .node-pulse-2 {{ animation: pulse 4.1s ease-in-out 0.9s infinite; }}
    .node-pulse-3 {{ animation: pulse 3.6s ease-in-out 1.7s infinite; }}
    .flow-line {{ stroke-dasharray: 4 5; animation: dashFlow 3.5s linear infinite; }}
    .status-dot {{ animation: pulse 2s ease-in-out infinite; }}
    .snowflake-group {{ animation: floatSlow 5s ease-in-out infinite; }}
  </style>
  <g clip-path="url(#cardClip-{mode})">
    <rect x="0" y="0" width="920" height="190" fill="url(#bgGrad-{mode})"/>
    <rect x="0" y="0" width="920" height="190" fill="url(#dotGrid-{mode})" opacity="0.7"/>
    <circle cx="810" cy="70" r="170" fill="url(#orb1-{mode})"/>
    <circle cx="140" cy="175" r="150" fill="url(#orb2-{mode})"/>
    <rect x="0" y="0" width="920" height="3.5" fill="url(#accentGrad-{mode})"/>
    <g transform="translate(40, 42)">
      <rect x="0" y="0" width="292" height="24" rx="12" fill="{t['surface']}" stroke="{t['border']}" stroke-width="1"/>
      <circle cx="14" cy="12" r="4" fill="{t['accent3']}" class="status-dot"/>
      <text x="26" y="16" class="badge-txt">Building Streamlit in Snowflake (SiS)</text>
      <text x="0" y="66" class="title">Sandeep Vishnu</text>
      <text x="0" y="92" class="sub">Senior Software Engineer @ Snowflake  |  Greater Seattle Area</text>
      <text x="0" y="116" class="tagline">Distributed Systems  &#183;  Cloud-Native Platforms  &#183;  OpenTelemetry  &#183;  Go &amp; Python</text>
    </g>
    <g transform="translate(650, 18)">
      <line x1="55" y1="78" x2="128" y2="38" stroke="{t['accent']}" stroke-width="1.4" opacity="0.65" class="flow-line"/>
      <line x1="128" y1="38" x2="205" y2="78" stroke="{t['accent2']}" stroke-width="1.4" opacity="0.65" class="flow-line"/>
      <line x1="205" y1="78" x2="128" y2="118" stroke="{t['accent4']}" stroke-width="1.4" opacity="0.65" class="flow-line"/>
      <line x1="128" y1="118" x2="55" y2="78" stroke="{t['accent3']}" stroke-width="1.4" opacity="0.65" class="flow-line"/>
      <line x1="55" y1="78" x2="205" y2="78" stroke="{t['accent']}" stroke-width="1" opacity="0.35" class="flow-line"/>
      <line x1="128" y1="38" x2="128" y2="118" stroke="{t['accent']}" stroke-width="1" opacity="0.35" class="flow-line"/>
      <g class="snowflake-group" transform="translate(128, 78)">
        <circle r="24" fill="{t['surface']}" stroke="{t['accent']}" stroke-width="1.8"/>
        <g stroke="{t['accent']}" stroke-width="2" stroke-linecap="round">
          <line x1="0" y1="-14" x2="0" y2="14"/>
          <line x1="-12.1" y1="-7" x2="12.1" y2="7"/>
          <line x1="-12.1" y1="7" x2="12.1" y2="-7"/>
          <polyline points="-3.5,-10 0,-7 3.5,-10" fill="none"/>
          <polyline points="-3.5,10 0,7 3.5,10" fill="none"/>
          <polyline points="-10,-2 -6.5,-3.8 -7.2,-7.8" fill="none"/>
          <polyline points="10,2 6.5,3.8 7.2,7.8" fill="none"/>
          <polyline points="-10,2 -6.5,3.8 -7.2,7.8" fill="none"/>
          <polyline points="10,-2 6.5,-3.8 7.2,-7.8" fill="none"/>
        </g>
      </g>
      <g class="node-pulse">
        <circle cx="128" cy="30" r="12" fill="{t['surface']}" stroke="{t['accent2']}" stroke-width="1.5"/>
        <text x="128" y="34" text-anchor="middle" class="mono-small" fill="{t['accent2']}">K8s</text>
      </g>
      <g class="node-pulse-2">
        <circle cx="208" cy="78" r="14" fill="{t['surface']}" stroke="{t['accent4']}" stroke-width="1.5"/>
        <text x="208" y="82" text-anchor="middle" class="mono-small" fill="{t['accent4']}">OTel</text>
      </g>
      <g class="node-pulse-3">
        <circle cx="128" cy="126" r="12" fill="{t['surface']}" stroke="{t['accent3']}" stroke-width="1.5"/>
        <text x="128" y="130" text-anchor="middle" class="mono-small" fill="{t['accent3']}">Go</text>
      </g>
      <g class="node-pulse">
        <circle cx="48" cy="78" r="14" fill="{t['surface']}" stroke="{t['warn']}" stroke-width="1.5"/>
        <text x="48" y="82" text-anchor="middle" class="mono-small" fill="{t['warn']}">Raft</text>
      </g>
      <text x="128" y="156" text-anchor="middle" class="mono-small">cloud-native &#183; resilient &#183; observable</text>
    </g>
  </g>
  <rect x="1" y="1" width="918" height="188" rx="16" fill="none" stroke="{t['border']}" stroke-width="1.2"/>
</svg>
"""
def render_terminal_svg(mode: str, stats: dict[str, Any]) -> str:
    t = THEMES[mode]
    rows = [
        ("role", "Senior Software Engineer @ Snowflake (SiS)", t["accent"]),
        ("experience", f"{stats['years_exp']} (Snowflake, Microsoft Azure, VMware)", t["text"]),
        ("education", "M.S. Computer Science, Stony Brook University", t["text"]),
        ("focus", "Cloud-Native Runtimes, Distributed Systems, OpenTelemetry", t["accent2"]),
        ("languages", "Go, Python, Java, TypeScript, C", t["accent3"]),
        ("infra", "Kubernetes, Docker, Bazel, Prometheus, Grafana, RabbitMQ", t["text"]),
        ("patent", "US12056521B2 (ML Spot VM Replenishment, Azure)", t["accent4"]),
        ("publication", "DSAdvisor (IEEE LaTiCE 2016)", t["text"]),
        ("github.live", f"{stats['public_repos']} public repos | {stats['contributions_yr']} contribs/yr | {stats['total_stars']} stars", t["warn"]),
    ]
    row_lines = []
    y = 104
    for key, val, color in rows:
        dots = "." * max(2, 13 - len(key))
        row_lines.append(
            f'    <text x="275" y="{y}" class="mono">'
            f'<tspan fill="{t["warn"]}" font-weight="700">{esc(key)}</tspan>'
            f'<tspan fill="{t["subtle"]}"> {dots} </tspan>'
            f'<tspan fill="{color}">{esc(val)}</tspan>'
            f"</text>"
        )
        y += 26
    rows_svg = "\n".join(row_lines)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 920 390" width="920" height="390" role="img" aria-label="Sandeep Vishnu Neofetch Telemetry Card">
  <style>
    .chrome-title {{ font: 600 12px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; fill: {t['muted']}; }}
    .header-user {{ font: 700 15px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; fill: {t['accent']}; }}
    .mono {{ font: 500 13.5px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
    .prompt {{ font: 600 13px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
    .meta {{ font: 500 11px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; fill: {t['subtle']}; }}
    @keyframes blink {{ 0%, 49% {{ opacity: 1; }} 50%, 100% {{ opacity: 0; }} }}
    @keyframes spinSlow {{ from {{ transform: rotate(0deg); }} to {{ transform: rotate(360deg); }} }}
    .cursor {{ animation: blink 1.1s steps(1) infinite; }}
    .ring {{ transform-origin: 135px 190px; animation: spinSlow 45s linear infinite; }}
  </style>
  <rect x="1" y="1" width="918" height="388" rx="14" fill="{t['bg']}" stroke="{t['border']}" stroke-width="1.2"/>
  <path d="M 15 1 H 905 A 14 14 0 0 1 919 15 V 38 H 1 V 15 A 14 14 0 0 1 15 1 Z" fill="{t['surface']}"/>
  <line x1="1" y1="38" x2="919" y2="38" stroke="{t['border']}" stroke-width="1"/>
  <circle cx="22" cy="19.5" r="5.5" fill="#FF5F56"/>
  <circle cx="40" cy="19.5" r="5.5" fill="#FFBD2E"/>
  <circle cx="58" cy="19.5" r="5.5" fill="#27C93F"/>
  <text x="460" y="23.5" text-anchor="middle" class="chrome-title">sandeep@snowflake-sis: ~ (zsh)</text>
  <text x="900" y="23.5" text-anchor="end" class="meta">synced {esc(stats['updated_date'])}</text>
  <g>
    <circle cx="135" cy="190" r="88" fill="none" stroke="{t['border']}" stroke-width="1" stroke-dasharray="4 6" class="ring"/>
    <circle cx="135" cy="190" r="66" fill="{t['surface']}" stroke="{t['accent']}" stroke-width="1.5" opacity="0.9"/>
    <g transform="translate(135, 190)" stroke="{t['accent']}" stroke-width="2.8" stroke-linecap="round" fill="none">
      <line x1="0" y1="-44" x2="0" y2="44"/>
      <line x1="-38.1" y1="-22" x2="38.1" y2="22"/>
      <line x1="-38.1" y1="22" x2="38.1" y2="-22"/>
      <polyline points="-10,-32 0,-22 10,-32"/>
      <polyline points="-10,32 0,22 10,32"/>
      <polyline points="-32,-7 -19,-11 -22,-24"/>
      <polyline points="32,7 19,11 22,24"/>
      <polyline points="-32,7 -19,11 -22,24"/>
      <polyline points="32,-7 19,-11 22,-24"/>
      <polygon points="0,-11 9.5,-5.5 9.5,5.5 0,11 -9.5,5.5 -9.5,-5.5" fill="{t['bg']}" stroke="{t['accent2']}" stroke-width="2"/>
    </g>
    <g transform="translate(69, 305)">
      <rect x="0" y="0" width="18" height="10" rx="3" fill="{t['accent']}"/>
      <rect x="23" y="0" width="18" height="10" rx="3" fill="{t['accent2']}"/>
      <rect x="46" y="0" width="18" height="10" rx="3" fill="{t['accent3']}"/>
      <rect x="69" y="0" width="18" height="10" rx="3" fill="{t['warn']}"/>
      <rect x="92" y="0" width="18" height="10" rx="3" fill="{t['accent4']}"/>
      <rect x="115" y="0" width="18" height="10" rx="3" fill="{t['muted']}"/>
    </g>
    <text x="135" y="336" text-anchor="middle" class="meta">SANDEEP VISHNU // SEATTLE</text>
  </g>
  <line x1="252" y1="58" x2="252" y2="348" stroke="{t['border']}" stroke-width="1"/>
  <text x="275" y="72" class="header-user">sandeepkv93<tspan fill="{t['muted']}">@</tspan><tspan fill="{t['accent2']}">snowflake-data-cloud</tspan></text>
  <line x1="275" y1="82" x2="890" y2="82" stroke="{t['border']}" stroke-width="1"/>
{rows_svg}
  <line x1="275" y1="338" x2="890" y2="338" stroke="{t['border']}" stroke-width="1"/>
  <text x="275" y="364" class="prompt"><tspan fill="{t['accent3']}">&#10140;</tspan><tspan fill="{t['accent']}"> ~/systems </tspan><tspan fill="{t['muted']}">$</tspan><tspan fill="{t['text']}"> kubectl get pods -n telemetry --watch </tspan><tspan fill="{t['accent']}" class="cursor">&#9608;</tspan></text>
</svg>
"""
def render_stats_svg(mode: str, stats: dict[str, Any]) -> str:
    t = THEMES[mode]
    metrics = [
        ("Contributions (12m)", str(stats["contributions_yr"]), t["accent3"]),
        ("Public Repositories", str(stats["public_repos"]), t["accent"]),
        ("Pull Requests", str(stats["pull_requests"]), t["accent2"]),
        ("Stars Earned", str(stats["total_stars"]), t["warn"]),
        ("Followers", str(stats["followers"]), t["accent4"]),
    ]
    metric_rows = []
    my = 76
    for label, val, color in metrics:
        metric_rows.append(
            f'    <circle cx="38" cy="{my - 4}" r="4" fill="{color}"/>'
            f'    <text x="52" y="{my}" class="label">{esc(label)}</text>'
            f'    <text x="415" y="{my}" text-anchor="end" class="val" fill="{color}">{esc(val)}</text>'
        )
        my += 28
    bar_x, bar_y, bar_w, bar_h = 485, 66, 395, 12
    segs = []
    curr_x = bar_x
    langs = stats["top_langs"]
    total_pct = sum(l["pct"] for l in langs) or 100.0
    for i, lang in enumerate(langs):
        seg_w = (lang["pct"] / total_pct) * bar_w
        if i == len(langs) - 1:
            seg_w = (bar_x + bar_w) - curr_x
        segs.append(f'      <rect x="{curr_x:.1f}" y="{bar_y}" width="{max(seg_w, 2):.1f}" height="{bar_h}" fill="{lang["color"]}"/>')
        curr_x += seg_w
    lang_rows = []
    ly = 106
    for lang in langs:
        lw = max(8, (lang["pct"] / 100.0) * 195)
        lang_rows.append(
            f'    <circle cx="491" cy="{ly - 4}" r="4.5" fill="{lang["color"]}"/>'
            f'    <text x="504" y="{ly}" class="label">{esc(lang["name"])}</text>'
            f'    <rect x="615" y="{ly - 10}" width="195" height="8" rx="4" fill="{t["bar_bg"]}"/>'
            f'    <rect x="615" y="{ly - 10}" width="{lw:.1f}" height="8" rx="4" fill="{lang["color"]}"/>'
            f'    <text x="880" y="{ly}" text-anchor="end" class="pct">{lang["pct"]:.1f}%</text>'
        )
        ly += 24
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 920 226" width="920" height="226" role="img" aria-label="Sandeep Vishnu GitHub Activity and Top Languages">
  <defs>
    <clipPath id="langBarClip-{mode}">
      <rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="6"/>
    </clipPath>
  </defs>
  <style>
    .sec-title {{ font: 700 14px -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; fill: {t['text']}; }}
    .label {{ font: 500 13px -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; fill: {t['muted']}; }}
    .val {{ font: 700 14px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
    .pct {{ font: 600 12.5px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; fill: {t['text']}; }}
    .foot {{ font: 500 10.5px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; fill: {t['subtle']}; }}
  </style>
  <rect x="1" y="1" width="446" height="224" rx="14" fill="{t['surface']}" stroke="{t['border']}" stroke-width="1.2"/>
  <text x="28" y="34" class="sec-title">GitHub Telemetry</text>
  <text x="415" y="34" text-anchor="end" class="foot">AUTO-SYNCED DAILY</text>
  <line x1="28" y1="48" x2="418" y2="48" stroke="{t['border']}" stroke-width="1"/>
{chr(10).join(metric_rows)}
  <rect x="462" y="1" width="457" height="224" rx="14" fill="{t['surface']}" stroke="{t['border']}" stroke-width="1.2"/>
  <text x="485" y="34" class="sec-title">Top Languages (Public Repos)</text>
  <text x="880" y="34" text-anchor="end" class="foot">OWNED CODEBASES</text>
  <line x1="485" y1="48" x2="880" y2="48" stroke="{t['border']}" stroke-width="1"/>
  <g clip-path="url(#langBarClip-{mode})">
    <rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" fill="{t['bar_bg']}"/>
{chr(10).join(segs)}
  </g>
{chr(10).join(lang_rows)}
</svg>
"""
def render_footer_svg(mode: str) -> str:
    t = THEMES[mode]
    grad_start = "#161B22" if mode == "dark" else "#DCEBFA"
    grad_mid = t["accent"]
    grad_end = "#6E40C9" if mode == "dark" else t["accent4"]
    back_op = "0.24" if mode == "dark" else "0.18"
    mid_op = "0.45" if mode == "dark" else "0.34"
    front_op = "0.92" if mode == "dark" else "0.84"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 920 100" width="920" height="100" role="img" aria-label="Footer Wave">
  <defs>
    <linearGradient id="footerGrad-{mode}" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{grad_start}"/>
      <stop offset="52%" stop-color="{grad_mid}"/>
      <stop offset="100%" stop-color="{grad_end}"/>
    </linearGradient>
    <linearGradient id="footerGradRev-{mode}" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{grad_end}"/>
      <stop offset="50%" stop-color="{t['accent2']}"/>
      <stop offset="100%" stop-color="{grad_mid}"/>
    </linearGradient>
    <clipPath id="footerClip-{mode}">
      <path d="M 0 0 H 920 V 86 A 14 14 0 0 1 906 100 H 14 A 14 14 0 0 1 0 86 Z"/>
    </clipPath>
  </defs>
  <style>
    @keyframes waveBreath {{ 0%, 100% {{ opacity: {back_op}; }} 50% {{ opacity: {mid_op}; }} }}
    .wave-back {{ animation: waveBreath 6s ease-in-out infinite; }}
  </style>
  <g clip-path="url(#footerClip-{mode})">
    <path d="M 0 42 C 180 12, 340 72, 540 38 C 700 10, 820 56, 920 30 L 920 100 L 0 100 Z" fill="url(#footerGradRev-{mode})" opacity="{back_op}" class="wave-back"/>
    <path d="M 0 56 C 210 24, 390 82, 600 46 C 750 20, 840 62, 920 44 L 920 100 L 0 100 Z" fill="url(#footerGrad-{mode})" opacity="{mid_op}"/>
    <path d="M 0 68 C 190 40, 360 90, 560 58 C 720 34, 830 76, 920 56 L 920 100 L 0 100 Z" fill="url(#footerGrad-{mode})" opacity="{front_op}"/>
  </g>
</svg>
"""
def main() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    stats = fetch_github_stats()
    for mode in ("dark", "light"):
        for name, content in (
            (f"banner-{mode}.svg", render_banner_svg(mode)),
            (f"terminal-{mode}.svg", render_terminal_svg(mode, stats)),
            (f"stats-{mode}.svg", render_stats_svg(mode, stats)),
            (f"footer-{mode}.svg", render_footer_svg(mode)),
        ):
            (ASSETS_DIR / name).write_text(content, encoding="utf-8")
    print(f"Generated 8 SVGs in {ASSETS_DIR}")
if __name__ == "__main__":
    main()
