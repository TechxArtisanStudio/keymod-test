"""Keymod BLE Tester — 常量与配置"""

# ──────────────────────────────────────────────
# BLE UUID
# ──────────────────────────────────────────────

# 常见 BLE 串口特征 UUID（按优先级依次尝试）
UART_SERVICE_UUIDS = [
    "6e400001-b5a3-f393-e0a9-e50e24dcca9e",   # Nordic UART
    "0000ffe0-0000-1000-8000-00805f9b34fb",   # HM-10 / 0xFFE0
    "0000fff0-0000-1000-8000-00805f9b34fb",   # 0xFFF0
]

UART_TX_CHAR_UUIDS = [
    "6e400002-b5a3-f393-e0a9-e50e24dcca9e",   # Nordic TX
    "0000ffe1-0000-1000-8000-00805f9b34fb",   # HM-10 TX
    "0000fff1-0000-1000-8000-00805f9b34fb",   # 0xFFF0 TX
]

UART_RX_CHAR_UUIDS = [
    "6e400003-b5a3-f393-e0a9-e50e24dcca9e",   # Nordic RX (notify)
    "0000ffe1-0000-1000-8000-00805f9b34fb",   # HM-10 RX
    "0000fff1-0000-1000-8000-00805f9b34fb",   # 0xFFF0 RX
]

# ──────────────────────────────────────────────
# 默认扫描参数
# ──────────────────────────────────────────────
DEFAULT_SCAN_DURATION = 5.0   # 秒
MAX_HISTORY_ENTRIES = 20

# ──────────────────────────────────────────────
# QSettings
# ──────────────────────────────────────────────
APP_ORG = "TechxArtisanStudio"
APP_NAME = "KeymodTester"
