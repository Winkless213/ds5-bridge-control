"""Headless-ish Qt smoke test for the receiver coach dialog.

Runs with a temporary APPDATA so it never touches the real user config.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from dse_panel.ui import MainWindow, ReceiverCoachDialog


def main() -> int:
    os.environ["APPDATA"] = tempfile.mkdtemp(prefix="dse-coach-smoke-")
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    page = window.receiver
    window.switchTo(page)
    app.processEvents()

    seen: dict[str, object] = {}

    def inspect_and_confirm() -> None:
        dialog = QApplication.activeModalWidget()
        seen["dialog"] = dialog
        if not isinstance(dialog, ReceiverCoachDialog):
            print(f"FAIL active modal is {type(dialog).__name__}")
            app.quit()
            return
        print(f"dialog title={dialog.windowTitle()!r}")
        dialog._confirm()

    QTimer.singleShot(400, inspect_and_confirm)
    page._open_coach("rumble_level", 2)
    app.processEvents()

    status = page._status_text("rumble_level")
    print(f"status={status!r}")
    ok = isinstance(seen.get("dialog"), ReceiverCoachDialog) and "2 级" in status
    first_dialog = seen.get("dialog")
    print(
        "first_dialog_visible="
        f"{getattr(first_dialog, 'isVisible', lambda: None)()} "
        f"active_modal={type(QApplication.activeModalWidget()).__name__}"
    )

    out = Path(__file__).resolve().parent.parent / "output" / "frontend-qa"
    out.mkdir(parents=True, exist_ok=True)
    window.switchTo(page)
    app.processEvents()
    time.sleep(0.8)
    app.processEvents()
    window.grab().save(str(out / "receiver-recorded-v1.png"))
    print(f"saved {out / 'receiver-recorded-v1.png'}")

    hold_dialog = page.build_coach("settings_key", "on")
    hold_dialog._start_hold()
    hold_dialog._hold_start = time.monotonic() - 6
    hold_dialog._tick_hold()
    hold_ok = hold_dialog._hold_done and hold_dialog.hold_bar.value() == 100
    print(f"hold_done={hold_dialog._hold_done} hold_bar={hold_dialog.hold_bar.value()}")
    hold_dialog.close()
    ok = ok and hold_ok

    print("PASS" if ok else "FAIL")
    window.close()
    app.quit()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
