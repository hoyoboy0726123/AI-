"""Markdown 渲染器 — 把 markdown 文字渲染成 Tk Text widget 內的富文字。

支援:
- 標題(# / ## / ###)
- **粗體** / *斜體* / `inline code`
- ```fenced code blocks```
- - / * 項目符號 + 1. 數字列表
- > blockquote
- [text](url) 連結(藍底底線,複製貼上有效)
- 水平分隔線(---)
- markdown 表格(用嵌入的 CTkFrame grid 渲染,真正的表格樣式)

依 customtkinter 當前 appearance mode 自動切色票(dark / light)。
"""

import re
import tkinter as tk
import customtkinter as ctk


# ---------- Block patterns ----------

RE_H1 = re.compile(r"^# (.+)$")
RE_H2 = re.compile(r"^## (.+)$")
RE_H3 = re.compile(r"^### (.+)$")
RE_HR = re.compile(r"^[-*_]{3,}\s*$")
RE_FENCE = re.compile(r"^```(\w*)\s*$")
RE_BULLET = re.compile(r"^([-*+])\s+(.*)$")
RE_NUMBER = re.compile(r"^(\d+)\.\s+(.*)$")
RE_QUOTE = re.compile(r"^>\s?(.*)$")
RE_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
RE_TABLE_SEP = re.compile(r"^\s*\|[\s:|\-]+\|\s*$")


# ---------- Inline patterns ----------
# 順序重要:code 先(避免 ** 在 code 內被當粗體)、其次 link、然後 bold / italic
INLINE_PATTERNS = [
    ("code",   re.compile(r"`([^`\n]+)`")),
    ("link",   re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")),
    ("bold",   re.compile(r"\*\*([^*\n]+)\*\*")),
    ("bold",   re.compile(r"__([^_\n]+)__")),
    ("italic", re.compile(r"(?<![*])\*([^*\n]+?)\*(?![*])")),
    ("italic", re.compile(r"(?<![_])_([^_\n]+?)_(?![_])")),
]


def _is_dark():
    try:
        return ctk.get_appearance_mode().lower().startswith("dark")
    except Exception:
        return False


def _palette():
    """依當前 mode 回傳一組顏色。"""
    if _is_dark():
        return {
            "fg":          "#e6edf3",
            "muted":       "#8b949e",
            "code_bg":     "#262b33",
            "code_fg":     "#f0f6fc",
            "block_bg":    "#161b22",
            "block_fg":    "#c9d1d9",
            "quote_fg":    "#9aa0a6",
            "quote_bar":   "#3a4250",
            "link":        "#58a6ff",
            "hr":          "#2a3038",
            "table_head_bg":  "#1f2937",
            "table_row_bg":   "#161b22",
            "table_alt_bg":   "#1a2029",
            "table_border":   "#30363d",
        }
    return {
        "fg":          "#1f2328",
        "muted":       "#6b7280",
        "code_bg":     "#eff1f3",
        "code_fg":     "#1f2328",
        "block_bg":    "#f6f8fa",
        "block_fg":    "#24292f",
        "quote_fg":    "#57606a",
        "quote_bar":   "#d0d7de",
        "link":        "#0969da",
        "hr":          "#d0d7de",
        "table_head_bg":  "#f6f8fa",
        "table_row_bg":   "#ffffff",
        "table_alt_bg":   "#f9fafb",
        "table_border":   "#d0d7de",
    }


class MarkdownRenderer:
    """把 markdown 文字渲染到 Tk Text widget。

    用法:
        renderer = MarkdownRenderer(text_widget, base_size=13)
        renderer.render("# Hello\\n\\n**bold** and *italic*\\n")

    Tag 會在第一次 render 時設好,之後切換 appearance mode 需要 refresh_tags()。
    """

    def __init__(self, text_widget, base_size=13, mono_font="Consolas",
                 base_font="Microsoft JhengHei"):
        self.txt = text_widget
        self.base_size = base_size
        self.mono = mono_font
        self.base = base_font
        self._tables = []  # 保住嵌入的 frame ref,避免 gc
        self._setup_tags()

    def refresh_tags(self):
        """appearance mode 切換時重建 tag 顏色。"""
        self._setup_tags()

    def _setup_tags(self):
        c = _palette()
        t = self.txt
        bs = self.base_size
        t.tag_config("md_p",         font=(self.base, bs),                spacing1=2, spacing3=4, foreground=c["fg"])
        t.tag_config("md_h1",        font=(self.base, bs + 8, "bold"),    spacing1=14, spacing3=6, foreground=c["fg"])
        t.tag_config("md_h2",        font=(self.base, bs + 4, "bold"),    spacing1=12, spacing3=5, foreground=c["fg"])
        t.tag_config("md_h3",        font=(self.base, bs + 2, "bold"),    spacing1=10, spacing3=4, foreground=c["fg"])
        t.tag_config("md_bold",      font=(self.base, bs, "bold"),        foreground=c["fg"])
        t.tag_config("md_italic",    font=(self.base, bs, "italic"),      foreground=c["fg"])
        t.tag_config("md_code",      font=(self.mono, bs - 1),            background=c["code_bg"], foreground=c["code_fg"])
        t.tag_config("md_codeblock", font=(self.mono, bs - 1),
                     background=c["block_bg"], foreground=c["block_fg"],
                     lmargin1=14, lmargin2=14, rmargin=14,
                     spacing1=6, spacing3=6)
        t.tag_config("md_quote",     foreground=c["quote_fg"], lmargin1=18, lmargin2=18, spacing1=2, spacing3=2)
        t.tag_config("md_quote_bar", foreground=c["quote_bar"])
        t.tag_config("md_link",      foreground=c["link"], underline=1)
        t.tag_config("md_list",      lmargin1=10, lmargin2=28, spacing1=1, spacing3=1, foreground=c["fg"])
        t.tag_config("md_hr",        foreground=c["hr"], spacing1=6, spacing3=6, justify="center")
        t.tag_config("md_muted",     foreground=c["muted"])

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def render(self, text):
        """把整段 markdown 寫到 widget end。"""
        if not text:
            return
        lines = text.replace("\r\n", "\n").split("\n")
        i = 0
        n = len(lines)
        while i < n:
            line = lines[i]

            # fenced code block
            m = RE_FENCE.match(line)
            if m:
                code_lines = []
                i += 1
                while i < n and not RE_FENCE.match(lines[i]):
                    code_lines.append(lines[i])
                    i += 1
                # skip closing ```
                if i < n:
                    i += 1
                self.txt.insert("end", "\n".join(code_lines) + "\n", ("md_codeblock",))
                continue

            # markdown table
            if (RE_TABLE_ROW.match(line)
                    and i + 1 < n
                    and RE_TABLE_SEP.match(lines[i + 1])):
                header = line
                data = []
                j = i + 2
                while j < n and RE_TABLE_ROW.match(lines[j]):
                    data.append(lines[j])
                    j += 1
                self._render_table(header, data)
                i = j
                continue

            # headers
            for pat, tag in ((RE_H1, "md_h1"), (RE_H2, "md_h2"), (RE_H3, "md_h3")):
                hm = pat.match(line)
                if hm:
                    self._render_inline(hm.group(1), default_tag=tag)
                    self.txt.insert("end", "\n")
                    break
            else:
                # hr
                if RE_HR.match(line.strip()):
                    self.txt.insert("end", "─" * 40 + "\n", ("md_hr",))
                    i += 1
                    continue
                # bullet list
                bm = RE_BULLET.match(line)
                if bm:
                    self.txt.insert("end", "  • ", ("md_list",))
                    self._render_inline(bm.group(2), default_tag="md_list")
                    self.txt.insert("end", "\n")
                    i += 1
                    continue
                # numbered list
                nm = RE_NUMBER.match(line)
                if nm:
                    self.txt.insert("end", f"  {nm.group(1)}. ", ("md_list",))
                    self._render_inline(nm.group(2), default_tag="md_list")
                    self.txt.insert("end", "\n")
                    i += 1
                    continue
                # blockquote
                qm = RE_QUOTE.match(line)
                if qm:
                    self.txt.insert("end", "│ ", ("md_quote_bar",))
                    self._render_inline(qm.group(1), default_tag="md_quote")
                    self.txt.insert("end", "\n")
                    i += 1
                    continue
                # plain paragraph or empty
                if line.strip() == "":
                    self.txt.insert("end", "\n")
                else:
                    self._render_inline(line, default_tag="md_p")
                    self.txt.insert("end", "\n")
            i += 1

    # ------------------------------------------------------------------
    # Inline + table
    # ------------------------------------------------------------------

    def _find_first_inline(self, text, start):
        best = None
        best_pos = len(text) + 1
        best_tag = None
        for tag, pat in INLINE_PATTERNS:
            m = pat.search(text, start)
            if m and m.start() < best_pos:
                best, best_pos, best_tag = m, m.start(), tag
        return best, best_tag

    def _render_inline(self, text, default_tag=None):
        cursor = 0
        plain_tags = (default_tag,) if default_tag else ()
        while cursor < len(text):
            m, tag = self._find_first_inline(text, cursor)
            if m is None:
                self.txt.insert("end", text[cursor:], plain_tags)
                return
            if m.start() > cursor:
                self.txt.insert("end", text[cursor:m.start()], plain_tags)
            if tag == "link":
                label, url = m.group(1), m.group(2)
                tags = ("md_link",) + plain_tags
                self.txt.insert("end", label, tags)
                # 留 url 在 muted 小字旁(可複製);避免 click handler 亂打架
                self.txt.insert("end", f" ({url})", ("md_muted",) + plain_tags)
            else:
                tag_name = {"bold": "md_bold", "italic": "md_italic", "code": "md_code"}[tag]
                tags = (tag_name,) + plain_tags
                self.txt.insert("end", m.group(1), tags)
            cursor = m.end()

    def _render_table(self, header_line, data_lines):
        c = _palette()

        def split_cells(line):
            line = line.strip()
            if line.startswith("|"):
                line = line[1:]
            if line.endswith("|"):
                line = line[:-1]
            return [cell.strip() for cell in line.split("|")]

        headers = split_cells(header_line)
        rows = [split_cells(r) for r in data_lines]
        n_cols = max(len(headers), max((len(r) for r in rows), default=0))
        # pad
        while len(headers) < n_cols:
            headers.append("")
        for r in rows:
            while len(r) < n_cols:
                r.append("")

        # 用 CTkFrame 包,圓角 + 邊框
        frame = ctk.CTkFrame(
            self.txt,
            fg_color=c["table_row_bg"],
            border_color=c["table_border"],
            border_width=1,
            corner_radius=8,
        )

        # 每 cell 是 CTkLabel
        for j, cell in enumerate(headers):
            lbl = ctk.CTkLabel(
                frame,
                text=cell,
                font=ctk.CTkFont(family=self.base, size=self.base_size, weight="bold"),
                anchor="w",
                fg_color=c["table_head_bg"],
                corner_radius=0,
                padx=12,
                pady=6,
            )
            lbl.grid(row=0, column=j, sticky="nsew", padx=0, pady=0)

        for i, row in enumerate(rows, start=1):
            row_bg = c["table_row_bg"] if i % 2 == 1 else c["table_alt_bg"]
            for j in range(n_cols):
                lbl = ctk.CTkLabel(
                    frame,
                    text=row[j],
                    font=ctk.CTkFont(family=self.base, size=self.base_size - 1),
                    anchor="w",
                    fg_color=row_bg,
                    corner_radius=0,
                    padx=12,
                    pady=5,
                    justify="left",
                )
                lbl.grid(row=i, column=j, sticky="nsew", padx=0, pady=0)

        for j in range(n_cols):
            frame.grid_columnconfigure(j, weight=1, minsize=80, uniform="tbl")

        self.txt.window_create("end", window=frame, padx=10, pady=8)
        self.txt.insert("end", "\n")
        self._tables.append(frame)  # keep ref
