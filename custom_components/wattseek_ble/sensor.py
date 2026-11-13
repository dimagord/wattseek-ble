"""Sensor platform for WattSeek BLE."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ADDRESS, DOMAIN
from .coordinator import WattSeekCoordinator
from .registers import REGISTERS, Reg, decode


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: WattSeekCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        WattSeekSensor(coordinator, entry.data[CONF_ADDRESS], reg) for reg in REGISTERS
    )


class WattSeekSensor(CoordinatorEntity[WattSeekCoordinator], SensorEntity):
    """A single inverter register exposed as a sensor."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: WattSeekCoordinator, address: str, reg: Reg) -> None:
        super().__init__(coordinator)
        self._reg = reg
        self._attr_unique_id = f"{address}_{reg.key}"
        self.entity_description = SensorEntityDescription(
            key=reg.key,
            name=reg.name,
            native_unit_of_measurement=reg.unit,
            device_class=reg.device_class,
            state_class=reg.state_class,
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            name=f"WattSeek Inverter ({address})",
            manufacturer="JSD Solar / WattSeek",
            model="Hybrid Inverter (BLE local)",
        )

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        return decode(self._reg, self.coordinator.data)

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.data is not None
            and self.native_value is not None
        )
