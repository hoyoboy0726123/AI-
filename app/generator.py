"""依 Excel 數據與 Word 範本批次產出報告。"""

import os

import pandas as pd
from docxtpl import DocxTemplate

from app.config import OUTPUT_DIR, REPORT_FILENAME_TEMPLATE


class ReportGenerator:
    """讀取 Excel 表格，逐列以 docxtpl 渲染 Word 範本並儲存。"""

    def __init__(self, word_path, excel_path, output_dir=OUTPUT_DIR):
        self.word_path = word_path
        self.excel_path = excel_path
        self.output_dir = output_dir

    def generate(self, progress_callback=None):
        """產出所有報告。

        progress_callback(current, total) 用來回報進度（例如更新 UI）。
        回傳實際產出檔案數量。
        """
        df = pd.read_excel(self.excel_path)
        os.makedirs(self.output_dir, exist_ok=True)

        total = len(df)
        for index, row in df.iterrows():
            doc = DocxTemplate(self.word_path)
            doc.render(row.to_dict())
            filename = REPORT_FILENAME_TEMPLATE.format(index=index + 1)
            doc.save(os.path.join(self.output_dir, filename))

            if progress_callback:
                progress_callback(index + 1, total)

        return total
