# -*- coding: utf-8 -*-
import json
import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.security import verify_signature
from app.diff_extractor import DiffExtractor
from app.rate_limiter import RateLimiter
from app.config import settings
from app.logger import get_logger

logger = get_logger("webhook")
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
            logger.info("WebhookHandler - bot detecte ignore")
            return

        sender = payload.get("sender", {}).get("login", "unknown")
        if not self.limiter.check_quota(sender):
            logger.info("WebhookHandler - quota depasse ignore")
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
        from app.commenter import GitHubCommenter
        from app.llm_analyzer import LLMAnalyzer

        comment_body = payload.get("comment", {}).get("body", "")
        repo = payload.get("repository", {}).get("full_name", "")
        pr_number = payload.get("issue", {}).get("number", 0)

        if "@ai-reviewer" not in comment_body:
            return
        if comment_body.startswith("🤖"):
            return
        if self.is_bot_sender(payload):
            return

        logger.info(f"NF-9 - mention @ai-reviewer detectee sur PR #{pr_number}")

        question = comment_body.replace("@ai-reviewer", "").strip()

        try:
            diff = await self.extractor.fetch_diff(repo, pr_number)
        except Exception as e:
            logger.error(f"NF-9 - impossible de recuperer le diff: {e}")
            diff = ""

        if not diff or self.extractor.is_oversized(diff):
            diff_context = "(diff non disponible ou trop volumineux)"
        else:
            diff_context = diff[:3000]

        context = f"""Tu es un expert en revue de code.

Un developpeur pose cette question sur la PR #{pr_number} :
"{question}"

Voici le diff de la PR :
---
{diff_context}
---

Reponds directement a la question en te basant sur le code.
Sois concis et professionnel. Reponds en francais."""

        analyzer = LLMAnalyzer()
        response = analyzer.analyze(context)

        if not response or not response.strip():
            response = "Analyse effectuee - aucun probleme critique detecte."

        commenter = GitHubCommenter()
        await commenter.post_single_comment(
            body=f"🤖 **@ai-reviewer**\n\n{response}",
            pr_id=str(pr_number),
            repo=repo
        )

    async def process_pr(self, repo: str, pr_number: int, commit_sha: str) -> None:
        from app.llm_analyzer import LLMAnalyzer
        from app.commenter import GitHubCommenter
        from app.database import save_review, update_review

        commenter = GitHubCommenter()
        analyzer = LLMAnalyzer()

        logger.info(f"PR #{pr_number} - debut traitement")

        save_review(pr_number=pr_number, repo=repo, status="processing", bugs=0)

        diff = await self.extractor.fetch_diff(repo, pr_number)

        if self.extractor.is_oversized(diff):
            logger.warning(f"PR #{pr_number} - diff > {settings.MAX_LINES} lignes refuse")
            update_review(pr_number=pr_number, repo=repo, status="oversized", bugs=0)
            await commenter.post_single_comment(
                body=f"🤖 **GitHub Review Agent**\n\n⚠️ Cette PR depasse la limite de **{settings.MAX_LINES} lignes**.",
                pr_id=str(pr_number),
                repo=repo
            )
            return

        hunks = self.extractor.parse_hunks(diff)
        logger.info(f"PR #{pr_number} - {len(hunks)} fichiers extraits")

        if not hunks:
            update_review(pr_number=pr_number, repo=repo, status="analysed", bugs=0)
            await commenter.post_single_comment(
                body="🤖 **GitHub Review Agent**\n\nAucune modification detectee.",
                pr_id=str(pr_number),
                repo=repo
            )
            return

        async def analyze_one(hunk):
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, analyzer.analyze_hunk, hunk)
            logger.info(f"  -> {hunk.file} analyse (valide={result.is_valid})")
            return (hunk, result)

        raw_results = await asyncio.gather(*[analyze_one(hunk) for hunk in hunks])
        results = list(raw_results)

        critical_count = sum(1 for _, r in results if r.severity == "critical")
        warning_count  = sum(1 for _, r in results if r.severity == "warning")
        total_bugs     = critical_count + warning_count

        await commenter.post_review(
            results=results,
            repo=repo,
            pr_number=pr_number,
            commit_sha=commit_sha
        )

        update_review(pr_number=pr_number, repo=repo, status="analysed", bugs=total_bugs,
                      critical_count=critical_count, warning_count=warning_count)

        logger.info(f"PR #{pr_number} - traitement termine")

        try:
            from app.main import manager
            asyncio.create_task(manager.broadcast({
                "event": "review_completed",
                "pr_number": pr_number,
                "repo": repo,
                "bugs": total_bugs
            }))
        except Exception as e:
            logger.warning(f"WebSocket broadcast failed: {e}")


handler = WebhookHandler()


@router.post("/webhook", status_code=202)
async def github_webhook(request: Request):
    body = await verify_signature(request, settings.WEBHOOK_SECRET)
    payload = json.loads(body)
    event = request.headers.get("X-GitHub-Event", "")
    asyncio.create_task(handler.handle_webhook(payload, event))
    return JSONResponse(status_code=202, content={"status": "accepted"})

