"""WattSeek BLE wire protocol.

Reverse-engineered from the WattSeek Android app (com.cvte.wattseek).

Outer frame (what is written to / notified from the GATT characteristic):

    offset  size  field
    0       2     total length of everything after these 2 bytes (big-endian)
    2       2     PROTO_ID, always 0x0006 (big-endian)
    4       2     plaintext length before padding (big-endian)
    6       1     DEVICE_ADDR, always 0x01
    7       1     FunctionCode (0x17 TRANSPARENT, 0x18 SET, 0x19 QUERY, ...)
    8       N     AES-128-CBC(plaintext padded to 16), IV == key
    8+N     2     CRC16/Modbus over bytes [0 .. 8+N)  (little-endian)

Crypto: AES-128-CBC, NoPadding, key == iv == DATA_KEY (16 ASCII bytes).
The plaintext is zero-padded up to the next 16-byte boundary before encryption;
the real length is carried in the header so the receiver can trim it.

The *inner* (decrypted) payload carries an application layer that this module
builds in a best-effort way; raw frames are logged at DEBUG so the app layer
can be refined against a live device.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .const import (
    DATA_KEY,
    DEVICE_ADDR,
    FC_QUERY,
    FC_SET,
    FC_TRANSPARENT,
    PROTO_ID,
)

_LOGGER = logging.getLogger(__name__)


class ProtocolError(Exception):
    """Raised when a frame cannot be parsed."""


# --------------------------------------------------------------------------
# CRC16 / Modbus
# --------------------------------------------------------------------------
def crc16_modbus(data: bytes) -> int:
    """Return the Modbus CRC16 of *data*."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


# --------------------------------------------------------------------------
# AES-128-CBC, NoPadding, iv == key
# --------------------------------------------------------------------------
def _aes(key: bytes):
    return Cipher(algorithms.AES(key), modes.CBC(key[:16]))


def aes_encrypt(plaintext: bytes, key: bytes = DATA_KEY) -> bytes:
    if len(plaintext) % 16:
        plaintext = plaintext + b"\x00" * (16 - len(plaintext) % 16)
    enc = _aes(key).encryptor()
    return enc.update(plaintext) + enc.finalize()


def aes_decrypt(ciphertext: bytes, key: bytes = DATA_KEY) -> bytes:
    dec = _aes(key).decryptor()
    return dec.update(ciphertext) + dec.finalize()


# --------------------------------------------------------------------------
# Outer frame
# --------------------------------------------------------------------------
def build_frame(function_code: int, plaintext: bytes, key: bytes = DATA_KEY) -> bytes:
    """Wrap *plaintext* into a complete, ready-to-write BLE frame."""
    plain_len = len(plaintext)
    cipher = aes_encrypt(plaintext, key)
    header = bytearray()
    header += (PROTO_ID).to_bytes(2, "big")
    header += (plain_len).to_bytes(2, "big")
    header += bytes([DEVICE_ADDR, function_code])
    body = bytes(header) + cipher
    total = len(body) + 2  # + CRC
    frame = bytearray()
    frame += total.to_bytes(2, "big")
    frame += body
    # Outer trailer is CRC16/Modbus over all preceding bytes, big-endian.
    frame += crc16_modbus(frame).to_bytes(2, "big")
    return bytes(frame)


@dataclass
class Frame:
    """A parsed BLE frame."""

    function_code: int
    plain_len: int
    plaintext: bytes  # decrypted, trimmed to plain_len
    raw: bytes

    @property
    def payload(self) -> bytes:
        return self.plaintext[: self.plain_len]


def parse_frame(raw: bytes, key: bytes = DATA_KEY) -> Frame:
    """Parse and decrypt a complete BLE frame received from the logger."""
    if len(raw) < 12:
        raise ProtocolError(f"frame too short: {raw.hex()}")
    total = int.from_bytes(raw[0:2], "big")
    if len(raw) != total + 2:
        _LOGGER.debug("frame length mismatch: hdr=%d len=%d raw=%s", total, len(raw), raw.hex())
    want_crc = int.from_bytes(raw[-2:], "big")
    got_crc = crc16_modbus(raw[:-2])
    if want_crc != got_crc:
        _LOGGER.debug("CRC mismatch want=%04x got=%04x raw=%s", want_crc, got_crc, raw.hex())
    plain_len = int.from_bytes(raw[4:6], "big")
    function_code = raw[7]
    cipher = raw[8:-2]
    if len(cipher) % 16:
        raise ProtocolError(f"cipher not block-aligned ({len(cipher)}): {raw.hex()}")
    plaintext = aes_decrypt(cipher, key)
    return Frame(function_code, plain_len, plaintext, raw)


# --------------------------------------------------------------------------
# Modbus RTU (inverter side, carried over TRANSPARENT)
# --------------------------------------------------------------------------
def modbus_read_holding(slave: int, start: int, count: int) -> bytes:
    """Build a Modbus RTU 'read holding registers' (0x03) request frame."""
    pdu = bytes([slave, 0x03]) + start.to_bytes(2, "big") + count.to_bytes(2, "big")
    return pdu + crc16_modbus(pdu).to_bytes(2, "little")


def modbus_parse_holding(resp: bytes, slave: int) -> list[int]:
    """Parse a Modbus RTU 0x03 response into a list of 16-bit register words."""
    if len(resp) < 5:
        raise ProtocolError(f"modbus response too short: {resp.hex()}")
    if resp[0] != slave:
        raise ProtocolError(f"modbus slave mismatch: {resp.hex()}")
    if resp[1] & 0x80:
        raise ProtocolError(f"modbus exception {resp[2]:#x}: {resp.hex()}")
    if resp[1] != 0x03:
        raise ProtocolError(f"unexpected modbus function {resp[1]:#x}")
    byte_count = resp[2]
    data = resp[3 : 3 + byte_count]
    if len(data) != byte_count:
        raise ProtocolError(f"modbus short payload: {resp.hex()}")
    return [int.from_bytes(data[i : i + 2], "big") for i in range(0, byte_count, 2)]


# --------------------------------------------------------------------------
# Application layer
# --------------------------------------------------------------------------
# Verified against WattSeek app captures.
#
# Request inner payload:
#   [9 bytes device id = "000000000"][0x69 0x55][type][0x6c 0x6c][body]
# Response inner payload:
#   [9 bytes "SXDICA3EC"][0x1a 0x55][type][2 bytes seq][body]
#
# For a register read (type 0x43) the body is:
#   addr(2 BE) + count(2 BE) + CRC16/Modbus(b"\x01\x03" + addr + count) little-endian
# i.e. the app builds the full Modbus RTU request `01 03 addr count crc` but sends
# only `addr count crc`; the logger re-adds the 01 03 (slave + function) and relays
# it to the inverter. The response body is the Modbus reply reduced to
# [byte_count][data].
REQUEST_ID = b"000000000"  # 9 bytes; requests always use this literal id
_SEQ = b"\x6c\x6c"
_RESP_HEADER = 14  # 9 id + 0x1a 0x55 + type + 2 seq


class AppSession:
    """Builds app-layer command frames."""

    def __init__(self) -> None:
        self.device_id = REQUEST_ID

    def transparent_read(self, addr: int, count: int) -> bytes:
        """Build a TRANSPARENT inverter register read (Modbus function 0x03)."""
        a = addr.to_bytes(2, "big")
        c = count.to_bytes(2, "big")
        crc = crc16_modbus(b"\x01\x03" + a + c).to_bytes(2, "little")
        inner = REQUEST_ID + bytes([0x69, 0x55, 0x43]) + _SEQ + a + c + crc
        return build_frame(FC_TRANSPARENT, inner)

    def query(self, param_code: int) -> bytes:
        inner = REQUEST_ID + bytes([0x69, 0x55, 0x48]) + _SEQ + param_code.to_bytes(2, "big") + b"\x00\x00"
        return build_frame(FC_QUERY, inner)

    def set_param(self, param_code: int, value: bytes) -> bytes:
        inner = (
            REQUEST_ID
            + bytes([0x69, 0x55, 0x4A])
            + _SEQ
            + param_code.to_bytes(2, "big")
            + len(value).to_bytes(2, "big")
            + value
        )
        return build_frame(FC_SET, inner)


def parse_transparent_registers(payload: bytes) -> list[int]:
    """Extract 16-bit registers from a TRANSPARENT read response payload."""
    if len(payload) < _RESP_HEADER + 1:
        raise ProtocolError(f"transparent response too short: {payload.hex()}")
    byte_count = payload[_RESP_HEADER]
    data = payload[_RESP_HEADER + 1 : _RESP_HEADER + 1 + byte_count]
    if len(data) != byte_count or byte_count % 2:
        raise ProtocolError(f"bad transparent byte_count {byte_count}: {payload.hex()}")
    return [int.from_bytes(data[i : i + 2], "big") for i in range(0, byte_count, 2)]
