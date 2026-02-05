# app.py - FastAPI application entry point
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from config import IMAGE_DIR
from web.routes import router
from web.submit_log_context import submit_client_ip, submit_request_id, submit_user_id


class SubmitTimingFormatter(logging.Formatter):
    """Prepend request_id, ip, user_id to each submit_timing log line."""

    def format(self, record):
        request_id = submit_request_id.get()
        client_ip = submit_client_ip.get()
        user_id = submit_user_id.get()
        prefix = f"[request_id={request_id}] [ip={client_ip}] [user_id={user_id}] "
        msg = record.getMessage()
        record.msg = prefix + msg
        record.args = ()
        return super().format(record)


# Configure submit_timing logger to write to a dedicated file
_log_dir = Path(__file__).resolve().parent / "logs"
_log_dir.mkdir(exist_ok=True)
_submit_timing_log = _log_dir / "submit_timing.log"
_submit_logger = logging.getLogger("submit_timing")
_submit_logger.setLevel(logging.INFO)
_submit_logger.propagate = False
_handler = logging.FileHandler(_submit_timing_log, encoding="utf-8")
_handler.setFormatter(SubmitTimingFormatter("%(asctime)s %(message)s"))
_submit_logger.addHandler(_handler)

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
    uvicorn.run("app:app", host="0.0.0.0", port=7860, reload=True)
