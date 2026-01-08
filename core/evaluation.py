# Core evaluation logic: poem selection and formatting
import random
from data.catalog import CATALOG, POEM_INFO, get_distractors


def get_evaluation_item():
    """
    Get a random poem with its image and 3 distractors for Phase 1.
    Returns: (poem_title, image_path, distractors_list, poem_options_dict, target_letter)
    poem_options_dict: {"A": poem_title, "B": distractor1, "C": distractor2, "D": distractor3}
    """
    keys = list(CATALOG.keys())
    if not keys:
        raise RuntimeError("CATALOG is empty (no valid images found).")

    target_title = random.choice(keys)
    image_path = CATALOG[target_title]
    
    # Get 3 pre-defined similar distractors from CSV
    distractor_titles = get_distractors(target_title, CATALOG, POEM_INFO, num_distractors=3)
    
    # Create options: A = target, B/C/D = distractors (shuffled)
    all_options = [target_title] + distractor_titles
    random.shuffle(all_options)
    
    # Find which letter is the target
    target_letter = None
    options_dict = {}
    for i, title in enumerate(all_options):
        letter = chr(65 + i)  # A, B, C, D
        options_dict[letter] = title
        if title == target_title:
            target_letter = letter
    
    return target_title, image_path, distractor_titles, options_dict, target_letter


def format_poem_choice_html(title: str, letter: str, choice_id: str) -> str:
    """Format a poem choice with inline radio button and collapsible full content."""
    info = POEM_INFO.get(title, {})
    author = info.get("author", "")
    content = info.get("content", "")
    
    # Create a unique ID for this choice's collapsible section
    collapsible_id = f"poem_{choice_id}"
    
    # Show first 2-3 lines as preview
    lines = content.split('\n') if content else []
    preview_lines = lines[:3] if len(lines) > 3 else lines
    preview = '\n'.join(preview_lines)
    full_content = content
    
    # Check if there's more content to show (only show unfold button if needed)
    has_more_content = preview != full_content
    
    # Escape HTML special characters in content
    def escape_html(text):
        return (text.replace('&', '&amp;')
                   .replace('<', '&lt;')
                   .replace('>', '&gt;')
                   .replace('"', '&quot;')
                   .replace("'", '&#39;'))
    
    preview_escaped = escape_html(preview)
    full_escaped = escape_html(full_content)
    title_escaped = escape_html(title)
    author_escaped = escape_html(author)
    
    # Build the unfold button HTML only if there's more content
    unfold_button_html = ""
    if has_more_content:
        unfold_button_html = f"""
    <div style="margin-left: 30px; margin-top: 10px;">
        <button type="button" id="btn_{collapsible_id}" 
                onclick="(function() {{
                    var elem = document.getElementById('{collapsible_id}');
                    var toggle = document.getElementById('toggle_{collapsible_id}');
                    if (elem && toggle) {{
                        if (elem.style.display === 'none' || elem.style.display === '') {{
                            elem.style.display = 'block';
                            toggle.textContent = '收起';
                        }} else {{
                            elem.style.display = 'none';
                            toggle.textContent = '展开完整内容';
                        }}
                    }}
                }})();"
                style="background: none; border: 1px solid #ccc; padding: 5px 10px; cursor: pointer; border-radius: 4px; font-size: 0.9em;">
            <span id="toggle_{collapsible_id}">展开完整内容</span>
        </button>
        <div id="{collapsible_id}" style="display: none; margin-top: 10px; white-space: pre-wrap; padding: 10px; background: #f5f5f5; border-radius: 4px;">
            {full_escaped}
        </div>
    </div>"""
    # If no more content, don't add any extra div - just show preview
    
    return f"""
<div class="poem-choice-container" style="margin-bottom: 20px; padding: 15px; border: 1px solid #e0e0e0; border-radius: 8px;">
    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px;">
        <input type="radio" name="phase1_choice" id="radio_{choice_id}" value="{letter}" 
               onchange="(function() {{
                   // Uncheck other radio buttons first
                   document.querySelectorAll('input[name=\\'phase1_choice\\']').forEach(r => {{
                       if (r.id !== 'radio_{choice_id}') r.checked = false;
                   }});
                   
                   // Update the hidden Gradio Radio component which will trigger the reveal button
                   // Find the hidden radio by ID
                   var hiddenRadioContainer = document.getElementById('phase1_choice_hidden_radio');
                   var targetRadio = null;
                   
                   if (hiddenRadioContainer) {{
                       // Find the radio input with the matching value within the container
                       var radios = hiddenRadioContainer.querySelectorAll('input[type=\\'radio\\']');
                       for (var i = 0; i < radios.length; i++) {{
                           if (radios[i].value === '{letter}') {{
                               targetRadio = radios[i];
                               break;
                           }}
                       }}
                   }} else {{
                       // Fallback: search all radio inputs for one with the value
                       var allRadios = document.querySelectorAll('input[type=\\'radio\\']');
                       for (var i = 0; i < allRadios.length; i++) {{
                           var r = allRadios[i];
                           var id = r.id || '';
                           var name = r.name || '';
                           if ((id.includes('phase1_choice_hidden') || name.includes('phase1_choice_hidden')) && r.value === '{letter}') {{
                               targetRadio = r;
                               break;
                           }}
                       }}
                   }}
                   
                   if (targetRadio) {{
                       // Select the radio option - this will trigger Gradio's change event
                       targetRadio.checked = true;
                       targetRadio.click();
                       // Trigger change event to ensure Gradio picks it up
                       var changeEvent = new Event('change', {{ bubbles: true, cancelable: true }});
                       targetRadio.dispatchEvent(changeEvent);
                   }}
               }})();" />
        <label for="radio_{choice_id}" onclick="document.getElementById('radio_{choice_id}').click();" style="font-weight: bold; font-size: 1.1em; cursor: pointer; flex: 1;">
            {title_escaped}
        </label>
    </div>
    <div style="margin-left: 30px; color: #666; font-style: italic; margin-bottom: 10px;">
        {author_escaped}
    </div>
    <div style="margin-left: 30px; white-space: pre-wrap; margin-bottom: {10 if has_more_content else 0}px;">
        {preview_escaped}
    </div>
    {unfold_button_html}
</div>
"""


def format_poem_full(title: str) -> str:
    """Format full poem for Phase 2 display."""
    info = POEM_INFO.get(title, {})
    author = info.get("author", "")
    content = info.get("content", "")
    return f"**{title}**\n**{author}**\n\n{content}"

