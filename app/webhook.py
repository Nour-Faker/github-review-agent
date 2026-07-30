import json
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.security import verify_signature
from app.diff_extractor import DiffExtractor
from app.rate_limiter import RateLimiter
from app.config import settings

router = APIRouter()

class WebhookHandler:
    """WebhookHandler — diagramme Classes."""

    def __init__(self):
        self.extractor = DiffExtractor()
        self.limiter = RateLimiter()

    def is_bot_sender(self, payload: dict) -> bool:
        """NF-15 — Détecte les bots."""
        sender = payload.get("sender", {})
        is_bot_type = sender.get("type", "") == "Bot"
        is_bot_login = sender.get("login", "").endswith("[bot]")
        return is_bot_type or is_bot_login

    async def handle_webhook(self, payload: dict, event: str) -> None:
        """Traitement principal."""
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
                print(f"[PR #{pr_number}] Début traitement...")
                await self.process_pr(repo, pr_number, commit_sha)

        elif event == "issue_comment":
            await self.handle_mention_comment(payload)

    async def handle_mention_comment(self, payload: dict) -> None:
        """NF-9 — Gestion des mentions @ai-reviewer."""
        from app.commenter import GitHubCommenter
        from app.llm_analyzer import LLMAnalyzer

        comment_body = payload.get("comment", {}).get("body", "")
        repo = payload.get("repository", {}).get("full_name", "")
        pr_number = payload.get("issue", {}).get("number", 0)

        if "@ai-reviewer" not in comment_body:
            return

        if self.is_bot_sender(payload):
            return

        print(f"[NF-9] Mention détectée — PR #{pr_number}")
        question = comment_body.replace("@ai-reviewer", "").strip()
        analyzer = LLMAnalyzer()
        response = analyzer.analyze(f"Question sur PR #{pr_number} : {question}\nRéponds en français.")

        commenter = GitHubCommenter()
        await commenter.post_single_comment(
            body=f"🤖 **@ai-reviewer**\n\n{response}",
            pr_id=str(pr_number),
            repo=repo
        )

    async def process_pr(self, repo: str, pr_number: int, commit_sha: str) -> None:
        """NF-5 + NF-6 + NF-8 + NF-13 + NF-14."""
        from app.llm_analyzer import LLMAnalyzer
        from app.commenter import GitHubCommenter

        commenter = GitHubCommenter()
        analyzer = LLMAnalyzer()

        diff = await self.extractor.fetch_diff(repo, pr_number)

        if self.extractor.is_oversized(diff):
            print(f"[PR #{pr_number}] Diff > {settings.MAX_LINES} lignes — refusé")
            await commenter.post_single_comment(
                body=f"🤖 **GitHub Review Agent**\n\n⚠️ Cette PR dépasse **{settings.MAX_LINES} lignes** — analyse impossible.\n\nMerci de découper cette PR.",
                pr_id=str(pr_number),
                repo=repo
            )
            return

        hunks = self.extractor.parse_hunks(diff)
        print(f"[PR #{pr_number}] {len(hunks)} fichiers extraits")

        if not hunks:
            return

        results = []
        for hunk in hunks:
            self.limiter.check_and_wait_retry()
            result = analyzer.analyze_hunk(hunk)
            print(f"  → {hunk.file} : analysé ({result.is_valid})")
            results.append((hunk, result))

        await commenter.post_review(
            results=results,
            repo=repo,
            pr_number=pr_number,
            commit_sha=commit_sha
        )
        print(f"[PR #{pr_number}] Sprint 3 terminé ✅")


handler = WebhookHandler()


@router.post("/webhook", status_code=202)
async def github_webhook(request: Request):
    """Point d'entrée webhook."""
    body = await verify_signature(request, settings.WEBHOOK_SECRET)
    payload = json.loads(body)
    event = request.headers.get("X-GitHub-Event", "")
    print(f"[Webhook] Event reçu: {event}")
    await handler.handle_webhook(payload, event)
    return JSONResponse(status_code=202, content={"status": "accepted"})