"""BLE transport for the WattSeek logger.

Runs on top of Home Assistant's Bluetooth stack, so it works equally with a
local Bluetooth adapter on the HA host and with an ESPHome Bluetooth proxy.
"""
from __future__ import annotations

import asyncio
import logging
import time

from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from .const import CHAR_UUID, HANDSHAKE_KEY, PARAM_BLUETOOTH_KEY
from .protocol import (
    AppSession,
    Frame,
    ProtocolError,
    parse_frame,
    parse_transparent_registers,
)

_LOGGER = logging.getLogger(__name__)

COMMAND_TIMEOUT = 8.0
HANDSHAKE_TIMEOUT = 10.0


class WattSeekBLEError(Exception):
    """Transport-level error."""


class WattSeekBLEDevice:
    """Owns a connection to one WattSeek BLE logger."""

    def __init__(self, ble_device: BLEDevice) -> None:
        self._ble_device = ble_device
        self._client: BleakClientWithServiceCache | None = None
        self._session = AppSession()
        self._lock = asyncio.Lock()
        self._buffer = bytearray()
        self._expected = 0
        self._future: asyncio.Future[Frame] | None = None
        self._connected = False
        # Round-trip time (s) of each successful command since the last
        # reset_timing(): from the GATT write until the matching response frame.
        self.rtts: list[float] = []
        self.last_rtt: float | None = None
        self.request_errors = 0

    def reset_timing(self) -> None:
        self.rtts = []

    @property
    def address(self) -> str:
        return self._ble_device.address

    def set_ble_device(self, ble_device: BLEDevice) -> None:
        """Refresh the BLEDevice (HA re-discovers it periodically)."""
        self._ble_device = ble_device

    # -- connection --------------------------------------------------------
    async def connect(self) -> bool:
        """Connect if needed. Returns True when a new connection was made."""
        if self._connected and self._client and self._client.is_connected:
            return False
        _LOGGER.debug("connecting to %s", self.address)
        client = await establish_connection(
            BleakClientWithServiceCache,
            self._ble_device,
            self._ble_device.name or self.address,
            disconnected_callback=self._on_disconnect,
        )
        self._client = client
        self._buffer.clear()
        self._expected = 0
        await client.start_notify(CHAR_UUID, self._on_notify)
        self._session = AppSession()
        await self._handshake()
        self._connected = True
        _LOGGER.debug("connected and handshaked with %s", self.address)
        return True

    def _on_disconnect(self, _client) -> None:
        _LOGGER.debug("disconnected from %s", self.address)
        self._connected = False
        if self._future and not self._future.done():
            self._future.set_exception(WattSeekBLEError("disconnected"))

    async def disconnect(self) -> None:
        self._connected = False
        if self._client and self._client.is_connected:
            try:
                await self._client.stop_notify(CHAR_UUID)
            except BleakError:
                pass
            await self._client.disconnect()
        self._client = None

    # -- notify reassembly -------------------------------------------------
    def _on_notify(self, _char, data: bytearray) -> None:
        _LOGGER.debug("notify <- %s", data.hex())
        self._buffer += data
        # Drain every complete frame currently in the buffer. The logger pushes
        # unsolicited status beacons (FunctionCode 0x18) continuously, so several
        # frames can pile up between reads.
        while len(self._buffer) >= 2:
            total = int.from_bytes(self._buffer[0:2], "big") + 2
            if len(self._buffer) < total:
                break
            raw = bytes(self._buffer[:total])
            del self._buffer[:total]
            self._deliver(raw)

    def _deliver(self, raw: bytes) -> None:
        try:
            frame = parse_frame(raw)
        except ProtocolError as err:
            _LOGGER.debug("bad frame: %s", err)
            return
        if self._future is None or self._future.done():
            return
        # Only resolve the pending command with a frame that matches the
        # function code we asked for; ignore the beacon spam otherwise.
        if self._expect_fc is not None and frame.function_code != self._expect_fc:
            _LOGGER.debug("ignoring fc=%#x (waiting for %#x)", frame.function_code, self._expect_fc)
            return
        self._future.set_result(frame)

    # -- command/response --------------------------------------------------
    async def _command(
        self,
        frame_bytes: bytes,
        expect_fc: int | None = None,
        timeout: float = COMMAND_TIMEOUT,
    ) -> Frame:
        if not self._client or not self._client.is_connected:
            raise WattSeekBLEError("not connected")
        async with self._lock:
            loop = asyncio.get_running_loop()
            self._future = loop.create_future()
            self._expect_fc = expect_fc
            self._buffer.clear()
            _LOGGER.debug("write -> %s", frame_bytes.hex())
            started = time.monotonic()
            try:
                await self._client.write_gatt_char(CHAR_UUID, frame_bytes, response=True)
                frame = await asyncio.wait_for(self._future, timeout)
            except (BleakError, asyncio.TimeoutError) as err:
                self.request_errors += 1
                raise WattSeekBLEError(f"command failed: {err!r}") from err
            except WattSeekBLEError:
                # Set on the future by _on_disconnect mid-request.
                self.request_errors += 1
                raise
            else:
                rtt = time.monotonic() - started
                self.last_rtt = rtt
                self.rtts.append(rtt)
                _LOGGER.debug("response in %.0f ms", rtt * 1000)
                return frame
            finally:
                self._future = None
                self._expect_fc = None

    async def _handshake(self) -> None:
        frame = self._session.set_param(PARAM_BLUETOOTH_KEY, HANDSHAKE_KEY)
        try:
            await self._command(frame, expect_fc=0x18, timeout=HANDSHAKE_TIMEOUT)
        except WattSeekBLEError as err:
            _LOGGER.warning("handshake did not complete cleanly: %s", err)

    # -- high level --------------------------------------------------------
    async def async_query(self, param_code: int) -> bytes:
        """Return the raw payload of a QUERY response."""
        from .const import FC_QUERY

        frame = await self._command(self._session.query(param_code), expect_fc=FC_QUERY)
        return frame.payload

    async def async_read_registers(self, start: int, count: int) -> list[int]:
        """Read inverter holding registers over the TRANSPARENT tunnel."""
        from .const import FC_TRANSPARENT

        frame = await self._command(
            self._session.transparent_read(start, count), expect_fc=FC_TRANSPARENT
        )
        try:
            return parse_transparent_registers(frame.payload)
        except ProtocolError as err:
            raise WattSeekBLEError(str(err)) from err

    async def async_write_register(self, addr: int, value: int) -> None:
        """Write a single inverter holding register over the TRANSPARENT tunnel."""
        from .const import FC_TRANSPARENT

        await self._command(
            self._session.transparent_write(addr, value), expect_fc=FC_TRANSPARENT
        )
