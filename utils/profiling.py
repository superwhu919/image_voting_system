# Profiling helpers for diagnosing slow concurrent usage.
# Set PROFILING_ENABLED=1 to log request, segment, and lock timings.
# High lock_wait.* times under load indicate lock contention.
import contextvars
import logging
import time
from contextlib import contextmanager
from typing import Optional

from config import PROFILING_ENABLED

logger = logging.getLogger("profiling")
if PROFILING_ENABLED and not logger.handlers:
    handler = logging.StreamHandler()
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

# Context var so request_id propagates across async awaits
_request_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "profiling_request_id", default=None
)


def set_request_id(value: Optional[str]) -> None:
    _request_id.set(value)


def get_request_id() -> Optional[str]:
    return _request_id.get(None)


@contextmanager
def profile(segment_name: str):
    """Context manager that records segment duration when profiling is enabled."""
    if not PROFILING_ENABLED:
        yield
        return
    t0 = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        rid = get_request_id()
        log_data = {"segment": segment_name, "ms": round(elapsed_ms, 2)}
        if rid is not None:
            log_data["request_id"] = rid
        logger.info("profile %s", log_data)


@contextmanager
def timed_lock(lock, name: str):
    """
    Wraps lock acquisition to record wait_ms (time to acquire) and hold_ms (time held).
    Use when profiling is enabled to see lock contention.
    """
    if not PROFILING_ENABLED:
        with lock:
            yield
        return
    t0 = time.perf_counter()
    lock.acquire()
    t1 = time.perf_counter()
    wait_ms = (t1 - t0) * 1000
    rid = get_request_id()
    logger.info(
        "profile %s",
        {"segment": f"lock_wait.{name}", "ms": round(wait_ms, 2), **({"request_id": rid} if rid else {})},
    )
    try:
        yield
    finally:
        hold_ms = (time.perf_counter() - t1) * 1000
        logger.info(
            "profile %s",
            {"segment": f"lock_hold.{name}", "ms": round(hold_ms, 2), **({"request_id": rid} if rid else {})},
        )
        lock.release()
