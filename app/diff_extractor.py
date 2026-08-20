import httpx
import os
from dataclasses import dataclass, field
from app.database import get_setting  # add this at the top with other imports

@dataclass
class DiffHunk:
    """
    Représente un bloc de modification dans le diff d'une PR.
    'position' = position dans le diff (utilisée par GitHub API pour poster un commentaire inline).
    """
    file: str
    lines: str
    content: str
    position: int = 1  # position réelle dans le diff GitHub


class DiffExtractor:
    """
    NF-5 — Extraction des modifications de code (Diffs)
    Récupère et analyse le diff d'une Pull Request via GitHub API.
    """

    def is_oversized(self, diff: str) -> bool:
        max_lines = int(get_setting("max_diff_lines", "500"))
        return len(diff.split("\n")) > max_lines
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
        """
        Découpe le diff en blocs (hunks) par fichier.
        Calcule la position réelle de chaque hunk dans le diff
        pour que GitHub accepte les commentaires inline (NF-14).
        """
        hunks = []
        current_file = ""
        current_lines = ""
        current_content = []
        current_position = 1   # position globale dans le diff (commence à 1)
        hunk_start_position = 1

        for line in diff.split("\n"):
            if line.startswith("diff --git"):
                # Sauvegarder le fichier précédent
                if current_file and current_content:
                    hunks.append(DiffHunk(
                        file=current_file,
                        lines=current_lines,
                        content="\n".join(current_content),
                        position=hunk_start_position
                    ))
                current_file = line.split(" b/")[-1]
                current_content = []
                current_lines = ""

            elif line.startswith("@@"):
                # Nouvelle hunk header — on mémorise la position de départ
                current_lines = line
                hunk_start_position = current_position

            else:
                current_content.append(line)

            current_position += 1

        # Ajouter le dernier bloc
        if current_file and current_content:
            hunks.append(DiffHunk(
                file=current_file,
                lines=current_lines,
                content="\n".join(current_content),
                position=hunk_start_position
            ))

        return hunks