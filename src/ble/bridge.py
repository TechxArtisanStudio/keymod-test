"""异步桥接工具（备用）"""
# 当前实现中，BLEClient 直接继承 QObject 并使用 pyqtSignal
# 此模块保留用于更复杂的异步-Qt 桥接场景

from PyQt6.QtCore import QObject, pyqtSignal, QTimer
import asyncio


class AsyncBridge(QObject):
    """异步任务桥接到 Qt 信号（备用工具类）"""
    task_completed = pyqtSignal(object)
    task_failed = pyqtSignal(str)

    def __init__(self):
        super().__init__()

    def run_async(self, coro):
        """在后台运行异步任务，完成后发射信号"""
        async def wrapper():
            try:
                result = await coro
                # 使用 QTimer 确保在主线程发射信号
                QTimer.singleShot(0, lambda: self.task_completed.emit(result))
            except Exception as e:
                QTimer.singleShot(0, lambda: self.task_failed.emit(str(e)))

        asyncio.create_task(wrapper())
