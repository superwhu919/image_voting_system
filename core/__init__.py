# Core business logic module
from .session import (
    start_session,
    reveal_poem,
    update_phase2_answer,
    submit_evaluation,
    remaining,
)
from .evaluation import (
    get_evaluation_item,
    format_poem_data,
    format_poem_full,
)

# Load questions for templates
import json
from config import QUESTIONS_JSON_PATH
with open(QUESTIONS_JSON_PATH, 'r', encoding='utf-8') as f:
    QUESTIONS = json.load(f)

__all__ = [
    "start_session",
    "reveal_poem",
    "update_phase2_answer",
    "submit_evaluation",
    "remaining",
    "QUESTIONS",
    "get_evaluation_item",
    "format_poem_data",
    "format_poem_full",
]
