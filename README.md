# TBD Smartshunt for Home Assistant

Bluetooth integration for TBD Smartshunt / DaYan DA1 battery monitors.

## ⚡ Recommended Setup: ESPHome Native BLE Client

> **The TBD Smartshunt requires BLE link encryption (SMP pairing) to read
> telemetry. ESPHome Bluetooth Proxies cannot perform real SMP pairing with
> the Dialog DA14531 chip. The recommended approach is to use a dedicated
> ESP32 as a native BLE client.**

### How It Works

Instead of using an ESP32 as a Bluetooth proxy (which can't pair), you flash
one ESP32 with a config that makes it connect **directly** to the shunt(s),
handle pairing locally (just like your phone does), read telemetry, and expose
sensors to Home Assistant via the ESPHome API.

### Quick Setup

1. Copy `esphome/tbd_smartshunt_reader.yaml` to your ESPHome config directory
2. Edit the `substitutions` section with your shunt MAC address(es)
3. Configure your `secrets.yaml` with WiFi, API key, and OTA password
4. Flash to any ESP32: `esphome run tbd_smartshunt_reader.yaml`
5. Sensors appear automatically in Home Assistant

See [esphome/README.md](esphome/README.md) for detailed instructions.

### What You Get

Per shunt:
- **State of Charge** (%) — device-reported, not recalculated
- **Voltage** (V) — battery voltage
- **Current** (A) — charge/discharge current
- **Power** (W) — calculated power
- **Connection Status** — binary sensor showing BLE connection state

## Alternative: Custom Integration (USB Bluetooth Dongle)

If your Home Assistant host has a **local USB Bluetooth adapter** (not an
ESPHome proxy), the custom integration can pair using BlueZ natively.

### Install

In HACS add `https://github.com/mrbrito/ha-tbd-smartshunt` as a custom repository
of type Integration, download, then restart Home Assistant. Alternatively copy
`custom_components/tbd_smartshunt` into your HA configuration's `custom_components`
directory and restart.

### Setup and Pairing

1. Power the shunt and ensure a **local** Bluetooth adapter is available.
2. Disconnect the vendor app and nRF Connect; they may occupy the device's connection.
3. Confirm the discovered TBD device, or add TBD Smartshunt and enter its MAC.
4. Setup connects, pairs via BlueZ, and reads telemetry.

> ⚠️ **This will NOT work via ESPHome Bluetooth Proxies.** If you only have
> ESP32 proxies and no USB Bluetooth dongle, use the ESPHome native BLE client
> approach above.

## Sensors and Evidence

Voltage, current, power and **Reported State of Charge** are exposed per shunt.
Two devices and three captured packets support the voltage/current/power layout.
Positive current was observed while charging with no load in the tested wiring.
Discharge encoding still requires a real capture. SOC is reported by the shunt:
it can say 100% on a depleted battery. This integration does not correct or
recalibrate it. Do not use that reported estimate as battery protection.

## Protocol (Provisional)

Service: `18424398-7cbc-11e9-8f9e-2a86e4085a59`

Telemetry: `2d86686a-53dc-25b3-0c4a-f0e10c8dee20`

| Offset | Interpretation | Status |
| --- | --- | --- |
| 0..3 | Little-endian uint32 reported SOC | Only 100% captured; width/scaling need more samples |
| 4..7 | Little-endian float32 voltage | Supported by captures |
| 8..11 | Little-endian float32 current | Supported; discharge sign unverified |
| 12..15 | Little-endian float32 power | Supported by captures |
| 16..43 | Unknown fields | Preserved without physical units |

Exactly 44 bytes are accepted. Nonfinite measurements, SOC outside 0..100 and
negative voltage are rejected. This is a read-only measurement integration.

## Why Not Bluetooth Proxies?

The Dialog DA14531 BLE chip on the TBD Smartshunt enforces `GATT_PERM_READ_ENCRYPTED`
on all telemetry characteristics. This requires a real SMP (Security Manager Protocol)
key exchange to establish an encrypted BLE link. ESPHome Bluetooth Proxies relay
GATT commands but cannot perform real SMP pairing — the proxy reports success but
the link remains unencrypted. Every approach was tested over 5 releases (v1.0.1–v1.0.5):

- Direct GATT reads → ATT Error 5
- GATT notification subscriptions (CCCD writes) → ATT Error 5
- `client.pair()` via proxy → Returns instantly without real key exchange
- Post-pairing reads → Still ATT Error 5

Phones work because they use native BLE stacks that handle SMP correctly. The
ESPHome native `ble_client` approach works the same way — the ESP32's own ESP-IDF
Bluedroid stack handles pairing directly.

## Development and Validation

Run `python -B -m unittest discover -s tests -v`. Tests cover captured packets,
malformed values and the read/pair/read transaction. Mock pairing tests do not
prove hardware compatibility. See CHANGELOG.md for changes and live-test results.

References:
- https://developers.home-assistant.io/docs/bluetooth/
- https://esphome.io/components/ble_client.html
- https://esphome.io/components/esp32_ble.html
- https://github.com/Bluetooth-Devices/bleak-esphome

MIT license.
