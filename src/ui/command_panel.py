"""命令面板（发送区 + 日志 + 可视化命令面板）"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QCheckBox, QSplitter, QLabel, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from .widgets import LogArea, HexLineEdit, StatusBadge, CollapsibleSection
from .command_palette import CommandPalette
from protocol import CH9329Frame, COMMAND_META


class CommandPanel(QWidget):
    """命令面板（连接成功后显示）"""

    # 信号：请求发送数据
    send_requested = pyqtSignal(bytes)

    def __init__(self):
        super().__init__()
        self._auto_checksum = True
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 可折叠的命令面板区域
        self._collapsible = CollapsibleSection("命令面板 ▶")
        self._collapsible.set_expanded(False)  # 默认折叠

        # 内部布局
        inner_layout = QVBoxLayout()
        inner_layout.setContentsMargins(4, 4, 4, 4)

        # 命令卡片网格
        self._palette = CommandPalette()
        self._palette.command_selected.connect(self._on_command_selected)
        inner_layout.addWidget(self._palette)

        # 分隔线
        from PyQt6.QtWidgets import QFrame
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        inner_layout.addWidget(line)

        self._collapsible.add_widget(self._create_inner_widget(inner_layout))
        layout.addWidget(self._collapsible)

        # 发送区
        layout.addWidget(self._create_send_area())

        # 日志区
        self._log = LogArea()
        layout.addWidget(self._log, stretch=1)

    def _create_inner_widget(self, inner_layout: QVBoxLayout) -> QWidget:
        w = QWidget()
        w.setLayout(inner_layout)
        return w

    def _create_send_area(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background-color: #1E1E1E; border-top: 1px solid #3E3E3E;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 6, 8, 6)

        # 标题行
        title_row = QHBoxLayout()
        title_label = QLabel("发送区")
        title_label.setStyleSheet("color: #CCCCCC; font-weight: 500;")
        title_row.addWidget(title_label)
        title_row.addStretch()

        self._auto_checksum_cb = QCheckBox("自动补校验和")
        self._auto_checksum_cb.setChecked(True)
        self._auto_checksum_cb.setStyleSheet("color: #CCCCCC;")
        self._auto_checksum_cb.stateChanged.connect(self._on_auto_checksum_changed)
        title_row.addWidget(self._auto_checksum_cb)

        layout.addLayout(title_row)

        # 输入行
        input_row = QHBoxLayout()
        self._hex_input = HexLineEdit("输入十六进制数据（如 57 AB 00 01 00）...")
        self._hex_input.setMinimumHeight(28)
        self._hex_input.setStyleSheet("""
            QLineEdit {
                background-color: #252526;
                color: #D4D4D4;
                border: 1px solid #3E3E3E;
                padding: 4px;
                border-radius: 3px;
            }
            QLineEdit:focus {
                border-color: #007ACC;
            }
        """)
        input_row.addWidget(self._hex_input)

        self._send_btn = QPushButton("发送")
        self._send_btn.setFixedWidth(80)
        self._send_btn.setMinimumHeight(28)
        self._send_btn.setStyleSheet("""
            QPushButton {
                background-color: #007ACC;
                color: white;
                border: none;
                padding: 6px;
                border-radius: 3px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #1A8BDD; }
            QPushButton:disabled { background-color: #3E3E42; color: #888; }
        """)
        self._send_btn.clicked.connect(self._on_send_clicked)
        input_row.addWidget(self._send_btn)

        layout.addLayout(input_row)

        return w

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
        # 简化：如果用户输入不足 6 字节（不够完整帧），自动补
        # 否则检查最后一字节是否为校验和（不自动补，由用户决定）
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
