import httpx
from app.config import settings
from app.llm_analyzer import AnalysisResult
from app.diff_extractor import DiffHunk
from app.logger import get_logger
logger = get_logger("commenter")


class CommentValidator:
    """
    CommentValidator — diagramme Classes.
    NF-14 — Commentaires GitHub placés sur des lignes invalides.
    Valide chaque AnalysisResult avant de le poster sur GitHub.
    """

    def validate(self, result: AnalysisResult) -> bool:
        if not result.is_valid:
            return False
        if not result.comment or len(result.comment.strip()) == 0:
            return False
        if len(result.comment) < 10:
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

        CORRECTIF : on utilise hunk.position (calculée par DiffExtractor)
        au lieu de position=1 hardcodé, pour que GitHub accepte les commentaires inline.
        NF-14 — Si position invalide, fallback sur commentaire global.
        """
        comments = []
        fallback_comments = []

        for hunk, result in results:
            if not self.validator.validate(result):
                logger.warning(f"CommentValidator — commentaire invalide sur {hunk.file} ignoré")

                continue

            if hunk.position and hunk.position > 0:
                # ✅ CORRECTIF — position réelle du hunk dans le diff
                comments.append({
                    "path": hunk.file,
                    "position": hunk.position,
                    "body": f"🤖 **AI Review — {hunk.file}**\n\n{result.comment}"
                })
            else:
                # NF-14 — position invalide → on garde pour commentaire global
                fallback_comments.append(f"**{hunk.file}**\n{result.comment}")

        # Poster la review inline si on a des commentaires valides
        if comments:
            review_body = {
                "commit_id": commit_sha,
                "body": "## 🤖 GitHub Review Agent\nRevue automatique générée par l'agent IA.",
                "event": "COMMENT",
                "comments": comments
            }

            url = f"{self.base_url}/repos/{repo}/pulls/{pr_number}/reviews"

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=review_body
                )

            if response.status_code in [200, 201]:
                logger.info(f"GitHubCommenter — review publiée {len(comments)} commentaires inline")

            else:
                logger.error(f"GitHubCommenter — erreur review {response.status_code}: {response.text}")

                # Si la review inline échoue, on poste en fallback global
                fallback_comments = [c["body"] for c in comments] + fallback_comments

        # Poster les commentaires en fallback global (NF-14)
        if fallback_comments:
            body = "## 🤖 GitHub Review Agent\n\n" + "\n\n---\n\n".join(fallback_comments)
            await self.post_single_comment(
                body=body,
                pr_id=str(pr_number),
                repo=repo
            )

        # Aucun commentaire du tout → PR propre
        if not comments and not fallback_comments:
            await self.post_single_comment(
                body="🤖 **GitHub Review Agent**\n\n✅ Aucun problème détecté dans cette PR.",
                pr_id=str(pr_number),
                repo=repo
            )

    async def post_single_comment(
        self,
        body: str,
        pr_id: str,
        repo: str = ""
    ) -> None:
        """
        Post un commentaire global sur la PR (issue comment).
        Utilisé pour : oversized, erreurs, NF-9 mentions, NF-14 fallback.
        """
        url = f"{self.base_url}/repos/{repo}/issues/{pr_id}/comments"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=self.headers,
                json={"body": body}
            )

        if response.status_code == 201:
            logger.info(f"GitHubCommenter — commentaire global posté sur PR #{pr_id}")

        else:
            logger.error(f"GitHubCommenter — erreur commentaire {response.status_code}: {response.text}")