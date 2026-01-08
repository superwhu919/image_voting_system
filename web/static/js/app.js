// Main JavaScript for voting system

// API base URL
const API_BASE = '/api';

// State management
let currentSession = {
    user_id: null,
    user_age: null,
    user_gender: null,
    user_education: null,
    poem_title: null,
    image_path: null,
    image_url: null,
    options_dict: null,
    options_data: null,
    target_letter: null,
    phase1_choice: null,
    phase1_start_ms: null,
    phase2_start_ms: null,
    phase2_answers: {},
};

// Initialize image modal once on page load
function initImageModal() {
    let imageModal = document.getElementById('image-modal');
    if (!imageModal) {
        const body = document.body;
        imageModal = document.createElement('div');
        imageModal.id = 'image-modal';
        imageModal.className = 'img-modal';
        imageModal.onclick = function() { this.classList.remove('open'); };
        body.appendChild(imageModal);
    }
    return imageModal;
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initImageModal();
    setupEventListeners();
});

function setupEventListeners() {
    // Start button
    const startBtn = document.getElementById('start-btn');
    if (startBtn) {
        startBtn.addEventListener('click', handleStart);
    }
    
    // Reveal button
    const revealBtn = document.getElementById('reveal-btn');
    if (revealBtn) {
        revealBtn.addEventListener('click', handleReveal);
    }
    
    // Submit button
    const submitBtn = document.getElementById('submit-btn');
    if (submitBtn) {
        submitBtn.addEventListener('click', handleSubmit);
    }
    
    // Phase 1 radio buttons
    document.querySelectorAll('input[name="phase1_choice"]').forEach(radio => {
        radio.addEventListener('change', handlePhase1Choice);
    });
    
    // Phase 2 radio buttons
    document.querySelectorAll('input[name^="q"]').forEach(radio => {
        radio.addEventListener('change', handlePhase2Answer);
    });
    
    // Image modal
    setupImageModal();
}

function handleStart() {
    const userInput = document.getElementById('user-input');
    const userAgeInput = document.getElementById('user-age');
    const userGenderInput = document.getElementById('user-gender');
    const userEducationInput = document.getElementById('user-education');
    
    const userId = userInput.value.trim();
    const userAgeStr = userAgeInput ? userAgeInput.value.trim() : '';
    const userAge = userAgeStr ? parseInt(userAgeStr) : null;
    const userGender = userGenderInput ? userGenderInput.value.trim() : '';
    const userEducation = userEducationInput ? userEducationInput.value.trim() : '';
    
    if (!userId) {
        showStatus('请输入您的昵称。', 'error');
        return;
    }
    
    if (!userAge || isNaN(userAge) || userAge <= 0) {
        showStatus('请输入有效的年龄。', 'error');
        return;
    }
    
    if (!userGender) {
        showStatus('请选择性别。', 'error');
        return;
    }
    
    if (!userEducation) {
        showStatus('请选择教育程度。', 'error');
        return;
    }
    
    fetch(`${API_BASE}/start`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
            user_id: userId,
            age: userAge,
            gender: userGender,
            education: userEducation
        }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            // Disable user input field after successful start
            if (userInput) {
                userInput.disabled = true;
                userInput.setAttribute('readonly', 'readonly');
            }
            
            // Disable user info fields
            if (userAgeInput) userAgeInput.disabled = true;
            if (userGenderInput) userGenderInput.disabled = true;
            if (userEducationInput) userEducationInput.disabled = true;
            
            // Disable start button
            const startBtn = document.getElementById('start-btn');
            if (startBtn) {
                startBtn.disabled = true;
            }
            
            currentSession = {
                user_id: data.user_id,
                user_age: userAge,
                user_gender: userGender,
                user_education: userEducation,
                poem_title: data.poem_title,
                image_path: data.image_path,
                image_url: data.image_url || null,
                options_dict: data.options_dict,
                options_data: data.options_data,
                target_letter: data.target_letter,
                phase1_choice: null,
                phase1_start_ms: data.phase1_start_ms,
                phase2_start_ms: data.phase2_start_ms,
                phase2_answers: {},
            };
            updateUIForPhase1(data);
            showStatus(data.message, 'success');
            updateRemaining(data.remaining);
        } else if (data.name_taken) {
            // Name is taken - allow user to change it
            showStatus(data.message, 'error');
            // Keep all fields enabled so user can change name and try again
            if (userInput) {
                userInput.focus();
                userInput.select();
            }
        } else {
            showStatus(data.message, 'error');
            if (data.remaining !== undefined) {
                updateRemaining(data.remaining);
            }
        }
    })
    .catch(error => {
        showStatus('发生错误，请重试。', 'error');
    });
}

function handlePhase1Choice(event) {
    const choice = event.target.value;
    currentSession.phase1_choice = choice;
    
    // Enable reveal button and add visual feedback
    const revealBtn = document.getElementById('reveal-btn');
    if (revealBtn) {
        revealBtn.disabled = false;
        revealBtn.classList.remove('disabled');
        revealBtn.classList.remove('btn-secondary');
        revealBtn.classList.add('btn-primary');
    }
}

function handleReveal() {
    if (!currentSession.phase1_choice) {
        showStatus('请先选择一首诗。', 'error');
        return;
    }
    
    fetch(`${API_BASE}/reveal`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            user_id: currentSession.user_id,
            poem_title: currentSession.poem_title,
            image_path: currentSession.image_path,
            options_dict: currentSession.options_dict,
            target_letter: currentSession.target_letter,
            phase1_choice: currentSession.phase1_choice,
            phase1_start_ms: currentSession.phase1_start_ms,
        }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            currentSession.phase2_start_ms = data.phase2_start_ms;
            
            // Show answer next to reveal button
            const revealAnswer = document.getElementById('reveal-answer');
            if (revealAnswer && data.target_letter) {
                const isCorrect = data.is_correct;
                const answerText = `正确答案: ${data.target_letter} ${isCorrect ? '✓ 正确！' : '✗ 不正确'}`;
                revealAnswer.textContent = answerText;
                revealAnswer.className = isCorrect ? 'text-success' : 'text-danger';
                revealAnswer.classList.remove('hidden');
            }
            
            // Disable reveal button after revealing
            const revealBtn = document.getElementById('reveal-btn');
            if (revealBtn) {
                revealBtn.disabled = true;
                revealBtn.classList.add('disabled');
            }
            
            updateUIForPhase2(data);
            // Don't show status message at top, answer is shown next to button
        } else {
            showStatus(data.message, 'error');
        }
    })
    .catch(error => {
        showStatus('发生错误，请重试。', 'error');
    });
}

function handlePhase2Answer(event) {
    const qId = event.target.name;
    const answer = event.target.value;
    
    fetch(`${API_BASE}/update-answer`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            q_id: qId,
            answer: answer,
            phase2_answers: currentSession.phase2_answers,
        }),
    })
    .then(response => response.json())
    .then(data => {
        currentSession.phase2_answers = data.phase2_answers;
        
        // Enable submit button if all answered
        const submitBtn = document.getElementById('submit-btn');
        if (submitBtn) {
            submitBtn.disabled = !data.all_answered;
            if (data.all_answered) {
                submitBtn.classList.remove('disabled');
            }
        }
    })
    .catch(error => {
        // Silently handle error
    });
}

function handleSubmit() {
    if (!currentSession.phase1_choice) {
        showStatus('请完成第一阶段选择。', 'error');
        return;
    }
    
    const allAnswered = Object.keys(currentSession.phase2_answers).length >= 12;
    if (!allAnswered) {
        showStatus('请完成所有第二阶段问题。', 'error');
        return;
    }
    
    fetch(`${API_BASE}/submit`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            user_id: currentSession.user_id,
            user_age: currentSession.user_age,
            user_gender: currentSession.user_gender,
            user_education: currentSession.user_education,
            poem_title: currentSession.poem_title,
            image_path: currentSession.image_path,
            options_dict: currentSession.options_dict,
            target_letter: currentSession.target_letter,
            phase1_choice: currentSession.phase1_choice,
            phase1_response_ms: 0, // Will be calculated on server
            phase2_answers: currentSession.phase2_answers,
            phase2_start_ms: currentSession.phase2_start_ms,
            phase1_start_ms: currentSession.phase1_start_ms,
        }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            // Reset for next evaluation (preserve user info)
            const preservedUserInfo = {
                user_age: currentSession.user_age,
                user_gender: currentSession.user_gender,
                user_education: currentSession.user_education,
            };
            currentSession = {
                user_id: data.user_id,
                ...preservedUserInfo,
                poem_title: data.poem_title,
                image_path: data.image_path,
                image_url: data.image_url || null,
                options_dict: data.options_dict,
                options_data: data.options_data,
                target_letter: data.target_letter,
                phase1_choice: null,
                phase1_start_ms: data.phase1_start_ms,
                phase2_start_ms: data.phase2_start_ms,
                phase2_answers: {},
            };
            updateUIForPhase1(data);
            showStatus(data.message, 'success');
            updateRemaining(data.remaining);
        } else {
            showStatus(data.message, 'error');
            if (data.remaining !== undefined) {
                updateRemaining(data.remaining);
            }
        }
    })
    .catch(error => {
        showStatus('发生错误，请重试。', 'error');
    });
}

function updateUIForPhase1(data) {
    // Show evaluation box
    const evalBox = document.getElementById('evaluation-box');
    if (evalBox) {
        evalBox.classList.remove('hidden');
    }
    
    // Update Phase 1 question text from questions.json (q0)
    const phase1Question = document.getElementById('phase1-question');
    if (phase1Question && data.q0 && data.q0.question) {
        const questionId = data.q0.id ? data.q0.id.toUpperCase() : 'Q0';
        const newText = `<strong>${questionId}. ${escapeHtml(data.q0.question)}</strong>`;
        phase1Question.innerHTML = newText;
    }
    
    // Update image - use image_url if available, otherwise construct from image_path
    const imageUrl = data.image_url || currentSession.image_url || `/static/images/${data.image_path.split('/').pop()}`;
    updateImage(imageUrl);
    
    // Update poem choices
    updatePoemChoices(data.options_data);
    
    // Hide phase 2
    const phase2Box = document.getElementById('phase2-box');
    if (phase2Box) {
        phase2Box.classList.add('hidden');
    }
    
    // Reset reveal button
    const revealBtn = document.getElementById('reveal-btn');
    if (revealBtn) {
        revealBtn.disabled = true;
        revealBtn.classList.add('disabled');
        revealBtn.classList.remove('btn-primary');
        revealBtn.classList.add('btn-secondary');
    }
    
    // Hide reveal answer
    const revealAnswer = document.getElementById('reveal-answer');
    if (revealAnswer) {
        revealAnswer.classList.add('hidden');
        revealAnswer.textContent = '';
    }
    
    // Reset phase 1 choice
    document.querySelectorAll('input[name="phase1_choice"]').forEach(radio => {
        radio.checked = false;
    });
    currentSession.phase1_choice = null;
}

function updateUIForPhase2(data) {
    // Show phase 2 box
    const phase2Box = document.getElementById('phase2-box');
    if (phase2Box) {
        phase2Box.classList.remove('hidden');
    }
    
    // Update revealed poem (both left and right versions)
    if (data.poem_data) {
        // Remove 《》 characters from poem content
        const cleanedContent = data.poem_data.content.replace(/[《》]/g, '');
        
        // Left side poem (original)
        const poemTitle = document.getElementById('poem-title');
        const poemAuthor = document.getElementById('poem-author');
        const poemContent = document.getElementById('poem-content');
        
        if (poemTitle) poemTitle.textContent = data.poem_data.title;
        if (poemAuthor) poemAuthor.innerHTML = `<strong>${escapeHtml(data.poem_data.author)}</strong>`;
        if (poemContent) poemContent.textContent = cleanedContent;
        
        // Right side poem (below image)
        const poemTitleRight = document.getElementById('poem-title-right');
        const poemAuthorRight = document.getElementById('poem-author-right');
        const poemContentRight = document.getElementById('poem-content-right');
        
        if (poemTitleRight) poemTitleRight.textContent = data.poem_data.title;
        if (poemAuthorRight) poemAuthorRight.innerHTML = `<strong>${escapeHtml(data.poem_data.author)}</strong>`;
        if (poemContentRight) poemContentRight.textContent = cleanedContent;
    }
    
    // Display image in Phase 2
    const phase2ImageContainer = document.getElementById('phase2-image-container');
    if (phase2ImageContainer && currentSession.image_url) {
        // Get or create image modal
        let imageModal = document.getElementById('image-modal') || initImageModal();
        
        // Set modal image source
        let modalImg = imageModal.querySelector('img');
        if (!modalImg) {
            modalImg = document.createElement('img');
            modalImg.onclick = function(e) { 
                e.stopPropagation(); 
                imageModal.classList.remove('open'); 
            };
            imageModal.appendChild(modalImg);
        }
        modalImg.src = currentSession.image_url;
        
        // Set container image
        phase2ImageContainer.innerHTML = `
            <img class="eval-image" src="${currentSession.image_url}" 
                 style="width: 100%; max-width: 500px; height: auto; display: block; cursor: zoom-in;"
                 onclick="document.getElementById('image-modal').classList.add('open')" />
        `;
    }
    
    // Render questions if not already rendered
    renderQuestions(data.questions);
    
    // Reset submit button
    const submitBtn = document.getElementById('submit-btn');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.classList.add('disabled');
    }
    
    // Reset phase 2 answers
    currentSession.phase2_answers = {};
    document.querySelectorAll('input[name^="q"]').forEach(radio => {
        radio.checked = false;
    });
}

function updateImage(imageUrl) {
    const imageContainer = document.getElementById('image-container');
    if (imageContainer) {
        // Get or create image modal
        let imageModal = document.getElementById('image-modal') || initImageModal();
        
        // Set modal image source
        let modalImg = imageModal.querySelector('img');
        if (!modalImg) {
            modalImg = document.createElement('img');
            modalImg.onclick = function(e) { 
                e.stopPropagation(); 
                imageModal.classList.remove('open'); 
            };
            imageModal.appendChild(modalImg);
        }
        modalImg.src = imageUrl;
        
        // Set container image
        imageContainer.innerHTML = `
            <div style="display:flex; justify-content:flex-start;">
                <img class="eval-image" src="${imageUrl}" 
                     style="cursor: zoom-in;"
                     onclick="document.getElementById('image-modal').classList.add('open')" />
            </div>
        `;
    }
}

function updatePoemChoices(optionsData) {
    const choicesContainer = document.getElementById('poem-choices');
    if (!choicesContainer) return;
    
    let html = '';
    for (const letter of ['A', 'B', 'C', 'D']) {
        const poem = optionsData[letter];
        if (!poem) continue;
        
        html += `
            <div class="poem-choice-container">
                <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px;">
                    <input type="radio" name="phase1_choice" id="radio_${letter.toLowerCase()}" 
                           value="${letter}" class="poem-choice-radio" />
                    <label for="radio_${letter.toLowerCase()}" class="poem-choice-title">
                        ${escapeHtml(poem.title)}
                    </label>
                </div>
                <div class="poem-choice-author">${escapeHtml(poem.author)}</div>
                ${poem.has_more_content ? `
                    <div class="poem-choice-preview">${escapeHtml(poem.preview)}</div>
                    <button type="button" class="poem-expand-btn" 
                            onclick="togglePoem('poem_${letter.toLowerCase()}')">
                        <span id="toggle_poem_${letter.toLowerCase()}">展开完整内容</span>
                    </button>
                    <div id="poem_${letter.toLowerCase()}" class="poem-choice-full hidden">${escapeHtml(poem.content.trim().replace(/^\s+/gm, ''))}</div>
                ` : `
                    <div class="poem-choice-full">${escapeHtml(poem.content.trim().replace(/^\s+/gm, ''))}</div>
                `}
            </div>
        `;
    }
    
    choicesContainer.innerHTML = html;
    
    // Re-attach event listeners
    document.querySelectorAll('input[name="phase1_choice"]').forEach(radio => {
        radio.addEventListener('change', handlePhase1Choice);
    });
}

function renderQuestions(questions) {
    const questionsContainer = document.getElementById('phase2-questions');
    if (!questionsContainer || questionsContainer.innerHTML.trim() !== '') {
        return; // Already rendered
    }
    
    let html = '';
    
    // Render all questions q1-q12
    for (let i = 1; i <= 12; i++) {
        const qId = `q${i}`;
        if (questions[qId]) {
            html += renderQuestion(qId, questions[qId]);
        }
    }
    
    questionsContainer.innerHTML = html;
    
    // Attach event listeners
    document.querySelectorAll('input[name^="q"]').forEach(radio => {
        radio.addEventListener('change', handlePhase2Answer);
    });
}

function renderQuestion(qId, question) {
    if (!question || !question.question) {
        return '';
    }
    
    // Use question ID from JSON, fallback to qId parameter
    const questionId = question.id ? question.id.toUpperCase() : qId.toUpperCase();
    
    let html = `
        <div class="phase2-question">
            <label><strong>${questionId}.</strong> ${escapeHtml(question.question)}</label>
    `;
    
    if (question.options && Array.isArray(question.options)) {
        for (const option of question.options) {
            html += `
                <div class="form-check">
                    <input class="form-check-input" type="radio" name="${qId}" 
                           id="${qId}_${option.value}" value="${option.value}">
                    <label class="form-check-label" for="${qId}_${option.value}">
                        ${escapeHtml(option.label)}
                    </label>
                </div>
            `;
        }
    }
    
    html += '</div>';
    return html;
}

function togglePoem(id) {
    const elem = document.getElementById(id);
    const toggle = document.getElementById('toggle_' + id);
    if (elem && toggle) {
        if (elem.classList.contains('hidden')) {
            elem.classList.remove('hidden');
            toggle.textContent = '收起';
        } else {
            elem.classList.add('hidden');
            toggle.textContent = '展开完整内容';
        }
    }
}

function setupImageModal() {
    // Already handled in updateImage
}

function showStatus(message, type = 'info') {
    const statusDiv = document.getElementById('status-message');
    if (statusDiv) {
        statusDiv.textContent = message;
        statusDiv.className = `status-message status-${type}`;
        statusDiv.classList.remove('hidden');
    }
}

function updateRemaining(count) {
    const remainingDiv = document.getElementById('remaining-count');
    if (remainingDiv) {
        remainingDiv.textContent = `剩余: ${count} / ${10}`;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

