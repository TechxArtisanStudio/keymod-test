"""BLE 设备名称修改面板"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from ui.widgets import LogArea
from protocol.ch9329 import CH9329Frame


class BLENamePanel(QWidget):
    """BLE 设备名称修改面板"""

    send_requested = pyqtSignal(bytes)

    def __init__(self):
        super().__init__()
        self._connected = False
        self._setup_ui()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        # 标题
        title = QLabel("修改 BLE 设备名称")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #CCCCCC;")
        outer.addWidget(title)

        # 警告横幅
        warning = QFrame()
        warning.setFrameShape(QFrame.Shape.StyledPanel)
        warning.setStyleSheet("""
            QFrame {
                background-color: #3E2E1E;
                border: 1px solid #CE9178;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        warning_layout = QVBoxLayout(warning)
        warning_layout.setContentsMargins(10, 8, 10, 8)

        warn_label = QLabel(
            "⚠ 修改名称后设备将自动重启，BLE 连接会断开。\n"
            "名称写入 Flash，断电后仍然保留。"
        )
        warn_label.setWordWrap(True)
        warn_label.setStyleSheet("color: #CE9178; font-size: 12px;")
        warning_layout.addWidget(warn_label)

        outer.addWidget(warning)

        # 连接状态
        self._conn_label = QLabel("● 未连接")
        self._conn_label.setStyleSheet("color: #F44747; font-size: 12px; font-weight: 500;")
        outer.addWidget(self._conn_label)

        # 名称输入行
        input_row = QHBoxLayout()
        input_row.setSpacing(10)

        name_label = QLabel("设备名称:")
        name_label.setStyleSheet("color: #CCCCCC; font-size: 13px;")
        input_row.addWidget(name_label)

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("输入新名称...")
        self._name_input.setMaxLength(20)
        self._name_input.setMinimumHeight(34)
        self._name_input.setStyleSheet("""
            QLineEdit {
                background-color: #252526;
                color: #D4D4D4;
                border: 1px solid #3E3E3E;
                padding: 6px 10px;
                border-radius: 4px;
                font-family: 'Monaco', 'Consolas', monospace;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #007ACC;
                background-color: #2D2D30;
            }
        """)
        self._name_input.textChanged.connect(self._on_text_changed)
        input_row.addWidget(self._name_input, stretch=1)

        self._send_btn = QPushButton("修改名称")
        self._send_btn.setFixedSize(100, 34)
        self._send_btn.setEnabled(False)
        self._send_btn.setStyleSheet("""
            QPushButton {
                background-color: #007ACC;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #1A8BDD; }
            QPushButton:pressed { background-color: #005A9E; }
            QPushButton:disabled { background-color: #3E3E42; color: #888; }
        """)
        self._send_btn.clicked.connect(self._on_send_clicked)
        input_row.addWidget(self._send_btn)

        outer.addLayout(input_row)

        # 字符计数
        self._count_label = QLabel("0/20")
        self._count_label.setStyleSheet("color: #888; font-size: 11px;")
        outer.addWidget(self._count_label)

        # 日志区域
        self._log = LogArea()
        outer.addWidget(self._log, stretch=1)

    def _on_text_changed(self, text: str):
        """文本变化 → 更新计数和按钮状态"""
        # 过滤非 ASCII 字符
        filtered = ''.join(c for c in text if ord(c) < 128)
        if filtered != text:
            self._name_input.setText(filtered)
            return

        length = len(filtered)
        self._count_label.setText(f"{length}/20")
        self._send_btn.setEnabled(self._connected and 1 <= length <= 20)

    def _on_send_clicked(self):
        """发送按钮 → 构建帧并发射"""
        name = self._name_input.text().strip()
        if not name:
            self._log.append_err("名称不能为空")
            return

        payload = name.encode('ascii')
        frame = CH9329Frame(addr=0x00, cmd=0x23, payload=payload)
        data = frame.to_bytes()

        self._log.append_tx(data)
        self._log.append_sys(f"正在发送名称: \"{name}\" ({len(payload)} 字节)")
        self.send_requested.emit(data)

    def set_connection_state(self, connected: bool):
        """更新连接状态"""
        self._connected = connected
        if connected:
            self._conn_label.setText("● 已连接")
            self._conn_label.setStyleSheet("color: #4EC9B0; font-size: 12px; font-weight: 500;")
        else:
            self._conn_label.setText("● 未连接")
            self._conn_label.setStyleSheet("color: #F44747; font-size: 12px; font-weight: 500;")
        self._send_btn.setEnabled(self._connected and len(self._name_input.text().strip()) > 0)

    def append_rx(self, data: bytes):
        """显示接收数据"""
        try:
            self._log.append_rx(data)
            # 解析响应状态
            if len(data) >= 6:
                try:
                    frame = CH9329Frame.from_bytes(data)
                    if len(frame.payload) > 0:
                        status = frame.payload[0]
                        if status == 0x00:
                            self._log.append_sys("✓ 名称修改成功！设备正在重启...")
                        else:
                            self._log.append_err(f"设备返回错误码: 0x{status:02X}")
                except Exception:
                    pass
        except Exception as e:
            # 防止 UI 更新导致闪退
            print(f"BLENamePanel.append_rx error: {e}")

    def append_err(self, msg: str):
        self._log.append_err(msg)

    def append_sys(self, msg: str):
        self._log.append_sys(msg)
