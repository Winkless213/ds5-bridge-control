# -*- coding: utf-8 -*-
"""Background HID service: all device I/O stays off the UI thread."""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from .battery import BatteryTracker
from .protocol import (
    REPORT_INPUT,
    DeviceInfo,
    Ds5Error,
    changed_keys,
    config_text,
    configs_equal,
    find_supported_device,
    firmware_block_reason,
    firmware_writable,
    open_device,
    parse_battery,
    claim_lights_report,
    play_test_haptics,
    play_test_rumble,
    probe_devices,
    read_config,
    read_firmware,
    read_status,
    reconnect_usb,
    write_config,
)
from .rate import compute_stats

log = logging.getLogger("ds5.service")
battery_log = logging.getLogger("ds5.battery")


class _TaskSignals(QObject):
    success = Signal(object)
    error = Signal(str)
    done = Signal()


class _HidTask(QRunnable):
    def __init__(self, fn: Callable[[], Any], signals: _TaskSignals, name: str = "") -> None:
        super().__init__()
        self.fn = fn
        self.signals = signals
        self.name = name
        self.setAutoDelete(True)

    def run(self) -> None:
        try:
            self.signals.success.emit(self.fn())
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI
            message = str(exc).strip() or exc.__class__.__name__
            # Expected device errors need no traceback; anything else does.
            log.warning(
                "任务 %s 失败：%s",
                self.name or "-",
                message,
                exc_info=not isinstance(exc, (Ds5Error, OSError)),
            )
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


def _ensure_writable(info: DeviceInfo) -> None:
    if not firmware_writable(info.firmware):
        raise Ds5Error(firmware_block_reason(info.firmware))


def _reconnect_and_collect(path: bytes) -> tuple[DeviceInfo, dict[str, Any], str, dict[str, Any]]:
    try:
        device = open_device(path)
        try:
            reconnect_usb(device)
        finally:
            device.close()
    except Ds5Error as exc:
        # The receiver may drop the link before the report completes.
        log.info("重连指令发送时连接已断开（正常）：%s", exc)

    deadline = time.monotonic() + 10.0
    last_error = "设备没有重新出现。"
    attempts = 0
    while time.monotonic() < deadline:
        time.sleep(0.45)
        attempts += 1
        try:
            info = find_supported_device()
            device = open_device(info.path)
            try:
                result = info, read_config(device), read_firmware(device), read_status(device)
            finally:
                device.close()
            log.info("USB 重连完成：第 %d 次检测找到接收器", attempts)
            return result
        except Ds5Error as exc:
            last_error = str(exc)
    log.warning("USB 重连超时（%d 次检测）：%s", attempts, last_error)
    raise Ds5Error(f"自动重连超时：{last_error}")


def _battery_text(view: dict[str, Any] | None) -> str:
    if not view:
        return "未知"
    percent = view.get("percent")
    head = f"{percent}% " if percent is not None else ""
    return f"{head}{view.get('label')}"


class BatteryReader(QObject):
    """Read battery state from the standard 0x01 input report.

    A persistent handle is kept open so the UI does not pay an open/close
    cost every second. Feature-report calls use their own short-lived
    handles; Windows HID allows both readers at the same time.
    """

    battery = Signal(object)

    # Raw changes are logged in full, but a flapping byte must not flood the
    # log: at most RAW_LOG_LIMIT lines per RAW_LOG_WINDOW seconds.
    RAW_LOG_LIMIT = 120
    RAW_LOG_WINDOW = 600.0

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._lock = threading.Lock()
        self._path: bytes | None = None
        self._stop = threading.Event()
        self._raw_times: deque[float] = deque()
        self._raw_suppressed = 0
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

    def _log_raw(self, reading: dict[str, Any], view: dict[str, Any]) -> None:
        now = time.monotonic()
        while self._raw_times and now - self._raw_times[0] > self.RAW_LOG_WINDOW:
            self._raw_times.popleft()
        if len(self._raw_times) >= self.RAW_LOG_LIMIT:
            self._raw_suppressed += 1
            return
        if self._raw_suppressed:
            battery_log.info("（省略了 %d 条电量原始变化）", self._raw_suppressed)
            self._raw_suppressed = 0
        self._raw_times.append(now)
        flags = reading["flags"]
        battery_log.info(
            "原始 b53=0x%02X（状态 0x%X 电量档 %d）b54=0x%02X（USB数据 %d 供电 %d 蓝牙供电 %d）→ 显示 %s%s",
            reading["raw"],
            reading["state"],
            reading["level"],
            flags,
            (flags >> 3) & 1,
            (flags >> 4) & 1,
            (flags >> 5) & 1,
            _battery_text(view),
            f"；{view['note']}" if view.get("note") else "",
        )

    def _run(self) -> None:
        device: Any = None
        device_path: bytes | None = None
        misses = 0
        unknown = False
        last_emit = 0.0
        last_state: dict[str, Any] | None = None
        last_raw: tuple[int, int] | None = None
        tracker = BatteryTracker()

        while not self._stop.is_set():
            with self._lock:
                path = self._path
            if path is None:
                if device is not None:
                    device.close()
                    device = None
                    device_path = None
                    battery_log.info("停止读取电量")
                misses = 0
                last_state = None
                last_raw = None
                tracker.reset()
                self._stop.wait(0.25)
                continue

            if device is None or device_path != path:
                if device is not None:
                    device.close()
                device = None
                device_path = None
                try:
                    device = open_device(path)
                except (Ds5Error, OSError) as exc:
                    if not unknown:
                        battery_log.warning("打开电量读取句柄失败：%s", exc)
                        self.battery.emit(None)
                        unknown = True
                    last_state = None
                    self._stop.wait(1.0)
                    continue
                battery_log.info("开始读取电量")
                device_path = path
                misses = 0
                unknown = False
                last_emit = 0.0
                last_state = None
                last_raw = None

            try:
                data = device.read(64, 400)
            except OSError as exc:
                battery_log.warning("读取输入报文失败：%s", exc)
                device.close()
                device = None
                device_path = None
                if not unknown:
                    self.battery.emit(None)
                    unknown = True
                last_state = None
                last_raw = None
                self._stop.wait(0.8)
                continue

            if not data:
                misses += 1
                if misses >= 3 and not unknown:
                    battery_log.info("1.2 秒没有收到输入报文，电量显示为未知")
                    self.battery.emit(None)
                    unknown = True
                    last_raw = None
                    tracker.reset()
                if unknown:
                    last_state = None
                continue

            misses = 0
            reading = parse_battery(data)
            if reading is None:
                continue
            with self._lock:
                if self._path != path:
                    continue
            view = tracker.update(reading).as_dict()
            raw_key = (reading["raw"], reading["flags"])
            if raw_key != last_raw:
                self._log_raw(reading, view)
                last_raw = raw_key
            now = time.monotonic()
            if now - last_emit >= 0.8:
                if view != last_state:
                    if last_state is None or (
                        view.get("percent"), view.get("label")
                    ) != (last_state.get("percent"), last_state.get("label")):
                        battery_log.info("显示电量：%s", _battery_text(view))
                    self.battery.emit(view)
                    last_state = view
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
        except (Ds5Error, OSError) as exc:
            log.warning("回报率采集打开设备失败：%s", exc)
            self.sample.emit(None)
            return
        log.debug("回报率采集开始")
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
        except OSError as exc:
            log.warning("回报率采集读取失败：%s", exc)
            self.sample.emit(None)
        finally:
            device.close()
            log.debug("回报率采集结束")


class DeviceService(QObject):
    """Runs HID work one task at a time on a worker thread.

    User actions are queued instead of dropped while another task runs; live
    previews coalesce so only the newest pending one is written.
    """

    busy_changed = Signal(bool)
    probe_done = Signal(list)
    connected = Signal(object, dict, str, dict)
    status_read = Signal(dict)
    status_failed = Signal(str)
    battery_changed = Signal(object)
    rate_sample = Signal(object)
    applied = Signal(object)
    preview_done = Signal(object)
    preview_failed = Signal(str)
    error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self._busy = False
        self._running = False
        self._signals: set[_TaskSignals] = set()
        self._queue: deque[tuple[str, Callable[[], bool]]] = deque()
        self._last_probe_lines: list[str] = []
        self.info: DeviceInfo | None = None
        self.config: dict[str, Any] | None = None
        self._battery = BatteryReader(self)
        self._battery.battery.connect(self.battery_changed)
        self._rate = InputRateMonitor(self)
        self._rate.sample.connect(self.rate_sample)

    @property
    def busy(self) -> bool:
        return self._busy

    @property
    def idle(self) -> bool:
        return not self._running and not self._queue

    def _finish(self, signals: _TaskSignals) -> None:
        self._running = False
        self._signals.discard(signals)
        if self._busy:
            self._busy = False
            self.busy_changed.emit(False)
        self._pump()

    def _submit(
        self,
        fn: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[str], None] | None = None,
        *,
        quiet_busy: bool = False,
        name: str = "",
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
        self.pool.start(_HidTask(fn, signals, name))
        return True

    def _enqueue(self, kind: str, start: Callable[[], bool]) -> bool:
        if kind == "preview" and self._queue and self._queue[-1][0] == "preview":
            # Only the newest trailing preview matters.
            self._queue[-1] = (kind, start)
        else:
            self._queue.append((kind, start))
        self._pump()
        return True

    def _pump(self) -> None:
        while not self._running and self._queue:
            _, start = self._queue.popleft()
            start()

    # ------------------------------------------------------------- actions
    def probe(self, quiet: bool = False) -> bool:
        """Look for the receiver. ``quiet`` is for background re-detection:
        failures are only logged, and an unchanged result is not re-logged."""

        def work() -> list[DeviceInfo]:
            infos = probe_devices()
            lines = [
                "检测：%s PID %04X 接口 %s 固件 %s 可用 %s%s"
                % (
                    info.product,
                    info.product_id,
                    info.interface,
                    info.firmware or "-",
                    info.supported,
                    f"（{info.error}）" if info.error else "",
                )
                for info in infos
            ] or ["检测：没有找到 Sony 手柄接口"]
            if not quiet or lines != self._last_probe_lines:
                for line in lines:
                    log.info(line)
            self._last_probe_lines = lines
            return infos

        def failed(message: str) -> None:
            log.info("后台检测失败：%s", message)

        return self._enqueue(
            "probe",
            lambda: self._submit(
                work,
                self.probe_done.emit,
                failed if quiet else None,
                quiet_busy=quiet,
                name="检测",
            ),
        )

    def connect(self, info: DeviceInfo) -> bool:
        def work() -> tuple[DeviceInfo, dict[str, Any], str, dict[str, Any]]:
            device = open_device(info.path)
            try:
                result = info, read_config(device), read_firmware(device), read_status(device)
            finally:
                device.close()
            log.info(
                "读取配置：%s 固件 %s · %s",
                info.product,
                result[2] or info.firmware or "-",
                config_text(result[1]),
            )
            return result

        def done(result: tuple[DeviceInfo, dict[str, Any], str, dict[str, Any]]) -> None:
            self.info, self.config = result[0], result[1]
            self._battery.watch(result[0].path)
            self.connected.emit(*result)

        return self._enqueue("connect", lambda: self._submit(work, done, name="读取配置"))

    def refresh_status(self) -> bool:
        """Quiet poll: skipped (not queued) while other work is pending."""
        if not self.info or not self.idle:
            return False
        info = self.info

        def work() -> dict[str, Any]:
            device = open_device(info.path)
            try:
                return read_status(device)
            finally:
                device.close()

        return self._submit(
            work,
            self.status_read.emit,
            self.status_failed.emit,
            quiet_busy=True,
            name="状态",
        )

    def apply(self, config: dict[str, Any], save: bool, reconnect: bool = False) -> bool:
        if not self.info:
            return False
        config = dict(config)
        return self._enqueue("apply", lambda: self._start_apply(config, save, reconnect))

    def _start_apply(self, config: dict[str, Any], save: bool, reconnect: bool) -> bool:
        info = self.info
        if info is None:
            return False
        before = dict(self.config) if self.config else None

        def work() -> ApplyResult:
            _ensure_writable(info)
            device = open_device(info.path)
            try:
                fresh = write_config(device, config, save=save)
            finally:
                device.close()
            log.info(
                "%s配置：改动 %s · 结果 %s",
                "保存" if save else "应用",
                ",".join(changed_keys(before, fresh)) or "无",
                config_text(fresh),
            )

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

        return self._submit(work, done, name="保存" if save else "应用")

    def preview(self, config: dict[str, Any]) -> bool:
        """Write config to the receiver's RAM only (no flash save)."""
        if not self.info:
            return False
        config = dict(config)
        return self._enqueue("preview", lambda: self._start_preview(config))

    def _start_preview(self, config: dict[str, Any]) -> bool:
        info = self.info
        if info is None:
            return False
        before = dict(self.config) if self.config else None

        def work() -> dict[str, Any]:
            _ensure_writable(info)
            device = open_device(info.path)
            try:
                fresh = write_config(device, config, save=False)
            finally:
                device.close()
            log.info(
                "试用（未保存）：与已保存值相比 %s",
                ",".join(changed_keys(before, fresh)) or "无差异",
            )
            return fresh

        return self._submit(
            work,
            self.preview_done.emit,
            self.preview_failed.emit,
            quiet_busy=True,
            name="试用",
        )

    def test_rumble(self) -> bool:
        """Short classic-rumble pulse so the rumble strength can be felt."""
        if not self.info:
            return False
        info = self.info

        def work() -> None:
            device = open_device(info.path)
            try:
                play_test_rumble(device)
            finally:
                device.close()
            log.info("试普通震动")

        def failed(message: str) -> None:
            self.error.emit(f"试普通震动失败：{message}")

        return self._enqueue(
            "rumble",
            lambda: self._submit(work, lambda _: None, failed, quiet_busy=True, name="试震动"),
        )

    def test_haptics(self) -> bool:
        """Short HD-haptics pulse so the HD gain can be felt without a game."""
        if not self.info:
            return False
        info = self.info

        def work() -> None:
            # The handle is only needed to hand the actuators back from the
            # motors; if it cannot be opened, play anyway.
            try:
                device = open_device(info.path)
            except Ds5Error:
                log.info("试 HD 触觉：打不开设备，直接播放")
                log.info("试 HD 触觉：%s", play_test_haptics())
                return
            try:
                log.info("试 HD 触觉：%s", play_test_haptics(device))
            finally:
                device.close()

        def failed(message: str) -> None:
            self.error.emit(f"试 HD 触觉失败：{message}")

        return self._enqueue(
            "haptics",
            lambda: self._submit(work, lambda _: None, failed, quiet_busy=True, name="试触觉"),
        )

    def claim_lights(self) -> bool:
        """Stop the pad's "unclaimed" blink by taking the LEDs over.

        Best effort: a pad that ignores it just keeps blinking, which is what
        would have happened anyway, so a failure here is not worth a toast.
        """
        if not self.info:
            return False
        info = self.info

        def work() -> None:
            device = open_device(info.path)
            try:
                report = claim_lights_report()
                # The pad latches ResetLights on a pulse; a couple of repeats
                # cover a dropped BT frame right after connecting.
                for _ in range(3):
                    device.write(report)
                    time.sleep(0.05)
            finally:
                device.close()
            log.info("已接管手柄灯光")

        return self._enqueue(
            "lights",
            lambda: self._submit(
                work, lambda _: None, lambda message: log.info("接管灯光失败：%s", message),
                quiet_busy=True, name="接管灯光",
            ),
        )

    def write_now(self, config: dict[str, Any]) -> bool:
        """Blocking RAM write used on quit to drop unsaved previews."""
        self._queue.clear()
        self.pool.waitForDone(2000)
        info = self.info
        if info is None or not firmware_writable(info.firmware):
            return False
        try:
            device = open_device(info.path)
            try:
                fresh = write_config(device, config, save=False)
            finally:
                device.close()
        except (Ds5Error, OSError) as exc:
            log.warning("恢复已保存的设置失败：%s", exc)
            return False
        ok = configs_equal(fresh, config)
        log.info("已把接收器恢复为保存的设置（核对%s）", "一致" if ok else "不一致")
        return ok

    def reconnect(self) -> bool:
        if not self.info:
            return False

        def start() -> bool:
            info = self.info
            if info is None:
                return False

            def work() -> tuple[DeviceInfo, dict[str, Any], str, dict[str, Any]]:
                log.info("手动重连 USB")
                self._battery.watch(None)
                time.sleep(0.45)
                return _reconnect_and_collect(info.path)

            def done(result: tuple[DeviceInfo, dict[str, Any], str, dict[str, Any]]) -> None:
                self.info, self.config = result[0], result[1]
                self._battery.watch(result[0].path)
                self.connected.emit(*result)

            return self._submit(work, done, name="重连")

        return self._enqueue("reconnect", start)

    def watch_battery(self, path: bytes | None) -> None:
        self._battery.watch(path)

    def start_rate(self, path: bytes) -> None:
        self._rate.start(path)

    def stop_rate(self) -> None:
        self._rate.stop()

    def shutdown(self) -> None:
        self._queue.clear()
        self._rate.stop()
        self._battery.stop()

    def reset_defaults(self) -> bool:
        from .protocol import DEFAULTS, normalize_config

        return self.apply(normalize_config(DEFAULTS), save=True)
