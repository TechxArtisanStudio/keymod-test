"""CH9329 兼容协议编解码"""
from dataclasses import dataclass
from typing import Optional
from .models import CommandMeta


@dataclass
class CH9329Frame:
    """CH9329 协议帧"""
    addr: int
    cmd: int
    payload: bytes = b""

    HEADER = b'\x57\xAB'

    @property
    def checksum(self) -> int:
        """8-bit 加和校验"""
        total = 0x57 + 0xAB + self.addr + self.cmd + len(self.payload)
        return (total + sum(self.payload)) & 0xFF

    def to_bytes(self) -> bytes:
        """序列化为字节流"""
        frame = self.HEADER + bytes([self.addr, self.cmd, len(self.payload)]) + self.payload
        return frame + bytes([self.checksum])

    @classmethod
    def from_bytes(cls, data: bytes) -> "CH9329Frame":
        """从字节流反序列化"""
        if len(data) < 6:
            raise ValueError(f"Frame too short: {len(data)} bytes")
        if data[:2] != cls.HEADER:
            raise ValueError(f"Invalid header: {data[:2].hex()}")
        addr = data[2]
        cmd = data[3]
        plen = data[4]
        if len(data) != 5 + plen + 1:
            raise ValueError(f"Length mismatch: expected {5 + plen + 1}, got {len(data)}")
        payload = data[5:5 + plen]
        expected_cs = sum(data[:-1]) & 0xFF
        if data[-1] != expected_cs:
            raise ValueError(f"Checksum mismatch: expected {expected_cs:02X}, got {data[-1]:02X}")
        return cls(addr, cmd, payload)

    def is_response(self) -> bool:
        """判断是否为响应帧"""
        return bool(self.cmd & 0x80)

    def is_error(self) -> bool:
        """判断是否为错误响应"""
        return bool(self.cmd & 0xC0) and not (self.cmd & 0x80)

    def status_code(self) -> Optional[int]:
        """提取状态码（响应帧的第一个 payload 字节）"""
        if self.is_response() and len(self.payload) > 0:
            return self.payload[0]
        return None


# ──────────────────────────────────────────────
# 命令元数据（供 UI 自动生成面板）
# ──────────────────────────────────────────────

COMMAND_META: dict[int, CommandMeta] = {
    0x01: CommandMeta(
        cmd=0x01,
        name="Get Info",
        payload_desc="无",
        resp_len=8,
        tooltip_rich="""
        <b>0x01 Get Info</b><br>
        读取设备信息（8 字节响应）<br>
        <table>
        <tr><td>Byte 0</td><td>硬件类型：0x01=KVM-GO, 0x02=MiniKVM, 0x03=KeyMod</td></tr>
        <tr><td>Byte 1</td><td>USB 枚举状态：0x01=已连接, 0x00=未连接</td></tr>
        <tr><td>Byte 2</td><td>键盘 LED 位图（CapsLock/NumLock/ScrollLock）</td></tr>
        <tr><td>Byte 3</td><td>固件版本号</td></tr>
        <tr><td>Byte 4-7</td><td>保留</td></tr>
        </table>
        """,
        example_request=bytes.fromhex("57AB00010003"),
        example_response=bytes.fromhex("57AB008108030100050000000094"),
    ),
    0x02: CommandMeta(
        cmd=0x02,
        name="Keyboard",
        payload_desc="8 字节：[modifier][reserved][key1][key2][key3][key4][key5][key6]",
        resp_len=1,
        tooltip_rich="""
        <b>0x02 Keyboard Report</b><br>
        标准键盘 HID 报文（8 字节）<br>
        <table>
        <tr><td>data[0]</td><td>修饰键位图（Ctrl/Shift/Alt/GUI）</td></tr>
        <tr><td>data[1]</td><td>保留（通常 0x00）</td></tr>
        <tr><td>data[2-7]</td><td>最多 6 个键码（0xE0-0xE7 自动折叠到修饰键）</td></tr>
        </table>
        <b>注意</b>：需发送全零报文释放按键
        """,
        example_request=bytes.fromhex("57AB00020800000000000000000C"),
        example_response=bytes.fromhex("57AB0082010085"),
    ),
    0x03: CommandMeta(
        cmd=0x03,
        name="Media/ACPI",
        payload_desc="2 或 4 字节：ACPI=[0x01, code] | Media=[0x02, bitmap(3B)]",
        resp_len=1,
        tooltip_rich="""
        <b>0x03 Media / ACPI Report</b><br>
        媒体键 / ACPI 电源键<br>
        <table>
        <tr><td>ACPI</td><td>data[0]=0x01, data[1]=acpi_code</td></tr>
        <tr><td>Media</td><td>data[0]=0x02, data[1-3]=24-bit bitmap</td></tr>
        </table>
        """,
    ),
    0x04: CommandMeta(
        cmd=0x04,
        name="Abs Mouse",
        payload_desc="≥7 字节：[reserved][buttons][x_lo][x_hi][y_lo][y_hi][wheel]",
        resp_len=1,
        tooltip_rich="""
        <b>0x04 Absolute Mouse</b><br>
        绝对坐标鼠标 / 手写笔<br>
        <table>
        <tr><td>buttons</td><td>位图：bit0=左, bit1=右, bit2=中</td></tr>
        <tr><td>x/y</td><td>16-bit LE 坐标（自动映射到 HID 范围）</td></tr>
        <tr><td>wheel</td><td>滚轮值（有符号）</td></tr>
        </table>
        """,
    ),
    0x05: CommandMeta(
        cmd=0x05,
        name="Rel Mouse",
        payload_desc="≥5 字节：[reserved][buttons][dx][dy][wheel]",
        resp_len=1,
        tooltip_rich="""
        <b>0x05 Relative Mouse</b><br>
        相对坐标鼠标<br>
        <table>
        <tr><td>buttons</td><td>位图：bit0=左, bit1=右, bit2=中</td></tr>
        <tr><td>dx/dy</td><td>相对位移（有符号）</td></tr>
        <tr><td>wheel</td><td>滚轮值（有符号）</td></tr>
        </table>
        """,
    ),
    0x08: CommandMeta(
        cmd=0x08,
        name="Get Param",
        payload_desc="无",
        resp_len=44,
        tooltip_rich="""
        <b>0x08 Get Parameter Configuration</b><br>
        CH9329 兼容配置块（44 字节）<br>
        仅用于兼容旧版软件，固件不动态解析
        """,
    ),
    0x17: CommandMeta(
        cmd=0x17,
        name="SD Switch",
        payload_desc="板级特定",
        resp_len=None,
        tooltip_rich="""
        <b>0x17 SD Switch</b><br>
        Openterface 扩展：SD 卡切换逻辑
        """,
    ),
    0x18: CommandMeta(
        cmd=0x18,
        name="Temperature",
        payload_desc="板级特定",
        resp_len=None,
        tooltip_rich="""
        <b>0x18 Temperature</b><br>
        Openterface 扩展：DS18B20 温度传感器
        """,
    ),
    0x22: CommandMeta(
        cmd=0x22,
        name="BLE Security",
        payload_desc="1 字节子命令：0x01=开配对窗口, 0x02=擦除绑定, 0x03=查询绑定数",
        resp_len=None,
        tooltip_rich="""
        <b>0x22 BLE Security</b><br>
        Openterface 扩展：BLE 配对/绑定管理<br>
        <table>
        <tr><td>0x01</td><td>开启配对窗口（返回剩余秒数 + passkey）</td></tr>
        <tr><td>0x02</td><td>擦除所有绑定（仅 USB 侧允许）</td></tr>
        <tr><td>0x03</td><td>查询绑定数量</td></tr>
        </table>
        """,
    ),
    0x23: CommandMeta(
        cmd=0x23,
        name="BLE Set Name",
        payload_desc="1-20 字节 ASCII 名称",
        resp_len=1,
        tooltip_rich="""
        <b>0x23 BLE Set Name</b><br>
        Openterface 扩展：设置 BLE 设备名<br>
        <b>注意</b>：成功后设备自动重启！<br>
        <table>
        <tr><td>长度</td><td>1-20 字符（超长截断）</td></tr>
        <tr><td>持久化</td><td>写入 Flash，断电不丢失</td></tr>
        </table>
        """,
    ),
    0x26: CommandMeta(
        cmd=0x26,
        name="Set ECM IP",
        payload_desc="子命令+数据：0x00=全部, 0x01=Host侧, 0x02=Target侧, 0x03=重置默认",
        resp_len=1,
        tooltip_rich="""
        <b>0x26 Set ECM IP Configuration</b><br>
        Openterface 扩展：配置 ECM 网络 IP<br>
        立即生效，无需重启<br>
        <table>
        <tr><td>默认 Host IP</td><td>192.168.20.1</td></tr>
        <tr><td>默认 Dev IP</td><td>192.168.20.3</td></tr>
        <tr><td>默认 Subnet</td><td>255.255.255.0</td></tr>
        </table>
        """,
    ),
    0x27: CommandMeta(
        cmd=0x27,
        name="Get ECM IP",
        payload_desc="无",
        resp_len=21,
        tooltip_rich="""
        <b>0x27 Get ECM IP Configuration</b><br>
        Openterface 扩展：读取 ECM 网络 IP 配置（21 字节）<br>
        从 RAM 缓存读取，不访问 Flash
        """,
    ),
    0x30: CommandMeta(
        cmd=0x30,
        name="USB Work Mode",
        payload_desc="子命令：无=读状态, 0x01=写模式, 0x02=清除, 0x03=重启",
        resp_len=12,
        tooltip_rich="""
        <b>0x30 USB Work Mode</b><br>
        Openterface 扩展：USB 工作模式选择<br>
        <table>
        <tr><td>Mode 1</td><td>HID + Host CDC ACM</td></tr>
        <tr><td>Mode 2</td><td>HID + UAC Bridge + Host CDC ACM</td></tr>
        <tr><td>Mode 3</td><td>HID + Target CDC ACM + Host CDC ACM</td></tr>
        <tr><td>Mode 4</td><td>HID + Target CDC ECM + Host CDC ECM</td></tr>
        </table>
        """,
    ),
    0x31: CommandMeta(
        cmd=0x31,
        name="System Reset",
        payload_desc="无=正常复位, 0x00=重置 BLE 名后复位",
        resp_len=1,
        tooltip_rich="""
        <b>0x31 System Reset</b><br>
        Openterface 扩展：系统复位<br>
        <b>注意</b>：设备立即重启，BLE 连接将断开！<br>
        <table>
        <tr><td>无 payload</td><td>正常复位</td></tr>
        <tr><td>0x00</td><td>重置 BLE 名为出厂默认后复位</td></tr>
        </table>
        """,
    ),
}
