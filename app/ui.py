"""主視窗 GUI（customtkinter）。"""

import threading
from tkinter import filedialog, messagebox

import customtkinter as ctk

from app.config import (
    APPEARANCE_MODE,
    COLOR_BLUE,
    COLOR_BLUE_HOVER,
    COLOR_GREEN,
    COLOR_GREEN_HOVER,
    COLOR_RED,
    COLOR_THEME,
    HOTKEY,
    OUTPUT_DIR,
    WINDOW_HEADER,
    WINDOW_SIZE,
    WINDOW_TITLE,
)
from app.generator import ReportGenerator
from app.hotkey import HotkeyManager
from app.mapper import OfficeMapper

ctk.set_appearance_mode(APPEARANCE_MODE)
ctk.set_default_color_theme(COLOR_THEME)


class AutoReportApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(WINDOW_TITLE)
        self.geometry(WINDOW_SIZE)

        self.word_path = ctk.StringVar()
        self.excel_path = ctk.StringVar()
        self.mapping_active = False

        self.hotkey_manager = HotkeyManager(HOTKEY, self._on_hotkey)

        self._build_ui()

    def _build_ui(self):
        ctk.CTkLabel(
            self,
            text=WINDOW_HEADER,
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(pady=20)

        files = ctk.CTkFrame(self)
        files.pack(pady=10, padx=20, fill="x")

        ctk.CTkLabel(files, text="Word 報告範本:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        ctk.CTkEntry(files, textvariable=self.word_path, width=300).grid(row=0, column=1, padx=10, pady=10)
        ctk.CTkButton(files, text="選取", width=80, command=self._select_word).grid(row=0, column=2, padx=10, pady=10)

        ctk.CTkLabel(files, text="Excel 數據源:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        ctk.CTkEntry(files, textvariable=self.excel_path, width=300).grid(row=1, column=1, padx=10, pady=10)
        ctk.CTkButton(files, text="選取", width=80, command=self._select_excel).grid(row=1, column=2, padx=10, pady=10)

        control = ctk.CTkFrame(self)
        control.pack(pady=20, padx=20, fill="both", expand=True)

        self.btn_mapping = ctk.CTkButton(
            control,
            text=f"開啟標籤映射模式 ({HOTKEY.upper()})",
            fg_color=COLOR_GREEN,
            hover_color=COLOR_GREEN_HOVER,
            command=self._toggle_mapping,
        )
        self.btn_mapping.pack(pady=15, padx=20, fill="x")

        ctk.CTkButton(
            control,
            text="開始執行批次產出報告",
            fg_color=COLOR_BLUE,
            hover_color=COLOR_BLUE_HOVER,
            command=self._run_generation,
        ).pack(pady=15, padx=20, fill="x")

        self.log_box = ctk.CTkTextbox(control, height=100)
        self.log_box.pack(pady=10, padx=20, fill="both", expand=True)
        self.log("系統準備就緒。")

    # ---- helpers ----

    def log(self, msg):
        self.log_box.insert("end", f"> {msg}\n")
        self.log_box.see("end")

    def _select_word(self):
        path = filedialog.askopenfilename(filetypes=[("Word Files", "*.docx")])
        if path:
            self.word_path.set(path)

    def _select_excel(self):
        path = filedialog.askopenfilename(filetypes=[("Excel Files", "*.xlsx")])
        if path:
            self.excel_path.set(path)

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
        success, message = OfficeMapper.insert_tag_at_cursor()
        if success:
            self.log(f"映射成功: {message}")
        else:
            self.log(message)

    # ---- batch generation ----

    def _run_generation(self):
        w_path = self.word_path.get()
        e_path = self.excel_path.get()

        if not w_path or not e_path:
            messagebox.showwarning("警告", "請先選取範本與數據檔案！")
            return

        threading.Thread(
            target=self._process_files,
            args=(w_path, e_path),
            daemon=True,
        ).start()

    def _process_files(self, w_path, e_path):
        try:
            self.log("開始讀取數據...")
            generator = ReportGenerator(w_path, e_path)
            count = generator.generate(
                progress_callback=lambda i, total: self.log(f"進度: {i}/{total}"),
            )
            self.log(f"完成！檔案儲存於 {OUTPUT_DIR}")
            messagebox.showinfo("成功", f"已產出 {count} 份報告！")
        except Exception as e:
            self.log(f"生成失敗: {e}")
