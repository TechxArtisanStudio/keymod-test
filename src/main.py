"""Keymod BLE Tester — 入口"""
import sys
import asyncio
import traceback
import faulthandler
import os
from pathlib import Path

# 启用 faulthandler — 崩溃时输出 Python 栈到 stderr
faulthandler.enable()

# 确保 src 目录在 Python 路径中
src_path = Path(__file__).parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
import qasync
from ui.main_window import MainWindow


def exception_hook(exctype, value, tb):
    """全局异常钩子 — 防止未捕获异常导致闪退，并写入日志文件"""
    crash_file = Path(__file__).parent / "crash.log"
    try:
        with open(crash_file, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"未捕获异常: {exctype.__name__}: {value}\n")
            f.write(''.join(traceback.format_exception(exctype, value, tb)))
            f.write(f"{'='*60}\n")
    except Exception:
        pass

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"未捕获异常: {exctype.__name__}: {value}", file=sys.stderr)
    print(''.join(traceback.format_exception(exctype, value, tb)), file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)


def asyncio_exception_handler(loop, context):
    """asyncio 异常处理器 — 防止异步任务异常导致闪退"""
    exception = context.get('exception')
    message = context.get('message', '未知错误')

    crash_file = Path(__file__).parent / "crash.log"
    try:
        with open(crash_file, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"asyncio 异常: {message}\n")
            if exception:
                f.write(''.join(traceback.format_exception(type(exception), exception, exception.__traceback__)))
            f.write(f"{'='*60}\n")
    except Exception:
        pass

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"asyncio 异常: {message}", file=sys.stderr)
    if exception:
        print(''.join(traceback.format_exception(type(exception), exception, exception.__traceback__)), file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)


def signal_handler(signum, frame):
    """信号处理器 — 捕获崩溃信号并输出栈"""
    import signal
    sig_name = signal.Signals(signum).name
    crash_file = Path(__file__).parent / "crash.log"
    try:
        with open(crash_file, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"收到信号: {sig_name} ({signum})\n")
            f.write("Python 栈:\n")
            traceback.print_stack(frame, file=f)
            f.write(f"{'='*60}\n")
    except Exception:
        pass
    print(f"\n收到信号 {sig_name}，栈信息已写入 {crash_file}", file=sys.stderr)
    # 不退出，让 faulthandler 处理


def main():
    """主函数"""
    import signal

    # 注册信号处理器（捕获崩溃信号）
    for sig in (signal.SIGSEGV, signal.SIGABRT, signal.SIGBUS):
        signal.signal(sig, signal_handler)

    # 设置全局异常钩子
    sys.excepthook = exception_hook

    # 启用高 DPI 支持
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # 创建 QApplication
    app = QApplication(sys.argv)
    app.setApplicationName("Keymod BLE Tester")
    app.setOrganizationName("TechxArtisanStudio")

    # 设置深色主题样式
    app.setStyle("Fusion")
    app.setPalette(_create_dark_palette())

    # 集成 qasync（让 asyncio 和 Qt 事件循环共存）
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    # 设置 asyncio 异常处理器
    loop.set_exception_handler(asyncio_exception_handler)

    # 创建主窗口
    window = MainWindow()
    window.show()

    # 运行事件循环
    with loop:
        loop.run_forever()


def _create_dark_palette():
    """创建深色主题调色板"""
    from PyQt6.QtGui import QPalette, QColor
    from PyQt6.QtCore import Qt

    palette = QPalette()

    # 基础色
    palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(212, 212, 212))
    palette.setColor(QPalette.ColorRole.Base, QColor(37, 37, 38))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(45, 45, 48))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(37, 37, 38))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(212, 212, 212))
    palette.setColor(QPalette.ColorRole.Text, QColor(212, 212, 212))
    palette.setColor(QPalette.ColorRole.Button, QColor(45, 45, 48))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(212, 212, 212))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 51, 51))
    palette.setColor(QPalette.ColorRole.Link, QColor(86, 156, 214))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 122, 204))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))

    # 禁用色
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(128, 128, 128))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(128, 128, 128))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(128, 128, 128))

    return palette


if __name__ == "__main__":
    main()
