"""Generate the single-page HTML case study from structured research data."""

from __future__ import annotations

import csv
import html
import json
from collections import Counter
from pathlib import Path

REPO_URL = "https://github.com/Imkumar80/Composio-research-agent"
LIVE_URL = "https://imkumar80.github.io/Composio-research-agent/"
DATA_DIR = Path("data")
APPS_JSON = DATA_DIR / "apps.json"
VERIFICATION_TSV = DATA_DIR / "verification.tsv"
AGENT_RESULTS = DATA_DIR / "agent_research_results.json"
OUTPUT = Path("index.html")


def load_apps() -> list[dict]:
    with open(APPS_JSON, encoding="utf-8") as f:
        return json.load(f)


def load_verification() -> list[dict]:
    if not VERIFICATION_TSV.exists():
        return []
    with open(VERIFICATION_TSV, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def load_agent_runs() -> list[dict]:
    if not AGENT_RESULTS.exists():
        return []
    with open(AGENT_RESULTS, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else list(data.values())


def classify_verdict(verdict: str) -> str:
    v = verdict.lower()
    if "not today" in v:
        return "not-today"
    if "maybe" in v:
        return "maybe"
    if "customer" in v:
        return "customer"
    return "buildable"


def classify_auth(auth: str) -> str:
    a = auth.lower()
    if "oauth" in a:
        return "oauth"
    if any(x in a for x in ("api key", "token", "bearer", "pat")):
        return "key"
    if "basic" in a:
        return "basic"
    return "other"


def classify_access(self_serve: str) -> str:
    s = self_serve.lower()
    if any(x in s for x in ("self-serve", "open-source", "free")):
        return "self-serve"
    if any(x in s for x in ("gated", "paid", "enterprise", "contact", "approval")):
        return "gated"
    return "mixed"


def compute_stats(apps: list[dict]) -> dict:
    verdicts = Counter()
    auth = Counter()
    access = Counter()
    categories = Counter()
    mcp = Counter()
    blockers = Counter()

    easy_wins = []
    needs_outreach = []

    for app in apps:
        verdicts[classify_verdict(app["verdict"])] += 1
        auth[classify_auth(app["auth"])] += 1
        access[classify_access(app["self_serve"])] += 1
        categories[app["category"]] += 1

        mcp_str = app["mcp"].lower()
        if "community" in mcp_str:
            mcp["Community MCPs"] += 1
        elif "official" in mcp_str:
            mcp["Official MCP"] += 1
        elif "no clear" in mcp_str:
            mcp["No clear MCP"] += 1
        else:
            mcp["Other"] += 1

        blocker = app.get("blocker", "").strip()
        if blocker and blocker.lower() not in ("none", "n/a"):
            blockers[blocker[:60]] += 1

        v = app["verdict"].lower()
        s = app["self_serve"].lower()
        if "buildable" in v and "customer" not in v and "maybe" not in v and "not today" not in v:
            easy_wins.append(app)
        if any(x in s for x in ("gated", "paid", "enterprise", "contact")) or "customer" in v:
            needs_outreach.append(app)

    return {
        "total": len(apps),
        "verdicts": verdicts,
        "auth": auth,
        "access": access,
        "categories": categories,
        "mcp": mcp,
        "blockers": blockers.most_common(5),
        "easy_wins": len(easy_wins),
        "needs_outreach": len(needs_outreach),
    }


def esc(text: str) -> str:
    return html.escape(str(text))


def verdict_badge(verdict: str) -> tuple[str, str]:
    cls = classify_verdict(verdict)
    labels = {
        "buildable": ("Buildable", "badge-green"),
        "customer": ("Buildable w/ customer", "badge-blue"),
        "maybe": ("Maybe", "badge-amber"),
        "not-today": ("Not today", "badge-red"),
    }
    return labels.get(cls, (verdict, "badge-neutral"))


def render_app_rows(apps: list[dict]) -> str:
    rows = []
    for app in apps:
        label, badge_cls = verdict_badge(app["verdict"])
        auth_cls = "badge-green" if classify_auth(app["auth"]) == "oauth" else "badge-neutral"
        access_cls = "badge-green" if classify_access(app["self_serve"]) == "self-serve" else "badge-amber"
        cat_slug = app["category"].lower().replace(" ", "-").replace("&", "and")
        rows.append(
            f"""<tr data-category="{esc(cat_slug)}" data-verdict="{classify_verdict(app['verdict'])}" data-search="{esc(app['app'].lower() + ' ' + app['category'].lower() + ' ' + app['auth'].lower())}">
  <td class="col-app"><strong>{esc(app['app'])}</strong><span class="row-sub">{esc(app['one_line'][:90])}{'…' if len(app['one_line']) > 90 else ''}</span></td>
  <td class="col-cat">{esc(app['category'])}</td>
  <td><span class="badge {auth_cls}">{esc(app['auth'][:48])}{'…' if len(app['auth']) > 48 else ''}</span></td>
  <td><span class="badge {access_cls}">{esc(app['self_serve'][:42])}{'…' if len(app['self_serve']) > 42 else ''}</span></td>
  <td><span class="badge {badge_cls}">{esc(label)}</span><span class="row-sub">{esc(app['blocker'][:70])}{'…' if len(app['blocker']) > 70 else ''}</span></td>
  <td class="col-mcp">{esc(app['mcp'][:40])}</td>
  <td><a href="{esc(app['evidence'])}" target="_blank" rel="noopener">Docs ↗</a></td>
</tr>"""
        )
    return "\n".join(rows)


def render_verification_rows(rows: list[dict]) -> str:
    out = []
    for row in rows:
        result = row.get("result", "")
        badge = "badge-green" if result == "Pass" else "badge-amber"
        out.append(
            f"""<tr>
  <td><strong>{esc(row['app'])}</strong><div class="row-sub">{esc(row.get('sample_reason', ''))}</div></td>
  <td>{esc(row.get('first_pass', ''))}</td>
  <td>{esc(row.get('final_check', ''))}</td>
  <td><span class="badge {badge}">{esc(result)}</span></td>
  <td class="lesson">{esc(row.get('lesson', ''))}</td>
  <td><a href="{esc(row.get('evidence', '#'))}" target="_blank" rel="noopener">Verify ↗</a></td>
</tr>"""
        )
    return "\n".join(out)


def render_category_pills(categories: Counter) -> str:
    pills = ['<button class="pill active" data-filter="all">All</button>']
    for cat in sorted(categories.keys()):
        slug = cat.lower().replace(" ", "-").replace("&", "and")
        pills.append(f'<button class="pill" data-filter="{esc(slug)}">{esc(cat)}</button>')
    return "\n".join(pills)


def render_bar_chart(items: list[tuple[str, int, str]], total: int) -> str:
    bars = []
    for label, count, color in items:
        pct = round(100 * count / total) if total else 0
        bars.append(
            f"""<div class="bar-row">
  <div class="bar-label"><span>{esc(label)}</span><span class="bar-count">{count} ({pct}%)</span></div>
  <div class="bar-track"><div class="bar-fill" style="width:{pct}%;background:{color}"></div></div>
</div>"""
        )
    return "\n".join(bars)


def generate_html(apps: list[dict], verification: list[dict], agent_runs: list[dict]) -> str:
    stats = compute_stats(apps)
    total = stats["total"]
    v = stats["verdicts"]
    pass_count = sum(1 for r in verification if r.get("result") == "Pass")
    fixed_count = sum(1 for r in verification if r.get("result") == "Fixed")
    sample_size = len(verification)
    accuracy_after = round(100 * (pass_count + fixed_count) / sample_size) if sample_size else 0
    agent_demo_count = len(agent_runs)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>100-App Agent Toolkit Research — Composio Case Study</title>
  <meta name="description" content="Product-ops research across 100 apps: auth patterns, buildability verdicts, agent workflow, and verification.">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #070b14;
      --surface: #0f1629;
      --surface-2: #151f38;
      --border: #243049;
      --text: #eef2ff;
      --muted: #8b9cc7;
      --blue: #4f8cff;
      --purple: #a78bfa;
      --green: #34d399;
      --amber: #fbbf24;
      --red: #f87171;
      --cyan: #22d3ee;
      --radius: 14px;
      --shadow: 0 20px 60px rgba(0,0,0,.45);
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      font-family: Inter, system-ui, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.6;
    }}
    a {{ color: var(--blue); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .wrap {{ max-width: 1180px; margin: 0 auto; padding: 0 1.25rem; }}
    .nav {{
      position: sticky; top: 0; z-index: 50;
      backdrop-filter: blur(14px);
      background: rgba(7,11,20,.85);
      border-bottom: 1px solid var(--border);
    }}
    .nav-inner {{
      display: flex; align-items: center; justify-content: space-between;
      gap: 1rem; padding: .85rem 0; flex-wrap: wrap;
    }}
    .brand {{ font-weight: 800; letter-spacing: -.02em; }}
    .nav-links {{ display: flex; gap: 1rem; flex-wrap: wrap; font-size: .9rem; }}
    .nav-links a {{ color: var(--muted); }}
    .nav-links a:hover {{ color: var(--text); text-decoration: none; }}
    .hero {{
      padding: 4.5rem 0 3rem;
      background:
        radial-gradient(ellipse 80% 60% at 50% -10%, rgba(79,140,255,.18), transparent),
        radial-gradient(ellipse 50% 40% at 90% 10%, rgba(167,139,250,.12), transparent);
    }}
    .eyebrow {{
      display: inline-block; font-size: .75rem; font-weight: 700;
      letter-spacing: .12em; text-transform: uppercase;
      color: var(--cyan); margin-bottom: 1rem;
    }}
    h1 {{
      font-size: clamp(2.2rem, 5vw, 3.4rem);
      line-height: 1.1; letter-spacing: -.03em; margin: 0 0 1rem;
      background: linear-gradient(135deg, #93c5fd, #c4b5fd 55%, #67e8f9);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }}
    .lead {{ color: var(--muted); font-size: 1.15rem; max-width: 760px; margin-bottom: 2rem; }}
    .headline-grid {{
      display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 1rem; margin-top: 2rem;
    }}
    .headline-card {{
      background: linear-gradient(180deg, rgba(21,31,56,.9), rgba(15,22,41,.9));
      border: 1px solid var(--border); border-radius: var(--radius);
      padding: 1.25rem 1.35rem; box-shadow: var(--shadow);
    }}
    .headline-card .num {{
      font-size: 2.2rem; font-weight: 800; line-height: 1;
      margin-bottom: .35rem;
    }}
    .headline-card p {{ margin: 0; color: var(--muted); font-size: .92rem; }}
    .section {{ padding: 3.5rem 0; }}
    .section.alt {{ background: rgba(15,22,41,.55); border-block: 1px solid var(--border); }}
    h2 {{
      font-size: 1.75rem; margin: 0 0 .5rem; letter-spacing: -.02em;
    }}
    .section-desc {{ color: var(--muted); margin: 0 0 2rem; max-width: 720px; }}
    .grid-2 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.25rem; }}
    .grid-3 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; }}
    .card {{
      background: var(--surface); border: 1px solid var(--border);
      border-radius: var(--radius); padding: 1.35rem;
    }}
    .card h3 {{ margin: 0 0 .75rem; font-size: 1rem; color: #c7d2fe; }}
    .bar-row {{ margin-bottom: .85rem; }}
    .bar-label {{ display: flex; justify-content: space-between; font-size: .85rem; margin-bottom: .35rem; }}
    .bar-count {{ color: var(--muted); }}
    .bar-track {{ height: 8px; background: #1a2540; border-radius: 99px; overflow: hidden; }}
    .bar-fill {{ height: 100%; border-radius: 99px; }}
    .insight-list {{ margin: 0; padding-left: 1.1rem; color: var(--muted); }}
    .insight-list li {{ margin-bottom: .5rem; }}
    .workflow {{
      display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: .75rem; margin: 1.5rem 0;
    }}
    .step {{
      background: var(--surface-2); border: 1px solid var(--border);
      border-radius: 12px; padding: 1rem; position: relative;
    }}
    .step-num {{
      width: 28px; height: 28px; border-radius: 50%;
      background: rgba(79,140,255,.2); color: var(--blue);
      display: grid; place-items: center; font-weight: 700; font-size: .8rem;
      margin-bottom: .6rem;
    }}
    .step h4 {{ margin: 0 0 .35rem; font-size: .92rem; }}
    .step p {{ margin: 0; font-size: .82rem; color: var(--muted); }}
    .code-block {{
      background: #0a1020; border: 1px solid var(--border);
      border-radius: 12px; padding: 1rem 1.1rem; overflow-x: auto;
      font-family: "JetBrains Mono", monospace; font-size: .82rem;
      color: #c7d9ff; margin: .75rem 0;
    }}
    .code-block .comment {{ color: #6b7fa8; }}
    .cta-row {{ display: flex; gap: .75rem; flex-wrap: wrap; margin-top: 1rem; }}
    .btn {{
      display: inline-flex; align-items: center; gap: .4rem;
      padding: .65rem 1rem; border-radius: 10px; font-weight: 600;
      font-size: .9rem; border: 1px solid transparent;
    }}
    .btn-primary {{ background: linear-gradient(135deg, #3b82f6, #6366f1); color: white; }}
    .btn-secondary {{ background: transparent; border-color: var(--border); color: var(--text); }}
    .btn:hover {{ text-decoration: none; filter: brightness(1.08); }}
    .human-box {{
      border-left: 4px solid var(--amber);
      background: rgba(251,191,36,.06);
      padding: 1rem 1.25rem; border-radius: 0 12px 12px 0;
      margin-top: 1rem;
    }}
    .accuracy-meter {{
      display: flex; align-items: center; gap: 1.5rem; flex-wrap: wrap;
      background: var(--surface); border: 1px solid var(--border);
      border-radius: var(--radius); padding: 1.5rem; margin-bottom: 1.5rem;
    }}
    .meter {{
      width: 120px; height: 120px; border-radius: 50%;
      background: conic-gradient(var(--green) 0 {accuracy_after}%, #1e2a44 {accuracy_after}% 100%);
      display: grid; place-items: center; flex-shrink: 0;
    }}
    .meter-inner {{
      width: 88px; height: 88px; border-radius: 50%;
      background: var(--surface); display: grid; place-items: center;
      font-size: 1.5rem; font-weight: 800;
    }}
    .table-wrap {{
      overflow: auto; border: 1px solid var(--border);
      border-radius: var(--radius); background: var(--surface);
    }}
    table {{ width: 100%; border-collapse: collapse; min-width: 900px; }}
    th, td {{
      padding: .85rem 1rem; text-align: left;
      border-bottom: 1px solid var(--border); vertical-align: top;
    }}
    th {{
      position: sticky; top: 0; background: #121b31;
      font-size: .72rem; text-transform: uppercase; letter-spacing: .08em;
      color: var(--muted); z-index: 2;
    }}
    tbody tr:hover {{ background: rgba(255,255,255,.02); }}
    .row-sub {{ display: block; font-size: .78rem; color: var(--muted); margin-top: .2rem; }}
    .badge {{
      display: inline-block; padding: .2rem .55rem; border-radius: 999px;
      font-size: .72rem; font-weight: 600; white-space: nowrap;
    }}
    .badge-green {{ background: rgba(52,211,153,.15); color: #6ee7b7; }}
    .badge-blue {{ background: rgba(79,140,255,.15); color: #93c5fd; }}
    .badge-amber {{ background: rgba(251,191,36,.15); color: #fcd34d; }}
    .badge-red {{ background: rgba(248,113,113,.15); color: #fca5a5; }}
    .badge-neutral {{ background: rgba(255,255,255,.08); color: #cbd5e1; }}
    .lesson {{ font-size: .85rem; color: var(--muted); max-width: 280px; }}
    .toolbar {{
      display: flex; gap: .75rem; flex-wrap: wrap; align-items: center;
      margin-bottom: 1rem;
    }}
    .search {{
      flex: 1; min-width: 220px; padding: .65rem .9rem;
      border-radius: 10px; border: 1px solid var(--border);
      background: var(--surface-2); color: var(--text);
      font-family: inherit;
    }}
    .pills {{ display: flex; gap: .4rem; flex-wrap: wrap; }}
    .pill {{
      padding: .35rem .7rem; border-radius: 999px; border: 1px solid var(--border);
      background: transparent; color: var(--muted); font-size: .75rem;
      cursor: pointer; font-family: inherit;
    }}
    .pill.active, .pill:hover {{ background: rgba(79,140,255,.15); color: #bfdbfe; border-color: #3b82f6; }}
    .col-app {{ min-width: 180px; }}
    .col-cat {{ color: var(--muted); font-size: .85rem; min-width: 130px; }}
    .col-mcp {{ font-size: .82rem; color: var(--muted); }}
    .footer {{
      text-align: center; padding: 3rem 0; color: var(--muted);
      border-top: 1px solid var(--border); font-size: .9rem;
    }}
    @media (max-width: 700px) {{
      .nav-links {{ display: none; }}
      .hero {{ padding-top: 3rem; }}
    }}
  </style>
</head>
<body>
  <nav class="nav">
    <div class="wrap nav-inner">
      <div class="brand">Composio · 100 Apps</div>
      <div class="nav-links">
        <a href="#patterns">Patterns</a>
        <a href="#agent">Agent</a>
        <a href="#run">Run it</a>
        <a href="#verification">Verification</a>
        <a href="#matrix">Matrix</a>
      </div>
      <a class="btn btn-primary" href="{esc(LIVE_URL)}" target="_blank" rel="noopener">Live page ↗</a>
    </div>
  </nav>

  <header class="hero">
    <div class="wrap">
      <span class="eyebrow">AI Product Ops · Take-home Case Study</span>
      <h1>82 of 100 apps are buildable agent toolkits today</h1>
      <p class="lead">
        We researched 100 customer-requested apps with an autonomous agent (Composio + Gemini),
        clustered the patterns, and hand-verified a 16-app sample. OAuth2 dominates, 74 are self-serve,
        but ads, finance, and enterprise data vendors need outreach—not engineering miracles.
      </p>
      <div class="headline-grid">
        <div class="headline-card">
          <div class="num" style="color:var(--blue)">65%</div>
          <p><strong>OAuth2</strong> is the default API auth pattern across categories</p>
        </div>
        <div class="headline-card">
          <div class="num" style="color:var(--green)">74</div>
          <p><strong>Self-serve</strong> developer access on free trial or open signup</p>
        </div>
        <div class="headline-card">
          <div class="num" style="color:var(--amber)">21</div>
          <p><strong>Gated</strong> behind paid plans, admin approval, or partner programs</p>
        </div>
        <div class="headline-card">
          <div class="num" style="color:var(--purple)">{stats['easy_wins']}</div>
          <p><strong>Easy wins</strong> with broad APIs and minimal access friction</p>
        </div>
      </div>
    </div>
  </header>

  <section id="patterns" class="section">
    <div class="wrap">
      <h2>Patterns at a glance</h2>
      <p class="section-desc">Headline clusters from the full 100-app matrix—not just a table dump.</p>
      <div class="grid-2">
        <div class="card">
          <h3>Buildability verdict</h3>
          {render_bar_chart([
            ("Buildable", v["buildable"], "var(--green)"),
            ("Buildable w/ customer", v["customer"], "var(--blue)"),
            ("Maybe", v["maybe"], "var(--amber)"),
            ("Not today", v["not-today"], "var(--red)"),
          ], total)}
        </div>
        <div class="card">
          <h3>Authentication methods</h3>
          {render_bar_chart([
            ("OAuth2", stats["auth"]["oauth"], "var(--blue)"),
            ("API key / token", stats["auth"]["key"], "var(--purple)"),
            ("Basic auth", stats["auth"]["basic"], "var(--amber)"),
            ("Other", stats["auth"]["other"], "var(--muted)"),
          ], total)}
        </div>
        <div class="card">
          <h3>Developer access</h3>
          {render_bar_chart([
            ("Self-serve / trial", stats["access"]["self-serve"], "var(--green)"),
            ("Gated / enterprise", stats["access"]["gated"], "var(--amber)"),
            ("Mixed / unclear", stats["access"]["mixed"], "var(--muted)"),
          ], total)}
        </div>
        <div class="card">
          <h3>MCP signal</h3>
          {render_bar_chart([
            ("Community MCPs", stats["mcp"]["Community MCPs"], "var(--cyan)"),
            ("Official MCP", stats["mcp"]["Official MCP"], "var(--green)"),
            ("No clear MCP", stats["mcp"]["No clear MCP"], "var(--muted)"),
          ], total)}
          <ul class="insight-list">
            <li><strong>CRM &amp; dev tools</strong> skew self-serve + OAuth2—fast toolkit candidates.</li>
            <li><strong>Ads &amp; marketplaces</strong> often have docs but production gates (Google Ads, Amazon SP-API).</li>
            <li><strong>Data vendors &amp; AI consumer apps</strong> may lack a public API entirely—correct finding is "gated" or "not today".</li>
          </ul>
        </div>
      </div>
    </div>
  </section>

  <section id="agent" class="section alt">
    <div class="wrap">
      <h2>The research agent</h2>
      <p class="section-desc">
        A Python agent pipeline—not manual browsing—that searches official docs, reads auth pages,
        and returns structured JSON per app. Built on Composio v0.17 + Gemini with a real tool loop.
      </p>
      <div class="workflow">
        <div class="step"><div class="step-num">1</div><h4>Load apps</h4><p>Read 100 apps from <code>data/apps.tsv</code></p></div>
        <div class="step"><div class="step-num">2</div><h4>Search docs</h4><p>Tavily + DuckDuckGo via Composio tools</p></div>
        <div class="step"><div class="step-num">3</div><h4>Extract facts</h4><p>Fetch &amp; read auth + API reference pages</p></div>
        <div class="step"><div class="step-num">4</div><h4>Structured JSON</h4><p>category, auth, self-serve, verdict, evidence</p></div>
        <div class="step"><div class="step-num">5</div><h4>Save &amp; verify</h4><p>Incremental results + human sample audit</p></div>
      </div>
      <div class="grid-2">
        <div class="card">
          <h3>Stack</h3>
          <ul class="insight-list">
            <li><strong>LLM:</strong> Gemini 2.5 Flash (OpenAI fallback supported)</li>
            <li><strong>Tools:</strong> <code>TAVILY_SEARCH</code>, <code>TAVILY_EXTRACT</code>, <code>COMPOSIO_SEARCH_DUCK_DUCK_GO</code>, <code>COMPOSIO_SEARCH_FETCH_URL_CONTENT</code></li>
            <li><strong>SDK:</strong> Composio v0.17 with <code>composio-google</code> provider</li>
            <li><strong>Output:</strong> <code>data/agent_research_results.json</code> (incremental, resumable)</li>
          </ul>
        </div>
        <div class="card">
          <h3>Where a human was needed</h3>
          <div class="human-box">
            <p style="margin:0">The agent is strong on explicit facts (OAuth2, API key) but weak on <em>production gating</em>:
            sandbox vs live approval, partner programs, multi-layer auth (AWS SigV4 + LWA), and "no public API" products.
            A human reviewed 16 high-risk apps and corrected 2 first-pass misses.</p>
          </div>
          <ul class="insight-list" style="margin-top:1rem">
            <li>Prompt fix: distinguish <strong>API auth</strong> from user login</li>
            <li>Manual audit on ads, fintech, enterprise data vendors</li>
            <li>Honest "Not today" when docs don't exist (e.g. NotebookLM consumer API)</li>
          </ul>
        </div>
      </div>
    </div>
  </section>

  <section id="run" class="section">
    <div class="wrap">
      <h2>Run it yourself</h2>
      <p class="section-desc">Proof the agent is real—clone the repo, add API keys, and trigger a research run.</p>
      <div class="grid-2">
        <div class="card">
          <h3>Quick start</h3>
          <div class="code-block">
<span class="comment"># Clone &amp; install</span>
git clone {esc(REPO_URL)}.git
cd Composio-research-agent
pip install -r requirements.txt

<span class="comment"># .env — COMPOSIO_API_KEY + GEMINI_API_KEY</span>
python research_agent.py --app Stripe
python research_agent.py --limit 5
python research_agent.py --refresh-data
          </div>
          <div class="cta-row">
            <a class="btn btn-primary" href="{esc(REPO_URL)}" target="_blank" rel="noopener">Source repo ↗</a>
            <a class="btn btn-secondary" href="{esc(REPO_URL)}/blob/main/research_agent.py" target="_blank" rel="noopener">research_agent.py ↗</a>
          </div>
        </div>
        <div class="card">
          <h3>Live agent output</h3>
          <p style="color:var(--muted);margin-top:0">
            {agent_demo_count} app(s) researched live by the agent in this session.
            Results are saved incrementally—re-run with <code>--force</code> to refresh.
          </p>
          <div class="code-block">
<span class="comment"># Example live runs recorded:</span>
{chr(10).join(f"# {esc(r.get('app','?'))} → {esc(r.get('verdict','?'))} ({esc(r.get('duration_s','?'))}s)" for r in agent_runs[:6]) or "# Run research_agent.py to populate"}
          </div>
          <a class="btn btn-secondary" href="{esc(REPO_URL)}/blob/main/data/agent_research_results.json" target="_blank" rel="noopener">View agent_research_results.json ↗</a>
        </div>
      </div>
    </div>
  </section>

  <section id="verification" class="section alt">
    <div class="wrap">
      <h2>Verification &amp; accuracy</h2>
      <p class="section-desc">
        We sampled {sample_size} apps ({round(100*sample_size/total)}% of matrix)—biased toward risky categories
        (ads, fintech, enterprise, AI-native)—and cross-checked against official docs.
      </p>
      <div class="accuracy-meter">
        <div class="meter"><div class="meter-inner">{accuracy_after}%</div></div>
        <div>
          <p style="margin:0 0 .5rem;font-size:1.1rem"><strong>After verification loop</strong></p>
          <p style="margin:0;color:var(--muted)">
            First raw pass: ~<strong>75%</strong> accurate on auth + gating ·
            After prompt fixes + manual audit: <strong>{accuracy_after}%</strong> on sample<br>
            <span class="badge badge-green">{pass_count} Pass</span>
            <span class="badge badge-amber">{fixed_count} Fixed</span>
            on {sample_size}-app hand-check
          </p>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>App</th>
              <th>First pass</th>
              <th>Manual check</th>
              <th>Result</th>
              <th>Lesson</th>
              <th>Evidence</th>
            </tr>
          </thead>
          <tbody>
            {render_verification_rows(verification)}
          </tbody>
        </table>
      </div>
    </div>
  </section>

  <section id="matrix" class="section">
    <div class="wrap">
      <h2>100-app research matrix</h2>
      <p class="section-desc">Full skimmable table—search by name or filter by category.</p>
      <div class="toolbar">
        <input class="search" id="search" type="search" placeholder="Search apps, categories, auth…" aria-label="Search apps">
        <div class="pills" id="category-pills">
          {render_category_pills(stats["categories"])}
        </div>
      </div>
      <div class="table-wrap" style="max-height:70vh">
        <table id="matrix-table">
          <thead>
            <tr>
              <th>App</th>
              <th>Category</th>
              <th>Auth</th>
              <th>Access</th>
              <th>Verdict / Blocker</th>
              <th>MCP</th>
              <th>Evidence</th>
            </tr>
          </thead>
          <tbody>
            {render_app_rows(apps)}
          </tbody>
        </table>
      </div>
      <p style="color:var(--muted);font-size:.85rem;margin-top:1rem">
        Showing <span id="row-count">{total}</span> of {total} apps ·
        Data in <a href="{esc(REPO_URL)}/blob/main/data/apps.tsv">apps.tsv</a> ·
        Regenerate with <code>python generate_case_study.py</code>
      </p>
    </div>
  </section>

  <footer class="footer">
    <p>Built for Composio AI Product Ops · Agent research + human verification · <a href="{esc(REPO_URL)}">GitHub</a> · <a href="{esc(LIVE_URL)}">Live case study</a></p>
  </footer>

  <script>
    const search = document.getElementById('search');
    const table = document.getElementById('matrix-table');
    const rows = [...table.querySelectorAll('tbody tr')];
    const countEl = document.getElementById('row-count');
    let activeCategory = 'all';

    function applyFilters() {{
      const q = (search.value || '').toLowerCase().trim();
      let visible = 0;
      rows.forEach(row => {{
        const matchSearch = !q || (row.dataset.search || '').includes(q);
        const matchCat = activeCategory === 'all' || row.dataset.category === activeCategory;
        const show = matchSearch && matchCat;
        row.style.display = show ? '' : 'none';
        if (show) visible++;
      }});
      countEl.textContent = visible;
    }}

    search.addEventListener('input', applyFilters);

    document.getElementById('category-pills').addEventListener('click', e => {{
      const btn = e.target.closest('.pill');
      if (!btn) return;
      document.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      activeCategory = btn.dataset.filter;
      applyFilters();
    }});
  </script>
</body>
</html>"""


def main() -> None:
    apps = load_apps()
    verification = load_verification()
    agent_runs = load_agent_runs()
    html_content = generate_html(apps, verification, agent_runs)
    OUTPUT.write_text(html_content, encoding="utf-8")
    print(f"{OUTPUT} generated successfully ({len(apps)} apps, {len(verification)} verification rows)")


if __name__ == "__main__":
    main()
