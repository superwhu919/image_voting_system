# app.py - FastAPI application entry point
import time
import uuid
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from config import IMAGE_DIR, PROFILING_ENABLED
from web.routes import router

# Create FastAPI app
app = FastAPI(title="Image-Poem Alignment Evaluation")


class ProfilingMiddleware(BaseHTTPMiddleware):
    """When PROFILING_ENABLED=1, set request_id and log request duration."""

    async def dispatch(self, request: Request, call_next):
        if not PROFILING_ENABLED:
            return await call_next(request)
        request_id = uuid.uuid4().hex[:8]
        from utils.profiling import set_request_id, logger

        set_request_id(request_id)
        t0 = time.perf_counter()
        try:
            response = await call_next(request)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            path = request.scope.get("path", "")
            method = request.scope.get("method", "")
            status = getattr(response, "status_code", None)
            logger.info(
                "profile %s",
                {
                    "segment": "request",
                    "method": method,
                    "path": path,
                    "ms": round(elapsed_ms, 2),
                    "request_id": request_id,
                    "status": status,
                },
            )
            return response
        finally:
            set_request_id(None)


if PROFILING_ENABLED:
    app.add_middleware(ProfilingMiddleware)

# Mount static files
app.mount("/static", StaticFiles(directory="web/static"), name="static")

# Mount images directory
# Note: We use a custom route in web/routes.py to handle Unicode filenames
# instead of StaticFiles mount, which has issues with Unicode paths
# The route is defined as @router.get("/static/images/{image_path:path}")

# Include routes
app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=7860, reload=True)
