# Changelog

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
