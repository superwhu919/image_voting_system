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
    ROOT_DIR_A = DATA_DIR / "gpt"
    ROOT_DIR_B = DATA_DIR / "Nano"
    XLSX_PATH = DATA_DIR / "tangshi_300_unique_name.xlsx"
else:
    ROOT_ABS = Path("/Users/williamhu/Desktop/poem-work/Tangshi-Bench/imgs/ready")
    ROOT_DIR_A = ROOT_ABS / "gpt"
    ROOT_DIR_B = ROOT_ABS / "Nano"
    XLSX_PATH = BASE_DIR / "tangshi_sub1.xlsx"

# =============================
# Persistence (no /data on Space)
# =============================
PERSIST_DIR = BASE_DIR
PERSIST_DIR.mkdir(parents=True, exist_ok=True)
VOTES_CSV = PERSIST_DIR / "votes.csv"
DB_PATH = PERSIST_DIR / "votes.db"

# =============================
# App settings
# =============================
MAX_PER_USER = 10
CSV_ENCODING = "utf-8-sig"

# Image naming
A_SUFFIX = ".png"
B_SUFFIX = "_nano3_1.png"
