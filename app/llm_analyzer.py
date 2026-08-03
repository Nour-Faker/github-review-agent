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
    """
    LLMAnalyzer — diagramme Classes.
    NF-6  — Analyse du code par le LLM
    NF-13 — Dépassement de la limite de tokens du LLM
    """

    def __init__(self):
        # Connexion Azure OpenAI
        self.client = AzureOpenAI(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_KEY,
            api_version="2025-01-01-preview"
        )
        self.deployment = settings.AZURE_OPENAI_DEPLOYMENT
        self.limiter = RateLimiter()

    def analyze_hunk(self, hunk: DiffHunk) -> AnalysisResult:
        """
        NF-6 — Analyse un hunk de code via le LLM.
        Correspond à analyze_hunk(hunk: DiffHunk) dans le diagramme Classes.
        """
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
            # NF-13 — Retry si dépassement tokens
            return self._call_with_retry(prompt)

        except Exception as e:
            print(f"[LLMAnalyzer] Erreur analyse {hunk.file}: {e}")
            return AnalysisResult(
                comment=f"Erreur lors de l'analyse de {hunk.file}.",
                is_valid=False
            )

    def _call_with_retry(self, prompt: str, max_retries: int = 3) -> AnalysisResult:
        """
        NF-13 — Gestion dépassement limite tokens avec retry.
        Correspond à check_and_wait_retry() dans RateLimiter.
        """
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.deployment,
                    messages=[
                        {
                            "role": "system",
                            "content": "Tu es un expert en revue de code."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    max_completion_tokens=1000,
                    
                )
                comment = response.choices[0].message.content
                return AnalysisResult(comment=comment, is_valid=True)

            except Exception as e:
                error = str(e)
                # NF-13 — Dépassement limite tokens ou rate limit
                if "rate_limit" in error or "tokens" in error:
                    print(f"[LLMAnalyzer] Rate limit — retry {attempt+1}/{max_retries}")
                    self.limiter.check_and_wait_retry()
                    time.sleep(2 ** attempt)  # Backoff exponentiel
                else:
                    raise e

        return AnalysisResult(
            comment="Analyse impossible après plusieurs tentatives.",
            is_valid=False
        )

    def analyze(self, context: str) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[{"role": "user", "content": context}],
                max_completion_tokens=500
            )
            content = response.choices[0].message.content
            print(f"[LLMAnalyzer] analyze() content: {repr(content)}")
            if not content or not content.strip():
                return "Analyse effectuée — aucun problème critique détecté dans ce code."
            return content
        except Exception as e:
            print(f"[LLMAnalyzer] analyze() erreur: {e}")
            return f"Erreur analyse : {str(e)}"
