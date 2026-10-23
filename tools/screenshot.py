from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication
from qfluentwidgets import Theme, setTheme, setThemeColor

from dse_panel.ui import MainWindow

OUT = Path(__file__).resolve().parent.parent / "output" / "frontend-qa"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> int:
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei UI", 10))
    setTheme(Theme.DARK)
    setThemeColor("#4F8CFF")
    window = MainWindow()
    window.show()

    pages = [
        ("overview", window.overview),
        ("rumble", window.rumble),
        ("receiver", window.receiver),
        ("back", window.back),
        ("audio", window.audio),
        ("about", window.about),
    ]
    state = {"index": 0}

    def capture_next() -> None:
        index = state["index"]
        if index >= len(pages):
            window.close()
            app.quit()
            return
        name, page = pages[index]
        window.switchTo(page)
        app.processEvents()
        time.sleep(0.35)
        app.processEvents()
        path = OUT / f"{name}-v1.png"
        window.grab().save(str(path))
        print(f"saved {path}")
        state["index"] += 1
        QTimer.singleShot(400, capture_next)

    QTimer.singleShot(1800, capture_next)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
