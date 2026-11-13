# WattSeek BLE — Home Assistant integration

Local (cloud-free) monitoring of JSD Solar / WattSeek hybrid inverters over
**Bluetooth Low Energy**, speaking the same BLE protocol the WattSeek phone app
uses in its local mode. No wiring into the inverter, no RS-232/485 adapter, no
cloud polling.

> Status: **early / community**. The BLE transport, AES encryption, framing and
> CRC are fully reproduced and verified against real captures. The inverter
> register read-out over the TRANSPARENT tunnel is implemented from the
> published JSD Solar V1.20 register map and may need one round of tuning
> against your unit — see [Troubleshooting](#troubleshooting).

## How it works

```
Home Assistant  ──BLE──►  WattSeek logger  ──Modbus RTU──►  inverter
   (this integration)      (FF00 service)    (transparent tunnel)
```

- Transport: HA's own Bluetooth stack, so it works with a **local Bluetooth
  adapter** on the HA host **or** an **ESPHome Bluetooth proxy** near the
  inverter — no configuration needed either way.
- Encryption: AES-128-CBC (NoPadding, IV = key), exactly as the app does it.
- Inverter data: standard Modbus `read holding registers` requests are tunnelled
  to the inverter through the logger's `TRANSPARENT` function and decoded with
  the JSD Solar 3KU register map.

## Requirements

- Home Assistant 2024.8 or newer with the **Bluetooth** integration working
  (a local adapter or an ESPHome Bluetooth proxy within range of the inverter).
- The inverter powered on.
- **The WattSeek phone app must not be connected to the logger at the same
  time** — BLE allows only one active connection, so close the app (or turn off
  its Bluetooth) while HA is polling.

## Installation (HACS)

1. HACS → ⋮ → **Custom repositories**.
2. Add `https://github.com/dimagord/wattseek-ble`, category **Integration**.
3. Install **WattSeek BLE**, then restart Home Assistant.
4. The logger should be auto-discovered (**Settings → Devices & Services →
   Discovered**). If not, add it manually via **＋ Add Integration → WattSeek
   BLE**.

### Manual installation

Copy `custom_components/wattseek_ble/` into your HA `config/custom_components/`
folder and restart.

## Options

**Settings → Devices & Services → WattSeek BLE → Configure**:

- **Update interval** — how often HA polls the inverter (5–600 s, default 30 s).

## Troubleshooting

Enable debug logging to capture the raw BLE frames:

```yaml
logger:
  default: warning
  logs:
    custom_components.wattseek_ble: debug
```

If sensors stay unavailable, the most likely cause is the application-layer
framing of the TRANSPARENT request differing slightly on your firmware. The
debug log prints every `write ->` and `notify <-` frame; open an issue with a
short excerpt (the handshake plus one poll cycle) and it can be tuned quickly.

## Credits / protocol

The wire protocol was reverse-engineered from the WattSeek app for
interoperability with the owner's own hardware. See
[`PROTOCOL.md`](PROTOCOL.md) for the full details (UUIDs, keys, frame format,
function and parameter codes, register map).

This project is unofficial and not affiliated with WattSeek, CVTE or JSD Solar.
Use at your own risk; writing settings to an inverter can be dangerous, so this
integration is **read-only**.
