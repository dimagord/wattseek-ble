# WattSeek BLE local protocol

Reverse-engineered from `com.cvte.wattseek` (React Native / Hermes bundle) and
verified against live BLE captures, for interoperability with one's own
inverter. Read-only use.

## BLE GATT

| | UUID |
|---|---|
| Service | `000000ff-0000-1000-8000-00805f9b34fb` |
| Characteristic (write + notify) | `0000ff01-0000-1000-8000-00805f9b34fb` |

A single characteristic carries both directions: write with response to send,
notifications to receive. Writes use "with-response".

## Encryption

- **AES-128-CBC, no padding, IV = key.**
- Data key: `sxd_aiot_key_001` (16 ASCII bytes).
- Handshake key: `shuoxd_aiot_local_wireless_key01` (32 ASCII bytes), sent once
  as `SET BLUETOOTH_KEY` right after connecting.
- Plaintext is zero-padded to a 16-byte boundary before encryption; the real
  length travels in the header.

## Outer frame

| offset | size | field |
|---|---|---|
| 0 | 2 | length of everything after these 2 bytes (big-endian) |
| 2 | 2 | `PROTO_ID` = `0x0006` (big-endian) |
| 4 | 2 | plaintext length before padding (big-endian) |
| 6 | 1 | `DEVICE_ADDR` = `0x01` |
| 7 | 1 | FunctionCode |
| 8 | N | AES ciphertext (multiple of 16) |
| 8+N | 2 | **CRC16/Modbus** over bytes `0 … 8+N`, **big-endian** |

(The inverter-side Modbus frames carried inside TRANSPARENT use the normal
Modbus CRC byte order — little-endian — as usual.)

## FunctionCode

| name | value |
|---|---|
| TRANSPARENT | `0x17` |
| SET | `0x18` |
| QUERY | `0x19` |
| FOTA | `0x26` |
| WIRELESS_CT_PAIRING | `0x30` |
| TRANSPARENT_BATCH | `0x47` |

- **SET / QUERY** operate on *datalogger* parameters (see ParamCode).
- **TRANSPARENT** tunnels raw bytes to the inverter's Modbus line — this is how
  live electrical data is read: send `01 03 <addr> <count> <crc>`, receive the
  Modbus reply back inside the response payload.

## ParamCode (datalogger, used with SET/QUERY)

| name | value |
|---|---|
| DATA_INTERVAL | 4 |
| DATALOGGER_SN | 8 |
| LOCAL_IP | 14 |
| REMOTE_IP | 17 |
| FIRMWARE_VERSION | 21 |
| BLUETOOTH_KEY | 54 |
| CONNECT_STATUS | 55 |
| WIFI_SSID | 56 |
| LINK_STATUS | 60 |
| DEVICE_SN | 106 |
| PROTOCOL_VERSION | 200 |
| INVERTER_PRODUCT_CODE | 201 |
| INVERTER_MODEL_CODE | 203 |
| INVERTER_DEVICE_MODEL | 204 |

## Inner application layer (best-effort)

Decrypted payloads begin with a 9-byte device-id field: `"000000000"` from the
client until the logger reports its own id (`"SXDICA3EC"…`), followed by a small
header `69 55 <func-byte> <seq:2>` for requests. This part is reconstructed
heuristically and logged raw for refinement.

## Inverter register map

JSD Solar 3KU family, protocol V1.20 (same map the ESPHome JSDSolar project
uses). Key realtime holding registers (function `0x03`):

| addr | value | scale | signed |
|---|---|---|---|
| 0x0050 | Grid voltage | 0.1 V | no |
| 0x0053 | Grid power | 1 W | yes |
| 0x0080 | Battery voltage | 0.1 V | no |
| 0x0081 | Battery current | 0.1 A | yes |
| 0x0084 | Battery SOC | 0.1 % | no |
| 0x0085 | Battery power | 1 W | yes |
| 0x0096 | PV1 voltage | 0.1 V | no |
| 0x0098 | PV1 power | 1 W | yes |
| 0x009B | PV2 power | 1 W | yes |
| 0x0331 | Inverter temperature | 0.1 °C | yes |

(full list in `registers.py`)
