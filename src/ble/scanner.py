"""BLE 扫描器"""
import asyncio
from typing import AsyncGenerator
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from ..protocol.models import DeviceInfo


class BLEScanner:
    """BLE 设备扫描器"""

    def __init__(self):
        self._scanner: BleakScanner | None = None
        self._devices: dict[str, DeviceInfo] = {}
        self._scanning = False

    async def start(self, duration: float = 5.0) -> list[DeviceInfo]:
        """扫描 BLE 设备（指定时长）"""
        self._devices.clear()
        self._scanning = True

        def callback(device: BLEDevice, adv: AdvertisementData):
            if device.address in self._devices:
                # 更新 RSSI
                self._devices[device.address].rssi = adv.rssi
                self._devices[device.address].last_seen = asyncio.get_event_loop().time()
            else:
                self._devices[device.address] = DeviceInfo(
                    address=device.address,
                    name=device.name,
                    rssi=adv.rssi,
                    last_seen=asyncio.get_event_loop().time(),
                )

        self._scanner = BleakScanner(detection_callback=callback)
        await self._scanner.start()
        await asyncio.sleep(duration)
        await self._scanner.stop()
        self._scanning = False

        # 按 RSSI 降序排序
        return sorted(self._devices.values(), key=lambda d: d.rssi, reverse=True)

    async def stop(self):
        """停止扫描"""
        if self._scanner and self._scanning:
            await self._scanner.stop()
            self._scanning = False

    @property
    def is_scanning(self) -> bool:
        return self._scanning
