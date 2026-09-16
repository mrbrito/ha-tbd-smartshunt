# Changelog

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
