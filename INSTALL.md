# Keymod BLE Tester - 环境配置指南

## 系统要求

- **Python**: 3.9 或更高版本（推荐 3.10+）
- **操作系统**: macOS / Windows / Linux
- **硬件**: 支持 BLE 的蓝牙适配器

## 快速开始

### 1. 克隆项目

```bash
git clone <repository-url>
cd Opf_test
```

### 2. 创建虚拟环境（推荐）

#### macOS / Linux
```bash
python3 -m venv venv
source venv/bin/activate
```

#### Windows
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 运行应用

```bash
# 方式 1：直接运行
python src/main.py

# 方式 2：作为模块运行
python -m src.main
```

## 详细安装步骤

### macOS

1. **安装 Python 3.9+**
   ```bash
   # 使用 Homebrew
   brew install python@3.11
   
   # 或使用官方安装包
   # https://www.python.org/downloads/macos/
   ```

2. **安装依赖**
   ```bash
   # 激活虚拟环境后
   pip install -r requirements.txt
   ```

3. **macOS 特殊说明**
   - 首次运行可能需要允许蓝牙权限：系统设置 → 隐私与安全性 → 蓝牙
   - 如果使用系统 Python，可能需要安装 Xcode Command Line Tools：
     ```bash
     xcode-select --install
     ```

### Windows

1. **安装 Python 3.9+**
   - 下载并安装：https://www.python.org/downloads/windows/
   - 安装时勾选 "Add Python to PATH"

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **蓝牙驱动**
   - 确保蓝牙适配器驱动已安装
   - Windows 10/11 通常自动支持 BLE

### Linux

1. **安装系统依赖**
   ```bash
   # Ubuntu/Debian
   sudo apt-get update
   sudo apt-get install python3 python3-pip python3-venv
   sudo apt-get install libgl1-mesa-glx libglib2.0-0  # PyQt6 依赖
   
   # Fedora
   sudo dnf install python3 python3-pip
   ```

2. **安装 Python 依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **蓝牙权限**
   ```bash
   # 添加用户到 bluetooth 组
   sudo usermod -aG bluetooth $USER
   
   # 重启或重新登录
   ```

## VSCode 配置

### 推荐扩展

1. **Python** (ms-python.python)
2. **Pylance** (ms-python.vscode-pylance)
3. **Python Debugger** (ms-python.debugpy)

### 配置步骤

1. **打开项目**
   ```bash
   code /Users/txa/project/Opf_test
   ```

2. **选择 Python 解释器**
   - 按 `Cmd+Shift+P` (macOS) 或 `Ctrl+Shift+P` (Windows/Linux)
   - 输入 `Python: Select Interpreter`
   - 选择 `./venv/bin/python` (或 `.\venv\Scripts\python.exe` on Windows)

3. **运行/调试**
   - 按 `F5` 或点击调试按钮
   - 选择配置 "Run App (GUI)"

### 常见问题

#### "No module named debugpy"
```bash
pip install debugpy
```

#### "ModuleNotFoundError: No module named 'PyQt6'"
确保已激活虚拟环境并安装依赖：
```bash
source venv/bin/activate  # macOS/Linux
# 或
venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

#### macOS: "Permission denied" 或蓝牙错误
- 检查系统设置 → 隐私与安全性 → 蓝牙，确保终端或 Python 有权限
- 尝试重启蓝牙服务或重启电脑

## 依赖说明

### 核心依赖

| 包名 | 版本 | 用途 |
|------|------|------|
| PyQt6 | ≥6.6 | GUI 框架 |
| bleak | ≥0.22 | BLE 通信（跨平台） |
| qasync | ≥0.11 | asyncio 与 Qt 事件循环集成 |

### 开发依赖

| 包名 | 版本 | 用途 |
|------|------|------|
| pytest | ≥8.0 | 测试框架 |
| pytest-asyncio | ≥0.23 | 异步测试支持 |
| debugpy | latest | VSCode 调试支持 |

### 平台特定依赖

#### macOS
- `pyobjc-core` - Objective-C 桥接
- `pyobjc-framework-CoreBluetooth` - CoreBluetooth API
- `pyobjc-framework-Cocoa` - Cocoa API
- `pyobjc-framework-libdispatch` - GCD 支持

#### Windows
- bleak 自动使用 WinRT 后端

#### Linux
- bleak 使用 BlueZ 后端
- 需要 `bluez` 系统包

## 故障排除

### 应用无法启动

1. **检查 Python 版本**
   ```bash
   python --version
   # 应该显示 3.9 或更高
   ```

2. **重新安装依赖**
   ```bash
   pip uninstall -r requirements.txt -y
   pip install -r requirements.txt
   ```

3. **清除缓存**
   ```bash
   find . -type d -name "__pycache__" -exec rm -rf {} +
   find . -type f -name "*.pyc" -delete
   ```

### BLE 连接问题

1. **检查蓝牙是否开启**
   ```bash
   # macOS
   system_profiler SPBluetoothDataType
   
   # Linux
   bluetoothctl show
   ```

2. **重启蓝牙服务**
   ```bash
   # macOS
   sudo killall bluetoothd
   
   # Linux
   sudo systemctl restart bluetooth
   ```

3. **检查设备是否在范围内**
   - 确保设备已开机且可被发现
   - 距离不超过 10 米

### VSCode 调试问题

1. **重新加载窗口**
   - `Cmd+Shift+P` → `Developer: Reload Window`

2. **清除 Python 扩展缓存**
   - `Cmd+Shift+P` → `Python: Clear Cache and Reload Window`

3. **检查 launch.json**
   - 确保 `python.defaultInterpreterPath` 指向正确的 venv

## 开发环境

### 代码格式化

项目使用 `black` 和 `isort` 进行代码格式化：

```bash
pip install black isort
black src/
isort src/
```

### 运行测试

```bash
# 运行所有测试
pytest tests/

# 运行特定测试
pytest tests/test_protocol.py

# 带覆盖率
pytest --cov=src tests/
```

### 项目结构

```
Opf_test/
├── src/
│   ├── main.py              # 应用入口
│   ├── config.py            # 配置常量
│   ├── ui/                  # GUI 组件
│   │   ├── main_window.py   # 主窗口
│   │   ├── scan_panel.py    # 扫描面板
│   │   ├── command_panel.py # 命令面板
│   │   ├── ble_name_panel.py # BLE 名称修改
│   │   ├── ecm_test_panel.py # ECM 网络测试
│   │   └── widgets.py       # 通用组件
│   ├── ble/                 # BLE 通信
│   │   ├── scanner.py       # BLE 扫描
│   │   └── client.py        # BLE 客户端
│   └── protocol/            # 协议实现
│       ├── ch9329.py        # CH9329 协议
│       └── models.py        # 数据模型
├── tests/                   # 测试用例
├── docs/                    # 文档
├── requirements.txt         # 依赖列表
└── README.md               # 项目说明
```

## 更新日志

### 2026-10-27
- 添加 BLE 名称修改功能
- 添加 ECM 网络测试功能
- 修复 macOS 上的崩溃问题
- 改进 VSCode 调试配置

### 2026-10-26
- 初始版本
- 基础 BLE 扫描和连接
- CH9329 协议支持
- 命令面板

## 获取帮助

如遇问题，请：
1. 检查本文档的故障排除部分
2. 查看 README.md
3. 提交 Issue 到项目仓库
