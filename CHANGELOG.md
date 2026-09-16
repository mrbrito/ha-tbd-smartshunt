# Changelog

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
