#!/usr/bin/env python3
"""测试修改ECM IP到20网段并检查连通性"""
import asyncio
import subprocess
import sys
from pathlib import Path

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from bleak import BleakScanner, BleakClient
from protocol.ch9329 import CH9329Frame


async def main():
    print("=" * 60)
    print("BLE ECM IP 配置测试")
    print("=" * 60)

    # 扫描设备
    print("\n[1] 扫描BLE设备...")
    devices = await BleakScanner.discover(timeout=5.0)

    print(f"\n扫描到 {len(devices)} 个BLE设备:")
    for i, d in enumerate(devices[:10]):
        print(f"  {i}: {d.name or 'Unknown'} ({d.address})")

    kvm_devices = [d for d in devices if d.name and ("KVM" in d.name or "Openterface" in d.name or "KeyMod" in d.name)]

    if not kvm_devices:
        print("❌ 未找到KVM设备")
        return

    print(f"\n找到 {len(kvm_devices)} 个KVM设备:")
    for i, d in enumerate(kvm_devices):
        print(f"  {i}: {d.name} ({d.address})")

    # 连接第一个设备
    target = kvm_devices[0]
    print(f"\n[2] 连接到 {target.name}...")

    response_queue = asyncio.Queue()

    def notification_handler(sender, data):
        """处理BLE通知数据"""
        try:
            raw = bytes(data)
            print(f"[DEBUG] 收到原始数据: {raw.hex()}")
            frame = CH9329Frame.from_bytes(raw)
            print(f"[DEBUG] 解析成功: cmd=0x{frame.cmd:02X}, payload_len={len(frame.payload)}")
            response_queue.put_nowait(frame)
        except Exception as e:
            print(f"[DEBUG] 解析响应失败: {e}")

    async with BleakClient(target.address) as client:
        print("✅ 已连接")

        # 发现服务
        services = client.services

        print("\n可用服务:")
        for service in services:
            print(f"  {service.uuid}")
            for char in service.characteristics:
                print(f"    {char.uuid} ({', '.join(char.properties)})")

        uart_service = None

        # 查找UART服务
        for svc_uuid in ["6e400001-b5a3-f393-e0a9-e50e24dcca9e", "0000ffe0-0000-1000-8000-00805f9b34fb", "0000fff0-0000-1000-8000-00805f9b34fb"]:
            service = services.get_service(svc_uuid)
            if service:
                uart_service = service
                break

        if not uart_service:
            print("❌ 未找到UART服务")
            return

        # 查找TX和RX特征
        tx_char = None
        rx_char = None

        for tx_uuid in ["6e400002-b5a3-f393-e0a9-e50e24dcca9e", "0000ffe1-0000-1000-8000-00805f9b34fb", "0000fff2-0000-1000-8000-00805f9b34fb"]:
            tx_char = uart_service.get_characteristic(tx_uuid)
            if tx_char:
                break

        for rx_uuid in ["6e400003-b5a3-f393-e0a9-e50e24dcca9e", "0000ffe1-0000-1000-8000-00805f9b34fb", "0000fff1-0000-1000-8000-00805f9b34fb"]:
            rx_char = uart_service.get_characteristic(rx_uuid)
            if rx_char:
                break

        if not tx_char or not rx_char:
            print("❌ 未找到TX/RX特征")
            return

        # 启动通知
        await client.start_notify(rx_char, notification_handler)
        print("✅ 已启用通知")

        try:
            # 获取当前IP配置
            print("\n[3] 获取当前IP配置...")
            get_cmd = CH9329Frame(addr=0x00, cmd=0x27, payload=b"")
            cmd_bytes = get_cmd.to_bytes()
            print(f"[DEBUG] 发送命令: {cmd_bytes.hex()}")
            await client.write_gatt_char(tx_char, cmd_bytes, response=False)
            print("[DEBUG] 命令已发送")

            # 等待响应
            try:
                response = await asyncio.wait_for(response_queue.get(), timeout=3.0)
                print(f"[DEBUG] 收到响应: {response.to_bytes().hex()}")
                if response.is_response():
                    payload = response.payload
                    if len(payload) >= 21:
                        host_ip = f"{payload[1]}.{payload[2]}.{payload[3]}.{payload[4]}"
                        host_subnet = f"{payload[5]}.{payload[6]}.{payload[7]}.{payload[8]}"
                        dev_ip = f"{payload[9]}.{payload[10]}.{payload[11]}.{payload[12]}"
                        dev_subnet = f"{payload[13]}.{payload[14]}.{payload[15]}.{payload[16]}"

                        print(f"当前配置:")
                        print(f"  Host IP:     {host_ip}")
                        print(f"  Host Subnet: {host_subnet}")
                        print(f"  Dev IP:      {dev_ip}")
                        print(f"  Dev Subnet:  {dev_subnet}")
                    else:
                        print(f"❌ 响应长度不正确: {len(payload)} bytes")
                        print(f"   Payload: {payload.hex()}")
                else:
                    print("❌ 未收到响应")
            except asyncio.TimeoutError:
                print("❌ 等待响应超时")

            # 设置IP到20网段
            print("\n[4] 设置IP到20网段 (192.168.20.x)...")

            # 构建payload: 子命令(1字节) + Host IP(4字节) + Host Subnet(4字节) + Dev IP(4字节) + Dev Subnet(4字节)
            # 子命令 0x00 = 设置全部
            new_host_ip = [192, 168, 20, 1]
            new_host_subnet = [255, 255, 255, 0]
            new_dev_ip = [192, 168, 20, 3]
            new_dev_subnet = [255, 255, 255, 0]

            payload = bytes([0x00]) + bytes(new_host_ip) + bytes(new_host_subnet) + bytes(new_dev_ip) + bytes(new_dev_subnet)
            set_cmd = CH9329Frame(addr=0x00, cmd=0x26, payload=payload)
            cmd_bytes = set_cmd.to_bytes()
            print(f"[DEBUG] 发送设置命令: {cmd_bytes.hex()}")

            await client.write_gatt_char(tx_char, cmd_bytes, response=False)
            print("[DEBUG] 设置命令已发送")

            # 等待响应
            try:
                response = await asyncio.wait_for(response_queue.get(), timeout=3.0)
                print(f"[DEBUG] 收到响应: {response.to_bytes().hex()}")
                if response.is_response():
                    status = response.status_code()
                    if status == 0x00:
                        print("✅ IP配置已更新")
                    else:
                        print(f"❌ 设置失败，状态码: 0x{status:02X}" if status else "❌ 设置失败")
                else:
                    print("❌ 未收到响应")
            except asyncio.TimeoutError:
                print("❌ 等待响应超时")

            # 验证新配置
            print("\n[5] 验证新配置...")
            await asyncio.sleep(0.5)

            await client.write_gatt_char(tx_char, get_cmd.to_bytes(), response=False)

            try:
                response = await asyncio.wait_for(response_queue.get(), timeout=3.0)
                if response.is_response():
                    payload = response.payload
                    if len(payload) >= 21:
                        host_ip = f"{payload[1]}.{payload[2]}.{payload[3]}.{payload[4]}"
                        dev_ip = f"{payload[9]}.{payload[10]}.{payload[11]}.{payload[12]}"

                        print(f"新配置:")
                        print(f"  Host IP: {host_ip}")
                        print(f"  Dev IP:  {dev_ip}")

                        if host_ip == "192.168.20.1" and dev_ip == "192.168.20.3":
                            print("✅ IP配置验证成功")
                        else:
                            print("❌ IP配置验证失败")
            except asyncio.TimeoutError:
                print("❌ 等待响应超时")

            # 测试ping
            print("\n[6] 测试ping连通性...")
            print("等待5秒让设备应用新配置...")
            await asyncio.sleep(5)

            # 检查网络接口
            print("\n检查网络接口...")
            result = subprocess.run(["ifconfig"], capture_output=True, text=True)
            if "192.168.20" in result.stdout:
                print("✅ 检测到192.168.20.x网络接口")
                for line in result.stdout.split('\n'):
                    if 'inet 192.168.20' in line:
                        print(f"  {line.strip()}")
            else:
                print("⚠️  未检测到192.168.20.x网络接口")
                print("可能需要手动配置网络接口或等待DHCP")

            # 尝试ping设备
            dev_ip = "192.168.20.3"
            print(f"\n尝试ping {dev_ip}...")
            result = subprocess.run(
                ["ping", "-c", "4", "-W", "2", dev_ip],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                print("✅ Ping成功!")
                print(result.stdout)
            else:
                print("❌ Ping失败")
                print(result.stdout)
                if result.stderr:
                    print(result.stderr)

        finally:
            await client.stop_notify(rx_char)

    print("\n[7] 已断开连接")


if __name__ == "__main__":
    asyncio.run(main())
