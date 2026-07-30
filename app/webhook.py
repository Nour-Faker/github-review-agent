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
    """WebhookHandler — diagramme Classes Sprint 3."""

    def __init__(self):
        self.extractor = DiffExtractor()
        self.limiter = RateLimiter()

    def is_bot_sender(self, payload: dict) -> bool:
        """
        NF-15 — Évite la boucle infinie.
        Ignore les événements déclenchés par le bot lui-même.
        """
        sender = payload.get("sender", {})
        # Vérifie sender.type == "Bot" OU sender.login == "nom-app[bot]"
        is_bot_type = sender.get("type", "") == "Bot"
        is_bot_login = sender.get("login", "").endswith("[bot]")
        return is_bot_type or is_bot_login

    async def handle_webhook(self, payload: dict, event: str) -> None:
        """
        Traitement principal — diagramme Séquence étapes 2 à 20.
        Gère pull_request ET issue_comment (NF-9).
        """
        # NF-15 — is_bot_sender() → ignorer les bots
        if self.is_bot_sender(payload):
            print("[WebhookHandler] Bot détecté — ignoré")
            return

        # Étape 4 — check_quota()
        sender = payload.get("sender", {}).get("login", "unknown")
        if not self.limiter.check_quota(sender):
            print(f"[WebhookHandler] Quota dépassé pour {sender}")
            return

        # NF-8 — Traiter les Pull Requests
        if event == "pull_request":
            action = payload.get("action", "")
            if action in ["opened", "synchronize"]:
                pr_number = payload["pull_request"]["number"]
                repo = payload["repository"]["full_name"]
                commit_sha = payload["pull_request"]["head"]["sha"]
                print(f"[PR #{pr_number}] Début traitement — {repo}")
                await self.process_pr(repo, pr_number, commit_sha)  # ← await direct

        # NF-9 — Gestion des commandes textuelles (@ai-reviewer)
        elif event == "issue_comment":
            await self.handle_mention_comment(payload)

    async def handle_mention_comment(self, payload: dict) -> None:
        """NF-9 — Gestion des commandes textuelles."""
        from app.commenter import GitHubCommenter
        from app.llm_analyzer import LLMAnalyzer

        comment_body = payload.get("comment", {}).get("body", "")
        repo = payload.get("repository", {}).get("full_name", "")
        pr_number = payload.get("issue", {}).get("number", 0)

        print(f"[NF-9] Event reçu — comment: '{comment_body[:50]}' repo: {repo} pr: {pr_number}")

        if "@ai-reviewer" not in comment_body:
            print(f"[NF-9] Pas de mention @ai-reviewer — ignoré")
            return

        if self.is_bot_sender(payload):
            print(f"[NF-9] Bot détecté — ignoré")
            return

        print(f"[NF-9] Mention détectée — traitement PR #{pr_number}")

        question = comment_body.replace("@ai-reviewer", "").strip()
        analyzer = LLMAnalyzer()
        context = f"Question sur PR #{pr_number} : {question}\nRéponds en français."
        response = analyzer.analyze(context)

        print(f"[NF-9] Réponse LLM générée — {len(response)} caractères")

        commenter = GitHubCommenter()
        await commenter.post_single_comment(
            body=f"🤖 **@ai-reviewer**\n\n{response}",
            pr_id=str(pr_number),
            repo=repo
        )
        print(f"[NF-9] Commentaire posté sur PR #{pr_number}")

    async def process_pr(
        self,
        repo: str,
        pr_number: int,
        commit_sha: str
    ) -> None:
        """
        NF-8 + NF-14 + NF-15 — Traitement complet d'une PR.
        """
        from app.llm_analyzer import LLMAnalyzer
        from app.commenter import GitHubCommenter

        commenter = GitHubCommenter()
        analyzer = LLMAnalyzer()

        print(f"[PR #{pr_number}] Début traitement...")

        # NF-5 — fetch_diff()
        diff = await self.extractor.fetch_diff(repo, pr_number)

        # NF-13 — is_oversized() → commentaire explicatif si refusé
        if self.extractor.is_oversized(diff):
            print(f"[PR #{pr_number}] Diff > {settings.MAX_LINES} lignes — refusé")
            await commenter.post_single_comment(
                body=f"🤖 **GitHub Review Agent**\n\n⚠️ Cette PR dépasse la limite de **{settings.MAX_LINES} lignes** modifiées et ne peut pas être analysée automatiquement.\n\nMerci de découper cette PR en plus petites unités.",
                pr_id=str(pr_number),
                repo=repo
            )
            return

        # NF-5 — parse_hunks()
        hunks = self.extractor.parse_hunks(diff)
        print(f"[PR #{pr_number}] {len(hunks)} fichiers extraits")

        if not hunks:
            return

        # NF-6 + NF-13 — analyze_hunk() pour chaque fichier
        results = []
        for hunk in hunks:
            self.limiter.check_and_wait_retry()
            result = analyzer.analyze_hunk(hunk)
            print(f"  → {hunk.file} : analysé ({result.is_valid})")
            results.append((hunk, result))

        # NF-8 — post_review() avec NF-14 validate()
        await commenter.post_review(
            results=results,
            repo=repo,
            pr_number=pr_number,
            commit_sha=commit_sha
        )

        print(f"[PR #{pr_number}] Sprint 3 terminé ✅")


# Instance globale
handler = WebhookHandler()


@router.post("/webhook", status_code=202)
async def github_webhook(request: Request):
    """Point d'entrée — HTTP 202 immédiat."""
    body = await verify_signature(request, settings.WEBHOOK_SECRET)
    payload = json.loads(body)
    event = request.headers.get("X-GitHub-Event", "")
    
    print(f"[Webhook] Event reçu: {event}")
    
    # Appel direct au lieu de create_task
    await handler.handle_webhook(payload, event)

    return JSONResponse(status_code=202, content={"status": "accepted"})