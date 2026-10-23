from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QScrollArea
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
    window.switchTo(window.receiver)
    app.processEvents()
    time.sleep(0.5)
    app.processEvents()

    scroll = window.receiver.findChild(QScrollArea)
    if scroll is not None:
        scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
        app.processEvents()
        time.sleep(0.3)
        path = OUT / "receiver-bottom-v1.png"
        window.grab().save(str(path))
        print(f"saved {path}")
        scroll.verticalScrollBar().setValue(0)
        app.processEvents()

    for name, key, value in (("rumble", "rumble_level", 2), ("settings", "settings_key", "on")):
        dialog = window.receiver.build_coach(key, value)
        dialog.show()
        app.processEvents()
        time.sleep(0.4)
        app.processEvents()
        path = OUT / f"receiver-coach-{name}-v1.png"
        dialog.grab().save(str(path))
        print(f"saved {path}")
        dialog.close()

    window.close()
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
