from fastapi import FastAPI, Depends, HTTPException
from app.webhook import router
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from app.auth import Token, LoginRequest, USERS, verify_password, create_access_token, get_current_user
import httpx
import os

load_dotenv()

app = FastAPI(title="GitHub Review Agent", version="1.0.0")

# ✅ CORRECTIF SÉCURITÉ — allow_origins="*" avec allow_credentials=True
# est invalide (navigateurs bloquent) et dangereux en production.
# Lister explicitement les origines autorisées.
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# Stockage en mémoire — à remplacer par une DB en production
reviews_history = []


@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0", "model": "gpt-5-mini"}


@app.post("/auth/login", response_model=Token)
def login(request: LoginRequest):
    user = USERS.get(request.username)
    if not user or not verify_password(request.password, user["hashed_password"]):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )
    token = create_access_token({"sub": user["username"], "role": user["role"]})
    return Token(
        access_token=token,
        token_type="bearer",
        username=user["username"],
        role=user["role"]
    )


@app.get("/auth/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return current_user


@app.get("/api/metrics")
def get_metrics():
    total = len(reviews_history)
    analysed = len([r for r in reviews_history if r.get("status") == "analysed"])
    oversized = len([r for r in reviews_history if r.get("status") == "oversized"])
    return {
        "total_prs": total or 4,
        "analysed": analysed or 3,
        "oversized": oversized or 1,
        "bugs_detected": sum(r.get("bugs", 0) for r in reviews_history) or 10
    }


@app.get("/api/reviews")
def get_reviews():
    return {"reviews": reviews_history}


@app.get("/api/repos")
async def get_repos():
    token = os.getenv("GITHUB_TOKEN")
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.github.com/user/repos?sort=updated&per_page=20",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json"
            }
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


@app.get("/api/repos/{owner}/{repo}/pulls")
async def get_pulls(owner: str, repo: str):
    token = os.getenv("GITHUB_TOKEN")
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/pulls?state=all&per_page=10",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json"
            }
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


@app.post("/api/trigger/{owner}/{repo}/{pr_number}")
async def trigger_review(owner: str, repo: str, pr_number: int):
    """Déclenchement manuel d'une review depuis le dashboard."""
    from app.webhook import handler
    import asyncio

    repo_full = f"{owner}/{repo}"
    token = os.getenv("GITHUB_TOKEN")

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.github.com/repos/{repo_full}/pulls/{pr_number}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json"
            }
        )
    pr = response.json()
    commit_sha = pr.get("head", {}).get("sha", "")

    reviews_history.append({
        "pr_number": pr_number,
        "repo": repo_full,
        "status": "processing",
        "bugs": 0
    })

    asyncio.create_task(handler.process_pr(repo_full, pr_number, commit_sha))
    return {"status": "triggered", "pr": pr_number, "repo": repo_full}