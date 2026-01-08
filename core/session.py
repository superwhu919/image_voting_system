# Core session management logic
import time
import json
import gradio as gr

from config import MAX_PER_USER, EVALUATIONS_CSV, QUESTIONS_JSON_PATH
from data.storage import user_count, write_evaluation
from core.evaluation import get_evaluation_item, format_poem_choice_html, format_poem_full

# Load questions
with open(QUESTIONS_JSON_PATH, 'r', encoding='utf-8') as f:
    QUESTIONS = json.load(f)


def remaining(uid: str) -> int:
    """Calculate remaining evaluations for a user."""
    return max(0, MAX_PER_USER - user_count(uid))


def start_session(uid_input):
    """
    Initialize Phase 1 evaluation.
    Returns all UI state updates.
    """
    uid = (uid_input or "").strip()
    now_ms = int(time.time() * 1000)

    if not uid:
        return _empty_session_response(now_ms)

    rem = remaining(uid)
    if rem <= 0:
        return _limit_reached_response(uid, now_ms)

    # Get new evaluation item
    poem_title, image_path, distractors, options_dict, target_letter = get_evaluation_item()
    
    # Format poem options as HTML with inline radio buttons
    option_a_html = format_poem_choice_html(options_dict["A"], "A", "a")
    option_b_html = format_poem_choice_html(options_dict["B"], "B", "b")
    option_c_html = format_poem_choice_html(options_dict["C"], "C", "c")
    option_d_html = format_poem_choice_html(options_dict["D"], "D", "d")

    return (
        gr.update(value=f"欢迎, **{uid}**! 请选择与图像最匹配的诗。", visible=True),  # status_md
        gr.update(visible=True),  # evaluation_box
        gr.update(value=image_path),  # image_display
        gr.update(value=option_a_html),  # option_a (HTML)
        gr.update(value=option_b_html),  # option_b (HTML)
        gr.update(value=option_c_html),  # option_c (HTML)
        gr.update(value=option_d_html),  # option_d (HTML)
        gr.update(value=None),  # phase1_choice_hidden
        gr.update(interactive=False),  # reveal_btn
        gr.update(visible=False),  # phase2_box
        gr.update(value=""),  # poem_revealed_md
        gr.update(value=None),  # q2_radio
        gr.update(value=None),  # q3_radio
        gr.update(value=None),  # q4_radio
        gr.update(value=None),  # q5_radio
        gr.update(value=None),  # q6_radio
        gr.update(value=None),  # q7_radio
        gr.update(value=None),  # q8_radio
        gr.update(value=None),  # q9_radio
        gr.update(value=None),  # q10_radio
        gr.update(value=None),  # q11_radio
        gr.update(interactive=False),  # submit_btn
        uid,  # user_state
        poem_title,  # poem_state
        image_path,  # image_state
        options_dict,  # options_state
        target_letter,  # target_letter_state
        "",  # phase1_choice_state
        {},  # phase2_answers_state
        str(now_ms),  # phase1_start_ms
        str(now_ms),  # phase2_start_ms
        gr.update(value=f"剩余: {rem} / {MAX_PER_USER}"),  # remaining_lbl
        gr.update(value=EVALUATIONS_CSV),  # dl_evaluations
    )


def _empty_session_response(now_ms):
    """Return empty session response when no user ID."""
    return (
        gr.update(value="请输入您的昵称。", visible=True),  # status_md
        gr.update(visible=False),  # evaluation_box
        gr.update(value=None),  # image_display
        gr.update(value=""),  # option_a (HTML)
        gr.update(value=""),  # option_b (HTML)
        gr.update(value=""),  # option_c (HTML)
        gr.update(value=""),  # option_d (HTML)
        gr.update(value=None),  # phase1_choice_hidden
        gr.update(interactive=False),  # reveal_btn
        gr.update(visible=False),  # phase2_box
        gr.update(value=""),  # poem_revealed_md (Markdown)
        gr.update(value=None),  # q2_radio (Radio - must be None)
        gr.update(value=None),  # q3_radio (Radio - must be None)
        gr.update(value=None),  # q4_radio (Radio - must be None)
        gr.update(value=None),  # q5_radio (Radio - must be None)
        gr.update(value=None),  # q6_radio (Radio - must be None)
        gr.update(value=None),  # q7_radio (Radio - must be None)
        gr.update(value=None),  # q8_radio (Radio - must be None)
        gr.update(value=None),  # q9_radio (Radio - must be None)
        gr.update(value=None),  # q10_radio (Radio - must be None)
        gr.update(value=None),  # q11_radio (Radio - must be None)
        gr.update(interactive=False),  # submit_btn
        "", "", "", {}, "", "", {}, str(now_ms), str(now_ms),  # states
        gr.update(value=f"剩余: 0 / {MAX_PER_USER}"),  # remaining_lbl
        gr.update(value=EVALUATIONS_CSV),  # dl_evaluations
    )


def _limit_reached_response(uid, now_ms):
    """Return response when user has reached evaluation limit."""
    return (
        gr.update(value=f"感谢！您已达到限制 ({MAX_PER_USER})。", visible=True),  # status_md
        gr.update(visible=False),  # evaluation_box
        gr.update(value=None),  # image_display
        gr.update(value=""),  # option_a (HTML)
        gr.update(value=""),  # option_b (HTML)
        gr.update(value=""),  # option_c (HTML)
        gr.update(value=""),  # option_d (HTML)
        gr.update(value=None),  # phase1_choice_hidden
        gr.update(interactive=False),  # reveal_btn
        gr.update(visible=False),  # phase2_box
        gr.update(value=""),  # poem_revealed_md (Markdown)
        gr.update(value=None),  # q2_radio (Radio - must be None)
        gr.update(value=None),  # q3_radio (Radio - must be None)
        gr.update(value=None),  # q4_radio (Radio - must be None)
        gr.update(value=None),  # q5_radio (Radio - must be None)
        gr.update(value=None),  # q6_radio (Radio - must be None)
        gr.update(value=None),  # q7_radio (Radio - must be None)
        gr.update(value=None),  # q8_radio (Radio - must be None)
        gr.update(value=None),  # q9_radio (Radio - must be None)
        gr.update(value=None),  # q10_radio (Radio - must be None)
        gr.update(value=None),  # q11_radio (Radio - must be None)
        gr.update(interactive=False),  # submit_btn
        uid, "", "", {}, "", "", {}, str(now_ms), str(now_ms),  # states
        gr.update(value=f"剩余: 0 / {MAX_PER_USER}"),  # remaining_lbl
        gr.update(value=EVALUATIONS_CSV),  # dl_evaluations
    )


def select_phase1_choice(choice, current_choice):
    """Handle Phase 1 poem selection - enable reveal button."""
    if choice:
        return (
            choice,
            gr.update(interactive=True),  # reveal_btn
        )
    return (
        current_choice,
        gr.update(interactive=False),
    )


def reveal_poem(uid, poem_title, image_path, options_dict, target_letter, phase1_choice, phase1_start_ms):
    """
    Reveal the correct poem and show Phase 2 questions.
    """
    now_ms = int(time.time() * 1000)
    phase1_response_ms = now_ms - int(phase1_start_ms or now_ms)
    
    if not phase1_choice:
        return (
            gr.update(value="请先选择一首诗。", visible=True),
            gr.update(visible=False),  # phase2_box
            gr.update(value=""),  # poem_revealed_md (Markdown, not radio)
            gr.update(interactive=False),  # submit_btn
            str(now_ms),  # phase2_start_ms
            phase1_choice,
            phase1_response_ms,
        )
    
    # Format full poem
    poem_md = format_poem_full(poem_title)
    
    # Check if correct
    is_correct = (phase1_choice == target_letter)
    status_text = f"正确答案是 **{target_letter}**。{'✓ 正确！' if is_correct else '✗ 不正确。'}"
    
    return (
        gr.update(value=status_text, visible=True),
        gr.update(visible=True),  # phase2_box
        gr.update(value=poem_md),  # poem_revealed_md
        gr.update(interactive=False),  # submit_btn (wait for Phase 2 answers)
        str(now_ms),  # phase2_start_ms
        phase1_choice,
        phase1_response_ms,
    )


def update_phase2_answer(q_id, answer, phase2_answers):
    """Update a Phase 2 answer and check if all questions are answered."""
    if not isinstance(phase2_answers, dict):
        phase2_answers = {}
    
    phase2_answers = phase2_answers.copy()
    if answer:
        phase2_answers[q_id] = answer
    
    # Check if all 11 questions (q2-q11) are answered
    all_answered = all(f"q{i}" in phase2_answers for i in range(2, 12))
    
    return (
        phase2_answers,
        gr.update(interactive=all_answered),  # submit_btn
    )


def submit_evaluation(
    uid, poem_title, image_path, options_dict, target_letter,
    phase1_choice, phase1_response_ms,
    phase2_answers, phase2_start_ms, phase1_start_ms
):
    """
    Submit complete evaluation (Phase 1 + Phase 2).
    """
    now_ms = int(time.time() * 1000)
    
    if not uid:
        return _empty_session_response(now_ms)
    
    if not phase1_choice:
        return (
            gr.update(value="请完成第一阶段选择。", visible=True),
            gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(),
            gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(),
            gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(),
            gr.update(), gr.update(), gr.update(),
            uid, poem_title, image_path, options_dict, target_letter,
            phase1_choice, phase2_answers or {},
            str(phase1_start_ms), str(phase2_start_ms),
            gr.update(value=f"剩余: {remaining(uid)} / {MAX_PER_USER}"),
            gr.update(value=EVALUATIONS_CSV),
        )
    
    if not isinstance(phase2_answers, dict) or len(phase2_answers) < 10:
        return (
            gr.update(value="请完成所有第二阶段问题。", visible=True),
            gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(),
            gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(),
            gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(),
            gr.update(), gr.update(), gr.update(),
            uid, poem_title, image_path, options_dict, target_letter,
            phase1_choice, phase2_answers or {},
            str(phase1_start_ms), str(phase2_start_ms),
            gr.update(value=f"剩余: {remaining(uid)} / {MAX_PER_USER}"),
            gr.update(value=EVALUATIONS_CSV),
        )
    
    if remaining(uid) <= 0:
        return _limit_reached_response(uid, now_ms)
    
    # Calculate response times
    phase1_ms = int(phase1_response_ms or 0)
    phase2_ms = now_ms - int(phase2_start_ms or now_ms)
    total_ms = now_ms - int(phase1_start_ms or now_ms)
    
    # Write evaluation
    write_evaluation(
        uid=uid,
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
    
    option_a_html = format_poem_choice_html(options_dict_next["A"], "A", "a")
    option_b_html = format_poem_choice_html(options_dict_next["B"], "B", "b")
    option_c_html = format_poem_choice_html(options_dict_next["C"], "C", "c")
    option_d_html = format_poem_choice_html(options_dict_next["D"], "D", "d")
    
    rem_after = remaining(uid)
    
    return (
        gr.update(value="已提交！下一组…", visible=True),  # status_md
        gr.update(visible=True),  # evaluation_box
        gr.update(value=image_path_next),  # image_display
        gr.update(value=option_a_html),  # option_a (HTML)
        gr.update(value=option_b_html),  # option_b (HTML)
        gr.update(value=option_c_html),  # option_c (HTML)
        gr.update(value=option_d_html),  # option_d (HTML)
        gr.update(value=None),  # phase1_choice_hidden
        gr.update(interactive=False),  # reveal_btn
        gr.update(visible=False),  # phase2_box
        gr.update(value=""),  # poem_revealed_md
        gr.update(value=None),  # q2_radio
        gr.update(value=None),  # q3_radio
        gr.update(value=None),  # q4_radio
        gr.update(value=None),  # q5_radio
        gr.update(value=None),  # q6_radio
        gr.update(value=None),  # q7_radio
        gr.update(value=None),  # q8_radio
        gr.update(value=None),  # q9_radio
        gr.update(value=None),  # q10_radio
        gr.update(value=None),  # q11_radio
        gr.update(interactive=False),  # submit_btn
        uid, poem_title_next, image_path_next, options_dict_next, target_letter_next,
        "", {},
        str(now_ms), str(now_ms),
        gr.update(value=f"剩余: {rem_after} / {MAX_PER_USER}"),
        gr.update(value=EVALUATIONS_CSV),
    )

