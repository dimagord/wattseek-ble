"""DataUpdateCoordinator for WattSeek BLE."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL, DOMAIN
from .device import WattSeekBLEDevice, WattSeekBLEError
from .registers import READ_BLOCKS
from .settings import SETTINGS_BLOCKS

_LOGGER = logging.getLogger(__name__)


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
        try:
            await self.device.connect()
        except WattSeekBLEError as err:
            await self.device.disconnect()
            raise UpdateFailed(str(err)) from err

        failures = 0
        for start, count in (*READ_BLOCKS, *SETTINGS_BLOCKS):
            try:
                regs = await self.device.async_read_registers(start, count)
            except WattSeekBLEError as err:
                failures += 1
                _LOGGER.debug("block %#06x+%d failed: %s", start, count, err)
                continue
            for i, value in enumerate(regs):
                words[start + i] = value

        if not words:
            # Drop a possibly wedged link so the logger starts advertising again.
            await self.device.disconnect()
            raise UpdateFailed("no register blocks could be read")
        if failures:
            _LOGGER.debug("%d register block(s) failed this cycle", failures)
        return words

    async def async_write_setting(self, addr: int, value: int) -> None:
        """Write one settings register, then refresh."""
        self._refresh_ble_device()
        try:
            await self.device.connect()
            await self.device.async_write_register(addr, value)
        except WattSeekBLEError as err:
            raise HomeAssistantError(f"Failed to write {addr:#06x}: {err}") from err
        if self.data is not None:
            self.data[addr] = value & 0xFFFF
            self.async_update_listeners()
        await self.async_request_refresh()
