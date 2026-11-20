"""DataUpdateCoordinator for WattSeek BLE."""
from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_ALLOW_WRITES, CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL, DOMAIN
from .device import WattSeekBLEDevice, WattSeekBLEError
from .registers import READ_BLOCKS
from .settings import SETTINGS_BLOCKS

_LOGGER = logging.getLogger(__name__)

# Each logger round trip costs ~0.5 s regardless of size, so nearby blocks are
# read as one Modbus request. Not every span works: the inverter rejects a read
# that crosses unmapped addresses, so these are the spans verified on hardware.
# Live data, read every poll:
FAST_SPANS: tuple[tuple[int, int], ...] = (
    (0x0042, 0x5C),  # state/fault/alarm + grid/load + battery/BMS + PV1/PV2
    (0x0218, 0x10),  # output
    (0x0260, 0x0F),  # PV totals
)
# Slowly changing data (counters, temperatures, settings), read every
# SLOW_EVERY seconds and right after a settings write. Blocks not covered by
# any span are read on their own in the slow pass.
SLOW_SPANS: tuple[tuple[int, int], ...] = (
    (0x4100, 0x44),  # all settings blocks
)
SLOW_EVERY = 60.0
# A merged span that fails this many times in a row while its own blocks read
# fine is abandoned until the integration reloads.
SPAN_GIVE_UP = 3

Plan = list[tuple[tuple[int, int], list[tuple[int, int]]]]


def build_plans(blocks: tuple[tuple[int, int], ...]) -> tuple[Plan, Plan]:
    """Assign every register block to a fast or slow (span, members) read."""
    def inside(span, block):
        return span[0] <= block[0] and block[0] + block[1] <= span[0] + span[1]

    remaining = sorted(set(blocks))
    plans: list[Plan] = []
    for spans in (FAST_SPANS, SLOW_SPANS):
        plan: Plan = []
        for span in spans:
            members = [b for b in remaining if inside(span, b)]
            if members:
                plan.append((span, members))
                remaining = [b for b in remaining if b not in members]
        plans.append(plan)
    fast, slow = plans
    slow += [(b, [b]) for b in remaining]
    return fast, slow


class WattSeekCoordinator(DataUpdateCoordinator[dict[int, int]]):
    """Polls the inverter registers over BLE on a configurable interval."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, device: WattSeekBLEDevice) -> None:
        interval = entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )
        self.entry = entry
        self.device = device
        self._fast_plan, self._slow_plan = build_plans((*READ_BLOCKS, *SETTINGS_BLOCKS))
        self._span_failures: dict[tuple[int, int], int] = {}
        self._last_slow = 0.0
        self._force_slow = True
        # Link-quality diagnostics, refreshed every poll (see sensor.py).
        self.timing: dict[str, Any] = {
            "response_time": None,      # mean request->response RTT this poll, ms
            "response_time_max": None,  # slowest request this poll, ms
            "poll_duration": None,      # whole poll incl. (re)connect, ms
            "connect_time": None,       # last connect + handshake, ms
            "write_response_time": None,  # last settings write RTT, ms
            "last_response": None,      # when the inverter last answered
        }

    @property
    def request_errors(self) -> int:
        return self.device.request_errors

    def _record_timing(self, started: float) -> None:
        rtts = self.device.rtts
        if rtts:
            self.timing["response_time"] = round(sum(rtts) / len(rtts) * 1000)
            self.timing["response_time_max"] = round(max(rtts) * 1000)
            self.timing["last_response"] = dt_util.utcnow()
        self.timing["poll_duration"] = round((time.monotonic() - started) * 1000)

    def _refresh_ble_device(self) -> None:
        # Refresh the BLEDevice handle from HA's bluetooth manager (it may have
        # been re-advertised via a different adapter/proxy since last time).
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.device.address, connectable=True
        )
        if ble_device:
            self.device.set_ble_device(ble_device)

    async def _async_update_data(self) -> dict[int, int]:
        self._refresh_ble_device()
        words: dict[int, int] = {}
        started = time.monotonic()
        self.device.reset_timing()
        try:
            if await self.device.connect():
                self.timing["connect_time"] = round((time.monotonic() - started) * 1000)
                # Keep the handshake out of the per-request response times.
                self.device.reset_timing()
        except WattSeekBLEError as err:
            await self.device.disconnect()
            self._record_timing(started)
            raise UpdateFailed(str(err)) from err

        slow = self._force_slow or time.monotonic() - self._last_slow >= SLOW_EVERY
        plan = self._fast_plan + (self._slow_plan if slow else [])
        failures = 0
        for span, members in plan:
            if len(members) > 1 and self._span_failures.get(span, 0) < SPAN_GIVE_UP:
                regs = await self._read(*span)
                if regs is not None:
                    self._span_failures[span] = 0
                    words.update({span[0] + i: v for i, v in enumerate(regs)})
                    continue
            ok = 0
            for start, count in members:
                regs = await self._read(start, count)
                if regs is None:
                    failures += 1
                    continue
                ok += 1
                words.update({start + i: v for i, v in enumerate(regs)})
            if len(members) > 1 and ok == len(members):
                # The merged read failed but the pieces work: the inverter
                # probably rejects this span.
                n = self._span_failures.get(span, 0) + 1
                self._span_failures[span] = n
                if n == SPAN_GIVE_UP:
                    _LOGGER.info(
                        "merged read %#06x+%d keeps failing; reading its %d blocks separately",
                        span[0], span[1], len(members),
                    )
        if slow and words:
            self._last_slow = time.monotonic()
            self._force_slow = False

        self._record_timing(started)
        if not words:
            # Drop a possibly wedged link so the logger starts advertising again.
            await self.device.disconnect()
            raise UpdateFailed("no register blocks could be read")
        if failures:
            _LOGGER.debug("%d register block(s) failed this cycle", failures)
        # Keep the slow registers from earlier polls; fresh reads win.
        return {**(self.data or {}), **words}

    async def _read(self, start: int, count: int) -> list[int] | None:
        try:
            regs = await self.device.async_read_registers(start, count)
        except WattSeekBLEError as err:
            _LOGGER.debug("read %#06x+%d failed: %s", start, count, err)
            return None
        if len(regs) != count:
            _LOGGER.debug("read %#06x+%d returned %d registers", start, count, len(regs))
            return None
        return regs

    async def async_write_setting(self, addr: int, value: int) -> None:
        """Write one settings register, then refresh."""
        if not self.entry.options.get(CONF_ALLOW_WRITES, False):
            raise HomeAssistantError(
                "Changing inverter settings is disabled. Enable "
                "'Allow changing inverter settings' in the WattSeek BLE options."
            )
        self._refresh_ble_device()
        try:
            await self.device.connect()
            await self.device.async_write_register(addr, value)
        except WattSeekBLEError as err:
            raise HomeAssistantError(f"Failed to write {addr:#06x}: {err}") from err
        if self.device.last_rtt is not None:
            self.timing["write_response_time"] = round(self.device.last_rtt * 1000)
            self.timing["last_response"] = dt_util.utcnow()
        self._force_slow = True  # re-read settings on the refresh below
        if self.data is not None:
            self.data[addr] = value & 0xFFFF
            self.async_update_listeners()
        await self.async_request_refresh()
