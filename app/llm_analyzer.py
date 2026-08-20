import json
import time
from dataclasses import dataclass
from app.config import settings
from app.diff_extractor import DiffHunk
from app.rate_limiter import RateLimiter
from app.logger import get_logger

logger = get_logger("llm_analyzer")

@dataclass
class AnalysisResult:
    comment: str
    is_valid: bool
    severity: str = "info"
    category: str = "style"
    confidence: float = 0.5

def _build_client():
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
        prompt = f"""Tu es un expert en revue de code. Analyse ce bloc de code et retourne UNIQUEMENT un objet JSON, sans markdown, sans explication.

Format JSON attendu :
{{
  "comment": "Explication claire du problème en français",
  "severity": "critical|warning|info",
  "category": "bug|security|performance|style",
  "confidence": 0.0
}}

Règles de sévérité :
- critical : bug, faille de sécurité, exception non gérée, crash potentiel
- warning : anti-pattern, risque aux limites, mauvaise pratique fréquente
- info : style, nommage, refactoring mineur

Si aucun problème : {{"comment": "Aucun problème détecté.", "severity": "info", "category": "style", "confidence": 1.0}}

Fichier : {hunk.file}
Lignes : {hunk.lines}
Modifications :
{hunk.content}"""
        try:
            return self._call_with_retry(prompt)
        except Exception as e:
            logger.error(f"LLMAnalyzer — erreur {hunk.file}: {e}")
            return AnalysisResult(comment=f"Erreur analyse {hunk.file}.", is_valid=False)

    def _call_with_retry(self, prompt: str, max_retries: int = 3) -> AnalysisResult:
        messages = [
            {"role": "system", "content": "Tu es un expert en revue de code. Réponds UNIQUEMENT en JSON valide, sans markdown."},
            {"role": "user", "content": prompt}
        ]
        for attempt in range(max_retries):
            try:
                raw = self._create_completion(messages, 1000)
                try:
                    data = json.loads(raw)
                    severity = data.get("severity", "info")
                    return AnalysisResult(
                        comment=data.get("comment", "Aucun problème détecté."),
                        severity=severity,
                        category=data.get("category", "style"),
                        confidence=float(data.get("confidence", 0.5)),
                        is_valid=severity in ("critical", "warning")
                    )
                except json.JSONDecodeError:
                    logger.warning(f"LLMAnalyzer — JSON invalide, fallback texte brut")
                    return AnalysisResult(
                        comment=raw,
                        severity="info",
                        category="style",
                        confidence=0.3,
                        is_valid=False
                    )
            except Exception as e:
                if "rate_limit" in str(e):
                    self.limiter.check_and_wait_retry()
                    time.sleep(2 ** attempt)
                else:
                    raise e
        return AnalysisResult(comment="Analyse impossible.", is_valid=False, severity="info")

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