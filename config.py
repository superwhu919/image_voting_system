import os
from pathlib import Path

# -----------------------------
# Detect environment
# -----------------------------
ON_HF = bool(os.getenv("SPACE_ID")) or os.getenv("SYSTEM") == "spaces"

# -----------------------------
# Base directory
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

if ON_HF:
    # HF Space: images must live inside repo or /data
    ROOT_ABS = BASE_DIR / "imgs"
    ROOT_DIR_A = ROOT_ABS / "gpt"
    ROOT_DIR_B = ROOT_ABS / "nano"
    XLSX_PATH = BASE_DIR / "tangshi_sub1.xlsx"
else:
    # Local Mac paths
    ROOT_DIR_A = Path("/Users/williamhu/Desktop/poem-work/Tangshi-Bench/imgs/ready/gpt")
    ROOT_DIR_B = Path("/Users/williamhu/Desktop/poem-work/Tangshi-Bench/imgs/ready/Nano")
    ROOT_ABS   = Path("/Users/williamhu/Desktop/poem-work/Tangshi-Bench/imgs/ready")
    XLSX_PATH  = BASE_DIR / "tangshi_sub1.xlsx"

# -----------------------------
# Output / persistence paths
# -----------------------------
if ON_HF:
    # Use persistent storage if enabled; otherwise repo root
    VOTES_CSV = Path("/data/votes.csv") if Path("/data").exists() else BASE_DIR / "votes.csv"
    DB_PATH   = Path("/data/votes.db")  if Path("/data").exists() else BASE_DIR / "votes.db"
else:
    VOTES_CSV = BASE_DIR / "votes.csv"
    DB_PATH   = BASE_DIR / "votes.db"

# -----------------------------------
# Settings
# -----------------------------------
MAX_PER_USER = 10
CSV_ENCODING = "utf-8-sig"


# config.py
A_SUFFIX = ".png"
B_SUFFIX = "_nano3_1.png"