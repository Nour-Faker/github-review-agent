from dataclasses import dataclass
from openai import AzureOpenAI
from app.config import settings
from app.diff_extractor import DiffHunk
from app.rate_limiter import RateLimiter
import time 

@dataclass
class AnalysisResult:
    """ AnalysisReusult_diagramme de class"""
    comment:str
    is_valid:bool
class LLMAnalyzer:
    """
    LLMAnalyzer-diagramme de class
    NF-6- analyse du code par le llm
    NF13-Dépassement de la limite de tokens du LLM"""

    def __init__(self):
        #connection to OpenAI
        self.client=AzureOpenAI(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_KEY,
            api_version="2024-02-01")
        self.deployement=settings.AZURE_OPENAI_DEPLOYMENT
        self.limiter=RateLimiter()
    def analyze_hunk(self,hunk:DiffHunk)->analysisResult:
        """analyse un hunk de code via le llm . 
        correspond a analyse_hubk(hunk:DiffHubk)dans le diagramme de classes"""
        prompt=f"""tu es un expert en revue de code.
        analyse ce bloc de code modifié et identifie:
        -les bugs potentiels
        -les problèmes de sécurité
        -les mauvaises pratiques
          
        Fichier : {hunk.file}
        Lignes : {hunk.lines}
        Modifications :
        {hunk.content}

        Réponds en français, de façon concise et professionnelle."""

        try:
            #NF-13-retry si dpassement tokens
            return self._call_with_retry(prompt)
        except Exception as e:
            print(f"[LLMAnalyzer] Erreur analyse {hunk.file}: {e}")
            return AnalysisResult(
                comment=f"Erreur lors de l'analyse de {hunk.file}.",
                is_valid=False
            )
    def _call_with_retry(self, prompt:str,max_retries:int=3)->AnalysisResult:
        """
        NF3-getion depassement limite tokens avec retry.
        correspo,d a check_and_await-retry() dans RAtelimiter.
        """
        for attempt in range(max_retries):
            try:
                response=self.client.chat.completions.create(
                    model=self.deployement
                    messages=[{
                        "role":"system",
                        "content":"Tu es un expert en revue de code"

                    },
                    {
                        "role":"user",
                        "content":prompt
                    }],
                    max_tokens=1000,
                    temperature=0.2
                )
                comment=response.choices[0].message.content
                return AnalysisResult(comment=comment,is_valid=True)
            
            except Exception as e:
                error=str(e)
                #Dépassement des limites de tokens or rate limit
                if"rate_limit"in error or "tokens"in error:
                    print(f"[LLMAnalyzer]Rate limit-retry{attempt+1}/{max_retries}")
                    self.limiter.check_and_wait_retry()
                    time.sleep(2**attempt) #Backoff expoentiel
                else:
                    raise e
                
        return AnalysisResult(
            comment="Analyse impossible aprés plusieurs tentatives.",
            is_valid=False
        )
    
def analyze(self,context:str)->str:
    """
    Analyse un context général-diagramme Classes.
    Utilisé pour les mentions @ai-reviewer"""

    try:
        response=self.client.chat.completions.create(
            model=self.deployment,
            messages=[{"role":"user","content":context}]
            max_tokens=500,
            temperature=0.2
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Erreur analyse:{str(e)}"


