from fastapi import FastAPI
from app.webhook import router
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="GitHub Review Agent", version="0.1.0")
app.include_router(router)

@app.get("/health")
def health():
    return {"status": "ok"}