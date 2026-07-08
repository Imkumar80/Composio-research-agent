import os
import json
import asyncio
import time
from dotenv import load_dotenv
from composio import ComposioToolSet, App
from openai import AsyncOpenAI
from google import genai

# Load environment variables from .env file
load_dotenv()

# Set up APIs
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY")

async def run_simulation():
    """Runs a simulated, interactive demonstration of the research agent workflow."""
    print("==================================================")
    print("   COMPOSIO RESEARCH AGENT - SIMULATION MODE      ")
    print("==================================================")
    print("[*] No API keys detected. Running in high-fidelity simulation mode...")
    await asyncio.sleep(1)

    sample_apps = [
        {
            "app": "Salesforce",
            "url": "https://developer.salesforce.com/docs/apis",
            "steps": [
                "Using Google Search tool to find Salesforce developer docs...",
                "Found URL: https://developer.salesforce.com/docs/apis",
                "Calling `firecrawl.scrape` to extract page content...",
                "Running LLM reasoning to extract Schema: auth, accessibility, and blockers..."
            ],
            "result": {
                "category": "CRM and Sales",
                "auth": "OAuth2, JWT bearer, username-password",
                "self_serve": "Self-serve trial",
                "api_surface": "Broad REST, Bulk, Streaming, Metadata",
                "verdict": "Buildable"
            }
        },
        {
            "app": "Google Ads",
            "url": "https://developers.google.com/google-ads",
            "steps": [
                "Searching for 'Google Ads API documentation'...",
                "Found URL: https://developers.google.com/google-ads/api/docs/start",
                "Scraping Developer Console setup guide...",
                "Parsing developer token and review process..."
            ],
            "result": {
                "category": "Marketing and Ads",
                "auth": "OAuth2 + Developer Token",
                "self_serve": "Gated (Requires Developer Token review/approval)",
                "api_surface": "Broad gRPC and REST APIs",
                "verdict": "Buildable with approval"
            }
        },
        {
            "app": "Plaid",
            "url": "https://plaid.com/docs",
            "steps": [
                "Searching for Plaid API reference...",
                "Scraping Plaid Quickstart and Auth guides...",
                "Evaluating Sandbox vs Production environment gates..."
            ],
            "result": {
                "category": "Finance and Fintech",
                "auth": "client_id/secret, Link tokens",
                "self_serve": "Self-serve sandbox, Gated production",
                "api_surface": "Broad REST API",
                "verdict": "Buildable with approval"
            }
        }
    ]

    for item in sample_apps:
        print(f"\n[*] Starting research for app: {item['app']}")
        await asyncio.sleep(0.8)
        for step in item['steps']:
            print(f"    [TOOL] {step}")
            await asyncio.sleep(1)
        
        print(f"    [OK] Success! Extracted JSON: {json.dumps(item['result'], indent=8)}")
        await asyncio.sleep(0.5)

    print("\n==================================================")
    print("           VERIFICATION LOOP & HITL               ")
    print("==================================================")
    print("[*] Randomly sampling 15% of records for audit...")
    await asyncio.sleep(1)
    print("[!] Discrepancy found in Google Ads: First pass marked as 'Self-Serve', docs show developer token review is required.")
    await asyncio.sleep(1)
    print("[*] Automatically updating row validation metric...")
    print("[OK] Human-in-the-loop audit complete. Accuracy: 75% -> 95%")
    print("==================================================")

async def run_real():
    """Runs a real, live query using OpenAI or Gemini and Composio."""
    APPS_TO_RESEARCH = ["HubSpot", "Twilio", "Stripe"]
    
    SYSTEM_PROMPT = """
    You are an AI Product Ops Research Agent. Your job is to research developer API documentation.
    Extract the following details in JSON: category, one_line, auth, self_serve, api_surface, verdict, blocker, evidence.
    """

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

        for app in APPS_TO_RESEARCH:
            print(f"[*] Querying ADK Runner for: {app}")
            response = runner.run(f"Research the developer API for: {app}")
            # The runner's response object holds the final string output
            print(f"[OK] Result for {app}: {response.text if hasattr(response, 'text') else str(response)}")
            
    elif OPENAI_API_KEY:
        print("[*] Initializing OpenAI with Composio...")
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        toolset = ComposioToolSet(api_key=COMPOSIO_API_KEY)
        tools = toolset.get_tools(apps=[App.FIRECRAWL])

        for app in APPS_TO_RESEARCH:
            print(f"[*] Querying OpenAI for: {app}")
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
            print(f"[OK] Result for {app}: {response.choices[0].message.content}")

async def main():
    if not COMPOSIO_API_KEY or (not OPENAI_API_KEY and not GEMINI_API_KEY):
        await run_simulation()
    else:
        await run_real()

if __name__ == "__main__":
    asyncio.run(main())
