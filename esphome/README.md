# ESPHome Native BLE Client for TBD Smartshunt

This directory contains an ESPHome configuration that turns a dedicated ESP32
into a native BLE client for one or two TBD Smartshunt / DaYan DA1 battery
monitors.

## Why a Dedicated ESP32?

The TBD Smartshunt uses a Dialog DA14531 BLE chip that requires an **encrypted
link** (SMP pairing) to read telemetry. ESPHome Bluetooth Proxies cannot perform
real SMP key exchange — the proxy reports success but the link stays unencrypted.

By running the ESP32 as a **native BLE client** (not a proxy), the ESP32's own
BLE stack (ESP-IDF Bluedroid) handles "Just Works" pairing directly — just like
your phone does with nRF Connect.

## Quick Start

### 1. Prepare Secrets

Make sure your ESPHome `secrets.yaml` has these entries:

```yaml
wifi_ssid: "YourWiFiSSID"
wifi_password: "YourWiFiPassword"
api_encryption_key: "your-api-key-here"  # Generate with: esphome wizard
ota_password: "your-ota-password"
fallback_password: "your-fallback-password"
```

### 2. Edit the Config

Open `tbd_smartshunt_reader.yaml` and update the `substitutions` section with
your shunt MAC addresses:

```yaml
substitutions:
  shunt_1_mac: "FB:FB:FB:FF:0D:74"   # Your first shunt
  shunt_2_mac: "FB:FB:FF:02:AF"      # Your second shunt (or remove shunt_2 sections)
```

If you only have **one shunt**, delete or comment out all `shunt_2` related
sections (ble_client entry, globals, sensors, binary_sensor).

### 3. Flash

Using the ESPHome Dashboard or CLI:

```bash
esphome run tbd_smartshunt_reader.yaml
```

### 4. Add to Home Assistant

The ESP32 will appear as a new ESPHome device in Home Assistant. The sensors
(SOC, Voltage, Current, Power) per shunt will be available automatically.

## Important Notes

- This ESP32 is **dedicated** to reading shunts. It does **not** act as a
  Bluetooth Proxy for other devices. Your other ESP32s continue as proxies.

- The config uses `esp-idf` framework (not Arduino) for reliable BLE bonding.

- The ESP32 stores bonding keys in NVS (flash). After the first successful
  pairing, reconnections are instant without re-pairing.

- **Close vendor apps and nRF Connect** on your phone before flashing — they
  may hold the shunt's single BLE connection slot.

- The `board: esp32dev` works for most generic ESP32 boards. If you have a
  specific board (ESP32-C3, ESP32-S3), change accordingly.

## Telemetry Protocol

The 44-byte telemetry packet at characteristic `2d86686a-53dc-25b3-0c4a-f0e10c8dee20`
in service `18424398-7cbc-11e9-8f9e-2a86e4085a59` is parsed as:

| Offset | Type    | Field   |
|--------|---------|---------|
| 0–3    | uint32  | SOC (%) |
| 4–7    | float32 | Voltage (V) |
| 8–11   | float32 | Current (A) |
| 12–15  | float32 | Power (W) |
| 16–43  | unknown | Reserved |

## Troubleshooting

- **ESP32 connects but no sensor data**: Check ESPHome logs for SMP pairing
  events. The shunt may need a few seconds to complete pairing on first connect.

- **Frequent disconnects**: Ensure the ESP32 is within ~5m of the shunt.
  The DA14531 has limited range.

- **"Insufficient authentication" in logs**: This means the ESP-IDF stack is
  failing to negotiate SMP. Try erasing NVS (`esphome clean tbd_smartshunt_reader.yaml`)
  and reflashing to clear any stale bonding data.
