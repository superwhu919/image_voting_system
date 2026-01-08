# UI helper functions for image handling and path resolution
import os
import base64
from config import ROOT_ABS


def to_abs(p: str) -> str:
    """Convert path to absolute path."""
    if not p:
        return ""
    if os.path.isabs(p) and os.path.exists(p):
        return p
    # try relative to ROOT_ABS
    cand = os.path.join(ROOT_ABS, p)
    return cand if os.path.exists(cand) else p


def extract_path(x):
    """Extract file path from various input types."""
    if x is None:
        return ""
    if isinstance(x, str):
        return x
    if isinstance(x, dict):
        if "value" in x:
            return extract_path(x["value"])
        if "path" in x:
            return extract_path(x["path"])
    return ""


def path_to_data_uri(p: str) -> str:
    """Convert image file path to data URI."""
    p = to_abs(p)
    if not p or not os.path.exists(p):
        return ""
    ext = os.path.splitext(p)[1].lower()
    mime = "image/png" if ext in [".png"] else "image/jpeg"
    with open(p, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def img_html(img_id: str, modal_id: str, path_any) -> str:
    """Generate HTML for image display with modal."""
    path = extract_path(path_any)
    uri = path_to_data_uri(path)
    if not uri:
        return "<div></div>"

    return f"""
<div style="display:flex; justify-content:flex-start;">
  <img class="eval-image" src="{uri}"
       onclick="document.getElementById('{modal_id}').classList.add('open')" />
</div>

<div id="{modal_id}" class="img-modal"
     onclick="this.classList.remove('open')">
  <img src="{uri}" onclick="this.parentElement.classList.remove('open')" />
</div>
"""

