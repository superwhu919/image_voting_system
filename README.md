# Tangshi Image-Poem Evaluation System

## User Information & Data Saving Logic

### When User Information is Saved

**When user clicks "开始" (Start) button:**
- User nickname, age, gender, and education level are saved to `users` table
- Used for identity verification and duplicate name checking on subsequent logins

### Duplicate Name Checking Logic

**If the entered nickname already exists:**
1. System retrieves saved user information (age, gender, education)
2. **All match** → Allow continuation, treat as same user
3. **Any mismatch** → Reject, prompt to use different nickname

### When Evaluation Records are Saved

**Evaluation data is only saved when user clicks "提交评估" (Submit):**
- If user exits before submitting, evaluation data **will not be saved**
- Incomplete evaluations do not count toward user's completed evaluation count
- User's remaining evaluation count remains unchanged after re-login

### Data Saved on Submit

**When user completes Phase 2 and clicks "提交评估", the following data is saved to `evaluations` table:**

- **User Info**: Nickname, age, gender, education level
- **Evaluation Content**: Poem title, image path, Phase 1 choice (A/B/C/D)
- **Phase 2 Answers**: All answers from q0 to q12
- **Timing Data**:
  - Phase 1 response time (from start to choice)
  - Phase 2 response time (from Phase 2 start to submit)
  - Total response time (from start to final submit)

### Database Structure

- **`users` table**: Stores basic user information (created when user clicks "开始")
- **`evaluations` table**: Stores complete evaluation records (only created when user submits)

---

# 唐诗配图评测系统

## 用户信息与数据保存逻辑

### 用户信息保存时机

**当用户点击"开始"按钮时：**
- 用户昵称、年龄、性别、教育程度保存到 `users` 表
- 用于后续登录时的身份验证和重名检查

### 重名检查逻辑

**如果用户输入的昵称已存在：**
1. 系统检索已保存的用户信息（年龄、性别、教育程度）
2. **全部匹配** → 允许继续，视为同一用户
3. **任一不匹配** → 拒绝，提示使用不同昵称

### 评估记录保存时机

**评估数据仅在用户点击"提交评估"时保存：**
- 如果用户在提交前退出页面，评估数据**不会保存**
- 未完成的评估不计入用户已完成的评估数量
- 用户重新登录后，剩余评估次数保持不变

### 提交时保存的数据

**当用户完成 Phase 2 并点击"提交评估"时，以下数据保存到 `evaluations` 表：**

- **用户信息**：昵称、年龄、性别、教育程度
- **评估内容**：诗歌标题、图像路径、Phase 1 选择（A/B/C/D）
- **Phase 2 答案**：q0 到 q12 的所有问题答案
- **时间数据**：
  - Phase 1 响应时间（从开始到选择）
  - Phase 2 响应时间（从 Phase 2 开始到提交）
  - 总响应时间（从开始到最终提交）

### 数据库结构

- **`users` 表**：存储用户基本信息（在用户点击"开始"时创建）
- **`evaluations` 表**：存储完整的评估记录（仅在用户提交时创建）

