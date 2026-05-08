"""依使用者自訂模板渲染輸出檔名（支援以欄位值命名）。"""

import re

UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\n\r\t]')


def render_filename(template, row_data, index):
    """將 template 中的 {欄位名} 以 row_data 替換；{index} 為列序號。

    模板格式錯誤或欄位缺漏時，回退為 report_{index}.docx，
    並過濾檔名不允許的字元，避免儲存失敗。
    """
    safe_data = {str(k): "" if v is None else str(v) for k, v in row_data.items()}
    safe_data["index"] = index

    try:
        name = template.format(**safe_data)
    except (KeyError, IndexError, ValueError):
        name = f"report_{index}.docx"

    name = UNSAFE_CHARS.sub("_", name).strip()
    if not name:
        name = f"report_{index}.docx"
    if not name.lower().endswith(".docx"):
        name += ".docx"
    return name
