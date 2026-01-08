# UI styles and CSS

CSS = """
.selected-btn { 
  outline: 3px solid #3B82F6 !important; 
  border-radius: 6px; 
}

/* Image display */
.eval-image {
  width: 500px;
  height: 500px;
  object-fit: contain;
  cursor: zoom-in;
  border-radius: 8px;
}

/* Image container - left align */
.image-container {
  display: flex;
  justify-content: flex-start;
  align-items: flex-start;
}

/* Inline radio buttons with choices */
.radio-choice-container {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 15px;
}

.radio-choice-container .markdown {
  flex: 1;
}

.radio-choice-container .form-radio {
  margin-top: 5px;
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

/* Hide the phase1 choice state input but keep it in DOM for JavaScript */
input#phase1_choice_state_input,
input[id*="phase1_choice_state_input"],
textarea#phase1_choice_state_input,
textarea[id*="phase1_choice_state_input"] {
  position: absolute !important;
  opacity: 0 !important;
  pointer-events: auto !important;
  width: 1px !important;
  height: 1px !important;
  left: -9999px !important;
  top: -9999px !important;
  overflow: hidden !important;
}
"""

