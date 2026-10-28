"""ECM 网络测试面板"""
import asyncio
import subprocess
import platform
from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFrame, QTextEdit, QGroupBox, QGridLayout,
    QLineEdit, QCheckBox, QProgressBar
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QThread, pyqtSlot
from PyQt6.QtGui import QFont, QColor, QTextCharFormat
from protocol.ch9329 import CH9329Frame
from ui.widgets import LogArea


class PingWorker(QThread):
    """异步 Ping 工作线程"""
    result_ready = pyqtSignal(bool, str, float)  # success, ip, latency_ms
    finished_all = pyqtSignal()

    def __init__(self, ip: str, count: int = 3, timeout: int = 2000):
        super().__init__()
        self.ip = ip
        self.count = count
        self.timeout = timeout
        self._cancelled = False

    def run(self):
        """执行 ping"""
        try:
            system = platform.system().lower()
            if system == "windows":
                cmd = ["ping", "-n", str(self.count), "-w", str(self.timeout), self.ip]
            else:
                cmd = ["ping", "-c", str(self.count), "-W", str(self.timeout // 1000), self.ip]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=(self.timeout * self.count / 1000) + 5)
            output = result.stdout + result.stderr

            # 解析延迟
            latency = 0.0
            if result.returncode == 0:
                # 尝试提取平均延迟
                import re
                if system == "windows":
                    match = re.search(r"Average = (\d+)ms", output)
                else:
                    match = re.search(r"min/avg/max/mdev = [\d.]+/([\d.]+)/", output)
                if match:
                    latency = float(match.group(1))

            success = (result.returncode == 0)
            self.result_ready.emit(success, self.ip, latency)
        except subprocess.TimeoutExpired:
            self.result_ready.emit(False, self.ip, 0.0)
        except Exception as e:
            self.result_ready.emit(False, self.ip, 0.0)
        finally:
            if not self._cancelled:
                self.finished_all.emit()

    def cancel(self):
        self._cancelled = True


class ECMTestPanel(QWidget):
    """ECM 网络测试面板"""

    send_requested = pyqtSignal(bytes)

    def __init__(self):
        super().__init__()
        self._connected = False
        self._ecm_info = {}
        self._ping_worker: Optional[PingWorker] = None
        self._setup_ui()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        # 标题
        title = QLabel("ECM 网络连通性测试")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #CCCCCC;")
        outer.addWidget(title)

        # 说明横幅
        info = QFrame()
        info.setFrameShape(QFrame.Shape.StyledPanel)
        info.setStyleSheet("""
            QFrame {
                background-color: #1E2D3E;
                border: 1px solid #3E6E8E;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(10, 8, 10, 8)

        info_label = QLabel(
            "ECM (Ethernet Control Model) 允许设备通过 USB 虚拟网卡。\n"
            "通过蓝牙发送命令获取 IP 配置，然后测试网络连通性。"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #8AB4F8; font-size: 12px;")
        info_layout.addWidget(info_label)

        outer.addWidget(info)

        # 连接状态
        self._conn_label = QLabel("● 未连接")
        self._conn_label.setStyleSheet("color: #F44747; font-size: 12px; font-weight: 500;")
        outer.addWidget(self._conn_label)

        # IP 信息显示区域
        ip_group = QGroupBox("ECM IP 配置")
        ip_group.setStyleSheet("""
            QGroupBox {
                color: #CCCCCC;
                font-weight: bold;
                border: 1px solid #3E3E3E;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        ip_layout = QGridLayout(ip_group)
        ip_layout.setSpacing(8)
        ip_layout.setContentsMargins(12, 20, 12, 12)

        # 标签
        self._ip_labels = {}
        fields = [
            ("host_ip", "Host IP:"),
            ("dev_ip", "Target IP:"),
            ("subnet", "子网掩码:"),
            ("gateway", "网关:"),
            ("mac", "MAC 地址:"),
        ]
        for i, (key, label_text) in enumerate(fields):
            label = QLabel(label_text)
            label.setStyleSheet("color: #888; font-size: 12px;")
            ip_layout.addWidget(label, i, 0)

            value = QLabel("—")
            value.setStyleSheet("color: #D4D4D4; font-size: 12px; font-family: Monaco, Consolas, monospace;")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self._ip_labels[key] = value
            ip_layout.addWidget(value, i, 1)

        outer.addWidget(ip_group)

        # 操作按钮区域
        btn_group = QGroupBox("测试操作")
        btn_group.setStyleSheet("""
            QGroupBox {
                color: #CCCCCC;
                font-weight: bold;
                border: 1px solid #3E3E3E;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        btn_layout = QVBoxLayout(btn_group)
        btn_layout.setSpacing(8)
        btn_layout.setContentsMargins(12, 20, 12, 12)

        # 获取 IP 按钮
        self._get_ip_btn = QPushButton("🔍 获取 ECM IP 配置")
        self._get_ip_btn.setFixedHeight(36)
        self._get_ip_btn.setEnabled(False)
        self._get_ip_btn.setStyleSheet(self._btn_style("#007ACC"))
        self._get_ip_btn.clicked.connect(self._on_get_ip_clicked)
        btn_layout.addWidget(self._get_ip_btn)

        # Ping 测试按钮
        self._ping_btn = QPushButton("🏓 Ping 测试连通性")
        self._ping_btn.setFixedHeight(36)
        self._ping_btn.setEnabled(False)
        self._ping_btn.setStyleSheet(self._btn_style("#4CAF50"))
        self._ping_btn.clicked.connect(self._on_ping_clicked)
        btn_layout.addWidget(self._ping_btn)

        # 进度条
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # 不确定模式
        self._progress.setVisible(False)
        self._progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #3E3E3E;
                border-radius: 3px;
                background-color: #252526;
                text-align: center;
                color: #CCCCCC;
            }
            QProgressBar::chunk {
                background-color: #007ACC;
                border-radius: 2px;
            }
        """)
        btn_layout.addWidget(self._progress)

        outer.addWidget(btn_group)

        # 日志区域
        self._log = LogArea()
        self._log.setMinimumHeight(150)
        outer.addWidget(self._log, stretch=1)

    def _btn_style(self, color: str) -> str:
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: 600;
                font-size: 13px;
            }}
            QPushButton:hover {{ background-color: {self._darken_color(color)}; }}
            QPushButton:pressed {{ background-color: {self._darken_color(color, 0.3)}; }}
            QPushButton:disabled {{ background-color: #3E3E42; color: #888; }}
        """

    def _darken_color(self, color: str, factor: float = 0.15) -> str:
        """简单的颜色加深"""
        color = color.lstrip('#')
        r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
        r = max(0, int(r * (1 - factor)))
        g = max(0, int(g * (1 - factor)))
        b = max(0, int(b * (1 - factor)))
        return f"#{r:02X}{g:02X}{b:02X}"

    def set_connection_state(self, connected: bool):
        """更新连接状态"""
        self._connected = connected
        if connected:
            self._conn_label.setText("● 已连接")
            self._conn_label.setStyleSheet("color: #4EC9B0; font-size: 12px; font-weight: 500;")
        else:
            self._conn_label.setText("● 未连接")
            self._conn_label.setStyleSheet("color: #F44747; font-size: 12px; font-weight: 500;")

        self._get_ip_btn.setEnabled(connected)
        self._ping_btn.setEnabled(connected and bool(self._ecm_info))

    def _on_get_ip_clicked(self):
        """获取 ECM IP 配置"""
        if not self._connected:
            self._log.append_err("设备未连接")
            return

        self._log.append_sys("正在获取 ECM IP 配置...")
        frame = CH9329Frame(addr=0x00, cmd=0x27, payload=b"")
        data = frame.to_bytes()
        self._log.append_tx(data)
        self.send_requested.emit(data)

    def _on_ping_clicked(self):
        """Ping 测试"""
        if not self._connected:
            self._log.append_err("设备未连接")
            return

        # 优先 ping Target IP，其次 Host IP
        target_ip = self._ecm_info.get("dev_ip") or self._ecm_info.get("host_ip")
        if not target_ip or target_ip == "—":
            self._log.append_err("没有可用的 IP 地址，请先获取 IP 配置")
            return

        self._log.append_sys(f"正在 Ping {target_ip}...")
        self._ping_btn.setEnabled(False)
        self._progress.setVisible(True)

        # 取消之前的 ping
        if self._ping_worker and self._ping_worker.isRunning():
            self._ping_worker.cancel()
            self._ping_worker.wait(1000)

        self._ping_worker = PingWorker(target_ip, count=3)
        self._ping_worker.result_ready.connect(self._on_ping_result)
        self._ping_worker.finished_all.connect(self._on_ping_finished)
        self._ping_worker.start()

    @pyqtSlot(bool, str, float)
    def _on_ping_result(self, success: bool, ip: str, latency: float):
        """Ping 结果处理"""
        if success:
            self._log.append_sys(f"✓ Ping {ip} 成功！平均延迟: {latency:.1f} ms")
        else:
            self._log.append_err(f"✗ Ping {ip} 失败（超时或不可达）")

    @pyqtSlot()
    def _on_ping_finished(self):
        """Ping 完成"""
        self._ping_btn.setEnabled(True)
        self._progress.setVisible(False)

    def handle_response(self, frame: CH9329Frame):
        """处理响应帧"""
        # 0x27 Get ECM IP 响应
        if frame.cmd == 0xA7:  # 响应命令 = 0x27 | 0x80
            self._parse_ecm_ip_response(frame)

    def _parse_ecm_ip_response(self, frame: CH9329Frame):
        """解析 Get ECM IP 响应 (21 字节)"""
        if len(frame.payload) < 21:
            self._log.append_err(f"响应数据长度不足: {len(frame.payload)} 字节 (期望 21)")
            return

        payload = frame.payload

        # 解析：前 4 字节 Host IP，接下来 4 字节 Dev IP，4 字节 Subnet，4 字节 Gateway，6 字节 MAC
        # 假设响应格式：[host_ip(4)][dev_ip(4)][subnet(4)][gateway(4)][mac(6)]
        host_ip = ".".join(str(b) for b in payload[0:4])
        dev_ip = ".".join(str(b) for b in payload[4:8])
        subnet = ".".join(str(b) for b in payload[8:12])
        gateway = ".".join(str(b) for b in payload[12:16])
        mac = ":".join(f"{b:02X}" for b in payload[16:22])

        self._ecm_info = {
            "host_ip": host_ip,
            "dev_ip": dev_ip,
            "subnet": subnet,
            "gateway": gateway,
            "mac": mac,
        }

        # 更新 UI
        self._ip_labels["host_ip"].setText(host_ip)
        self._ip_labels["dev_ip"].setText(dev_ip)
        self._ip_labels["subnet"].setText(subnet)
        self._ip_labels["gateway"].setText(gateway)
        self._ip_labels["mac"].setText(mac)

        self._log.append_sys(f"✓ 获取到 ECM IP 配置:")
        self._log.append_sys(f"  Host IP: {host_ip}")
        self._log.append_sys(f"  Target IP: {dev_ip}")
        self._log.append_sys(f"  子网掩码: {subnet}")
        self._log.append_sys(f"  网关: {gateway}")
        self._log.append_sys(f"  MAC: {mac}")

        # 启用 Ping 按钮
        self._ping_btn.setEnabled(self._connected)

    def append_rx(self, data: bytes):
        """显示接收数据"""
        self._log.append_rx(data)
        # 尝试解析响应
        try:
            frame = CH9329Frame.from_bytes(data)
            self.handle_response(frame)
        except Exception:
            pass

    def append_err(self, msg: str):
        self._log.append_err(msg)

    def append_sys(self, msg: str):
        self._log.append_sys(msg)