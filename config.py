import os
from pathlib import Path
from huggingface_hub import snapshot_download

# =============================
# Environment
# =============================
ON_HF = bool(os.getenv("SPACE_ID")) or os.getenv("SYSTEM") == "spaces"
BASE_DIR = Path(__file__).resolve().parent

# =============================
# HF private dataset
# =============================
def download_dataset() -> Path:
    token = os.getenv("Token")  # HF Space secret (case-sensitive)
    if not token:
        raise RuntimeError(
            "HF Space secret 'Token' not found. "
            "Add it in Space Settings → Secrets and restart the Space."
        )

    return Path(
        snapshot_download(
            repo_id="superwhu919/tangshi-data",
            repo_type="dataset",
            revision="main",
            token=token,
        )
    )

# =============================
# Data paths
# =============================
if ON_HF:
    DATA_DIR = download_dataset()
    ROOT_ABS = DATA_DIR
    IMAGE_DIR = DATA_DIR / "Nano"
    XLSX_PATH = DATA_DIR / "tangshi_300_unique_name.xlsx"
    CSV_PATH = DATA_DIR / "method3_similar.csv"
else:
    # Support remote deployment via environment variable
    # If DATA_ROOT is set, use it (for remote instance/Docker)
    # Otherwise, use local Mac development path
    DATA_ROOT = os.getenv("DATA_ROOT")
    if DATA_ROOT:
        ROOT_ABS = Path(DATA_ROOT)
        IMAGE_DIR = ROOT_ABS / "Nano"
        # CSV path can be overridden, otherwise look in data root or base dir
        CSV_ENV = os.getenv("CSV_PATH")
        if CSV_ENV:
            CSV_PATH = Path(CSV_ENV)
        else:
            # Try data root first, then base dir
            csv_in_data = ROOT_ABS / "method3_similar.csv"
            csv_in_base = BASE_DIR / "method3_similar.csv"
            CSV_PATH = csv_in_data if csv_in_data.exists() else csv_in_base
        # Excel path can be overridden, otherwise look in data root or base dir
        XLSX_ENV = os.getenv("XLSX_PATH")
        if XLSX_ENV:
            XLSX_PATH = Path(XLSX_ENV)
        else:
            # Try data root first, then base dir
            xlsx_in_data = ROOT_ABS / "tangshi_300_unique_name.xlsx"
            xlsx_in_base = BASE_DIR / "tangshi_300_unique_name.xlsx"
            XLSX_PATH = xlsx_in_data if xlsx_in_data.exists() else xlsx_in_base
    else:
        # Local development mode (Mac)
        ROOT_ABS = Path("/Users/williamhu/Desktop/poem-work/Tangshi-Bench/imgs/ready")
        IMAGE_DIR = Path("/Users/williamhu/Desktop/poem-work/tangshi-data/all_images")
        XLSX_PATH = BASE_DIR / "tangshi_300_unique_name.xlsx"
        CSV_PATH = BASE_DIR / "method3_similar.csv"

# =============================
# Persistence (no /data on Space)
# =============================
PERSIST_DIR = BASE_DIR
PERSIST_DIR.mkdir(parents=True, exist_ok=True)
EVALUATIONS_CSV = PERSIST_DIR / "evaluations.csv"
USERS_DB_PATH = PERSIST_DIR / "users.db"
EVALUATIONS_DB_PATH = PERSIST_DIR / "evaluations.db"
# Keep DB_PATH for backward compatibility (points to evaluations)
DB_PATH = EVALUATIONS_DB_PATH

# =============================
# App settings
# =============================
MAX_PER_USER = 10
CSV_ENCODING = "utf-8-sig"

# Image naming
# Images are now named as: {poem_title}_{type}.png where type is gpt, mj, or nano
# IMAGE_SUFFIX is no longer used - images are discovered by scanning the directory
IMAGE_SUFFIX = None  # Deprecated - kept for backward compatibility

# Questions configuration
QUESTIONS_JSON_PATH = BASE_DIR / "questions.json"
