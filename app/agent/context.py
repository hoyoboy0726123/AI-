"""AppContext：將 AutoReportApp 的 UI 狀態包裝給 agent 工具讀寫。

關鍵：所有 Tk 變數的修改都透過 self._app.after(...) 排程到主執行緒，
agent 工作緒透過 Event 等待完成。避免從背景緒直接動 Tk widget 引發崩潰。
"""

import os
import threading


class AppContext:
    def __init__(self, app):
        self._app = app

    # ---------- 同步主執行緒呼叫 ----------

    def _on_main(self, fn, timeout=10):
        if threading.current_thread() is threading.main_thread():
            return fn()
        result, error, done = [], [], threading.Event()

        def wrap():
            try:
                result.append(fn())
            except Exception as e:
                error.append(e)
            finally:
                done.set()

        self._app.after(0, wrap)
        if not done.wait(timeout=timeout):
            raise RuntimeError("UI 操作逾時。")
        if error:
            raise error[0]
        return result[0] if result else None

    # ---------- 讀取 ----------

    def get_settings(self) -> dict:
        return {
            "word_path": self._app.word_path.get(),
            "excel_path": self._app.excel_path.get(),
            "sheet_name": self._app.sheet_name.get(),
            "header_row": self._app._header_row_int(),
            "output_dir": self._app.output_dir.get(),
            "filename_template": self._app.filename_template.get(),
            "image_width_mm": self._app._image_width_mm_int(),
            "grid_columns": self._app._grid_columns_int(),
        }

    # ---------- 寫入 ----------

    def set_word_path(self, path: str) -> dict:
        if not path:
            return {"error": "未提供路徑"}
        if not os.path.isfile(path):
            return {"error": f"檔案不存在: {path}"}
        if not path.lower().endswith(".docx"):
            return {"error": "Word 範本必須是 .docx"}
        self._on_main(lambda: self._app.word_path.set(path))
        return {"ok": True, "value": path}

    def set_excel_path(self, path: str) -> dict:
        if not path:
            return {"error": "未提供路徑"}
        if not os.path.isfile(path):
            return {"error": f"檔案不存在: {path}"}
        if not path.lower().endswith((".xlsx", ".xls")):
            return {"error": "Excel 必須是 .xlsx 或 .xls"}

        def update():
            self._app.excel_path.set(path)
            try:
                self._app._refresh_sheet_list(silent=True)
            except Exception:
                pass

        self._on_main(update)
        return {"ok": True, "value": path}

    def set_sheet_name(self, name: str) -> dict:
        self._on_main(lambda: self._app.sheet_name.set(name or ""))
        return {"ok": True, "value": name or ""}

    def set_header_row(self, row) -> dict:
        try:
            r = max(1, int(row))
        except (TypeError, ValueError):
            return {"error": "row 必須是正整數"}
        self._on_main(lambda: self._app.header_row.set(str(r)))
        return {"ok": True, "value": r}

    def set_output_dir(self, path: str) -> dict:
        if not path:
            return {"error": "未提供路徑"}
        self._on_main(lambda: self._app.output_dir.set(path))
        return {"ok": True, "value": path}

    def set_filename_template(self, template: str) -> dict:
        if not template:
            return {"error": "模板不可為空"}
        self._on_main(lambda: self._app.filename_template.set(template))
        return {"ok": True, "value": template}

    def set_image_width_mm(self, value) -> dict:
        try:
            v = max(1, int(float(value)))
        except (TypeError, ValueError):
            return {"error": "value 必須是正整數（mm）"}
        self._on_main(lambda: self._app.image_width_mm.set(str(v)))
        return {"ok": True, "value": v}

    # ---------- 操作 ----------

    def _build_generator(self):
        from app.generator import ReportGenerator
        return ReportGenerator(
            word_path=self._app.word_path.get(),
            excel_path=self._app.excel_path.get(),
            output_dir=self._app.output_dir.get(),
            sheet_name=self._app.sheet_name.get() or None,
            header_row=self._app._header_row_int(),
            filename_template=self._app.filename_template.get(),
            image_width_mm=self._app._image_width_mm_int(),
        )

    def validate_template(self) -> dict:
        if not self._app.word_path.get() or not self._app.excel_path.get():
            return {"error": "請先設定 Word 與 Excel 路徑"}
        try:
            missing, extra = self._build_generator().validate()
        except Exception as e:
            return {"error": str(e)}
        return {
            "missing_in_excel": sorted(missing),
            "extra_in_excel": sorted(extra),
            "passed": not missing,
        }

    def generate_reports(self) -> dict:
        if self._app.is_generating:
            return {"error": "已有生成任務在執行中"}
        if not self._app.word_path.get() or not self._app.excel_path.get():
            return {"error": "請先設定 Word 與 Excel 路徑"}

        cancel_event = threading.Event()
        self._app.cancel_event = cancel_event
        self._app.is_generating = True

        from app.config import COLOR_RED

        def start_ui():
            try:
                self._app.btn_generate.configure(text="取消產出", fg_color=COLOR_RED)
                self._app.progress.set(0)
                self._app.progress_label.configure(text="準備中...")
            except Exception:
                pass

        self._app.after(0, start_ui)

        def progress_ui(current, total):
            ratio = current / total if total else 0

            def update():
                try:
                    self._app.progress.set(ratio)
                    self._app.progress_label.configure(text=f"進度 {current}/{total}")
                except Exception:
                    pass

            self._app.after(0, update)

        try:
            generator = self._build_generator()
            produced, total = generator.generate(
                progress_callback=progress_ui,
                cancel_event=cancel_event,
            )
        except Exception as e:
            return {"error": str(e)}
        finally:
            self._app.is_generating = False
            self._app.after(0, self._app._reset_generation_ui)

        return {
            "produced": produced,
            "total": total,
            "output_dir": self._app.output_dir.get(),
            "cancelled": cancel_event.is_set(),
        }

    def open_output_folder(self) -> dict:
        from app.ui import open_folder

        path = self._app.output_dir.get()
        if not path:
            return {"error": "尚未設定輸出資料夾"}
        os.makedirs(path, exist_ok=True)
        ok = open_folder(path)
        return {"ok": ok, "path": path}
