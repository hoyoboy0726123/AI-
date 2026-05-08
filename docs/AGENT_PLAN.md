# AI 自動化代理 — 評估計劃

> 本文件保留設計決策；實作以階段化方式推進，每階段可獨立 demo 與回滾。

## 1. 目標

把現有 mapper / generator 等模組包成 LLM 工具，使用者用自然語言下指令；
LLM 缺資訊時主動反問、執行中卡住會中斷詢問人類；每份產出由另一個 VLM
審查 agent 把關，全通過才結案。雙引擎：Gemini API + Ollama 本地，
settings 介面要列出可用模型。

**重要前提：** 既有手動工作流（設定 / 對應 / 產出 三個頁籤）必須維持完整
可用，AI 層為純加值，無 LLM 也能用。

## 2. 系統架構

```
┌───────────────────────────────────────────────────────┐
│                    Tk UI（既有）                        │
│  Tabs: 設定 / 對應 / 產出 / 【新】AI 引擎 / 【新】Agent  │
└──────────────┬───────────────────────────┬─────────────┘
               │                           │
        Agent Tab IO                  Settings: provider/model
               │                           │
┌──────────────▼───────────────────────────▼─────────────┐
│                   AgentOrchestrator                     │
│  - planner loop (tool calling)                          │
│  - human-in-the-loop queue (pause/resume)               │
│  - per-report reviewer dispatch                         │
└──┬─────────────────┬────────────────────┬──────────────┘
   │                 │                    │
   ▼                 ▼                    ▼
┌──────┐       ┌──────────┐         ┌────────────┐
│Tools │       │LLM Client│         │ Reviewer   │
│Reg.  │       │ (abstract│         │  (VLM)     │
│      │       │  -ion)   │         │            │
└──┬───┘       └────┬─────┘         └─────┬──────┘
   │                │                     │
   │       ┌────────┴────────┐            │
   │       ▼                 ▼            ▼
   │   Gemini Cli.      Ollama Cli.   Doc→Image
   │                                  (Word COM
   │                                  → PDF → PNG)
   ▼
mapper / generator / settings / filename / hotkey
```

### 2.1 LLM Provider 抽象

```python
class LLMClient:
    def is_available(self) -> bool
    def list_models(self) -> list[str]
    def list_vision_models(self) -> list[str]
    def chat(self, messages, tools=None) -> Message
    def chat_with_images(self, messages, images, ...) -> Message
```

實作：
- **GeminiClient**：用 `google-generativeai`；models 過濾 `generateContent`；
  Gemini 1.5+ 全部多模態。
- **OllamaClient**：HTTP `GET /api/tags` 列模型；vision 走 base64 image。

⚠ Ollama 工具呼叫穩定度依模型而定，需要白名單（llama3.1+ / qwen2.5+ / mistral-nemo 等）。

### 2.2 Tool Registry

| 類別 | Tool | 對應現有程式 |
|---|---|---|
| 探索 | `list_excel_sheets(path)` | `pd.ExcelFile` |
|  | `read_excel_columns(path, sheet, header_row)` | `pd.read_excel` |
|  | `read_template_variables(word_path)` | `DocxTemplate.get_undeclared_template_variables` |
| 配置 | `set_filename_template(template)` | settings |
|  | `set_output_dir(dir)` | settings |
|  | `set_image_width_mm(value)` | settings |
| 驗證 | `validate_template(...)` | `ReportGenerator.validate` |
| 執行 | `generate_reports(...)` | `ReportGenerator.generate` |
|  | `open_output_folder()` | `open_folder` |
| 互動 | `ask_user(question, options?)` | UI queue → 對話框 |
|  | `request_file(prompt, kind)` | filedialog 代理 |
| 審查 | `review_report(path, criteria)` | reviewer agent |

工具集中在 `app/agent/tools.py`，每個工具皆為純函式 + JSON schema，
便於跨 provider 重用。

### 2.3 Planner Loop

```
system + 使用者目標
  │
  ▼
  while not done:
     resp = llm.chat(messages, tools)
     if resp.tool_calls:
        for tc in resp.tool_calls:
           if tc.name == "ask_user":
              pause_and_ask(tc.args)
           else:
              result = registry.run(tc.name, tc.args)
           messages.append(tool_result)
     elif "DONE" in resp.text:
        done = True
```

- 工具呼叫失敗 → 回給 LLM 錯誤訊息；最多 N 次自動重試後 escalate `ask_user`。
- 所有對話寫進 Agent 頁籤（user / assistant / tool 三色），便於除錯。

### 2.4 Human-in-the-Loop

- `AgentOrchestrator` 持兩個 queue：問題 queue（agent → UI）、回覆 queue（UI → agent）。
- Agent 線程 block 等候回覆；UI 不會凍結（agent 在 background thread 跑）。
- 「中止 agent」按鈕 set `cancel_event`，下一輪迴圈跳出。

### 2.5 Reviewer Agent（VLM）

每份報告產出後：

1. **Word → 圖片**：用 Word COM `ExportAsFixedFormat` 轉 PDF，
   再 `pdf2image` 或 `PyMuPDF` 轉每頁 PNG。
2. **VLM 評估**：呼 vision-capable 模型，prompt 含：
   - 報告原始上下文（哪一列數據）
   - 範本變數
   - **使用者自訂 rubric**（settings 中可改）
3. **回傳結構化結果**：`{passed, score, issues[], suggestions[]}`。
4. **失敗處理**：依使用者選擇——
   - **預設策略：標記到 `Failed_Reports/` 等下一批調整再做**（已確認）
   - 不自動重產，由人手動或下批 prompt 處理。

⚠ 成本控管：可關閉 reviewer、抽樣審查（每 N 份審 1 份）、預算上限。

## 3. UI 變更

### 新增「AI 引擎」頁籤（P1）

```
[Provider: Gemini ▼]                     [刷新] [測試連線]

──── Gemini ─────────────────────────────────────
API Key 來源: .env (GEMINI_API_KEY)   [狀態: 已設定]
Planner Model:   [gemini-2.5-pro    ▼]
Reviewer Model:  [gemini-2.5-flash  ▼]

──── Ollama ─────────────────────────────────────
Endpoint: [http://localhost:11434]
Planner Model:   [llama3.1:8b   ▼]
Reviewer Model:  [llava:13b     ▼]

──── 審查設定 ────────────────────────────────────
☑ 啟用審查
抽樣比例: [100] %        最大重試: [3]
評分標準（rubric）:
┌──────────────────────────────────────────────┐
│ 1. 無未替換 {{...}} 佔位符                     │
│ 2. 欄位值符合語意                              │
│ ...                                          │
└──────────────────────────────────────────────┘
```

### 新增「Agent」頁籤（P3+）

```
[聊天視窗 — user / assistant / tool 三色訊息流]
[輸入框: 例「用 abc.docx 配 data.xlsx 第二個工作表，全部產出」]
[送出]   [中止]   [清空]
[狀態列: idle / thinking / waiting_user / executing X / reviewing 3/10]
```

## 4. 依賴新增（2026-05 已查證最新版）

```
python-dotenv >= 1.2.2       # .env 讀取
google-genai >= 2.0.0        # Gemini（新版統一 SDK；舊 google-generativeai 已棄用）
# Ollama 使用 stdlib urllib，P1 不另外加；P3 視 tool calling 需求再決定是否加 ollama lib
PyMuPDF                      # docx → png（reviewer 用，P5）
docx2pdf                     # docx → pdf（Win 上靠 Word COM，P5）
```

**SDK 重點變更**：Google 於 2025 年將 `google-generativeai` 標為 deprecated；
新版 `google-genai`（套件名 google-genai，匯入 `from google import genai`）
為統一 SDK，AI Studio 與 Vertex AI 皆走同一支介面。
所有 client 操作走 `client = genai.Client()`、`client.models.list()`、
`client.models.generate_content(...)`，`GEMINI_API_KEY` 環境變數會自動讀取。

## 5. 模組規劃（不動 mapper/generator）

```
app/
  agent/
    __init__.py
    tools.py            # Tool dataclass + registry, schema
    orchestrator.py     # Planner loop, human-in-loop
    reviewer.py         # VLM reviewer agent
    docx_render.py      # docx → PDF → image
    llm/
      __init__.py
      base.py           # LLMClient ABC
      gemini.py         # Gemini 實作
      ollama.py         # Ollama 實作
  ui_agent.py           # Agent 頁籤（chat box, controls）
```

`ui.py` 只新增 import + tab。

## 6. 關鍵風險與對策

| 風險 | 對策 |
|---|---|
| Word COM apartment 衝突（多執行緒）| 集中所有 COM 呼叫到單一 worker thread；agent 透過 queue 派工 |
| Ollama 工具呼叫格式不穩 | 包一層 JSON 自我修正：呼叫失敗→回給模型「請以 X 格式重發」 |
| VLM 將正確報告誤判失敗 | 失敗只標記到 `Failed_Reports/`；不自動重產 |
| 成本（Gemini API） | 預算 cap、抽樣審查、本地 reviewer 選項（llava）|
| 阻塞 UI | 一律 background thread + `self.after` 同步 UI |
| **API key 外流** | **`.env` + `python-dotenv`；`.gitignore` 明確排除 .env** |
| docx → image 失敗（Office 不在）| 雙路徑：Word COM 優先，PyMuPDF + python-docx 渲染備援 |
| 自動 retry 死循環 | 每個 task 設次數上限與整體時間上限 |
| **無 LLM 環境亦需可用** | **agent 模組全部 lazy import；缺套件 / API key 不影響手動頁籤** |

## 7. 階段化實作

| Phase | 範圍 | 可交付 |
|---|---|---|
| **P1 ✓** | LLM provider 抽象 + 模型列表 + AI 引擎 tab + .env | 在 UI 看到 Gemini / Ollama 模型；測試連線通 |
| **P2 ✓** | Tool registry + 3 個 read-only tool + Agent 頁籤 + chat loop | 用 chat 問「這個 Excel 有哪些欄位」能正確答 |
| **P3 ✓** | 寫入類 tool + validate + generate；planner 完整對話流 | 自然語言下「產出全部報告」能跑完 |
| P4 | Human-in-the-loop（ask_user / request_file 對話框）| 缺檔案會主動問 |
| P5 | docx → image pipeline | 任一 docx 轉成 PNG 列陣 |
| P6 | Reviewer agent + 失敗標記 → `Failed_Reports/` | 自動審查；失敗存 fail folder 等下批處理 |
| P7 | 抽樣 / 預算上限 / 進度 UI / 對話日誌匯出 | 生產級可用 |

## 8. 已確認決策（user 2026-05-08）

1. **rubric 來源**：UI 提供多行文字輸入框，預設值為「無未替換變數、欄位填值合理、版面未破、圖片正確嵌入」。
2. **審查失敗處理**：標記到 `Failed_Reports/`，等下一批調整再做。
3. **Ollama**：本機已安裝。
4. **Gemini API Key**：已備妥；存 `.env`，`python-dotenv` 啟動載入。
5. **對話 UI**：完整對話日誌（user / assistant / tool）逐則顯示。
6. **API Key 管理**：`.env`（不寫進 settings.json，亦不入 git）。
