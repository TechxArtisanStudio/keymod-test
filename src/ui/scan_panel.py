"""扫描面板（设备列表 + 连接历史）"""
from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableView, QHeaderView, QLabel, QSpinBox, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal, QAbstractTableModel
from PyQt6.QtGui import QAction
from protocol.models import DeviceInfo, ConnectionHistoryEntry
from config import DEFAULT_SCAN_DURATION


class DeviceTableModel(QAbstractTableModel):
    """设备表格模型"""
    COLUMNS = ["名称", "地址", "RSSI", "操作"]

    def __init__(self):
        super().__init__()
        self._devices: list[DeviceInfo] = []
        self._history: list[ConnectionHistoryEntry] = []
        self._connected_address: str = ""

    def set_connected_address(self, address: str):
        """设置当前连接的设备地址（用于显示"已连接"）"""
        self._connected_address = address
        self.beginResetModel()
        self.endResetModel()

    def set_devices(self, devices: list[DeviceInfo]):
        self.beginResetModel()
        self._devices = devices
        self.endResetModel()

    def set_history(self, history: list[ConnectionHistoryEntry]):
        self.beginResetModel()
        self._history = history
        self.endResetModel()

    def rowCount(self, parent=None):
        return len(self._history) + len(self._devices)

    def columnCount(self, parent=None):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.COLUMNS[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        row, col = index.row(), index.column()
        is_history = row < len(self._history)

        if is_history:
            entry = self._history[row]
            if col == 0:
                return entry.display_name()
            elif col == 1:
                return entry.address
            elif col == 2:
                return "历史"
            elif col == 3:
                return "连接"
        else:
            dev = self._devices[row - len(self._history)]
            if col == 0:
                return dev.display_name()
            elif col == 1:
                return dev.address
            elif col == 2:
                return str(dev.rssi)
            elif col == 3:
                # 已连接的设备显示"已连接"
                if hasattr(self, '_connected_address') and dev.address == self._connected_address:
                    return "已连接"
                return "连接"

        return None

    def get_device_at(self, row: int) -> Optional[DeviceInfo]:
        if row < len(self._history):
            entry = self._history[row]
            return DeviceInfo(address=entry.address, name=entry.name)
        elif row < len(self._history) + len(self._devices):
            return self._devices[row - len(self._history)]
        return None


class ScanPanel(QWidget):
    """扫描面板"""
    scan_requested = pyqtSignal(float)  # duration
    stop_requested = pyqtSignal()
    connect_requested = pyqtSignal(str)  # address
    disconnect_requested = pyqtSignal()  # 断开连接

    def __init__(self):
        super().__init__()
        self._connected = False
        self._connected_address = ""
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # 标题行
        title_row = QHBoxLayout()
        title_label = QLabel("BLE 设备扫描")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #CCCCCC;")
        title_row.addWidget(title_label)
        title_row.addStretch()

        # 扫描时长
        duration_label = QLabel("时长:")
        duration_label.setStyleSheet("color: #CCCCCC;")
        title_row.addWidget(duration_label)

        self._duration_spin = QSpinBox()
        self._duration_spin.setRange(1, 30)
        self._duration_spin.setValue(int(DEFAULT_SCAN_DURATION))
        self._duration_spin.setSuffix(" 秒")
        self._duration_spin.setStyleSheet("""
            QSpinBox {
                background-color: #252526;
                color: #D4D4D4;
                border: 1px solid #3E3E3E;
                padding: 2px;
            }
        """)
        title_row.addWidget(self._duration_spin)

        # 扫描按钮
        self._scan_btn = QPushButton("开始扫描")
        self._scan_btn.setFixedWidth(100)
        self._scan_btn.setStyleSheet("""
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
        self._scan_btn.clicked.connect(self._on_scan_clicked)
        title_row.addWidget(self._scan_btn)

        # 断开按钮（连接后显示）
        self._disconnect_btn = QPushButton("断开连接")
        self._disconnect_btn.setFixedWidth(100)
        self._disconnect_btn.setVisible(False)
        self._disconnect_btn.setStyleSheet("""
            QPushButton {
                background-color: #CE9178;
                color: white;
                border: none;
                padding: 6px;
                border-radius: 3px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #D4A585; }
        """)
        self._disconnect_btn.clicked.connect(lambda: self.disconnect_requested.emit())
        title_row.addWidget(self._disconnect_btn)

        layout.addLayout(title_row)

        # 设备表格
        self._model = DeviceTableModel()
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(32)  # 行高
        self._table.setMinimumHeight(300)  # 最小高度
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(2, 100)
        self._table.setColumnWidth(3, 120)
        self._table.setStyleSheet("""
            QTableView {
                background-color: #1E1E1E;
                alternate-background-color: #252526;
                color: #D4D4D4;
                gridline-color: #3E3E3E;
                border: 1px solid #3E3E3E;
                min-height: 300px;
            }
            QTableView::item {
                padding: 6px;
            }
            QTableView::item:selected {
                background-color: #007ACC;
            }
            QHeaderView::section {
                background-color: #2D2D2D;
                color: #CCCCCC;
                padding: 6px;
                border: 1px solid #3E3E3E;
                min-height: 30px;
            }
        """)
        self._table.doubleClicked.connect(self._on_row_double_clicked)
        self._table.clicked.connect(self._on_row_clicked)

        # 右键菜单
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_context_menu)

        layout.addWidget(self._table)

        # 状态栏
        self._status_label = QLabel("就绪")
        self._status_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self._status_label)

    def _on_scan_clicked(self):
        if self._scan_btn.text() == "开始扫描":
            duration = float(self._duration_spin.value())
            self._scan_btn.setText("停止扫描")
            self._scan_btn.setStyleSheet("""
                QPushButton {
                    background-color: #CE9178;
                    color: white;
                    border: none;
                    padding: 6px;
                    border-radius: 3px;
                    font-weight: 500;
                }
                QPushButton:hover { background-color: #D4A585; }
            """)
            self._status_label.setText("扫描中...")
            self.scan_requested.emit(duration)
        else:
            self._scan_btn.setText("开始扫描")
            self._scan_btn.setStyleSheet("""
                QPushButton {
                    background-color: #007ACC;
                    color: white;
                    border: none;
                    padding: 6px;
                    border-radius: 3px;
                    font-weight: 500;
                }
                QPushButton:hover { background-color: #1A8BDD; }
            """)
            self._status_label.setText("已停止")
            self.stop_requested.emit()

    def _on_row_double_clicked(self, index):
        """双击行 → 连接"""
        dev = self._model.get_device_at(index.row())
        if dev:
            self.connect_requested.emit(dev.address)

    def _on_row_clicked(self, index):
        """单击行 — 如果点击的是操作列（第3列），触发连接"""
        if index.column() == 3:
            dev = self._model.get_device_at(index.row())
            if dev:
                self.connect_requested.emit(dev.address)

    def _on_context_menu(self, pos):
        """右键菜单"""
        index = self._table.indexAt(pos)
        if not index.isValid():
            return

        dev = self._model.get_device_at(index.row())
        if not dev:
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #252526;
                color: #D4D4D4;
                border: 1px solid #3E3E3E;
            }
            QMenu::item:selected {
                background-color: #007ACC;
            }
        """)

        connect_action = QAction("连接", self)
        connect_action.triggered.connect(lambda: self.connect_requested.emit(dev.address))
        menu.addAction(connect_action)

        menu.exec(self._table.mapToGlobal(pos))

    def update_devices(self, devices: list[DeviceInfo]):
        """更新扫描到的设备"""
        self._model.set_devices(devices)
        self._status_label.setText(f"发现 {len(devices)} 个设备")

    def set_history(self, history: list[ConnectionHistoryEntry]):
        """设置连接历史"""
        self._model.set_history(history)

    def set_scanning(self, scanning: bool):
        """设置扫描状态"""
        if scanning:
            self._scan_btn.setText("停止扫描")
            self._status_label.setText("扫描中...")
        else:
            self._scan_btn.setText("开始扫描")
            self._status_label.setText("就绪")

    def set_connected(self, connected: bool, address: str = ""):
        """设置连接状态"""
        self._connected = connected
        self._connected_address = address

        # 更新模型中的连接地址（用于显示"已连接"）
        self._model.set_connected_address(address if connected else "")

        # 断开按钮
        self._disconnect_btn.setVisible(connected)

        # 扫描按钮：连接后仍然可以扫描
        # 不再禁用扫描

        if connected:
            self._status_label.setText(f"已连接: {address}")
        else:
            self._status_label.setText("就绪")
