"""最小化 BLE 断开测试 — 不使用 Qt UI"""
import sys
import asyncio
import signal
import traceback
from pathlib import Path

# 启用 faulthandler
import faulthandler
crash_log = Path(__file__).parent / "crash_minimal.log"
faulthandler.enable(file=open(crash_log, "w"))

sys.path.insert(0, str(Path(__file__).parent))

from bleak import BleakClient
import qasync
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer


async def test_bleak_disconnect():
    """测试 Bleak 在设备断开时的行为"""
    print("扫描设备...")
    from bleak import BleakScanner
    devices = await BleakScanner.discover(timeout=3.0)

    if not devices:
        print("未发现设备")
        return

    # 选择第一个有名称的设备
    target = None
    for d in devices:
        if d.name:
            target = d
            break

    if not target:
        print("没有可用的 BLE 设备")
        return

    print(f"连接到 {target.name} ({target.address})...")

    # 不使用 disconnected_callback
    client = BleakClient(target.address)

    try:
        await client.connect()
        print(f"已连接，MTU={client.mtu_size}")

        # 轮询连接状态
        for i in range(30):  # 最多等 30 秒
            await asyncio.sleep(1)
            try:
                if not client.is_connected:
                    print("设备已断开（通过轮询检测到）")
                    break
            except Exception as e:
                print(f"检查连接状态时出错: {e}")
                break
            print(f"  {i+1}s - 连接中...")
        else:
            print("超时，主动断开")
    except Exception as e:
        print(f"连接/断开过程中出错: {e}")
        traceback.print_exc()
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass
        print("测试完成")


def main():
    print("=" * 60)
    print("最小化 BLE 断开测试")
    print("=" * 60)

    # 创建 QApplication（qasync 需要）
    app = QApplication(sys.argv)

    # 创建 qasync 事件循环
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    print("事件循环已启动")

    # 运行测试
    try:
        loop.run_until_complete(test_bleak_disconnect())
    except KeyboardInterrupt:
        print("\n用户中断")
    except Exception as e:
        print(f"\n未捕获异常: {e}")
        traceback.print_exc()

    print("程序正常退出")


if __name__ == "__main__":
    main()
