# -*- coding: utf-8 -*-
"""QML entry point for the DS5 Bridge console."""
from __future__ import annotations

import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

# GDI keeps ClearType sub-pixel rendering for Chinese text; Qt 6 defaults to
# DirectWrite grayscale antialiasing on Windows.
os.environ.setdefault("QT_QPA_PLATFORM", "windows:fontengine=gdi")

from PySide6.QtCore import QObject, QTimer, QUrl
from PySide6.QtGui import QFont, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from ds5_bridge.qml_bridge import ThemeModel, UiBridge
from ds5_bridge.tray import create_tray

APP_NAME = "DS5 Bridge 控制台"


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


def _icon_path() -> Path:
    base = _base_dir()
    icon = base / "assets" / "ds5_bridge.ico"
    return icon if icon.exists() else base / "assets" / "icon.ico"


def _screenshot_dir() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent
    path = base / "output" / "frontend-qa"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _self_test_log_path() -> Path:
    return Path(tempfile.gettempdir()) / "DS5BridgeControl-self-test.log"


def _write_self_test_log(lines: list[str]) -> None:
    try:
        _self_test_log_path().write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        pass


def _run_self_test(window: QQuickWindow, bridge: UiBridge) -> int:
    """Verify the packaged runtime without requiring a controller."""
    lines = [
        f"time={time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"executable={sys.executable}",
        f"frozen={getattr(sys, 'frozen', False)}",
    ]
    try:
        import hid  # noqa: F401

        lines.append(f"python={sys.version.split()[0]}")
        lines.append(f"qml_page={window.property('page')!r}")
        config_page = window.findChild(QObject, "configPage")
        if config_page is None:
            raise RuntimeError("QML configPage object was not created")
        if not _icon_path().exists():
            raise RuntimeError(f"application icon is missing: {_icon_path()}")
        lines.append("result=ok")
        _write_self_test_log(lines)
        bridge.shutdown()
        return 0
    except BaseException:
        lines.append("result=failed")
        lines.append(traceback.format_exc())
        _write_self_test_log(lines)
        bridge.shutdown()
        return 3


def _run_screenshot(window: QQuickWindow, app: QApplication) -> None:
    out = _screenshot_dir()
    log_path = out / "ds5-qml-screenshot.log"

    def log(message: str) -> None:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%H:%M:%S')} {message}\n")

    log("qml screenshot mode start")
    steps = [
        (0, "ds5-qml-config.png", ""),
        (0, "ds5-qml-config-collapsed.png", "collapse"),
        (0, "ds5-qml-config-expanded.png", "expand"),
        (1, "ds5-qml-device.png", ""),
        (2, "ds5-qml-about.png", ""),
        (0, "ds5-qml-config-compact.png", "compact"),
    ]
    state = {"index": 0}
    config_page = window.findChild(QObject, "configPage")

    def save_current(page: int, name: str, action: str) -> None:
        try:
            path = out / name
            ok = window.grabWindow().save(str(path))
            log(f"capture page={page} action={action or 'none'} saved={ok} path={path}")
        except BaseException:
            log(f"capture page={page} failed:\n{traceback.format_exc()}")
            app.quit()
            return
        state["index"] += 1
        QTimer.singleShot(260, capture_next)

    def capture_next() -> None:
        index = state["index"]
        if index >= len(steps):
            log("all pages captured")
            window.close()
            app.quit()
            return
        page, name, action = steps[index]
        if action == "compact":
            window.resize(1080, 720)
        else:
            window.resize(1280, 820)
        current = window.property("page")
        if page != current:
            ok = window.setProperty("page", page)
            log(f"switch page {current!r} -> {page} ok={ok} now={window.property('page')!r}")
        else:
            log(f"page already {current!r}")
        if config_page is not None:
            if action == "collapse":
                config_page.setProperty("audioOpen", False)
            elif action == "expand":
                config_page.setProperty("audioOpen", True)
        delay = 2200 if page == 1 else 620
        QTimer.singleShot(delay, lambda p=page, n=name, a=action: save_current(p, n, a))

    QTimer.singleShot(2800, capture_next)


def main() -> int:
    screenshot = "--screenshot" in sys.argv
    self_test = "--self-test" in sys.argv
    argv = [arg for arg in sys.argv if arg not in ("--screenshot", "--self-test")]
    if self_test:
        # The installer uses this mode to check the bundled Qt/QML runtime
        # without flashing a window.
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

    QQuickStyle.setStyle("Basic")
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("DS5 Bridge Control")
    font = QFont("Microsoft YaHei UI", 11)
    font.setHintingPreference(QFont.PreferFullHinting)
    app.setFont(font)
    icon_path = _icon_path()
    app_icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    bridge = UiBridge()
    theme = ThemeModel()
    app.aboutToQuit.connect(bridge.shutdown)

    engine = QQmlApplicationEngine()
    context = engine.rootContext()
    context.setContextProperty("bridge", bridge)
    context.setContextProperty("theme", theme)
    qml = _base_dir() / "ds5_bridge" / "qml" / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml)))
    roots = engine.rootObjects()
    if not roots:
        print(f"QML load failed: {qml}", flush=True)
        _write_self_test_log([f"qml={qml}", "result=failed", "QML rootObjects is empty"])
        bridge.shutdown()
        return 2
    window = roots[0]
    if not isinstance(window, QQuickWindow):
        print("QML root is not a window", flush=True)
        _write_self_test_log(["result=failed", "QML root is not a QQuickWindow"])
        bridge.shutdown()
        return 2

    if self_test:
        return _run_self_test(window, bridge)

    tray = None if screenshot else create_tray(app, window, bridge, app_icon)

    if screenshot:
        _run_screenshot(window, app)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
