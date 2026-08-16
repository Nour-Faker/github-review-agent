from fastapi import FastAPI, HTTPException
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

# React router fallback — toutes les routes inconnues servent index.html
@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    # Ne pas interférer avec les routes API et webhook
    if full_path.startswith(("api/", "auth/", "webhook", "health", "docs", "openapi")):
        raise HTTPException(status_code=404)
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    raise HTTPException(status_code=404)


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
def login(request: LoginRequest):
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


@app.get("/api/metrics")
def get_metrics():
    try:
        return db_get_metrics()
    except Exception as e:
        logger.error(f"DB metrics error: {e}")
        return {"total_prs": 0, "analysed": 0, "oversized": 0, "bugs_detected": 0}


@app.get("/api/reviews")
def get_reviews():
    try:
        return {"reviews": get_all_reviews()}
    except Exception as e:
        logger.error(f"DB reviews error: {e}")
        return {"reviews": []}


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