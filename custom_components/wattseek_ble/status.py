"""Decoding of the inverter state machine, fault and alarm registers.

Source: JSD Solar Modbus protocol (registers 0x0042, 0x0046-0x0049).
"""
from __future__ import annotations

STATE_ADDR = 0x0042
FAULT1_ADDR, FAULT2_ADDR = 0x0046, 0x0047
ALARM1_ADDR, ALARM2_ADDR = 0x0048, 0x0049

STATES: dict[int, str] = {
    0: "Power on",
    1: "Initialization",
    2: "Standby",
    3: "Grid (AC) mode",
    4: "Solar mode",
    5: "Battery mode",
    6: "Generator mode",
    7: "Fault",
    8: "Power off",
    9: "Factory mode",
    10: "Firmware upgrade",
}

FAULT1 = (
    "Mains soft start failure", "Bus overvoltage", "Bus undervoltage",
    "Battery overcurrent", "Overtemperature", "Battery overvoltage",
    "Battery soft start failure", "Bus short circuit", "Inverter soft start failure",
    "Inverter overvoltage", "Inverter undervoltage", "Inverter short circuit",
    "Negative power protection", "Overload failure",
    "Model/hardware incompatibility", "No bootloader",
)
FAULT2 = (
    "Programming in progress", "PV reverse connection", "Parallel serial number abnormal",
    "Parallel communication abnormal", "Parallel battery voltage difference",
    "Parallel mains voltage difference", "Parallel mains frequency difference",
    "Parallel phase loss", "Parallel output sync lost", "BMS fault", "MCU fault",
    None, "Inverter load abnormal",
)
ALARM1 = (
    "Battery not connected", "Battery undervoltage", "Battery low voltage",
    "Charger short circuit", None, "Battery overcharge", "BMS lost",
    "Overtemperature", "Fan stalled", "EEPROM fault", "Overload",
    "Generator waveform abnormal", "Weak PV energy", "Parallel sync signal lost",
    "Parallel phase loss", "Parallel version incompatible",
)
ALARM2 = (
    "Parallel communication error", "Parallel voltage/frequency difference",
    "Low SOC shutdown", "Low SOC alarm", "Parallel battery difference",
    "Battery short circuit", "Battery below starting voltage", "Generator overload",
    "Generator undervoltage", "Generator overvoltage", "CT reverse connection",
    "Unstable mains power",
)


def active_bits(words: dict[int, int], spec: tuple[tuple[int, tuple], ...]) -> list[str] | None:
    """Return the names of set bits across the given (address, names) pairs."""
    out: list[str] = []
    for addr, names in spec:
        raw = words.get(addr)
        if raw is None:
            return None
        for bit in range(16):
            if raw & (1 << bit):
                name = names[bit] if bit < len(names) and names[bit] else f"bit {bit} @ {addr:#06x}"
                out.append(name)
    return out


FAULT_SPEC = ((FAULT1_ADDR, FAULT1), (FAULT2_ADDR, FAULT2))
ALARM_SPEC = ((ALARM1_ADDR, ALARM1), (ALARM2_ADDR, ALARM2))
