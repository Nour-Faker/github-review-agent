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
    def __init__(self):
        self.extractor = DiffExtractor()
        self.limiter = RateLimiter()

    def is_bot_sender(self, payload: dict) -> bool:
        sender = payload.get("sender", {})
        is_bot_type = sender.get("type", "") == "Bot"
        is_bot_login = sender.get("login", "").endswith("[bot]")
        return is_bot_type or is_bot_login

    async def handle_webhook(self, payload: dict, event: str) -> None:
        if self.is_bot_sender(payload):
            print("[WebhookHandler] Bot détecté — ignoré")
            return

        sender = payload.get("sender", {}).get("login", "unknown")
        if not self.limiter.check_quota(sender):
            print(f"[WebhookHandler] Quota dépassé pour {sender}")
            return

        if event == "pull_request":
            action = payload.get("action", "")
            if action in ["opened", "synchronize"]:
                pr_number = payload["pull_request"]["number"]
                repo = payload["repository"]["full_name"]
                commit_sha = payload["pull_request"]["head"]["sha"]
                asyncio.create_task(self.process_pr(repo, pr_number, commit_sha))

        elif event == "issue_comment":
            await self.handle_mention_comment(payload)

    async def handle_mention_comment(self, payload: dict) -> None:
        """
        NF-9 — Handler pour les mentions @ai-reviewer dans les commentaires.

        CORRECTIF PRINCIPAL : on fetch le diff de la PR AVANT d'appeler le LLM,
        sinon le LLM répond dans le vide sans voir le code.
        """
        from app.commenter import GitHubCommenter
        from app.llm_analyzer import LLMAnalyzer

        comment_body = payload.get("comment", {}).get("body", "")
        repo = payload.get("repository", {}).get("full_name", "")
        pr_number = payload.get("issue", {}).get("number", 0)

        # Gardes — ordre important
        if "@ai-reviewer" not in comment_body:
            return
        if comment_body.startswith("🤖"):
            return  # NF-15 — bot loop prevention
        if self.is_bot_sender(payload):
            return

        print(f"[NF-9] Mention @ai-reviewer détectée sur PR #{pr_number}")

        question = comment_body.replace("@ai-reviewer", "").strip()

        # ✅ CORRECTIF — fetch du diff pour donner le contexte réel au LLM
        try:
            diff = await self.extractor.fetch_diff(repo, pr_number)
        except Exception as e:
            print(f"[NF-9] Impossible de récupérer le diff : {e}")
            diff = ""

        if not diff or self.extractor.is_oversized(diff):
            diff_context = "(diff non disponible ou trop volumineux pour cette analyse)"
        else:
            # On limite à 3000 caractères pour ne pas dépasser le contexte LLM
            diff_context = diff[:3000]

        context = f"""Tu es un expert en revue de code.

Un développeur pose cette question sur la PR #{pr_number} :
"{question}"

Voici le diff de la PR (code réellement modifié) :
---
{diff_context}
---

Réponds directement à la question en te basant sur le code ci-dessus.
Sois concis et professionnel. Réponds en français."""

        analyzer = LLMAnalyzer()
        response = analyzer.analyze(context)

        if not response or not response.strip():
            response = "Analyse effectuée — aucun problème critique détecté dans ce code."

        commenter = GitHubCommenter()
        await commenter.post_single_comment(
            body=f"🤖 **@ai-reviewer**\n\n{response}",
            pr_id=str(pr_number),
            repo=repo
        )

    async def process_pr(self, repo: str, pr_number: int, commit_sha: str) -> None:
        """Pipeline complet de review automatique d'une PR."""
        from app.llm_analyzer import LLMAnalyzer
        from app.commenter import GitHubCommenter

        commenter = GitHubCommenter()
        analyzer = LLMAnalyzer()

        print(f"[PR #{pr_number}] Début traitement...")

        diff = await self.extractor.fetch_diff(repo, pr_number)

        if self.extractor.is_oversized(diff):
            print(f"[PR #{pr_number}] Diff > {settings.MAX_LINES} lignes — refusé")
            await commenter.post_single_comment(
                body=f"🤖 **GitHub Review Agent**\n\n⚠️ Cette PR dépasse la limite de **{settings.MAX_LINES} lignes**.",
                pr_id=str(pr_number),
                repo=repo
            )
            return

        hunks = self.extractor.parse_hunks(diff)
        print(f"[PR #{pr_number}] {len(hunks)} fichiers extraits")

        if not hunks:
            await commenter.post_single_comment(
                body="🤖 **GitHub Review Agent**\n\nAucune modification de code détectée dans cette PR.",
                pr_id=str(pr_number),
                repo=repo
            )
            return

        results = []
        for hunk in hunks:
            self.limiter.check_and_wait_retry()
            result = analyzer.analyze_hunk(hunk)
            print(f"  -> {hunk.file} : analysé (valide={result.is_valid})")
            results.append((hunk, result))

        await commenter.post_review(
            results=results,
            repo=repo,
            pr_number=pr_number,
            commit_sha=commit_sha
        )
        print(f"[PR #{pr_number}] Traitement terminé ✅")


handler = WebhookHandler()


@router.post("/webhook", status_code=202)
async def github_webhook(request: Request):
    body = await verify_signature(request, settings.WEBHOOK_SECRET)
    payload = json.loads(body)
    event = request.headers.get("X-GitHub-Event", "")
    asyncio.create_task(handler.handle_webhook(payload, event))
    return JSONResponse(status_code=202, content={"status": "accepted"})