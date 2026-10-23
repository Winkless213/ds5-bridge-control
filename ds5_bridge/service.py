# -*- coding: utf-8 -*-
"""Background HID service: all device I/O stays off the UI thread."""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from .protocol import (
    REPORT_INPUT,
    DeviceInfo,
    Ds5Error,
    configs_equal,
    find_supported_device,
    open_device,
    parse_battery,
    probe_devices,
    read_config,
    read_firmware,
    read_status,
    reconnect_usb,
    write_config,
)
from .rate import compute_stats


class _TaskSignals(QObject):
    success = Signal(object)
    error = Signal(str)
    done = Signal()


class _HidTask(QRunnable):
    def __init__(self, fn: Callable[[], Any], signals: _TaskSignals) -> None:
        super().__init__()
        self.fn = fn
        self.signals = signals
        self.setAutoDelete(True)

    def run(self) -> None:
        try:
            self.signals.success.emit(self.fn())
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI
            message = str(exc).strip() or exc.__class__.__name__
            self.signals.error.emit(message)
        finally:
            self.signals.done.emit()


@dataclass(slots=True)
class ApplyResult:
    config: dict[str, Any]
    saved: bool
    reconnected: bool
    info: DeviceInfo
    firmware: str = ""
    status: dict[str, Any] | None = None
    reconnect_error: str = ""


def _reconnect_and_collect(path: bytes) -> tuple[DeviceInfo, dict[str, Any], str, dict[str, Any]]:
    try:
        device = open_device(path)
        try:
            reconnect_usb(device)
        finally:
            device.close()
    except Ds5Error:
        # The receiver may drop the link before the report completes.
        pass

    deadline = time.monotonic() + 10.0
    last_error = "设备没有重新出现。"
    while time.monotonic() < deadline:
        time.sleep(0.45)
        try:
            info = find_supported_device()
            device = open_device(info.path)
            try:
                return info, read_config(device), read_firmware(device), read_status(device)
            finally:
                device.close()
        except Ds5Error as exc:
            last_error = str(exc)
    raise Ds5Error(f"自动重连超时：{last_error}")


class BatteryReader(QObject):
    """Read battery state from the standard 0x01 input report.

    A persistent handle is kept open so the UI does not pay an open/close
    cost every second. Feature-report calls use their own short-lived
    handles; Windows HID allows both readers at the same time.
    """

    battery = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._lock = threading.Lock()
        self._path: bytes | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name="ds5-battery", daemon=True
        )
        self._thread.start()

    def watch(self, path: bytes | None) -> None:
        new_path = bytes(path) if path else None
        with self._lock:
            changed = new_path != self._path
            self._path = new_path
        if changed:
            self.battery.emit(None)

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)

    def _run(self) -> None:
        device: Any = None
        device_path: bytes | None = None
        misses = 0
        unknown = False
        last_emit = 0.0
        last_state: dict[str, Any] | None = None

        while not self._stop.is_set():
            with self._lock:
                path = self._path
            if path is None:
                if device is not None:
                    device.close()
                    device = None
                    device_path = None
                misses = 0
                last_state = None
                self._stop.wait(0.25)
                continue

            if device is None or device_path != path:
                if device is not None:
                    device.close()
                device = None
                device_path = None
                try:
                    device = open_device(path)
                except (Ds5Error, OSError):
                    if not unknown:
                        self.battery.emit(None)
                        unknown = True
                    last_state = None
                    self._stop.wait(1.0)
                    continue
                device_path = path
                misses = 0
                unknown = False
                last_emit = 0.0
                last_state = None

            try:
                data = device.read(64, 400)
            except OSError:
                device.close()
                device = None
                device_path = None
                if not unknown:
                    self.battery.emit(None)
                    unknown = True
                last_state = None
                self._stop.wait(0.8)
                continue

            if not data:
                misses += 1
                if misses >= 3 and not unknown:
                    self.battery.emit(None)
                    unknown = True
                if unknown:
                    last_state = None
                continue

            misses = 0
            state = parse_battery(data)
            if state is None:
                continue
            with self._lock:
                if self._path != path:
                    continue
            now = time.monotonic()
            if now - last_emit >= 0.8:
                if state != last_state:
                    self.battery.emit(state)
                    last_state = state
                last_emit = now
                unknown = False
            # Battery changes slowly; read at ~6 Hz instead of the full
            # 250/500 Hz report rate to keep idle CPU near zero.
            self._stop.wait(0.15)

        if device is not None:
            device.close()


class InputRateMonitor(QObject):
    """Count 0x01 input reports on a dedicated HID handle."""

    sample = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self, path: bytes) -> None:
        self.stop()
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            args=(bytes(path), self._stop),
            name="ds5-rate",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)
        self._thread = None

    def _run(self, path: bytes, stop: threading.Event) -> None:
        try:
            device = open_device(path)
        except (Ds5Error, OSError):
            self.sample.emit(None)
            return
        times: deque[float] = deque()
        last_publish = 0.0
        try:
            while not stop.is_set():
                data = device.read(64, 20)
                now = time.perf_counter()
                if not data or data[0] != REPORT_INPUT:
                    continue
                times.append(now)
                cutoff = now - 3.0
                while times and times[0] < cutoff:
                    times.popleft()
                if now - last_publish >= 0.25:
                    stats = compute_stats(times, now, window=2.0)
                    if stats is not None:
                        self.sample.emit(stats)
                    last_publish = now
        except OSError:
            self.sample.emit(None)
        finally:
            device.close()


class DeviceService(QObject):
    busy_changed = Signal(bool)
    probe_done = Signal(list)
    connected = Signal(object, dict, str, dict)
    status_read = Signal(dict)
    battery_changed = Signal(object)
    rate_sample = Signal(object)
    applied = Signal(object)
    error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self._busy = False
        self._running = False
        self._signals: set[_TaskSignals] = set()
        self.info: DeviceInfo | None = None
        self.config: dict[str, Any] | None = None
        self._battery = BatteryReader(self)
        self._battery.battery.connect(self.battery_changed)
        self._rate = InputRateMonitor(self)
        self._rate.sample.connect(self.rate_sample)

    @property
    def busy(self) -> bool:
        return self._busy

    def _finish(self, signals: _TaskSignals) -> None:
        self._running = False
        self._signals.discard(signals)
        if self._busy:
            self._busy = False
            self.busy_changed.emit(False)

    def _submit(
        self,
        fn: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[str], None] | None = None,
        *,
        quiet_busy: bool = False,
    ) -> bool:
        if self._running:
            return False
        self._running = True
        if not quiet_busy:
            self._busy = True
            self.busy_changed.emit(True)
        signals = _TaskSignals()
        signals.success.connect(on_success)
        signals.error.connect(on_error or self.error.emit)
        signals.done.connect(lambda s=signals: self._finish(s))
        self._signals.add(signals)
        self.pool.start(_HidTask(fn, signals))
        return True

    def probe(self) -> bool:
        return self._submit(probe_devices, self.probe_done.emit)

    def connect(self, info: DeviceInfo) -> bool:
        def work() -> tuple[DeviceInfo, dict[str, Any], str, dict[str, Any]]:
            device = open_device(info.path)
            try:
                return info, read_config(device), read_firmware(device), read_status(device)
            finally:
                device.close()

        def done(result: tuple[DeviceInfo, dict[str, Any], str, dict[str, Any]]) -> None:
            self.info, self.config = result[0], result[1]
            self._battery.watch(result[0].path)
            self.connected.emit(*result)

        return self._submit(work, done)

    def refresh_status(self) -> bool:
        if not self.info:
            return False

        def work() -> dict[str, Any]:
            device = open_device(self.info.path)  # type: ignore[union-attr]
            try:
                return read_status(device)
            finally:
                device.close()

        return self._submit(work, self.status_read.emit, quiet_busy=True)

    def apply(self, config: dict[str, Any], save: bool, reconnect: bool = False) -> bool:
        if not self.info:
            return False
        info = self.info

        def work() -> ApplyResult:
            device = open_device(info.path)
            try:
                fresh = write_config(device, config, save=save)
            finally:
                device.close()

            if not reconnect:
                return ApplyResult(fresh, save, False, info)

            # Release the input handle before re-enumeration; otherwise the
            # old HID handle can delay the receiver coming back.
            self._battery.watch(None)
            time.sleep(0.45)
            try:
                new_info, new_config, firmware, status = _reconnect_and_collect(info.path)
            except Ds5Error as exc:
                # The write already succeeded; surface the reconnect failure
                # without discarding the saved configuration in the UI.
                return ApplyResult(fresh, save, False, info, reconnect_error=str(exc))
            return ApplyResult(new_config, save, True, new_info, firmware, status)

        def done(result: ApplyResult) -> None:
            self.info = result.info
            self.config = result.config
            if result.reconnected:
                self._battery.watch(result.info.path)
            elif result.reconnect_error:
                self._battery.watch(None)
            self.applied.emit(result)

        return self._submit(work, done)

    def reconnect(self) -> bool:
        if not self.info:
            return False

        def work() -> tuple[DeviceInfo, dict[str, Any], str, dict[str, Any]]:
            self._battery.watch(None)
            time.sleep(0.45)
            return _reconnect_and_collect(self.info.path)  # type: ignore[union-attr]

        def done(result: tuple[DeviceInfo, dict[str, Any], str, dict[str, Any]]) -> None:
            self.info, self.config = result[0], result[1]
            self._battery.watch(result[0].path)
            self.connected.emit(*result)

        return self._submit(work, done)

    def watch_battery(self, path: bytes | None) -> None:
        self._battery.watch(path)

    def start_rate(self, path: bytes) -> None:
        self._rate.start(path)

    def stop_rate(self) -> None:
        self._rate.stop()

    def shutdown(self) -> None:
        self._rate.stop()
        self._battery.stop()

    def reset_defaults(self) -> bool:
        from .protocol import DEFAULTS, normalize_config

        return self.apply(normalize_config(DEFAULTS), save=True)
