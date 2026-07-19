import json
import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.security import verify_signature
from app.diff_extractor import DiffExtractor
from app.rate_limiter import RateLimiter
from app.config import settings

router = APIRouter()

class WebhookHandler:
    """WebhookHandler — diagramme Classes Sprint 2."""

    def __init__(self):
        self.extractor = DiffExtractor()
        self.limiter = RateLimiter()

    def is_bot_sender(self, payload: dict) -> bool:
        """Étape 3 — Vérifie si l'expéditeur est un bot."""
        sender = payload.get("sender", {})
        return sender.get("type", "") == "Bot"

    async def handle_webhook(self, payload: dict, event: str) -> None:
        """Étapes 2 à 20 — Traitement principal du webhook."""

        # Étape 3 — is_bot_sender()
        if self.is_bot_sender(payload):
            print("[WebhookHandler] Bot détecté — ignoré")
            return

        # Étape 4 — check_quota()
        sender = payload.get("sender", {}).get("login", "unknown")
        if not self.limiter.check_quota(sender):
            print(f"[WebhookHandler] Quota dépassé pour {sender}")
            return

        # Étape 5 — Traiter uniquement les Pull Requests
        if event == "pull_request":
            action = payload.get("action", "")
            if action in ["opened", "synchronize"]:
                pr_number = payload["pull_request"]["number"]
                repo = payload["repository"]["full_name"]
                asyncio.create_task(self.process_pr(repo, pr_number))

    async def handle_mention_comment(self, payload: dict) -> None:
        """Traitement des mentions @ai-reviewer dans les commentaires."""
        comment = payload.get("comment", {}).get("body", "")
        if "@ai-reviewer" in comment:
            pr_number = payload["issue"]["number"]
            repo = payload["repository"]["full_name"]
            print(f"[WebhookHandler] Mention détectée — PR #{pr_number}")
            asyncio.create_task(self.process_pr(repo, pr_number))

    async def process_pr(self, repo: str, pr_number: int) -> None:
        """NF-5 + NF-6 + NF-13 — Diff extraction + LLM analysis."""

        from app.llm_analyzer import LLMAnalyzer
        analyzer = LLMAnalyzer()

        # Étape 8 — NF-5 fetch_diff()
        print(f"[PR #{pr_number}] Récupération du diff...")
        diff = await self.extractor.fetch_diff(repo, pr_number)

        # Étape 10 — NF-13 is_oversized() → refus si > 500 lignes
        if self.extractor.is_oversized(diff):
            print(f"[PR #{pr_number}] Diff > {settings.MAX_LINES} lignes — refusé")
            return

        # Étape 9 — NF-5 parse_hunks()
        hunks = self.extractor.parse_hunks(diff)
        print(f"[PR #{pr_number}] {len(hunks)} fichiers extraits")

        # Étape 14-16 — NF-6 analyze_hunk() pour chaque fichier
        results = []
        for hunk in hunks:
            # check_and_wait_retry() avant chaque appel LLM
            self.limiter.check_and_wait_retry()
            result = analyzer.analyze_hunk(hunk)
            print(f"  → {hunk.file} : analysé ({result.is_valid})")
            results.append((hunk, result))

        print(f"[PR #{pr_number}] Analyse terminée — {len(results)} résultats")
        # Sprint 3 → GitHubCommenter.post_review(results)


# Instance globale
handler = WebhookHandler()


@router.post("/webhook", status_code=202)
async def github_webhook(request: Request):
    """Point d'entrée — retourne HTTP 202 immédiatement."""

    # Étape 2 — verify_signature()
    body = await verify_signature(request, settings.WEBHOOK_SECRET)
    payload = json.loads(body)
    event = request.headers.get("X-GitHub-Event", "")

    # Étape 7 — HTTP 202 Accepted (Async start)
    asyncio.create_task(handler.handle_webhook(payload, event))

    return JSONResponse(status_code=202, content={"status": "accepted"})