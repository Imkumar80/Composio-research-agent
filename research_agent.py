"""
AI Product Ops Research Agent

Researches developer API documentation for apps using Composio web-search tools
and an LLM agentic loop (Gemini or OpenAI). Saves structured JSON results and
can refresh the case-study data files.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path("data")
RESULTS_FILE = DATA_DIR / "agent_research_results.json"
APPS_TSV = DATA_DIR / "apps.tsv"
APPS_JSON = DATA_DIR / "apps.json"

COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

USER_ID = "research_agent"
MAX_TOOL_ROUNDS = 12

RESEARCH_TOOLS = [
    "TAVILY_SEARCH",
    "TAVILY_EXTRACT",
    "COMPOSIO_SEARCH_DUCK_DUCK_GO",
    "COMPOSIO_SEARCH_FETCH_URL_CONTENT",
]

OUTPUT_FIELDS = [
    "category",
    "one_line",
    "auth",
    "self_serve",
    "api_surface",
    "mcp",
    "verdict",
    "blocker",
    "evidence",
]

SYSTEM_PROMPT = """You are an AI Product Ops Research Agent. Your job is to research
developer API documentation for a given app and return structured findings.

WORKFLOW (follow in order):
1. Use TAVILY_SEARCH or COMPOSIO_SEARCH_DUCK_DUCK_GO to find the official developer
   documentation (look for developer.*, docs.*, api.* domains — not marketing pages).
2. Use TAVILY_EXTRACT or COMPOSIO_SEARCH_FETCH_URL_CONTENT on the official docs pages
   to read authentication and API reference sections.
3. Base every field on evidence from those docs. Do not guess.

RULES:
- "auth" means API authentication (OAuth2, API key, bearer token, basic auth, etc.),
  NOT end-user login methods like "email/password" or "SSO".
- "self_serve": can a developer sign up and get API credentials without sales/partner
  approval? Use values like "Self-serve trial" or "Gated/paid enterprise".
- "mcp": note if there is an official or community MCP server for this app;
  otherwise use "No clear MCP" or "Community MCPs".
- "verdict": one of "Buildable", "Buildable with customer", "Maybe", "Not today".
- "evidence": a single primary HTTPS URL to the official developer docs (pick the best one).

Return ONLY a single valid JSON object with these keys:
category, one_line, auth, self_serve, api_surface, mcp, verdict, blocker, evidence
No markdown fences, no commentary outside the JSON."""


def build_user_prompt(app_name: str, category_hint: str = "") -> str:
    hint = f" (likely category: {category_hint})" if category_hint else ""
    return (
        f"Research the developer API for: {app_name}{hint}.\n"
        "Search the web, read the official developer docs, then return the JSON object."
    )


def parse_json_response(text: str) -> dict[str, Any]:
    """Extract and parse JSON from model output, tolerating markdown fences."""
    if not text:
        raise ValueError("Empty model response")

    cleaned = text.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise


def normalize_result(raw: dict[str, Any], app_name: str) -> dict[str, str]:
    """Ensure all expected fields exist with string values."""
    result = {"app": app_name}
    for key in OUTPUT_FIELDS:
        value = raw.get(key, "")
        result[key] = str(value).strip() if value is not None else ""

    # Keep one canonical evidence URL when the model returns several.
    evidence = result.get("evidence", "")
    if evidence:
        urls = re.findall(r"https?://[^\s\"'<>]+", evidence)
        if urls:
            result["evidence"] = urls[0].rstrip(".,;)")
    return result


def load_apps(filepath: Path = APPS_TSV) -> list[dict[str, str]]:
    apps: list[dict[str, str]] = []
    if not filepath.exists():
        return apps
    with open(filepath, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            apps.append(dict(row))
    return apps


def load_existing_results() -> dict[str, dict[str, Any]]:
    if not RESULTS_FILE.exists():
        return {}
    with open(RESULTS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return {item["app"]: item for item in data if "app" in item}
    return data


def save_results(results: dict[str, dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ordered = sorted(results.values(), key=lambda r: r.get("app", ""))
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(ordered, f, indent=2, ensure_ascii=False)


def merge_into_apps_json(results: dict[str, dict[str, Any]]) -> None:
    """Update apps.json rows with agent research output."""
    if not APPS_JSON.exists():
        return
    with open(APPS_JSON, encoding="utf-8") as f:
        apps = json.load(f)

    by_name = {r["app"]: r for r in results.values() if r.get("status") == "ok"}
    for app in apps:
        name = app.get("app", "")
        if name not in by_name:
            continue
        research = by_name[name]
        for key in OUTPUT_FIELDS:
            if research.get(key):
                app[key] = research[key]

    with open(APPS_JSON, "w", encoding="utf-8") as f:
        json.dump(apps, f, indent=2, ensure_ascii=False)


def write_apps_tsv(apps: list[dict[str, str]]) -> None:
    columns = ["id", "category", "app", *OUTPUT_FIELDS]
    with open(APPS_TSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in apps:
            writer.writerow(row)


def regenerate_html() -> None:
    script = Path("generate_case_study.py")
    if script.exists():
        subprocess.run([sys.executable, str(script)], check=False)


@dataclass
class ResearchRunConfig:
    provider: str = "gemini"
    limit: int | None = None
    start: int = 0
    app_filter: str | None = None
    skip_existing: bool = True
    refresh_data: bool = False
    model: str | None = None


class GeminiResearchAgent:
    def __init__(self, model: str = "gemini-2.5-flash") -> None:
        os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY or ""
        from composio import Composio
        from composio_google import GoogleProvider
        from google import genai
        from google.genai import types

        self._types = types
        self.composio = Composio(api_key=COMPOSIO_API_KEY, provider=GoogleProvider())
        self.client = genai.Client()
        self.model = model
        self.tools = self.composio.tools.get(user_id=USER_ID, tools=RESEARCH_TOOLS)
        self.config = types.GenerateContentConfig(
            tools=self.tools,
            system_instruction=SYSTEM_PROMPT,
        )

    def research(self, app_name: str, category_hint: str = "") -> str:
        chat = self.client.chats.create(model=self.model, config=self.config)
        response = chat.send_message(build_user_prompt(app_name, category_hint))

        for _ in range(MAX_TOOL_ROUNDS):
            if not response.function_calls:
                break
            parts = []
            for fc in response.function_calls:
                result = self.composio.provider.execute_tool_call(
                    user_id=USER_ID, function_call=fc
                )
                parts.append(
                    self._types.Part.from_function_response(name=fc.name, response=result)
                )
            response = chat.send_message(parts)

        if not response.text:
            raise RuntimeError("Model returned no text after tool loop")
        return response.text


class OpenAIResearchAgent:
    def __init__(self, model: str = "gpt-4o-mini") -> None:
        from openai import OpenAI
        from composio import Composio
        from composio_openai import OpenAIProvider

        self.composio = Composio(api_key=COMPOSIO_API_KEY, provider=OpenAIProvider())
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.model = model
        self.tools = self.composio.tools.get(user_id=USER_ID, tools=RESEARCH_TOOLS)

    def research(self, app_name: str, category_hint: str = "") -> str:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(app_name, category_hint)},
        ]

        for _ in range(MAX_TOOL_ROUNDS):
            response = self.client.chat.completions.create(
                model=self.model,
                tools=self.tools,
                messages=messages,
            )
            msg = response.choices[0].message
            if not msg.tool_calls:
                if not msg.content:
                    raise RuntimeError("Model returned no content after tool loop")
                return msg.content

            results = self.composio.provider.handle_tool_calls(
                response=response, user_id=USER_ID
            )
            messages.append(msg.model_dump())
            for i, tc in enumerate(msg.tool_calls):
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(results[i]),
                    }
                )

        raise RuntimeError(f"Exceeded {MAX_TOOL_ROUNDS} tool rounds without final answer")


def pick_provider(config: ResearchRunConfig):
    if config.provider == "openai":
        if not OPENAI_API_KEY:
            raise SystemExit("[!] OPENAI_API_KEY is missing in .env")
        model = config.model or "gpt-4o-mini"
        print(f"[*] Using OpenAI ({model}) + Composio search tools")
        return OpenAIResearchAgent(model=model)

    if not GEMINI_API_KEY:
        raise SystemExit("[!] GEMINI_API_KEY is missing in .env")
    model = config.model or "gemini-2.5-flash"
    print(f"[*] Using Gemini ({model}) + Composio search tools")
    return GeminiResearchAgent(model=model)


def select_apps(apps: list[dict[str, str]], config: ResearchRunConfig) -> list[dict[str, str]]:
    if config.app_filter:
        apps = [a for a in apps if a.get("app", "").lower() == config.app_filter.lower()]
    apps = apps[config.start :]
    if config.limit is not None:
        apps = apps[: config.limit]
    return apps


def run_research(config: ResearchRunConfig) -> dict[str, dict[str, Any]]:
    if not COMPOSIO_API_KEY:
        raise SystemExit("[!] COMPOSIO_API_KEY is missing in .env")

    apps = load_apps()
    if not apps:
        apps = [{"id": "", "category": "", "app": name} for name in ["Stripe", "HubSpot", "Salesforce"]]

    apps = select_apps(apps, config)
    if not apps:
        print("[!] No apps matched your filters.")
        return {}

    existing = load_existing_results()
    agent = pick_provider(config)

    print(f"[*] Researching {len(apps)} app(s)...")
    results = dict(existing)

    for i, row in enumerate(apps, start=1):
        app_name = row.get("app", "").strip()
        if not app_name:
            continue

        if config.skip_existing and app_name in results and results[app_name].get("status") == "ok":
            print(f"[=] ({i}/{len(apps)}) Skipping {app_name} (already researched)")
            continue

        category_hint = row.get("category", "")
        print(f"[*] ({i}/{len(apps)}) Researching: {app_name}")
        started = time.time()

        try:
            raw_text = agent.research(app_name, category_hint)
            parsed = parse_json_response(raw_text)
            normalized = normalize_result(parsed, app_name)
            entry = {
                **normalized,
                "status": "ok",
                "raw_result": raw_text,
                "researched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "duration_s": round(time.time() - started, 1),
            }
            print(f"[OK] {app_name}: {normalized.get('verdict', '?')} — {normalized.get('evidence', '')[:80]}")
        except Exception as exc:
            entry = {
                "app": app_name,
                "status": "error",
                "error": str(exc),
                "researched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            print(f"[!] Error researching {app_name}: {exc}")

        results[app_name] = entry
        save_results(results)

    if config.refresh_data:
        merge_into_apps_json(results)
        print(f"[*] Updated {APPS_JSON}")

    regenerate_html()
    print(f"[*] Done. Results in {RESULTS_FILE}")
    return results


def parse_args() -> ResearchRunConfig:
    parser = argparse.ArgumentParser(description="Research developer APIs using Composio + LLM")
    parser.add_argument(
        "--provider",
        choices=["gemini", "openai"],
        default="gemini" if GEMINI_API_KEY else "openai",
        help="LLM provider (default: gemini if GEMINI_API_KEY is set)",
    )
    parser.add_argument("--model", help="Override default model name")
    parser.add_argument("--limit", type=int, help="Max number of apps to research")
    parser.add_argument("--start", type=int, default=0, help="Start index in apps.tsv")
    parser.add_argument("--app", dest="app_filter", help="Research a single app by name")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-research apps even if a successful result already exists",
    )
    parser.add_argument(
        "--refresh-data",
        action="store_true",
        help="Merge successful results into data/apps.json and regenerate index.html",
    )
    args = parser.parse_args()
    return ResearchRunConfig(
        provider=args.provider,
        model=args.model,
        limit=args.limit,
        start=args.start,
        app_filter=args.app_filter,
        skip_existing=not args.force,
        refresh_data=args.refresh_data,
    )


def main() -> None:
    config = parse_args()
    run_research(config)


if __name__ == "__main__":
    main()
