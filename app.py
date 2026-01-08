# app.py - Main entry point for Gradio application
import os
import time
import gradio as gr

from config import ROOT_ABS, EVALUATIONS_CSV, ON_HF
from core import (
    start_session,
    reveal_poem,
    update_phase2_answer,
    submit_evaluation,
    QUESTIONS,
)
from ui.styles import CSS
from ui.helpers import img_html

# =========================
# UI Wrapper Functions
# =========================
def start_session_ui(user_id: str):
    """Wrap start_session to convert image path to HTML."""
    res = list(start_session(user_id))
    # res[2] is image_display (index 2)
    if len(res) > 2 and res[2]:
        res[2] = img_html("eval_img", "eval_modal", res[2])
    return tuple(res)


def reveal_poem_ui(uid, poem_title, image_path, options_dict, target_letter, phase1_choice, phase1_start_ms):
    """Wrap reveal_poem - image already in HTML format."""
    res = list(reveal_poem(uid, poem_title, image_path, options_dict, target_letter, phase1_choice, phase1_start_ms))
    return tuple(res)


def submit_evaluation_ui(
    uid, poem_title, image_path, options_dict, target_letter,
    phase1_choice, phase1_response_ms,
    phase2_answers, phase2_start_ms, phase1_start_ms
):
    """Wrap submit_evaluation to convert image path to HTML."""
    res = list(submit_evaluation(
        uid, poem_title, image_path, options_dict, target_letter,
        phase1_choice, phase1_response_ms,
        phase2_answers, phase2_start_ms, phase1_start_ms
    ))
    # res[2] is image_display (index 2)
    if len(res) > 2 and res[2]:
        res[2] = img_html("eval_img", "eval_modal", res[2])
    return tuple(res)


# =========================
# UI Layout
# =========================
with gr.Blocks(css=CSS, title="Image-Poem Alignment Evaluation") as demo:
    gr.Markdown("# 图像-诗歌对齐评估")
    gr.Markdown("评估协议：图像-诗歌对齐")
    
    user_input = gr.Textbox(label="您的昵称", placeholder="e.g., 王维")
    start_btn = gr.Button("开始", variant="primary")
    
    status_md = gr.Markdown(visible=False)
    remaining_lbl = gr.Label(value="", visible=True)
    
    evaluation_box = gr.Group(visible=False)
    with evaluation_box:
        # Phase 1: Blind Evaluation
        gr.Markdown("## 第一阶段：盲评")
        
        gr.Markdown("**Q1. 这首诗摘录最可能代表这张图像？**")
        
        with gr.Row():
            # Left side: Image
            with gr.Column(scale=1):
                image_display = gr.HTML()  # Single image with modal
            
            # Right side: Choices with inline radio buttons
            with gr.Column(scale=1):
                option_a = gr.HTML()
                option_b = gr.HTML()
                option_c = gr.HTML()
                option_d = gr.HTML()
                
                # Hidden radio to track selection (updated by JavaScript, triggers Gradio update)
                phase1_choice_hidden = gr.Radio(
                    choices=["A", "B", "C", "D"],
                    value=None,
                    visible=False,
                    elem_id="phase1_choice_hidden_radio"
                )
        reveal_btn = gr.Button("揭示正确答案", variant="secondary", interactive=False)
        
        # Phase 2: Revealed Evaluation
        phase2_box = gr.Group(visible=False)
        with phase2_box:
            gr.Markdown("## 第二阶段：揭示评估")
            gr.Markdown("（现在显示正确的目标诗与图像。）")
            
            poem_revealed_md = gr.Markdown()
            
            gr.Markdown("### 第二部分：视觉回忆 — 名词测试")
            
            q2_radio = gr.Radio(
                choices=[(opt["label"], opt["value"]) for opt in QUESTIONS["q2"]["options"]],
                label=QUESTIONS["q2"]["question"],
                value=None,
            )
            
            q3_radio = gr.Radio(
                choices=[(opt["label"], opt["value"]) for opt in QUESTIONS["q3"]["options"]],
                label=QUESTIONS["q3"]["question"],
                value=None,
            )
            
            gr.Markdown("### 第三部分：视觉保真度 — 描述测试")
            
            q4_radio = gr.Radio(
                choices=[(opt["label"], opt["value"]) for opt in QUESTIONS["q4"]["options"]],
                label=QUESTIONS["q4"]["question"],
                value=None,
            )
            
            q5_radio = gr.Radio(
                choices=[(opt["label"], opt["value"]) for opt in QUESTIONS["q5"]["options"]],
                label=QUESTIONS["q5"]["question"],
                value=None,
            )
            
            gr.Markdown("### 第四部分：全局语义 — 境/意测试")
            
            q6_radio = gr.Radio(
                choices=[(opt["label"], opt["value"]) for opt in QUESTIONS["q6"]["options"]],
                label=QUESTIONS["q6"]["question"],
                value=None,
            )
            
            q7_radio = gr.Radio(
                choices=[(opt["label"], opt["value"]) for opt in QUESTIONS["q7"]["options"]],
                label=QUESTIONS["q7"]["question"],
                value=None,
            )
            
            q8_radio = gr.Radio(
                choices=[(opt["label"], opt["value"]) for opt in QUESTIONS["q8"]["options"]],
                label=QUESTIONS["q8"]["question"],
                value=None,
            )
            
            gr.Markdown("### 第五部分：负面约束 — 幻觉检测")
            
            q9_radio = gr.Radio(
                choices=[(opt["label"], opt["value"]) for opt in QUESTIONS["q9"]["options"]],
                label=QUESTIONS["q9"]["question"],
                value=None,
            )
            
            q10_radio = gr.Radio(
                choices=[(opt["label"], opt["value"]) for opt in QUESTIONS["q10"]["options"]],
                label=QUESTIONS["q10"]["question"],
                value=None,
            )
            
            q11_radio = gr.Radio(
                choices=[(opt["label"], opt["value"]) for opt in QUESTIONS["q11"]["options"]],
                label=QUESTIONS["q11"]["question"],
                value=None,
            )
            
            submit_btn = gr.Button("提交评估", variant="primary", interactive=False)
    
    # ---- States ----
    user_state = gr.State("")
    poem_state = gr.State("")
    image_state = gr.State("")
    options_state = gr.State({})
    target_letter_state = gr.State("")
    phase1_choice_state = gr.State("")
    phase1_response_ms_state = gr.State(0)
    phase2_answers_state = gr.State({})
    phase1_start_ms = gr.State(str(int(time.time() * 1000)))
    phase2_start_ms = gr.State(str(int(time.time() * 1000)))
    dl_evaluations = gr.State(EVALUATIONS_CSV)
    
    # =========================
    # Event Wiring
    # =========================
    start_btn.click(
        start_session_ui,
        inputs=[user_input],
        outputs=[
            status_md,
            evaluation_box,
            image_display,
            option_a,
            option_b,
            option_c,
            option_d,
            phase1_choice_hidden,
            reveal_btn,
            phase2_box,
            poem_revealed_md,
            q2_radio, q3_radio, q4_radio, q5_radio,
            q6_radio, q7_radio, q8_radio,
            q9_radio, q10_radio, q11_radio,
            submit_btn,
            user_state,
            poem_state,
            image_state,
            options_state,
            target_letter_state,
            phase1_choice_state,
            phase2_answers_state,
            phase1_start_ms,
            phase2_start_ms,
            remaining_lbl,
            dl_evaluations,
        ],
    )
    
    # Update phase1_choice_state when hidden radio changes (updated by JavaScript)
    def sync_choice_from_hidden_radio(choice_value):
        """Sync the hidden radio value to phase1_choice_state and enable reveal button."""
        if choice_value:
            return choice_value, gr.update(interactive=True)
        return "", gr.update(interactive=False)
    
    phase1_choice_hidden.change(
        sync_choice_from_hidden_radio,
        inputs=[phase1_choice_hidden],
        outputs=[phase1_choice_state, reveal_btn],
    )
    
    # Phase 1: Reveal poem
    reveal_btn.click(
        reveal_poem_ui,
        inputs=[
            user_state,
            poem_state,
            image_state,
            options_state,
            target_letter_state,
            phase1_choice_state,
            phase1_start_ms,
        ],
        outputs=[
            status_md,
            phase2_box,
            poem_revealed_md,
            submit_btn,
            phase2_start_ms,
            phase1_choice_state,
            phase1_response_ms_state,
        ],
    )
    
    # Phase 2: Update answers (Q2-Q11)
    # Create individual updater functions for each question
    def update_q2(answer, current_answers):
        return update_phase2_answer("q2", answer, current_answers)
    def update_q3(answer, current_answers):
        return update_phase2_answer("q3", answer, current_answers)
    def update_q4(answer, current_answers):
        return update_phase2_answer("q4", answer, current_answers)
    def update_q5(answer, current_answers):
        return update_phase2_answer("q5", answer, current_answers)
    def update_q6(answer, current_answers):
        return update_phase2_answer("q6", answer, current_answers)
    def update_q7(answer, current_answers):
        return update_phase2_answer("q7", answer, current_answers)
    def update_q8(answer, current_answers):
        return update_phase2_answer("q8", answer, current_answers)
    def update_q9(answer, current_answers):
        return update_phase2_answer("q9", answer, current_answers)
    def update_q10(answer, current_answers):
        return update_phase2_answer("q10", answer, current_answers)
    def update_q11(answer, current_answers):
        return update_phase2_answer("q11", answer, current_answers)
    
    q2_radio.change(update_q2, inputs=[q2_radio, phase2_answers_state], outputs=[phase2_answers_state, submit_btn])
    q3_radio.change(update_q3, inputs=[q3_radio, phase2_answers_state], outputs=[phase2_answers_state, submit_btn])
    q4_radio.change(update_q4, inputs=[q4_radio, phase2_answers_state], outputs=[phase2_answers_state, submit_btn])
    q5_radio.change(update_q5, inputs=[q5_radio, phase2_answers_state], outputs=[phase2_answers_state, submit_btn])
    q6_radio.change(update_q6, inputs=[q6_radio, phase2_answers_state], outputs=[phase2_answers_state, submit_btn])
    q7_radio.change(update_q7, inputs=[q7_radio, phase2_answers_state], outputs=[phase2_answers_state, submit_btn])
    q8_radio.change(update_q8, inputs=[q8_radio, phase2_answers_state], outputs=[phase2_answers_state, submit_btn])
    q9_radio.change(update_q9, inputs=[q9_radio, phase2_answers_state], outputs=[phase2_answers_state, submit_btn])
    q10_radio.change(update_q10, inputs=[q10_radio, phase2_answers_state], outputs=[phase2_answers_state, submit_btn])
    q11_radio.change(update_q11, inputs=[q11_radio, phase2_answers_state], outputs=[phase2_answers_state, submit_btn])
    
    # Phase 2: Submit evaluation
    submit_btn.click(
        submit_evaluation_ui,
        inputs=[
            user_state,
            poem_state,
            image_state,
            options_state,
            target_letter_state,
            phase1_choice_state,
            phase1_response_ms_state,
            phase2_answers_state,
            phase2_start_ms,
            phase1_start_ms,
        ],
        outputs=[
            status_md,
            evaluation_box,
            image_display,
            option_a,
            option_b,
            option_c,
            option_d,
            phase1_choice_hidden,
            reveal_btn,
            phase2_box,
            poem_revealed_md,
            q2_radio, q3_radio, q4_radio, q5_radio,
            q6_radio, q7_radio, q8_radio,
            q9_radio, q10_radio, q11_radio,
            submit_btn,
            user_state,
            poem_state,
            image_state,
            options_state,
            target_letter_state,
            phase1_choice_state,
            phase2_answers_state,
            phase1_start_ms,
            phase2_start_ms,
            remaining_lbl,
            dl_evaluations,
        ],
    )


if __name__ == "__main__":
    import time
    if ON_HF:
        demo.launch(server_name="0.0.0.0", server_port=7860)
    else:
        # Check if running on remote instance (has DATA_ROOT env var)
        # If so, bind to 0.0.0.0 for external access
        # Otherwise use share=True for local development
        if os.getenv("DATA_ROOT"):
            demo.launch(server_name="0.0.0.0", server_port=7860, allowed_paths=[str(ROOT_ABS)])
        else:
            demo.launch(share=True, allowed_paths=[str(ROOT_ABS)])
