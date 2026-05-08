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
                pct = int(ratio * 100)
                self._app.progress_label.configure(
                    text=f"進度 {current}/{total} ({pct}%)"
                )
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

    def _build_planner_client(self):
        """回傳 (client, model, error_or_None)。"""
        provider = self._app.llm_provider.get()
        if provider == "Gemini":
            from app.agent.llm import GeminiClient
            client = GeminiClient()
            model = self._app.gemini_planner_model.get()
        else:
            from app.agent.llm import OllamaClient
            client = OllamaClient(endpoint=self._app.ollama_endpoint.get())
            model = self._app.ollama_planner_model.get()

        if not client.is_available():
            return client, model, f"{provider} planner 不可用（檢查 API key / endpoint）"
        if not model:
            return client, model, f"未選 {provider} planner 模型（請至 AI 引擎頁籤選定）"
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

        budget = getattr(self._app, "budget", None)
        budget_exhausted = False

        for prod, tot, saved_path, row_dict in generator.generate_iter(cancel_event=cancel_event):
            produced = prod
            total = tot
            self._progress_ui(produced, total)

            if random.random() * 100 > sampling:
                continue

            if budget is not None and not budget.can_use_reviewer():
                budget_exhausted = True
                # 預算到頂後，剩下的 docx 仍會繼續產出但不再 review
                continue

            result = review_report(
                vlm,
                saved_path,
                row_dict,
                rubric,
                model,
                max_pages=4,
            )
            if budget is not None:
                budget.use_reviewer()
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

        result_dict = {
            "produced": produced,
            "total": total,
            "reviewed": reviewed,
            "failed_count": len(failed),
            "failed": failed[:10],  # 控制回傳大小
            "output_dir": self._app.output_dir.get(),
            "failed_dir": failed_dir,
            "cancelled": cancel_event.is_set(),
        }
        if budget_exhausted:
            result_dict["review_budget_exhausted"] = True
            result_dict["note"] = (
                f"reviewer 預算已用完（{budget.reviewer_limit}）；"
                f"後續 {produced - reviewed} 份未審查"
            )
        return result_dict

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

        budget = getattr(self._app, "budget", None)
        if budget is not None and not budget.can_use_reviewer():
            return {"error": f"已達 reviewer 預算上限 {budget.reviewer_limit}"}

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
        result = review_report(vlm, docx_path, row_context, rubric, model, max_pages=4)
        if budget is not None and "error" not in result:
            budget.use_reviewer()
        return result

    def open_output_folder(self) -> dict:
        from app.ui import open_folder

        path = self._app.output_dir.get()
        if not path:
            return {"error": "尚未設定輸出資料夾"}
        os.makedirs(path, exist_ok=True)
        ok = open_folder(path)
        return {"ok": ok, "path": path}

    # ---------- 範本對應 (P8: 自動對應) ----------

    def read_docx_text(self, word_path: str = "", max_paragraphs: int = 0) -> dict:
        from app.agent.template_edit import read_docx_text as _read

        path = word_path or self._app.word_path.get()
        return _read(path, max_paragraphs=max_paragraphs)

    def rename_template_variable(
        self, old: str, new: str, word_path: str = ""
    ) -> dict:
        from app.agent.template_edit import rename_template_variable as _rename

        path = word_path or self._app.word_path.get()
        return _rename(path, old, new)

    def insert_template_variable(
        self,
        anchor: str,
        variable: str,
        position: str = "after",
        word_path: str = "",
    ) -> dict:
        from app.agent.template_edit import insert_template_variable as _insert

        path = word_path or self._app.word_path.get()
        return _insert(path, anchor, variable, position)

    def suggest_mappings(self, word_path: str = "", excel_path: str = "") -> dict:
        """讀範本 + Excel，呼 planner LLM 回傳 renames / inserts 建議清單。

        消耗 1 次 planner 預算（成功時）。
        """
        from app.agent.mapping_suggester import suggest_mappings as _suggest
        from app.agent.template_edit import read_docx_text as _read_docx

        wp = word_path or self._app.word_path.get()
        ep = excel_path or self._app.excel_path.get()
        if not wp:
            return {"error": "未提供 Word 路徑"}
        if not ep:
            return {"error": "未提供 Excel 路徑"}

        # 讀範本段落（限制長度避免吃太多 prompt）
        rd = _read_docx(wp, max_paragraphs=80)
        if "error" in rd:
            return {"error": f"讀範本失敗: {rd['error']}"}
        paragraphs = rd.get("paragraphs", [])

        # 讀範本既有變數
        try:
            from docxtpl import DocxTemplate
            tpl_vars = list(DocxTemplate(wp).get_undeclared_template_variables())
        except Exception as e:
            return {"error": f"讀範本變數失敗: {e}"}

        # 讀 Excel 欄位
        try:
            import pandas as pd
            df = pd.read_excel(
                ep,
                sheet_name=self._app.sheet_name.get() or 0,
                header=max(0, self._app._header_row_int() - 1),
                nrows=0,
            )
            excel_columns = [str(c) for c in df.columns]
        except Exception as e:
            return {"error": f"讀 Excel 欄位失敗: {e}"}

        # planner LLM
        llm, model, err = self._build_planner_client()
        if err:
            return {"error": err}

        budget = getattr(self._app, "budget", None)
        if budget is not None and not budget.can_use_planner():
            return {"error": f"已達 planner 預算上限 {budget.planner_limit}"}

        result = _suggest(llm, paragraphs, tpl_vars, excel_columns, model)
        if "error" not in result and budget is not None:
            budget.use_planner()
        return result

    # ---------- 圖片資料夾 → Word 位置（P9） ----------

    def list_folder_files(self, folder_path: str, kind: str = "image", max_files: int = 0) -> dict:
        from app.agent.folder_scan import list_folder_files as _list

        return _list(folder_path, kind=kind, max_files=max_files)

    def insert_image_at_anchor(
        self,
        anchor: str,
        image_path: str,
        width_mm: int = 0,
        word_path: str = "",
    ) -> dict:
        from app.agent.template_edit import insert_image_at_anchor as _insert

        path = word_path or self._app.word_path.get()
        try:
            w = int(width_mm) if width_mm else self._app._image_width_mm_int()
        except (TypeError, ValueError):
            w = self._app._image_width_mm_int()
        return _insert(path, anchor, image_path, width_mm=w)

    def suggest_image_placements(
        self,
        image_folder: str,
        word_path: str = "",
    ) -> dict:
        """讀範本段落 + 列圖片檔名，呼 planner LLM 配對；不會自動套用。

        回傳 {placements:[{image, image_path, anchor, reason}]}，
        path 已補成完整路徑供後續 insert_image_at_anchor 使用。
        消耗 1 次 planner 預算（成功時）。
        """
        import os as _os

        from app.agent.folder_scan import list_folder_files as _list_files
        from app.agent.mapping_suggester import (
            suggest_image_placements as _suggest_imgs,
        )
        from app.agent.template_edit import read_docx_text as _read_docx

        wp = word_path or self._app.word_path.get()
        if not wp:
            return {"error": "未提供 Word 路徑"}
        if not image_folder or not _os.path.isdir(image_folder):
            return {"error": f"資料夾不存在: {image_folder}"}

        rd = _read_docx(wp, max_paragraphs=80)
        if "error" in rd:
            return {"error": f"讀範本失敗: {rd['error']}"}
        paragraphs = rd.get("paragraphs", [])

        listing = _list_files(image_folder, kind="image")
        if "error" in listing:
            return {"error": f"列圖片失敗: {listing['error']}"}
        files = listing.get("files", [])
        if not files:
            return {"error": f"資料夾中沒有圖片: {image_folder}"}

        image_names = [f["name"] for f in files]

        llm, model, err = self._build_planner_client()
        if err:
            return {"error": err}

        budget = getattr(self._app, "budget", None)
        if budget is not None and not budget.can_use_planner():
            return {"error": f"已達 planner 預算上限 {budget.planner_limit}"}

        result = _suggest_imgs(llm, paragraphs, image_names, model)
        if "error" not in result and budget is not None:
            budget.use_planner()

        # 補上完整路徑供後續 insert
        if "placements" in result:
            name_to_path = {f["name"]: f["path"] for f in files}
            for p in result["placements"]:
                p["image_path"] = name_to_path.get(p["image"], "")

        return result

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
