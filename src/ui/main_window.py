"""主窗口"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QStatusBar, QMenuBar, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QAction
from ui.scan_panel import ScanPanel
from ui.command_panel import CommandPanel
from ui.widgets import StatusBadge
from ble.scanner import BLEScanner
from ble.client import BLEClient
from protocol import CH9329Frame, DeviceInfo, ConnectionHistoryEntry
from config import MAX_HISTORY_ENTRIES
from PyQt6.QtCore import QSettings
from config import APP_ORG, APP_NAME
import asyncio


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Keymod BLE Tester")
        self.setMinimumSize(900, 600)

        # BLE 组件
        self._scanner = BLEScanner()
        self._client = BLEClient()
        self._scan_task = None

        # 连接历史
        self._history: list[ConnectionHistoryEntry] = []
        self._load_history()

        # UI
        self._setup_ui()
        self._setup_signals()
        self._setup_statusbar()

        # 加载历史到扫描面板
        self._scan_panel.set_history(self._history)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 主分割器（上下）
        self._splitter = QSplitter(Qt.Orientation.Vertical)

        # 上部：扫描面板（较小）
        self._scan_panel = ScanPanel()
        self._splitter.addWidget(self._scan_panel)

        # 下部：命令面板（默认可见，串口调试助手风格）
        self._command_panel = CommandPanel()
        self._command_panel.setVisible(True)  # 默认可见
        self._splitter.addWidget(self._command_panel)

        # 设置初始大小：扫描面板 150px，命令面板占剩余空间
        self._splitter.setSizes([150, 500])

        layout.addWidget(self._splitter)

        # 菜单栏
        self._setup_menubar()

    def _setup_menubar(self):
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar {
                background-color: #2D2D2D;
                color: #CCCCCC;
                border-bottom: 1px solid #3E3E3E;
            }
            QMenuBar::item:selected {
                background-color: #007ACC;
            }
            QMenu {
                background-color: #252526;
                color: #D4D4D4;
                border: 1px solid #3E3E3E;
            }
            QMenu::item:selected {
                background-color: #007ACC;
            }
        """)

        # 文件菜单
        file_menu = menubar.addMenu("文件")

        export_action = QAction("导出日志", self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self._on_export_log)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 历史菜单
        history_menu = menubar.addMenu("历史")

        clear_action = QAction("清除连接历史", self)
        clear_action.triggered.connect(self._on_clear_history)
        history_menu.addAction(clear_action)

    def _setup_statusbar(self):
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._statusbar.setStyleSheet("background-color: #007ACC; color: white;")

        self._status_badge = StatusBadge("Disconnected", "#F44747")
        self._statusbar.addPermanentWidget(self._status_badge)

    def _setup_signals(self):
        # 扫描面板信号
        self._scan_panel.scan_requested.connect(self._on_scan_requested)
        self._scan_panel.stop_requested.connect(self._on_stop_requested)
        self._scan_panel.connect_requested.connect(self._on_connect_requested)

        # 命令面板信号
        self._command_panel.send_requested.connect(self._on_send_requested)

        # BLE 客户端信号
        self._client.connected.connect(self._on_connected)
        self._client.disconnected.connect(self._on_disconnected)
        self._client.response_received.connect(self._on_response_received)
        self._client.error_occurred.connect(self._on_error)

    # ──────────────────────────────────────────────
    # 扫描相关
    # ──────────────────────────────────────────────

    def _on_scan_requested(self, duration: float):
        """开始扫描"""
        self._scan_task = asyncio.create_task(self._do_scan(duration))

    async def _do_scan(self, duration: float):
        """执行扫描（异步）"""
        try:
            devices = await self._scanner.start(duration)
            self._scan_panel.update_devices(devices)
        except Exception as e:
            self._on_error(f"扫描失败: {str(e)}")
        finally:
            self._scan_panel.set_scanning(False)

    def _on_stop_requested(self):
        """停止扫描"""
        asyncio.create_task(self._scanner.stop())

    # ──────────────────────────────────────────────
    # 连接相关
    # ──────────────────────────────────────────────

    def _on_connect_requested(self, address: str):
        """请求连接"""
        asyncio.create_task(self._do_connect(address))

    async def _do_connect(self, address: str):
        """执行连接（异步）"""
        self._status_badge.set_state("Connecting...", "#DCDCAA")
        self._scan_panel.set_connected(True)

        success = await self._client.connect(address)
        if not success:
            self._status_badge.set_state("Disconnected", "#F44747")
            self._scan_panel.set_connected(False)

    def _on_connected(self):
        """连接成功"""
        addr = self._client._client.address if self._client._client else "Unknown"
        self._status_badge.set_state(f"Connected: {addr}", "#4EC9B0")
        self._scan_panel.set_connected(True)

        # 显示命令面板
        self._command_panel.setVisible(True)
        self._command_panel.append_sys(f"已连接到 {addr}")

        # 保存到历史
        self._save_to_history(addr)

    def _on_disconnected(self):
        """断开连接"""
        self._status_badge.set_state("Disconnected", "#F44747")
        self._scan_panel.set_connected(False)

        # 命令面板保持可见
        self._command_panel.append_sys("连接已断开")

    # ──────────────────────────────────────────────
    # 收发相关
    # ──────────────────────────────────────────────

    def _on_send_requested(self, data: bytes):
        """发送数据"""
        try:
            frame = CH9329Frame.from_bytes(data)
            asyncio.create_task(self._do_send(frame))
        except Exception as e:
            self._command_panel.append_err(f"帧构建失败: {str(e)}")

    async def _do_send(self, frame: CH9329Frame):
        """执行发送（异步）"""
        success = await self._client.send(frame)
        if not success:
            self._command_panel.append_err("发送失败")

    def _on_response_received(self, frame: CH9329Frame):
        """收到响应"""
        data = frame.to_bytes()
        self._command_panel.append_rx(data)

        # 解析响应内容
        self._parse_response(frame)

    def _parse_response(self, frame: CH9329Frame):
        """解析响应帧并显示字段含义"""
        # 提取原始命令（响应命令 = 原命令 | 0x80 或 | 0xC0）
        original_cmd = frame.cmd & 0x7F
        is_error = bool(frame.cmd & 0x40)

        # 状态码映射
        status_codes = {
            0x00: "成功",
            0xE1: "超时",
            0xE2: "帧头错误",
            0xE3: "不支持的命令",
            0xE4: "校验和错误",
            0xE5: "参数错误",
            0xE6: "帧/执行错误",
            0xE9: "Flash 页擦除失败",
            0xEA: "Flash 字编程失败",
            0xEB: "Flash 写回验证失败",
        }

        # 显示帧结构
        hex_str = ' '.join(f"{b:02X}" for b in frame.to_bytes())
        self._command_panel.append_sys(f"帧: {hex_str}")
        self._command_panel.append_sys(
            f"  Header=57AB, Addr=0x{frame.addr:02X}, "
            f"Cmd=0x{frame.cmd:02X} (响应 0x{original_cmd:02X}), "
            f"Len={len(frame.payload)}"
        )

        if is_error:
            self._command_panel.append_sys("  类型: 错误响应")

        # 解析 payload
        if len(frame.payload) == 0:
            self._command_panel.append_sys("  Payload: (空)")
            return

        # 第一个字节通常是状态码
        status = frame.payload[0]
        status_text = status_codes.get(status, f"未知(0x{status:02X})")
        self._command_panel.append_sys(f"  Status: 0x{status:02X} ({status_text})")

        # 按命令类型解析
        if original_cmd == 0x01 and len(frame.payload) >= 4:
            # Get Info 响应
            hw = frame.payload[1] if len(frame.payload) > 1 else 0
            usb = frame.payload[2] if len(frame.payload) > 2 else 0
            led = frame.payload[3] if len(frame.payload) > 3 else 0
            fw = frame.payload[4] if len(frame.payload) > 4 else 0

            hw_names = {0x01: "KVM-GO", 0x02: "MiniKVM", 0x03: "KeyMod"}
            hw_name = hw_names.get(hw, f"Unknown(0x{hw:02X})")

            self._command_panel.append_sys(
                f"  HW=0x{hw:02X} ({hw_name}), "
                f"USB={'已连接' if usb else '未连接'}, "
                f"LED=0x{led:02X}, FW=v{fw}"
            )
        else:
            # 通用 payload 显示
            payload_hex = ' '.join(f"{b:02X}" for b in frame.payload)
            self._command_panel.append_sys(f"  Payload: {payload_hex}")

    def _on_error(self, msg: str):
        """错误处理"""
        self._command_panel.append_err(msg)
        self._status_badge.set_state("Error", "#F44747")

    # ──────────────────────────────────────────────
    # 历史管理
    # ──────────────────────────────────────────────

    def _load_history(self):
        """从 QSettings 加载连接历史"""
        settings = QSettings(APP_ORG, APP_NAME)
        count = settings.beginReadArray("connections")
        for i in range(count):
            settings.setArrayIndex(i)
            entry = ConnectionHistoryEntry(
                address=settings.value("address", ""),
                name=settings.value("name"),
                last_connected=settings.value("last_connected", 0.0, type=float),
            )
            if entry.address:
                self._history.append(entry)
        settings.endArray()

    def _save_history(self):
        """保存连接历史到 QSettings"""
        settings = QSettings(APP_ORG, APP_NAME)
        settings.beginWriteArray("connections", len(self._history))
        for i, entry in enumerate(self._history):
            settings.setArrayIndex(i)
            settings.setValue("address", entry.address)
            settings.setValue("name", entry.name)
            settings.setValue("last_connected", entry.last_connected)
        settings.endArray()

    def _save_to_history(self, address: str):
        """保存/更新连接记录"""
        import time
        now = time.time()

        # 查找是否已存在
        for entry in self._history:
            if entry.address == address:
                entry.last_connected = now
                break
        else:
            # 新增
            self._history.insert(0, ConnectionHistoryEntry(
                address=address,
                name=None,
                last_connected=now,
            ))

        # 限制数量
        if len(self._history) > MAX_HISTORY_ENTRIES:
            self._history = self._history[:MAX_HISTORY_ENTRIES]

        # 按最近连接排序
        self._history.sort(key=lambda e: e.last_connected, reverse=True)

        # 保存并更新 UI
        self._save_history()
        self._scan_panel.set_history(self._history)

    def _on_clear_history(self):
        """清除连接历史"""
        self._history.clear()
        self._save_history()
        self._scan_panel.set_history(self._history)

    def _on_export_log(self):
        """导出日志"""
        self._command_panel.export_log()

    # ──────────────────────────────────────────────
    # 生命周期
    # ──────────────────────────────────────────────

    def closeEvent(self, event):
        """窗口关闭时清理"""
        asyncio.create_task(self._cleanup())
        event.accept()

    async def _cleanup(self):
        """清理资源"""
        await self._client.disconnect()
        await self._scanner.stop()
