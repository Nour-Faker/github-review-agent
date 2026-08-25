import os
import httpx
from fastapi import APIRouter, HTTPException, Request
from app.database import get_all_reviews, get_metrics as db_get_metrics
from app.logger import get_logger
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = get_logger("api")
router = APIRouter(prefix="/api")
limiter = Limiter(key_func=get_remote_address)

GITHUB_HEADERS = lambda: {
    "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}",
    "Accept": "application/vnd.github.v3+json"
}

@router.get("/metrics")
@limiter.limit("60/minute")
def get_metrics(request: Request):
    try:
        return db_get_metrics()
    except Exception as e:
        logger.error(f"DB metrics error: {e}")
        return {"total_prs": 0, "analysed": 0, "oversized": 0, "bugs_detected": 0}

@router.get("/reviews")
@limiter.limit("60/minute")
def get_reviews(request: Request):
    try:
        return {"reviews": get_all_reviews()}
    except Exception as e:
        logger.error(f"DB reviews error: {e}")
        return {"reviews": []}

@router.get("/repos")
@limiter.limit("30/minute")
async def get_repos(request: Request):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.github.com/user/repos?sort=updated&per_page=20",
            headers=GITHUB_HEADERS()
        )
    repos = response.json()
    return {
        "repos": [
            {
                "name": r["full_name"],
                "private": r["private"],
                "stars": r["stargazers_count"],
                "language": r["language"],
                "updated": r["updated_at"]
            }
            for r in repos if isinstance(r, dict)
        ]
    }

@router.get("/repos/{owner}/{repo}/pulls")
@limiter.limit("30/minute")
async def get_pulls(request: Request, owner: str, repo: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/pulls?state=all&per_page=10",
            headers=GITHUB_HEADERS()
        )
    pulls = response.json()
    if not isinstance(pulls, list):
        return {"pulls": []}
    return {
        "pulls": [
            {
                "number": p["number"],
                "title": p["title"],
                "state": p["state"],
                "user": p["user"]["login"],
                "created_at": p["created_at"],
                "head_sha": p["head"]["sha"]
            }
            for p in pulls
        ]
    }

@router.post("/trigger/{owner}/{repo}/{pr_number}")
async def trigger_review(owner: str, repo: str, pr_number: int):
    import asyncio
    from app.webhook import handler
    repo_full = f"{owner}/{repo}"
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.github.com/repos/{repo_full}/pulls/{pr_number}",
            headers=GITHUB_HEADERS()
        )
    pr = response.json()
    commit_sha = pr.get("head", {}).get("sha", "")
    asyncio.create_task(handler.process_pr(repo_full, pr_number, commit_sha))
    return {"status": "triggered", "pr": pr_number, "repo": repo_full}

@router.post("/summarize/{owner}/{repo}/{pr_number}")
@limiter.limit("10/minute")
async def summarize_pr(request: Request, owner: str, repo: str, pr_number: int):
    from app.diff_extractor import DiffExtractor
    from app.llm_analyzer import LLMAnalyzer
    extractor = DiffExtractor()
    analyzer = LLMAnalyzer()
    try:
        diff = await extractor.fetch_diff(f"{owner}/{repo}", pr_number)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Impossible de recuperer le diff: {e}")
    if extractor.is_oversized(diff):
        raise HTTPException(status_code=413, detail="PR trop grande pour etre resumee.")
    hunks = extractor.parse_hunks(diff)
    if not hunks:
        return {"summary": "Aucune modification detectee dans cette PR."}
    context = f"Voici les modifications de la PR #{pr_number} sur {owner}/{repo}:\n\n"
    for hunk in hunks[:10]:
        context += f"### {hunk.file}\n{hunk.content[:500]}\n\n"
    context += """
Genere un resume structure en francais avec :
1. Objectif — ce que fait cette PR en une phrase
2. Fichiers modifies — liste des fichiers cles
3. Points positifs — bonnes pratiques observees
4. Risques — bugs potentiels ou points d attention
5. Verdict — APPROUVER / DEMANDER DES MODIFICATIONS
"""
    summary = analyzer.analyze(context)
    return {"pr": f"{owner}/{repo}#{pr_number}", "files_analysed": len(hunks), "summary": summary}

from app.database import get_setting, save_setting
from pydantic import BaseModel

class SettingsPayload(BaseModel):
    max_diff_lines: int

@router.get("/settings")
def get_settings(request: Request):
    return {
        "max_diff_lines": int(get_setting("max_diff_lines", "500"))
    }

@router.patch("/settings")
def update_settings(payload: SettingsPayload, request: Request):
    save_setting("max_diff_lines", str(payload.max_diff_lines))
    return {"status": "saved", "max_diff_lines": payload.max_diff_lines}