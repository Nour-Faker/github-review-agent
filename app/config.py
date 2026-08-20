import os
from dotenv import load_dotenv
load_dotenv()

class AppSettings:
    """AppSettings — diagramme Classes."""
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    WEBHOOK_SECRET: str = os.getenv("GITHUB_WEBHOOK_SECRET", "")
    AZURE_OPENAI_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    AZURE_OPENAI_KEY: str = os.getenv("AZURE_OPENAI_KEY", "")
    AZURE_OPENAI_DEPLOYMENT: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    MAX_LINES: int = 500
    # NF-24/25 — Multi-fournisseurs LLM
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "azure")  # "azure" | "openai"
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

settings = AppSettings()