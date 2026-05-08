"""3 個 read-only 工具與預設 registry 工廠。

Tool 為純函式 + JSON schema，不直接依賴任何 LLM provider；
由 LLMClient.chat 將 schema 轉為各 provider 的原生格式，
由 AgentOrchestrator 在 LLM 要求呼叫時執行。
"""

import os

import pandas as pd
from docxtpl import DocxTemplate

from app.agent.registry import Tool, ToolRegistry


def _list_excel_sheets(path: str) -> dict:
    if not path:
        return {"error": "未提供檔案路徑。"}
    if not os.path.isfile(path):
        return {"error": f"檔案不存在: {path}"}
    try:
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
        doc = DocxTemplate(word_path)
        variables = doc.get_undeclared_template_variables()
    except Exception as e:
        return {"error": str(e)}
    return {"variables": sorted(str(v) for v in variables)}


def build_default_registry() -> ToolRegistry:
    reg = ToolRegistry()

    reg.register(
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
        )
    )

    reg.register(
        Tool(
            name="read_excel_columns",
            description="讀取 Excel 指定工作表的欄位名稱（標題列）。若未提供 sheet 則使用第一個。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Excel 檔案完整路徑",
                    },
                    "sheet": {
                        "type": "string",
                        "description": "工作表名稱；不指定則讀第一個",
                    },
                    "header_row": {
                        "type": "integer",
                        "description": "標題列編號（1-based，預設 1）",
                    },
                },
                "required": ["path"],
            },
            func=_read_excel_columns,
        )
    )

    reg.register(
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
        )
    )

    return reg
