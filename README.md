# Composio 100-App Toolkit Research

Research whether 100 customer-requested apps can become Composio-style agent toolkits.

**Live case study:** [imkumar80.github.io/Composio-research-agent](https://imkumar80.github.io/Composio-research-agent/)

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file:

```txt
COMPOSIO_API_KEY=your_composio_key
GEMINI_API_KEY=your_gemini_key   # preferred
# OPENAI_API_KEY=your_openai_key # optional fallback
```

## How to run

Research apps from `data/apps.tsv`:

```bash
# Quick test — one app
python research_agent.py --app Stripe

# First 5 apps
python research_agent.py --limit 5

# All 100 apps, merge into apps.json, regenerate index.html
python research_agent.py --refresh-data

# Re-research with OpenAI instead of Gemini
python research_agent.py --app HubSpot --force --provider openai
```

Regenerate the case study page only:

```bash
python generate_case_study.py
```

Results are saved incrementally to `data/agent_research_results.json`.

## Repo contents

- `index.html` — single-page case study
- `data/apps.tsv` — 100-app research matrix
- `data/verification.tsv` — hand-check sample
- `research_agent.py` — Composio + Gemini research agent
