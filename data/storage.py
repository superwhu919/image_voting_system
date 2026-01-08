# storage.py
import sqlite3
import threading
from datetime import datetime
from config import DB_PATH
from utils.flush import maybe_flush

WRITE_LOCK = threading.Lock()

def db_connect():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=30)

    # ✅ Option A: single-file DB snapshot (best for HF upload)
    conn.execute("PRAGMA journal_mode=DELETE;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")

    # Drop old votes table if it exists (migration)
    conn.execute("DROP TABLE IF EXISTS votes")
    
    conn.execute("""
    CREATE TABLE IF NOT EXISTS evaluations(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT,
        user_id TEXT,
        poem_title TEXT,
        image_path TEXT,
        phase1_choice TEXT,
        phase1_response_ms INTEGER,
        q2_main_subject TEXT,
        q3_quantity TEXT,
        q4_attributes TEXT,
        q5_action_state TEXT,
        q6_environment TEXT,
        q7_seasonal_temporal TEXT,
        q8_atmospheric_tone TEXT,
        q9_historical_violations TEXT,
        q10_irrelevant_intrusion TEXT,
        q11_pseudo_text TEXT,
        phase2_response_ms INTEGER,
        total_response_ms INTEGER
    )""")
    conn.commit()
    return conn

DB = db_connect()

def user_count(uid: str) -> int:
    with WRITE_LOCK:
        (n,) = DB.execute("SELECT COUNT(*) FROM evaluations WHERE user_id=?", (uid,)).fetchone()
    return int(n or 0)

def write_evaluation(
    uid,
    poem_title,
    image_path,
    phase1_choice,
    phase1_response_ms,
    phase2_answers,  # dict with keys q2, q3, ..., q11
    phase2_response_ms,
    total_response_ms
):
    """
    Write a complete evaluation to the database.
    phase2_answers should be a dict like:
    {
        "q2": "Present",
        "q3": "Correct quantity",
        ...
        "q11": "None"
    }
    """
    ts = datetime.utcnow().isoformat()
    with WRITE_LOCK:
        DB.execute(
            """INSERT INTO evaluations(
                ts, user_id, poem_title, image_path,
                phase1_choice, phase1_response_ms,
                q2_main_subject, q3_quantity, q4_attributes,
                q5_action_state, q6_environment, q7_seasonal_temporal,
                q8_atmospheric_tone, q9_historical_violations,
                q10_irrelevant_intrusion, q11_pseudo_text,
                phase2_response_ms, total_response_ms
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                ts, uid, poem_title, image_path,
                phase1_choice, phase1_response_ms,
                phase2_answers.get("q2", ""),
                phase2_answers.get("q3", ""),
                phase2_answers.get("q4", ""),
                phase2_answers.get("q5", ""),
                phase2_answers.get("q6", ""),
                phase2_answers.get("q7", ""),
                phase2_answers.get("q8", ""),
                phase2_answers.get("q9", ""),
                phase2_answers.get("q10", ""),
                phase2_answers.get("q11", ""),
                phase2_response_ms, total_response_ms
            ),
        )
        DB.commit()
        maybe_flush()
    return ts
