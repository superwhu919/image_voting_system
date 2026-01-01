# operating_logic.py
import random
import time

import gradio as gr

from config import MAX_PER_USER, VOTES_CSV
from catalog import CATALOG, POEM_INFO
from storage import user_count, write_vote


# =========================
# Helpers
# =========================
def remaining(uid: str) -> int:
    return max(0, MAX_PER_USER - user_count(uid))


def random_pair():
    """Pick a random poem and two distinct images under it."""
    poem_title = random.choice(list(CATALOG.keys()))
    left, right = random.sample(CATALOG[poem_title], 2)
    if random.random() < 0.5:
        left, right = right, left
    return poem_title, left, right


def next_pair():
    """Return (poem_title, poem_markdown, left_path, right_path)."""
    poem_title, left, right = random_pair()
    info = POEM_INFO.get(poem_title, {})
    author = info.get("author", "")
    content = info.get("content", "")

    poem_md = f"**{poem_title}**  \n**{author}**\n\n{content}"
    return poem_title, poem_md, left, right


# =========================
# Button selection handlers
# =========================
def choose_left(current_choice):
    return (
        "Left",
        gr.update(interactive=True),              # submit_btn
        gr.update(elem_classes=["selected-btn"]), # btn_left
        gr.update(elem_classes=[]),               # btn_right
        gr.update(elem_classes=[]),               # btn_good
        gr.update(elem_classes=[]),               # btn_bad
    )


def choose_right(current_choice):
    return (
        "Right",
        gr.update(interactive=True),
        gr.update(elem_classes=[]),
        gr.update(elem_classes=["selected-btn"]),
        gr.update(elem_classes=[]),
        gr.update(elem_classes=[]),
    )


def choose_both_good(current_choice):
    return (
        "BothGood",
        gr.update(interactive=True),
        gr.update(elem_classes=[]),
        gr.update(elem_classes=[]),
        gr.update(elem_classes=["selected-btn"]),
        gr.update(elem_classes=[]),
    )


def choose_both_bad(current_choice):
    return (
        "BothBad",
        gr.update(interactive=True),
        gr.update(elem_classes=[]),
        gr.update(elem_classes=[]),
        gr.update(elem_classes=[]),
        gr.update(elem_classes=["selected-btn"]),
    )


# =========================
# Start session
# =========================
def start_session(uid_input):
    """
    Outputs:
      status_md, vote_box, poem_md, left_img, right_img,
      user_state, poem_state, left_state, right_state, choice_state,
      remaining_lbl, submit_btn, t_start_ms, dl_votes,
      btn_left, btn_right, btn_good, btn_bad
    """
    uid = (uid_input or "").strip()
    now_ms = int(time.time() * 1000)

    if not uid:
        return (
            gr.update(value="请输入代码。", visible=True),          # status_md
            gr.update(visible=False),                            # vote_box
            gr.update(value=""),                                 # poem_md
            gr.update(value=None),                               # left_img
            gr.update(value=None),                               # right_img
            "", "", "", "", "",                                  # states
            gr.update(value=f"Remaining: 0 / {MAX_PER_USER}"),   # remaining_lbl
            gr.update(interactive=False),                        # submit_btn
            str(now_ms),                                         # t_start_ms
            gr.update(value=VOTES_CSV),                          # dl_votes (state only)
            gr.update(elem_classes=[]),                          # btn_left
            gr.update(elem_classes=[]),                          # btn_right
            gr.update(elem_classes=[]),                          # btn_good
            gr.update(elem_classes=[]),                          # btn_bad
        )

    rem = remaining(uid)
    if rem <= 0:
        return (
            gr.update(
                value=f"Thanks! You've reached the limit ({MAX_PER_USER}).",
                visible=True,
            ),
            gr.update(visible=False),
            gr.update(value=""),
            gr.update(value=None),
            gr.update(value=None),
            uid, "", "", "", "",
            gr.update(value=f"Remaining: 0 / {MAX_PER_USER}"),
            gr.update(interactive=False),
            str(now_ms),
            gr.update(value=VOTES_CSV),
            gr.update(elem_classes=[]),
            gr.update(elem_classes=[]),
            gr.update(elem_classes=[]),
            gr.update(elem_classes=[]),
        )

    poem_title, poem_md_val, left_path, right_path = next_pair()
    return (
        gr.update(value=f"Welcome, **{uid}**!", visible=True),  # status_md
        gr.update(visible=True),                                # vote_box
        gr.update(value=poem_md_val),                           # poem_md
        gr.update(value=left_path),                             # left_img
        gr.update(value=right_path),                            # right_img
        uid, poem_title, left_path, right_path, "",             # states
        gr.update(value=f"Remaining: {rem} / {MAX_PER_USER}"),  # remaining_lbl
        gr.update(interactive=False),                           # submit_btn
        str(now_ms),                                            # t_start_ms
        gr.update(value=VOTES_CSV),                             # dl_votes
        gr.update(elem_classes=[]),                             # btn_left
        gr.update(elem_classes=[]),                             # btn_right
        gr.update(elem_classes=[]),                             # btn_good
        gr.update(elem_classes=[]),                             # btn_bad
    )


# =========================
# Submit logic
# =========================
def submit_choice(uid, poem_title, left_path, right_path, chosen, t0):
    """
    Outputs:
      status_md, vote_box, poem_md, left_img, right_img,
      user_state, poem_state, left_state, right_state, choice_state,
      remaining_lbl, t_start_ms, dl_votes, submit_btn,
      btn_left, btn_right, btn_good, btn_bad
    """
    now_ms = int(time.time() * 1000)

    if not uid:
        return (
            gr.update(value="请输入代码并开始。", visible=True),
            gr.update(visible=False),
            gr.update(value=""),
            gr.update(value=None),
            gr.update(value=None),
            "", "", "", "", "",
            gr.update(value=f"Remaining: 0 / {MAX_PER_USER}"),
            str(now_ms),
            gr.update(value=VOTES_CSV),
            gr.update(interactive=False),
            gr.update(elem_classes=[]),
            gr.update(elem_classes=[]),
            gr.update(elem_classes=[]),
            gr.update(elem_classes=[]),
        )

    if not chosen:
        return (
            gr.update(value="请选择一个选项。", visible=True),
            gr.update(), gr.update(), gr.update(), gr.update(),
            uid, poem_title, left_path, right_path, chosen,
            gr.update(value=f"Remaining: {remaining(uid)} / {MAX_PER_USER}"),
            str(t0),
            gr.update(value=VOTES_CSV),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
        )

    if remaining(uid) <= 0:
        return (
            gr.update(
                value=f"Thanks! You've reached the limit ({MAX_PER_USER}).",
                visible=True,
            ),
            gr.update(visible=False),
            gr.update(value=""),
            gr.update(value=None),
            gr.update(value=None),
            uid, poem_title, left_path, right_path, "",
            gr.update(value=f"Remaining: 0 / {MAX_PER_USER}"),
            str(now_ms),
            gr.update(value=VOTES_CSV),
            gr.update(interactive=False),
            gr.update(elem_classes=[]),
            gr.update(elem_classes=[]),
            gr.update(elem_classes=[]),
            gr.update(elem_classes=[]),
        )

    preferred = left_path if chosen == "Left" else (right_path if chosen == "Right" else "")
    response_ms = now_ms - int(t0 or now_ms)

    write_vote(uid, poem_title, left_path, right_path, chosen, preferred, response_ms)

    poem_title_next, poem_md_next, left_next, right_next = next_pair()
    rem_after = remaining(uid)

    return (
        gr.update(value="已提交，下一组…", visible=True),
        gr.update(visible=True),
        gr.update(value=poem_md_next),
        gr.update(value=left_next),
        gr.update(value=right_next),
        uid, poem_title_next, left_next, right_next, "",
        gr.update(value=f"Remaining: {rem_after} / {MAX_PER_USER}"),
        str(now_ms),
        gr.update(value=VOTES_CSV),
        gr.update(interactive=False),
        gr.update(elem_classes=[]),
        gr.update(elem_classes=[]),
        gr.update(elem_classes=[]),
        gr.update(elem_classes=[]),
    )
