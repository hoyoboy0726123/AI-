"""應用程式進入點。"""

# 載入 .env（若有），讓子模組能讀到 GEMINI_API_KEY 等。
# 缺少 python-dotenv 不影響手動頁籤運作。
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from app.ui import AutoReportApp


def main():
    app = AutoReportApp()
    app.mainloop()


if __name__ == "__main__":
    main()
