"""Agent-flow 對話框。

P4 提供兩種：
- ChoiceDialog：模擬單選題（CTkInputDialog 只能輸入文字，無法選擇）
- 檔案選取則使用 tkinter.filedialog 內建對話框

所有 dialog 都在 Tk 主執行緒被建立與顯示；agent 工作緒透過 Event 等待結果。
"""

import customtkinter as ctk


class ChoiceDialog(ctk.CTkToplevel):
    """模擬選擇題對話框（單選 radio）。

    使用方式同 CTkInputDialog：
        d = ChoiceDialog(parent, "問題？", ["A", "B", "C"])
        answer = d.get_input()  # 回傳選定字串；按取消或關閉回 None
    """

    def __init__(self, parent, question, choices, title="Agent 詢問"):
        super().__init__(parent)
        self.title(title)
        self.geometry("420x340")
        self.transient(parent)
        try:
            self.grab_set()
        except Exception:
            pass

        self.result = None
        self._choices = list(choices)

        ctk.CTkLabel(
            self, text=question, wraplength=400, justify="left"
        ).pack(pady=(15, 8), padx=15, anchor="w")

        body = ctk.CTkScrollableFrame(self)
        body.pack(fill="both", expand=True, padx=15, pady=4)

        self.var = ctk.StringVar(value=self._choices[0] if self._choices else "")
        for choice in self._choices:
            ctk.CTkRadioButton(
                body, text=choice, variable=self.var, value=choice
            ).pack(anchor="w", padx=8, pady=4)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(side="bottom", pady=12)
        ctk.CTkButton(btn_frame, text="確認", width=90, command=self._ok).pack(side="left", padx=6)
        ctk.CTkButton(btn_frame, text="取消", width=90, command=self._cancel).pack(side="left", padx=6)

        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _ok(self):
        self.result = self.var.get()
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()

    def get_input(self):
        self.wait_window()
        return self.result
