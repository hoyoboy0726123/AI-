# AI 辦公自動化 - 視覺化映射工具

Office 視覺化對應與自動生成系統 (Windows 桌面應用)。

透過互動式快捷鍵在 Word 與 Excel 間建立標籤映射，並依 Excel 數據批次產出 Word 報告。

## 功能

- **視覺化標籤映射**：按下 `Ctrl+Shift+M`，自動讀取 Excel 當前選取欄的標題，並以 `{{ tag }}` 形式插入 Word 游標位置。
- **批次報告產出**：以 Word 範本搭配 Excel 表格，一鍵生成多份 docx 檔案，輸出至 `Generated_Reports/`。
- **現代化 UI**：使用 customtkinter，自動跟隨系統深色/淺色模式。

## 環境需求

- Windows 系統 (使用 `pywin32` 操作 Word / Excel)
- Python 3.9+
- 已安裝 Microsoft Word 與 Excel

## 安裝

```bash
pip install -r requirements.txt
```

## 使用方式

```bash
python main.py
```

1. 在 GUI 中選取 Word 範本 (`.docx`) 與 Excel 數據檔 (`.xlsx`)。
2. 開啟 Word 與 Excel 檔案。
3. 點擊「開啟標籤映射模式」，回到 Word，將游標放在欲填入的位置；於 Excel 點選對應欄的任一儲存格，按 `Ctrl+Shift+M`，即可在 Word 插入該欄標題的範本標籤。
4. 完成範本標註後，點擊「開始執行批次產出報告」，依 Excel 每一列產出一份 Word 報告。

## Excel 數據格式

第一列為欄位名稱 (即 Word 範本中的標籤名)，每一列代表一份報告的數據。
