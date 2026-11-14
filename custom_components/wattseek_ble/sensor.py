"""Sensor platform for WattSeek BLE."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ADDRESS, DOMAIN
from .coordinator import WattSeekCoordinator
from .registers import REGISTERS, Reg, decode
from .status import ALARM_SPEC, FAULT_SPEC, STATE_ADDR, STATE_ICONS, STATES, active_bits, localize


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: WattSeekCoordinator = hass.data[DOMAIN][entry.entry_id]
    address = entry.data[CONF_ADDRESS]
    entities: list[SensorEntity] = [WattSeekSensor(coordinator, address, reg) for reg in REGISTERS]
    entities += [
        WattSeekStatusSensor(coordinator, address),
        WattSeekBitsSensor(coordinator, address, "active_faults", "faults", FAULT_SPEC, "mdi:alert-octagon"),
        WattSeekBitsSensor(coordinator, address, "active_alarms", "alarms", ALARM_SPEC, "mdi:alert"),
    ]
    async_add_entities(entities)


def _device_info(address: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, address)},
        name=f"WattSeek Inverter ({address})",
        manufacturer="JSD Solar / WattSeek",
        model="Hybrid Inverter (BLE local)",
    )


class WattSeekStatusSensor(CoordinatorEntity[WattSeekCoordinator], SensorEntity):
    """Human-readable inverter state machine."""

    _attr_has_entity_name = True
    _attr_translation_key = "status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(STATES.values())

    def __init__(self, coordinator: WattSeekCoordinator, address: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{address}_status"
        self._attr_device_info = _device_info(address)

    @property
    def native_value(self) -> str | None:
        raw = (self.coordinator.data or {}).get(STATE_ADDR)
        return STATES.get(raw) if raw is not None else None

    @property
    def icon(self) -> str:
        return STATE_ICONS.get(self.native_value or "", "mdi:state-machine")


class WattSeekBitsSensor(CoordinatorEntity[WattSeekCoordinator], SensorEntity):
    """Decoded fault/alarm bitfields: 'OK' or a list of active conditions."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, address, key, translation_key, spec, icon) -> None:
        super().__init__(coordinator)
        self._spec = spec
        self._problem_icon = icon
        self._attr_unique_id = f"{address}_{key}"
        self._attr_translation_key = translation_key
        self._attr_device_info = _device_info(address)

    def _active(self) -> list[str] | None:
        active = active_bits(self.coordinator.data or {}, self._spec)
        return None if active is None else localize(active, self.hass.config.language)

    @property
    def native_value(self) -> str | None:
        active = self._active()
        if active is None:
            return None
        if not active:
            return "Немає" if self.hass.config.language.split("-")[0] == "uk" else "None"
        return ", ".join(active)[:255]

    @property
    def icon(self) -> str:
        return self._problem_icon if self._active() else "mdi:check-circle-outline"

    @property
    def extra_state_attributes(self) -> dict:
        active = self._active() or []
        return {"count": len(active), "active": active}


_RAW_CODES = {"inverter_state", "fault_code", "alarm_code"}


class WattSeekSensor(CoordinatorEntity[WattSeekCoordinator], SensorEntity):
    """A single inverter register exposed as a sensor."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: WattSeekCoordinator, address: str, reg: Reg) -> None:
        super().__init__(coordinator)
        self._reg = reg
        self._attr_unique_id = f"{address}_{reg.key}"
        # Derive display precision from the register scale (0.1 -> 1, 0.01 -> 2,
        # 1 -> 0) so values show consistently, e.g. "56.0 V" rather than "56 V".
        if reg.scale >= 1:
            precision = 0
        else:
            precision = len(f"{reg.scale:f}".rstrip("0").split(".")[1])
        self.entity_description = SensorEntityDescription(
            key=reg.key,
            name=reg.name,
            native_unit_of_measurement=reg.unit,
            device_class=reg.device_class,
            state_class=reg.state_class,
            suggested_display_precision=precision,
            entity_category=EntityCategory.DIAGNOSTIC if reg.diagnostic else None,
            # Raw state/fault/alarm codes are superseded by the decoded sensors.
            entity_registry_enabled_default=reg.key not in _RAW_CODES,
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
