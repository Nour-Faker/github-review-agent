import httpx
import os
from dataclasses import dataclass

@dataclass
class DiffHunk:
    """Représente un bloc de modification dans le diff d'une PR."""
    file: str
    lines: str
    content: str

class DiffExtractor:
    """
    NF-5 — Extraction des modifications de code (Diffs)
    Récupère et analyse le diff d'une Pull Request via GitHub API.
    """

    MAX_LINES = 500

    def __init__(self):
        self.token = os.getenv("GITHUB_TOKEN")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3.diff",
        }

    async def fetch_diff(self, repo: str, pr_number: int) -> str:
        """Récupère le diff brut d'une PR depuis GitHub API."""
        url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers)
        response.raise_for_status()
        return response.text

    def is_oversized(self, diff: str) -> bool:
        """Retourne True si le diff dépasse MAX_LINES lignes."""
        return len(diff.split("\n")) > self.MAX_LINES

    def parse_hunks(self, diff: str) -> list[DiffHunk]:
        """Découpe le diff en blocs (hunks) par fichier."""
        hunks = []
        current_file = ""
        current_lines = ""
        current_content = []

        for line in diff.split("\n"):
            if line.startswith("diff --git"):
                # Nouveau fichier détecté
                if current_file and current_content:
                    hunks.append(DiffHunk(
                        file=current_file,
                        lines=current_lines,
                        content="\n".join(current_content)
                    ))
                current_file = line.split(" b/")[-1]
                current_content = []
            elif line.startswith("@@"):
                current_lines = line
            else:
                current_content.append(line)

        # Ajouter le dernier bloc
        if current_file and current_content:
            hunks.append(DiffHunk(
                file=current_file,
                lines=current_lines,
                content="\n".join(current_content)
            ))

        return hunks