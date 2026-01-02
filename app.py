# app.py
import time
import gradio as gr
import os, base64

from config import ROOT_ABS, VOTES_CSV, ON_HF
from operating_logic import (
    start_session,
    submit_choice,
    choose_left,
    choose_right,
    choose_both_good,
    choose_both_bad,
)

# =========================
# CSS
# =========================
CSS = """
.selected-btn { 
  outline: 3px solid #3B82F6 !important; 
  border-radius: 6px; 
}

/* 400x400 tiles */
.vote-tile {
  width: 400px;
  height: 400px;
  object-fit: contain;
  cursor: zoom-in;
  border-radius: 8px;
}

/* modal */
.img-modal {
  display: none;
  position: fixed;
  z-index: 9999;
  inset: 0;
  background: rgba(0,0,0,0.78);
  align-items: center;
  justify-content: center;
}
.img-modal.open { display: flex; }
.img-modal img {
  max-width: min(96vw, 1100px);
  max-height: 92vh;
  object-fit: contain;
  border-radius: 10px;
  cursor: zoom-out;
}
"""

# =========================
# Helpers
# =========================
def _to_abs(p: str) -> str:
    if not p:
        return ""
    if os.path.isabs(p) and os.path.exists(p):
        return p
    # try relative to ROOT_ABS
    cand = os.path.join(ROOT_ABS, p)
    return cand if os.path.exists(cand) else p

def _extract_path(x):
    if x is None:
        return ""
    if isinstance(x, str):
        return x
    if isinstance(x, dict):
        if "value" in x:
            return _extract_path(x["value"])
        if "path" in x:
            return _extract_path(x["path"])
    return ""

def _path_to_data_uri(p: str) -> str:
    p = _to_abs(p)
    if not p or not os.path.exists(p):
        return ""
    ext = os.path.splitext(p)[1].lower()
    mime = "image/png" if ext in [".png"] else "image/jpeg"
    with open(p, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"

def _img_html(img_id: str, modal_id: str, path_any) -> str:
    path = _extract_path(path_any)
    uri = _path_to_data_uri(path)
    if not uri:
        return "<div></div>"

    return f"""
<div style="display:flex; justify-content:center;">
  <img class="vote-tile" src="{uri}"
       onclick="document.getElementById('{modal_id}').classList.add('open')" />
</div>

<div id="{modal_id}" class="img-modal"
     onclick="this.classList.remove('open')">
  <img src="{uri}" onclick="this.parentElement.classList.remove('open')" />
</div>
"""


def start_session_ui(user_id: str):
    res = list(start_session(user_id))
    # outputs order: status(0), vote_box(1), poem_md(2), left(3), right(4), ...
    left_any = res[3]
    right_any = res[4]
    res[3] = _img_html("left_img", "left_modal", left_any)
    res[4] = _img_html("right_img", "right_modal", right_any)
    return tuple(res)

def submit_choice_ui(user_id, poem_title, left_path, right_path, choice, t_start_ms):
    res = list(submit_choice(user_id, poem_title, left_path, right_path, choice, t_start_ms))
    left_any = res[3]
    right_any = res[4]
    res[3] = _img_html("left_img", "left_modal", left_any)
    res[4] = _img_html("right_img", "right_modal", right_any)
    return tuple(res)

# =========================
# UI Layout
# =========================
with gr.Blocks(css=CSS, title="Image Preference Voting") as demo:
    gr.Markdown("# 唐诗配图投票")
    gr.Markdown("请选择一个选项（四选一）。")

    user_input = gr.Textbox(label="您的昵称", placeholder="e.g., 王维")
    start_btn = gr.Button("开始", variant="primary")

    status_md = gr.Markdown(visible=False)
    remaining_lbl = gr.Label(value="", visible=True)

    vote_box = gr.Group(visible=False)
    with vote_box:
        poem_md = gr.Markdown()

        with gr.Row():
            left_img = gr.HTML()   # <- custom click-to-modal, no UI
            right_img = gr.HTML()

        with gr.Row():
            btn_left = gr.Button("左边图片更好")
            btn_right = gr.Button("右边图片更好")

        with gr.Row():
            btn_good = gr.Button("两张都很好，难以选择")
            btn_bad = gr.Button("两张都很糟糕，无法选择")

        with gr.Row():
            submit_btn = gr.Button("提交", variant="primary")

    # ---- States ----
    user_state   = gr.State("")
    poem_state   = gr.State("")
    left_state   = gr.State("")
    right_state  = gr.State("")
    choice_state = gr.State("")
    t_start_ms   = gr.State(str(int(time.time() * 1000)))
    dl_votes     = gr.State(VOTES_CSV)

    # =========================
    # Wiring
    # =========================
    start_btn.click(
        start_session_ui,
        inputs=[user_input],
        outputs=[
            status_md,
            vote_box,
            poem_md,
            left_img,
            right_img,
            user_state,
            poem_state,
            left_state,
            right_state,
            choice_state,
            remaining_lbl,
            submit_btn,
            t_start_ms,
            dl_votes,
            btn_left,
            btn_right,
            btn_good,
            btn_bad,
        ],
    )

    btn_left.click(
        choose_left,
        inputs=[choice_state],
        outputs=[choice_state, submit_btn, btn_left, btn_right, btn_good, btn_bad],
    )
    btn_right.click(
        choose_right,
        inputs=[choice_state],
        outputs=[choice_state, submit_btn, btn_left, btn_right, btn_good, btn_bad],
    )
    btn_good.click(
        choose_both_good,
        inputs=[choice_state],
        outputs=[choice_state, submit_btn, btn_left, btn_right, btn_good, btn_bad],
    )
    btn_bad.click(
        choose_both_bad,
        inputs=[choice_state],
        outputs=[choice_state, submit_btn, btn_left, btn_right, btn_good, btn_bad],
    )

    submit_btn.click(
        submit_choice_ui,
        inputs=[user_state, poem_state, left_state, right_state, choice_state, t_start_ms],
        outputs=[
            status_md,
            vote_box,
            poem_md,
            left_img,
            right_img,
            user_state,
            poem_state,
            left_state,
            right_state,
            choice_state,
            remaining_lbl,
            t_start_ms,
            dl_votes,
            submit_btn,
            btn_left,
            btn_right,
            btn_good,
            btn_bad,
        ],
    )

if __name__ == "__main__":
    if ON_HF:
        demo.launch(server_name="0.0.0.0", server_port=7860)
    else:
        demo.launch(share=True, allowed_paths=[str(ROOT_ABS)])
