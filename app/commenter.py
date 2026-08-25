# -*- coding: utf-8 -*-
import httpx
from app.config import settings
from app.llm_analyzer import AnalysisResult
from app.diff_extractor import DiffHunk
from app.logger import get_logger

logger = get_logger("commenter")

SEVERITY_EMOJI = {
    "critical": "🔴",
    "warning": "🟠",
    "info": "💡",
}

class CommentValidator:
    def validate(self, result: AnalysisResult) -> bool:
        if not result.is_valid:
            return False
        if not result.comment or len(result.comment.strip()) == 0:
            return False
        if len(result.comment) < 10:
            return False
        return True


class GitHubCommenter:
    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        self.base_url = "https://api.github.com"
        self.validator = CommentValidator()

    def _format_comment(self, hunk: DiffHunk, result: AnalysisResult) -> str:
        emoji = SEVERITY_EMOJI.get(getattr(result, "severity", "info"), "💡")
        category = getattr(result, "category", "style").upper()
        return f"{emoji} **AI Review [{category}] — {hunk.file}**\n\n{result.comment}"

    async def post_review(
        self,
        results: list[tuple[DiffHunk, AnalysisResult]],
        repo: str = "",
        pr_number: int = 0,
        commit_sha: str = ""
    ) -> None:
        comments = []
        fallback_comments = []

        for hunk, result in results:
            if not self.validator.validate(result):
                logger.warning(f"CommentValidator - commentaire invalide sur {hunk.file} ignore")
                continue

            body = self._format_comment(hunk, result)

            if hunk.position and hunk.position > 0:
                comments.append({
                    "path": hunk.file,
                    "position": hunk.position,
                    "body": body
                })
            else:
                fallback_comments.append(body)

        if comments:
            review_body = {
                "commit_id": commit_sha,
                "body": "## 🤖 GitHub Review Agent\nRevue automatique generee par l'agent IA.",
                "event": "COMMENT",
                "comments": comments
            }
            url = f"{self.base_url}/repos/{repo}/pulls/{pr_number}/reviews"
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self.headers, json=review_body)

            if response.status_code in [200, 201]:
                logger.info(f"GitHubCommenter - review publiee {len(comments)} commentaires inline")
            else:
                logger.error(f"GitHubCommenter - erreur review {response.status_code}: {response.text}")
                fallback_comments = [c["body"] for c in comments] + fallback_comments

        if fallback_comments:
            body = "## 🤖 GitHub Review Agent\n\n" + "\n\n---\n\n".join(fallback_comments)
            await self.post_single_comment(body=body, pr_id=str(pr_number), repo=repo)

        if not comments and not fallback_comments:
            await self.post_single_comment(
                body="🤖 **GitHub Review Agent**\n\n✅ Aucun probleme detecte dans cette PR.",
                pr_id=str(pr_number),
                repo=repo
            )

    async def post_single_comment(self, body: str, pr_id: str, repo: str = "") -> None:
        url = f"{self.base_url}/repos/{repo}/issues/{pr_id}/comments"
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=self.headers, json={"body": body})
        if response.status_code == 201:
            logger.info(f"GitHubCommenter - commentaire global poste sur PR #{pr_id}")
        else:
            logger.error(f"GitHubCommenter - erreur commentaire {response.status_code}: {response.text}")
