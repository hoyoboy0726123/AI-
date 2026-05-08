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
