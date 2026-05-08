"""使用者設定持久化（路徑、檔名規則、工作表等）。"""

import json
from pathlib import Path

SETTINGS_PATH = Path.home() / ".auto_report" / "settings.json"

DEFAULTS = {
    "word_path": "",
    "excel_path": "",
    "output_dir": "Generated_Reports",
    "filename_template": "報告_{index}.docx",
    "sheet_name": "",
    "header_row": 1,
    "image_width_mm": 80,
    "grid_columns": 2,
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
