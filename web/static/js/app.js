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
    image_type: null,
    options_dict: null,
    options_data: null,
    target_letter: null,
    phase1_choice: null,
    phase1_start_ms: null,
    phase1_answers: {},  // Answers to q1-2 and q1-3
    phase2_start_ms: null,
    phase2_answers: {},
    answer_revealed: false,  // Track if answer has been revealed
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
    updateCoverage();  // Load coverage metrics on page load
});

function setupEventListeners() {
    // Start button
    const startBtn = document.getElementById('start-btn');
    if (startBtn) {
        // Use click event, not submit - this prevents any form submission behavior
        startBtn.addEventListener('click', function(event) {
            event.preventDefault(); // Prevent any default behavior
            event.stopPropagation(); // Stop event bubbling
            handleStart();
        });
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
        // Prevent clicks if answer has been revealed
        radio.addEventListener('click', function(event) {
            if (currentSession.answer_revealed) {
                event.preventDefault();
                event.stopPropagation();
                return false;
            }
        });
    });
    
    // Phase 2 radio buttons
    document.querySelectorAll('input[name^="q"]').forEach(radio => {
        radio.addEventListener('change', handlePhase2Answer);
    });
    
    // Image modal
    setupImageModal();
}

function handleStart(userInfoOverride = null) {
    // Get input elements - query fresh each time to avoid stale references
    const userInput = document.getElementById('user-input');
    const userAgeInput = document.getElementById('user-age');
    const userGenderInput = document.getElementById('user-gender');
    const userEducationInput = document.getElementById('user-education');
    
    // Use override if provided (for retries), otherwise read from inputs
    let userId, userAge, userGender, userEducation;
    if (userInfoOverride) {
        userId = userInfoOverride.userId || '';
        userAge = userInfoOverride.userAge;
        userGender = userInfoOverride.userGender || '';
        userEducation = userInfoOverride.userEducation || '';
    } else {
        // Read values from input elements
        // IMPORTANT: Read .value property directly - this gets the current value
        // getAttribute('value') only returns the initial HTML attribute, not the current value
        if (!userInput) {
            showStatus('系统错误：找不到用户名输入框。', 'error');
            return;
        }
        
        // Read username - use .value property (not getAttribute)
        // .value property always returns a string (empty string "" if no value entered)
        // Ensure we read the actual current value
        userId = String(userInput.value || '').trim();
        
        // Read age
        if (userAgeInput) {
            const ageStr = (userAgeInput.value || '').trim();
            userAge = ageStr ? parseInt(ageStr) : null;
        } else {
            userAge = null;
        }
        
        // Read gender (select element)
        if (userGenderInput) {
            userGender = (userGenderInput.value || '').trim();
        } else {
            userGender = '';
        }
        
        // Read education (select element)
        if (userEducationInput) {
            userEducation = (userEducationInput.value || '').trim();
        } else {
            userEducation = '';
        }
    }
    
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
    
    // Debug logging
    const requestData = { 
        user_id: userId,
        age: userAge,
        gender: userGender,
        education: userEducation
    };
    
    fetch(`${API_BASE}/start`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData),
    })
    .then(response => {
        return response.json();
    })
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
                image_type: data.image_type || null,
                options_dict: data.options_dict,
                options_data: data.options_data,
                target_letter: data.target_letter,
                phase1_choice: null,
                phase1_answers: {},
                phase1_start_ms: data.phase1_start_ms,
                phase2_start_ms: data.phase2_start_ms,
                phase2_answers: {},
                answer_revealed: false,
                questions: {}, // Initialize questions object
            };
            updateUIForPhase1(data);
            showStatus(data.message, 'success');
            updateRemaining(data.remaining, data.user_limit || 10);
            updateCoverage();  // Update coverage metrics after start
        } else if (data.status === 'limit_reached') {
            // User has hit 10 limits - show modal to ask if they want to continue
            // Don't disable fields yet - wait for user's decision
            // Store user info for retry
            const storedUserInfo = {
                userId: userId,
                userAge: userAge,
                userGender: userGender,
                userEducation: userEducation
            };
            
            // Verify we have valid user info
            if (!storedUserInfo.userId || !storedUserInfo.userAge || !storedUserInfo.userGender || !storedUserInfo.userEducation) {
                console.error('Missing user info:', storedUserInfo);
                showStatus('错误：用户信息不完整。请重新填写并重试。', 'error');
                return;
            }
            
            showLimitExtensionModal(
                data.message + '\n\n点击"是"将增加您的限制 5 次。',
                () => {
                    // User clicked Yes - increase limit and retry start
                    if (!storedUserInfo.userId) {
                        showStatus('错误：无法获取用户信息。', 'error');
                        return;
                    }
                    
                    fetch(`${API_BASE}/increase-limit`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ 
                            user_id: storedUserInfo.userId
                        }),
                    })
                    .then(response => response.json())
                    .then(limitData => {
                        if (limitData.status === 'success') {
                            showStatus(limitData.message, 'success');
                            // Retry the start request with stored user info
                            handleStart(storedUserInfo);
                        } else {
                            showStatus('增加限制时发生错误，请重试。', 'error');
                        }
                    })
                    .catch(error => {
                        console.error('Error increasing limit:', error);
                        showStatus('发生错误，请重试。', 'error');
                    });
                },
                () => {
                    // User clicked No - show thank you message
                    showStatus('感谢您的参与！', 'success');
                    // Hide evaluation box if visible
                    const evalBox = document.getElementById('evaluation-box');
                    if (evalBox) {
                        evalBox.classList.add('hidden');
                    }
                    if (data.remaining !== undefined) {
                        updateRemaining(data.remaining, data.user_limit || 10);
                    }
                }
            );
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
                updateRemaining(data.remaining, data.user_limit || 10);
            }
        }
    })
    .catch(error => {
        showStatus('发生错误，请重试。', 'error');
    });
}

function handlePhase1Choice(event) {
    // Prevent changing choice after answer has been revealed
    if (currentSession.answer_revealed) {
        event.preventDefault();
        event.stopPropagation();
        // Restore the previous selection
        const previousChoice = currentSession.phase1_choice;
        document.querySelectorAll('input[name="phase1_choice"]').forEach(radio => {
            radio.checked = (radio.value === previousChoice);
        });
        return;
    }
    
    const choice = event.target.value;
    currentSession.phase1_choice = choice;
    
    // Questions are already shown, just check if all are answered
    // (q1-2 and q1-3 are shown immediately when Phase 1 loads)
    checkPhase1Complete();
}

function showPhase1Questions() {
    const phase1QuestionsContainer = document.getElementById('phase1-questions');
    const phase1QuestionsContent = document.getElementById('phase1-questions-container');
    
    if (!phase1QuestionsContainer || !phase1QuestionsContent) {
        return;
    }
    
    // Get questions from current session data
    const questions = currentSession.questions || {};
    const q1_2 = questions['q1-2'];
    const q1_3 = questions['q1-3'];
    
    if (!q1_2 || !q1_3) {
        return;
    }
    
    let html = '';
    
    // Render q1-2
    if (q1_2) {
        html += renderPhase1Question('q1-2', q1_2);
    }
    
    // Render q1-3
    if (q1_3) {
        html += renderPhase1Question('q1-3', q1_3);
    }
    
    phase1QuestionsContent.innerHTML = html;
    phase1QuestionsContainer.classList.remove('hidden');
    // Override !important from .hidden class
    phase1QuestionsContainer.style.setProperty('display', 'block', 'important');
    
    // Attach event listeners
    document.querySelectorAll('input[name^="q1-"]').forEach(radio => {
        radio.addEventListener('change', handlePhase1Answer);
    });
}

function renderPhase1Question(qId, question) {
    if (!question || !question.question) {
        return '';
    }
    
    const questionId = question.id ? question.id.toUpperCase() : qId.toUpperCase();
    
    let html = `
        <div class="phase1-question mb-3">
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

function handlePhase1Answer(event) {
    const qId = event.target.name;
    const answer = event.target.value;
    
    if (!currentSession.phase1_answers) {
        currentSession.phase1_answers = {};
    }
    
    currentSession.phase1_answers[qId] = answer;
    
    // Check if all Phase 1 questions are answered
    checkPhase1Complete();
}

function checkPhase1Complete() {
    // Check if poem is selected
    if (!currentSession.phase1_choice) {
        return;
    }
    
    // Check if q1-2 and q1-3 are answered
    const phase1Answers = currentSession.phase1_answers || {};
    const q1_2_answered = phase1Answers['q1-2'];
    const q1_3_answered = phase1Answers['q1-3'];
    
    const revealBtn = document.getElementById('reveal-btn');
    if (revealBtn) {
        if (q1_2_answered && q1_3_answered) {
            revealBtn.disabled = false;
            revealBtn.classList.remove('disabled');
            revealBtn.classList.remove('btn-secondary');
            revealBtn.classList.add('btn-primary');
        } else {
            revealBtn.disabled = true;
            revealBtn.classList.add('disabled');
            revealBtn.classList.remove('btn-primary');
            revealBtn.classList.add('btn-secondary');
        }
    }
}

function handleReveal() {
    if (!currentSession.phase1_choice) {
        showStatus('请先选择一首诗。', 'error');
        return;
    }
    
    // Check if all Phase 1 questions are answered
    const phase1Answers = currentSession.phase1_answers || {};
    if (!phase1Answers['q1-2'] || !phase1Answers['q1-3']) {
        showStatus('请先回答所有问题。', 'error');
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
            phase1_answers: currentSession.phase1_answers,
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
            
            // Mark answer as revealed and disable all phase 1 radio buttons
            currentSession.answer_revealed = true;
            document.querySelectorAll('input[name="phase1_choice"]').forEach(radio => {
                radio.disabled = true;
                radio.style.pointerEvents = 'none';
            });
            // Also disable labels to prevent clicking them
            document.querySelectorAll('label[for^="radio_"]').forEach(label => {
                label.style.pointerEvents = 'none';
                label.style.cursor = 'not-allowed';
            });
            // Disable Phase 1 additional questions
            document.querySelectorAll('input[name^="q1-"]').forEach(radio => {
                radio.disabled = true;
                radio.style.pointerEvents = 'none';
            });
            document.querySelectorAll('label[for^="q1-"]').forEach(label => {
                label.style.pointerEvents = 'none';
                label.style.cursor = 'not-allowed';
            });
            
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
    
    // Get the number of Phase 2 questions from the last reveal response
    // We'll check this dynamically by counting questions in phase2-questions container
    const phase2Questions = document.querySelectorAll('#phase2-questions .phase2-question');
    const requiredCount = phase2Questions.length;
    const allAnswered = Object.keys(currentSession.phase2_answers).length >= requiredCount;
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
            image_type: currentSession.image_type || '',
            options_dict: currentSession.options_dict,
            target_letter: currentSession.target_letter,
            phase1_choice: currentSession.phase1_choice,
            phase1_answers: currentSession.phase1_answers || {},
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
                image_type: data.image_type || null,
                options_dict: data.options_dict,
                options_data: data.options_data,
                target_letter: data.target_letter,
                phase1_choice: null,
                phase1_answers: {},
                phase1_start_ms: data.phase1_start_ms,
                phase2_start_ms: data.phase2_start_ms,
                phase2_answers: {},
                answer_revealed: false,
                questions: data.questions || currentSession.questions || {},
            };
            updateUIForPhase1(data);
            showStatus(data.message, 'success');
            updateRemaining(data.remaining, data.user_limit || 10);
            updateCoverage();  // Update coverage metrics after submission
        } else if (data.status === 'limit_reached') {
            // User has reached limit - show modal asking if they want to continue
            const preservedUserInfo = {
                userId: currentSession.user_id,
                userAge: currentSession.user_age,
                userGender: currentSession.user_gender,
                userEducation: currentSession.user_education,
            };
            
            showLimitExtensionModal(
                data.message + '\n\n点击"是"将增加您的限制 5 次。',
                () => {
                    // User clicked Yes - increase limit and get next evaluation
                    if (!preservedUserInfo.userId) {
                        showStatus('错误：无法获取用户信息。', 'error');
                        return;
                    }
                    
                    fetch(`${API_BASE}/increase-limit`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ 
                            user_id: preservedUserInfo.userId
                        }),
                    })
                    .then(response => response.json())
                    .then(limitData => {
                        if (limitData.status === 'success') {
                            showStatus(limitData.message, 'success');
                            // Get next evaluation by calling start with preserved user info
                            handleStart(preservedUserInfo);
                        } else {
                            showStatus('增加限制时发生错误，请重试。', 'error');
                        }
                    })
                    .catch(error => {
                        console.error('Error increasing limit:', error);
                        showStatus('发生错误，请重试。', 'error');
                    });
                },
                () => {
                    // User clicked No - show thank you message
                    showStatus('感谢您的参与！', 'success');
                    // Hide evaluation box
                    const evalBox = document.getElementById('evaluation-box');
                    if (evalBox) {
                        evalBox.classList.add('hidden');
                    }
                    if (data.remaining !== undefined) {
                        updateRemaining(data.remaining, data.user_limit || 10);
                    }
                }
            );
        } else {
            showStatus(data.message, 'error');
            if (data.remaining !== undefined) {
                updateRemaining(data.remaining, data.user_limit || 10);
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
    
    // Store questions in session if provided
    if (data.questions) {
        currentSession.questions = data.questions;
    } else {
        // Fallback: construct questions object from individual question fields
        currentSession.questions = currentSession.questions || {};
        if (data['q1-1']) {
            currentSession.questions['q1-1'] = data['q1-1'];
        }
        if (data['q1-2']) {
            currentSession.questions['q1-2'] = data['q1-2'];
        }
        if (data['q1-3']) {
            currentSession.questions['q1-3'] = data['q1-3'];
        }
    }
    
    // Update Phase 1 question text from questions.json (q1-1)
    const phase1Question = document.getElementById('phase1-question');
    if (phase1Question && currentSession.questions['q1-1'] && currentSession.questions['q1-1'].question) {
        const questionId = currentSession.questions['q1-1'].id ? currentSession.questions['q1-1'].id.toUpperCase() : 'Q1-1';
        const newText = `<strong>${questionId}. ${escapeHtml(currentSession.questions['q1-1'].question)}</strong>`;
        phase1Question.innerHTML = newText;
    }
    
    // Show all Phase 1 questions (q1-1, q1-2, q1-3) immediately
    showPhase1Questions();
    
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
    
    // Phase 1 questions (q1-2, q1-3) will be shown by showPhase1Questions() called in updateUIForPhase1
    // Don't hide them here - they should be visible from the start
    
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
    
    // Reset phase 1 choice and re-enable radio buttons for new evaluation
    document.querySelectorAll('input[name="phase1_choice"]').forEach(radio => {
        radio.checked = false;
        radio.disabled = false;
        radio.style.pointerEvents = 'auto';
    });
    // Re-enable labels
    document.querySelectorAll('label[for^="radio_"]').forEach(label => {
        label.style.pointerEvents = 'auto';
        label.style.cursor = 'pointer';
    });
    currentSession.phase1_choice = null;
    currentSession.answer_revealed = false;  // Reset reveal flag for new evaluation
}

function updateUIForPhase2(data) {
    // Hide Phase 1 questions container - MUST be hidden before Phase 2
    const phase1QuestionsContainer = document.getElementById('phase1-questions');
    if (phase1QuestionsContainer) {
        phase1QuestionsContainer.classList.add('hidden');
        phase1QuestionsContainer.style.display = 'none'; // Force hide
    }
    
    // Also hide the Phase 1 question container content
    const phase1QuestionsContent = document.getElementById('phase1-questions-container');
    if (phase1QuestionsContent) {
        phase1QuestionsContent.innerHTML = ''; // Clear content
    }
    
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
        // Don't set max-width in inline style - let CSS handle responsive sizing
        phase2ImageContainer.innerHTML = `
            <img class="eval-image" src="${currentSession.image_url}" 
                 style="width: 100%; height: auto; display: block; cursor: zoom-in;"
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
    document.querySelectorAll('input[name^="q2-"]').forEach(radio => {
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
    
    // Re-attach event listeners and ensure radio buttons are enabled
    document.querySelectorAll('input[name="phase1_choice"]').forEach(radio => {
        radio.disabled = false;
        radio.style.pointerEvents = 'auto';
        radio.addEventListener('change', handlePhase1Choice);
        // Prevent clicks if answer has been revealed
        radio.addEventListener('click', function(event) {
            if (currentSession.answer_revealed) {
                event.preventDefault();
                event.stopPropagation();
                return false;
            }
        });
    });
    // Re-enable labels
    document.querySelectorAll('label[for^="radio_"]').forEach(label => {
        label.style.pointerEvents = 'auto';
        label.style.cursor = 'pointer';
    });
}

function renderQuestions(questions) {
    const questionsContainer = document.getElementById('phase2-questions');
    if (!questionsContainer) {
        return;
    }
    
    if (!questions) {
        return;
    }
    
    // Always clear and re-render to ensure we show all current questions
    questionsContainer.innerHTML = '';
    
    let html = '';
    
    // Get all Phase 2 question IDs (q2-*), sorted numerically
    const questionIds = Object.keys(questions)
        .filter(qId => qId.startsWith('q2-'))
        .sort((a, b) => {
            // Extract number from q2-X format
            const numA = parseInt(a.split('-')[1]) || 999;
            const numB = parseInt(b.split('-')[1]) || 999;
            return numA - numB;
        });
    
    // Render all Phase 2 questions dynamically
    for (const qId of questionIds) {
        if (questions[qId]) {
            html += renderQuestion(qId, questions[qId]);
        }
    }
    questionsContainer.innerHTML = html;
    
    // Attach event listeners only to Phase 2 questions (q2-*)
    document.querySelectorAll('input[name^="q2-"]').forEach(radio => {
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

function updateRemaining(count, userLimit = 10) {
    const remainingDiv = document.getElementById('remaining-count');
    if (remainingDiv) {
        remainingDiv.textContent = `剩余: ${count} / ${userLimit}`;
    }
}

function updateCoverage() {
    fetch(`${API_BASE}/coverage`)
        .then(response => response.json())
        .then(data => {
            const coverageDiv = document.getElementById('coverage-metrics');
            if (coverageDiv) {
                // Display primary queue information
                const primaryQueue = data.primary_queue || 1;
                const remainingPercentage = data.primary_queue_remaining_percentage || 0.0;
                
                const queueText = `Q${primaryQueue}: ${remainingPercentage.toFixed(1)}%`;
                
                coverageDiv.innerHTML = `
                    <div class="coverage-item">
                        <strong>当前队列:</strong> ${queueText}
                    </div>
                `;
            }
        })
        .catch(error => {
            // Silently handle error
        });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showLimitExtensionModal(message, onYes, onNo) {
    const modal = document.getElementById('limit-extension-modal');
    const messageEl = document.getElementById('limit-extension-message');
    const yesBtn = document.getElementById('limit-extension-yes-btn');
    const noBtn = document.getElementById('limit-extension-no-btn');
    
    if (!modal || !messageEl || !yesBtn || !noBtn) {
        // Fallback to native confirm if modal elements don't exist
        const confirmed = confirm(message);
        if (confirmed) {
            onYes();
        } else {
            onNo();
        }
        return;
    }
    
    // Set message (preserve line breaks)
    messageEl.innerHTML = message.replace(/\n/g, '<br>');
    
    // Show modal
    modal.style.display = 'block';
    
    // Remove existing event listeners by cloning and replacing buttons
    const newYesBtn = yesBtn.cloneNode(true);
    const newNoBtn = noBtn.cloneNode(true);
    yesBtn.parentNode.replaceChild(newYesBtn, yesBtn);
    noBtn.parentNode.replaceChild(newNoBtn, noBtn);
    
    // Add event listeners
    newYesBtn.addEventListener('click', function() {
        modal.style.display = 'none';
        onYes();
    });
    
    newNoBtn.addEventListener('click', function() {
        modal.style.display = 'none';
        onNo();
    });
    
    // Close modal when clicking outside of it
    modal.addEventListener('click', function(event) {
        if (event.target === modal) {
            modal.style.display = 'none';
            onNo();
        }
    });
}

