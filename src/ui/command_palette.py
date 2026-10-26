"""命令面板（可视化命令卡片网格）"""
from PyQt6.QtWidgets import QWidget, QScrollArea, QGridLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal
from .widgets import CommandCard
from ..protocol import COMMAND_META


class CommandPalette(QWidget):
    """命令卡片网格"""
    command_selected = pyqtSignal(int)  # cmd byte

    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        # 滚动区域
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # 内容容器
        content = QWidget()
        self._layout = QGridLayout(content)
        self._layout.setSpacing(8)
        self._layout.setContentsMargins(4, 4, 4, 4)

        # 按顺序添加命令卡片（每行 4 个）
        row, col = 0, 0
        for cmd, meta in sorted(COMMAND_META.items()):
            # Tooltip 使用富文本
            tooltip = meta.tooltip_rich
            card = CommandCard(cmd, meta.name, tooltip)
            card.clicked.connect(self.command_selected.emit)
            self._layout.addWidget(card, row, col)

            col += 1
            if col >= 4:
                col = 0
                row += 1

        # 底部占位
        self._layout.setRowStretch(row + 1, 1)

        scroll.setWidget(content)

        # 主布局
        layout = self.layout()
        if layout is None:
            from PyQt6.QtWidgets import QVBoxLayout
            layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)
