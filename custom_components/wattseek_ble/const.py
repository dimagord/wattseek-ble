"""Constants for the WattSeek BLE integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "wattseek_ble"

# --- BLE GATT -------------------------------------------------------------
# DATALOGGER_BLE_CONFIG from the WattSeek app (com.cvte.wattseek).
# The logger exposes one service with a single characteristic used for both
# writing commands and receiving notifications.
SERVICE_UUID: Final = "000000ff-0000-1000-8000-00805f9b34fb"
CHAR_UUID: Final = "0000ff01-0000-1000-8000-00805f9b34fb"

# --- Crypto ---------------------------------------------------------------
# AES-128-CBC, NoPadding, IV == key. Key is the ASCII bytes of this string.
# (The app also ships a 32-byte BLUETOOTH_HANDSHAKE_KEY used only during the
# SET BLUETOOTH_KEY handshake, see protocol.py.)
DATA_KEY: Final = b"sxd_aiot_key_001"
HANDSHAKE_KEY: Final = b"shuoxd_aiot_local_wireless_key01"

# --- Frame --------------------------------------------------------------
PROTO_ID: Final = 0x0006
DEVICE_ADDR: Final = 0x01

# FunctionCode enum (from the app)
FC_TRANSPARENT: Final = 0x17
FC_SET: Final = 0x18
FC_QUERY: Final = 0x19
FC_FOTA: Final = 0x26
FC_WIRELESS_CT_PAIRING: Final = 0x30
FC_TRANSPARENT_BATCH: Final = 0x47

# ParamCode enum (datalogger parameters, used with SET/QUERY)
PARAM_DATALOGGER_SN: Final = 8
PARAM_LOCAL_IP: Final = 14
PARAM_REMOTE_IP: Final = 17
PARAM_FIRMWARE_VERSION: Final = 21
PARAM_DATA_INTERVAL: Final = 4
PARAM_LINK_STATUS: Final = 60
PARAM_BLUETOOTH_KEY: Final = 54
PARAM_CONNECT_STATUS: Final = 55
PARAM_WIFI_SSID: Final = 56
PARAM_DEVICE_SN: Final = 106
PARAM_PROTOCOL_VERSION: Final = 200

# Inverter Modbus slave address (reached through the TRANSPARENT tunnel)
INVERTER_MODBUS_ID: Final = 0x01

# --- Config entry options -------------------------------------------------
CONF_ADDRESS: Final = "address"
CONF_UPDATE_INTERVAL: Final = "update_interval"
CONF_ALLOW_WRITES: Final = "allow_writes"
DEFAULT_UPDATE_INTERVAL: Final = 30
MIN_UPDATE_INTERVAL: Final = 5
MAX_UPDATE_INTERVAL: Final = 600
