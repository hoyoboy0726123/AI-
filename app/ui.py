"""主視窗 GUI（customtkinter）。"""

import os
import subprocess
import sys
import threading
from tkinter import filedialog, messagebox

import customtkinter as ctk
import pandas as pd
import tkinter as tk

from app.agent.markdown_render import MarkdownRenderer
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

from app.agent.budget import BudgetTracker
from app.agent.context import AppContext
from app.agent.llm import GEMINI_AVAILABLE, PROVIDERS, get_client
from app.agent.orchestrator import AgentOrchestrator
from app.agent.tools import build_default_registry
from app.generator import ReportGenerator
from app.hotkey import HotkeyManager
from app.mapper import OfficeMapper
from app.settings import load_settings, save_settings

ctk.set_appearance_mode(APPEARANCE_MODE)
ctk.set_default_color_theme(COLOR_THEME)

# 拖拉檔案支援（可選；缺套件時退化）
try:
    import tkinterdnd2
    DND_AVAILABLE = True
except ImportError:
    tkinterdnd2 = None
    DND_AVAILABLE = False


def _short_path(p: str, max_len: int = 50) -> str:
    """log 用：太長的路徑顯示為 .../parent/name；短的維持原樣。"""
    if not p:
        return ""
    if len(p) <= max_len:
        return p
    parent = os.path.basename(os.path.dirname(p))
    name = os.path.basename(p)
    if parent:
        return f".../{parent}/{name}"
    return name


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
        # 在建立 widget 前套用主題（避免閃爍）
        try:
            ctk.set_appearance_mode(self.settings.get("appearance_mode", "System"))
        except Exception:
            pass
        self.title(WINDOW_TITLE)
        self.geometry(WINDOW_SIZE)
        self.minsize(720, 620)

        # 拖拉檔案支援（可選）
        self._dnd_enabled = False
        if DND_AVAILABLE:
            try:
                tkinterdnd2.TkinterDnD._require(self)
                self.drop_target_register(tkinterdnd2.DND_FILES)
                self.dnd_bind("<<Drop>>", self._on_file_drop)
                self._dnd_enabled = True
            except Exception:
                self._dnd_enabled = False

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
        self.max_planner_calls = ctk.StringVar(value=str(self.settings["max_planner_calls"]))
        self.max_reviewer_calls = ctk.StringVar(value=str(self.settings["max_reviewer_calls"]))
        self.appearance_mode = ctk.StringVar(value=self.settings.get("appearance_mode", "System"))

        self.mapping_active = False
        self.is_generating = False
        self.cancel_event = threading.Event()
        self.mapping_history = []  # list of (label, (start, end))

        self.agent_orchestrator = None
        self.agent_thread = None
        self.agent_chat_log = []  # list of {ts, kind, ...}

        self.budget = BudgetTracker(
            planner_limit=int(self.settings["max_planner_calls"]),
            reviewer_limit=int(self.settings["max_reviewer_calls"]),
        )
        self.app_context = AppContext(self)

        self.hotkey_manager = HotkeyManager(HOTKEY, self._on_hotkey)

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        if self.excel_path.get() and os.path.isfile(self.excel_path.get()):
            self._refresh_sheet_list(silent=True)

        # 啟動預算顯示輪詢（每 1.5s）
        self.after(500, self._refresh_budget_label)
        # 產出按鈕的 enable/disable 狀態輪詢
        self.after(800, self._refresh_generate_button_state)

    # ---- UI build ----

    def _build_ui(self):
        # 標題列：左側 header,右側主題切換
        header_bar = ctk.CTkFrame(self, fg_color="transparent")
        header_bar.pack(fill="x", padx=18, pady=(18, 0))

        title_box = ctk.CTkFrame(header_bar, fg_color="transparent")
        title_box.pack(side="left")
        ctk.CTkLabel(
            title_box, text="AI 辦公自動化",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=("#1f2328", "#e6edf3"),
            anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_box, text="Office 視覺化對應與自動生成系統",
            font=ctk.CTkFont(size=12),
            text_color=("#6b7280", "#8b949e"),
            anchor="w",
        ).pack(anchor="w")

        appearance_box = ctk.CTkFrame(header_bar, fg_color="transparent")
        appearance_box.pack(side="right")
        ctk.CTkLabel(
            appearance_box, text="主題",
            font=ctk.CTkFont(size=11),
            text_color=("#6b7280", "#8b949e"),
        ).pack(side="left", padx=(0, 6))
        ctk.CTkOptionMenu(
            appearance_box,
            variable=self.appearance_mode,
            values=["System", "Dark", "Light"],
            width=100, height=30,
            command=self._on_appearance_changed,
        ).pack(side="left")

        # 細分隔線
        sep = ctk.CTkFrame(self, fg_color=("#e5e7eb", "#262b33"), height=1)
        sep.pack(fill="x", padx=18, pady=(12, 0))

        tabs = ctk.CTkTabview(
            self,
            segmented_button_selected_color=COLOR_BLUE,
            segmented_button_selected_hover_color=COLOR_BLUE_HOVER,
        )
        tabs.pack(padx=18, pady=8, fill="both", expand=True)
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

        # 底部 log:小標 + textbox(輕量分隔風格)
        log_wrap = ctk.CTkFrame(self, fg_color="transparent")
        log_wrap.pack(fill="x", padx=18, pady=(4, 14))
        ctk.CTkLabel(
            log_wrap, text="Log",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=("#9aa0a6", "#6e7681"),
            anchor="w",
        ).pack(anchor="w", pady=(0, 2))
        self.log_box = ctk.CTkTextbox(
            log_wrap, height=96, wrap="word",
            font=ctk.CTkFont(family="Consolas", size=11),
            border_width=1,
            border_color=("#e5e7eb", "#262b33"),
            fg_color=("#fbfbfd", "#0f1115"),
        )
        self.log_box.pack(fill="x")

        # 智慧預設頁籤：未配置 LLM 停在「AI 引擎」，已配置且有路徑停在「Agent」
        self.tabs = tabs
        try:
            if self._llm_ready() and (self.word_path.get() or self.excel_path.get()):
                tabs.set("Agent")
            elif self._llm_ready():
                tabs.set("Agent")
            else:
                tabs.set("AI 引擎")
        except Exception:
            pass

        # 歡迎訊息
        self.log("──── 快速上手 ────")
        self.log("1) AI 引擎：選 Provider / 模型 / 預算")
        self.log("2) Agent：用一句話描述目標（缺資料會自動跳對話框）")
        self.log("3) 也可以走「設定 / 對應 / 產出」三頁籤手動操作（無 LLM 亦可）")
        if self._dnd_enabled:
            self.log("提示：可直接拖拉 .docx / .xlsx / 圖片 / 資料夾到視窗自動填入。")

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
        ctk.CTkLabel(
            parent,
            text="（Excel 中欄位名稱所在列，預設 1）",
            text_color="gray",
        ).grid(row=r, column=2, padx=(0, 10), pady=8, sticky="w")

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
        ctk.CTkLabel(
            parent,
            text="（插入圖片與圖片欄位的預設寬度，自動鎖長寬比）",
            text_color="gray",
        ).grid(row=r, column=2, padx=(0, 10), pady=8, sticky="w")

        r += 1
        ctk.CTkLabel(parent, text="網格欄數:").grid(row=r, column=0, padx=10, pady=8, sticky="w")
        ctk.CTkEntry(parent, textvariable=self.grid_columns, width=80).grid(
            row=r, column=1, padx=10, pady=8, sticky="w"
        )
        ctk.CTkLabel(
            parent,
            text="（多張圖片網格貼圖時每列張數）",
            text_color="gray",
        ).grid(row=r, column=2, padx=(0, 10), pady=8, sticky="w")

    def _build_mapping_tab(self, parent):
        # ---- 上排:實機模式 button (原快捷鍵流程) ----
        live_bar = ctk.CTkFrame(parent, fg_color="transparent")
        live_bar.pack(fill="x", padx=12, pady=(12, 6))
        self.btn_mapping = ctk.CTkButton(
            live_bar,
            text=f"實機模式 — 開啟全域快捷鍵標注 ({HOTKEY.upper()})",
            fg_color=COLOR_GREEN, hover_color=COLOR_GREEN_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
            height=38,
            command=self._toggle_mapping,
        )
        self.btn_mapping.pack(fill="x")
        ctk.CTkLabel(
            live_bar,
            text="(在實際 Word/Excel 視窗操作:於 Excel 點欄位儲存格,在 Word 游標處按快捷鍵插入該欄標籤)",
            font=ctk.CTkFont(size=11), text_color=("#6b7280", "#8b949e"),
        ).pack(anchor="w", pady=(4, 0))

        # ---- 中段:左右對照面板 ----
        main = ctk.CTkFrame(
            parent,
            fg_color=("#fbfbfd", "#0f1115"),
            border_color=("#e5e7eb", "#262b33"),
            border_width=1, corner_radius=10,
        )
        main.pack(fill="both", expand=True, padx=12, pady=8)

        hdr = ctk.CTkFrame(main, fg_color="transparent")
        hdr.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(
            hdr, text="GUI 內標注",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=("#1f2328", "#e6edf3"),
        ).pack(side="left")
        ctk.CTkLabel(
            hdr, text="(直接在範本檔上標,免開 Word/Excel)",
            font=ctk.CTkFont(size=11), text_color=("#6b7280", "#8b949e"),
        ).pack(side="left", padx=(8, 0))
        ctk.CTkButton(
            hdr, text="重新載入", width=84, height=28,
            fg_color="transparent", border_width=1,
            text_color=("#1f2328", "#e6edf3"),
            border_color=("#d0d7de", "#30363d"),
            hover_color=("#eaeef2", "#262b33"),
            command=self._mapping_view_load,
        ).pack(side="right")

        body = ctk.CTkFrame(main, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=10, pady=4)

        # 左:Excel 欄位
        left_box = ctk.CTkFrame(body, fg_color="transparent", width=300)
        left_box.pack(side="left", fill="y", padx=(0, 6))
        left_box.pack_propagate(False)
        ctk.CTkLabel(
            left_box, text="◉ Excel 欄位",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).pack(anchor="w", padx=4, pady=(2, 4))
        self.mapping_view_left = ctk.CTkScrollableFrame(
            left_box, fg_color=("#ffffff", "#161b22"),
            border_color=("#e5e7eb", "#262b33"),
            border_width=1,
        )
        self.mapping_view_left.pack(fill="both", expand=True)

        # 右:Word 段落
        right_box = ctk.CTkFrame(body, fg_color="transparent")
        right_box.pack(side="left", fill="both", expand=True, padx=(6, 0))
        ctk.CTkLabel(
            right_box, text="◉ Word 範本段落  (點選做為 anchor)",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).pack(anchor="w", padx=4, pady=(2, 4))
        self.mapping_view_right = tk.Text(
            right_box, wrap="word",
            borderwidth=1, highlightthickness=0,
            relief="solid",
            background=self._tk_resolve(("#ffffff", "#161b22")),
            foreground=self._tk_resolve(("#1f2328", "#e6edf3")),
            cursor="arrow", padx=10, pady=8,
            font=("Microsoft JhengHei", 11),
        )
        self.mapping_view_right.pack(fill="both", expand=True)
        self.mapping_view_right.bind("<Key>", self._agent_box_block_keys)

        # footer status bar
        footer = ctk.CTkFrame(main, fg_color="transparent")
        footer.pack(fill="x", padx=12, pady=(6, 10))
        self.mapping_view_status = ctk.CTkLabel(
            footer, text="尚未選取 anchor — 在右側 Word 段落點一下選定插入位置",
            font=ctk.CTkFont(size=11),
            text_color=("#6b7280", "#8b949e"),
            anchor="w",
        )
        self.mapping_view_status.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            footer, text="清除選取", width=80, height=26,
            fg_color="transparent", border_width=1,
            text_color=("#6b7280", "#8b949e"),
            border_color=("#d0d7de", "#30363d"),
            command=self._mapping_view_clear_anchor,
        ).pack(side="right")

        # ---- 下排:圖片插入 + 映射歷史 ----
        img_row = ctk.CTkFrame(parent, fg_color="transparent")
        img_row.pack(fill="x", padx=12, pady=(0, 4))
        ctk.CTkButton(
            img_row, text="預覽圖片資料夾",
            command=self._mapping_preview_image_folder, height=30,
            fg_color="transparent", border_width=1,
            text_color=("#1f2328", "#e6edf3"),
            border_color=("#d0d7de", "#30363d"),
            hover_color=("#eaeef2", "#262b33"),
        ).pack(side="left", padx=(0, 4))
        ctk.CTkButton(
            img_row, text="從檔案總管選圖片插入 Word 游標位置",
            command=self._insert_image_at_cursor, height=30,
        ).pack(side="left", fill="x", expand=True, padx=4)
        ctk.CTkButton(
            img_row, text="多選圖片網格貼入",
            command=self._insert_image_grid_at_cursor, height=30,
        ).pack(side="left", fill="x", expand=True, padx=(4, 0))

        hist_card = ctk.CTkFrame(parent, fg_color="transparent")
        hist_card.pack(fill="x", padx=12, pady=(4, 12))
        hist_hdr = ctk.CTkFrame(hist_card, fg_color="transparent")
        hist_hdr.pack(fill="x")
        ctk.CTkLabel(
            hist_hdr, text="映射歷史(最新在上)",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=("#6b7280", "#8b949e"),
            anchor="w",
        ).pack(side="left")
        ctk.CTkButton(
            hist_hdr, text="復原最近", width=80, height=26,
            command=self._undo_last_mapping,
        ).pack(side="right", padx=(4, 0))
        ctk.CTkButton(
            hist_hdr, text="全部復原", width=80, height=26,
            fg_color=COLOR_RED, hover_color="#c0392b",
            command=self._undo_all_mappings,
        ).pack(side="right")
        self.history_box = ctk.CTkTextbox(
            hist_card, height=68, wrap="word",
            font=ctk.CTkFont(family="Consolas", size=11),
            border_width=1, border_color=("#e5e7eb", "#262b33"),
        )
        self.history_box.pack(fill="x", pady=(4, 0))

        # ---- state ----
        self.mapping_view_word_paragraphs = []   # [(idx, text), ...]
        self.mapping_view_anchor_idx = None
        self.mapping_view_anchor_text = None
        self.mapping_view_excel_columns = []
        self.mapping_view_excel_samples = {}

        # 第一次載入
        self.after(120, self._mapping_view_load)

    # ----------------------------------------------------------------
    # Mapping side-by-side helpers
    # ----------------------------------------------------------------

    def _mapping_view_load(self):
        """從目前 settings 讀 Word + Excel,刷新左右兩 pane。"""
        word_path = self.word_path.get()
        excel_path = self.excel_path.get()

        # ---- 右:Word ----
        self._mapping_view_right_clear()
        if not word_path or not os.path.isfile(word_path):
            self._mapping_view_right_show_message(
                "尚未指定 Word 範本(請到「設定」分頁設定路徑)"
            )
        else:
            try:
                styled = self._mapping_view_read_docx_styled(word_path)
                # paragraphs: list of (idx, text, style_name)
                self.mapping_view_word_paragraphs = [
                    (i, t) for i, (t, _) in enumerate(styled)
                ]
                self.mapping_view_word_styles = [s for _, s in styled]
                self._mapping_view_render_right()
            except Exception as e:
                self._mapping_view_right_show_message(f"讀範本失敗: {e}")

        # ---- 左:Excel 欄位 ----
        self._mapping_view_left_clear()
        if not excel_path or not os.path.isfile(excel_path):
            self._mapping_view_left_show_message(
                "尚未指定 Excel\n(請到「設定」分頁)"
            )
        else:
            try:
                # 先抓 sheet names 給切換器
                try:
                    sheet_names = pd.ExcelFile(excel_path).sheet_names
                except Exception:
                    sheet_names = []
                self._mapping_view_sheet_names = sheet_names

                df = pd.read_excel(
                    excel_path,
                    sheet_name=self.sheet_name.get() or 0,
                    header=max(0, self._header_row_int() - 1),
                    nrows=10,
                )
                cols = [str(c) for c in df.columns]
                df.columns = cols
                samples = {}
                for c in cols:
                    try:
                        samples[c] = "" if len(df) == 0 else str(df[c].iloc[0])
                    except Exception:
                        samples[c] = ""
                self.mapping_view_excel_columns = cols
                self.mapping_view_excel_samples = samples
                self._mapping_view_excel_df = df
                self._mapping_view_render_left()
            except Exception as e:
                self._mapping_view_left_show_message(f"讀 Excel 失敗:\n{e}")

        # 嘗試還原 anchor 選取(如果原段落還在)
        if self.mapping_view_anchor_text:
            for idx, p in self.mapping_view_word_paragraphs:
                if self.mapping_view_anchor_text in p:
                    self._mapping_view_select_anchor(idx, p)
                    return
            self._mapping_view_clear_anchor()

    def _mapping_view_right_clear(self):
        try:
            self.mapping_view_right.configure(state="normal")
            self.mapping_view_right.delete("1.0", "end")
        except Exception:
            pass

    def _mapping_view_right_show_message(self, msg):
        self._mapping_view_right_clear()
        self.mapping_view_right.tag_config("muted", foreground="#9aa0a6")
        self.mapping_view_right.insert("end", msg, ("muted",))
        try:
            self.mapping_view_right.configure(state="disabled")
        except Exception:
            pass

    def _mapping_view_read_docx_styled(self, path):
        """讀 docx 段落,連帶每段的 style 名稱。

        回傳 [(text, style_name), ...]。涵蓋 body 段落 + 表格內段落。
        """
        from docx import Document
        doc = Document(path)
        out = []
        def collect(paragraphs):
            for p in paragraphs:
                style = "Normal"
                try:
                    if p.style is not None:
                        style = p.style.name or "Normal"
                except Exception:
                    pass
                out.append((p.text, style))
        collect(doc.paragraphs)
        for tbl in doc.tables:
            for row in tbl.rows:
                for cell in row.cells:
                    collect(cell.paragraphs)
        return out

    def _mapping_view_style_tag_config(self, txt):
        """為 Heading 1/2/3/Title/Normal 設定不同字型。"""
        base = self._tk_resolve(("#1f2328", "#e6edf3"))
        muted = self._tk_resolve(("#6b7280", "#8b949e"))
        family = "Microsoft JhengHei"
        txt.tag_config("style_Title",      font=(family, 16, "bold"), foreground=base, spacing1=10, spacing3=8)
        txt.tag_config("style_Heading 1",  font=(family, 14, "bold"), foreground=base, spacing1=8,  spacing3=4)
        txt.tag_config("style_Heading 2",  font=(family, 12, "bold"), foreground=base, spacing1=6,  spacing3=3)
        txt.tag_config("style_Heading 3",  font=(family, 11, "bold"), foreground=base, spacing1=4,  spacing3=2)
        txt.tag_config("style_Normal",     font=(family, 11),         foreground=base)
        txt.tag_config("style_blank",      font=(family, 11),         foreground=muted)

    def _mapping_view_render_right(self):
        self._mapping_view_right_clear()
        txt = self.mapping_view_right
        self._mapping_view_style_tag_config(txt)

        # Tag 設定:hover / anchor selected / variable highlight
        hover_bg = self._tk_resolve(("#f3f4f6", "#1c2128"))
        anchor_bg = self._tk_resolve(("#dbeafe", "#1e3a8a"))
        anchor_fg = self._tk_resolve(("#1e40af", "#bfdbfe"))
        muted_fg = self._tk_resolve(("#9aa0a6", "#6e7681"))
        var_fg = self._tk_resolve(("#7c3aed", "#a78bfa"))
        drop_target_bg = self._tk_resolve(("#fef3c7", "#3b2e0e"))

        # 記錄每行所屬的 paragraph idx(供 drag-drop 找 drop target)
        self.mapping_view_line_to_para = {}
        styles = getattr(self, "mapping_view_word_styles", []) or []

        for idx, p in self.mapping_view_word_paragraphs:
            tag = f"para_{idx}"
            style_name = styles[idx] if idx < len(styles) else "Normal"
            style_tag = f"style_{style_name}" if style_name in (
                "Title", "Heading 1", "Heading 2", "Heading 3", "Normal"
            ) else "style_Normal"
            if not p:
                style_tag = "style_blank"
            display = p if p else "·"
            line_no = int(txt.index("end-1c").split(".")[0])
            self.mapping_view_line_to_para[line_no] = idx
            txt.insert("end", display + "\n", (tag, style_tag))
            txt.tag_config(tag, background="")
            # interactive
            def on_click(e, i=idx, t=p):
                self._mapping_view_select_anchor(i, t)
            def on_enter(e, t=tag, i=idx):
                if getattr(self, "_mapping_drag_column", None):
                    # 拖拉中:用黃色 drop target 高亮
                    txt.tag_config(t, background=drop_target_bg)
                elif self.mapping_view_anchor_idx is None or t != f"para_{self.mapping_view_anchor_idx}":
                    txt.tag_config(t, background=hover_bg)
            def on_leave(e, t=tag):
                if self.mapping_view_anchor_idx is None or t != f"para_{self.mapping_view_anchor_idx}":
                    txt.tag_config(t, background="")
            txt.tag_bind(tag, "<Button-1>", on_click)
            txt.tag_bind(tag, "<Enter>", on_enter)
            txt.tag_bind(tag, "<Leave>", on_leave)

        # highlight {{ var }} markers inline + 點擊反向高亮對應 Excel 欄位
        import re as _re
        end = txt.index("end-1c")
        text_all = txt.get("1.0", end)
        self._mapping_view_var_ranges = []  # [(start_index, end_index, var_name), ...]
        for m in _re.finditer(r"\{\{\s*([^{}]+?)\s*\}\}", text_all):
            start_idx = self._tk_index_of(text_all, m.start())
            end_idx = self._tk_index_of(text_all, m.end())
            txt.tag_add("md_var", start_idx, end_idx)
            self._mapping_view_var_ranges.append((start_idx, end_idx, m.group(1).strip()))
        txt.tag_config("md_var", foreground=var_fg,
                        font=("Microsoft JhengHei", 11, "bold"),
                        underline=False)
        # 點 var 反向找 Excel 欄
        txt.tag_bind("md_var", "<Button-1>", self._mapping_view_on_var_click)
        txt.tag_bind("md_var", "<Enter>", lambda e: txt.config(cursor="hand2"))
        txt.tag_bind("md_var", "<Leave>", lambda e: txt.config(cursor="arrow"))

        try:
            txt.configure(state="disabled")
        except Exception:
            pass

        self._mapping_view_palette = {
            "anchor_bg": anchor_bg,
            "anchor_fg": anchor_fg,
            "muted_fg": muted_fg,
            "drop_target_bg": drop_target_bg,
        }

    def _tk_index_of(self, text, char_offset):
        """把字串字元 offset 轉成 Tk Text widget 的 line.col 索引。"""
        line = 1
        col = 0
        for i, c in enumerate(text):
            if i == char_offset:
                return f"{line}.{col}"
            if c == "\n":
                line += 1
                col = 0
            else:
                col += 1
        return f"{line}.{col}"

    def _mapping_view_select_anchor(self, idx, text):
        # 清除舊 highlight
        if self.mapping_view_anchor_idx is not None:
            try:
                self.mapping_view_right.tag_config(
                    f"para_{self.mapping_view_anchor_idx}", background=""
                )
            except Exception:
                pass
        # 套新 highlight
        anchor_bg = self._tk_resolve(("#dbeafe", "#1e3a8a"))
        try:
            self.mapping_view_right.tag_config(f"para_{idx}", background=anchor_bg)
        except Exception:
            pass
        self.mapping_view_anchor_idx = idx
        self.mapping_view_anchor_text = text
        short = text if len(text) <= 60 else text[:60] + "…"
        self.mapping_view_status.configure(
            text=f"anchor:「{short}」 — 在左側點欄位的「+ 插入」即會把 {{{{欄位}}}} 寫到此段落後",
            text_color=("#1e40af", "#93c5fd"),
        )

    def _mapping_view_clear_anchor(self):
        if self.mapping_view_anchor_idx is not None:
            try:
                self.mapping_view_right.tag_config(
                    f"para_{self.mapping_view_anchor_idx}", background=""
                )
            except Exception:
                pass
        self.mapping_view_anchor_idx = None
        self.mapping_view_anchor_text = None
        self.mapping_view_status.configure(
            text="尚未選取 anchor — 在右側 Word 段落點一下選定插入位置",
            text_color=("#6b7280", "#8b949e"),
        )

    def _mapping_view_left_clear(self):
        for w in list(self.mapping_view_left.winfo_children()):
            try:
                w.destroy()
            except Exception:
                pass

    def _mapping_view_left_show_message(self, msg):
        self._mapping_view_left_clear()
        ctk.CTkLabel(
            self.mapping_view_left, text=msg,
            text_color=("#9aa0a6", "#6e7681"),
            wraplength=240, justify="left",
        ).pack(padx=10, pady=14)

    def _mapping_view_render_left(self):
        self._mapping_view_left_clear()
        if not self.mapping_view_excel_columns:
            self._mapping_view_left_show_message("Excel 沒有可用欄位")
            return

        # ---- Sheet 切換器(多 sheet 才顯示) ----
        sheet_names = getattr(self, "_mapping_view_sheet_names", []) or []
        if len(sheet_names) > 1:
            sheet_bar = ctk.CTkFrame(self.mapping_view_left, fg_color="transparent")
            sheet_bar.pack(fill="x", padx=4, pady=(4, 2))
            ctk.CTkLabel(
                sheet_bar, text="Sheet:",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=("#6b7280", "#8b949e"),
            ).pack(side="left", padx=(4, 6))
            current = self.sheet_name.get() or sheet_names[0]
            sheet_var = ctk.StringVar(value=current)

            def on_sheet_change(name):
                self.sheet_name.set(name)
                # 同步主 sheet_combo
                try:
                    self.sheet_combo.set(name)
                except Exception:
                    pass
                self._mapping_view_load()

            ctk.CTkOptionMenu(
                sheet_bar,
                values=sheet_names,
                variable=sheet_var,
                command=on_sheet_change,
                width=180, height=28,
                font=ctk.CTkFont(size=11),
            ).pack(side="left")

        # ---- 頂部:資料預覽(Treeview) ----
        df = getattr(self, "_mapping_view_excel_df", None)
        if df is not None and len(df) > 0:
            preview_card = ctk.CTkFrame(
                self.mapping_view_left,
                fg_color=("#ffffff", "#0f1115"),
                corner_radius=6,
            )
            preview_card.pack(fill="x", padx=4, pady=(4, 6))
            ctk.CTkLabel(
                preview_card,
                text=f"資料預覽(前 {min(3, len(df))} 列 · 共 {len(df)} 列)",
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color=("#6b7280", "#8b949e"),
                anchor="w",
            ).pack(anchor="w", padx=8, pady=(6, 2))

            from tkinter import ttk
            # ttk style for dark/light
            style = ttk.Style()
            try:
                style.theme_use("default")
            except Exception:
                pass
            tree_bg = self._tk_resolve(("#ffffff", "#0f1115"))
            tree_fg = self._tk_resolve(("#1f2328", "#e6edf3"))
            head_bg = self._tk_resolve(("#f3f4f6", "#1c2128"))
            sel_bg = self._tk_resolve(("#dbeafe", "#1e3a8a"))
            style.configure("Mapping.Treeview",
                            background=tree_bg, foreground=tree_fg,
                            fieldbackground=tree_bg, borderwidth=0,
                            rowheight=22, font=("Microsoft JhengHei", 10))
            style.configure("Mapping.Treeview.Heading",
                            background=head_bg, foreground=tree_fg,
                            font=("Microsoft JhengHei", 10, "bold"),
                            relief="flat")
            style.map("Mapping.Treeview",
                      background=[("selected", sel_bg)],
                      foreground=[("selected", tree_fg)])

            tree_wrap = ctk.CTkFrame(preview_card, fg_color="transparent")
            tree_wrap.pack(fill="x", padx=4, pady=(0, 6))
            cols = self.mapping_view_excel_columns
            tree = ttk.Treeview(
                tree_wrap, columns=cols, show="headings",
                height=min(3, len(df)), style="Mapping.Treeview",
            )
            for c in cols:
                tree.heading(c, text=c)
                tree.column(c, width=110, anchor="w", stretch=False)
            for _, r in df.head(3).iterrows():
                values = []
                for c in cols:
                    v = r[c]
                    s = "" if v is None else str(v)
                    if len(s) > 22:
                        s = s[:22] + "…"
                    values.append(s)
                tree.insert("", "end", values=values)
            hsb = ttk.Scrollbar(tree_wrap, orient="horizontal", command=tree.xview)
            tree.configure(xscrollcommand=hsb.set)
            tree.grid(row=0, column=0, sticky="nsew")
            hsb.grid(row=1, column=0, sticky="ew")
            tree_wrap.grid_columnconfigure(0, weight=1)

            # 點任一 cell → 高亮 Word 中對應的 {{ 欄位 }}
            tree.bind("<Button-1>",
                       lambda e, t=tree, c=list(cols): self._mapping_view_on_cell_click(e, t, c))
            self._mapping_view_tree = tree

        # ---- 欄位 list(可拖拉 + 點按鈕) ----
        ctk.CTkLabel(
            self.mapping_view_left,
            text="欄位(拖到右側段落,或按「+ 插入」)",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=("#6b7280", "#8b949e"),
            anchor="w",
        ).pack(anchor="w", padx=8, pady=(2, 4))

        self._mapping_view_col_row_frames = {}
        for col in self.mapping_view_excel_columns:
            sample = self.mapping_view_excel_samples.get(col, "")
            if len(sample) > 32:
                sample = sample[:32] + "…"

            row = ctk.CTkFrame(
                self.mapping_view_left,
                fg_color=("#f9fafb", "#1c2128"),
                corner_radius=8,
                cursor="hand2",
            )
            row.pack(fill="x", padx=4, pady=3)
            self._mapping_view_col_row_frames[col] = row

            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True, padx=(10, 4), pady=6)
            name_lbl = ctk.CTkLabel(
                info, text="⋮⋮ " + col,
                font=ctk.CTkFont(size=12, weight="bold"),
                anchor="w",
                text_color=("#1f2328", "#e6edf3"),
                cursor="hand2",
            )
            name_lbl.pack(anchor="w")
            sample_lbl = None
            if sample:
                sample_lbl = ctk.CTkLabel(
                    info, text=f"範例:{sample}",
                    font=ctk.CTkFont(size=10),
                    text_color=("#6b7280", "#8b949e"),
                    anchor="w",
                    cursor="hand2",
                )
                sample_lbl.pack(anchor="w")

            ctk.CTkButton(
                row, text="+ 插入", width=64, height=26,
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color=COLOR_BLUE, hover_color=COLOR_BLUE_HOVER,
                command=lambda c=col: self._mapping_view_insert(c),
            ).pack(side="right", padx=8, pady=6)

            # ---- 綁定拖拉事件(在 row / info / labels 上,但不在 button 上) ----
            for w in (row, info, name_lbl) + ((sample_lbl,) if sample_lbl else ()):
                w.bind("<ButtonPress-1>",  lambda e, c=col: self._mapping_drag_begin(e, c))
                w.bind("<B1-Motion>",      lambda e: self._mapping_drag_move(e))
                w.bind("<ButtonRelease-1>", lambda e: self._mapping_drag_end(e))

    # ----------------------------------------------------------------
    # 圖片資料夾預覽(Toplevel + thumbnail grid)
    # ----------------------------------------------------------------

    def _mapping_preview_image_folder(self, folder=None):
        from app.config import IMAGE_EXTENSIONS

        if folder is None:
            folder = filedialog.askdirectory(title="選圖片資料夾預覽")
            if not folder:
                return
        if not os.path.isdir(folder):
            messagebox.showerror("錯誤", f"資料夾不存在: {folder}")
            return

        files = []
        for name in sorted(os.listdir(folder)):
            if name.lower().endswith(IMAGE_EXTENSIONS):
                files.append(name)
        if not files:
            messagebox.showinfo("資料夾沒有圖片", folder)
            return

        try:
            from PIL import Image as _PImage
        except ImportError:
            messagebox.showerror("需要 Pillow", "請先 pip install Pillow")
            return

        win = ctk.CTkToplevel(self)
        win.title(f"圖片預覽 — {len(files)} 張 — {os.path.basename(folder)}")
        win.geometry("760x560")
        win.transient(self)

        hdr = ctk.CTkFrame(win, fg_color="transparent")
        hdr.pack(fill="x", padx=10, pady=(10, 4))
        ctk.CTkLabel(
            hdr, text=folder,
            font=ctk.CTkFont(size=11),
            text_color=("#6b7280", "#8b949e"),
            anchor="w",
        ).pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            hdr, text=f"{len(files)} 張",
            font=ctk.CTkFont(size=11, weight="bold"),
        ).pack(side="right")

        scroll = ctk.CTkScrollableFrame(win, fg_color=("#fbfbfd", "#0f1115"))
        scroll.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        cols = 4
        thumb_size = (150, 150)

        # 用 Pillow.thumbnail + CTkImage,保 ref 避免 gc
        self._mapping_preview_keep_ref = []

        for i, name in enumerate(files):
            path = os.path.join(folder, name)
            try:
                img = _PImage.open(path).convert("RGB")
                img.thumbnail(thumb_size)
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
            except Exception:
                continue
            self._mapping_preview_keep_ref.append(ctk_img)

            cell = ctk.CTkFrame(
                scroll,
                fg_color=("#ffffff", "#1c2128"),
                border_color=("#e5e7eb", "#262b33"),
                border_width=1,
                corner_radius=8,
            )
            cell.grid(row=i // cols, column=i % cols, padx=6, pady=6, sticky="nsew")
            ctk.CTkLabel(cell, image=ctk_img, text="").pack(padx=6, pady=(8, 4))

            try:
                size_kb = os.path.getsize(path) // 1024
            except Exception:
                size_kb = 0
            ctk.CTkLabel(
                cell, text=name,
                font=ctk.CTkFont(size=11, weight="bold"),
                wraplength=140, justify="center",
            ).pack(padx=4, pady=(0, 1))
            ctk.CTkLabel(
                cell, text=f"{size_kb} KB",
                font=ctk.CTkFont(size=10),
                text_color=("#6b7280", "#8b949e"),
            ).pack(padx=4, pady=(0, 6))

        for c in range(cols):
            scroll.grid_columnconfigure(c, weight=1, uniform="thumb")

    # ----------------------------------------------------------------
    # Word {{ var }} click → 反向高亮 Excel 欄位
    # ----------------------------------------------------------------

    def _mapping_view_on_var_click(self, event):
        """點 Word pane 中的 {{ var }} → 找 Excel 對應欄並 flash 高亮。"""
        txt = self.mapping_view_right
        index = txt.index(f"@{event.x},{event.y}")
        for start, end, name in getattr(self, "_mapping_view_var_ranges", []):
            if txt.compare(start, "<=", index) and txt.compare(index, "<", end):
                self._mapping_view_flash_column(name)
                return "break"
        return None

    def _mapping_view_flash_column(self, var_name):
        """短暫高亮左 pane 對應欄位 row 與 status,自動 scroll 到該 row。"""
        if var_name not in self.mapping_view_excel_columns:
            self.mapping_view_status.configure(
                text=f"Excel 欄位中找不到「{var_name}」(這是 Word 範本獨有的變數)",
                text_color=("#b45309", "#fbbf24"),
            )
            return
        target_row = getattr(self, "_mapping_view_col_row_frames", {}).get(var_name)
        if target_row is None:
            return

        # ---- scroll 到目標 row ----
        try:
            scroll = self.mapping_view_left
            canvas = getattr(scroll, "_parent_canvas", None)
            if canvas is not None:
                scroll.update_idletasks()
                row_y = target_row.winfo_y()
                inner_h = scroll._scrollbar_frame.winfo_height() if hasattr(scroll, "_scrollbar_frame") else canvas.winfo_height()
                # 用 row 在 canvas 上的相對位置算 yview fraction
                inner = scroll
                # 取 inner frame 高度
                bbox = canvas.bbox("all")
                total_h = bbox[3] - bbox[1] if bbox else 1
                if total_h > 0:
                    fraction = max(0.0, min(1.0, (row_y - 20) / total_h))
                    canvas.yview_moveto(fraction)
        except Exception:
            pass

        try:
            orig = target_row.cget("fg_color")
        except Exception:
            orig = ("#f9fafb", "#1c2128")
        try:
            target_row.configure(fg_color=("#fef3c7", "#3b2e0e"),
                                 border_color=("#f59e0b", "#fbbf24"),
                                 border_width=2)
        except Exception:
            pass

        def restore():
            try:
                target_row.configure(fg_color=orig, border_width=0)
            except Exception:
                pass
        self.after(2200, restore)

        self.mapping_view_status.configure(
            text=f"反向找到欄位「{var_name}」(左側已標出)",
            text_color=("#1e40af", "#93c5fd"),
        )

    # ----------------------------------------------------------------
    # Excel cell click → 高亮 Word 對應變數
    # ----------------------------------------------------------------

    def _mapping_view_on_cell_click(self, event, tree, cols):
        """點 Treeview 任一 cell → 抓欄位名 → 在右側 Word 找 {{ 欄位 }} 高亮。"""
        # 找出被點的 column index
        col_id = tree.identify_column(event.x)  # "#1" 等
        if not col_id or not col_id.startswith("#"):
            return
        try:
            col_idx = int(col_id[1:]) - 1
        except ValueError:
            return
        if col_idx < 0 or col_idx >= len(cols):
            return
        col_name = cols[col_idx]
        # 強制更新 cell 選取顯示
        tree.selection_set()
        item = tree.identify_row(event.y)
        if item:
            tree.selection_set(item)
        self._mapping_view_highlight_word_var(col_name)

    def _mapping_view_highlight_word_var(self, var_name):
        """在右側 Word pane 標出所有 {{ var_name }} 並 scroll 到第一個。"""
        txt = self.mapping_view_right
        # 清除舊的 cell-driven highlight
        try:
            txt.tag_remove("cell_var_hi", "1.0", "end")
        except Exception:
            pass

        import re as _re
        text_all = txt.get("1.0", "end-1c")
        pat = _re.compile(r"\{\{\s*" + _re.escape(var_name) + r"\s*\}\}")
        matches = list(pat.finditer(text_all))

        if not matches:
            self.mapping_view_status.configure(
                text=f"Word 範本中找不到 {{{{ {var_name} }}}}(尚未標注此欄位)",
                text_color=("#b45309", "#fbbf24"),
            )
            return

        # 設 tag 顏色(亮黃 + 紅字)
        hi_bg = self._tk_resolve(("#fef08a", "#854d0e"))
        hi_fg = self._tk_resolve(("#92400e", "#fef3c7"))
        txt.tag_config(
            "cell_var_hi",
            background=hi_bg,
            foreground=hi_fg,
            font=("Microsoft JhengHei", 11, "bold"),
        )
        # 蓋過 md_var(同字)的順序:用 raise
        try:
            txt.tag_raise("cell_var_hi")
        except Exception:
            pass

        for m in matches:
            start_idx = self._tk_index_of(text_all, m.start())
            end_idx = self._tk_index_of(text_all, m.end())
            txt.tag_add("cell_var_hi", start_idx, end_idx)

        # scroll 到第一個 match
        first_start = self._tk_index_of(text_all, matches[0].start())
        try:
            txt.see(first_start)
        except Exception:
            pass

        n = len(matches)
        self.mapping_view_status.configure(
            text=f"已高亮 Word 中所有 {{{{ {var_name} }}}} ({n} 處)",
            text_color=("#92400e", "#fde68a"),
        )

    # ----------------------------------------------------------------
    # Drag-drop (column → paragraph)
    # ----------------------------------------------------------------

    def _mapping_drag_begin(self, event, column):
        self._mapping_drag_column = column
        self._mapping_drag_start = (event.x_root, event.y_root)
        self._mapping_drag_started = False  # 真正進入 drag 在 motion 才觸發(避免單擊也觸發)
        # 預先建立 tooltip 但隱藏
        try:
            tip = tk.Toplevel(self)
            tip.overrideredirect(True)
            tip.attributes("-topmost", True)
            tip.attributes("-alpha", 0.92)
            tip.withdraw()
            label = tk.Label(
                tip,
                text=f"⋮⋮  {{ {column} }}",
                bg="#1e40af", fg="#ffffff",
                font=("Microsoft JhengHei", 10, "bold"),
                padx=10, pady=5,
                bd=0,
            )
            label.pack()
            self._mapping_drag_tooltip = tip
        except Exception:
            self._mapping_drag_tooltip = None

    def _mapping_drag_move(self, event):
        col = getattr(self, "_mapping_drag_column", None)
        if not col:
            return
        # 真正進入 drag 的閾值:游標移動超過 4px
        if not self._mapping_drag_started:
            sx, sy = self._mapping_drag_start
            if abs(event.x_root - sx) + abs(event.y_root - sy) >= 4:
                self._mapping_drag_started = True
                tip = self._mapping_drag_tooltip
                if tip:
                    try:
                        tip.deiconify()
                    except Exception:
                        pass
        if not self._mapping_drag_started:
            return
        # 更新 tooltip 位置
        tip = self._mapping_drag_tooltip
        if tip:
            try:
                tip.geometry(f"+{event.x_root + 14}+{event.y_root + 14}")
            except Exception:
                pass
        # 更新 drop target highlight
        self._mapping_drag_update_drop_target(event.x_root, event.y_root)

    def _mapping_drag_update_drop_target(self, x_root, y_root):
        """高亮目前游標下的段落為 drop target。"""
        txt = self.mapping_view_right
        # cursor 是否在 Text widget 內
        widget = self.winfo_containing(x_root, y_root)
        para_idx = None
        if widget is txt:
            try:
                x = x_root - txt.winfo_rootx()
                y = y_root - txt.winfo_rooty()
                index = txt.index(f"@{x},{y}")
                line = int(index.split(".")[0])
                line_map = getattr(self, "mapping_view_line_to_para", {}) or {}
                para_idx = line_map.get(line)
            except Exception:
                pass
        prev = getattr(self, "_mapping_drag_drop_target", None)
        if prev == para_idx:
            return
        # clear previous target highlight
        if prev is not None:
            try:
                if self.mapping_view_anchor_idx == prev:
                    txt.tag_config(f"para_{prev}",
                                    background=self._tk_resolve(("#dbeafe", "#1e3a8a")))
                else:
                    txt.tag_config(f"para_{prev}", background="")
            except Exception:
                pass
        # apply new target highlight
        if para_idx is not None:
            try:
                txt.tag_config(f"para_{para_idx}",
                                background=self._tk_resolve(("#fde68a", "#3b2e0e")))
            except Exception:
                pass
        self._mapping_drag_drop_target = para_idx

    def _mapping_drag_end(self, event):
        col = getattr(self, "_mapping_drag_column", None)
        started = getattr(self, "_mapping_drag_started", False)
        # cleanup tooltip
        tip = getattr(self, "_mapping_drag_tooltip", None)
        if tip:
            try:
                tip.destroy()
            except Exception:
                pass
        self._mapping_drag_tooltip = None
        self._mapping_drag_column = None
        self._mapping_drag_started = False

        # clear any drop-target highlight
        target = getattr(self, "_mapping_drag_drop_target", None)
        if target is not None:
            try:
                if self.mapping_view_anchor_idx == target:
                    self.mapping_view_right.tag_config(
                        f"para_{target}",
                        background=self._tk_resolve(("#dbeafe", "#1e3a8a")),
                    )
                else:
                    self.mapping_view_right.tag_config(f"para_{target}", background="")
            except Exception:
                pass
        self._mapping_drag_drop_target = None

        if not col or not started:
            return  # 單擊 — 不執行 drop

        # 找游標下的段落
        widget = self.winfo_containing(event.x_root, event.y_root)
        if widget is not self.mapping_view_right:
            return
        try:
            x = event.x_root - self.mapping_view_right.winfo_rootx()
            y = event.y_root - self.mapping_view_right.winfo_rooty()
            index = self.mapping_view_right.index(f"@{x},{y}")
            line = int(index.split(".")[0])
            para_idx = (getattr(self, "mapping_view_line_to_para", {}) or {}).get(line)
        except Exception:
            return
        if para_idx is None:
            return
        # 找該段落的文字
        for i, p in self.mapping_view_word_paragraphs:
            if i == para_idx:
                self._mapping_view_select_anchor(i, p)
                self._mapping_view_insert(col)
                return

    def _mapping_view_insert(self, column):
        if not self.mapping_view_anchor_text:
            messagebox.showwarning(
                "請先選 anchor",
                "請先在右側「Word 範本段落」點選一段做為插入位置。",
            )
            return
        word_path = self.word_path.get()
        if not word_path or not os.path.isfile(word_path):
            messagebox.showerror("錯誤", "找不到 Word 範本。")
            return
        from app.agent.template_edit import insert_template_variable
        result = insert_template_variable(
            word_path,
            anchor=self.mapping_view_anchor_text,
            variable=column,
            position="after",
        )
        if "error" in result:
            messagebox.showerror("插入失敗", result["error"])
            return
        anchor_short = self.mapping_view_anchor_text[:30]
        msg = f"GUI: 在「{anchor_short}」後插入 {{{{ {column} }}}}"
        self.mapping_history.append((msg, None))
        self._refresh_history_box()
        self.log(msg)
        self._mapping_view_load()  # reload + re-anchor

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
            command=lambda _v: self._on_provider_changed(),
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

        rubric_header = ctk.CTkFrame(rv, fg_color="transparent")
        rubric_header.grid(row=2, column=0, columnspan=5, padx=10, pady=(8, 2), sticky="ew")
        ctk.CTkLabel(rubric_header, text="評分標準 (rubric)：").pack(side="left")
        ctk.CTkButton(
            rubric_header, text="重置為預設", width=90, command=self._reset_rubric
        ).pack(side="right")

        self.rubric_box = ctk.CTkTextbox(rv, height=140)
        self.rubric_box.grid(row=3, column=0, columnspan=5, padx=10, pady=(0, 10), sticky="ew")
        self.rubric_box.insert("1.0", self.settings["review_rubric"])
        rv.grid_columnconfigure(0, weight=1)

        # 預算上限
        bd = ctk.CTkFrame(scroll)
        bd.pack(fill="x", padx=8, pady=(10, 6))
        ctk.CTkLabel(bd, text="預算上限（本回合）", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, columnspan=4, padx=10, pady=(10, 4), sticky="w"
        )
        ctk.CTkLabel(bd, text="Planner 上限:").grid(row=1, column=0, padx=10, pady=6, sticky="e")
        ctk.CTkEntry(bd, textvariable=self.max_planner_calls, width=70).grid(row=1, column=1, padx=4, pady=6, sticky="w")
        ctk.CTkLabel(bd, text="Reviewer 上限:").grid(row=1, column=2, padx=10, pady=6, sticky="e")
        ctk.CTkEntry(bd, textvariable=self.max_reviewer_calls, width=70).grid(row=1, column=3, padx=4, pady=6, sticky="w")

        self.budget_status_label = ctk.CTkLabel(bd, text="本回合已用：planner 0 / reviewer 0", text_color="gray")
        self.budget_status_label.grid(row=2, column=0, columnspan=3, padx=10, pady=(2, 8), sticky="w")
        ctk.CTkButton(bd, text="重置計數", width=90, command=self._reset_budget).grid(
            row=2, column=3, padx=10, pady=(2, 8)
        )

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

    def _on_provider_changed(self):
        """切換 provider 時自動切換子面板並背景刷新模型清單。"""
        self._show_provider_frame()
        self._refresh_llm_models()

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

    # ---- Budget ----

    def _reset_budget(self):
        self.budget.update_limits(
            planner_limit=self._max_planner_calls_int(),
            reviewer_limit=self._max_reviewer_calls_int(),
        )
        self.budget.reset()
        self._refresh_budget_label()
        self.log("已重置本回合 LLM 預算計數。")

    def _sync_budget_limits(self):
        """把 UI 數值同步到 BudgetTracker，但不重置已用次數。"""
        self.budget.update_limits(
            planner_limit=self._max_planner_calls_int(),
            reviewer_limit=self._max_reviewer_calls_int(),
        )

    def _reset_rubric(self):
        from app.config import DEFAULT_REVIEW_RUBRIC

        self.rubric_box.delete("1.0", "end")
        self.rubric_box.insert("1.0", DEFAULT_REVIEW_RUBRIC)
        self.log("rubric 已還原為預設值。")

    def _refresh_generate_button_state(self):
        """缺路徑時把「開始批次產出報告」按鈕灰階。"""
        if not hasattr(self, "btn_generate"):
            return
        if self.is_generating:
            return  # 取消模式時保持原樣
        ready = bool(self.word_path.get() and self.excel_path.get())
        try:
            if ready:
                self.btn_generate.configure(
                    state="normal",
                    fg_color=COLOR_BLUE,
                    text="開始批次產出報告",
                )
            else:
                self.btn_generate.configure(
                    state="disabled",
                    text="請先到「設定」頁籤指定 Word + Excel 路徑",
                )
        except Exception:
            pass
        self.after(800, self._refresh_generate_button_state)

    def _refresh_budget_label(self):
        s = self.budget.status()
        if hasattr(self, "budget_status_label"):
            self.budget_status_label.configure(
                text=(
                    f"本回合已用：planner {s['planner_used']}/{s['planner_limit']}"
                    f"  reviewer {s['reviewer_used']}/{s['reviewer_limit']}"
                )
            )
        # 每 1.5 秒刷一次（輕量）
        self.after(1500, self._refresh_budget_label)

    # ---- Agent 頁籤 ----

    # 狀態 → (顯示文字, 顏色) 對照
    _AGENT_STATUS_THEMES = {
        "idle":         ("待命",     "#9aa0a6"),
        "thinking":     ("思考中",   "#3b82f6"),
        "calling":      ("執行工具", "#10b981"),
        "waiting_user": ("等候輸入", "#f59e0b"),
        "cancelling":   ("中止中",   "#ef4444"),
    }

    def _build_agent_tab(self, parent):
        # ------- 頂部:狀態 pill + 動作按鈕 -------
        top = ctk.CTkFrame(parent, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(12, 6))

        status_box = ctk.CTkFrame(top, fg_color=("#f1f3f5", "#1e2230"), corner_radius=14)
        status_box.pack(side="left")
        # status dot 用 Canvas 畫一個小圓
        self.agent_status_dot = tk.Canvas(
            status_box, width=10, height=10,
            highlightthickness=0, bd=0, bg=self._tk_resolve(("#f1f3f5", "#1e2230")),
        )
        self.agent_status_dot.create_oval(1, 1, 9, 9, fill="#9aa0a6", outline="")
        self.agent_status_dot.pack(side="left", padx=(10, 6), pady=6)
        self.agent_status = ctk.CTkLabel(
            status_box, text="待命",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#9aa0a6",
        )
        self.agent_status.pack(side="left", padx=(0, 12), pady=4)

        btn_box = ctk.CTkFrame(top, fg_color="transparent")
        btn_box.pack(side="right")
        ctk.CTkButton(
            btn_box, text="新對話", width=84, height=30,
            fg_color="transparent", border_width=1,
            text_color=("#1f2328", "#e6edf3"),
            border_color=("#d0d7de", "#30363d"),
            hover_color=("#eaeef2", "#262b33"),
            command=self._agent_reset,
        ).pack(side="right", padx=4)
        ctk.CTkButton(
            btn_box, text="匯出對話", width=84, height=30,
            fg_color="transparent", border_width=1,
            text_color=("#1f2328", "#e6edf3"),
            border_color=("#d0d7de", "#30363d"),
            hover_color=("#eaeef2", "#262b33"),
            command=self._agent_export_chat,
        ).pack(side="right", padx=4)
        ctk.CTkButton(
            btn_box, text="中止", width=70, height=30,
            fg_color=COLOR_RED, hover_color="#c0392b",
            command=self._agent_cancel,
        ).pack(side="right", padx=4)

        # ------- 對話區:CTkScrollableFrame 容納每則訊息 frame -------
        self.agent_messages = ctk.CTkScrollableFrame(
            parent, fg_color=("#fbfbfd", "#0f1115")
        )
        self.agent_messages.pack(fill="both", expand=True, padx=12, pady=4)

        # ------- 輸入區 -------
        bottom = ctk.CTkFrame(parent, fg_color="transparent")
        bottom.pack(fill="x", padx=12, pady=(6, 12))
        input_wrap = ctk.CTkFrame(
            bottom,
            fg_color=("#ffffff", "#161b22"),
            border_color=("#d0d7de", "#30363d"),
            border_width=1,
            corner_radius=10,
        )
        input_wrap.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.agent_input = ctk.CTkTextbox(
            input_wrap, height=78, wrap="word",
            fg_color="transparent", border_width=0,
        )
        self.agent_input.pack(fill="both", expand=True, padx=8, pady=6)
        self.agent_input.bind("<Control-Return>", lambda _e: (self._agent_send(), "break")[1])
        ctk.CTkLabel(
            bottom, text="Ctrl+Enter\n送出",
            font=ctk.CTkFont(size=10), text_color=("#6b7280", "#8b949e"),
        ).pack(side="right", padx=(0, 6))
        ctk.CTkButton(
            bottom, text="送出 ▸", width=86, height=82,
            fg_color=COLOR_BLUE, hover_color=COLOR_BLUE_HOVER,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._agent_send,
        ).pack(side="right")

        # 內部 markdown renderer cache:每個訊息 bubble 都會建一個獨立 renderer
        self._chat_md_renderers = []

        # 顯示 welcome card
        self._chat_show_welcome()

    # ----------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------

    def _tk_resolve(self, color):
        """customtkinter 顏色 tuple (light, dark) 在 tk widget 用,要解析成單值。"""
        if isinstance(color, (tuple, list)):
            return color[1] if ctk.get_appearance_mode().lower().startswith("dark") else color[0]
        return color

    def _chat_scroll_to_bottom(self):
        try:
            self.agent_messages.update_idletasks()
            canvas = getattr(self.agent_messages, "_parent_canvas", None)
            if canvas:
                canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _chat_clear(self):
        for w in list(self.agent_messages.winfo_children()):
            try:
                w.destroy()
            except Exception:
                pass
        self._chat_md_renderers = []

    # ----------------------------------------------------------------
    # Welcome card
    # ----------------------------------------------------------------

    def _chat_show_welcome(self):
        card = ctk.CTkFrame(
            self.agent_messages,
            fg_color=("#ffffff", "#161b22"),
            border_color=("#e5e7eb", "#262b33"),
            border_width=1,
            corner_radius=14,
        )
        card.pack(fill="x", padx=20, pady=(20, 12))

        ctk.CTkLabel(
            card, text="Agent 已就緒",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=("#1f2328", "#e6edf3"),
        ).pack(anchor="w", padx=22, pady=(20, 4))
        ctk.CTkLabel(
            card,
            text="用一句話描述目標即可。Agent 會自動呼工具、缺資料時跳對話框問你。",
            font=ctk.CTkFont(size=13),
            text_color=("#57606a", "#8b949e"),
            justify="left",
            wraplength=620,
        ).pack(anchor="w", padx=22, pady=(0, 14))

        # 提示卡片(範例 prompt)
        examples = [
            ("把標籤對好", "幫我把 Word 範本的變數對應到 Excel 欄位。"),
            ("全部產出", "依當前設定批次產出所有報告,並啟用審查。"),
            ("圖片貼到範本", "把資料夾裡的圖片依檔名語意貼到 Word 對應段落。"),
        ]
        chip_row = ctk.CTkFrame(card, fg_color="transparent")
        chip_row.pack(fill="x", padx=18, pady=(0, 18))
        for title, prompt in examples:
            chip = ctk.CTkButton(
                chip_row,
                text=title,
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color=("#eef2ff", "#1f2937"),
                hover_color=("#e0e7ff", "#283041"),
                text_color=("#3730a3", "#a5b4fc"),
                border_width=1,
                border_color=("#c7d2fe", "#374151"),
                corner_radius=999,
                width=120, height=30,
                command=lambda p=prompt: self._chat_set_input(p),
            )
            chip.pack(side="left", padx=4, pady=2)

        ctk.CTkLabel(
            card, text="( 按上方範例填入,或直接打字 )",
            font=ctk.CTkFont(size=11),
            text_color=("#9aa0a6", "#6e7681"),
        ).pack(anchor="w", padx=22, pady=(0, 18))

        self._welcome_card = card

    def _chat_set_input(self, text):
        try:
            self.agent_input.delete("1.0", "end")
            self.agent_input.insert("1.0", text)
            self.agent_input.focus_set()
        except Exception:
            pass

    def _chat_dismiss_welcome(self):
        if getattr(self, "_welcome_card", None):
            try:
                self._welcome_card.destroy()
            except Exception:
                pass
            self._welcome_card = None

    # ----------------------------------------------------------------
    # Message bubbles
    # ----------------------------------------------------------------

    def _chat_message_frame(self, role, ts):
        """建立一個訊息容器(header + body)。回傳 body container (供 caller 塞內容)。"""
        outer = ctk.CTkFrame(self.agent_messages, fg_color="transparent")
        outer.pack(fill="x", padx=4, pady=(4, 2))

        # 角色色票
        role_styles = {
            "user":      ("#dbeafe", "#1e3a8a", "你"),
            "assistant": ("#dcfce7", "#14532d", "助理"),
            "system":    ("#fef3c7", "#7c2d12", "系統"),
            "tool":      ("#f3f4f6", "#374151", "工具"),
        }
        light_bg, dark_fg, label = role_styles.get(role, ("#e5e7eb", "#374151", role))

        # header(badge + 時間戳)
        hdr = ctk.CTkFrame(outer, fg_color="transparent")
        hdr.pack(fill="x", padx=4, pady=(0, 2))
        badge_colors = {
            "user":      (("#1e40af"), ("#60a5fa")),
            "assistant": (("#15803d"), ("#86efac")),
            "system":    (("#b45309"), ("#fbbf24")),
            "tool":      (("#4b5563"), ("#9ca3af")),
        }
        bg = badge_colors.get(role, ("#4b5563", "#9ca3af"))
        ctk.CTkLabel(
            hdr, text=label,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=bg,
        ).pack(side="left", padx=(8, 6))
        ctk.CTkLabel(
            hdr, text=ts,
            font=ctk.CTkFont(size=10),
            text_color=("#9aa0a6", "#6e7681"),
        ).pack(side="left")

        # body bubble
        bubble_bg = {
            "user":      ("#eff6ff", "#172033"),
            "assistant": ("#f0fdf4", "#0d1f17"),
            "system":    ("#fffbeb", "#1f1a0d"),
            "tool":      ("#f9fafb", "#161b22"),
        }
        bubble_border = {
            "user":      ("#bfdbfe", "#1e3a8a"),
            "assistant": ("#bbf7d0", "#14532d"),
            "system":    ("#fde68a", "#92400e"),
            "tool":      ("#e5e7eb", "#262b33"),
        }
        bubble = ctk.CTkFrame(
            outer,
            fg_color=bubble_bg.get(role, ("#f3f4f6", "#1e2230")),
            border_color=bubble_border.get(role, ("#e5e7eb", "#374151")),
            border_width=1,
            corner_radius=10,
        )
        bubble.pack(fill="x", padx=4, pady=(0, 0))
        return bubble

    def _chat_add_user(self, text, ts):
        bubble = self._chat_message_frame("user", ts)
        lbl = ctk.CTkLabel(
            bubble, text=text,
            font=ctk.CTkFont(size=13),
            text_color=("#1e293b", "#e6edf3"),
            anchor="w", justify="left",
            wraplength=600,
        )
        lbl.pack(fill="x", padx=14, pady=10)
        self._chat_scroll_to_bottom()

    def _chat_add_assistant_md(self, text, ts):
        bubble = self._chat_message_frame("assistant", ts)
        body = tk.Text(
            bubble, wrap="word", borderwidth=0, highlightthickness=0,
            padx=14, pady=10, height=1, width=10,
            background=self._tk_resolve(("#f0fdf4", "#0d1f17")),
            foreground=self._tk_resolve(("#1f2328", "#e6edf3")),
            cursor="arrow",
        )
        body.pack(fill="x", padx=2, pady=2)
        renderer = MarkdownRenderer(body, base_size=13)
        renderer.render(text)
        self._chat_md_renderers.append(renderer)
        body.update_idletasks()
        try:
            n_lines = int(body.index("end-1c").split(".")[0])
            body.configure(height=max(1, min(80, n_lines + 1)))
        except Exception:
            pass
        # 唯讀:接管 key event
        body.bind("<Key>", self._agent_box_block_keys)
        self._chat_scroll_to_bottom()

    def _chat_add_system(self, text, ts=None):
        bubble = self._chat_message_frame("system", ts or "")
        ctk.CTkLabel(
            bubble, text=text,
            font=ctk.CTkFont(size=12),
            text_color=("#78350f", "#fbbf24"),
            anchor="w", justify="left",
            wraplength=600,
        ).pack(fill="x", padx=14, pady=8)
        self._chat_scroll_to_bottom()

    def _chat_add_tool_call(self, name, args, ts):
        outer = ctk.CTkFrame(self.agent_messages, fg_color="transparent")
        outer.pack(fill="x", padx=12, pady=(2, 0))
        args_str = json.dumps(args, ensure_ascii=False) if args else "{}"
        if len(args_str) > 90:
            args_str = args_str[:90] + "…"
        ctk.CTkLabel(
            outer,
            text=f"▸ 呼叫 {name}({args_str})",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=("#6b7280", "#8b949e"),
            anchor="w",
        ).pack(fill="x", padx=4)
        self._chat_scroll_to_bottom()

    def _chat_add_tool_result(self, name, preview_text, ts):
        outer = ctk.CTkFrame(self.agent_messages, fg_color="transparent")
        outer.pack(fill="x", padx=12, pady=(0, 4))
        preview = preview_text if len(preview_text) <= 240 else preview_text[:240] + "…"
        ctk.CTkLabel(
            outer,
            text=f"  ↳ {preview}",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=("#9ca3af", "#6e7681"),
            anchor="w", justify="left",
            wraplength=620,
        ).pack(fill="x", padx=4)
        self._chat_scroll_to_bottom()

    # ----------------------------------------------------------------
    # Status indicator
    # ----------------------------------------------------------------

    def _agent_set_status(self, text):
        # 找到 theme key
        key = None
        for k in self._AGENT_STATUS_THEMES:
            if text.startswith(k) or k in text:
                key = k
                break
        label, color = self._AGENT_STATUS_THEMES.get(key, (text, "#9aa0a6"))

        def update():
            try:
                self.agent_status.configure(text=label, text_color=color)
                # update dot
                self.agent_status_dot.delete("all")
                self.agent_status_dot.create_oval(1, 1, 9, 9, fill=color, outline="")
            except Exception:
                pass
        self.after(0, update)

    def _agent_box_block_keys(self, event):
        """Read-only Text widget:阻擋打字、放行複製/選取/捲動。"""
        allowed = ("c", "C", "a", "A", "Insert")
        if event.state & 0x4 and event.keysym in allowed:
            return None
        if event.keysym in (
            "Left", "Right", "Up", "Down", "Home", "End",
            "Prior", "Next", "Shift_L", "Shift_R", "Control_L", "Control_R",
        ):
            return None
        return "break"

    # ----------------------------------------------------------------
    # Render incoming agent message
    # ----------------------------------------------------------------

    def _agent_render(self, msg):
        import datetime
        ts = datetime.datetime.now().strftime("%H:%M:%S")

        # 第一則訊息出現時把 welcome card 收掉
        self._chat_dismiss_welcome()

        if msg.role == "user":
            self.agent_chat_log.append({"ts": ts, "kind": "user", "text": msg.text})
            self.after(0, lambda: self._chat_add_user(msg.text, ts))
            return
        if msg.role == "assistant":
            for tc in msg.tool_calls:
                self.agent_chat_log.append({
                    "ts": ts, "kind": "tool_call",
                    "name": tc.name, "args": tc.arguments,
                })
                self.after(0, lambda n=tc.name, a=tc.arguments: self._chat_add_tool_call(n, a, ts))
            if msg.text:
                self.agent_chat_log.append({"ts": ts, "kind": "assistant", "text": msg.text})
                self.after(0, lambda t=msg.text: self._chat_add_assistant_md(t, ts))
            return
        if msg.role == "tool":
            self.agent_chat_log.append({
                "ts": ts, "kind": "tool_result",
                "name": msg.tool_name, "text": msg.text,
            })
            self.after(0, lambda n=msg.tool_name, t=msg.text: self._chat_add_tool_result(n, t, ts))
            return

    def _agent_reset(self):
        if self.agent_thread and self.agent_thread.is_alive():
            self.log("Agent 仍在執行中，請先中止。")
            return
        self.agent_orchestrator = None
        self.agent_chat_log = []
        self.budget.update_limits(
            planner_limit=self._max_planner_calls_int(),
            reviewer_limit=self._max_reviewer_calls_int(),
        )
        self.budget.reset()
        self._refresh_budget_label()
        self._chat_clear()
        self._chat_show_welcome()
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
            self._chat_add_system(
                f"[錯誤] {provider} 不可用：請至「AI 引擎」頁籤檢查 API key / endpoint。"
            )
            return None

        model = self._agent_planner_model()
        if not model:
            self._chat_add_system(
                "[錯誤] 尚未選擇 planner 模型,請至「AI 引擎」頁籤刷新並選定。"
            )
            return None

        ui_context = {
            "word_path": self.word_path.get(),
            "excel_path": self.excel_path.get(),
            "sheet_name": self.sheet_name.get(),
            "header_row": self._header_row_int(),
            "output_dir": self.output_dir.get(),
        }
        # 啟動前同步預算上限到 tracker（不重置已用次數）
        self._sync_budget_limits()
        return AgentOrchestrator(
            llm=client,
            registry=build_default_registry(self.app_context),
            model=model,
            context=ui_context,
            budget=self.budget,
        )

    def _agent_send(self):
        text = self.agent_input.get("1.0", "end").strip()
        if not text:
            return
        if self.agent_thread and self.agent_thread.is_alive():
            self._chat_add_system("[提示] 正在處理中,請稍候。")
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
            self.after(0, lambda err=e: self._chat_add_system(f"[執行錯誤] {err}"))
        finally:
            self._agent_set_status("idle")

    def _agent_export_chat(self):
        if not self.agent_chat_log:
            self.log("沒有對話可匯出。")
            return
        import datetime
        default_name = f"agent_chat_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M')}.md"
        path = filedialog.asksaveasfilename(
            title="匯出對話為 Markdown",
            defaultextension=".md",
            initialfile=default_name,
            filetypes=[("Markdown", "*.md"), ("Text", "*.txt"), ("All Files", "*.*")],
        )
        if not path:
            return
        content = self._format_chat_markdown()
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            self.log(f"對話已匯出至 {_short_path(path)}")
            self._chat_add_system(f"── 對話已匯出至 {path} ──")
        except Exception as e:
            self.log(f"匯出失敗: {e}")

    def _format_chat_markdown(self):
        import datetime
        lines = ["# Agent 對話", ""]
        lines.append(f"匯出時間：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Provider：{self.llm_provider.get()}")
        if self.llm_provider.get() == "Gemini":
            lines.append(f"Planner Model：{self.gemini_planner_model.get() or '(未設)'}")
            lines.append(f"Reviewer Model：{self.gemini_reviewer_model.get() or '(未設)'}")
        else:
            lines.append(f"Endpoint：{self.ollama_endpoint.get()}")
            lines.append(f"Planner Model：{self.ollama_planner_model.get() or '(未設)'}")
            lines.append(f"Reviewer Model：{self.ollama_reviewer_model.get() or '(未設)'}")
        s = self.budget.status()
        lines.append(
            f"預算使用：planner {s['planner_used']}/{s['planner_limit']}，"
            f"reviewer {s['reviewer_used']}/{s['reviewer_limit']}"
        )
        lines.append("")

        for entry in self.agent_chat_log:
            ts = entry.get("ts", "")
            kind = entry["kind"]
            if kind == "user":
                lines.append(f"## [{ts}] 你")
                lines.append(entry.get("text", ""))
            elif kind == "assistant":
                lines.append(f"## [{ts}] 助理")
                lines.append(entry.get("text", ""))
            elif kind == "tool_call":
                args_json = json.dumps(entry.get("args", {}), ensure_ascii=False)
                lines.append(f"### [{ts}] 助理 → 工具呼叫")
                lines.append("```")
                lines.append(f"{entry.get('name','')}({args_json})")
                lines.append("```")
            elif kind == "tool_result":
                lines.append(f"### [{ts}] 工具回傳：{entry.get('name', '?')}")
                lines.append("```json")
                lines.append(entry.get("text", ""))
                lines.append("```")
            lines.append("")
        return "\n".join(lines)

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

    def _max_planner_calls_int(self):
        try:
            return max(1, int(self.max_planner_calls.get()))
        except (ValueError, TypeError):
            return 50

    def _max_reviewer_calls_int(self):
        try:
            return max(1, int(self.max_reviewer_calls.get()))
        except (ValueError, TypeError):
            return 100

    def _on_appearance_changed(self, value):
        try:
            ctk.set_appearance_mode(value)
        except Exception as e:
            self.log(f"切換主題失敗: {e}")

    # ---- 拖拉檔案 ----

    def _on_file_drop(self, event):
        """處理拖入視窗的檔案；依副檔名自動分流。"""
        try:
            paths = self.tk.splitlist(event.data)
        except Exception:
            paths = [event.data]

        routed = []
        for raw in paths:
            # tkdnd 在路徑含空白時會包 {}，需剝除
            p = raw.strip()
            if p.startswith("{") and p.endswith("}"):
                p = p[1:-1]
            if not p:
                continue
            kind = self._route_dropped_path(p)
            if kind:
                routed.append((kind, p))

        if not routed:
            self.log("拖入的檔案沒有可辨識的類型（支援 .docx / .xlsx / 圖片 / 資料夾）。")
            return

        for kind, p in routed:
            self.log(f"拖入 → {kind}: {_short_path(p)}")

    def _route_dropped_path(self, path: str):
        """依副檔名 / 是否目錄分流到對應 Var；回傳路徑類型字串或 None。"""
        if os.path.isdir(path):
            self.output_dir.set(path)
            return "輸出資料夾"

        if not os.path.isfile(path):
            return None

        ext = os.path.splitext(path)[1].lower()
        if ext == ".docx":
            self.word_path.set(path)
            return "Word 範本"
        if ext in (".xlsx", ".xls"):
            self.excel_path.set(path)
            try:
                self._refresh_sheet_list(silent=True)
            except Exception:
                pass
            return "Excel 數據"
        if ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp"):
            # 圖片：不自動寫到 path Var，因為沒有對應欄位；轉到 mapping 流程
            ok, message, rng = OfficeMapper.insert_image_at_cursor(
                path, width_mm=self._image_width_mm_int()
            )
            if ok:
                self.mapping_history.append((f"[圖] {message}", rng))
                self._refresh_history_box()
            else:
                self.log(message)
            return "Word 圖片（已嘗試插入到游標位置）"

        return None

    def _llm_ready(self) -> bool:
        """是否已選好 provider + planner 模型（不檢查 endpoint 是否真的可達）。"""
        provider = self.llm_provider.get()
        if provider == "Gemini":
            if not GEMINI_AVAILABLE:
                return False
            if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
                return False
            return bool(self.gemini_planner_model.get())
        # Ollama
        return bool(self.ollama_planner_model.get())

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
                "max_planner_calls": self._max_planner_calls_int(),
                "max_reviewer_calls": self._max_reviewer_calls_int(),
                "appearance_mode": self.appearance_mode.get(),
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

        # AppContext.generate_reports 會自行設置 is_generating / cancel_event /
        # 並驅動 progress UI；此處只啟動背景緒。
        threading.Thread(target=self._process_files, daemon=True).start()

    def _process_files(self):
        # 啟用審查時，預算上限同步到 tracker
        self._sync_budget_limits()
        self._safe_log("開始讀取數據...")
        try:
            result = self.app_context.generate_reports()
        except Exception as e:
            self._safe_log(f"生成失敗: {e}")
            return

        if "error" in result:
            self._safe_log(f"生成失敗: {result['error']}")
            return

        self._show_completion_summary(result)

    def _show_completion_summary(self, result):
        produced = result.get("produced", 0)
        total = result.get("total", produced)
        cancelled = result.get("cancelled", False)

        parts = [f"產出 {produced}/{total}"]
        if "reviewed" in result:
            parts.append(f"審查 {result['reviewed']} 份")
            failed_count = result.get("failed_count", 0)
            if failed_count > 0:
                parts.append(f"失敗 {failed_count} 份 → {result.get('failed_dir', 'Failed_Reports')}")
            if result.get("review_budget_exhausted"):
                parts.append("（reviewer 預算用盡）")
        if cancelled:
            parts.append("(已取消)")

        msg = "，".join(parts)
        self._safe_log(f"完成：{msg}")
        if not cancelled:
            self.after(0, lambda: messagebox.showinfo("成功", msg))

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
