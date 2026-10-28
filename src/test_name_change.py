"""测试 BLE 名称修改功能"""
import sys
import asyncio
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from bleak import BleakClient, BleakScanner
from protocol.ch9329 import CH9329Frame


async def scan_and_connect():
    """扫描并连接到设备"""
    print("=" * 60)
    print("BLE 名称修改测试")
    print("=" * 60)

    print("\n[1/4] 扫描设备...")
    devices = await BleakScanner.discover(timeout=5.0)

    if not devices:
        print("未发现设备")
        return None, None

    # 显示发现的设备
    print(f"\n发现 {len(devices)} 个设备:")
    for i, d in enumerate(devices):
        if d.name:
            print(f"  {i}: {d.name} ({d.address})")

    # 选择第一个有名称的设备，优先选择 KeyMod
    target = None
    for d in devices:
        if d.name and "KeyMod" in d.name:
            target = d
            break
    if not target:
        for d in devices:
            if d.name:
                target = d
                break

    if not target:
        print("没有可用的 BLE 设备")
        return None, None

    print(f"\n[2/4] 连接到 {target.name} ({target.address})...")
    client = BleakClient(target.address)

    try:
        await client.connect()
        print(f"✓ 已连接，MTU={client.mtu_size}")
    except Exception as e:
        print(f"✗ 连接失败: {e}")
        return None, None

    # 发现服务和特征
    print("\n[3/4] 发现服务和特征...")
    tx_char = None
    rx_char = None

    # 尝试常见的 UART 服务
    uart_services = [
        "6e400001-b5a3-f393-e0a9-e50e24dcca9e",  # Nordic UART
        "0000ffe0-0000-1000-8000-00805f9b34fb",  # HM-10
        "0000fff0-0000-1000-8000-00805f9b34fb",  # 0xFFF0
    ]

    uart_tx_chars = [
        "6e400002-b5a3-f393-e0a9-e50e24dcca9e",
        "0000ffe1-0000-1000-8000-00805f9b34fb",
        "0000fff2-0000-1000-8000-00805f9b34fb",
    ]

    uart_rx_chars = [
        "6e400003-b5a3-f393-e0a9-e50e24dcca9e",
        "0000ffe1-0000-1000-8000-00805f9b34fb",
        "0000fff1-0000-1000-8000-00805f9b34fb",
    ]

    for svc_uuid in uart_services:
        service = client.services.get_service(svc_uuid)
        if service:
            for tx_uuid, rx_uuid in zip(uart_tx_chars, uart_rx_chars):
                tx = service.get_characteristic(tx_uuid)
                rx = service.get_characteristic(rx_uuid)
                if tx and rx:
                    tx_char = tx
                    rx_char = rx
                    print(f"✓ 找到 UART 服务: {svc_uuid}")
                    print(f"  TX: {tx.uuid}")
                    print(f"  RX: {rx.uuid}")
                    break
        if tx_char:
            break

    # 如果没找到，自动发现所有支持写和 notify 的特征
    if not tx_char:
        print("  尝试自动发现特征...")
        for service in client.services:
            for char in service.characteristics:
                props = char.properties
                if "write" in props or "write-without-response" in props:
                    if tx_char is None:
                        tx_char = char
                        print(f"  找到 TX: {char.uuid} (service: {service.uuid}, props: {props})")
                if "notify" in props or "indicate" in props:
                    if rx_char is None:
                        rx_char = char
                        print(f"  找到 RX: {char.uuid} (service: {service.uuid}, props: {props})")

    if not tx_char:
        print("✗ 未找到兼容的 UART 服务")
        await client.disconnect()
        return None, None

    return client, tx_char


async def test_name_change(client, tx_char):
    """测试名称修改"""
    print("\n[4/4] 测试名称修改...")

    # 启用 notify 监听响应
    response_received = asyncio.Event()
    response_data = None

    def notify_callback(sender, data):
        nonlocal response_data
        print(f"  收到响应: {data.hex()}")
        response_data = bytes(data)
        response_received.set()

    try:
        # 尝试启用 notify（可能失败，但不影响测试）
        service = client.services.get_service(tx_char.service_uuid)
        for char in service.characteristics:
            if "notify" in char.properties or "indicate" in char.properties:
                await client.start_notify(char, notify_callback)
                print(f"✓ Notify 已启用: {char.uuid}")
                break
    except Exception as e:
        print(f"⚠ Notify 启用失败（继续测试）: {e}")

    # 测试不同的名称
    test_names = ["TestBLE1", "KeyMod-01", "MyDevice"]

    for name in test_names:
        print(f"\n尝试修改名称为: {name}")

        # 构建命令帧
        payload = name.encode('ascii')
        frame = CH9329Frame(addr=0x00, cmd=0x23, payload=payload)
        data = frame.to_bytes()

        print(f"  发送: {data.hex()}")

        try:
            # 发送命令
            await client.write_gatt_char(tx_char, data, response=False)
            print(f"  ✓ 命令已发送")

            # 等待响应（最多 2 秒）
            response_received.clear()
            try:
                await asyncio.wait_for(response_received.wait(), timeout=2.0)
                print(f"  ✓ 收到响应")
            except asyncio.TimeoutError:
                print(f"  ⚠ 未收到响应（可能设备已重启）")

            # 检查连接状态
            await asyncio.sleep(0.5)
            if client.is_connected:
                print(f"  ✓ 仍然连接")
            else:
                print(f"  ⚠ 连接已断开（设备可能已重启）")
                break

        except Exception as e:
            print(f"  ✗ 发送失败: {e}")
            traceback.print_exc()
            break

    # 清理
    print("\n清理连接...")
    try:
        if client.is_connected:
            await client.disconnect()
            print("✓ 已断开连接")
    except Exception as e:
        print(f"⚠ 断开时出错: {e}")


async def main():
    """主函数"""
    client = None
    try:
        client, tx_char = await scan_and_connect()

        if client and tx_char:
            await test_name_change(client, tx_char)
        else:
            print("\n测试取消：无法连接到设备")

    except KeyboardInterrupt:
        print("\n\n用户中断")
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        traceback.print_exc()
    finally:
        if client and client.is_connected:
            try:
                await client.disconnect()
            except Exception:
                pass

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
