from dataclasses import dataclass
from openai import AzureOpenAI
from app.config import settings
from app.diff_extractor import DiffHunk
from app.rate_limiter import RateLimiter
import time

@dataclass
class AnalysisResult:
    """AnalysisResult — diagramme Classes."""
    comment: str
    is_valid: bool

class LLMAnalyzer:
    """LLMAnalyzer — NF-6 + NF-13."""

    def __init__(self):
        self.client = AzureOpenAI(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_KEY,
            api_version="2025-03-01-preview"
        )
        self.deployment = settings.AZURE_OPENAI_DEPLOYMENT
        self.limiter = RateLimiter()

    def analyze_hunk(self, hunk: DiffHunk) -> AnalysisResult:
        """NF-6 — Analyse un hunk via le LLM."""
        prompt = f"""Tu es un expert en revue de code.
Analyse ce bloc de code modifié et identifie :
- Les bugs potentiels
- Les problèmes de sécurité
- Les mauvaises pratiques

Fichier : {hunk.file}
Lignes : {hunk.lines}
Modifications :
{hunk.content}

Réponds en français, de façon concise et professionnelle."""

        try:
            return self._call_with_retry(prompt)
        except Exception as e:
            print(f"[LLMAnalyzer] Erreur analyse {hunk.file}: {e}")
            return AnalysisResult(
                comment=f"Erreur lors de l'analyse de {hunk.file}.",
                is_valid=False
            )

    def _call_with_retry(self, prompt: str, max_retries: int = 3) -> AnalysisResult:
        """NF-13 — Retry avec backoff exponentiel."""
        for attempt in range(max_retries):
            try:
                response = self.client.responses.create(
                    model=self.deployment,
                    input=[{"role": "user", "content": prompt}],
                    instructions="Tu es un expert en revue de code.",
                    max_output_tokens=1000
                )
                comment = response.output_text
                return AnalysisResult(comment=comment, is_valid=True)

            except Exception as e:
                error = str(e)
                if "rate_limit" in error or "tokens" in error:
                    print(f"[LLMAnalyzer] Rate limit — retry {attempt+1}/{max_retries}")
                    self.limiter.check_and_wait_retry()
                    time.sleep(2 ** attempt * 5)
                else:
                    raise e

        return AnalysisResult(
            comment="Analyse impossible après plusieurs tentatives.",
            is_valid=False
        )

    def analyze(self, context: str) -> str:
        """Analyse un contexte général — NF-9."""
        try:
            response = self.client.responses.create(
                model=self.deployment,
                input=[{"role": "user", "content": context}],
                instructions="Tu es un expert en revue de code.",
                max_output_tokens=500
            )
            return response.output_text
        except Exception as e:
            return f"Erreur analyse : {str(e)}"