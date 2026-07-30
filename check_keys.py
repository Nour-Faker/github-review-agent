import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

async def check_github():
    token = os.getenv("GITHUB_TOKEN")
    async with httpx.AsyncClient() as client:
        r = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"token {token}"}
        )
    if r.status_code == 200:
        print(f"✅ GitHub OK — logged as: {r.json()['login']}")
    else:
        print(f"❌ GitHub FAILED — {r.status_code}: {r.json()['message']}")

async def check_azure():
    key = os.getenv("AZURE_OPENAI_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    
    # Correct Azure OpenAI path
    url = f"{endpoint}openai/deployments/{deployment}/chat/completions?api-version=2024-02-01"
    
    payload = {
        "messages": [{"role": "user", "content": "say ok"}],
        "max_tokens": 5
    }
    
    async with httpx.AsyncClient() as client:
        r = await client.post(url, headers={"api-key": key}, json=payload)
    
    if r.status_code == 200:
        print("✅ Azure OpenAI OK — model responding")
    else:
        print(f"❌ Azure FAILED — {r.status_code}: {r.text}")
asyncio.run(check_github())
asyncio.run(check_azure())