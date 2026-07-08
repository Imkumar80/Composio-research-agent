# Composio 100-App Toolkit Research

This repo is a take-home assignment artifact for mapping whether 100 requested apps can become Composio-style agent toolkits.

## Deliverable

- **Live case study:** [imkumar80.github.io/Composio-research-agent](https://imkumar80.github.io/Composio-research-agent/)
- `index.html` — single-page case study (patterns, agent, verification, 100-app matrix)
- `data/apps.tsv` — full research matrix
- `data/verification.tsv` — hand-check sample with hits and misses
- `research_agent.py` — runnable Composio + Gemini research agent

## Deploy the case study

Pushes to `main` auto-deploy via GitHub Actions (`.github/workflows/pages.yml`).

Manual deploy:

```bash
python generate_case_study.py
git add index.html
git commit -m "Update case study"
git push
```

Then enable **GitHub Pages → Source: GitHub Actions** in repo settings (one-time).

## Run

```bash
pip install -r requirements.txt
```

Set these in `.env`:

```txt
COMPOSIO_API_KEY=your_composio_key
GEMINI_API_KEY=your_gemini_key   # preferred
# OPENAI_API_KEY=your_openai_key # optional fallback
```

Research apps (reads from `data/apps.tsv`):

```bash
# Research one app (quick test)
python research_agent.py --app Stripe

# Research first 5 apps
python research_agent.py --limit 5

# Research all 100, merge into apps.json, regenerate HTML
python research_agent.py --refresh-data

# Force re-research and use OpenAI instead of Gemini
python research_agent.py --app HubSpot --force --provider openai
```

Results are saved incrementally to `data/agent_research_results.json`.
Regenerate the case study page with `python generate_case_study.py` (also runs automatically at the end of each research run).

## Research Agent Workflow

1. Seed the 100 apps from the prompt and normalize category/app names.
2. Attach official docs or product URLs as evidence.
3. Classify auth, self-serve/gated status, API breadth, MCP signal, and buildability.
4. Risk-rank rows where model guesses are most likely to fail: ads APIs, finance APIs, enterprise data vendors, marketplace APIs, and obscure AI/media tools.
5. Hand-check a sample against docs and update rows where the first pass was incomplete or too optimistic.
6. Regenerate the static HTML page.

## Honesty Notes

Rows marked `Maybe` or `Not today` are not engineering failures. They are product-ops routing decisions: some apps need partner access, paid/admin credentials, customer-provided docs, or outreach before toolkit work is worth starting.
