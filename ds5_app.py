# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys
import time
import traceback
from pathlib import Path

# Qt 6 defaults to DirectWrite, which rasterizes small UI text with grayscale
# antialiasing on Windows. GDI keeps ClearType sub-pixel rendering, so Chinese
# text stays crisp instead of looking washed out on dark backgrounds.
os.environ.setdefault("QT_QPA_PLATFORM", "windows:fontengine=gdi")

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication
from qfluentwidgets import Theme, setTheme, setThemeColor

from ds5_bridge.theme import ACCENT
from ds5_bridge.ui import MainWindow


def _icon_path() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    icon = base / "assets" / "ds5_bridge.ico"
    return icon if icon.exists() else base / "assets" / "icon.ico"


def _run_screenshot(window: MainWindow, app: QApplication) -> None:
    base = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    out = base / "output" / "frontend-qa"
    out.mkdir(parents=True, exist_ok=True)
    log_path = out / "ds5-screenshot.log"

    def log(message: str) -> None:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%H:%M:%S')} {message}\n")

    log("screenshot mode start")
    pages = [
        (0, "ds5-config-v2.png"),
        (1, "ds5-device-v2.png"),
        (2, "ds5-about-v2.png"),
    ]
    state = {"index": 0}

    def save_current(page: int, name: str) -> None:
        try:
            path = out / name
            ok = window.grab().save(str(path))
            log(f"capture page={page} saved={ok} path={path}")
            print(f"saved {path}", flush=True)
        except BaseException:
            log(f"capture page={page} failed:\n{traceback.format_exc()}")
            window.close()
            app.quit()
            return
        state["index"] += 1
        QTimer.singleShot(220, capture_next)

    def capture_next() -> None:
        index = state["index"]
        if index >= len(pages):
            log("all pages captured")
            window.close()
            app.quit()
            return
        page, name = pages[index]
        window.switch_page(page)
        # Let the 170ms page fade and the layout settle before grabbing.
        QTimer.singleShot(360, lambda p=page, n=name: save_current(p, n))

    QTimer.singleShot(2200, capture_next)


def main() -> int:
    screenshot = "--screenshot" in sys.argv
    argv = [arg for arg in sys.argv if arg != "--screenshot"]
    app = QApplication(argv)
    app.setApplicationName("DS5 Bridge Control")
    app.setOrganizationName("DS5 Bridge Control")
    font = QFont("Microsoft YaHei UI", 11)
    font.setHintingPreference(QFont.PreferFullHinting)
    app.setFont(font)
    icon = _icon_path()
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    setTheme(Theme.DARK)
    setThemeColor(ACCENT)
    window = MainWindow()
    window.show()
    if screenshot:
        _run_screenshot(window, app)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
