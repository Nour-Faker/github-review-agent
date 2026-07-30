import httpx
from app.config import settings
from app.llm_analyzer import AnalysisResult
from app.diff_extractor import DiffHunk

class CommentValidator:
    """CommentValidator — NF-14."""

    def validate(self, result: AnalysisResult) -> bool:
        """Valide le résultat avant de poster."""
        if not result.is_valid:
            return False
        if not result.comment:
            return False
        if len(result.comment.strip()) < 5:
            return False
        return True

class GitHubCommenter:
    """GitHubCommenter — NF-8."""

    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        self.base_url = "https://api.github.com"
        self.validator = CommentValidator()

    async def post_review(
        self,
        results: list[tuple[DiffHunk, AnalysisResult]],
        repo: str = "",
        pr_number: int = 0,
        commit_sha: str = ""
    ) -> None:
        """NF-8 — Publie un commentaire global sur la PR."""
        body = "## 🤖 GitHub Review Agent\n\n"

        for hunk, result in results:
            if self.validator.validate(result):
                body += f"### 📁 `{hunk.file}`\n\n"
                body += f"{result.comment}\n\n"
                body += "---\n\n"

        if body == "## 🤖 GitHub Review Agent\n\n":
            body += "✅ Aucun problème détecté dans cette PR."

        await self.post_single_comment(
            body=body,
            pr_id=str(pr_number),
            repo=repo
        )
        print(f"[GitHubCommenter] Commentaire posté sur PR #{pr_number}")

    async def post_single_comment(
        self,
        body: str,
        pr_id: str,
        repo: str = ""
    ) -> None:
        """Post un commentaire global."""
        url = f"{self.base_url}/repos/{repo}/issues/{pr_id}/comments"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=self.headers,
                json={"body": body}
            )

        if response.status_code == 201:
            print(f"[GitHubCommenter] Commentaire global posté sur PR #{pr_id}")
        else:
            print(f"[GitHubCommenter] Erreur {response.status_code}: {response.text}")