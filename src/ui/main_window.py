"""主窗口"""
import sys
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QStatusBar, QMenuBar, QMenu, QTabWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QAction
from ui.scan_panel import ScanPanel
from ui.command_panel import CommandPanel
from ui.ble_name_panel import BLENamePanel
from ui.ecm_test_panel import ECMTestPanel
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

        # 顶部：扫描面板（全局共享）
        self._scan_panel = ScanPanel()
        layout.addWidget(self._scan_panel)

        # 下部：标签页切换
        self._tab_widget = QTabWidget()
        self._tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #3E3E3E;
                background-color: #1E1E1E;
            }
            QTabBar::tab {
                background-color: #2D2D2D;
                color: #CCCCCC;
                padding: 8px 16px;
                border: 1px solid #3E3E3E;
                border-bottom: none;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #1E1E1E;
                color: #FFFFFF;
                border-bottom: 2px solid #007ACC;
            }
            QTabBar::tab:hover {
                background-color: #3E3E42;
            }
        """)

        # Tab 0: 命令调试
        self._command_panel = CommandPanel()
        self._tab_widget.addTab(self._command_panel, "命令调试")

        # Tab 1: BLE 名称修改
        self._ble_name_panel = BLENamePanel()
        self._tab_widget.addTab(self._ble_name_panel, "BLE 名称")

        # Tab 2: ECM 网络测试
        self._ecm_test_panel = ECMTestPanel()
        self._tab_widget.addTab(self._ecm_test_panel, "ECM 网络")

        layout.addWidget(self._tab_widget, stretch=1)

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
        self._scan_panel.disconnect_requested.connect(self._on_disconnect_requested)

        # 命令面板信号
        self._command_panel.send_requested.connect(self._on_send_requested)

        # BLE 名称面板信号
        self._ble_name_panel.send_requested.connect(self._on_send_requested)

        # ECM 测试面板信号
        self._ecm_test_panel.send_requested.connect(self._on_send_requested)

        # BLE 客户端信号 — 信号桥已处理线程安全，直接用默认连接
        self._client.connected.connect(self._on_connected)
        self._client.disconnected.connect(self._on_disconnected)
        self._client.response_received.connect(self._on_response_received)
        self._client.error_occurred.connect(self._on_error)
        self._client.debug_info.connect(self._on_debug_info)

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

    def _on_disconnect_requested(self):
        """请求断开连接"""
        asyncio.create_task(self._do_disconnect())

    async def _do_disconnect(self):
        """执行断开（异步）"""
        try:
            await self._client.disconnect()
        except Exception as e:
            self._on_error(f"断开异常: {str(e)}")

    # ──────────────────────────────────────────────
    # 连接相关
    # ──────────────────────────────────────────────

    def _on_connect_requested(self, address: str):
        """请求连接"""
        asyncio.create_task(self._do_connect(address))

    async def _do_connect(self, address: str):
        """执行连接（异步）

        调试信息在此处发射，而不是在 BLEClient.connect() 内部，
        因为在 macOS 上 CoreBluetooth 的操作使用后台线程，
        在此期间发射 Qt 信号会导致线程冲突和 segfault。
        """
        try:
            self._status_badge.set_state("Connecting...", "#DCDCAA")
            self._scan_panel.set_connected(True)

            success = await self._client.connect(address)

            if success:
                # 连接成功后发射调试信息
                try:
                    tx_uuid = self._client._tx_char.uuid if self._client._tx_char else "?"
                    rx_uuid = self._client._rx_char.uuid if self._client._rx_char else "?"
                    self._on_debug_info(f"TX: {tx_uuid}")
                    self._on_debug_info(f"RX: {rx_uuid}")
                    self._on_debug_info(f"✓ Notify 已启用: {rx_uuid}")
                    self._on_debug_info(f"✓ 连接成功，MTU={self._client._client.mtu_size if self._client._client else '?'}")
                except Exception:
                    pass
            else:
                self._status_badge.set_state("Disconnected", "#F44747")
                self._scan_panel.set_connected(False)
        except Exception as e:
            # 连接过程中的异常
            self._status_badge.set_state("Disconnected", "#F44747")
            self._scan_panel.set_connected(False)
            self._on_error(f"连接异常: {str(e)}")

    def _on_connected(self):
        """连接成功"""
        # 使用缓存的设备地址，避免访问 BleakClient
        addr = self._client.device_address or "Unknown"

        try:
            self._status_badge.set_state(f"Connected: {addr}", "#4EC9B0")
            self._scan_panel.set_connected(True, addr)
            self._ble_name_panel.set_connection_state(True)
            self._ecm_test_panel.set_connection_state(True)

            # 日志提示
            self._command_panel.append_sys(f"已连接到 {addr}")
            self._ble_name_panel.append_sys(f"已连接到 {addr}")
            self._ecm_test_panel.append_sys(f"已连接到 {addr}")

            # 保存到历史
            self._save_to_history(addr)
        except Exception as e:
            self._on_error(f"连接回调异常: {str(e)}")

    def _on_disconnected(self):
        """断开连接"""
        try:
            self._status_badge.set_state("Disconnected", "#F44747")
            self._scan_panel.set_connected(False)
            self._ble_name_panel.set_connection_state(False)
            self._ecm_test_panel.set_connection_state(False)

            # 日志提示
            self._command_panel.append_sys("连接已断开")
            self._ble_name_panel.append_sys("连接已断开")
            self._ecm_test_panel.append_sys("连接已断开")
        except Exception as e:
            # 避免在 UI 更新时崩溃
            print(f"_on_disconnected error: {e}", file=sys.stderr)

    # ──────────────────────────────────────────────
    # 收发相关
    # ──────────────────────────────────────────────

    def _on_send_requested(self, data: bytes):
        """发送数据"""
        try:
            frame = CH9329Frame.from_bytes(data)
            task = asyncio.create_task(self._do_send(frame))
            # 添加异常回调，防止未捕获的异常导致闪退
            task.add_done_callback(self._on_send_task_done)
        except Exception as e:
            err_msg = f"帧构建失败: {str(e)}"
            self._command_panel.append_err(err_msg)
            self._ble_name_panel.append_err(err_msg)

    def _on_send_task_done(self, task):
        """发送任务完成回调（捕获未处理异常）"""
        try:
            exc = task.exception()
            if exc:
                err_msg = f"发送异常: {str(exc)}"
                self._command_panel.append_err(err_msg)
                self._ble_name_panel.append_err(err_msg)
        except asyncio.CancelledError:
            pass
        except Exception:
            # 彻底忽略任何异常，防止回调本身导致闪退
            pass

    async def _do_send(self, frame: CH9329Frame):
        """执行发送（异步）

        对于名称修改命令（0x23），设备可能会立即重启/断开，
        所以发送后不做任何 UI 更新，让响应处理或断开检测来更新 UI。
        """
        try:
            data = frame.to_bytes()
            # 在 BLE 操作之前安全地获取 UUID（避免在 write 期间访问）
            try:
                tx_uuid = self._client._tx_char.uuid if self._client._tx_char else "?"
            except Exception:
                tx_uuid = "?"
            self._on_debug_info(f"发送 {len(data)} 字节到 {tx_uuid}")

            # 检查是否是名称修改命令（0x23）
            is_name_change = (frame.cmd == 0x23)

            success = await self._client.send(frame)

            if success:
                if is_name_change:
                    # 名称修改命令：禁用连接轮询 3 秒，防止设备重启时检测到断开导致闪退
                    self._client.disable_polling_for(3.0)
                    # 延迟显示成功消息，避免在 BLE 操作后立即更新 UI
                    from PyQt6.QtCore import QTimer
                    QTimer.singleShot(100, lambda: self._on_debug_info("✓ 名称修改命令已发送，设备正在重启..."))
                else:
                    self._on_debug_info("✓ 发送成功")
            else:
                self._command_panel.append_err("发送失败")
                self._ble_name_panel.append_err("发送失败")
        except Exception as e:
            # 捕获所有异常，防止连接断开时闪退
            err_msg = f"发送错误: {str(e)}"
            self._command_panel.append_err(err_msg)
            self._ble_name_panel.append_err(err_msg)

    def _on_response_received(self, frame: CH9329Frame):
        """收到响应

        所有 UI 更新用 try/except 包裹，防止任何异常导致闪退。
        对于名称修改命令的响应，延迟处理，避免在 BLE 操作期间更新 UI。
        """
        try:
            # 检查是否是名称修改命令的响应（0x23 | 0x80 = 0xA3）
            is_name_change_response = ((frame.cmd & 0x7F) == 0x23)

            if is_name_change_response:
                # 名称修改响应：延迟处理，避免在 BLE 操作期间更新 UI
                from PyQt6.QtCore import QTimer
                # 使用 weak reference 避免循环引用
                import weakref
                self_ref = weakref.ref(self)
                frame_data = frame.to_bytes()

                def delayed_handle():
                    self_obj = self_ref()
                    if self_obj:
                        self_obj._handle_name_change_response(frame_data)

                QTimer.singleShot(200, delayed_handle)
            else:
                # 普通响应：立即处理
                data = frame.to_bytes()
                self._command_panel.append_rx(data)
                self._ble_name_panel.append_rx(data)
                self._ecm_test_panel.append_rx(data)
                self._parse_response(frame)
        except Exception as e:
            # 捕获所有异常，防止响应处理导致闪退
            print(f"_on_response_received error: {e}", file=sys.stderr)

    def _handle_name_change_response(self, data: bytes):
        """延迟处理名称修改响应"""
        try:
            self._command_panel.append_rx(data)
            self._ble_name_panel.append_rx(data)
            self._ecm_test_panel.append_rx(data)

            # 解析响应
            frame = CH9329Frame.from_bytes(data)
            self._parse_response(frame)
        except Exception as e:
            print(f"_handle_name_change_response error: {e}", file=sys.stderr)

    def _parse_response(self, frame: CH9329Frame):
        """解析响应帧并显示字段含义"""
        try:
            # 提取原始命令（响应命令 = 原命令 | 0x80 或 | 0xC0）
            original_cmd = frame.cmd & 0x7F
            is_error = bool(frame.cmd & 0x40)

            # 按命令类型解析
            if original_cmd == 0x01 and len(frame.payload) >= 4:
                # Get Info 响应 - 没有状态码，直接是设备信息
                hw = frame.payload[0]
                usb = frame.payload[1]
                led = frame.payload[2]
                fw = frame.payload[3]

                hw_names = {0x01: "KVM-GO", 0x02: "MiniKVM", 0x03: "KeyMod"}
                hw_name = hw_names.get(hw, f"Unknown(0x{hw:02X})")

                self._command_panel.append_sys(
                    f"✓ {hw_name} | USB={'已连接' if usb else '未连接'} | LED=0x{led:02X} | FW=v{fw}"
                )
            else:
                # 其他命令 - 显示状态码和 payload
                if len(frame.payload) > 0:
                    status = frame.payload[0]
                    status_text = "成功" if status == 0x00 else f"错误 0x{status:02X}"
                    self._command_panel.append_sys(f"  {status_text}")
                    self._ble_name_panel.append_sys(f"  {status_text}")
                    if len(frame.payload) > 1:
                        payload_hex = ' '.join(f"{b:02X}" for b in frame.payload[1:])
                        self._command_panel.append_sys(f"  Data: {payload_hex}")
                        self._ble_name_panel.append_sys(f"  Data: {payload_hex}")
                else:
                    self._command_panel.append_sys("  (空响应)")
                    self._ble_name_panel.append_sys("  (空响应)")
        except Exception as e:
            print(f"_parse_response error: {e}", file=sys.stderr)

    def _on_error(self, msg: str):
        """错误处理"""
        self._command_panel.append_err(msg)
        self._ble_name_panel.append_err(msg)
        self._ecm_test_panel.append_err(msg)
        self._status_badge.set_state("Error", "#F44747")

    def _on_debug_info(self, msg: str):
        """调试信息"""
        self._command_panel.append_sys(f"[BLE] {msg}")
        self._ble_name_panel.append_sys(f"[BLE] {msg}")
        self._ecm_test_panel.append_sys(f"[BLE] {msg}")

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
        # 取消所有待处理的异步任务
        if self._scan_task and not self._scan_task.done():
            self._scan_task.cancel()

        asyncio.create_task(self._cleanup())
        event.accept()

    async def _cleanup(self):
        """清理资源"""
        try:
            await self._client.disconnect()
            self._client.cleanup()
        except Exception:
            pass
        try:
            await self._scanner.stop()
        except Exception:
            pass
