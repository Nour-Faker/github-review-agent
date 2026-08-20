import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.logger import get_logger

logger = get_logger("http")

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        duration = (time.time() - start) * 1000
        logger.info(f"{request.method} {request.url.path} {response.status_code} {duration:.0f}ms")
        return response
