from dataclasses import dataclass
from openai import AzureOpenAI
from app.config import settings
from app.diff_extractor import DiffHunk
from app.rate_limiter import RateLimiter
import time
from app.logger import get_logger
logger = get_logger("llm_analyzer")

@dataclass
class AnalysisResult:
    comment: str
    is_valid: bool

class LLMAnalyzer:
    def __init__(self):
        self.client = AzureOpenAI(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_KEY,
            api_version="2025-01-01-preview"
        )
        self.deployment = settings.AZURE_OPENAI_DEPLOYMENT
        self.limiter = RateLimiter()

    def _create_completion(self, messages: list, max_tokens: int) -> str:
        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=messages,
            max_completion_tokens=max_tokens
        )
        return response.choices[0].message.content or ""

    def analyze_hunk(self, hunk: DiffHunk) -> AnalysisResult:
        prompt = f'''Tu es un expert en revue de code.
Analyse ce bloc de code modifie et identifie les bugs, problemes de securite, mauvaises pratiques.
Fichier : {hunk.file}
Lignes : {hunk.lines}
Modifications :
{hunk.content}
Reponds en francais, de facon concise.'''
        try:
            return self._call_with_retry(prompt)
        except Exception as e:
            logger.error(f"LLMAnalyzer — erreur {hunk.file}: {e}")
            return AnalysisResult(comment=f"Erreur analyse {hunk.file}.", is_valid=False)

    def _call_with_retry(self, prompt: str, max_retries: int = 3) -> AnalysisResult:
        messages = [
            {"role": "system", "content": "Tu es un expert en revue de code. Reponds en francais."},
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
            {"role": "system", "content": "Tu es un expert en revue de code. Reponds en francais."},
            {"role": "user", "content": context}
        ]
        try:
            content = self._create_completion(messages, 500)
            logger.info(f"LLMAnalyzer — content: {repr(content)}")
            return content if content.strip() else "Aucun probleme detecte."
        except Exception as e:
            logger.error(f"LLMAnalyzer — erreur: {e}")
            return f"Erreur analyse : {str(e)}"
