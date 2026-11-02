# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import sys
import threading

from ds5_bridge import applog


def test_setup_writes_rotating_log(tmp_path):
    hook_before = sys.excepthook
    thread_hook_before = threading.excepthook
    try:
        path = applog.setup_logging("9.9.9", tmp_path)
        assert path == tmp_path / applog.LOG_FILE
        assert applog.log_dir() == tmp_path
        # A second call keeps the first handler.
        assert applog.setup_logging("9.9.9", tmp_path / "other") == path
        logging.getLogger("ds5.battery").info("原始 b53=0x14")
        logging.getLogger("unrelated").warning("must not be captured")
    finally:
        applog.shutdown_logging()
    text = path.read_text(encoding="utf-8")
    assert "DS5 Bridge Control 9.9.9" in text
    assert "ds5.battery" in text and "原始 b53=0x14" in text
    assert "must not be captured" not in text
    # Hooks are restored after shutdown.
    assert sys.excepthook is hook_before
    assert threading.excepthook is thread_hook_before


def test_uncaught_exception_is_logged(tmp_path):
    path = applog.setup_logging("9.9.9", tmp_path)
    try:
        try:
            raise ValueError("boom")
        except ValueError:
            # Call the installed hook directly; the previous hook prints to
            # stderr, which pytest captures.
            sys.excepthook(*sys.exc_info())
    finally:
        applog.shutdown_logging()
    text = path.read_text(encoding="utf-8")
    assert "未捕获的异常" in text
    assert "ValueError: boom" in text


def test_unwritable_directory_returns_none(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    try:
        assert applog.setup_logging("9.9.9", blocker / "logs") is None
    finally:
        applog.shutdown_logging()
