"""BLE 客户端"""
import asyncio
from typing import Optional, Callable
from PyQt6.QtCore import QObject, pyqtSignal
from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
from protocol.ch9329 import CH9329Frame
from config import UART_SERVICE_UUIDS, UART_TX_CHAR_UUIDS, UART_RX_CHAR_UUIDS


class BLEClient(QObject):
    """BLE 客户端（连接/断开/收发）"""

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

    @property
    def is_connected(self) -> bool:
        return self._connected and self._client and self._client.is_connected

    async def connect(self, address: str) -> bool:
        """连接到 BLE 设备"""
        try:
            self._client = BleakClient(address, disconnected_callback=self._on_disconnect)

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
                    self.debug_info.emit(f"✓ Notify 已启用: {self._rx_char.uuid}")
                except Exception as e:
                    self.debug_info.emit(f"✗ Notify 启用失败: {e}")
                    raise

            self._connected = True
            self.debug_info.emit(f"✓ 连接成功，MTU={self._client.mtu_size}")
            self.connected.emit()
            return True

        except Exception as e:
            self.error_occurred.emit(f"连接失败: {str(e)}")
            return False

    async def _discover_characteristics(self) -> bool:
        """发现 UART 服务和特征"""
        if not self._client:
            return False

        services = self._client.services

        # 按优先级尝试已知 UUID
        for svc_uuid in UART_SERVICE_UUIDS:
            service = services.get_service(svc_uuid)
            if not service:
                continue

            # 找到服务，查找 TX/RX 特征
            for tx_uuid, rx_uuid in zip(UART_TX_CHAR_UUIDS, UART_RX_CHAR_UUIDS):
                tx_char = service.get_characteristic(tx_uuid)
                rx_char = service.get_characteristic(rx_uuid)
                if tx_char and rx_char:
                    self._tx_char = tx_char
                    self._rx_char = rx_char
                    self.debug_info.emit(f"TX: {tx_char.uuid}\nRX: {rx_char.uuid}")
                    return True

        # 未找到已知服务，尝试自动发现（遍历所有服务）
        for service in services:
            for char in service.characteristics:
                props = char.properties
                if "write" in props or "write-without-response" in props:
                    if self._tx_char is None:
                        self._tx_char = char
                        self.debug_info.emit(f"Auto TX: {char.uuid} (service: {service.uuid})")
                if "notify" in props or "indicate" in props:
                    if self._rx_char is None:
                        self._rx_char = char
                        self.debug_info.emit(f"Auto RX: {char.uuid} (service: {service.uuid})")

        return self._tx_char is not None and self._rx_char is not None

    def _on_disconnect(self, client: BleakClient):
        """断开连接回调"""
        self._connected = False
        self.disconnected.emit()

    def _on_notify(self, sender: BleakGATTCharacteristic, data: bytearray):
        """Notify 回调（收到数据）"""
        self.debug_info.emit(f"收到 {len(data)} 字节: {data.hex()}")
        try:
            frame = CH9329Frame.from_bytes(bytes(data))
            self.response_received.emit(frame)
        except Exception as e:
            # 解析失败，发射原始字节（用特殊标记）
            self.error_occurred.emit(f"帧解析失败: {e} | 原始数据: {data.hex()}")

    async def send(self, frame: CH9329Frame) -> bool:
        """发送命令帧"""
        if not self.is_connected or not self._tx_char:
            self.error_occurred.emit("设备未连接")
            return False

        try:
            data = frame.to_bytes()
            self.debug_info.emit(f"发送 {len(data)} 字节到 {self._tx_char.uuid}")
            await self._client.write_gatt_char(self._tx_char, data, response=False)
            self.debug_info.emit("✓ 发送成功")
            return True
        except Exception as e:
            self.error_occurred.emit(f"发送失败: {str(e)}")
            return False

    async def disconnect(self):
        """断开连接"""
        if self._client and self._client.is_connected:
            await self._client.disconnect()
        self._connected = False
        self._client = None
        self._tx_char = None
        self._rx_char = None
