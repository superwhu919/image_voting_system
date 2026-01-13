# Tangshi Image-Poem Evaluation System

A web-based evaluation system for assessing how well AI-generated images match classical Chinese Tang poems (唐诗). The system collects human evaluations through a two-phase process: blind selection and detailed assessment.

## What This Project Does

This system enables researchers to collect structured evaluations of image-poem alignments. Users are presented with AI-generated images (from GPT, Midjourney, or Nano models) and asked to:

1. **Phase 1 (Blind Selection)**: Select which poem best matches an image from 4 options (1 correct + 3 distractors)
2. **Phase 2 (Detailed Evaluation)**: After revealing the correct answer, answer 13 detailed questions about:
   - Content appropriateness and safety
   - Technical image quality
   - Cultural and historical accuracy
   - Artistic style alignment
   - Overall semantic alignment with the poem

The system uses a sophisticated 6-queue priority system to ensure fair distribution of image evaluations across all available images, preventing users from seeing duplicate poems while maximizing coverage.

## Code Structure

```
voting_system/
├── app.py                    # FastAPI application entry point
├── config.py                 # Configuration (paths, settings, environment detection)
├── requirements.txt          # Python dependencies
├── poem_pool.csv             # Poem metadata and similar poem mappings
├── questions.json            # Phase 2 evaluation questions
│
├── core/                     # Core business logic
│   ├── session.py           # Session management, user authentication, evaluation flow
│   ├── evaluation.py        # Poem selection, formatting, image selection system
│   └── image_selection.py   # 6-queue priority system for fair image distribution
│
├── data_logic/               # Data access layer
│   ├── catalog.py          # Builds image catalog from directory, loads poem info
│   └── storage.py           # Database operations (users, evaluations)
│
├── web/                      # Web interface
│   ├── routes.py            # API endpoints (start, reveal, submit, etc.)
│   ├── templates/           # HTML templates (Jinja2)
│   └── static/              # CSS and JavaScript
│
├── ui/                       # UI utilities
│   ├── helpers.py           # Helper functions
│   └── styles.py            # Style definitions
│
├── utils/                    # Utility scripts
│   ├── dump_db.py           # Database export utilities
│   └── flush.py             # Data flushing utilities
│
└── tests/                    # Test suites
    ├── test_user_login.py    # User login logic tests
    └── test_frontend_user_login.py  # Frontend integration tests
```

### Key Components

- **`app.py`**: FastAPI application that serves the web interface and API endpoints
- **`config.py`**: Centralized configuration that handles:
  - Environment detection (local, remote, HuggingFace Spaces)
  - Data path resolution (images, CSV, Excel files)
  - Database paths
- **`core/session.py`**: Manages user sessions, authentication, and the evaluation workflow
- **`core/evaluation.py`**: Handles poem selection, formatting, and coordinates with the image selection system
- **`core/image_selection.py`**: Implements a 6-queue priority system to ensure fair image distribution
- **`data_logic/catalog.py`**: Scans image directories and loads poem metadata
- **`data_logic/storage.py`**: SQLite database operations for users and evaluations
- **`web/routes.py`**: API endpoints for starting sessions, revealing answers, submitting evaluations

## How to Run the Application

### Prerequisites

1. **Python 3.7+** installed
2. **Dependencies** installed:
   ```bash
   pip install -r requirements.txt
   ```

### Running Locally (Development)

1. **Set up your data directory structure**:
   ```
   /path/to/your/images/
   └── Nano/                    # Image directory
       ├── {poem_title}_gpt.png
       ├── {poem_title}_mj.png
       └── {poem_title}_nano.png
   ```

2. **Configure paths** (see Configuration section below)

3. **Run the application**:
   ```bash
   python app.py
   ```

4. **Access the application**:
   - Open your browser to `http://127.0.0.1:7860`

### Running on Remote Instance

1. **Set environment variables**:
   ```bash
   export DATA_ROOT="/path/to/your/data"
   export CSV_PATH="/path/to/your/data/poem_pool.csv"  # Optional
   export XLSX_PATH="/path/to/your/data/tangshi_300_unique_name.xlsx"  # Optional
   ```

2. **Run the application**:
   ```bash
   python app.py
   ```

3. **Access the application**:
   - The app will bind to `0.0.0.0:7860`
   - Access via `http://YOUR_INSTANCE_IP:7860`
   - Make sure port 7860 is open in your firewall

### Running on HuggingFace Spaces

The system automatically detects HuggingFace Spaces environment when `SPACE_ID` or `SYSTEM=spaces` environment variables are set. It will download the dataset from the private HuggingFace repository.

## Configuration

### Data and Image Paths

The system supports three deployment modes, automatically detected:

#### 1. **Local Development Mode** (default when `DATA_ROOT` is not set)
- Uses hardcoded Mac paths in `config.py`
- Modify these paths in `config.py` for your local setup:
  ```python
  ROOT_ABS = Path("/Users/williamhu/Desktop/poem-work/Tangshi-Bench/imgs/ready")
  IMAGE_DIR = Path("/Users/williamhu/Desktop/poem-work/tangshi-data/all_images")
  ```

#### 2. **Remote Deployment Mode** (when `DATA_ROOT` is set)
- Set the `DATA_ROOT` environment variable to your data folder path
- The system will look for:
  - Images in: `{DATA_ROOT}/Nano/`
  - CSV file: `{DATA_ROOT}/poem_pool.csv` or `{BASE_DIR}/poem_pool.csv`
  - Excel file: `{DATA_ROOT}/tangshi_300_unique_name.xlsx` or `{BASE_DIR}/tangshi_300_unique_name.xlsx`

#### 3. **HuggingFace Spaces Mode** (when `SPACE_ID` or `SYSTEM=spaces` is set)
- Automatically downloads dataset from private HuggingFace repository
- Requires `Token` secret to be set in Space Settings

### Image Naming Convention

Images must follow this naming pattern:
```
{poem_title}_{type}.png
```

Where:
- `{poem_title}`: The exact poem title (must match titles in `poem_pool.csv`)
- `{type}`: One of `gpt`, `mj`, or `nano`

Example:
```
黄鹤楼送孟浩然之广陵_gpt.png
黄鹤楼送孟浩然之广陵_mj.png
黄鹤楼送孟浩然之广陵_nano.png
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATA_ROOT` | No | Mac path | Path to data folder with `Nano/` subdirectory |
| `CSV_PATH` | No | Auto-detect | Path to `poem_pool.csv` (checks `DATA_ROOT` then `BASE_DIR`) |
| `XLSX_PATH` | No | Auto-detect | Path to Excel file (checks `DATA_ROOT` then `BASE_DIR`) |
| `SPACE_ID` | No | - | If set, enables HuggingFace Spaces mode |
| `SYSTEM` | No | - | If `"spaces"`, enables HuggingFace Spaces mode |
| `Token` | Yes (HF Spaces) | - | HuggingFace token for private dataset access |

## Data Files

### `poem_pool.csv`

This CSV file contains the poem metadata and similar poem mappings used for generating distractors in Phase 1.

**Format:**
```csv
Poem_Index,Title,Author,URL,Content,A,B,C
1,黄鹤楼送孟浩然之广陵,李白 〔唐代〕,https://...,"故人西辞黄鹤楼...",酬张少府,黄鹤楼,赠孟浩然
```

**Columns:**
- `Poem_Index`: Unique identifier for the poem
- `Title`: Poem title (must match image filenames)
- `Author`: Author name
- `URL`: Source URL
- `Content`: Full poem text
- `A`, `B`, `C`: Three similar poems used as distractors in Phase 1

**Usage:**
- The system uses this file to:
  1. Load poem metadata (title, author, content)
  2. Generate distractors for Phase 1 (columns A, B, C)
  3. Display poem information during evaluation

**Location:**
- Default: `{BASE_DIR}/poem_pool.csv`
- Can be overridden with `CSV_PATH` environment variable

### `questions.json`

This JSON file defines all Phase 2 evaluation questions that users answer after the correct poem is revealed.

**Structure:**
```json
{
  "q0": {
    "id": "q0",
    "question": "仅根据这张图像判断，它最有可能对应右边的哪一首唐诗？"
  },
  "q1": {
    "id": "q1",
    "question": "请评估图片内容是否存在任何违规或可能引发不当联想的问题：",
    "options": [
      { "value": "A", "label": "存在轻微问题..." },
      { "value": "B", "label": "存在明显问题..." },
      { "value": "C", "label": "无任何问题" }
    ]
  },
  ...
}
```

**Question Categories:**
- **q0**: Phase 1 question (shown during blind selection)
- **q1**: Content safety and appropriateness
- **q2**: Technical image quality
- **q3**: Key imagery accuracy
- **q4**: Temporal/environmental consistency
- **q5**: Emotional tone alignment
- **q6**: Historical/cultural accuracy
- **q7**: Composition and perspective
- **q8**: Text accuracy (if text appears in image)
- **q9**: Evocative quality and imagination
- **q10**: Artistic style alignment
- **q11**: Metaphorical content handling
- **q12**: Overall detail and expressiveness
- **q13**: Overall semantic alignment (optional)

**Usage:**
- Loaded at application startup
- Questions are dynamically rendered in the Phase 2 interface
- Answers are saved to the `evaluations` database table

**Location:**
- Default: `{BASE_DIR}/questions.json`

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

Database files are created in the project root:
- `users.db`: User demographics and limits
- `evaluations.db`: Complete evaluation records

## Image Selection System

The system uses a sophisticated 6-queue priority system to ensure fair distribution:

1. **6 Independent Queues**: Each queue contains all images, independently shuffled
2. **Priority Selection**: Q1 → Q2 → ... → Q6 (always try Q1 first)
3. **Conflict Avoidance**:
   - **Scenario A**: New poem title → assign immediately
   - **Scenario B**: Same title, different image → recycle to queue bottom
   - **Scenario C**: Both title and path seen → skip to next queue
4. **Timeout Handling**: Images assigned but not rated within 10 minutes are returned to their queue

This ensures:
- Users don't see duplicate poems
- Fair coverage across all images
- Efficient use of evaluation capacity

## User Limits

- **Default limit**: 10 evaluations per user (configurable in `config.py` as `MAX_PER_USER`)
- **Limit extension**: Users can extend their limit by 5 when they reach the default limit
- **Custom limits**: Stored per-user in the database

## API Endpoints

- `GET /`: Main evaluation interface
- `POST /api/start`: Start new evaluation session
- `POST /api/reveal`: Reveal correct answer and show Phase 2
- `POST /api/update-answer`: Update a Phase 2 answer
- `POST /api/submit`: Submit complete evaluation
- `GET /api/remaining/{user_id}`: Get remaining evaluations count
- `POST /api/increase-limit`: Increase user's limit by 5
- `GET /api/coverage`: Get coverage metrics and queue statistics
- `GET /images/{image_path:path}`: Serve images with Unicode filename support

## Testing

Run the test suites:

```bash
# User login logic tests
python tests/test_user_login.py

# Frontend integration tests (requires Selenium)
python tests/test_frontend_user_login.py
```

## Troubleshooting

1. **Can't find images**: Check `IMAGE_DIR` path in `config.py` or set `DATA_ROOT` environment variable
2. **CSV not found**: Ensure `poem_pool.csv` is in the project root or set `CSV_PATH` environment variable
3. **Database errors**: Check file permissions in the project directory
4. **Port already in use**: Change the port in `app.py` or kill the process using port 7860

## License

[Add your license information here]
