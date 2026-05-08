"""應用程式進入點。"""

from app.ui import AutoReportApp


def main():
    app = AutoReportApp()
    app.mainloop()


if __name__ == "__main__":
    main()
