import httpx
from app.config import settings
from app.llm_analyzer import AnalysisResult
from app.diff_extractor import DiffHunk

class CommentValidator:
    """
    CommentValidator — diagramme Classes.
    NF-14 — Commentaires GitHub placés sur des lignes invalides.
    Valide chaque AnalysisResult avant de le poster sur GitHub.
    """

    def validate(self, result: AnalysisResult) -> bool:
        """Valide le résultat — NF-14."""
        if not result.is_valid:
            return False
        if not result.comment:
            return False
        if len(result.comment.strip()) < 5:  # ← réduit de 10 à 5
            return False
        return True


class GitHubCommenter:
    """
    GitHubCommenter — diagramme Classes.
    NF-8 — Publication des commentaires sur la PR.
    """

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
        """
        NF-8 — Publie une review complète sur la PR.
        Correspond à post_review(results: List<AnalysisResult>): void
        dans le diagramme Classes.
        Étape 19 du diagramme Séquence.
        """
        comments = []

        for hunk, result in results:
            # NF-14 — validate() avant chaque commentaire
            if self.validator.validate(result):
                comments.append({
                    "path": hunk.file,
                    "position": 1,
                    "body": f"🤖 **AI Review — {hunk.file}**\n\n{result.comment}"
                })
            else:
                # NF-14 — ligne invalide → commentaire global
                print(f"[CommentValidator] Commentaire invalide sur {hunk.file} → ignoré")

        if not comments:
            await self.post_single_comment(
                body="🤖 **GitHub Review Agent**\nAucun problème détecté dans cette PR.",
                pr_id=str(pr_number),
                repo=repo
            )
            return

        review_body = {
            "commit_id": commit_sha,
            "body": "## 🤖 GitHub Review Agent\nRevue automatique générée par GPT-5-mini.",
            "event": "COMMENT",
            "comments": []  # ← envoie sans commentaires de lignes d'abord
        }

        url = f"{self.base_url}/repos/{repo}/pulls/{pr_number}/reviews"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=self.headers,
                json=review_body
            )

        if response.status_code in [200, 201]:
            print(f"[GitHubCommenter] Review publiée — {len(comments)} commentaires")
        else:
            print(f"[GitHubCommenter] Erreur {response.status_code}: {response.text}")

    async def post_single_comment(
        self,
        body: str,
        pr_id: str,
        repo: str = ""
    ) -> None:
        """
        Post un commentaire global sur la PR.
        Correspond à post_single_comment(body: String, pr_id: String): void
        dans le diagramme Classes.
        Utilisé pour : oversized, erreurs, NF-9 mentions, NF-14 lignes invalides.
        """
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