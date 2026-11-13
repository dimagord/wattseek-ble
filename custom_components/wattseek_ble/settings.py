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

# Operating-mode register; some ranges depend on it (manual program 04).
OPERATING_MODE_ADDR = 0x4103
MODE_UPS = 1

# Exposed on purpose: only everyday operating choices plus setpoints whose
# ranges are bounded by the inverter manual (J6500HC, LCD programs 03-06,
# 20, 22, 23). Deliberately NOT exposed: output voltage/frequency (01/02,
# risk to connected appliances), battery type (17, changes the whole charge
# profile), grid-tie feed-in (36/37), factory reset (26) and the unverified
# 0x412F "max charge power" register (manual program 07 is a current in A).
SELECTS: tuple[SelectSetting, ...] = (
    SelectSetting(
        "output_priority", "Output Priority", 0x4102,
        {0: "GPB (Grid-PV-Battery)", 1: "PGB (PV-Grid-Battery)", 2: "PBG (PV-Battery-Grid)", 3: "MKS Mode"},
    ),
    SelectSetting("operating_mode", "Operating Mode", OPERATING_MODE_ADDR, {0: "APP", 1: "UPS", 2: "GEN"}),
    SelectSetting(
        "charging_priority", "Charging Priority", 0x4104,
        {0: "PNG (PV & Grid)", 1: "OPV (Only PV)", 2: "PVF (PV First)"},
    ),
    SelectSetting("ac_charging_current", "AC Charging Current", 0x4105, _AC_CURRENT),
)

NUMBERS: tuple[NumberSetting, ...] = (
    # Program 20: manual allows 48-60 V; capped at 58.4 V (16S LiFePO4 max)
    # because there is no BMS link to stop an overcharge.
    NumberSetting("battery_charge_voltage", "Battery Charge Voltage", 0x4118, 48.0, 58.4, 0.1, 0.1, "V"),
    # Program 22: APP/GEN 90-154 V, UPS 170-200 V (see GRID_LOW_UPS_RANGE).
    NumberSetting("grid_low_voltage", "Grid Low Voltage", 0x410E, 90.0, 154.0, 1.0, 1.0, "V"),
    # Program 23: APP/GEN 264-280 V; fixed at 264 V in UPS mode.
    NumberSetting("grid_high_voltage", "Grid High Voltage", 0x410F, 264.0, 280.0, 1.0, 1.0, "V"),
)

# Mode-dependent overrides: key -> (min, max) when operating mode is UPS.
UPS_RANGES: dict[str, tuple[float, float]] = {
    "grid_low_voltage": (170.0, 200.0),
    "grid_high_voltage": (264.0, 264.0),
}

# Register blocks that hold the settings above (read so current values show).
SETTINGS_BLOCKS: tuple[tuple[int, int], ...] = (
    (0x4100, 0x10),  # 0x4100 - 0x410F
    (0x4110, 0x10),  # 0x4110 - 0x411F
    (0x4120, 0x10),  # 0x4120 - 0x412F
    (0x4142, 0x02),  # 0x4142 - 0x4143
)
