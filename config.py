import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

IMAGE_DIR = BASE_DIR / "all_images"
CSV_PATH = Path(os.getenv("CSV_PATH", str(BASE_DIR / "method4_similar_with_translations_final.csv")))

USERS_DB_PATH = BASE_DIR / "users.db"
EVALUATIONS_DB_PATH = BASE_DIR / "evaluations.db"
DB_PATH = EVALUATIONS_DB_PATH

MAX_PER_USER = 10
CSV_ENCODING = "utf-8-sig"
QUESTIONS_JSON_PATH = BASE_DIR / "questions.json"
EVALUATIONS_CSV = BASE_DIR / "evaluations.csv"
