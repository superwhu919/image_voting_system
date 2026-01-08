# Core session management logic
import time
import json

from config import MAX_PER_USER, EVALUATIONS_CSV, QUESTIONS_JSON_PATH
from data.storage import user_count, write_evaluation, get_user_demographics, store_user_demographics
from core.evaluation import get_evaluation_item, format_poem_data, format_poem_full

# Load questions
with open(QUESTIONS_JSON_PATH, 'r', encoding='utf-8') as f:
    QUESTIONS = json.load(f)


def remaining(uid: str) -> int:
    """Calculate remaining evaluations for a user."""
    return max(0, MAX_PER_USER - user_count(uid))


def start_session(uid_input: str, user_age: int = None, user_gender: str = "", user_education: str = "") -> dict:
    """
    Initialize Phase 1 evaluation.
    Returns dict with session data.
    """
    uid = (uid_input or "").strip()
    now_ms = int(time.time() * 1000)

    if not uid:
        return {
            "status": "error",
            "message": "请输入您的昵称。",
            "remaining": 0,
        }

    # Check if name is already used (check users table first, then evaluations)
    existing_demo = get_user_demographics(uid)
    if existing_demo:
        # Compare demographics - all must match
        existing_age = existing_demo.get("age")
        existing_gender = (existing_demo.get("gender") or "").strip()
        existing_education = (existing_demo.get("education") or "").strip()
        
        # Normalize input values
        input_age = user_age if user_age is not None else None
        input_gender = (user_gender or "").strip()
        input_education = (user_education or "").strip()
        
        # Check if all demographics match
        # Age: both must be None or both must be equal (handle int comparison)
        if existing_age is not None:
            try:
                existing_age = int(existing_age)
            except (ValueError, TypeError):
                existing_age = None
        if input_age is not None:
            try:
                input_age = int(input_age)
            except (ValueError, TypeError):
                input_age = None
        age_match = (existing_age == input_age)
        
        gender_match = (existing_gender == input_gender)
        education_match = (existing_education == input_education)
        
        # If all demographics match, allow resume
        if age_match and gender_match and education_match:
            rem = remaining(uid)
            # Get new evaluation item for resume
            poem_title, image_path, distractors, options_dict, target_letter = get_evaluation_item()
            options_data = {}
            for letter in ["A", "B", "C", "D"]:
                options_data[letter] = format_poem_data(options_dict[letter], letter)
            
            return {
                "status": "success",
                "message": f"欢迎回来, {uid}! 继续您的评估。",
                "user_id": uid,
                "poem_title": poem_title,
                "image_path": image_path,
                "options_dict": options_dict,
                "options_data": options_data,
                "target_letter": target_letter,
                "remaining": rem,
                "phase1_start_ms": str(now_ms),
                "phase2_start_ms": str(now_ms),
                "q0": QUESTIONS.get("q0", {}),
            }
        
        # Demographics don't match - ask for different name
        return {
            "status": "error",
            "message": f"该昵称已被使用，但您的信息与记录不符。请使用不同的昵称。",
            "remaining": 0,
            "name_taken": True,
        }

    # New user - store demographics
    store_user_demographics(uid, user_age, user_gender, user_education)
    
    rem = remaining(uid)
    if rem <= 0:
        return {
            "status": "error",
            "message": f"感谢！您已达到限制 ({MAX_PER_USER})。",
            "remaining": 0,
        }

    # Get new evaluation item
    poem_title, image_path, distractors, options_dict, target_letter = get_evaluation_item()
    
    # Format poem options data
    options_data = {}
    for letter in ["A", "B", "C", "D"]:
        options_data[letter] = format_poem_data(options_dict[letter], letter)

    return {
        "status": "success",
        "message": f"欢迎, {uid}! 请选择与图像最匹配的诗。",
        "user_id": uid,
        "poem_title": poem_title,
        "image_path": image_path,
        "options_dict": options_dict,
        "options_data": options_data,
        "target_letter": target_letter,
        "remaining": rem,
        "phase1_start_ms": str(now_ms),
        "phase2_start_ms": str(now_ms),
        "q0": QUESTIONS.get("q0", {}),
    }


def reveal_poem(uid: str, poem_title: str, image_path: str, options_dict: dict, 
                target_letter: str, phase1_choice: str, phase1_start_ms: str) -> dict:
    """
    Reveal the correct poem and show Phase 2 questions.
    Returns dict with reveal data.
    """
    now_ms = int(time.time() * 1000)
    try:
        phase1_response_ms = now_ms - int(phase1_start_ms or now_ms)
    except (ValueError, TypeError):
        phase1_response_ms = 0
    
    if not phase1_choice:
        return {
            "status": "error",
            "message": "请先选择一首诗。",
        }
    
    # Format full poem
    poem_data = format_poem_full(poem_title)
    
    # Check if correct
    is_correct = (phase1_choice == target_letter)
    status_text = f"正确答案是 **{target_letter}**。{'✓ 正确！' if is_correct else '✗ 不正确。'}"
    
    return {
        "status": "success",
        "message": status_text,
        "poem_data": poem_data,
        "is_correct": is_correct,
        "target_letter": target_letter,
        "phase1_choice": phase1_choice,
        "phase1_response_ms": phase1_response_ms,
        "phase2_start_ms": str(now_ms),
        "questions": QUESTIONS,
    }


def update_phase2_answer(q_id: str, answer: str, phase2_answers: dict) -> dict:
    """Update a Phase 2 answer and check if all questions are answered."""
    if not isinstance(phase2_answers, dict):
        phase2_answers = {}
    
    phase2_answers = phase2_answers.copy()
    if answer:
        phase2_answers[q_id] = answer
    
    # Check if all 12 questions (q1-q12) are answered
    all_answered = all(f"q{i}" in phase2_answers for i in range(1, 13))
    
    return {
        "phase2_answers": phase2_answers,
        "all_answered": all_answered,
    }


def submit_evaluation(
    uid: str, user_age: int, user_gender: str, user_education: str,
    poem_title: str, image_path: str, options_dict: dict, target_letter: str,
    phase1_choice: str, phase1_response_ms: int,
    phase2_answers: dict, phase2_start_ms: str, phase1_start_ms: str
) -> dict:
    """
    Submit complete evaluation (Phase 1 + Phase 2).
    Returns dict with next evaluation or completion status.
    """
    now_ms = int(time.time() * 1000)
    
    if not uid:
        return {
            "status": "error",
            "message": "请输入您的昵称。",
            "remaining": 0,
        }
    
    if not phase1_choice:
        return {
            "status": "error",
            "message": "请完成第一阶段选择。",
            "remaining": remaining(uid),
        }
    
    if not isinstance(phase2_answers, dict) or len(phase2_answers) < 12:
        return {
            "status": "error",
            "message": "请完成所有第二阶段问题。",
            "remaining": remaining(uid),
        }
    
    if remaining(uid) <= 0:
        return {
            "status": "error",
            "message": f"感谢！您已达到限制 ({MAX_PER_USER})。",
            "remaining": 0,
        }
    
    # Calculate response times
    phase1_ms = int(phase1_response_ms or 0)
    phase2_ms = now_ms - int(phase2_start_ms or now_ms)
    total_ms = now_ms - int(phase1_start_ms or now_ms)
    
    # Write evaluation
    write_evaluation(
        uid=uid,
        user_age=user_age,
        user_gender=user_gender or "",
        user_education=user_education or "",
        poem_title=poem_title,
        image_path=image_path,
        phase1_choice=phase1_choice,
        phase1_response_ms=phase1_ms,
        phase2_answers=phase2_answers,
        phase2_response_ms=phase2_ms,
        total_response_ms=total_ms,
    )
    
    # Get next evaluation item
    poem_title_next, image_path_next, _, options_dict_next, target_letter_next = get_evaluation_item()
    
    # Format poem options data
    options_data_next = {}
    for letter in ["A", "B", "C", "D"]:
        options_data_next[letter] = format_poem_data(options_dict_next[letter], letter)
    
    rem_after = remaining(uid)
    
    return {
        "status": "success",
        "message": "已提交！下一组…",
        "user_id": uid,
        "poem_title": poem_title_next,
        "image_path": image_path_next,
        "options_dict": options_dict_next,
        "options_data": options_data_next,
        "target_letter": target_letter_next,
        "remaining": rem_after,
        "phase1_start_ms": str(now_ms),
        "phase2_start_ms": str(now_ms),
        "q0": QUESTIONS.get("q0", {}),
    }
