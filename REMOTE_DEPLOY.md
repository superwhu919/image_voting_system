# Remote Instance Deployment Guide

## What Changed

The code now supports remote deployment via environment variables:
- `DATA_ROOT`: Path to your data folder on the remote instance
- `XLSX_PATH`: (Optional) Path to Excel file, if different from default

## Setup on Remote Instance

### 1. Clone/Pull the Repository

```bash
cd /path/to/your/workspace
git clone git@github.com:superwhu919/image_voting_system.git
# OR if already cloned:
cd voting_system
git pull origin two-folder-version
```

### 2. Set Up Conda Environment

```bash
# Activate the tangshi conda environment
conda activate tangshi

# If the environment doesn't exist, create it:
# conda create -n tangshi python=3.x
# conda activate tangshi
```

### 3. Install Dependencies

```bash
cd voting_system
pip install -r requirements.txt
pip install gradio huggingface-hub  # If not in requirements.txt
```

### 4. Set Up Your Data Folder

Your data folder should have this structure:
```
/path/to/your/data/
├── gpt/                          # GPT-generated images (*.png)
├── Nano/                         # Nano-generated images (*_nano3_1.png)
└── tangshi_300_unique_name.xlsx  # Excel file (optional, can be in voting_system folder)
```

### 5. Run with Environment Variables

**Option A: Direct run (no Docker)**
```bash
conda activate tangshi
export DATA_ROOT="/path/to/your/data"
export CSV_PATH="/path/to/your/data/method3_similar.csv"  # Optional

cd voting_system
python app.py
```

**Option B: One-liner**
```bash
conda activate tangshi && DATA_ROOT="/path/to/your/data" python app.py
```

### 6. Access the Application

- The app will bind to `0.0.0.0:7860`
- Access via: `http://YOUR_INSTANCE_IP:7860`
- **Important**: Make sure port 7860 is open in your firewall:
  ```bash
  sudo ufw allow 7860  # Ubuntu/Debian
  ```

## Running in Background

Use `nohup` or `tmux`/`screen`:

```bash
# Using nohup
conda activate tangshi
nohup DATA_ROOT="/path/to/your/data" python app.py > app.log 2>&1 &

# Using tmux (recommended)
tmux new -s voting
conda activate tangshi
DATA_ROOT="/path/to/your/data" python app.py
# Press Ctrl+B then D to detach
# Reattach later with: tmux attach -t voting
```

## Environment Variables Summary

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATA_ROOT` | Yes (for remote) | Mac path | Path to data folder with gpt/ and Nano/ subdirs |
| `CSV_PATH` | No | Auto-detect | Path to CSV file (checks DATA_ROOT then BASE_DIR) |
| `SPACE_ID` | No | - | If set, enables HF Spaces mode |
| `SYSTEM` | No | - | If "spaces", enables HF Spaces mode |

## Notes

- **Conda Environment**: Always use `conda activate tangshi` before running the application
- **Local mode**: When `DATA_ROOT` is not set, uses Mac development path
- **Remote mode**: When `DATA_ROOT` is set, uses that path and binds to `0.0.0.0:7860`
- **HF Spaces mode**: When `SPACE_ID` or `SYSTEM=spaces` is set, downloads from HF Dataset

## Troubleshooting

1. **Can't access URL**: Check firewall, ensure port 7860 is open
2. **Data not found**: Verify `DATA_ROOT` path and folder structure
3. **CSV not found**: Set `CSV_PATH` explicitly or ensure file is in data folder or voting_system folder
4. **Conda environment not found**: Make sure `conda activate tangshi` works, or create the environment first



