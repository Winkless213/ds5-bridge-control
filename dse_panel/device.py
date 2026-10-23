"""设备发现与后台读写线程。

只使用 hidapi 的标准 DualSense 报文：读取 0x01，写入 0x02，读取特性报文 0x09/0x20。
对接收器不做任何厂商命令写入，避免干扰原生连接。
"""

from __future__ import annotations

import queue
import time
from dataclasses import dataclass, field

import hid
from PySide6.QtCore import QThread, Signal

from .protocol import (
    FEATURE_FIRMWARE,
    FEATURE_PAIRING,
    InputState,
    build_output_report,
    parse_firmware_info,
    parse_input_report,
    parse_pairing_info,
)

SONY_VID = 0x054C
DUALSENSE_PIDS = (0x0DF2, 0x0CE6)  # Edge / 普通 DualSense
GAMEPAD_USAGE_PAGE = 0x01
GAMEPAD_USAGE = 0x05


@dataclass
class DeviceInfo:
    path: str = ""
    product: str = ""
    manufacturer: str = ""
    firmware_build: str = ""
    firmware_hw: int = 0
    firmware_fw: int = 0
    mac: str = ""
    pid: int = 0


@dataclass
class _Rumble:
    weak: int
    strong: int
    until: float
    next_send: float = 0.0


class DeviceWorker(QThread):
    stateChanged = Signal(object)  # InputState
    statusChanged = Signal(bool, str)  # connected, message
    infoChanged = Signal(object)  # DeviceInfo
    logMessage = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._stop = False
        self._commands: queue.Queue[tuple] = queue.Queue()
        self._device: hid.device | None = None
        self._rumble: _Rumble | None = None
        self._last_emit = 0.0
        self._latest: InputState | None = None
        self._info = DeviceInfo()
        self._retry_at = 0.0
        self._connected = False

    # ---- UI 侧调用 ----
    def submit_rumble(self, weak: int, strong: int, duration_ms: int) -> None:
        self._commands.put(("rumble", weak, strong, duration_ms))

    def stop_rumble(self) -> None:
        self._commands.put(("stop_rumble",))

    def submit_output(self, **kwargs) -> None:
        self._commands.put(("output", kwargs))

    def shutdown(self) -> None:
        self._stop = True
        self._commands.put(("noop",))

    @property
    def latest_state(self) -> InputState | None:
        return self._latest

    @property
    def info(self) -> DeviceInfo:
        return self._info

    # ---- 线程主体 ----
    def run(self) -> None:  # noqa: C901 - 轮询循环保持直白
        while not self._stop:
            if self._device is None:
                if time.monotonic() < self._retry_at:
                    time.sleep(0.2)
                    continue
                if not self._connect():
                    self._retry_at = time.monotonic() + 1.5
                    continue

            try:
                data = self._device.read(64, 10)
            except (OSError, ValueError) as exc:
                self._disconnect(f"读取失败：{exc}")
                continue

            now = time.monotonic()
            if data:
                state = parse_input_report(data)
                if state is not None:
                    self._latest = state
                    if now - self._last_emit >= 0.02:
                        self._last_emit = now
                        self.stateChanged.emit(state)

            self._service_commands(now)
            self._service_rumble(now)

        self._close_device()

    def _connect(self) -> bool:
        try:
            for pid in DUALSENSE_PIDS:
                for entry in hid.enumerate(SONY_VID, pid):
                    if entry.get("usage_page") != GAMEPAD_USAGE_PAGE or entry.get("usage") != GAMEPAD_USAGE:
                        continue
                    dev = hid.device()
                    dev.open_path(entry["path"])
                    dev.set_nonblocking(0)
                    self._device = dev
                    self._info = DeviceInfo(
                        path=self._decode_path(entry["path"]),
                        product=entry.get("product_string") or "",
                        manufacturer=entry.get("manufacturer_string") or "",
                        pid=pid,
                    )
                    self._read_features()
                    self._connected = True
                    self.infoChanged.emit(self._info)
                    self.statusChanged.emit(True, f"已连接：{self._info.product or 'DualSense'}")
                    self.logMessage.emit("设备已连接")
                    return True
        except Exception as exc:  # hidapi 在拔插瞬间会抛 OSError
            self._close_device()
            self.logMessage.emit(f"连接失败：{exc}")
        return False

    def _read_features(self) -> None:
        assert self._device is not None
        try:
            fw = parse_firmware_info(self._device.get_feature_report(FEATURE_FIRMWARE, 64))
            if fw:
                self._info.firmware_build = str(fw.get("build", ""))
                self._info.firmware_hw = int(fw.get("hw_version", 0))
                self._info.firmware_fw = int(fw.get("fw_version", 0))
        except OSError:
            pass
        try:
            self._info.mac = parse_pairing_info(self._device.get_feature_report(FEATURE_PAIRING, 20))
        except OSError:
            pass

    def _service_commands(self, now: float) -> None:
        while True:
            try:
                cmd = self._commands.get_nowait()
            except queue.Empty:
                return
            if cmd[0] == "noop":
                continue
            if self._device is None:
                continue
            try:
                if cmd[0] == "rumble":
                    _, weak, strong, duration_ms = cmd
                    self._write(build_output_report(weak, strong))
                    self._rumble = _Rumble(weak, strong, now + max(0.05, duration_ms / 1000.0), now)
                elif cmd[0] == "stop_rumble":
                    self._rumble = None
                    self._write(build_output_report(0, 0))
                elif cmd[0] == "output":
                    self._write(build_output_report(**cmd[1]))
            except (OSError, ValueError) as exc:
                self._disconnect(f"写入失败：{exc}")
                return

    def _service_rumble(self, now: float) -> None:
        if self._device is None or self._rumble is None:
            return
        if now >= self._rumble.until:
            self._rumble = None
            try:
                self._write(build_output_report(0, 0))
            except (OSError, ValueError) as exc:
                self._disconnect(f"写入失败：{exc}")
            return
        if now >= self._rumble.next_send:
            self._rumble.next_send = now + 0.02
            try:
                self._write(build_output_report(self._rumble.weak, self._rumble.strong))
            except (OSError, ValueError) as exc:
                self._disconnect(f"写入失败：{exc}")

    def _write(self, report: bytes) -> None:
        if self._device is not None:
            self._device.write(report)

    def _disconnect(self, message: str) -> None:
        was_connected = self._connected
        self._connected = False
        self._close_device()
        self._retry_at = time.monotonic() + 1.0
        if was_connected:
            self.statusChanged.emit(False, message)
            self.logMessage.emit(message)

    def _close_device(self) -> None:
        if self._device is not None:
            try:
                self._device.close()
            except Exception:
                pass
            self._device = None

    @staticmethod
    def _decode_path(path) -> str:
        if isinstance(path, bytes):
            return path.decode("utf-8", "replace")
        return str(path)


def enumerate_devices() -> list[dict]:
    """只读枚举，用于 UI 在后台线程启动前显示占位信息。"""
    found: list[dict] = []
    for pid in DUALSENSE_PIDS:
        try:
            for entry in hid.enumerate(SONY_VID, pid):
                if entry.get("usage_page") == GAMEPAD_USAGE_PAGE and entry.get("usage") == GAMEPAD_USAGE:
                    found.append(entry)
        except Exception:
            continue
    return found
