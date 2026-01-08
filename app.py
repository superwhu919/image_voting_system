# app.py - FastAPI application entry point
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from config import ROOT_ABS, IMAGE_DIR, ON_HF
from web.routes import router

# Create FastAPI app
app = FastAPI(title="Image-Poem Alignment Evaluation")

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
    
    if ON_HF:
        uvicorn.run(app, host="0.0.0.0", port=7860)
    else:
        # Check if running on remote instance (has DATA_ROOT env var)
        if os.getenv("DATA_ROOT"):
            uvicorn.run("app:app", host="0.0.0.0", port=7860, reload=True)
        else:
            uvicorn.run("app:app", host="127.0.0.1", port=7860, reload=True)
