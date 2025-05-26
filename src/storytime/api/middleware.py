import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("storytime.api.middleware")

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        api_key = request.headers.get("x-api-key", "<none>")
        logger.info(f"Request: {request.method} {request.url.path} | API Key: {api_key}")
        response: Response = await call_next(request)
        logger.info(f"Response: {request.method} {request.url.path} | Status: {response.status_code} | API Key: {api_key}")
        return response 