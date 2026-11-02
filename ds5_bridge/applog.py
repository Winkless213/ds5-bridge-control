# -*- coding: utf-8 -*-
"""Rotating runtime log for the DS5 Bridge console.

``%LOCALAPPDATA%\\DS5 Bridge Control\\logs\\ds5-bridge.log`` collects device
probes, connections, config writes, every raw battery change, HID errors,
uncaught exceptions and QML warnings, so a problem can be diagnosed after the
fact. Four rotated 1 MB files are kept.
"""
from __future__ import annotations

import logging
import os
import platform
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOGGER_NAME = "ds5"
LOG_FILE = "ds5-bridge.log"
MAX_BYTES = 1024 * 1024
BACKUP_COUNT = 4

log = logging.getLogger(LOGGER_NAME)

_handler: logging.Handler | None = None
_directory: Path | None = None
_previous_excepthook = None
_previous_threading_hook = None


def default_log_dir() -> Path:
    override = os.environ.get("DS5_BRIDGE_LOG_DIR")
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) if base else Path.home() / "AppData" / "Local"
    return root / "DS5 Bridge Control" / "logs"


def log_dir() -> Path:
    return _directory or default_log_dir()


def log_file() -> Path:
    return log_dir() / LOG_FILE


def setup_logging(version: str, directory: Path | None = None) -> Path | None:
    """Attach the rotating file handler once. Returns the log path, or None
    when the directory is not writable (the app then runs without a log)."""
    global _handler, _directory
    if _handler is not None:
        return log_file()
    target = directory or default_log_dir()
    try:
        target.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            target / LOG_FILE,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
    except OSError:
        return None
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s.%(msecs)03d %(levelname)-7s %(name)s [%(threadName)s] %(message)s",
            "%Y-%m-%d %H:%M:%S",
        )
    )
    log.addHandler(handler)
    log.setLevel(logging.DEBUG if os.environ.get("DS5_BRIDGE_DEBUG") else logging.INFO)
    log.propagate = False
    _handler = handler
    _directory = target
    _install_exception_hooks()
    log.info(
        "==== DS5 Bridge Control %s 启动 · pid %s · %s · Python %s · %s",
        version,
        os.getpid(),
        "打包版" if getattr(sys, "frozen", False) else "源码版",
        platform.python_version(),
        platform.platform(),
    )
    log.info("程序路径 %s", sys.executable)
    return target / LOG_FILE


def shutdown_logging() -> None:
    """Detach the file handler and restore the exception hooks (tests, exit)."""
    global _handler, _directory, _previous_excepthook, _previous_threading_hook
    if _handler is None:
        return
    log.removeHandler(_handler)
    _handler.close()
    _handler = None
    _directory = None
    if _previous_excepthook is not None:
        sys.excepthook = _previous_excepthook
        _previous_excepthook = None
    if _previous_threading_hook is not None:
        threading.excepthook = _previous_threading_hook
        _previous_threading_hook = None


def _install_exception_hooks() -> None:
    global _previous_excepthook, _previous_threading_hook
    _previous_excepthook = sys.excepthook
    _previous_threading_hook = threading.excepthook
    previous = _previous_excepthook
    previous_thread = _previous_threading_hook

    def excepthook(exc_type, exc, tb) -> None:
        if not issubclass(exc_type, KeyboardInterrupt):
            log.critical("未捕获的异常", exc_info=(exc_type, exc, tb))
        previous(exc_type, exc, tb)

    def thread_hook(args: threading.ExceptHookArgs) -> None:
        if args.exc_type is not SystemExit:
            name = args.thread.name if args.thread is not None else "?"
            log.critical(
                "线程 %s 未捕获的异常",
                name,
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
            )
        previous_thread(args)

    sys.excepthook = excepthook
    threading.excepthook = thread_hook


def install_qt_message_handler() -> None:
    """Route Qt/QML warnings (binding errors, missing files) into the log."""
    from PySide6.QtCore import QtMsgType, qInstallMessageHandler

    levels = {
        QtMsgType.QtDebugMsg: logging.DEBUG,
        QtMsgType.QtInfoMsg: logging.INFO,
        QtMsgType.QtWarningMsg: logging.WARNING,
        QtMsgType.QtCriticalMsg: logging.ERROR,
        QtMsgType.QtFatalMsg: logging.CRITICAL,
    }
    qt_log = logging.getLogger(f"{LOGGER_NAME}.qt")

    def handler(mode, context, message) -> None:
        where = ""
        if context is not None and getattr(context, "file", None):
            where = f" ({context.file}:{context.line})"
        qt_log.log(levels.get(mode, logging.WARNING), "%s%s", message, where)
        if sys.stderr is not None:
            try:
                print(f"{message}{where}", file=sys.stderr)
            except (OSError, ValueError):
                pass

    qInstallMessageHandler(handler)


def open_log_folder() -> bool:
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices

    directory = log_dir()
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory)))
