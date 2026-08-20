from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv
from app.routers import auth, api, ws
from app.webhook import router as webhook_router
from app.middleware.logging import LoggingMiddleware
from app.database import init_db
from app.database import get_metrics as db_get_metrics
from app.logger import get_logger
import pathlib
import os

load_dotenv()
logger = get_logger("main")

BASE_DIR = pathlib.Path(__file__).parent.parent
STATIC_DIR = BASE_DIR / "static"

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
        logger.info("DB ready")
    except Exception as e:
        logger.error(f"DB startup failed: {e}")
    yield

app = FastAPI(title="GitHub Review Agent", version="1.0.0", lifespan=lifespan)

# Rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Middleware
app.add_middleware(LoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
if STATIC_DIR.exists():
    assets_dir = STATIC_DIR / "static"
    if assets_dir.exists():
        app.mount("/static", StaticFiles(directory=str(assets_dir)), name="static-assets")

# Routers
app.include_router(auth.router)
app.include_router(api.router)
app.include_router(ws.router)
app.include_router(webhook_router)

@app.get("/")
def root():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"status": "ok", "api": "github-review-agent"}

@app.get("/health")
async def health():
    import httpx
    from app.database import get_metrics as db_get_metrics
    result = {"status": "ok", "version": "1.0", "model": os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5-mini"), "dependencies": {}}
    try:
        db_get_metrics()
        result["dependencies"]["database"] = "ok"
    except Exception as e:
        result["dependencies"]["database"] = f"error: {str(e)}"
        result["status"] = "degraded"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.get(os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/") + "/")
        result["dependencies"]["openai"] = "reachable"
    except Exception:
        result["dependencies"]["openai"] = "unreachable"
    return result