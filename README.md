# Composio 100-App Toolkit Research

This repo is a take-home assignment artifact for mapping whether 100 requested apps can become Composio-style agent toolkits.

## Deliverable

- `index.html` is the single-page case study reviewers can open directly.
- `data/apps.tsv` is the 100-app research matrix with category, auth, access gate, API surface, MCP signal, verdict, blocker, and evidence URL.
- `data/verification.tsv` is the hand-check sample that records first-pass misses and final corrections.
- `research_agent.py` regenerates the HTML from the structured data.

## Run

```bash
python research_agent.py
```

Then open `index.html` in a browser.

## Research Agent Workflow

1. Seed the 100 apps from the prompt and normalize category/app names.
2. Attach official docs or product URLs as evidence.
3. Classify auth, self-serve/gated status, API breadth, MCP signal, and buildability.
4. Risk-rank rows where model guesses are most likely to fail: ads APIs, finance APIs, enterprise data vendors, marketplace APIs, and obscure AI/media tools.
5. Hand-check a sample against docs and update rows where the first pass was incomplete or too optimistic.
6. Regenerate the static HTML page.

## Honesty Notes

Rows marked `Maybe` or `Not today` are not engineering failures. They are product-ops routing decisions: some apps need partner access, paid/admin credentials, customer-provided docs, or outreach before toolkit work is worth starting.
