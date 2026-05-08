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

    def _progress_ui(self, current, total):
        ratio = current / total if total else 0

        def update():
            try:
                self._app.progress.set(ratio)
                self._app.progress_label.configure(text=f"進度 {current}/{total}")
            except Exception:
                pass

        self._app.after(0, update)

    def _start_generation_ui(self):
        from app.config import COLOR_RED

        def start_ui():
            try:
                self._app.btn_generate.configure(text="取消產出", fg_color=COLOR_RED)
                self._app.progress.set(0)
                self._app.progress_label.configure(text="準備中...")
            except Exception:
                pass

        self._app.after(0, start_ui)

    def _build_reviewer_client(self):
        """回傳 (client, model, error_or_None)。"""
        provider = self._app.llm_provider.get()
        if provider == "Gemini":
            from app.agent.llm import GeminiClient
            client = GeminiClient()
            model = self._app.gemini_reviewer_model.get()
        else:
            from app.agent.llm import OllamaClient
            client = OllamaClient(endpoint=self._app.ollama_endpoint.get())
            model = self._app.ollama_reviewer_model.get()

        if not client.is_available():
            return client, model, f"{provider} reviewer 不可用（檢查 API key / endpoint）"
        if not model:
            return client, model, f"未選 {provider} reviewer 模型（請至 AI 引擎頁籤選定）"
        return client, model, None

    def generate_reports(self) -> dict:
        if self._app.is_generating:
            return {"error": "已有生成任務在執行中"}
        if not self._app.word_path.get() or not self._app.excel_path.get():
            return {"error": "請先設定 Word 與 Excel 路徑"}

        cancel_event = threading.Event()
        self._app.cancel_event = cancel_event
        self._app.is_generating = True
        self._start_generation_ui()

        enable_review = bool(self._app.enable_review.get())

        try:
            if enable_review:
                return self._generate_with_review_loop(cancel_event)
            return self._generate_simple_loop(cancel_event)
        except Exception as e:
            return {"error": str(e)}
        finally:
            self._app.is_generating = False
            self._app.after(0, self._app._reset_generation_ui)

    def _generate_simple_loop(self, cancel_event) -> dict:
        generator = self._build_generator()
        produced, total = generator.generate(
            progress_callback=self._progress_ui,
            cancel_event=cancel_event,
        )
        return {
            "produced": produced,
            "total": total,
            "output_dir": self._app.output_dir.get(),
            "cancelled": cancel_event.is_set(),
        }

    def _generate_with_review_loop(self, cancel_event) -> dict:
        import random

        from app.agent.reviewer import move_to_failed_reports, review_report
        from app.config import FAILED_REPORTS_DIR

        vlm, model, err = self._build_reviewer_client()
        if err:
            return {"error": err}

        rubric = ""
        try:
            rubric = self._app.rubric_box.get("1.0", "end").rstrip()
        except Exception:
            pass
        sampling = self._app._review_sampling_int()

        # Failed_Reports/ 與 output_dir 同一層（皆相對於 cwd）
        output_dir = self._app.output_dir.get() or "."
        if os.path.isabs(output_dir):
            failed_dir = os.path.join(os.path.dirname(output_dir), FAILED_REPORTS_DIR)
        else:
            failed_dir = FAILED_REPORTS_DIR

        generator = self._build_generator()
        produced = 0
        total = 0
        reviewed = 0
        failed = []  # list of {index, path, score, issues}

        for prod, tot, saved_path, row_dict in generator.generate_iter(cancel_event=cancel_event):
            produced = prod
            total = tot
            self._progress_ui(produced, total)

            if random.random() * 100 > sampling:
                continue

            result = review_report(
                vlm,
                saved_path,
                row_dict,
                rubric,
                model,
                max_pages=4,
            )
            reviewed += 1

            if "error" in result:
                # reviewer 自身錯誤：不算 failed，繼續
                continue

            if not result.get("passed"):
                try:
                    target = move_to_failed_reports(saved_path, failed_dir)
                except Exception as e:
                    target = saved_path  # fallback to original
                failed.append(
                    {
                        "index": prod,
                        "path": target,
                        "score": result.get("score", 0),
                        "issues": result.get("issues", [])[:5],
                    }
                )

        return {
            "produced": produced,
            "total": total,
            "reviewed": reviewed,
            "failed_count": len(failed),
            "failed": failed[:10],  # 控制回傳大小
            "output_dir": self._app.output_dir.get(),
            "failed_dir": failed_dir,
            "cancelled": cancel_event.is_set(),
        }

    def review_single_docx(self, docx_path: str, row_context_json: str = "") -> dict:
        """單獨審查任一 docx，回傳 reviewer 結果。"""
        if not docx_path:
            return {"error": "未提供 docx_path"}
        if not os.path.isfile(docx_path):
            return {"error": f"檔案不存在: {docx_path}"}
        if not docx_path.lower().endswith(".docx"):
            return {"error": "必須是 .docx 檔"}

        vlm, model, err = self._build_reviewer_client()
        if err:
            return {"error": err}

        rubric = ""
        try:
            rubric = self._app.rubric_box.get("1.0", "end").rstrip()
        except Exception:
            pass

        row_context = {}
        if row_context_json:
            try:
                import json as _json
                row_context = _json.loads(row_context_json)
                if not isinstance(row_context, dict):
                    row_context = {"data": row_context}
            except Exception:
                row_context = {"raw": row_context_json}

        from app.agent.reviewer import review_report
        return review_report(vlm, docx_path, row_context, rubric, model, max_pages=4)

    def open_output_folder(self) -> dict:
        from app.ui import open_folder

        path = self._app.output_dir.get()
        if not path:
            return {"error": "尚未設定輸出資料夾"}
        os.makedirs(path, exist_ok=True)
        ok = open_folder(path)
        return {"ok": ok, "path": path}

    # ---------- 渲染 (P5: docx → image) ----------

    def render_docx_pages(self, docx_path: str, dpi: int = 150, max_pages: int = 0) -> dict:
        """把 docx 渲染成每頁一張 PNG，回傳 list of {page, path}。

        失敗（未安裝 pymupdf / Word COM 失敗 / 檔案問題）統一以 dict 回傳 error。
        """
        from app.agent.docx_render import docx_to_images

        if not docx_path:
            return {"error": "未提供 docx 路徑"}
        if not os.path.isfile(docx_path):
            return {"error": f"檔案不存在: {docx_path}"}
        if not docx_path.lower().endswith(".docx"):
            return {"error": "必須是 .docx 檔"}

        try:
            d = max(72, int(dpi or 150))
        except (TypeError, ValueError):
            d = 150
        try:
            mp = max(0, int(max_pages or 0))
        except (TypeError, ValueError):
            mp = 0

        try:
            pages = docx_to_images(docx_path, dpi=d, max_pages=mp)
        except FileNotFoundError as e:
            return {"error": f"檔案不存在: {e}"}
        except Exception as e:
            return {"error": str(e)}

        if not pages:
            return {"error": "未渲染出任何頁面"}

        output_dir = os.path.dirname(pages[0][1])
        return {
            "pages": [{"page": p, "path": path} for p, path in pages],
            "output_dir": output_dir,
            "page_count": len(pages),
        }

    # ---------- 互動 (P4: human-in-the-loop) ----------

    def _is_cancelled(self) -> bool:
        orch = getattr(self._app, "agent_orchestrator", None)
        if orch is None:
            return False
        ev = getattr(orch, "_cancel", None)
        return bool(ev and ev.is_set())

    def _set_status(self, text):
        try:
            self._app._agent_set_status(text)
        except Exception:
            pass

    def ask_user(self, question: str, choices=None) -> dict:
        """以對話框向使用者詢問，阻塞直到使用者回覆或取消。"""
        if not question:
            return {"error": "question 不可為空"}

        import customtkinter as ctk
        from app.agent.dialogs import ChoiceDialog

        self._set_status("waiting_user")
        state = {"answer": None, "dialog": None, "error": None}
        done = threading.Event()

        def show():
            if self._is_cancelled():
                done.set()
                return
            try:
                if choices:
                    dlg = ChoiceDialog(self._app, question, list(choices))
                    state["dialog"] = dlg
                    state["answer"] = dlg.get_input()
                else:
                    dlg = ctk.CTkInputDialog(text=question, title="Agent 詢問")
                    state["dialog"] = dlg
                    state["answer"] = dlg.get_input()
            except Exception as e:
                state["error"] = str(e)
            finally:
                done.set()

        self._app.after(0, show)

        try:
            while not done.wait(timeout=0.3):
                if self._is_cancelled():
                    dlg = state.get("dialog")
                    if dlg is not None:
                        try:
                            self._app.after(0, dlg.destroy)
                        except Exception:
                            pass
                    return {"cancelled": True}
        finally:
            self._set_status("thinking")

        if state["error"]:
            return {"error": state["error"]}
        ans = state["answer"]
        if ans is None or ans == "":
            return {"cancelled": True}
        return {"answer": ans}

    def request_file(self, prompt: str, kind: str = "any") -> dict:
        """開啟檔案 / 資料夾選取對話框，回傳路徑或 cancelled。"""
        from tkinter import filedialog

        self._set_status("waiting_user")
        state = {"path": None}
        done = threading.Event()

        def show():
            if self._is_cancelled():
                done.set()
                return
            try:
                if kind == "directory":
                    p = filedialog.askdirectory(title=prompt or "選取資料夾")
                elif kind == "word":
                    p = filedialog.askopenfilename(
                        title=prompt or "選取 Word 範本",
                        filetypes=[("Word", "*.docx")],
                    )
                elif kind == "excel":
                    p = filedialog.askopenfilename(
                        title=prompt or "選取 Excel 數據",
                        filetypes=[("Excel", "*.xlsx *.xls")],
                    )
                elif kind == "image":
                    p = filedialog.askopenfilename(
                        title=prompt or "選取圖片",
                        filetypes=[
                            ("Image", "*.png *.jpg *.jpeg *.gif *.bmp"),
                            ("All Files", "*.*"),
                        ],
                    )
                else:
                    p = filedialog.askopenfilename(title=prompt or "選取檔案")
                state["path"] = p
            finally:
                done.set()

        self._app.after(0, show)

        try:
            while not done.wait(timeout=0.3):
                if self._is_cancelled():
                    return {"cancelled": True}
        finally:
            self._set_status("thinking")

        p = state.get("path")
        if not p:
            return {"cancelled": True}
        return {"path": p}
