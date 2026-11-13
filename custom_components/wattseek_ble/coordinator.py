"""DataUpdateCoordinator for WattSeek BLE."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL, DOMAIN
from .device import WattSeekBLEDevice, WattSeekBLEError
from .registers import READ_BLOCKS

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

    async def _async_update_data(self) -> dict[int, int]:
        # Refresh the BLEDevice handle from HA's bluetooth manager (it may have
        # been re-advertised via a different adapter/proxy since last time).
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.device.address, connectable=True
        )
        if ble_device:
            self.device.set_ble_device(ble_device)

        words: dict[int, int] = {}
        try:
            await self.device.connect()
            for start, count in READ_BLOCKS:
                regs = await self.device.async_read_registers(start, count)
                for i, value in enumerate(regs):
                    words[start + i] = value
        except WattSeekBLEError as err:
            raise UpdateFailed(str(err)) from err
        return words
