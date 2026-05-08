import customtkinter as ctk
from tkinter import filedialog, messagebox
import win32com.client
import threading
import keyboard
import pandas as pd
from docxtpl import DocxTemplate
import os

# 設定介面風格
ctk.set_appearance_mode("System")  # 自動偵測系統深色/淺色模式
ctk.set_default_color_theme("blue")

class AutoReportApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AI 辦公自動化 - 視覺化映射工具 v1.0")
        self.geometry("600x520")

        # 變數儲存
        self.word_path = ctk.StringVar()
        self.excel_path = ctk.StringVar()
        self.mapping_active = False

        self.setup_ui()

    def setup_ui(self):
        # 標題
        self.label_title = ctk.CTkLabel(self, text="Office 視覺化對應與自動生成系統", font=ctk.CTkFont(size=20, weight="bold"))
        self.label_title.pack(pady=20)

        # 檔案選取區域
        self.frame_files = ctk.CTkFrame(self)
        self.frame_files.pack(pady=10, padx=20, fill="x")

        # Word 範本選取
        ctk.CTkLabel(self.frame_files, text="Word 報告範本:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        ctk.CTkEntry(self.frame_files, textvariable=self.word_path, width=300).grid(row=0, column=1, padx=10, pady=10)
        ctk.CTkButton(self.frame_files, text="選取", width=80, command=self.select_word).grid(row=0, column=2, padx=10, pady=10)

        # Excel 數據選取
        ctk.CTkLabel(self.frame_files, text="Excel 數據源:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        ctk.CTkEntry(self.frame_files, textvariable=self.excel_path, width=300).grid(row=1, column=1, padx=10, pady=10)
        ctk.CTkButton(self.frame_files, text="選取", width=80, command=self.select_excel).grid(row=1, column=2, padx=10, pady=10)

        # 控制區域
        self.frame_control = ctk.CTkFrame(self)
        self.frame_control.pack(pady=20, padx=20, fill="both", expand=True)

        self.btn_mapping = ctk.CTkButton(self.frame_control, text="開啟標籤映射模式 (Ctrl+Shift+M)",
                                        fg_color="#2ecc71", hover_color="#27ae60",
                                        command=self.toggle_mapping_mode)
        self.btn_mapping.pack(pady=15, padx=20, fill="x")

        self.btn_generate = ctk.CTkButton(self.frame_control, text="開始執行批次產出報告",
                                         fg_color="#3498db", hover_color="#2980b9",
                                         command=self.run_generation)
        self.btn_generate.pack(pady=15, padx=20, fill="x")

        # 狀態紀錄區
        self.log_box = ctk.CTkTextbox(self.frame_control, height=100)
        self.log_box.pack(pady=10, padx=20, fill="both", expand=True)
        self.log_message("系統準備就緒。")

    # --- 功能邏輯 ---

    def log_message(self, msg):
        self.log_box.insert("end", f"> {msg}\n")
        self.log_box.see("end")

    def select_word(self):
        path = filedialog.askopenfilename(filetypes=[("Word Files", "*.docx")])
        self.word_path.set(path)

    def select_excel(self):
        path = filedialog.askopenfilename(filetypes=[("Excel Files", "*.xlsx")])
        self.excel_path.set(path)

    def toggle_mapping_mode(self):
        if not self.mapping_active:
            self.mapping_active = True
            self.btn_mapping.configure(text="映射模式運作中... (按 Ctrl+Shift+M 標註)", fg_color="#e74c3c")
            self.log_message("映射模式啟動！請回到 Word 與 Excel 操作。")
            # 開啟監聽執行緒
            threading.Thread(target=self.start_hotkey_listener, daemon=True).start()
        else:
            self.mapping_active = False
            self.btn_mapping.configure(text="開啟標籤映射模式 (Ctrl+Shift+M)", fg_color="#2ecc71")
            self.log_message("映射模式已關閉。")

    def start_hotkey_listener(self):
        # 註冊快捷鍵
        keyboard.add_hotkey('ctrl+shift+m', self.do_mapping)
        while self.mapping_active:
            time.sleep(0.1)
        keyboard.remove_hotkey('ctrl+shift+m')

    def do_mapping(self):
        try:
            word = win32com.client.GetActiveObject("Word.Application")
            excel = win32com.client.GetActiveObject("Excel.Application")

            selected_cell = excel.Selection
            col_index = selected_cell.Column
            tag_name = excel.ActiveSheet.Cells(1, col_index).Value

            if tag_name:
                word.Selection.TypeText(f"{{{{ {tag_name} }}}}")
                self.log_message(f"映射成功: {tag_name}")
        except Exception as e:
            self.log_message(f"連線失敗: 確保檔案已開啟。")

    def run_generation(self):
        w_path = self.word_path.get()
        e_path = self.excel_path.get()

        if not w_path or not e_path:
            messagebox.showwarning("警告", "請先選取範本與數據檔案！")
            return

        threading.Thread(target=self.process_files, args=(w_path, e_path), daemon=True).start()

    def process_files(self, w_path, e_path):
        try:
            self.log_message("開始讀取數據...")
            df = pd.read_excel(e_path)
            output_dir = "Generated_Reports"
            if not os.path.exists(output_dir): os.makedirs(output_dir)

            for index, row in df.iterrows():
                doc = DocxTemplate(w_path)
                doc.render(row.to_dict())
                doc.save(f"{output_dir}/報告_{index+1}.docx")
                self.log_message(f"進度: {index+1}/{len(df)}")

            self.log_message(f"完成！檔案儲存於 {output_dir}")
            messagebox.showinfo("成功", f"已產出 {len(df)} 份報告！")
        except Exception as e:
            self.log_message(f"生成失敗: {str(e)}")

import time
if __name__ == "__main__":
    app = AutoReportApp()
    app.mainloop()
