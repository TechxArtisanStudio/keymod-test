"""BLE 客户端"""
import asyncio
import queue
import logging
from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
from protocol.ch9329 import CH9329Frame
from config import UART_SERVICE_UUIDS, UART_TX_CHAR_UUIDS, UART_RX_CHAR_UUIDS

logger = logging.getLogger(__name__)


class _SignalBridge(QObject):
    """线程安全的信号桥

    Bleak 的 notify 回调可能在 CoreBluetooth 的后台线程触发，
    直接 emit pyqtSignal 在 macOS 上会导致 segfault。
    这个桥通过一个线程安全队列 + 主线程 QTimer 轮询来保证安全。
    """
    _emit_response = pyqtSignal(object)
    _emit_error = pyqtSignal(str)
    _emit_debug = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._queue: queue.Queue = queue.Queue()
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._drain)
        self._timer.start()

    def enqueue(self, signal, *args):
        try:
            self._queue.put_nowait((signal, args))
        except queue.Full:
            pass

    def _drain(self):
        count = 0
        while count < 20:
            try:
                signal, args = self._queue.get_nowait()
                signal.emit(*args)
                count += 1
            except queue.Empty:
                break
            except Exception as e:
                logger.debug(f"Signal bridge drain error: {e}")
                break

    def stop(self):
        self._timer.stop()


class BLEClient(QObject):
    """BLE 客户端（连接/断开/收发）

    不使用 Bleak 的 disconnected_callback（在 macOS 上会导致崩溃），
    改用 QTimer 轮询连接状态来检测断开。
    """

    connected = pyqtSignal()
    disconnected = pyqtSignal()
    response_received = pyqtSignal(object)  # CH9329Frame
    error_occurred = pyqtSignal(str)
    debug_info = pyqtSignal(str)  # 调试信息

    def __init__(self):
        super().__init__()
        self._client: Optional[BleakClient] = None
        self._tx_char: Optional[BleakGATTCharacteristic] = None
        self._rx_char: Optional[BleakGATTCharacteristic] = None
        self._connected = False
        self._was_connected = False  # 用于检测断开
        self._notify_active = False  # 标记 notify 是否激活
        self._sending = False  # 标记是否正在发送数据（防止轮询冲突）
        self._poll_disabled_until = 0.0  # 临时禁用轮询的时间戳
        self._device_address = ""  # 缓存设备地址，避免访问 BleakClient
        # 信号桥：从后台线程安全地发射信号到主线程
        self._bridge = _SignalBridge()
        self._bridge._emit_response.connect(self.response_received)
        self._bridge._emit_error.connect(self.error_occurred)
        self._bridge._emit_debug.connect(self.debug_info)
        # 连接状态轮询定时器
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(200)  # 200ms 检查一次
        self._poll_timer.timeout.connect(self._poll_connection)
        self._poll_timer.start()

    @property
    def is_connected(self) -> bool:
        return self._connected and self._client and self._client.is_connected

    def _poll_connection(self):
        """在主线程中轮询连接状态，检测断开

        发送数据期间跳过轮询，避免在 CoreBluetooth 忙时访问连接状态
        导致线程冲突。
        """
        import time

        if not self._connected:
            return

        # 发送数据期间不检查，避免与 write_gatt_char 冲突
        if self._sending:
            return

        # 临时禁用轮询（例如发送名称修改命令后）
        if time.time() < self._poll_disabled_until:
            return

        # 检查 BleakClient 是否还连接着
        # 所有访问 self._client 的地方都用 try/except 包裹
        try:
            client = self._client
            if client is None:
                return

            # 缓存到局部变量，避免多次访问
            try:
                is_connected = client.is_connected
            except Exception:
                # is_connected 可能抛出异常（设备突然断开）
                is_connected = False

            if not is_connected:
                # 设备已断开 — 先清理状态，再发射信号
                self._connected = False
                self._notify_active = False
                self._tx_char = None
                self._rx_char = None
                try:
                    self.disconnected.emit()
                except Exception:
                    pass
        except Exception:
            # 彻底忽略，防止轮询本身导致闪退
            pass

    def disable_polling_for(self, seconds: float):
        """临时禁用连接轮询（用于名称修改等会导致设备重启的命令）"""
        import time
        self._poll_disabled_until = time.time() + seconds

    async def connect(self, address: str) -> bool:
        """连接到 BLE 设备

        注意：不在这里发射 debug_info 信号，因为在 macOS 上 CoreBluetooth
        的操作可能使用后台线程，在此期间发射 Qt 信号会导致线程冲突。
        调试信息由调用方在安全的上下文中发射。
        """
        try:
            # 缓存设备地址
            self._device_address = address

            # 不使用 disconnected_callback，避免 macOS 崩溃
            self._client = BleakClient(address)

            await self._client.connect()

            # 发现服务和特征
            if not await self._discover_characteristics():
                await self.disconnect()
                self.error_occurred.emit("未找到兼容的 UART 服务/特征")
                return False

            # 启用 notify（RX 特征）
            if self._rx_char:
                try:
                    await self._client.start_notify(self._rx_char, self._on_notify)
                    self._notify_active = True
                    # debug_info 由调用方发射
                except Exception as e:
                    # debug_info 由调用方发射
                    raise

            self._connected = True
            self._was_connected = True
            # debug_info 由调用方发射
            self.connected.emit()
            return True

        except Exception as e:
            self.error_occurred.emit(f"连接失败: {str(e)}")
            return False

    async def _discover_characteristics(self) -> bool:
        """发现 UART 服务和特征

        注意：不在这里发射 debug_info 信号，由调用方发射。
        """
        if not self._client:
            return False

        services = self._client.services

        for svc_uuid in UART_SERVICE_UUIDS:
            service = services.get_service(svc_uuid)
            if not service:
                continue

            for tx_uuid, rx_uuid in zip(UART_TX_CHAR_UUIDS, UART_RX_CHAR_UUIDS):
                tx_char = service.get_characteristic(tx_uuid)
                rx_char = service.get_characteristic(rx_uuid)
                if tx_char and rx_char:
                    self._tx_char = tx_char
                    self._rx_char = rx_char
                    # debug_info 由调用方发射
                    return True

        for service in services:
            for char in service.characteristics:
                props = char.properties
                if "write" in props or "write-without-response" in props:
                    if self._tx_char is None:
                        self._tx_char = char
                        # debug_info 由调用方发射
                if "notify" in props or "indicate" in props:
                    if self._rx_char is None:
                        self._rx_char = char
                        # debug_info 由调用方发射

        return self._tx_char is not None and self._rx_char is not None

    def _on_notify(self, sender: BleakGATTCharacteristic, data: bytearray):
        """Notify 回调 — 从 CoreBluetooth 后台线程调用，绝不直接操作 Qt

        所有访问 self 的地方都用 try/except 包裹，因为在 macOS 上
        CoreBluetooth 后台线程和主线程之间可能存在竞态条件。
        """
        try:
            # 缓存到局部变量，避免多次访问 self 属性
            notify_active = self._notify_active
            if not notify_active:
                return

            raw = bytes(data)

            frame = CH9329Frame.from_bytes(raw)

            # 再次检查标志，因为可能在处理过程中被停止
            # 使用缓存的 bridge 引用，避免访问 self._bridge
            if self._notify_active:
                bridge = self._bridge
                bridge.enqueue(bridge._emit_response, frame)
        except Exception:
            # 吞掉所有异常 — 后台线程中的异常无法安全传播
            # 也不能安全地访问 self 来发射错误信号
            pass

    async def send(self, frame: CH9329Frame) -> bool:
        """发送命令帧

        注意：不在这里发射 debug_info 信号，因为在 macOS 上 CoreBluetooth
        的 write_gatt_char 内部使用后台线程，在此期间发射 Qt 信号会导致
        线程冲突和 segfault。调试信息由调用方在安全的上下文中发射。
        """
        if not self.is_connected or not self._tx_char:
            self.error_occurred.emit("设备未连接")
            return False

        self._sending = True
        try:
            data = frame.to_bytes()
            # 不在此处发射 debug_info — 由调用方发射
            await self._client.write_gatt_char(self._tx_char, data, response=False)
            return True
        except Exception as e:
            error_msg = str(e)
            if "not connected" in error_msg.lower() or "disconnected" in error_msg.lower():
                self._connected = False
            self.error_occurred.emit(f"发送失败: {error_msg}")
            return False
        finally:
            self._sending = False

    async def disconnect(self):
        """断开连接

        顺序很重要：先停止 notify（防止后台线程回调），
        再清理状态，最后断开连接。
        """
        # 1. 先禁用 notify 标志，防止后台线程回调访问 self
        self._notify_active = False
        self._connected = False

        # 2. 缓存 client 引用，然后清空
        client = self._client
        rx_char = self._rx_char
        self._client = None
        self._tx_char = None
        self._rx_char = None
        self._device_address = ""  # 清空缓存的地址

        # 3. 停止 notify 监听（使用缓存的引用）
        if client and rx_char:
            try:
                await client.stop_notify(rx_char)
            except Exception:
                pass

        # 4. 断开连接
        if client:
            try:
                # 再次检查连接状态
                is_connected = False
                try:
                    is_connected = client.is_connected
                except Exception:
                    pass

                if is_connected:
                    await client.disconnect()
            except Exception:
                pass

    @property
    def device_address(self) -> str:
        """获取缓存的设备地址（避免访问 BleakClient）"""
        return self._device_address

    def cleanup(self):
        """清理资源"""
        self._bridge.stop()
        self._poll_timer.stop()
