"""3 個 read-only 工具與預設 registry 工廠。

Tool 為純函式 + JSON schema，不直接依賴任何 LLM provider；
由 LLMClient.chat 將 schema 轉為各 provider 的原生格式，
由 AgentOrchestrator 在 LLM 要求呼叫時執行。
"""

import os

from app.agent.registry import Tool, ToolRegistry


def _list_excel_sheets(path: str) -> dict:
    if not path:
        return {"error": "未提供檔案路徑。"}
    if not os.path.isfile(path):
        return {"error": f"檔案不存在: {path}"}
    try:
        import pandas as pd
        sheets = pd.ExcelFile(path).sheet_names
    except Exception as e:
        return {"error": str(e)}
    return {"sheets": list(sheets)}


def _read_excel_columns(path: str, sheet: str = "", header_row: int = 1) -> dict:
    if not path:
        return {"error": "未提供檔案路徑。"}
    if not os.path.isfile(path):
        return {"error": f"檔案不存在: {path}"}
    try:
        header_idx = max(0, int(header_row) - 1)
    except (TypeError, ValueError):
        header_idx = 0
    try:
        import pandas as pd
        df = pd.read_excel(
            path,
            sheet_name=sheet if sheet else 0,
            header=header_idx,
            nrows=0,
        )
    except Exception as e:
        return {"error": str(e)}
    return {
        "sheet": sheet or "(first)",
        "columns": [str(c) for c in df.columns],
    }


def _read_template_variables(word_path: str) -> dict:
    if not word_path:
        return {"error": "未提供 Word 檔案路徑。"}
    if not os.path.isfile(word_path):
        return {"error": f"檔案不存在: {word_path}"}
    try:
        from docxtpl import DocxTemplate
        doc = DocxTemplate(word_path)
        variables = doc.get_undeclared_template_variables()
    except Exception as e:
        return {"error": str(e)}
    return {"variables": sorted(str(v) for v in variables)}


def _read_only_tools() -> list:
    return [
        Tool(
            name="list_excel_sheets",
            description="列出 Excel 檔案中的所有工作表名稱。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Excel 檔案的完整路徑（.xlsx / .xls）",
                    },
                },
                "required": ["path"],
            },
            func=_list_excel_sheets,
        ),
        Tool(
            name="read_excel_columns",
            description="讀取 Excel 指定工作表的欄位名稱（標題列）。若未提供 sheet 則使用第一個。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Excel 檔案完整路徑"},
                    "sheet": {"type": "string", "description": "工作表名稱；不指定則讀第一個"},
                    "header_row": {"type": "integer", "description": "標題列編號（1-based，預設 1）"},
                },
                "required": ["path"],
            },
            func=_read_excel_columns,
        ),
        Tool(
            name="read_template_variables",
            description="讀取 Word 範本中所有未替換的 Jinja 範本變數（{{ ... }}）。",
            parameters={
                "type": "object",
                "properties": {
                    "word_path": {
                        "type": "string",
                        "description": "Word 範本檔（.docx）的完整路徑",
                    },
                },
                "required": ["word_path"],
            },
            func=_read_template_variables,
        ),
    ]


def make_writable_tools(ctx) -> list:
    """以 AppContext 包裝的「狀態變更」與「執行」類工具。"""
    return [
        Tool(
            name="get_current_settings",
            description="查看 UI 當前所有設定值（路徑 / 工作表 / 標題列 / 輸出 / 檔名規則 / 圖片寬度等）。",
            parameters={"type": "object", "properties": {}},
            func=ctx.get_settings,
        ),
        Tool(
            name="set_word_path",
            description="設定 Word 範本檔案路徑（絕對路徑、.docx）。",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Word 範本路徑"}},
                "required": ["path"],
            },
            func=ctx.set_word_path,
        ),
        Tool(
            name="set_excel_path",
            description="設定 Excel 數據檔案路徑；自動刷新工作表清單。",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Excel 路徑（.xlsx / .xls）"}},
                "required": ["path"],
            },
            func=ctx.set_excel_path,
        ),
        Tool(
            name="set_sheet_name",
            description="設定要使用的 Excel 工作表名稱（空字串代表使用第一個）。",
            parameters={
                "type": "object",
                "properties": {"name": {"type": "string", "description": "工作表名稱"}},
                "required": ["name"],
            },
            func=ctx.set_sheet_name,
        ),
        Tool(
            name="set_header_row",
            description="設定 Excel 標題列編號（1-based）。",
            parameters={
                "type": "object",
                "properties": {"row": {"type": "integer", "description": "標題列編號，預設 1"}},
                "required": ["row"],
            },
            func=ctx.set_header_row,
        ),
        Tool(
            name="set_output_dir",
            description="設定報告輸出資料夾。",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string", "description": "輸出資料夾路徑"}},
                "required": ["path"],
            },
            func=ctx.set_output_dir,
        ),
        Tool(
            name="set_filename_template",
            description="設定輸出檔名規則。可用 {欄位名} 與 {index} 佔位符（如 {客戶}_{日期}.docx）。",
            parameters={
                "type": "object",
                "properties": {"template": {"type": "string", "description": "檔名模板"}},
                "required": ["template"],
            },
            func=ctx.set_filename_template,
        ),
        Tool(
            name="set_image_width_mm",
            description="設定圖片插入時的預設寬度（毫米）。",
            parameters={
                "type": "object",
                "properties": {"value": {"type": "integer", "description": "寬度，單位 mm"}},
                "required": ["value"],
            },
            func=ctx.set_image_width_mm,
        ),
        Tool(
            name="validate_template",
            description="檢查 Word 範本變數與 Excel 欄位是否一致。回傳 missing_in_excel / extra_in_excel / passed。",
            parameters={"type": "object", "properties": {}},
            func=ctx.validate_template,
        ),
        Tool(
            name="generate_reports",
            description=(
                "依當前設定批次產出所有報告。建議先執行 validate_template；missing 欄位非空時應先告知使用者。"
                "若 AI 引擎頁籤的「啟用審查」開啟，會在每份產出後自動由 reviewer 模型審查；"
                "失敗者複製到 Failed_Reports/ 等下一批處理。"
                "回傳 produced / total / output_dir；啟用審查時另含 reviewed / failed_count / failed[] / failed_dir。"
            ),
            parameters={"type": "object", "properties": {}},
            func=ctx.generate_reports,
        ),
        Tool(
            name="open_output_folder",
            description="於檔案總管開啟當前輸出資料夾。",
            parameters={"type": "object", "properties": {}},
            func=ctx.open_output_folder,
        ),
        Tool(
            name="review_single_docx",
            description=(
                "用 VLM reviewer 審查單一 docx 檔，依 rubric 回傳 passed / score / issues / suggestions。"
                "需先在「AI 引擎」頁籤選好 reviewer 模型；呼叫後會自動把該 docx 渲染成 PNG 送 VLM。"
                "可選提供 row_context_json（產生這份報告所用的數據 JSON 字串）讓 reviewer 有上下文比對。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "docx_path": {
                        "type": "string",
                        "description": "Word 檔（.docx）的完整路徑",
                    },
                    "row_context_json": {
                        "type": "string",
                        "description": "可選：產生此份報告所用的資料（JSON 字串）",
                    },
                },
                "required": ["docx_path"],
            },
            func=ctx.review_single_docx,
        ),
        Tool(
            name="read_docx_text",
            description=(
                "讀取 Word 範本的所有段落文字（用於對應前先看內容）。"
                "max_paragraphs > 0 時截斷至前 N 段。"
                "未指定 word_path 則用當前設定。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "word_path": {
                        "type": "string",
                        "description": "Word 路徑；空則用當前設定",
                    },
                    "max_paragraphs": {
                        "type": "integer",
                        "description": "段落數上限；0 = 全部",
                    },
                },
                "required": [],
            },
            func=ctx.read_docx_text,
        ),
        Tool(
            name="rename_template_variable",
            description=(
                "把 Word 範本中的 {{ old }} 全部改成 {{ new }}（容忍空白變化），存檔。"
                "用於把既有變數名對齊 Excel 欄位。回傳 {changed: N}；找不到時 changed=0。"
                "未指定 word_path 則用當前設定。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "old": {"type": "string", "description": "舊變數名（不含 {{ }}）"},
                    "new": {"type": "string", "description": "新變數名（不含 {{ }}）"},
                    "word_path": {"type": "string"},
                },
                "required": ["old", "new"],
            },
            func=ctx.rename_template_variable,
        ),
        Tool(
            name="insert_template_variable",
            description=(
                "在範本中找到 anchor 文字並插入 {{ variable }}（用於從零標註空白範本）。"
                "範例：anchor=「客戶姓名：」、variable=「客戶名稱」、position=after → "
                "「客戶姓名：{{ 客戶名稱 }}」。只插入第一個出現的 anchor。"
                "未指定 word_path 則用當前設定。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "anchor": {
                        "type": "string",
                        "description": "範本中要對齊的文字（例：「客戶姓名：」）",
                    },
                    "variable": {
                        "type": "string",
                        "description": "要插入的變數名（不含 {{ }}）",
                    },
                    "position": {
                        "type": "string",
                        "enum": ["after", "before", "replace"],
                        "description": "插入位置；預設 after",
                    },
                    "word_path": {"type": "string"},
                },
                "required": ["anchor", "variable"],
            },
            func=ctx.insert_template_variable,
        ),
        Tool(
            name="suggest_mappings",
            description=(
                "讓 planner LLM 一次性比對 Word 範本內容與 Excel 欄位，回傳建議的 "
                "renames（變數改名）與 inserts（在某段文字附近插入變數）清單；不會自動套用。"
                "得到建議後請用 ask_user 確認，再呼叫 rename_template_variable / "
                "insert_template_variable 套用。消耗 1 次 planner 預算。"
                "word_path / excel_path 留空時使用當前設定。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "word_path": {"type": "string"},
                    "excel_path": {"type": "string"},
                },
                "required": [],
            },
            func=ctx.suggest_mappings,
        ),
        Tool(
            name="list_folder_files",
            description=(
                "列出任意資料夾中的檔案（用於圖片 / Word / Excel 等批次素材）。"
                "kind 可為 image / word / excel / pdf / any。"
                "回傳 {folder, files: [{name, path, size}], count}。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "folder_path": {"type": "string", "description": "資料夾完整路徑"},
                    "kind": {
                        "type": "string",
                        "enum": ["image", "word", "excel", "pdf", "any"],
                        "description": "檔案類型篩選；預設 image",
                    },
                    "max_files": {
                        "type": "integer",
                        "description": "回傳上限（0 = 全部）",
                    },
                },
                "required": ["folder_path"],
            },
            func=ctx.list_folder_files,
        ),
        Tool(
            name="insert_image_at_anchor",
            description=(
                "在 Word 範本中找到 anchor 文字（出現在哪一段），於該段下面新增一行並插入圖片。"
                "用途：把圖片資料夾的圖貼到 Word 對應位置（如「圖 1：流程圖」下面）。"
                "width_mm 留 0 時用 UI 的圖片寬度設定。未指定 word_path 用當前設定。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "anchor": {
                        "type": "string",
                        "description": "範本中要對齊的文字（圖片插在該段落下方）",
                    },
                    "image_path": {
                        "type": "string",
                        "description": "圖片完整路徑",
                    },
                    "width_mm": {
                        "type": "integer",
                        "description": "圖片寬度（mm）；0 = 用 UI 設定",
                    },
                    "word_path": {"type": "string"},
                },
                "required": ["anchor", "image_path"],
            },
            func=ctx.insert_image_at_anchor,
        ),
        Tool(
            name="suggest_image_placements",
            description=(
                "讓 planner LLM 看 Word 段落 + 圖片檔名，給出建議的「哪張圖放哪段下面」配對；"
                "不會自動套用。回傳 {placements:[{image, image_path, anchor, reason}]}。"
                "得到建議後請用 ask_user 確認，再呼叫 insert_image_at_anchor 套用。"
                "消耗 1 次 planner 預算。word_path 留空用當前設定。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "image_folder": {
                        "type": "string",
                        "description": "存放圖片的資料夾路徑",
                    },
                    "word_path": {"type": "string"},
                },
                "required": ["image_folder"],
            },
            func=ctx.suggest_image_placements,
        ),
        Tool(
            name="render_docx_pages",
            description=(
                "將 docx 檔渲染成每頁一張 PNG，供視覺檢查（reviewer 用）。"
                "需 Windows + Word + pymupdf。回傳 pages: [{page, path}]、output_dir、page_count。"
                "max_pages > 0 時只渲染前 N 頁。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "docx_path": {
                        "type": "string",
                        "description": "Word 檔（.docx）的完整路徑",
                    },
                    "dpi": {
                        "type": "integer",
                        "description": "渲染解析度 DPI；預設 150，不可低於 72",
                    },
                    "max_pages": {
                        "type": "integer",
                        "description": "只渲染前 N 頁；0 = 全部",
                    },
                },
                "required": ["docx_path"],
            },
            func=ctx.render_docx_pages,
        ),
        Tool(
            name="ask_user",
            description=(
                "向使用者顯示對話框詢問補充資訊（短問句）。"
                "缺少必要資料、需要使用者決定 yes/no 或從幾個選項挑一個時呼叫。"
                "使用者回覆字串放在 answer 欄位；按取消或關閉視窗回 cancelled=true。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "要問使用者的問題（簡短一句）",
                    },
                    "choices": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "可選：候選答案清單。提供時介面顯示為單選 radio；不提供則為自由輸入。",
                    },
                },
                "required": ["question"],
            },
            func=ctx.ask_user,
        ),
        Tool(
            name="request_file",
            description=(
                "開啟檔案 / 資料夾選取對話框讓使用者選一個路徑。"
                "缺少 word_path / excel_path / output_dir 這類路徑型資料時優先用此工具。"
                "回傳 path；使用者取消回 cancelled=true。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "對話框標題或說明（簡短）",
                    },
                    "kind": {
                        "type": "string",
                        "enum": ["word", "excel", "image", "directory", "any"],
                        "description": "要選的類型；word=*.docx, excel=*.xlsx/*.xls, image=圖片, directory=資料夾, any=任意檔",
                    },
                },
                "required": ["prompt"],
            },
            func=ctx.request_file,
        ),
    ]


def build_default_registry(context=None) -> ToolRegistry:
    """建立預設工具集。

    無 context（無法操作 UI 狀態）時，僅註冊 read-only 工具；
    傳入 AppContext 時，加入設定 / 驗證 / 執行類工具。
    """
    reg = ToolRegistry()
    for tool in _read_only_tools():
        reg.register(tool)
    if context is not None:
        for tool in make_writable_tools(context):
            reg.register(tool)
    return reg
