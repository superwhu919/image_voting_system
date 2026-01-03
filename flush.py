# flush.py
import os, time
from pathlib import Path
from huggingface_hub import HfApi
from config import ON_HF, DB_PATH

VOTES_REPO = "superwhu919/tangshi-votes-db"
FLUSH_EVERY_SEC = 60  # 1–3 min

_api = HfApi()
_last_flush = 0.0

def maybe_flush():
    global _last_flush
    if not ON_HF:
        return

    now = time.time()
    if now - _last_flush < FLUSH_EVERY_SEC:
        return

    token = os.getenv("WriteToken")
    if not token or not Path(DB_PATH).exists():
        return

    _api.upload_file(
        path_or_fileobj=str(DB_PATH),
        path_in_repo="votes/votes.db",
        repo_id=VOTES_REPO,
        repo_type="dataset",
        token=token,
        commit_message=time.strftime("votes %Y-%m-%d %H:%M:%S"),
    )
    _last_flush = now

    print("Flushed votes to HF")

