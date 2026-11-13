"""Writable inverter settings (JSD Solar 3KU, menu registers at 0x4100+).

Addresses, option maps and ranges mirror the validated ESPHome JSDSolar
config. Written over the WattSeek BLE TRANSPARENT tunnel (single-register
Modbus write, validated against app captures). Dangerous commands (factory
reset, power on/off) are intentionally omitted.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SelectSetting:
    key: str
    name: str
    address: int
    options: dict[int, str]  # register value -> label

    def label_for(self, raw: int | None) -> str | None:
        return self.options.get(raw) if raw is not None else None

    def value_for(self, label: str) -> int | None:
        for v, lbl in self.options.items():
            if lbl == label:
                return v
        return None


@dataclass(frozen=True)
class NumberSetting:
    key: str
    name: str
    address: int
    min_value: float
    max_value: float
    step: float = 1.0
    scale: float = 1.0  # engineering = raw * scale
    unit: str | None = None


_AC_CURRENT = {2: "2A"} | {a: f"{a}A" for a in range(10, 130, 10)}

SELECTS: tuple[SelectSetting, ...] = (
    SelectSetting("output_voltage", "Output Voltage", 0x4100, {1: "220V", 2: "230V", 3: "240V"}),
    SelectSetting("output_frequency", "Output Frequency", 0x4101, {0: "50Hz", 1: "60Hz"}),
    SelectSetting(
        "output_priority", "Output Priority", 0x4102,
        {0: "GPB (Grid-PV-Battery)", 1: "PGB (PV-Grid-Battery)", 2: "PBG (PV-Battery-Grid)", 3: "MKS Mode"},
    ),
    SelectSetting("operating_mode", "Operating Mode", 0x4103, {0: "APP", 1: "UPS", 2: "GEN"}),
    SelectSetting(
        "charging_priority", "Charging Priority", 0x4104,
        {0: "PNG (PV & Grid)", 1: "OPV (Only PV)", 2: "PVF (PV First)"},
    ),
    SelectSetting("ac_charging_current", "AC Charging Current", 0x4105, _AC_CURRENT),
    SelectSetting(
        "battery_type", "Battery Type", 0x4107,
        {0: "AGM", 1: "Flooded", 2: "Lithium", 3: "LiFePO4", 4: "User-Defined"},
    ),
)

NUMBERS: tuple[NumberSetting, ...] = (
    NumberSetting("battery_charge_voltage", "Battery Charge Voltage", 0x4118, 44.0, 60.0, 0.1, 0.1, "V"),
    NumberSetting("grid_low_voltage", "Grid Low Voltage", 0x410E, 90.0, 280.0, 1.0, 1.0, "V"),
    NumberSetting("grid_high_voltage", "Grid High Voltage", 0x410F, 90.0, 280.0, 1.0, 1.0, "V"),
    NumberSetting("max_charge_power", "Max Charge Power", 0x412F, 0.0, 12.0, 0.5, 0.1, "kW"),
)

# Register blocks that hold the settings above (read so current values show).
SETTINGS_BLOCKS: tuple[tuple[int, int], ...] = (
    (0x4100, 0x10),  # 0x4100 - 0x410F
    (0x4110, 0x10),  # 0x4110 - 0x411F
    (0x4120, 0x10),  # 0x4120 - 0x412F
    (0x4142, 0x02),  # 0x4142 - 0x4143
)
