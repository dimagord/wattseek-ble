"""Inverter Modbus register map (JSD Solar 3KU family, protocol V1.20).

Addresses, scales and signedness are taken from the published register map
used by the ESPHome JSDSolar project; they are read here over the WattSeek
BLE TRANSPARENT tunnel instead of a wired RS-232/485 link.
"""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)


@dataclass(frozen=True)
class Reg:
    key: str
    name: str
    address: int
    scale: float = 1.0
    signed: bool = False
    unit: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = SensorStateClass.MEASUREMENT


_P = SensorDeviceClass.POWER
_V = SensorDeviceClass.VOLTAGE
_A = SensorDeviceClass.CURRENT
_F = SensorDeviceClass.FREQUENCY
_T = SensorDeviceClass.TEMPERATURE
_B = SensorDeviceClass.BATTERY

REGISTERS: tuple[Reg, ...] = (
    # Grid
    Reg("grid_voltage", "Grid Voltage", 0x0050, 0.1, False, UnitOfElectricPotential.VOLT, _V),
    Reg("grid_current", "Grid Current", 0x0051, 0.01, False, UnitOfElectricCurrent.AMPERE, _A),
    Reg("grid_frequency", "Grid Frequency", 0x0052, 0.01, False, UnitOfFrequency.HERTZ, _F),
    Reg("grid_power", "Grid Power", 0x0053, 1, True, UnitOfPower.WATT, _P),
    # Load / output
    Reg("load_voltage", "Load Voltage", 0x0058, 0.1, False, UnitOfElectricPotential.VOLT, _V),
    Reg("load_current", "Load Current", 0x0059, 0.01, False, UnitOfElectricCurrent.AMPERE, _A),
    Reg("load_frequency", "Load Frequency", 0x005A, 0.01, False, UnitOfFrequency.HERTZ, _F),
    Reg("load_power", "Load Active Power", 0x005B, 1, True, UnitOfPower.WATT, _P),
    Reg("load_percentage", "Load Percentage", 0x005D, 0.1, False, PERCENTAGE, None),
    # Battery
    Reg("battery_voltage", "Battery Voltage", 0x0080, 0.1, False, UnitOfElectricPotential.VOLT, _V),
    Reg("battery_current", "Battery Current", 0x0081, 0.1, True, UnitOfElectricCurrent.AMPERE, _A),
    Reg("battery_soc", "Battery SOC", 0x0084, 1, False, PERCENTAGE, _B),
    Reg("battery_power", "Battery Power", 0x0085, 1, True, UnitOfPower.WATT, _P),
    # BMS
    Reg("bms_voltage", "BMS Voltage", 0x0088, 0.1, False, UnitOfElectricPotential.VOLT, _V),
    Reg("bms_current", "BMS Current", 0x0089, 0.1, True, UnitOfElectricCurrent.AMPERE, _A),
    Reg("bms_soc", "BMS SOC", 0x008A, 1, False, PERCENTAGE, _B),
    Reg("bms_temperature", "BMS Temperature", 0x008B, 1, True, UnitOfTemperature.CELSIUS, _T),
    # PV
    Reg("pv1_voltage", "PV1 Voltage", 0x0096, 0.1, False, UnitOfElectricPotential.VOLT, _V),
    Reg("pv1_current", "PV1 Current", 0x0097, 0.01, False, UnitOfElectricCurrent.AMPERE, _A),
    Reg("pv1_power", "PV1 Power", 0x0098, 1, True, UnitOfPower.WATT, _P),
    Reg("pv2_voltage", "PV2 Voltage", 0x0099, 0.1, False, UnitOfElectricPotential.VOLT, _V),
    Reg("pv2_current", "PV2 Current", 0x009A, 0.01, False, UnitOfElectricCurrent.AMPERE, _A),
    Reg("pv2_power", "PV2 Power", 0x009B, 1, True, UnitOfPower.WATT, _P),
    # Temperatures
    Reg("pv_temperature", "PV Temperature", 0x0330, 0.1, True, UnitOfTemperature.CELSIUS, _T),
    Reg("inverter_temperature", "Inverter Temperature", 0x0331, 0.1, True, UnitOfTemperature.CELSIUS, _T),
    Reg("charger_temperature", "Charger Temperature", 0x0332, 0.1, True, UnitOfTemperature.CELSIUS, _T),
    Reg("ambient_temperature", "Ambient Temperature", 0x0334, 0.1, True, UnitOfTemperature.CELSIUS, _T),
)

# Contiguous blocks to read (start, count). The logger accepts up to ~16
# registers per TRANSPARENT read, so larger spans are split.
READ_BLOCKS: tuple[tuple[int, int], ...] = (
    (0x0050, 0x0E),  # 0x50..0x5D  grid + load
    (0x0080, 0x0C),  # 0x80..0x8B  battery + bms
    (0x0096, 0x06),  # 0x96..0x9B  pv
    (0x0330, 0x05),  # 0x330..0x334 temperatures
)


# Value the inverter returns for a register it has no data for (e.g. BMS
# fields when no smart battery is wired to the BMS port).
SENTINELS = (0x7FFF, 0xFFFF)


def decode(reg: Reg, words: dict[int, int]) -> float | None:
    """Decode one register's engineering value from a {address: word} map."""
    raw = words.get(reg.address)
    if raw is None or raw in SENTINELS:
        return None
    if reg.signed and raw >= 0x8000:
        raw -= 0x10000
    value = raw * reg.scale
    return round(value, 2)
