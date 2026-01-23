# FastAPI route handlers
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, FileResponse
from starlette.templating import Jinja2Templates
from pydantic import BaseModel
from pathlib import Path
import os
from urllib.parse import unquote
from urllib.parse import unquote

from config import IMAGE_DIR
from core import start_session, reveal_poem, update_phase2_answer, submit_evaluation, remaining
from core.evaluation import IMAGE_SELECTION_SYSTEM
from data_logic.catalog import CATALOG
from data_logic.storage import get_coverage_metrics, increase_user_limit, get_recent_completed_ratings


# Request models
class StartRequest(BaseModel):
    user_id: str
    age: int = None
    gender: str = ""
    education: str = ""


class RevealRequest(BaseModel):
    user_id: str
    poem_title: str
    image_path: str
    options_dict: dict
    target_letter: str
    phase1_choice: str
    phase1_answers: dict = {}
    phase1_start_ms: str


class UpdateAnswerRequest(BaseModel):
    q_id: str
    answer: str
    phase2_answers: dict


class SubmitRequest(BaseModel):
    user_id: str
    user_age: int = None
    user_gender: str = ""
    user_education: str = ""
    poem_title: str
    image_path: str
    image_type: str = ""  # gpt, mj, nano, or seedream
    options_dict: dict
    target_letter: str
    phase1_choice: str
    phase1_answers: dict = {}
    phase1_response_ms: int
    phase2_answers: dict
    phase2_start_ms: str
    phase1_start_ms: str


class IncreaseLimitRequest(BaseModel):
    user_id: str

# Setup templates
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main page."""
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/images/{image_path:path}")
async def serve_image(image_path: str):
    """Serve images with proper Unicode filename handling."""
    try:
        # Decode URL-encoded path
        decoded_path = unquote(image_path)
        
        # Construct full file path
        # Handle both relative paths and just filenames
        if os.path.isabs(decoded_path):
            file_path = Path(decoded_path)
        else:
            # Try as relative to IMAGE_DIR first
            file_path = Path(IMAGE_DIR) / decoded_path
            # If that doesn't exist, try as just filename
            if not file_path.exists():
                file_path = Path(IMAGE_DIR) / os.path.basename(decoded_path)
        
        # Verify file exists and is within IMAGE_DIR for security
        file_path = file_path.resolve()
        image_dir_resolved = Path(IMAGE_DIR).resolve()
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"Image not found: {decoded_path}")
        
        # Security check: ensure file is within IMAGE_DIR
        try:
            file_path.relative_to(image_dir_resolved)
        except ValueError:
            raise HTTPException(status_code=403, detail="Access denied")
        
        return FileResponse(str(file_path))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error serving image: {str(e)}")


@router.post("/api/start")
async def api_start(request: StartRequest):
    """Start new evaluation session."""
    try:
        result = start_session(
            request.user_id,
            user_age=request.age,
            user_gender=request.gender or "",
            user_education=request.education or ""
        )
        # Store user info in result for frontend
        result["user_age"] = request.age
        result["user_gender"] = request.gender
        result["user_education"] = request.education
        
        # Convert image path to URL
        if result.get("status") == "success" and result.get("image_path"):
            image_path = result["image_path"]
            # Get relative path for serving
            if os.path.isabs(image_path):
                # Try to get relative to IMAGE_DIR
                try:
                    rel_path = os.path.relpath(image_path, IMAGE_DIR)
                    # Normalize path separators for URL (use forward slashes)
                    rel_path = rel_path.replace("\\", "/")
                    result["image_url"] = f"/images/{rel_path}"
                except ValueError:
                    # If can't make relative, use filename only
                    filename = os.path.basename(image_path)
                    result["image_url"] = f"/images/{filename}"
            else:
                # Normalize path separators for URL
                normalized_path = image_path.replace("\\", "/")
                result["image_url"] = f"/images/{normalized_path}"
        
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/reveal")
async def api_reveal(request: RevealRequest):
    """Reveal correct answer and show Phase 2."""
    try:
        result = reveal_poem(
            uid=request.user_id,
            poem_title=request.poem_title,
            image_path=request.image_path,
            options_dict=request.options_dict,
            target_letter=request.target_letter,
            phase1_choice=request.phase1_choice,
            phase1_answers=request.phase1_answers,
            phase1_start_ms=request.phase1_start_ms,
        )
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/update-answer")
async def api_update_answer(request: UpdateAnswerRequest):
    """Update a Phase 2 answer."""
    try:
        result = update_phase2_answer(
            q_id=request.q_id,
            answer=request.answer,
            phase2_answers=request.phase2_answers,
        )
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/submit")
async def api_submit(request: SubmitRequest):
    """Submit complete evaluation."""
    try:
        result = submit_evaluation(
            uid=request.user_id,
            user_age=request.user_age,
            user_gender=request.user_gender,
            user_education=request.user_education,
            poem_title=request.poem_title,
            image_path=request.image_path,
            image_type=request.image_type,
            options_dict=request.options_dict,
            target_letter=request.target_letter,
            phase1_choice=request.phase1_choice,
            phase1_answers=request.phase1_answers,
            phase1_response_ms=request.phase1_response_ms,
            phase2_answers=request.phase2_answers,
            phase2_start_ms=request.phase2_start_ms,
            phase1_start_ms=request.phase1_start_ms,
        )
        
        # Convert image path to URL
        if result.get("status") == "success" and result.get("image_path"):
            image_path = result["image_path"]
            if os.path.isabs(image_path):
                try:
                    rel_path = os.path.relpath(image_path, IMAGE_DIR)
                    # Normalize path separators for URL (use forward slashes)
                    rel_path = rel_path.replace("\\", "/")
                    result["image_url"] = f"/images/{rel_path}"
                except ValueError:
                    filename = os.path.basename(image_path)
                    result["image_url"] = f"/images/{filename}"
            else:
                # Normalize path separators for URL
                normalized_path = image_path.replace("\\", "/")
                result["image_url"] = f"/images/{normalized_path}"
        
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/remaining/{user_id}")
async def api_remaining(user_id: str):
    """Get remaining evaluations count for a user."""
    try:
        count = remaining(user_id)
        return JSONResponse(content={"remaining": count})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/increase-limit")
async def api_increase_limit(request: IncreaseLimitRequest):
    """Increase user's limit by 5."""
    try:
        new_limit = increase_user_limit(request.user_id, increment=5)
        return JSONResponse(content={
            "status": "success",
            "message": f"您的限制已增加到 {new_limit}。",
            "new_limit": new_limit
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/debug/questions")
async def api_debug_questions():
    """Debug endpoint to check loaded questions."""
    from core.session import QUESTIONS, PHASE2_QUESTION_IDS
    return JSONResponse(content={
        "total_questions": len(QUESTIONS),
        "question_ids": sorted(QUESTIONS.keys()),
        "phase2_question_ids": PHASE2_QUESTION_IDS,
        "q13_exists": "q13" in QUESTIONS,
        "q13_data": QUESTIONS.get("q13", "NOT FOUND")
    })


@router.get("/api/coverage")
async def api_coverage():
    """Get coverage metrics based on database (persistent across restarts)."""
    try:
        total_images = len(CATALOG)
        metrics = get_coverage_metrics(total_images)
        
        # All metrics are now database-based and persistent
        # Removed queue-based metrics as they are in-memory only
        
        return JSONResponse(content=metrics)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/queue", response_class=HTMLResponse)
async def admin_queue(request: Request):
    """Hidden admin page to view current queue state."""
    try:
        queue_state = IMAGE_SELECTION_SYSTEM.get_queue_state()
        stats = IMAGE_SELECTION_SYSTEM.get_statistics()
        completed_ratings = get_recent_completed_ratings(limit=200)  # Get last 200 completed ratings
        
        return templates.TemplateResponse("queue_debug.html", {
            "request": request,
            "queue_state": queue_state,
            "stats": stats,
            "completed_ratings": completed_ratings
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/admin/queue")
async def api_admin_queue():
    """API endpoint to get queue state as JSON."""
    try:
        queue_state = IMAGE_SELECTION_SYSTEM.get_queue_state()
        stats = IMAGE_SELECTION_SYSTEM.get_statistics()
        completed_ratings = get_recent_completed_ratings(limit=200)
        return JSONResponse(content={
            "queue_state": queue_state,
            "statistics": stats,
            "completed_ratings": completed_ratings
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

