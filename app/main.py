from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.auth import Token, LoginRequest, USERS, verify_password, create_access_token
from app.webhook import router
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db, save_review, get_all_reviews, get_metrics as db_get_metrics
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import httpx
import os
import logging
import json
import pathlib

# ── Logs JSON structurés ──────────────────────────────────────────────────────
class JSONFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        })

_handler = logging.StreamHandler()
_handler.setFormatter(JSONFormatter())
logging.root.setLevel(logging.INFO)
logging.root.handlers = [_handler]
logger = logging.getLogger("github_review_agent")

load_dotenv()

# ── Chemins ───────────────────────────────────────────────────────────────────
BASE_DIR = pathlib.Path(__file__).parent.parent
STATIC_DIR = BASE_DIR / "static"                 # build React

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="GitHub Review Agent", version="1.0.0")

# Rate limiting (NF-19)
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
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

# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
def startup():
    try:
        init_db()
        logger.info("DB ready")
    except Exception as e:
        logger.error(f"DB startup failed: {e}")

# ── Static files React (assets JS/CSS) ───────────────────────────────────────
if STATIC_DIR.exists():
    # Assets JS/CSS dans static/static/
    assets_dir = STATIC_DIR / "static"
    if assets_dir.exists():
        app.mount("/static", StaticFiles(directory=str(assets_dir)), name="static-assets")


# ── Webhook router ────────────────────────────────────────────────────────────
app.include_router(router)

# ── Stockage temporaire ───────────────────────────────────────────────────────
reviews_history = []

# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"status": "ok", "api": "github-review-agent"}




@app.get("/health")
async def health():
    result = {
        "status": "ok",
        "version": "1.0",
        "model": os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5-mini"),
        "dependencies": {}
    }
    # Check DB
    try:
        db_get_metrics()
        result["dependencies"]["database"] = "ok"
    except Exception as e:
        result["dependencies"]["database"] = f"error: {str(e)}"
        result["status"] = "degraded"
    # Check Azure OpenAI
    try:
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.get(azure_endpoint.rstrip("/") + "/")
        result["dependencies"]["openai"] = "reachable"
    except Exception:
        result["dependencies"]["openai"] = "unreachable"
    return result


@app.post("/auth/login", response_model=Token)
@limiter.limit("5/minute")
def login(request: Request, body: LoginRequest):
    user = USERS.get(request.username)
    if not user or not verify_password(request.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token({"sub": user["username"], "role": user["role"]})
    return Token(
        access_token=token,
        token_type="bearer",
        username=user["username"],
        role=user["role"]
    )


# Route metrics — 60/minute
@app.get("/api/metrics")
@limiter.limit("60/minute")
def get_metrics(request: Request):
    try:
        return db_get_metrics()
    except Exception as e:
        logger.error(f"DB metrics error: {e}")
        return {"total_prs": 0, "analysed": 0, "oversized": 0, "bugs_detected": 0}


# Route reviews — 60/minute  
@app.get("/api/reviews")
@limiter.limit("60/minute")
def get_reviews(request: Request):
    try:
        return {"reviews": get_all_reviews()}
    except Exception as e:
        logger.error(f"DB reviews error: {e}")
        return {"reviews": []}


# Route repos — 30/minute (appels GitHub API)
@app.get("/api/repos")
@limiter.limit("30/minute")
async def get_repos(request: Request):
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


# Route pulls — 30/minute
@app.get("/api/repos/{owner}/{repo}/pulls")
@limiter.limit("30/minute")
async def get_pulls(request: Request, owner: str, repo: str):
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

@app.post("/api/summarize/{owner}/{repo}/{pr_number}")
@limiter.limit("10/minute")
async def summarize_pr(request: Request, owner: str, repo: str, pr_number: int):
    """NF-28 — Résumé automatique de PR en langage naturel."""
    from app.diff_extractor import DiffExtractor
    from app.llm_analyzer import LLMAnalyzer

    extractor = DiffExtractor()
    analyzer = LLMAnalyzer()

    try:
        diff = await extractor.fetch_diff(f"{owner}/{repo}", pr_number)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Impossible de récupérer le diff: {e}")

    if extractor.is_oversized(diff):
        raise HTTPException(status_code=413, detail="PR trop grande pour être résumée.")

    hunks = extractor.parse_hunks(diff)
    if not hunks:
        return {"summary": "Aucune modification détectée dans cette PR."}

    # Construit un contexte global
    context = f"Voici les modifications de la PR #{pr_number} sur {owner}/{repo}:\n\n"
    for hunk in hunks[:10]:  # max 10 fichiers
        context += f"### {hunk.file}\n{hunk.content[:500]}\n\n"

    context += """
Génère un résumé structuré en français avec :
1. **Objectif** — ce que fait cette PR en une phrase
2. **Fichiers modifiés** — liste des fichiers clés
3. **Points positifs** — bonnes pratiques observées
4. **Risques** — bugs potentiels ou points d'attention
5. **Verdict** — APPROUVER / DEMANDER DES MODIFICATIONS
"""

    summary = analyzer.analyze(context)
    return {
        "pr": f"{owner}/{repo}#{pr_number}",
        "files_analysed": len(hunks),
        "summary": summary
    }