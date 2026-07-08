import os
import json
import asyncio
import csv
from dotenv import load_dotenv
from composio import ComposioToolSet, App
from openai import AsyncOpenAI

# Load environment variables from .env file
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY")

SYSTEM_PROMPT = """
You are an AI Product Ops Research Agent. Your job is to research developer API documentation.
Extract the following details in JSON format:
- category: The category of the app.
- one_line: What the app does in one line.
- auth: The authentication methods (OAuth2, API key, Basic, token, or other).
- self_serve: Whether a developer can get credentials themselves for free or on a trial (Self-serve vs Gated).
- api_surface: The API surface (e.g. broad REST, GraphQL, bulk APIs).
- verdict: Buildable or not (is it an agent toolkit today?).
- blocker: The main blocker if it is not easily buildable.
- evidence: URL to the documentation proving this.
"""

def load_apps_to_research(filepath="data/apps.tsv"):
    """Loads the list of apps to research from the TSV file."""
    apps = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                apps.append(row['app'])
    except FileNotFoundError:
        print(f"[!] Input file {filepath} not found. Please provide the list of apps.")
    return apps

async def main():
    if not COMPOSIO_API_KEY or (not OPENAI_API_KEY and not GEMINI_API_KEY):
        print("[!] ERROR: Missing API keys in .env file.")
        print("Please provide COMPOSIO_API_KEY and either OPENAI_API_KEY or GEMINI_API_KEY to run the agent.")
        return

    apps_to_research = load_apps_to_research()
    if not apps_to_research:
        # Fallback to a small test set if TSV doesn't exist
        apps_to_research = ["Salesforce", "HubSpot", "Stripe"]

    print(f"[*] Starting production research run for {len(apps_to_research)} apps...")
    results = []
    
    if GEMINI_API_KEY:
        print("[*] Initializing Google ADK Agent with Composio...")
        from google_adk import Agent, Runner
        from composio_google_adk import ComposioToolSet as GoogleComposioToolSet, App
        
        toolset = GoogleComposioToolSet(api_key=COMPOSIO_API_KEY)
        tools = toolset.get_tools(apps=[App.FIRECRAWL])

        # ADK natively runs the tool loop!
        agent = Agent(
            model="gemini-2.5-flash",
            tools=tools,
            system_instruction=SYSTEM_PROMPT
        )
        runner = Runner(agent)

        for app in apps_to_research:
            print(f"[*] Querying ADK Runner for: {app}")
            try:
                response = runner.run(f"Research the developer API for: {app}")
                output_text = response.text if hasattr(response, 'text') else str(response)
                print(f"[OK] Result for {app}: {output_text}")
                results.append({"app": app, "raw_result": output_text})
            except Exception as e:
                print(f"[!] Error researching {app}: {e}")
                
    elif OPENAI_API_KEY:
        print("[*] Initializing OpenAI with Composio...")
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        toolset = ComposioToolSet(api_key=COMPOSIO_API_KEY)
        tools = toolset.get_tools(apps=[App.FIRECRAWL])

        for app in apps_to_research:
            print(f"[*] Querying OpenAI for: {app}")
            try:
                response = await client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"Research the developer API for: {app}"}
                    ],
                    tools=tools,
                    tool_choice="auto",
                    response_format={ "type": "json_object" }
                )
                output_text = response.choices[0].message.content
                print(f"[OK] Result for {app}: {output_text}")
                results.append({"app": app, "raw_result": output_text})
            except Exception as e:
                print(f"[!] Error researching {app}: {e}")

    # Save output incrementally or at the end
    os.makedirs("data", exist_ok=True)
    with open("data/agent_research_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)
        
    print("[*] Run complete. Results saved to data/agent_research_results.json")

if __name__ == "__main__":
    asyncio.run(main())
