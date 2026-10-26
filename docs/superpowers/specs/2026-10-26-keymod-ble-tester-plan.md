# Keymod BLE Tester — 实施计划

> 基于 2026-10-26 与用户确认的设计，本计划按里程碑拆分任务，每个里程碑交付可验收的最小功能切片。

## 1. 项目定位

一款 **PyQt6 桌面 BLE 测试工具**，用于现场调试 Openterface KeyMod 硬件：
- 扫描并列出周围 BLE 设备
- 手动连接指定设备
- 发送 CH9329 兼容协议命令
- 查看/解析响应帧
- 持久化连接历史，支持一键重连

---

## 2. 技术栈

| 层 | 选型 | 版本约束 |
|----|------|----------|
| GUI | PyQt6 | ≥ 6.6 |
| BLE | bleak | ≥ 0.22 |
| 异步桥 | qasync | ≥ 0.11（替代 asyncqt） |
| 持久化 | QSettings（INI） | 连接历史 |
| Python | 3.10+ | 类型提示、match-case |

---

## 3. 目录结构（最终态）

```
keymod-test/
├── README.md
├── requirements.txt
├── src/
│   ├── main.py                      # 入口，启动 Qt + asyncio 事件循环
│   ├── ui/
│   │   ├── main_window.py           # 主窗口，组装 ScanPanel + CommandPanel
│   │   ├── scan_panel.py            # 扫描面板：设备表格 + 连接历史
│   │   ├── command_panel.py         # 命令面板：发送区 + 日志 + 折叠控制
│   │   ├── command_palette.py       # 可视化命令卡片网格
│   │   └── widgets.py               # 复用小部件（HexLineEdit、StatusBadge…）
│   ├── ble/
│   │   ├── scanner.py               # BleakScanner 封装
│   │   ├── client.py                # BleakClient 封装（连接/断开/收发）
│   │   └── bridge.py                # asyncio ↔ Qt 信号桥
│   ├── protocol/
│   │   ├── __init__.py
│   │   ├── ch9329.py                # 帧编解码 + checksum
│   │   └── models.py                # CommandMeta / DeviceInfo / ResponseFrame
│   └── config.py                    # 常量、UUID、默认值
├── tests/
│   ├── test_ch9329.py               # 协议单测
│   └── test_models.py
└── docs/
    └── superpowers/
        └── specs/
            ├── 2026-10-26-keymod-ble-tester-design.md   # 设计文档（本文件的前身）
            └── 2026-10-26-keymod-ble-tester-plan.md     # 本文件
```

---

## 4. 核心数据模型

### 4.1 CH9329 帧
```python
@dataclass
class CH9329Frame:
    addr: int              # 通常 0x00
    cmd: int               # 命令字节
    payload: bytes         # 不含 header/checksum
    
    HEADER = b'\x57\xAB'
    
    @property
    def checksum(self) -> int:
        """8-bit 加和校验"""
        total = 0x57 + 0xAB + self.addr + self.cmd + len(self.payload)
        return (total + sum(self.payload)) & 0xFF
    
    def to_bytes(self) -> bytes:
        frame = self.HEADER + bytes([self.addr, self.cmd, len(self.payload)]) + self.payload
        return frame + bytes([self.checksum])
    
    @classmethod
    def from_bytes(cls, data: bytes) -> "CH9329Frame":
        if len(data) < 6:
            raise ValueError("Frame too short")
        if data[:2] != cls.HEADER:
            raise ValueError("Invalid header")
        addr = data[2]
        cmd = data[3]
        plen = data[4]
        if len(data) != 5 + plen + 1:
            raise ValueError("Length mismatch")
        payload = data[5:5+plen]
        expected_cs = sum(data[:-1]) & 0xFF
        if data[-1] != expected_cs:
            raise ValueError("Checksum mismatch")
        return cls(addr, cmd, payload)
```

### 4.2 命令元数据（供 UI 自动生成面板）
```python
@dataclass
class CommandMeta:
    cmd: int
    name: str
    payload_desc: str           # 人类可读的 payload 结构描述
    resp_len: int | None        # 预期响应长度，None 表示变长
    tooltip_rich: str           # 富文本 tooltip（Markdown 或 HTML）
    example_request: bytes      # 示例请求帧（完整字节）
    example_response: bytes     # 示例响应帧
```

> **COMMAND_META** 字典将包含文档中列出的 14 条命令（0x01, 0x02, 0x03, 0x04, 0x05, 0x08, 0x17, 0x18, 0x22, 0x23, 0x26, 0x27, 0x30, 0x31）。

### 4.3 设备信息 & 连接历史
```python
@dataclass
class DeviceInfo:
    address: str                # MAC 地址（如 "AA:BB:CC:DD:EE:FF"）
    name: str | None            # BLE 广播名（可能为 None）
    rssi: int                   # 信号强度
    last_seen: float            # 时间戳
    
@dataclass
class ConnectionHistoryEntry:
    address: str
    name: str | None
    last_connected: float       # 上次连接成功时间
    nickname: str | None        # 用户自定义别名（可选，V2 再实现）
```

---

## 5. 实施里程碑

### M0：项目脚手架 & 依赖（≤ 0.5 天）
**目标**：能 `python src/main.py` 跑起空窗口，无报错。

- [ ] 创建 `requirements.txt`
- [ ] 创建 `src/main.py`，集成 qasync + QApplication
- [ ] 创建空 `MainWindow`，显示标题 "Keymod BLE Tester"
- [ ] 验证：窗口能弹出、关闭无残留进程

**验收**：
```bash
pip install -r requirements.txt
python src/main.py
# 窗口正常显示
```

---

### M1：BLE 扫描 & 设备列表（1 天）
**目标**：扫描周围 BLE 设备，表格显示 Name / Address / RSSI，按信号强度排序。

#### 任务拆解
1. `ble/scanner.py` — `BLEScanner` 类
   - `async def start(duration: float = 5.0) -> AsyncGenerator[DeviceInfo, None]`
   - 使用 `BleakScanner.discover()` 或 `start()` + 回调
   - 去重（按 MAC），持续更新 RSSI
2. `ui/scan_panel.py` — `ScanPanel(QWidget)`
   - `QTableView` + `QStandardItemModel`
   - 列：Name | Address | RSSI | "连接" 按钮
   - 顶部：开始扫描 / 停止扫描 按钮 + 扫描时长输入
   - 信号：`device_discovered(DeviceInfo)`、`connect_requested(str)`
3. `ble/bridge.py` — `AsyncBridge`
   - 将 asyncio 任务中的信号发射桥接到 Qt 主线程（使用 `QMetaObject.invokeMethod` 或 `QTimer.singleShot(0, ...)`）
4. `ui/main_window.py` — 组装 ScanPanel

**验收**：
- 点"开始扫描"，5 秒内表格出现周围设备
- 列表按 RSSI 降序排列
- 重复扫描去重

---

### M2：BLE 连接 & 状态管理（1 天）
**目标**：点击"连接"按钮，成功连接设备；状态栏显示连接状态；断开后回到扫描态。

#### 任务拆解
1. `ble/client.py` — `BLEClient(QObject)`
   - `async def connect(address: str)`
   - 自动发现 GATT 服务/特征（优先 Nordic UART，其次 0xFFE0/0xFFE1，再其次 0xFFF0/0xFFF1）
   - 启用 notify（RX 特征）
   - 信号：`connected()`、`disconnected()`、`response_received(bytes)`
   - `async def send(frame: CH9329Frame)`
   - `async def disconnect()`
2. `ui/scan_panel.py`
   - 连接中禁用扫描/其他连接按钮
   - 连接成功后自动折叠扫描面板（可选）
3. `ui/main_window.py`
   - 状态栏：显示 "Disconnected" / "Connecting..." / "Connected: AA:BB:CC:DD:EE:FF"
   - 连接成功 → 显示 CommandPanel

**验收**：
- 能连上 keymod 设备（或任意 BLE 串口设备）
- 断开（拔设备/点断开）后 UI 回到扫描态
- 异常（超时、信号差）不崩溃，状态栏提示错误

---

### M3：命令面板骨架 & 折叠交互（0.5 天）
**目标**：连接成功后显示 CommandPanel，**默认折叠**（仅显示标题栏 "Command Panel ▶"），点击展开。

#### 任务拆解
1. `ui/command_panel.py` — `CommandPanel(QWidget)`
   - 顶部标题栏：标题 + 折叠按钮（▶/▼）+ 关闭按钮（可选）
   - 内容区：`QSplitter` 垂直分割
     - 上半：`CommandPalette`（命令卡片网格）
     - 下半：`SendArea` + `LogArea`
   - 折叠状态持久化（QSettings）
2. `ui/command_panel.py` — 发送区
   - `QPlainTextEdit`（Hex 输入）
   - 输入模式切换：Hex / ASCII（暂只实现 Hex）
   - "自动补校验和" 复选框（默认开启）
   - "发送" 按钮
3. `ui/command_panel.py` — 日志区
   - `QPlainTextEdit`（只读）
   - TX=蓝、RX=绿、ERR=红、系统=灰
   - 右键菜单：复制、清空、导出 .txt

**验收**：
- CommandPanel 默认折叠
- 点击标题栏展开/折叠
- 发送区能输入 hex，点发送（即使设备未响应也不崩溃）
- 日志区正确记录发送内容

---

### M4：可视化命令面板（CommandPalette）（1.5 天）
**目标**：14 条命令以卡片形式展示，悬停显示 Tooltip（帧结构、Payload 说明、示例），点击预填发送区。

#### 任务拆解
1. `protocol/ch9329.py` — 补全 `COMMAND_META` 字典
   - 每条命令的 tooltip_rich（HTML 格式）：
     - 帧结构表格
     - Payload 字段逐字节解释
     - 请求/响应示例（十六进制 + ASCII 对照）
     - 常见错误码
2. `protocol/models.py` — `CommandMeta` 数据类
3. `ui/command_palette.py` — `CommandPalette(QWidget)`
   - `QScrollArea` + `QGridLayout`（每行 4-6 张卡片）
   - 每张卡片：`QFrame` + 标题 + 命令字节（如 "0x02"）
   - 悬停：显示富文本 Tooltip（`setToolTip()`）
   - 点击：发射 `command_selected(cmd: int)` 信号
4. `ui/command_panel.py`
   - 监听 `command_selected` → 预填发送区（自动补全 payload 结构）

**验收**：
- 14 张卡片正确渲染
- 悬停 0x02 看到 8-byte payload 结构图
- 点击 0x01 → 发送区自动填入 `57 AB 00 01 00`（无 payload，自动补校验和）
- 点击 0x02 → 发送区填入 `57 AB 00 02 08 00 00 00 00 00 00 00 00`（8 字节 0，光标停在第一个 00 处）

---

### M5：收发完整流程 & 响应解析（1 天）
**目标**：发送命令 → 收到 notify → 解析响应帧 → 日志区高亮显示。

#### 任务拆解
1. `ble/client.py` — `send()` 方法
   - 自动补校验和（如果用户未手动填）
   - 发送后等待响应（超时 3s）
   - 超时 → 日志区显示 "Timeout waiting for response"
2. `ble/client.py` — notify 回调
   - 收到字节 → 尝试解析 `CH9329Frame.from_bytes()`
   - 解析成功 → 发射 `response_received(CH9329Frame)`
   - 解析失败 → 日志区显示原始字节 + "Parse error"
3. `ui/command_panel.py` — 响应处理
   - 监听 `response_received` → 日志区追加（绿色）
   - 解析帧内容，逐字段高亮（如 0x01 响应的 8 字节状态块）

**验收**：
- 发 0x01 → 收到 8-byte 响应，日志区显示：
  ```
  RX: 57 AB 00 81 08 03 01 00 05 00 00 00 00 1A
       [Header] [Addr] [Cmd|0x80] [Len] [HW=0x03 KeyMod] [USB=0x01] [LED=0x00] [FW=0x05] ...
  ```
- 发 0x31（复位）→ 日志显示 "Device rebooting, connection will drop"
- 连续发 100 条命令不卡顿

---

### M6：连接历史持久化（0.5 天）
**目标**：记录连接过的设备，下次启动自动显示在扫描列表顶部（"常用设备" 分区）。

#### 任务拆解
1. `config.py` — `HistoryManager`
   - 使用 `QSettings("TechxArtisanStudio", "KeymodTester")`
   - `save_connection(DeviceInfo)`、`load_history() -> list[ConnectionHistoryEntry]`、`clear_history()`
   - 最多保存 20 条（FIFO）
2. `ui/scan_panel.py`
   - 表格分两区：
     - **常用设备**（顶部，背景色略深）：从历史加载
     - **新发现设备**（底部）：本次扫描发现
   - 右键菜单：从历史中移除
3. `ui/scan_panel.py` — 一键重连
   - 常用设备行的"连接"按钮始终可用（无需重新扫描）

**验收**：
- 连接一次 keymod → 关闭 app → 重启 → 常用设备区显示该设备
- 点"连接"直接连上（无需扫描）
- 最多保存 20 条，超出自动淘汰最旧的

---

### M7：打磨 & 异常处理（0.5 天）
**目标**：边界情况不崩溃，用户体验流畅。

#### 任务拆解
- [ ] 扫描时无设备 → 显示 "No devices found" 提示
- [ ] 连接超时 → 状态栏提示 "Connection timeout"
- [ ] 发送时设备已断开 → 自动重连提示 or 错误日志
- [ ] 输入非法 hex → 发送区红色高亮，禁用发送按钮
- [ ] 窗口关闭 → 自动断开 BLE 连接、保存折叠状态
- [ ] 日志区超过 10000 行 → 自动截断旧日志

---

## 6. 验收测试清单（端到端）

| 场景 | 步骤 | 预期结果 |
|------|------|----------|
| 首次扫描 | 启动 app → 点"开始扫描" | 5 秒内列出周围 BLE 设备 |
| 连接 | 点 keymod 设备的"连接" | 状态栏显示 "Connected"，CommandPanel 出现（默认折叠） |
| 展开面板 | 点标题栏 | CommandPalette 展开 |
| 发送 0x01 | 点击 0x01 卡片 → 点"发送" | 日志区显示 TX 帧 + RX 8-byte 响应 |
| 悬停 Tooltip | 悬停 0x02 卡片 | 显示 8-byte payload 结构图 |
| 断开 | 拔出 keymod USB 供电 | 状态栏回到 "Disconnected"，CommandPanel 隐藏 |
| 历史 | 重开 app | 常用设备区显示上次连接的 keymod |
| 一键重连 | 点常用设备"连接" | 直接连上，无需扫描 |

---

## 7. 依赖清单 (`requirements.txt`)

```txt
PyQt6>=6.6
bleak>=0.22
qasync>=0.11
pytest>=8.0
pytest-asyncio>=0.23
```

---

## 8. 风险 & 缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| bleak 在 macOS 需要权限 | 扫描不到设备 | README 中写明 macOS 蓝牙权限设置步骤 |
| keymod 固件 UUID 未知 | 连上但收不到数据 | 实现自动发现（Nordic UART → 0xFFE0 → 0xFFF0 依次尝试） |
| asyncio + Qt 事件循环冲突 | UI 卡顿 | 用 qasync 统一事件循环，BLE 操作全部 async |
| 协议帧解析错 | 响应显示乱码 | 单测覆盖所有命令的编解码，日志区显示原始字节兜底 |

---

## 9. 实施顺序 & 时间线

```
Day 1: M0 + M1 + M2（脚手架 + 扫描 + 连接）
Day 2: M3 + M4（命令面板骨架 + 可视化卡片）
Day 3: M5 + M6 + M7（收发流程 + 历史 + 打磨）
```

**总工时**：约 3 天（全职开发）

---

## 10. 下一步

1. ✅ 用户确认本计划
2. 🔲 创建 `requirements.txt`
3. 🔲 实现 M0（空窗口）
4. 🔲 逐步推进 M1 → M7
5. 🔲 每个里程碑完成后用户验收

---

**文档版本**：v1.0  
**最后更新**：2026-10-26  
**作者**：Claude Code (TechxArtisanStudio)
