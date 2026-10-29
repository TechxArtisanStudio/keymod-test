"""UI 复用小部件"""
from PyQt6.QtWidgets import (
    QPlainTextEdit, QLineEdit, QPushButton, QWidget,
    QHBoxLayout, QVBoxLayout, QLabel, QFrame, QToolTip
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QTextCharFormat, QSyntaxHighlighter, QTextDocument


class HexLineEdit(QLineEdit):
    """十六进制输入框（自动格式化）"""
    def __init__(self, placeholder: str = "输入十六进制数据..."):
        super().__init__()
        self.setPlaceholderText(placeholder)
        self.setFont(QFont("Monaco", 12))
        self.textChanged.connect(self._format_hex)

    def _format_hex(self, text: str):
        # 只保留十六进制字符（去掉空格和其他字符）
        hex_only = ''.join(c for c in text.upper() if c in '0123456789ABCDEF')

        # 每两个字符加一个空格
        formatted = ' '.join(hex_only[i:i+2] for i in range(0, len(hex_only), 2))

        if formatted != text:
            cursor_pos = self.cursorPosition()
            # 计算光标应该在哪
            # 去掉空格后的位置
            text_before_cursor = text[:cursor_pos]
            hex_before = ''.join(c for c in text_before_cursor.upper() if c in '0123456789ABCDEF')
            new_cursor = len(' '.join(hex_before[i:i+2] for i in range(0, len(hex_before), 2)))

            self.blockSignals(True)
            self.setText(formatted)
            self.setCursorPosition(new_cursor)
            self.blockSignals(False)

    def get_bytes(self) -> bytes:
        """获取输入的字节"""
        text = self.text().replace(' ', '')
        if not text:
            return b""
        # 如果长度是奇数，补0
        if len(text) % 2 == 1:
            text += '0'
        try:
            return bytes.fromhex(text)
        except ValueError:
            return b""


class HexHighlighter(QSyntaxHighlighter):
    """十六进制语法高亮"""
    def __init__(self, parent: QTextDocument = None):
        super().__init__(parent)
        self._formats = {
            'header': self._fmt(QColor("#569CD6")),      # 57 AB
            'addr': self._fmt(QColor("#4EC9B0")),        # 地址
            'cmd': self._fmt(QColor("#DCDCAA")),         # 命令
            'len': self._fmt(QColor("#C586C0")),         # 长度
            'payload': self._fmt(QColor("#9CDCFE")),     # payload
            'checksum': self._fmt(QColor("#CE9178")),    # 校验和
            'error': self._fmt(QColor("#F44747")),       # 错误
        }

    def _fmt(self, color: QColor) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        return fmt

    def highlightBlock(self, text: str):
        # 简化：逐行高亮
        # 实际项目中可以更精确地解析每个字节位置
        pass


class StatusBadge(QWidget):
    """状态标签（彩色圆点 + 文字）"""
    def __init__(self, text: str = "Disconnected", color: str = "#F44747"):
        super().__init__()
        self._color = color
        self._text = text
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        self._dot = QLabel("●")
        self._dot.setStyleSheet(f"color: {self._color}; font-size: 12px;")
        self._label = QLabel(self._text)
        self._label.setStyleSheet(f"color: {self._color}; font-weight: 500;")

        layout.addWidget(self._dot)
        layout.addWidget(self._label)
        layout.addStretch()

    def set_state(self, text: str, color: str):
        self._text = text
        self._color = color
        self._dot.setStyleSheet(f"color: {color}; font-size: 12px;")
        self._label.setText(text)
        self._label.setStyleSheet(f"color: {color}; font-weight: 500;")


class LogArea(QPlainTextEdit):
    """日志区域（彩色区分 TX/RX/ERR/SYS）"""
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setFont(QFont("Courier New", 9))
        self.setMaximumBlockCount(10000)

        # 预定义颜色
        self._colors = {
            'tx': QColor("#569CD6"),    # 蓝
            'rx': QColor("#4EC9B0"),    # 绿
            'err': QColor("#F44747"),   # 红
            'sys': QColor("#888888"),   # 灰
        }

    def append_log(self, text: str, level: str = 'sys'):
        """追加日志"""
        fmt = QTextCharFormat()
        fmt.setForeground(self._colors.get(level, self._colors['sys']))
        cursor = self.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text + "\n", fmt)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def append_tx(self, data: bytes):
        hex_str = ' '.join(f"{b:02X}" for b in data)
        self.append_log(hex_str, 'tx')

    def append_rx(self, data: bytes):
        hex_str = ' '.join(f"{b:02X}" for b in data)
        self.append_log(hex_str, 'rx')

    def append_err(self, text: str):
        self.append_log(f"ERR: {text}", 'err')

    def append_sys(self, text: str):
        self.append_log(text, 'sys')


class CollapsibleSection(QWidget):
    """可折叠区域（标题栏 + 内容区）"""
    def __init__(self, title: str = "Section", parent=None):
        super().__init__(parent)
        self._expanded = False
        self._setup_ui(title)

    def _setup_ui(self, title: str):
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        # 标题栏
        self._title_bar = QFrame()
        self._title_bar.setFrameShape(QFrame.Shape.StyledPanel)
        self._title_bar.setStyleSheet("background-color: #2D2D2D; border: 1px solid #3E3E3E;")
        title_layout = QHBoxLayout(self._title_bar)
        title_layout.setContentsMargins(8, 4, 8, 4)

        self._arrow = QLabel("▶")
        self._arrow.setStyleSheet("color: #CCCCCC;")
        title_layout.addWidget(self._arrow)

        self._title_label = QLabel(title)
        self._title_label.setStyleSheet("color: #CCCCCC; font-weight: 500;")
        title_layout.addWidget(self._title_label)

        title_layout.addStretch()

        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(20, 20)
        self._close_btn.setStyleSheet("""
            QPushButton { border: none; color: #888; background: transparent; }
            QPushButton:hover { color: #F44747; }
        """)
        self._close_btn.clicked.connect(self._on_close)
        title_layout.addWidget(self._close_btn)

        self._title_bar.mousePressEvent = self._on_title_click
        self._layout.addWidget(self._title_bar)

        # 内容区
        self._content = QWidget()
        self._content.setVisible(False)
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(4, 4, 4, 4)
        self._layout.addWidget(self._content)

    def _on_title_click(self, event):
        self.set_expanded(not self._expanded)

    def _on_close(self):
        self.setVisible(False)

    def set_expanded(self, expanded: bool):
        self._expanded = expanded
        self._content.setVisible(expanded)
        self._arrow.setText("▼" if expanded else "▶")

    def is_expanded(self) -> bool:
        return self._expanded

    def add_widget(self, widget: QWidget):
        self._content_layout.addWidget(widget)

    def set_content_layout(self, layout):
        # 清除旧布局
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        self._content_layout = layout
        self._content.setLayout(layout)


class CommandCard(QFrame):
    """命令卡片（点击选择命令）"""
    clicked = pyqtSignal(int)  # cmd byte

    def __init__(self, cmd: int, name: str, tooltip: str = ""):
        super().__init__()
        self._cmd = cmd
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            CommandCard {
                background-color: #252526;
                border: 1px solid #3E3E3E;
                border-radius: 4px;
            }
            CommandCard:hover {
                background-color: #2D2D30;
                border-color: #007ACC;
            }
        """)
        self.setFixedSize(90, 44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)

        self._cmd_label = QLabel(f"0x{cmd:02X}")
        self._cmd_label.setStyleSheet("color: #569CD6; font-weight: bold; font-size: 11px;")
        self._cmd_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._cmd_label)

        self._name_label = QLabel(name)
        self._name_label.setStyleSheet("color: #CCCCCC; font-size: 9px;")
        self._name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name_label.setWordWrap(True)
        layout.addWidget(self._name_label)

        if tooltip:
            self.setToolTip(tooltip)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._cmd)


class ConnectButton(QPushButton):
    """连接/断开按钮（状态感知）"""
    def __init__(self):
        super().__init__("连接")
        self.setFixedWidth(80)
        self.set_checkable(True)

    def set_checkable(self, connected: bool):
        if connected:
            self.setText("断开")
            self.setStyleSheet("""
                QPushButton { background-color: #CE9178; color: white; border: none; padding: 4px; }
                QPushButton:hover { background-color: #D4A585; }
            """)
        else:
            self.setText("连接")
            self.setStyleSheet("""
                QPushButton { background-color: #007ACC; color: white; border: none; padding: 4px; }
                QPushButton:hover { background-color: #1A8BDD; }
                QPushButton:disabled { background-color: #3E3E42; color: #888; }
            """)