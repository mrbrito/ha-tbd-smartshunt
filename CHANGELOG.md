# Changelog

## 2.0.0

**Architecture pivot: ESPHome Native BLE Client**

After extensive testing (v1.0.1–v1.0.5), we confirmed that ESPHome Bluetooth
Proxies cannot perform real SMP pairing with the Dialog DA14531 chip used in
TBD Smartshunt / DaYan DA1 devices. The proxy reports `paired=True` but the
BLE link remains unencrypted, causing all GATT operations (reads, CCCD writes,
notification subscriptions) to fail with `Insufficient authentication` (ATT
Error 0x05).

### New: ESPHome Native `ble_client` Config (Recommended)

- Added `esphome/tbd_smartshunt_reader.yaml` — a complete ESPHome config that
  turns a dedicated ESP32 into a native BLE client for 1-2 TBD Smartshunts.
- The ESP32 connects directly to each shunt, handles "Just Works" SMP pairing
  via the ESP-IDF Bluedroid stack, reads encrypted telemetry, and exposes SOC,
  Voltage, Current, and Power sensors to Home Assistant via the ESPHome API.
- Uses `esp-idf` framework for reliable BLE security support.
- Includes connection status binary sensors and diagnostic sensors.
- Bond persistence via NVS — reconnections are instant after first pairing.
- Added `esphome/README.md` with setup instructions and troubleshooting.

### Custom Integration Updates (for USB Bluetooth Dongle users)

- Detect whether connection is via ESPHome proxy or local BlueZ adapter.
- Improved error messages clearly recommend ESPHome native `ble_client` approach
  when proxy authentication fails.
- Increased pairing cooldown to 30s (stable release, no longer rapid testing).
- Bumped version to 2.0.0.

## 1.0.5

- Add GATT notification stream support (`client.start_notify`) on Characteristic `2d86686a-53dc-25b3-0c4a-f0e10c8dee20` via CCCD `0x2902`, enabling telemetry readouts across unbonded ESPHome Bluetooth Proxies.
- Add adaptive transport: automatically caches notification preference on peers where direct reads report insufficient authentication, skipping redundant auth-fail cycles on subsequent polls.
- Add MTU chunk reassembly (handles 20+20+4 byte fragments) with sliding-window packet validation.
- Log connecting adapter/proxy source (`device.details["source"]`) and Bleak backend (`BleakClientESPHome` vs. `BleakClientBlueZDBus`) at WARNING level for instant visibility in Home Assistant logs.
- Include full raw packet hex dump in error logs if a telemetry payload fails packet parsing.
- Provide explicit ESPHome proxy bonding configuration guidance (`esp32_ble: auth_req_mode: sc_bond`) in error messages and documentation.

## 1.0.4

- Pass `pair=True` in `establish_connection` to initiate link encryption on connect.
- Add 1.5s encryption stabilization delay and 3-attempt read retry loop after pairing.
- Purge stale bonds via `client.unpair()` if reads fail with Insufficient Authentication despite pairing.
- Clear pairing cooldown automatically on integration reload/init, and shorten cooldown to 10s.
- Promote key diagnostic logs to `WARNING` so all pairing/read steps appear in Home Assistant's System Log UI.

## 1.0.3

- Reduce pairing failure cooldown from 5 minutes (300s) to 15 seconds for testing.
- Include exact countdown seconds in the cooldown log message.

## 1.0.2

- Fix invalid syntax in pairing handler.
- Add bounded read/pair/read with auth-specific detection, failure cooldown,
  cancellation propagation, and disconnect cleanup that preserves original errors.
- Validate a telemetry read during setup; show distinct pairing failure and
  unsupported-adapter errors. Keep manual address input available.
- Restrict automatic discovery to TBD names and verify GATT service/characteristic.
- Reject malformed length, nonfinite values and out-of-range SOC.
- Stop publishing unverified auxiliary/capacity/time/uptime fields; label SOC
  as device-reported. Preserve measurement precision and remove fixed firmware ID.
- Add captured samples and pairing regression tests.

Live pairing verification is pending deployment.
