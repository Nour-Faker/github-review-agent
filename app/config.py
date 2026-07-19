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

settings = AppSettings()