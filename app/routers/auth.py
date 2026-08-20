from fastapi import APIRouter, HTTPException, Request
from app.auth import Token, LoginRequest, USERS, verify_password, create_access_token
from app.logger import get_logger
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = get_logger("auth")
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

@router.post("/auth/login", response_model=Token)
@limiter.limit("5/minute")
def login(request: Request, body: LoginRequest):
    user = USERS.get(body.username)
    if not user or not verify_password(body.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token({"sub": user["username"], "role": user["role"]})
    logger.info(f"Login reussi pour {body.username}")
    return Token(
        access_token=token,
        token_type="bearer",
        username=user["username"],
        role=user["role"]
    )
