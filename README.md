# Keymod BLE Tester

一款 PyQt6 桌面 BLE 测试工具，用于现场调试 Openterface KeyMod 硬件。

## 功能

- 🔍 **BLE 扫描**：发现周围 BLE 设备，显示名称、MAC、RSSI
- 🔗 **手动连接**：点击连接指定设备，支持一键重连
- 📡 **CH9329 协议**：完整实现 CH9329 兼容命令编解码
- 🎨 **可视化命令面板**：14 条命令以卡片形式展示，悬停显示帧结构 Tooltip，点击预填发送区
- 📜 **日志系统**：TX=蓝、RX=绿、ERR=红、系统=灰，支持导出
- 💾 **连接历史**：持久化保存最近 20 个连接过的设备
- ✏️ **BLE 名称修改**：通过命令 0x23 修改设备蓝牙名称（支持 1-20 字符）
- 🌐 **ECM 网络测试**：获取设备 ECM IP 配置，测试网络连通性（Ping）
- 📑 **多标签页界面**：命令调试、BLE 名称、ECM 网络三个独立标签页

## 安装

```bash
pip install -r requirements.txt
```

## 运行

```bash
python src/main.py
```

## 项目结构

```
keymod-test/
├── src/
│   ├── main.py              # 入口
│   ├── config.py            # 常量配置
│   ├── ui/                  # GUI 层
│   │   ├── main_window.py   # 主窗口
│   │   ├── scan_panel.py    # 扫描面板
│   │   ├── command_panel.py # 命令面板
│   │   ├── command_palette.py # 可视化命令卡片
│   │   ├── ble_name_panel.py # BLE 名称修改
│   │   ├── ecm_test_panel.py # ECM 网络测试
│   │   └── widgets.py       # 复用小部件
│   ├── ble/                 # BLE 通信层
│   │   ├── scanner.py       # BLE 扫描器
│   │   └── client.py        # BLE 客户端
│   └── protocol/            # 协议层
│       ├── ch9329.py        # CH9329 编解码
│       └── models.py        # 数据模型
├── tests/                   # 测试
├── docs/                    # 文档
├── INSTALL.md               # 环境配置指南
└── requirements.txt         # 依赖列表
```

## 使用说明

### 基本操作

1. **扫描设备**：点击"开始扫描"，等待 5 秒（可调）
2. **连接设备**：双击目标设备或右键选择"连接"
3. **发送命令**：连接成功后，命令面板出现（默认折叠）
   - 点击标题栏展开命令卡片
   - 点击卡片自动预填发送区
   - 修改 payload 后点击"发送"
4. **查看响应**：日志区显示 TX/RX 数据（彩色区分）
5. **历史重连**：下次启动自动显示连接过的设备

### 标签页功能

#### 命令调试
- 快速命令：常用命令一键发送
- 命令面板：所有支持的命令卡片
- 自定义发送：输入 HEX 或 ASCII 数据

#### BLE 名称修改
- 输入新名称（1-20 字符，仅 ASCII）
- 点击"修改名称"发送命令 0x23
- 注意：成功后设备会自动重启

#### ECM 网络测试
- 点击"获取 ECM IP 配置"读取设备网络设置
- 显示 Host IP、Target IP、子网掩码、网关、MAC
- 点击"Ping 测试连通性"测试网络（需要设备通过 USB 连接并启用 ECM 模式）

## 支持的命令

| 命令 | 名称 | 说明 |
|------|------|------|
| 0x01 | Get Info | 读取设备信息 |
| 0x02 | Keyboard | 标准键盘报文 |
| 0x03 | Media/ACPI | 媒体键/ACPI |
| 0x04 | Abs Mouse | 绝对鼠标 |
| 0x05 | Rel Mouse | 相对鼠标 |
| 0x08 | Get Param | CH9329 兼容配置 |
| 0x17 | SD Switch | SD 卡切换 |
| 0x18 | Temperature | DS18B20 温度 |
| 0x22 | BLE Security | BLE 配对/绑定 |
| 0x23 | BLE Set Name | 设置 BLE 名称 |
| 0x26 | Set ECM IP | ECM IP 配置 |
| 0x27 | Get ECM IP | 读取 ECM IP |
| 0x30 | USB Work Mode | USB 工作模式 |
| 0x31 | System Reset | 系统复位 |

## 系统要求

- Python ≥ 3.10
- macOS / Windows / Linux
- 支持 BLE 的硬件

## 开发

```bash
# 运行测试
pytest tests/

# 导出日志
Ctrl+E（在主界面）
```

## 许可证

MIT License
