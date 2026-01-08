# flush.py
import os, time
from pathlib import Path
from huggingface_hub import HfApi
from config import ON_HF, DB_PATH

VOTES_REPO = "superwhu919/tangshi-votes-db"
FLUSH_EVERY_SEC = 60

_api = HfApi()
_last_flush = 0.0

def maybe_flush():
    global _last_flush

    if not ON_HF:
        return

    token = os.getenv("WriteToken")
    print("maybe_flush | has WriteToken:", bool(token), flush=True)

    if not token:
        return

    if not Path(DB_PATH).exists():
        print("maybe_flush | DB not found:", DB_PATH, flush=True)
        return

    now = time.time()
    if now - _last_flush < FLUSH_EVERY_SEC:
        return

    try:
        _api.upload_file(
            path_or_fileobj=str(DB_PATH),
            path_in_repo="votes/votes.db",
            repo_id=VOTES_REPO,
            repo_type="dataset",
            token=token,
            commit_message=time.strftime("votes %Y-%m-%d %H:%M:%S"),
        )
        _last_flush = now
        print("FLUSH OK", flush=True)
    except Exception as e:
        print("FLUSH FAIL:", repr(e), flush=True)
