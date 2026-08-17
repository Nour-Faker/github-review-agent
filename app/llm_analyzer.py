from dataclasses import dataclass
from app.config import settings
from app.diff_extractor import DiffHunk
from app.rate_limiter import RateLimiter
from app.logger import get_logger
import time

logger = get_logger("llm_analyzer")

@dataclass
class AnalysisResult:
    comment: str
    is_valid: bool

def _build_client():
    """Factory — retourne le bon client selon LLM_PROVIDER."""
    if settings.LLM_PROVIDER == "openai":
        from openai import OpenAI
        logger.info("LLMAnalyzer — fournisseur: OpenAI")
        return OpenAI(api_key=settings.OPENAI_API_KEY), settings.OPENAI_MODEL
    else:
        from openai import AzureOpenAI
        logger.info("LLMAnalyzer — fournisseur: Azure OpenAI")
        return AzureOpenAI(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_KEY,
            api_version="2025-01-01-preview"
        ), settings.AZURE_OPENAI_DEPLOYMENT

class LLMAnalyzer:
    def __init__(self):
        self.client, self.deployment = _build_client()
        self.limiter = RateLimiter()

    def _create_completion(self, messages: list, max_tokens: int) -> str:
        kwargs = {"model": self.deployment, "messages": messages}
        if settings.LLM_PROVIDER == "azure":
            kwargs["max_completion_tokens"] = max_tokens
        else:
            kwargs["max_tokens"] = max_tokens
        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    def analyze_hunk(self, hunk: DiffHunk) -> AnalysisResult:
        prompt = f"""Tu es un expert en revue de code.
Analyse ce bloc de code modifié et identifie les bugs, problèmes de sécurité, mauvaises pratiques.
Fichier : {hunk.file}
Lignes : {hunk.lines}
Modifications :
{hunk.content}
Réponds en français, de façon concise."""
        try:
            return self._call_with_retry(prompt)
        except Exception as e:
            logger.error(f"LLMAnalyzer — erreur {hunk.file}: {e}")
            return AnalysisResult(comment=f"Erreur analyse {hunk.file}.", is_valid=False)

    def _call_with_retry(self, prompt: str, max_retries: int = 3) -> AnalysisResult:
        messages = [
            {"role": "system", "content": "Tu es un expert en revue de code. Réponds en français."},
            {"role": "user", "content": prompt}
        ]
        for attempt in range(max_retries):
            try:
                comment = self._create_completion(messages, 1000)
                return AnalysisResult(comment=comment, is_valid=True)
            except Exception as e:
                if "rate_limit" in str(e):
                    self.limiter.check_and_wait_retry()
                    time.sleep(2 ** attempt)
                else:
                    raise e
        return AnalysisResult(comment="Analyse impossible.", is_valid=False)

    def analyze(self, context: str) -> str:
        messages = [
            {"role": "system", "content": "Tu es un expert en revue de code. Réponds en français."},
            {"role": "user", "content": context}
        ]
        try:
            content = self._create_completion(messages, 500)
            logger.info(f"LLMAnalyzer — content: {repr(content)}")
            return content if content.strip() else "Aucun problème détecté."
        except Exception as e:
            logger.error(f"LLMAnalyzer — erreur: {e}")
            return f"Erreur analyse : {str(e)}"