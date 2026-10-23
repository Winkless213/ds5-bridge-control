from __future__ import annotations

import sys
import time
import traceback
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication
from qfluentwidgets import Theme, setTheme, setThemeColor

from dse_panel.ui import MainWindow


def _icon_path() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / "assets" / "icon.ico"


def _run_screenshot(window: MainWindow, app: QApplication) -> None:
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent
    out = base / "output" / "frontend-qa"
    out.mkdir(parents=True, exist_ok=True)
    log_path = out / "screenshot.log"

    def log(message: str) -> None:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%H:%M:%S')} {message}\n")

    log("screenshot mode start")
    pages = [
        ("overview", window.overview),
        ("rumble", window.rumble),
        ("receiver", window.receiver),
        ("back", window.back),
        ("audio", window.audio),
        ("about", window.about),
    ]
    index = {"value": 0}

    def capture_next() -> None:
        i = index["value"]
        if i >= len(pages):
            log("all pages captured")
            window.close()
            app.quit()
            return
        name, page = pages[i]
        try:
            log(f"capture {name} start")
            window.switchTo(page)
            log(f"capture {name} switched")
            app.processEvents()
            time.sleep(0.3)
            app.processEvents()
            path = out / f"packaged-{name}.png"
            ok = window.grab().save(str(path))
            log(f"capture {name} saved={ok} path={path}")
            print(f"saved {path}", flush=True)
        except BaseException:
            log(f"capture {name} failed:\n{traceback.format_exc()}")
            window.close()
            app.quit()
            return
        index["value"] += 1
        QTimer.singleShot(300, capture_next)

    QTimer.singleShot(1600, capture_next)


def main() -> int:
    screenshot = "--screenshot" in sys.argv
    argv = [a for a in sys.argv if a != "--screenshot"]
    app = QApplication(argv)
    app.setApplicationName("DSE Control")
    app.setOrganizationName("DSE Control")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    icon = _icon_path()
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    setTheme(Theme.DARK)
    setThemeColor("#4F8CFF")
    window = MainWindow()
    window.show()
    if screenshot:
        _run_screenshot(window, app)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
