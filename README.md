# AI 辦公自動化 - 視覺化映射工具

Office 視覺化對應與自動生成系統 (Windows 桌面應用)。

透過互動式快捷鍵在 Word 與 Excel 間建立標籤映射，並依 Excel 數據批次產出 Word 報告。

## 功能

- **視覺化標籤映射**：按下 `Ctrl+Shift+M`，自動讀取 Excel 當前選取欄的標題，並以 `{{ tag }}` 形式插入 Word 游標位置。
- **任意檔案插入圖片**：從檔案總管選取任一資料夾的圖片，直接插入到 Word 游標位置（支援 png / jpg / jpeg / gif / bmp，自動鎖定長寬比）。
- **映射歷史與復原**：所有映射 / 圖片插入會記錄於歷史清單，可一鍵還原最近一筆。
- **範本變數驗證**：產出前自動比對 Word 範本變數與 Excel 欄位，提早發現缺失。
- **檔名規則自訂**：以 `{欄位名}` 為佔位符客製檔名，例如 `{客戶名稱}_{日期}.docx`，`{index}` 為序號。
- **工作表 / 標題列可選**：支援多 Sheet 與非首列標題的 Excel 報表。
- **進度條與取消**：批次產出時顯示進度，可中途取消。
- **設定持久化**：路徑、輸出資料夾、檔名規則等自動存於 `~/.auto_report/settings.json`。
- **批次圖片欄位**：Excel 欄位填入圖片路徑，產出時自動以 `InlineImage` 嵌入 Word。
- **現代化 UI**：使用 customtkinter，自動跟隨系統深色 / 淺色模式。

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

1. 在「設定」頁籤指定 Word 範本、Excel 數據、工作表、標題列、輸出資料夾、檔名規則。
2. 開啟對應的 Word 與 Excel 檔。
3. 進入「對應」頁籤：
   - 點擊「開啟標籤映射模式」，回到 Word 將游標放定位置；於 Excel 點選欄位中的任一儲存格，按 `Ctrl+Shift+M`，即會在 Word 插入該欄標題標籤。
   - 點擊「從檔案總管選圖片並插入到 Word 游標位置」即可從任一資料夾選圖片插入。
   - 「復原最近一筆」可移除剛剛插入的標籤或圖片。
4. 進入「產出」頁籤：先按「檢查範本變數 vs Excel 欄位」確認對齊，再按「開始批次產出報告」。產出途中可按「取消產出」中斷。
5. 完成後可一鍵「開啟輸出資料夾」。

## 模板與資料格式

- **Excel**：標題列定義變數名稱，下方各列為一份報告的數據。
- **Word**：使用 docxtpl 的 Jinja 語法，例如 `{{ 客戶名稱 }}`、`{% for ... %}`。
- **圖片欄位**：在 Excel 中填入完整檔案路徑（含 `.png/.jpg` 等副檔名），檔案存在時會自動轉為內嵌圖片。

## AI Agent

新增「AI 引擎」與「Agent」兩個頁籤：

- **AI 引擎**：選 **Gemini** 或 **Ollama**，列出可用模型、測試連線、設定審查 rubric。
- **Agent**：自然語言對話，已支援 25 個工具（P2 → P9）：
  - 查詢：`list_excel_sheets` / `read_excel_columns` / `read_template_variables` / `get_current_settings` / `read_docx_text`
  - 設定：`set_word_path` / `set_excel_path` / `set_sheet_name` / `set_header_row` / `set_output_dir` / `set_filename_template` / `set_image_width_mm`
  - **範本對應 (P8)**：`suggest_mappings` / `rename_template_variable` / `insert_template_variable`
  - **圖片資料夾 (P9)**：`list_folder_files`（列任意資料夾檔案）/ `suggest_image_placements`（依檔名語意配對 Word 段落）/ `insert_image_at_anchor`（圖片貼到指定段落下面）
  - 驗證：`validate_template`
  - 執行：`generate_reports`（**啟用審查時** 每份產出後自動由 VLM 評分；失敗的搬到 `Failed_Reports/`）/ `open_output_folder`
  - 審查：`review_single_docx` / `render_docx_pages`（docx → 每頁 PNG）
  - 互動：`ask_user`（含 choices 單選）/ `request_file`（檔案 / 資料夾選取對話框）
  - Agent 缺資料時會主動跳檔案選取或單選對話框，不靠你貼路徑。
  - 範例：「**幫我把標籤對好**」「**把 ./photos 裡的圖貼到範本對應位置**」「全部產出」
  - Ctrl+Enter 送出。

### 圖片資料夾 → Word 位置（P9）

```
你: 把 D:\photos 裡的圖貼到範本對應位置

[助理 → list_folder_files] 列出 photos/ 下的所有圖片
[工具回傳] 12 張：圖1_流程圖.png, 圖2_組織架構.jpg, 客戶簽名範本.png, ...

[助理 → read_docx_text] 讀範本段落
[助理 → suggest_image_placements] LLM 配對檔名 → 段落
[工具回傳] {
  "placements": [
    {"image":"圖1_流程圖.png", "anchor":"圖 1：流程圖", "image_path":"D:\\photos\\圖1_流程圖.png", "reason":"檔名與段落直接對應"},
    {"image":"圖2_組織架構.jpg", "anchor":"圖 2：組織架構", ...},
    ...
  ]
}

[助理 → ask_user] 「要套用這 8 個配對嗎？」 [全部 / 逐一確認 / 都不要]
〔你選「全部」〕

[助理 → insert_image_at_anchor × 8]
[助理] 8 張圖片已貼到範本對應段落下面。DONE
```

### 自動範本對應（P8）

工作流：
```
你: 幫我把範本標籤對好

[助理 → suggest_mappings] LLM 看 Word 段落 + 既有變數 + Excel 欄位
[工具回傳] {
  "renames": [{"from":"客戶","to":"客戶名稱","reason":"Excel 用客戶名稱"}],
  "inserts": [{"anchor":"電話：","var":"電話","position":"after","reason":"範本有空白等待填入"}]
}
[助理 → ask_user] 「建議改 {{客戶}}→{{客戶名稱}}、在「電話：」後插入 {{電話}}。執行哪些？」
                  [全部執行 / 只 rename / 只 insert / 都不要]
〔你選「全部執行」〕
[助理 → rename_template_variable]
[助理 → insert_template_variable]
[助理 → validate_template] {"passed": true}
[助理] 範本對應完成，可開始批次產出。DONE
```

### 審查設定（AI 引擎頁籤）

- **啟用審查**：勾選後 `generate_reports` 改走「邊產邊審」流程；UI 的「開始批次產出報告」按鈕也會走相同路徑
- **抽樣比例**：1–100%；100 = 每份都審
- **評分標準（rubric）**：多行文字輸入；reviewer 依此 rubric 給 passed/score/issues
- 審查失敗的報告會 **複製** 到 `Failed_Reports/`（與 output_dir 同層），檔名重複自動加序號；不自動重產，等下批人工處理。

### 預算上限（AI 引擎頁籤）

- **Planner 上限**：每回合對話可呼叫 LLM 的次數上限（預設 50）；達上限會停止 agent 並提示去重置
- **Reviewer 上限**：每回合 VLM 審查呼叫上限（預設 100）；達上限後該回合剩餘的報告會跳過審查（仍會產出）
- 「**重置計數**」按鈕：歸零本回合已用次數
- 計數於「新對話」時自動重置；上限變動不會重置已用次數

### 對話日誌匯出（Agent 頁籤）

- **匯出對話** 按鈕：把整段對話（含工具呼叫 / 工具回傳 / 助理文字）以 Markdown 格式存檔，含時戳、provider、模型、預算用量。可作為審計或除錯紀錄。

Gemini 走最新版 [`google-genai`](https://pypi.org/project/google-genai/) 2.0+ 統一 SDK。
Ollama 走 stdlib urllib，無額外依賴。

API key 採 `.env` 管理：複製 `.env.example` 為 `.env` 並填入 `GEMINI_API_KEY`。

完整評估計劃見 [`docs/AGENT_PLAN.md`](docs/AGENT_PLAN.md)。

> 沒有 LLM 環境（沒裝 `google-genai`、沒設 API key、沒跑 Ollama）也完全
> 不影響「設定 / 對應 / 產出」三個手動頁籤的使用。

## 專案結構

```
.
├── main.py              # 進入點（會載入 .env）
├── requirements.txt
├── .env.example
├── docs/
│   └── AGENT_PLAN.md    # AI 代理階段化實作計劃
└── app/
    ├── config.py        # 常數
    ├── settings.py      # 使用者設定持久化
    ├── filename.py      # 檔名模板渲染
    ├── ui.py            # GUI 主視窗
    ├── mapper.py        # Word/Excel COM 操作
    ├── generator.py     # 批次報告產出
    ├── hotkey.py        # 全域快捷鍵
    └── agent/
        ├── registry.py            # Tool / ToolRegistry 框架
        ├── tools.py               # 工具實作（22 個工具）
        ├── context.py             # AppContext：UI 狀態橋接（執行緒安全）
        ├── budget.py              # BudgetTracker：planner / reviewer 呼叫次數上限
        ├── dialogs.py             # ChoiceDialog（agent 用單選對話框）
        ├── docx_render.py         # docx → PDF (Word COM) → PNG (PyMuPDF) 管線
        ├── reviewer.py            # VLM 審查（review_report + JSON 抽取 + 失敗檔搬移）
        ├── template_edit.py       # P8 / P9: read_docx_text + rename / insert template var + insert image
        ├── mapping_suggester.py   # P8 / P9: LLM 自動建議 renames / inserts / image placements
        ├── folder_scan.py         # P9: list_folder_files（任意資料夾掃描）
        ├── orchestrator.py        # planner loop（單回合 = 跑完所有 tool call；尊重預算）
        └── llm/             # LLM provider 抽象
            ├── base.py      # LLMClient + Message + ToolCall + vision_complete
            ├── gemini.py    # google-genai 2.0+ 實作（含 vision）
            └── ollama.py    # urllib REST 實作（含 vision）
```
