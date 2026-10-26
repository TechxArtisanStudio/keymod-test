"""命令面板（串口调试助手风格）"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QCheckBox, QSplitter, QLabel, QFileDialog, QRadioButton,
    QButtonGroup, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from ui.widgets import LogArea, HexLineEdit
from ui.command_palette import CommandPalette
from protocol import CH9329Frame, COMMAND_META


class CommandPanel(QWidget):
    """命令面板（连接成功后显示）- 串口调试助手风格"""

    # 信号：请求发送数据
    send_requested = pyqtSignal(bytes)

    def __init__(self):
        super().__init__()
        self._auto_checksum = True
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 快速命令栏（横向滚动）
        layout.addWidget(self._create_quick_commands())

        # 主区域：左右分割
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：命令面板（可折叠）
        self._palette_container = QWidget()
        palette_layout = QVBoxLayout(self._palette_container)
        palette_layout.setContentsMargins(0, 0, 0, 0)

        self._palette_label = QLabel("命令列表 ▶")
        self._palette_label.setStyleSheet("color: #CCCCCC; font-weight: bold; padding: 4px; cursor: pointer;")
        self._palette_label.mousePressEvent = self._toggle_palette
        palette_layout.addWidget(self._palette_label)

        self._palette = CommandPalette()
        self._palette.command_selected.connect(self._on_command_selected)
        self._palette.setVisible(True)
        palette_layout.addWidget(self._palette)

        splitter.addWidget(self._palette_container)

        # 右侧：日志 + 发送区
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # 日志区（上半部分）
        self._log = LogArea()
        right_layout.addWidget(self._log, stretch=1)

        # 发送区（下半部分）
        right_layout.addWidget(self._create_send_area())

        splitter.addWidget(right_panel)

        # 设置分割比例
        splitter.setSizes([250, 650])

        layout.addWidget(splitter, stretch=1)

    def _create_quick_commands(self) -> QWidget:
        """快速命令栏"""
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet("QFrame { background-color: #252526; border: 1px solid #3E3E3E; border-radius: 4px; }")

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)

        label = QLabel("快捷命令:")
        label.setStyleSheet("color: #888;")
        layout.addWidget(label)

        # 常用命令按钮
        quick_cmds = [
            (0x01, "Get Info", "57 AB 00 01 00 03"),
            (0x02, "Keyboard", "57 AB 00 02 08 00 00 00 00 00 00 00 00 0C"),
            (0x03, "Media", "57 AB 00 03 02 00 00 05"),
            (0x04, "AbsMouse", "57 AB 00 04 07 00 00 00 00 00 00 00 0B"),
            (0x05, "RelMouse", "57 AB 00 05 05 00 00 00 00 00 0A"),
        ]

        for cmd, name, hex_data in quick_cmds:
            btn = QPushButton(name)
            btn.setFixedHeight(28)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2D2D30;
                    color: #CCCCCC;
                    border: 1px solid #3E3E3E;
                    border-radius: 3px;
                    padding: 4px 8px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #007ACC;
                    color: white;
                }
            """)
            btn.clicked.connect(lambda checked, data=hex_data: self._fill_send_area(data))
            layout.addWidget(btn)

        layout.addStretch()

        return frame

    def _fill_send_area(self, hex_data: str):
        """填充发送区"""
        self._hex_input.setText(hex_data)

    def _toggle_palette(self, event):
        """切换命令面板显示/隐藏"""
        visible = self._palette.isVisible()
        self._palette.setVisible(not visible)
        self._palette_label.setText("命令列表 ▼" if visible else "命令列表 ▶")

    def _create_send_area(self) -> QWidget:
        """发送区（串口调试助手风格）"""
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet("""
            QFrame {
                background-color: #1E1E1E;
                border: 1px solid #3E3E3E;
                border-radius: 4px;
            }
        """)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # 选项行
        options_row = QHBoxLayout()
        options_row.setSpacing(12)  # 统一间距

        # 输入模式
        mode_label = QLabel("发送格式:")
        mode_label.setStyleSheet("color: #CCCCCC; font-size: 12px;")
        options_row.addWidget(mode_label)

        self._hex_radio = QRadioButton("HEX")
        self._hex_radio.setChecked(True)
        self._hex_radio.setStyleSheet("""
            QRadioButton {
                color: #CCCCCC;
                spacing: 6px;
                font-size: 12px;
            }
            QRadioButton::indicator {
                width: 14px;
                height: 14px;
            }
        """)
        options_row.addWidget(self._hex_radio)

        self._ascii_radio = QRadioButton("ASCII")
        self._ascii_radio.setStyleSheet("""
            QRadioButton {
                color: #CCCCCC;
                spacing: 6px;
                font-size: 12px;
            }
            QRadioButton::indicator {
                width: 14px;
                height: 14px;
            }
        """)
        options_row.addWidget(self._ascii_radio)

        self._mode_group = QButtonGroup()
        self._mode_group.addButton(self._hex_radio)
        self._mode_group.addButton(self._ascii_radio)

        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setStyleSheet("color: #3E3E3E;")
        separator.setFixedWidth(1)
        options_row.addWidget(separator)

        # 自动补校验和
        self._auto_checksum_cb = QCheckBox("自动补校验和")
        self._auto_checksum_cb.setChecked(True)
        self._auto_checksum_cb.setStyleSheet("""
            QCheckBox {
                color: #CCCCCC;
                spacing: 6px;
                font-size: 12px;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
            }
        """)
        self._auto_checksum_cb.stateChanged.connect(self._on_auto_checksum_changed)
        options_row.addWidget(self._auto_checksum_cb)

        options_row.addStretch()

        # 清空日志按钮
        clear_btn = QPushButton("清空日志")
        clear_btn.setFixedSize(80, 28)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #3E3E42;
                color: #CCCCCC;
                border: 1px solid #555;
                border-radius: 3px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #505054;
                border-color: #666;
            }
        """)
        clear_btn.clicked.connect(self._log.clear)
        options_row.addWidget(clear_btn)

        layout.addLayout(options_row)

        # 输入框
        input_layout = QHBoxLayout()
        input_layout.setSpacing(8)

        self._hex_input = HexLineEdit("输入十六进制数据（如 57 AB 00 01 00）...")
        self._hex_input.setMinimumHeight(34)
        self._hex_input.setStyleSheet("""
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
        input_layout.addWidget(self._hex_input, stretch=1)

        self._send_btn = QPushButton("发送")
        self._send_btn.setFixedSize(90, 34)
        self._send_btn.setStyleSheet("""
            QPushButton {
                background-color: #007ACC;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #1A8BDD;
            }
            QPushButton:pressed {
                background-color: #005A9E;
            }
            QPushButton:disabled {
                background-color: #3E3E42;
                color: #888;
            }
        """)
        self._send_btn.clicked.connect(self._on_send_clicked)
        input_layout.addWidget(self._send_btn)

        layout.addLayout(input_layout)

        return frame

    def _on_auto_checksum_changed(self, state):
        self._auto_checksum = (state == Qt.CheckState.Checked.value)

    def _on_command_selected(self, cmd: int):
        """命令卡片被点击 → 预填发送区"""
        meta = COMMAND_META.get(cmd)
        if not meta:
            return

        # 根据示例请求预填
        if meta.example_request:
            hex_str = ' '.join(f"{b:02X}" for b in meta.example_request)
            self._hex_input.setText(hex_str)
        else:
            # 没有示例，只填 header + addr + cmd + len
            frame = CH9329Frame(addr=0x00, cmd=cmd)
            hex_str = ' '.join(f"{b:02X}" for b in frame.to_bytes())
            self._hex_input.setText(hex_str)

    def _on_send_clicked(self):
        """发送按钮点击"""
        data = self._hex_input.get_bytes()
        if not data:
            self._log.append_err("无效输入")
            return

        # 检查是否需要自动补校验和
        if len(data) < 6:
            # 自动补全为完整帧
            if len(data) < 2 or data[0] != 0x57 or data[1] != 0xAB:
                self._log.append_err("必须以 57 AB 开头")
                return
            if len(data) < 3:
                self._log.append_err("缺少地址字节")
                return
            if len(data) < 4:
                self._log.append_err("缺少命令字节")
                return

            # 解析已有部分
            addr = data[2]
            cmd = data[3]
            payload = data[4:] if len(data) > 4 else b""

            frame = CH9329Frame(addr, cmd, payload)
            data = frame.to_bytes()

        hex_str = ' '.join(f"{b:02X}" for b in data)
        self._log.append_tx(hex_str)

        # 发射信号（由 MainWindow 处理实际发送）
        self.send_requested.emit(data)

    def append_tx(self, data: bytes):
        hex_str = ' '.join(f"{b:02X}" for b in data)
        self._log.append_tx(hex_str)

    def append_rx(self, data: bytes):
        hex_str = ' '.join(f"{b:02X}" for b in data)
        self._log.append_rx(hex_str)

    def append_err(self, msg: str):
        self._log.append_err(msg)

    def append_sys(self, msg: str):
        self._log.append_sys(msg)

    def export_log(self):
        """导出日志到文件"""
        path, _ = QFileDialog.getSaveFileName(self, "导出日志", "log.txt", "Text Files (*.txt)")
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self._log.toPlainText())
