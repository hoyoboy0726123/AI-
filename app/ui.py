"""主視窗 GUI（customtkinter）。"""

import os
import subprocess
import sys
import threading
from tkinter import filedialog, messagebox

import customtkinter as ctk
import pandas as pd

from app.config import (
    APPEARANCE_MODE,
    COLOR_BLUE,
    COLOR_BLUE_HOVER,
    COLOR_GREEN,
    COLOR_GREEN_HOVER,
    COLOR_RED,
    COLOR_THEME,
    HOTKEY,
    WINDOW_HEADER,
    WINDOW_SIZE,
    WINDOW_TITLE,
)
import json

from app.agent.llm import GEMINI_AVAILABLE, PROVIDERS, get_client
from app.agent.orchestrator import AgentOrchestrator
from app.agent.tools import build_default_registry
from app.generator import ReportGenerator
from app.hotkey import HotkeyManager
from app.mapper import OfficeMapper
from app.settings import load_settings, save_settings

ctk.set_appearance_mode(APPEARANCE_MODE)
ctk.set_default_color_theme(COLOR_THEME)


def open_folder(path):
    if not os.path.exists(path):
        return False
    if sys.platform.startswith("win"):
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.run(["open", path], check=False)
    else:
        subprocess.run(["xdg-open", path], check=False)
    return True


class AutoReportApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self.title(WINDOW_TITLE)
        self.geometry(WINDOW_SIZE)

        self.word_path = ctk.StringVar(value=self.settings["word_path"])
        self.excel_path = ctk.StringVar(value=self.settings["excel_path"])
        self.output_dir = ctk.StringVar(value=self.settings["output_dir"])
        self.filename_template = ctk.StringVar(value=self.settings["filename_template"])
        self.sheet_name = ctk.StringVar(value=self.settings["sheet_name"])
        self.header_row = ctk.StringVar(value=str(self.settings["header_row"]))
        self.image_width_mm = ctk.StringVar(value=str(self.settings["image_width_mm"]))
        self.grid_columns = ctk.StringVar(value=str(self.settings["grid_columns"]))

        self.llm_provider = ctk.StringVar(value=self.settings["llm_provider"])
        self.gemini_planner_model = ctk.StringVar(value=self.settings["gemini_planner_model"])
        self.gemini_reviewer_model = ctk.StringVar(value=self.settings["gemini_reviewer_model"])
        self.ollama_endpoint = ctk.StringVar(value=self.settings["ollama_endpoint"])
        self.ollama_planner_model = ctk.StringVar(value=self.settings["ollama_planner_model"])
        self.ollama_reviewer_model = ctk.StringVar(value=self.settings["ollama_reviewer_model"])
        self.enable_review = ctk.BooleanVar(value=self.settings["enable_review"])
        self.review_sampling = ctk.StringVar(value=str(self.settings["review_sampling_percent"]))
        self.max_review_retries = ctk.StringVar(value=str(self.settings["max_review_retries"]))

        self.mapping_active = False
        self.is_generating = False
        self.cancel_event = threading.Event()
        self.mapping_history = []  # list of (label, (start, end))

        self.agent_orchestrator = None
        self.agent_thread = None

        self.hotkey_manager = HotkeyManager(HOTKEY, self._on_hotkey)

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        if self.excel_path.get() and os.path.isfile(self.excel_path.get()):
            self._refresh_sheet_list(silent=True)

    # ---- UI build ----

    def _build_ui(self):
        ctk.CTkLabel(
            self, text=WINDOW_HEADER, font=ctk.CTkFont(size=20, weight="bold")
        ).pack(pady=(15, 8))

        tabs = ctk.CTkTabview(self)
        tabs.pack(padx=15, pady=8, fill="both", expand=True)
        tabs.add("設定")
        tabs.add("對應")
        tabs.add("產出")
        tabs.add("AI 引擎")
        tabs.add("Agent")

        self._build_settings_tab(tabs.tab("設定"))
        self._build_mapping_tab(tabs.tab("對應"))
        self._build_generate_tab(tabs.tab("產出"))
        self._build_ai_tab(tabs.tab("AI 引擎"))
        self._build_agent_tab(tabs.tab("Agent"))

        self.log_box = ctk.CTkTextbox(self, height=110)
        self.log_box.pack(padx=15, pady=(0, 12), fill="x")
        self.log("系統準備就緒。")

    def _build_settings_tab(self, parent):
        rows = [
            ("Word 範本:", self.word_path, self._select_word, "選取"),
            ("Excel 數據:", self.excel_path, self._select_excel, "選取"),
        ]
        for r, (label, var, cmd, btn) in enumerate(rows):
            ctk.CTkLabel(parent, text=label).grid(row=r, column=0, padx=10, pady=8, sticky="w")
            ctk.CTkEntry(parent, textvariable=var, width=380).grid(row=r, column=1, padx=10, pady=8)
            ctk.CTkButton(parent, text=btn, width=70, command=cmd).grid(row=r, column=2, padx=10, pady=8)

        r = 2
        ctk.CTkLabel(parent, text="工作表:").grid(row=r, column=0, padx=10, pady=8, sticky="w")
        self.sheet_combo = ctk.CTkComboBox(
            parent, variable=self.sheet_name, width=380, values=[""]
        )
        self.sheet_combo.grid(row=r, column=1, padx=10, pady=8)
        ctk.CTkButton(parent, text="刷新", width=70, command=self._refresh_sheet_list).grid(
            row=r, column=2, padx=10, pady=8
        )

        r += 1
        ctk.CTkLabel(parent, text="標題列:").grid(row=r, column=0, padx=10, pady=8, sticky="w")
        ctk.CTkEntry(parent, textvariable=self.header_row, width=80).grid(
            row=r, column=1, padx=10, pady=8, sticky="w"
        )
        ctk.CTkLabel(parent, text="（Excel 中欄位名稱所在列，預設 1）").grid(
            row=r, column=1, padx=(95, 10), pady=8, sticky="w"
        )

        r += 1
        ctk.CTkLabel(parent, text="輸出資料夾:").grid(row=r, column=0, padx=10, pady=8, sticky="w")
        ctk.CTkEntry(parent, textvariable=self.output_dir, width=380).grid(row=r, column=1, padx=10, pady=8)
        ctk.CTkButton(parent, text="選取", width=70, command=self._select_output_dir).grid(
            row=r, column=2, padx=10, pady=8
        )

        r += 1
        ctk.CTkLabel(parent, text="檔名規則:").grid(row=r, column=0, padx=10, pady=8, sticky="w")
        ctk.CTkEntry(parent, textvariable=self.filename_template, width=380).grid(
            row=r, column=1, padx=10, pady=8
        )

        r += 1
        ctk.CTkLabel(
            parent,
            text="例：{客戶名稱}_{日期}.docx；{index} 為自動序號",
            text_color="gray",
        ).grid(row=r, column=1, padx=10, pady=(0, 8), sticky="w")

        r += 1
        ctk.CTkLabel(parent, text="圖片寬度 (mm):").grid(row=r, column=0, padx=10, pady=8, sticky="w")
        ctk.CTkEntry(parent, textvariable=self.image_width_mm, width=80).grid(
            row=r, column=1, padx=10, pady=8, sticky="w"
        )
        ctk.CTkLabel(parent, text="（插入圖片與圖片欄位的預設寬度，自動鎖長寬比）").grid(
            row=r, column=1, padx=(95, 10), pady=8, sticky="w"
        )

        r += 1
        ctk.CTkLabel(parent, text="網格欄數:").grid(row=r, column=0, padx=10, pady=8, sticky="w")
        ctk.CTkEntry(parent, textvariable=self.grid_columns, width=80).grid(
            row=r, column=1, padx=10, pady=8, sticky="w"
        )
        ctk.CTkLabel(parent, text="（多張圖片網格貼圖時每列張數）").grid(
            row=r, column=1, padx=(95, 10), pady=8, sticky="w"
        )

    def _build_mapping_tab(self, parent):
        self.btn_mapping = ctk.CTkButton(
            parent,
            text=f"開啟標籤映射模式 ({HOTKEY.upper()})",
            fg_color=COLOR_GREEN,
            hover_color=COLOR_GREEN_HOVER,
            command=self._toggle_mapping,
        )
        self.btn_mapping.pack(pady=(15, 6), padx=15, fill="x")

        ctk.CTkButton(
            parent,
            text="從檔案總管選圖片並插入到 Word 游標位置",
            command=self._insert_image_at_cursor,
        ).pack(pady=6, padx=15, fill="x")

        ctk.CTkButton(
            parent,
            text="多選圖片以網格貼入 Word 游標位置",
            command=self._insert_image_grid_at_cursor,
        ).pack(pady=6, padx=15, fill="x")

        ctk.CTkLabel(
            parent, text="映射歷史（最新在最上）", font=ctk.CTkFont(weight="bold")
        ).pack(pady=(15, 4))

        history_frame = ctk.CTkFrame(parent)
        history_frame.pack(padx=15, pady=4, fill="both", expand=True)

        self.history_box = ctk.CTkTextbox(history_frame, height=160)
        self.history_box.pack(side="left", fill="both", expand=True, padx=(0, 8))

        undo_buttons = ctk.CTkFrame(history_frame, fg_color="transparent")
        undo_buttons.pack(side="right", padx=4, pady=4, anchor="n")
        ctk.CTkButton(
            undo_buttons, text="復原最近一筆", width=110, command=self._undo_last_mapping
        ).pack(pady=(0, 6))
        ctk.CTkButton(
            undo_buttons,
            text="全部復原",
            width=110,
            fg_color=COLOR_RED,
            command=self._undo_all_mappings,
        ).pack()

    def _build_generate_tab(self, parent):
        ctk.CTkButton(
            parent, text="檢查範本變數 vs Excel 欄位", command=self._validate
        ).pack(pady=(15, 6), padx=15, fill="x")

        self.btn_generate = ctk.CTkButton(
            parent,
            text="開始批次產出報告",
            fg_color=COLOR_BLUE,
            hover_color=COLOR_BLUE_HOVER,
            command=self._toggle_generation,
        )
        self.btn_generate.pack(pady=6, padx=15, fill="x")

        self.progress = ctk.CTkProgressBar(parent)
        self.progress.set(0)
        self.progress.pack(pady=(15, 4), padx=15, fill="x")
        self.progress_label = ctk.CTkLabel(parent, text="尚未開始")
        self.progress_label.pack(pady=2)

        ctk.CTkButton(
            parent, text="開啟輸出資料夾", command=self._open_output_dir
        ).pack(pady=(15, 8), padx=15, fill="x")

    def _build_ai_tab(self, parent):
        scroll = ctk.CTkScrollableFrame(parent)
        scroll.pack(fill="both", expand=True, padx=4, pady=4)

        # Provider 選擇
        head = ctk.CTkFrame(scroll, fg_color="transparent")
        head.pack(fill="x", padx=8, pady=(8, 4))
        ctk.CTkLabel(head, text="Provider:").pack(side="left", padx=(0, 6))
        self.provider_combo = ctk.CTkComboBox(
            head,
            variable=self.llm_provider,
            values=list(PROVIDERS),
            width=140,
            command=lambda _v: self._show_provider_frame(),
        )
        self.provider_combo.pack(side="left", padx=4)
        ctk.CTkButton(head, text="刷新模型", width=90, command=self._refresh_llm_models).pack(side="left", padx=4)
        ctk.CTkButton(head, text="測試連線", width=90, command=self._test_llm).pack(side="left", padx=4)

        # Gemini 設定區
        self.gemini_frame = ctk.CTkFrame(scroll)
        ctk.CTkLabel(self.gemini_frame, text="Gemini", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, columnspan=2, padx=10, pady=(10, 4), sticky="w"
        )
        ctk.CTkLabel(self.gemini_frame, text="API Key 來源:").grid(row=1, column=0, padx=10, pady=6, sticky="w")
        self.gemini_key_status = ctk.CTkLabel(self.gemini_frame, text=self._gemini_key_status_text())
        self.gemini_key_status.grid(row=1, column=1, padx=10, pady=6, sticky="w")
        ctk.CTkLabel(self.gemini_frame, text="Planner Model:").grid(row=2, column=0, padx=10, pady=6, sticky="w")
        self.gemini_planner_combo = ctk.CTkComboBox(
            self.gemini_frame, variable=self.gemini_planner_model, values=[""], width=320
        )
        self.gemini_planner_combo.grid(row=2, column=1, padx=10, pady=6, sticky="w")
        ctk.CTkLabel(self.gemini_frame, text="Reviewer Model:").grid(row=3, column=0, padx=10, pady=6, sticky="w")
        self.gemini_reviewer_combo = ctk.CTkComboBox(
            self.gemini_frame, variable=self.gemini_reviewer_model, values=[""], width=320
        )
        self.gemini_reviewer_combo.grid(row=3, column=1, padx=10, pady=(6, 10), sticky="w")

        # Ollama 設定區
        self.ollama_frame = ctk.CTkFrame(scroll)
        ctk.CTkLabel(self.ollama_frame, text="Ollama", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, columnspan=2, padx=10, pady=(10, 4), sticky="w"
        )
        ctk.CTkLabel(self.ollama_frame, text="Endpoint:").grid(row=1, column=0, padx=10, pady=6, sticky="w")
        ctk.CTkEntry(self.ollama_frame, textvariable=self.ollama_endpoint, width=320).grid(
            row=1, column=1, padx=10, pady=6, sticky="w"
        )
        ctk.CTkLabel(self.ollama_frame, text="Planner Model:").grid(row=2, column=0, padx=10, pady=6, sticky="w")
        self.ollama_planner_combo = ctk.CTkComboBox(
            self.ollama_frame, variable=self.ollama_planner_model, values=[""], width=320
        )
        self.ollama_planner_combo.grid(row=2, column=1, padx=10, pady=6, sticky="w")
        ctk.CTkLabel(self.ollama_frame, text="Reviewer Model:").grid(row=3, column=0, padx=10, pady=6, sticky="w")
        self.ollama_reviewer_combo = ctk.CTkComboBox(
            self.ollama_frame, variable=self.ollama_reviewer_model, values=[""], width=320
        )
        self.ollama_reviewer_combo.grid(row=3, column=1, padx=10, pady=(6, 10), sticky="w")

        self._show_provider_frame()

        # Reviewer 設定
        rv = ctk.CTkFrame(scroll)
        rv.pack(fill="x", padx=8, pady=(10, 6))
        ctk.CTkLabel(rv, text="審查設定", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, columnspan=4, padx=10, pady=(10, 4), sticky="w"
        )
        ctk.CTkCheckBox(rv, text="啟用審查", variable=self.enable_review).grid(
            row=1, column=0, padx=10, pady=6, sticky="w"
        )
        ctk.CTkLabel(rv, text="抽樣比例 (%):").grid(row=1, column=1, padx=10, pady=6, sticky="e")
        ctk.CTkEntry(rv, textvariable=self.review_sampling, width=70).grid(row=1, column=2, padx=4, pady=6, sticky="w")
        ctk.CTkLabel(rv, text="最大重試:").grid(row=1, column=3, padx=10, pady=6, sticky="e")
        ctk.CTkEntry(rv, textvariable=self.max_review_retries, width=70).grid(row=1, column=4, padx=4, pady=6, sticky="w")

        ctk.CTkLabel(rv, text="評分標準 (rubric)：").grid(row=2, column=0, columnspan=5, padx=10, pady=(8, 2), sticky="w")
        self.rubric_box = ctk.CTkTextbox(rv, height=140)
        self.rubric_box.grid(row=3, column=0, columnspan=5, padx=10, pady=(0, 10), sticky="ew")
        self.rubric_box.insert("1.0", self.settings["review_rubric"])
        rv.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            scroll,
            text="提示：Gemini API Key 由 .env 中 GEMINI_API_KEY 載入；無 LLM 環境亦可繼續使用其他頁籤。",
            text_color="gray",
        ).pack(padx=10, pady=(4, 8), anchor="w")

        if not GEMINI_AVAILABLE:
            ctk.CTkLabel(
                scroll,
                text="⚠ google-genai 套件未安裝，Gemini 功能將不可用（pip install google-genai）。",
                text_color="orange",
            ).pack(padx=10, pady=(0, 8), anchor="w")

    def _show_provider_frame(self):
        if self.llm_provider.get() == "Gemini":
            self.ollama_frame.pack_forget()
            self.gemini_frame.pack(fill="x", padx=8, pady=6)
        else:
            self.gemini_frame.pack_forget()
            self.ollama_frame.pack(fill="x", padx=8, pady=6)

    def _gemini_key_status_text(self):
        if not GEMINI_AVAILABLE:
            return "套件未安裝"
        if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
            return ".env (GEMINI_API_KEY) 已設定"
        return ".env 未設定"

    def _build_llm_client(self):
        provider = self.llm_provider.get()
        if provider == "Gemini":
            return get_client("Gemini")
        return get_client("Ollama", endpoint=self.ollama_endpoint.get())

    def _test_llm(self):
        threading.Thread(target=self._test_llm_thread, daemon=True).start()

    def _test_llm_thread(self):
        provider = self.llm_provider.get()
        try:
            client = self._build_llm_client()
            ok = client.is_available()
        except Exception as e:
            self._safe_log(f"{provider} 連線失敗: {e}")
            return
        self._safe_log(f"{provider} 連線測試: {'✓ 成功' if ok else '✗ 失敗 (檢查 API key 或 endpoint)'}")

    def _refresh_llm_models(self):
        threading.Thread(target=self._refresh_llm_models_thread, daemon=True).start()

    def _refresh_llm_models_thread(self):
        provider = self.llm_provider.get()
        try:
            client = self._build_llm_client()
            models = client.list_models()
            vision = client.list_vision_models()
        except Exception as e:
            self._safe_log(f"讀取模型清單失敗: {e}")
            return

        def update():
            if provider == "Gemini":
                planner_combo = self.gemini_planner_combo
                reviewer_combo = self.gemini_reviewer_combo
                planner_var = self.gemini_planner_model
                reviewer_var = self.gemini_reviewer_model
            else:
                planner_combo = self.ollama_planner_combo
                reviewer_combo = self.ollama_reviewer_combo
                planner_var = self.ollama_planner_model
                reviewer_var = self.ollama_reviewer_model

            planner_combo.configure(values=models or [""])
            reviewer_combo.configure(values=vision or models or [""])
            if planner_var.get() not in models and models:
                planner_var.set(models[0])
            if reviewer_var.get() not in (vision or models) and (vision or models):
                reviewer_var.set((vision or models)[0])
            self.log(f"{provider}: 共 {len(models)} 個模型，其中 {len(vision)} 個支援 vision。")

        self.after(0, update)

    # ---- Agent 頁籤 ----

    def _build_agent_tab(self, parent):
        top = ctk.CTkFrame(parent, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=(8, 4))
        self.agent_status = ctk.CTkLabel(top, text="狀態: idle", text_color="gray")
        self.agent_status.pack(side="left")
        ctk.CTkButton(top, text="新對話", width=90, command=self._agent_reset).pack(side="right", padx=4)
        ctk.CTkButton(
            top, text="中止", width=90, fg_color=COLOR_RED, command=self._agent_cancel
        ).pack(side="right", padx=4)

        self.agent_box = ctk.CTkTextbox(parent, wrap="word")
        self.agent_box.pack(fill="both", expand=True, padx=8, pady=4)
        self.agent_box.configure(state="disabled")

        bottom = ctk.CTkFrame(parent, fg_color="transparent")
        bottom.pack(fill="x", padx=8, pady=(4, 8))
        self.agent_input = ctk.CTkTextbox(bottom, height=70, wrap="word")
        self.agent_input.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.agent_input.bind("<Control-Return>", lambda _e: self._agent_send())
        ctk.CTkButton(bottom, text="送出", width=80, command=self._agent_send).pack(side="right")

        self._agent_append_text(
            "── Agent 已就緒 ──\n"
            "提示：在「AI 引擎」頁籤選好 provider 與模型後再開始對話。\n"
            "範例：「目前選的 Excel 有哪些工作表？」「list 範本變數」\n"
            "（Ctrl+Enter 也可送出）\n\n"
        )

    def _agent_set_status(self, text):
        def update():
            self.agent_status.configure(text=f"狀態: {text}")
        self.after(0, update)

    def _agent_append_text(self, text):
        def append():
            self.agent_box.configure(state="normal")
            self.agent_box.insert("end", text)
            self.agent_box.see("end")
            self.agent_box.configure(state="disabled")
        if threading.current_thread() is threading.main_thread():
            append()
        else:
            self.after(0, append)

    def _agent_render(self, msg):
        if msg.role == "user":
            self._agent_append_text(f"\n[你]\n{msg.text}\n")
            return
        if msg.role == "assistant":
            for tc in msg.tool_calls:
                args = json.dumps(tc.arguments, ensure_ascii=False)
                self._agent_append_text(f"\n[助理 → 工具呼叫] {tc.name}({args})\n")
            if msg.text:
                self._agent_append_text(f"\n[助理]\n{msg.text}\n")
            return
        if msg.role == "tool":
            preview = msg.text if len(msg.text) <= 600 else msg.text[:600] + "..."
            self._agent_append_text(f"\n[工具回傳 {msg.tool_name}]\n{preview}\n")
            return

    def _agent_reset(self):
        if self.agent_thread and self.agent_thread.is_alive():
            self.log("Agent 仍在執行中，請先中止。")
            return
        self.agent_orchestrator = None
        self.agent_box.configure(state="normal")
        self.agent_box.delete("1.0", "end")
        self.agent_box.configure(state="disabled")
        self._agent_append_text("── 對話已重置 ──\n")
        self._agent_set_status("idle")

    def _agent_cancel(self):
        if self.agent_orchestrator:
            self.agent_orchestrator.cancel()
            self._agent_set_status("cancelling")

    def _agent_planner_model(self):
        if self.llm_provider.get() == "Gemini":
            return self.gemini_planner_model.get()
        return self.ollama_planner_model.get()

    def _agent_build_orchestrator(self):
        provider = self.llm_provider.get()
        if provider == "Gemini":
            client = get_client("Gemini")
        else:
            client = get_client("Ollama", endpoint=self.ollama_endpoint.get())

        if not client.is_available():
            self._agent_append_text(
                f"[錯誤] {provider} 不可用：請至「AI 引擎」頁籤檢查 API key / endpoint。\n"
            )
            return None

        model = self._agent_planner_model()
        if not model:
            self._agent_append_text(
                "[錯誤] 尚未選擇 planner 模型，請至「AI 引擎」頁籤刷新並選定。\n"
            )
            return None

        context = {
            "word_path": self.word_path.get(),
            "excel_path": self.excel_path.get(),
            "sheet_name": self.sheet_name.get(),
            "header_row": self._header_row_int(),
            "output_dir": self.output_dir.get(),
        }
        return AgentOrchestrator(
            llm=client,
            registry=build_default_registry(),
            model=model,
            context=context,
        )

    def _agent_send(self):
        text = self.agent_input.get("1.0", "end").strip()
        if not text:
            return
        if self.agent_thread and self.agent_thread.is_alive():
            self._agent_append_text("[提示] 正在處理中，請稍候。\n")
            return

        self.agent_input.delete("1.0", "end")

        if self.agent_orchestrator is None:
            self.agent_orchestrator = self._agent_build_orchestrator()
            if self.agent_orchestrator is None:
                return

        self._agent_render(type("M", (), {"role": "user", "text": text, "tool_calls": []})())
        self.agent_orchestrator.add_user_message(text)
        self._agent_set_status("thinking")

        self.agent_thread = threading.Thread(target=self._agent_run_step, daemon=True)
        self.agent_thread.start()

    def _agent_run_step(self):
        try:
            for msg in self.agent_orchestrator.step():
                if msg.role == "assistant" and msg.tool_calls:
                    self._agent_set_status(f"calling {msg.tool_calls[0].name}")
                elif msg.role == "tool":
                    self._agent_set_status("thinking")
                self._agent_render(msg)
        except Exception as e:
            self._agent_append_text(f"\n[執行錯誤] {e}\n")
        finally:
            self._agent_set_status("idle")

    # ---- helpers ----

    def log(self, msg):
        self.log_box.insert("end", f"> {msg}\n")
        self.log_box.see("end")

    def _safe_log(self, msg):
        """從背景執行緒安全地寫 log。"""
        self.after(0, lambda: self.log(msg))

    def _header_row_int(self):
        try:
            return max(1, int(self.header_row.get()))
        except (ValueError, TypeError):
            return 1

    def _image_width_mm_int(self):
        try:
            return max(1, int(float(self.image_width_mm.get())))
        except (ValueError, TypeError):
            return 80

    def _grid_columns_int(self):
        try:
            return max(1, int(self.grid_columns.get()))
        except (ValueError, TypeError):
            return 2

    def _review_sampling_int(self):
        try:
            return max(1, min(100, int(float(self.review_sampling.get()))))
        except (ValueError, TypeError):
            return 100

    def _max_retries_int(self):
        try:
            return max(0, int(self.max_review_retries.get()))
        except (ValueError, TypeError):
            return 3

    def _refresh_history_box(self):
        self.history_box.delete("1.0", "end")
        for i, (label, _) in enumerate(reversed(self.mapping_history), 1):
            self.history_box.insert("end", f"{i}. {label}\n")

    def _persist_settings(self):
        self.settings.update(
            {
                "word_path": self.word_path.get(),
                "excel_path": self.excel_path.get(),
                "output_dir": self.output_dir.get(),
                "filename_template": self.filename_template.get(),
                "sheet_name": self.sheet_name.get(),
                "header_row": self._header_row_int(),
                "image_width_mm": self._image_width_mm_int(),
                "grid_columns": self._grid_columns_int(),
                "llm_provider": self.llm_provider.get(),
                "gemini_planner_model": self.gemini_planner_model.get(),
                "gemini_reviewer_model": self.gemini_reviewer_model.get(),
                "ollama_endpoint": self.ollama_endpoint.get(),
                "ollama_planner_model": self.ollama_planner_model.get(),
                "ollama_reviewer_model": self.ollama_reviewer_model.get(),
                "enable_review": bool(self.enable_review.get()),
                "review_sampling_percent": self._review_sampling_int(),
                "max_review_retries": self._max_retries_int(),
                "review_rubric": self.rubric_box.get("1.0", "end").rstrip(),
            }
        )
        try:
            save_settings(self.settings)
        except Exception as e:
            self.log(f"設定儲存失敗: {e}")

    def _on_close(self):
        self._persist_settings()
        self.hotkey_manager.stop()
        self.destroy()

    # ---- file pickers ----

    def _select_word(self):
        path = filedialog.askopenfilename(filetypes=[("Word Files", "*.docx")])
        if path:
            self.word_path.set(path)

    def _select_excel(self):
        path = filedialog.askopenfilename(filetypes=[("Excel Files", "*.xlsx *.xls")])
        if path:
            self.excel_path.set(path)
            self._refresh_sheet_list()

    def _select_output_dir(self):
        path = filedialog.askdirectory()
        if path:
            self.output_dir.set(path)

    def _refresh_sheet_list(self, silent=False):
        path = self.excel_path.get()
        if not path or not os.path.isfile(path):
            return
        try:
            sheets = pd.ExcelFile(path).sheet_names
        except Exception as e:
            self.log(f"讀取工作表失敗: {e}")
            return
        self.sheet_combo.configure(values=sheets or [""])
        if self.sheet_name.get() not in sheets:
            self.sheet_name.set(sheets[0] if sheets else "")
        if not silent:
            self.log(f"工作表清單: {', '.join(sheets)}")

    # ---- mapping ----

    def _toggle_mapping(self):
        if self.mapping_active:
            self.mapping_active = False
            self.hotkey_manager.stop()
            self.btn_mapping.configure(
                text=f"開啟標籤映射模式 ({HOTKEY.upper()})",
                fg_color=COLOR_GREEN,
            )
            self.log("映射模式已關閉。")
        else:
            self.mapping_active = True
            self.hotkey_manager.start()
            self.btn_mapping.configure(
                text=f"映射模式運作中... (按 {HOTKEY.upper()} 標註)",
                fg_color=COLOR_RED,
            )
            self.log("映射模式啟動！請回到 Word 與 Excel 操作。")

    def _on_hotkey(self):
        # 在 keyboard 監聽執行緒上呼叫 COM；UI 操作必須回到主執行緒。
        success, message, rng = OfficeMapper.insert_tag_at_cursor(
            header_row=self._header_row_int()
        )

        def apply():
            if success:
                self.mapping_history.append((message, rng))
                self._refresh_history_box()
                self.log(f"映射成功: {message}")
            else:
                self.log(message)

        self.after(0, apply)

    def _undo_last_mapping(self):
        if not self.mapping_history:
            self.log("沒有可復原的映射。")
            return
        label, rng = self.mapping_history.pop()
        if rng is None:
            self.log(f"已從歷史移除「{label}」（缺少位置資訊）。")
        else:
            ok, err = OfficeMapper.remove_range(*rng)
            if ok:
                self.log(f"已復原「{label}」。")
            else:
                self.log(f"復原「{label}」失敗: {err}")
        self._refresh_history_box()

    def _insert_image_at_cursor(self):
        path = filedialog.askopenfilename(
            title="選取要插入到 Word 的圖片",
            filetypes=[
                ("Image Files", "*.png *.jpg *.jpeg *.gif *.bmp"),
                ("All Files", "*.*"),
            ],
        )
        if not path:
            return
        ok, message, rng = OfficeMapper.insert_image_at_cursor(
            path, width_mm=self._image_width_mm_int()
        )
        if ok:
            self.mapping_history.append((f"[圖] {message}", rng))
            self._refresh_history_box()
            self.log(f"圖片已插入: {message}")
        else:
            self.log(message)

    def _insert_image_grid_at_cursor(self):
        paths = filedialog.askopenfilenames(
            title="多選要插入的圖片（將以網格貼入）",
            filetypes=[
                ("Image Files", "*.png *.jpg *.jpeg *.gif *.bmp"),
                ("All Files", "*.*"),
            ],
        )
        if not paths:
            return
        ok, message, rng = OfficeMapper.insert_image_grid_at_cursor(
            list(paths),
            columns=self._grid_columns_int(),
            width_mm=self._image_width_mm_int(),
        )
        if ok:
            self.mapping_history.append((f"[網格] {message}", rng))
            self._refresh_history_box()
            self.log(message)
        else:
            self.log(message)

    def _undo_all_mappings(self):
        if not self.mapping_history:
            self.log("沒有可復原的映射。")
            return
        total = len(self.mapping_history)
        failures = 0
        # 由新到舊復原；先刪後段位置才不會被前段刪除影響
        while self.mapping_history:
            label, rng = self.mapping_history.pop()
            if rng is None:
                continue
            ok, _ = OfficeMapper.remove_range(*rng)
            if not ok:
                failures += 1
        self._refresh_history_box()
        if failures:
            self.log(f"全部復原完成（共 {total} 筆，{failures} 筆失敗）。")
        else:
            self.log(f"已全部復原 {total} 筆。")

    # ---- generation ----

    def _build_generator(self):
        return ReportGenerator(
            word_path=self.word_path.get(),
            excel_path=self.excel_path.get(),
            output_dir=self.output_dir.get(),
            sheet_name=self.sheet_name.get() or None,
            header_row=self._header_row_int(),
            filename_template=self.filename_template.get(),
            image_width_mm=self._image_width_mm_int(),
        )

    def _validate(self):
        if not self.word_path.get() or not self.excel_path.get():
            messagebox.showwarning("警告", "請先選取範本與數據檔案！")
            return
        try:
            missing, extra = self._build_generator().validate()
        except Exception as e:
            self.log(f"驗證失敗: {e}")
            return

        if not missing:
            self.log("✓ Word 範本所有變數都有對應 Excel 欄位。")
        else:
            self.log(f"⚠ Excel 缺少欄位: {', '.join(sorted(missing))}")
        if extra:
            self.log(f"提示: Excel 多出未使用欄位: {', '.join(sorted(extra))}")

    def _toggle_generation(self):
        if self.is_generating:
            self.cancel_event.set()
            self.btn_generate.configure(text="正在取消...")
            return

        if not self.word_path.get() or not self.excel_path.get():
            messagebox.showwarning("警告", "請先選取範本與數據檔案！")
            return

        self.cancel_event = threading.Event()
        self.is_generating = True
        self.btn_generate.configure(text="取消產出", fg_color=COLOR_RED)
        self.progress.set(0)
        self.progress_label.configure(text="準備中...")

        threading.Thread(target=self._process_files, daemon=True).start()

    def _process_files(self):
        try:
            self._safe_log("開始讀取數據...")
            generator = self._build_generator()
            produced, total = generator.generate(
                progress_callback=self._on_progress,
                cancel_event=self.cancel_event,
            )
            if self.cancel_event.is_set():
                self._safe_log(f"已取消，已產出 {produced}/{total} 份。")
            else:
                self._safe_log(f"完成！共 {produced} 份，輸出於 {self.output_dir.get()}")
                self.after(
                    0,
                    lambda: messagebox.showinfo("成功", f"已產出 {produced} 份報告！"),
                )
        except Exception as e:
            self._safe_log(f"生成失敗: {e}")
        finally:
            self.is_generating = False
            self.after(0, self._reset_generation_ui)

    def _on_progress(self, current, total):
        ratio = current / total if total else 0

        def update():
            self.progress.set(ratio)
            self.progress_label.configure(text=f"進度 {current}/{total}")

        self.after(0, update)

    def _reset_generation_ui(self):
        self.btn_generate.configure(text="開始批次產出報告", fg_color=COLOR_BLUE)

    def _open_output_dir(self):
        path = self.output_dir.get()
        if not path:
            self.log("尚未設定輸出資料夾。")
            return
        os.makedirs(path, exist_ok=True)
        if not open_folder(path):
            self.log(f"無法開啟: {path}")
