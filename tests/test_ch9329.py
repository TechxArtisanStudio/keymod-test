"""CH9329 协议层测试"""
import pytest
from src.protocol.ch9329 import CH9329Frame, COMMAND_META


class TestCH9329Frame:
    """CH9329 帧编解码测试"""

    def test_checksum_calculation(self):
        """测试校验和计算"""
        frame = CH9329Frame(addr=0x00, cmd=0x01, payload=b"")
        # 0x57 + 0xAB + 0x00 + 0x01 + 0x00 = 0x103 → 0x03
        assert frame.checksum == 0x03

    def test_to_bytes_empty_payload(self):
        """测试序列化（无 payload）"""
        frame = CH9329Frame(addr=0x00, cmd=0x01, payload=b"")
        data = frame.to_bytes()
        assert data == bytes.fromhex("57AB00010003")

    def test_to_bytes_with_payload(self):
        """测试序列化（有 payload）"""
        frame = CH9329Frame(addr=0x00, cmd=0x02, payload=bytes(8))
        data = frame.to_bytes()
        # 0x57 + 0xAB + 0x00 + 0x02 + 0x08 + 8*0x00 = 0x112 → 0x12? 实际是 0x0C
        # Sum: 0x57+0xAB+0x00+0x02+0x08+8*0x00 = 0x112 → 0x12? No
        # Let's recalculate: 0x57 + 0xAB + 0x00 + 0x02 + 0x08 = 0x10C? No
        # 0x57=87, 0xAB=171, 0x00=0, 0x02=2, 0x08=8, 8*0=0
        # 87+171+0+2+8 = 268 = 0x10C → 0x0C
        expected = bytes.fromhex("57AB00020800000000000000000C")
        assert data == expected

    def test_from_bytes_empty_payload(self):
        """测试反序列化（无 payload）"""
        data = bytes.fromhex("57AB00010003")
        frame = CH9329Frame.from_bytes(data)
        assert frame.addr == 0x00
        assert frame.cmd == 0x01
        assert frame.payload == b""

    def test_from_bytes_with_payload(self):
        """测试反序列化（有 payload）"""
        data = bytes.fromhex("57AB00020800000000000000000C")
        frame = CH9329Frame.from_bytes(data)
        assert frame.addr == 0x00
        assert frame.cmd == 0x02
        assert len(frame.payload) == 8

    def test_round_trip(self):
        """测试序列化-反序列化往返"""
        original = CH9329Frame(addr=0x00, cmd=0x03, payload=bytes([0x01, 0x02]))
        data = original.to_bytes()
        restored = CH9329Frame.from_bytes(data)
        assert restored.addr == original.addr
        assert restored.cmd == original.cmd
        assert restored.payload == original.payload

    def test_invalid_header(self):
        """测试无效 header"""
        data = bytes.fromhex("57AC00010003")  # 第二个字节错误
        with pytest.raises(ValueError, match="Invalid header"):
            CH9329Frame.from_bytes(data)

    def test_invalid_checksum(self):
        """测试无效校验和"""
        data = bytes.fromhex("57AB00010004")  # 校验和错误
        with pytest.raises(ValueError, match="Checksum mismatch"):
            CH9329Frame.from_bytes(data)

    def test_frame_too_short(self):
        """测试帧太短"""
        data = bytes.fromhex("57AB00")
        with pytest.raises(ValueError, match="Frame too short"):
            CH9329Frame.from_bytes(data)

    def test_is_response(self):
        """测试响应帧判断"""
        req = CH9329Frame(addr=0x00, cmd=0x01)
        resp = CH9329Frame(addr=0x00, cmd=0x81)
        assert not req.is_response()
        assert resp.is_response()

    def test_status_code(self):
        """测试状态码提取"""
        frame = CH9329Frame(addr=0x00, cmd=0x81, payload=bytes([0x00]))
        assert frame.status_code() == 0x00


class TestCommandMeta:
    """命令元数据测试"""

    def test_all_commands_have_meta(self):
        """测试所有命令都有元数据"""
        expected_cmds = [0x01, 0x02, 0x03, 0x04, 0x05, 0x08, 0x17, 0x18, 0x22, 0x23, 0x26, 0x27, 0x30, 0x31]
        for cmd in expected_cmds:
            assert cmd in COMMAND_META, f"命令 0x{cmd:02X} 缺少元数据"

    def test_meta_fields(self):
        """测试元数据字段完整性"""
        for cmd, meta in COMMAND_META.items():
            assert meta.cmd == cmd
            assert meta.name, f"命令 0x{cmd:02X} 缺少名称"
            assert meta.tooltip_rich, f"命令 0x{cmd:02X} 缺少 tooltip"

    def test_example_requests_parseable(self):
        """测试示例请求可解析"""
        for cmd, meta in COMMAND_META.items():
            if meta.example_request:
                frame = CH9329Frame.from_bytes(meta.example_request)
                assert frame.cmd == cmd
