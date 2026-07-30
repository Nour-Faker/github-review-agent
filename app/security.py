import hmac
import hashlib
from fastapi import Request, HTTPException

async def verify_signature(request: Request, secret: str) -> bytes:
    """Vérification HMAC-SHA256 — NF-3."""
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not signature.startswith("sha256="):
        raise HTTPException(status_code=401, detail="Missing signature")

    expected = "sha256=" + hmac.new(
        secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    return body