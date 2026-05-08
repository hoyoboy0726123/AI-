"""使用者設定持久化（路徑、檔名規則、工作表、AI 引擎等）。

注意：API key 不寫進 settings.json，改由 .env 透過 python-dotenv 載入到環境變數。
"""

import json
from pathlib import Path

from app.config import DEFAULT_REVIEW_RUBRIC

SETTINGS_PATH = Path.home() / ".auto_report" / "settings.json"

DEFAULTS = {
    # 既有
    "word_path": "",
    "excel_path": "",
    "output_dir": "Generated_Reports",
    "filename_template": "報告_{index}.docx",
    "sheet_name": "",
    "header_row": 1,
    "image_width_mm": 80,
    "grid_columns": 2,
    # AI 引擎
    "llm_provider": "Gemini",
    "gemini_planner_model": "",
    "gemini_reviewer_model": "",
    "ollama_endpoint": "http://localhost:11434",
    "ollama_planner_model": "",
    "ollama_reviewer_model": "",
    "enable_review": True,
    "review_sampling_percent": 100,
    "max_review_retries": 3,
    "review_rubric": DEFAULT_REVIEW_RUBRIC,
    "max_planner_calls": 50,
    "max_reviewer_calls": 100,
}


def load_settings():
    if not SETTINGS_PATH.exists():
        return DEFAULTS.copy()
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return DEFAULTS.copy()
    merged = DEFAULTS.copy()
    merged.update(data)
    return merged


def save_settings(settings):
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
