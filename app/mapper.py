"""Word + Excel COM 連線與標籤映射邏輯。"""

import win32com.client

from app.config import HEADER_ROW


class OfficeMapper:
    """連動執行中的 Word 與 Excel 應用程式。"""

    @staticmethod
    def insert_tag_at_cursor():
        """讀取 Excel 當前選取欄的標題，插入到 Word 游標位置。

        回傳 (success: bool, message: str)。message 在成功時是標籤名，
        失敗時是錯誤訊息，方便上層 UI 直接顯示。
        """
        try:
            word = win32com.client.GetActiveObject("Word.Application")
            excel = win32com.client.GetActiveObject("Excel.Application")
        except Exception:
            return False, "連線失敗: 確保 Word 與 Excel 已開啟。"

        try:
            col_index = excel.Selection.Column
            tag_name = excel.ActiveSheet.Cells(HEADER_ROW, col_index).Value

            if not tag_name:
                return False, "找不到欄位標題（標題列為空）。"

            word.Selection.TypeText(f"{{{{ {tag_name} }}}}")
            return True, str(tag_name)
        except Exception as e:
            return False, f"映射失敗: {e}"
