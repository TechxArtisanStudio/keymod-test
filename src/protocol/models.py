"""协议层数据模型"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DeviceInfo:
    """BLE 设备信息"""
    address: str
    name: Optional[str] = None
    rssi: int = 0
    last_seen: float = 0.0

    def display_name(self) -> str:
        return self.name or "Unknown Device"


@dataclass
class ConnectionHistoryEntry:
    """连接历史条目"""
    address: str
    name: Optional[str] = None
    last_connected: float = 0.0

    def display_name(self) -> str:
        return self.name or "Unknown Device"


@dataclass
class CommandMeta:
    """CH9329 命令元数据（供 UI 自动生成面板）"""
    cmd: int
    name: str
    payload_desc: str
    resp_len: Optional[int]
    tooltip_rich: str
    example_request: bytes = b""
    example_response: bytes = b""
