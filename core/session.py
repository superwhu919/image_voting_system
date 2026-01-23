# Core session management logic
import time
import json

from config import MAX_PER_USER, EVALUATIONS_CSV, QUESTIONS_JSON_PATH
from data_logic.storage import user_count, write_evaluation, get_user_demographics, store_user_demographics, get_user_limit
from data_logic.catalog import CATALOG
from core.evaluation import get_evaluation_item, format_poem_data, format_poem_full, IMAGE_SELECTION_SYSTEM

# Load questions
with open(QUESTIONS_JSON_PATH, 'r', encoding='utf-8') as f:
    QUESTIONS = json.load(f)

# Get list of Phase 2 question IDs (all q2-* questions, excluding stage 1 questions q1-*)
def _sort_question_key(q_id):
    """Sort key for questions: q2-1, q2-2, etc."""
    if q_id.startswith("q2-"):
        try:
            return int(q_id.split("-")[1])
        except (ValueError, IndexError):
            return 999
    return 999

PHASE2_QUESTION_IDS = sorted([q_id for q_id in QUESTIONS.keys() if q_id.startswith("q2-")], 
                              key=_sort_question_key)


def remaining(uid: str) -> int:
    """Calculate remaining evaluations for a user."""
    # Check if user has a custom limit
    user_limit = get_user_limit(uid)
    limit = user_limit if user_limit is not None else MAX_PER_USER
    return max(0, limit - user_count(uid))


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
    
    # Validate all required fields before processing
    if user_age is None or user_age <= 0:
        return {
            "status": "error",
            "message": "请输入有效的年龄。",
            "remaining": 0,
        }
    
    if not user_gender or not user_gender.strip():
        return {
            "status": "error",
            "message": "请选择性别。",
            "remaining": 0,
        }
    
    if not user_education or not user_education.strip():
        return {
            "status": "error",
            "message": "请选择教育程度。",
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
            user_limit = get_user_limit(uid) or MAX_PER_USER
            completed = user_count(uid)
            
            # If user has reached their limit, ask if they want to extend
            if rem <= 0:
                return {
                    "status": "limit_reached",
                    "message": f"您已完成 {completed} 个评估。是否要继续？",
                    "remaining": 0,
                    "completed": completed,
                    "can_extend": True,
                    "user_limit": user_limit,
                }
            
            # Get new evaluation item for resume (use uid as user_id)
            try:
                result = get_evaluation_item(uid)
            except RuntimeError as e:
                # No more images available - user has seen all images
                if "No images available" in str(e) or "All queues exhausted" in str(e):
                    return {
                        "status": "all_images_seen",
                        "message": "您已看过所有图片。没有更多图片可供评估。",
                        "remaining": rem,
                        "completed": completed,
                    }
                # Re-raise if it's a different RuntimeError
                raise
            
            if result is None:
                return {
                    "status": "all_images_seen",
                    "message": "您已看过所有图片。没有更多图片可供评估。",
                    "remaining": rem,
                    "completed": completed,
                }
            
            poem_title, image_path, image_type, distractors, options_dict, target_letter = result
            options_data = {}
            for letter in ["A", "B", "C", "D"]:
                options_data[letter] = format_poem_data(options_dict[letter], letter)
            
            return {
                "status": "success",
                "message": f"欢迎回来, {uid}! 继续您的评估。",
                "user_id": uid,
                "poem_title": poem_title,
                "image_path": image_path,
                "image_type": image_type,
                "options_dict": options_dict,
                "options_data": options_data,
                "target_letter": target_letter,
                "remaining": rem,
                "user_limit": user_limit,
                "phase1_start_ms": str(now_ms),
                "phase2_start_ms": str(now_ms),
                "q1-1": QUESTIONS.get("q1-1", {}),
                "q1-2": QUESTIONS.get("q1-2", {}),
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
    user_limit = get_user_limit(uid) or MAX_PER_USER
    completed = user_count(uid)
    
    # If user has reached their limit, ask if they want to extend
    if rem <= 0:
        return {
            "status": "limit_reached",
            "message": f"您已完成 {completed} 个评估。是否要继续？",
            "remaining": 0,
            "completed": completed,
            "can_extend": True,
            "user_limit": user_limit,
        }
    
    # Get new evaluation item (use uid as user_id)
    try:
        result = get_evaluation_item(uid)
    except RuntimeError as e:
        # No more images available - user has seen all images
        if "No images available" in str(e) or "All queues exhausted" in str(e):
            return {
                "status": "all_images_seen",
                "message": "您已看过所有图片。没有更多图片可供评估。",
                "remaining": rem,
                "completed": completed,
            }
        # Re-raise if it's a different RuntimeError
        raise
    
    if result is None:
        return {
            "status": "all_images_seen",
            "message": "您已看过所有图片。没有更多图片可供评估。",
            "remaining": rem,
            "completed": completed,
        }
    
    poem_title, image_path, image_type, distractors, options_dict, target_letter = result
    
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
        "image_type": image_type,
        "options_dict": options_dict,
        "options_data": options_data,
        "target_letter": target_letter,
        "remaining": rem,
        "user_limit": user_limit,
        "phase1_start_ms": str(now_ms),
        "phase2_start_ms": str(now_ms),
        "q1-1": QUESTIONS.get("q1-1", {}),
        "q1-2": QUESTIONS.get("q1-2", {}),
    }


def reveal_poem(uid: str, poem_title: str, image_path: str, options_dict: dict, 
                target_letter: str, phase1_choice: str, phase1_answers: dict = None, phase1_start_ms: str = None) -> dict:
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
    
    # Only send Phase 2 questions (q2-*) to Phase 2
    phase2_questions = {q_id: QUESTIONS[q_id] for q_id in QUESTIONS.keys() if q_id.startswith("q2-")}
    
    return {
        "status": "success",
        "message": status_text,
        "poem_data": poem_data,
        "is_correct": is_correct,
        "target_letter": target_letter,
        "phase1_choice": phase1_choice,
        "phase1_response_ms": phase1_response_ms,
        "phase2_start_ms": str(now_ms),
        "questions": phase2_questions,
    }


def update_phase2_answer(q_id: str, answer: str, phase2_answers: dict) -> dict:
    """Update a Phase 2 answer and check if all questions are answered."""
    if not isinstance(phase2_answers, dict):
        phase2_answers = {}
    
    phase2_answers = phase2_answers.copy()
    if answer:
        phase2_answers[q_id] = answer
    
    # Check if all Phase 2 questions are answered (dynamically based on QUESTIONS)
    all_answered = all(q_id in phase2_answers for q_id in PHASE2_QUESTION_IDS)
    
    return {
        "phase2_answers": phase2_answers,
        "all_answered": all_answered,
    }


def submit_evaluation(
    uid: str, user_age: int, user_gender: str, user_education: str,
    poem_title: str, image_path: str, image_type: str, options_dict: dict, target_letter: str,
    phase1_choice: str, phase1_answers: dict = None, phase1_response_ms: int = 0,
    phase2_answers: dict = None, phase2_start_ms: str = None, phase1_start_ms: str = None
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
    
    if not isinstance(phase2_answers, dict) or len(phase2_answers) < len(PHASE2_QUESTION_IDS):
        return {
            "status": "error",
            "message": "请完成所有第二阶段问题。",
            "remaining": remaining(uid),
        }
    
    # Check remaining BEFORE writing - if 0 or less, don't allow submission
    rem_before = remaining(uid)
    if rem_before <= 0:
        user_limit = get_user_limit(uid) or MAX_PER_USER
        return {
            "status": "error",
            "message": f"感谢！您已达到限制 ({user_limit})。",
            "remaining": 0,
            "user_limit": user_limit,
        }
    
    # Calculate response times
    try:
        phase1_start = int(phase1_start_ms or now_ms)
        phase2_start = int(phase2_start_ms or now_ms)
        
        # Phase 1 time: from phase1_start_ms to phase2_start_ms (when reveal was called)
        phase1_ms = max(0, phase2_start - phase1_start)
        
        # Phase 2 time: from phase2_start_ms to now (when submit was called)
        phase2_ms = max(0, now_ms - phase2_start)
        
        # Total time: from phase1_start_ms to now
        total_ms = max(0, now_ms - phase1_start)
    except (ValueError, TypeError):
        # Fallback: use passed value if calculation fails
        phase1_ms = int(phase1_response_ms or 0)
        phase2_ms = max(0, now_ms - int(phase2_start_ms or now_ms))
        total_ms = max(0, now_ms - int(phase1_start_ms or now_ms))
    
    # Get image_type from catalog if not provided
    if not image_type and image_path:
        image_data = CATALOG.get(image_path)
        if image_data:
            image_type = image_data.get("image_type", "")
    
    # Write evaluation to database
    # Note: phase1_answers (q1-2) are passed but not yet stored in DB schema
    # This can be added later if needed
    write_evaluation(
        uid=uid,
        user_age=user_age,
        user_gender=user_gender or "",
        user_education=user_education or "",
        poem_title=poem_title,
        image_path=image_path,
        image_type=image_type or "",
        phase1_choice=phase1_choice,
        target_letter=target_letter,  # The correct answer for q1-1
        phase1_answers=phase1_answers or {},
        phase1_response_ms=phase1_ms,
        phase2_answers=phase2_answers or {},
        phase2_response_ms=phase2_ms,
        total_response_ms=total_ms,
    )
    
    # Submit rating to image selection system (use uid as user_id)
    IMAGE_SELECTION_SYSTEM.submit_rating(uid, image_path, poem_title)
    
    # Check remaining AFTER writing - if 0, show limit_reached modal instead of next evaluation
    rem_after = remaining(uid)
    user_limit = get_user_limit(uid) or MAX_PER_USER
    completed = user_count(uid)
    
    if rem_after <= 0:
        # User has reached their limit - show limit_reached modal
        return {
            "status": "limit_reached",
            "message": f"您已完成 {completed} 个评估。是否要继续？",
            "remaining": 0,
            "completed": completed,
            "can_extend": True,
            "user_limit": user_limit,
        }
    
    # Get next evaluation item (use uid as user_id)
    try:
        result = get_evaluation_item(uid)
    except RuntimeError as e:
        # No more images available - user has seen all images
        if "No images available" in str(e) or "All queues exhausted" in str(e):
            return {
                "status": "all_images_seen",
                "message": "您已看过所有图片。没有更多图片可供评估。",
                "remaining": rem_after,
                "completed": completed,
            }
        # Re-raise if it's a different RuntimeError
        raise
    
    if result is None:
        return {
            "status": "all_images_seen",
            "message": "您已看过所有图片。没有更多图片可供评估。",
            "remaining": rem_after,
            "completed": completed,
        }
    
    poem_title_next, image_path_next, image_type_next, _, options_dict_next, target_letter_next = result
    
    # Format poem options data
    options_data_next = {}
    for letter in ["A", "B", "C", "D"]:
        options_data_next[letter] = format_poem_data(options_dict_next[letter], letter)
    
    return {
        "status": "success",
        "message": "已提交！下一组…",
        "user_id": uid,
        "poem_title": poem_title_next,
        "image_path": image_path_next,
        "image_type": image_type_next,
        "options_dict": options_dict_next,
        "options_data": options_data_next,
        "target_letter": target_letter_next,
        "remaining": rem_after,
        "user_limit": user_limit,
        "phase1_start_ms": str(now_ms),
        "phase2_start_ms": str(now_ms),
        "q1-1": QUESTIONS.get("q1-1", {}),
        "q1-2": QUESTIONS.get("q1-2", {}),
    }
