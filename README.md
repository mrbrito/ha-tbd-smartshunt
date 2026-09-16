# TBD Smartshunt for Home Assistant

Experimental local Bluetooth integration for TBD Smartshunt / DaYan DA1 devices.
Version 1.0.2 fixes the broken pairing handler and validates telemetry before setup.

## Sensors and evidence

Voltage, current, power and **Reported State of Charge** are exposed per shunt.
Two devices and three captured packets support the voltage/current/power layout.
Positive current was observed while charging with no load in the tested wiring.
Discharge encoding still requires a real capture. SOC is reported by the shunt:
it can say 100% on a depleted battery. This integration does not correct or
recalibrate it. Do not use that reported estimate as battery protection.

Previous versions labeled unknown fields as consumed Ah, remaining minutes,
uptime and auxiliary voltage. Those meanings have not been validated, so these
sensors are no longer created. Existing registry entries may remain unavailable;
they can be removed from the device page. Raw trailing bytes stay in the parser
for further protocol research. Firmware version is no longer hard-coded.

## Install

In HACS add `https://github.com/mrbrito/ha-tbd-smartshunt` as a custom repository
of type Integration, download, then restart Home Assistant. Alternatively copy
`custom_components/tbd_smartshunt` into your HA configuration's `custom_components`
directory and restart. Local changes are not on GitHub until explicitly published.

## Setup and pairing

1. Power the shunt and place a connectable Bluetooth adapter/proxy nearby.
2. Disconnect the vendor app and nRF Connect; they may occupy the device's connection.
3. Confirm the discovered TBD device, or add TBD Smartshunt and enter its MAC.
4. Setup connects and reads telemetry. If ATT reports insufficient authentication
   or encryption, it attempts `client.pair()` on that same connection and reads again.
5. An entry is created only after a valid telemetry packet is read. Repeat for
   each shunt. Separate Bluetooth addresses identify the devices.

The normal path reads without pairing when the link is already authorized.
Each transaction attempts pairing at most once (30-second timeout) and retries
its read once. Failed pairing has a five-minute cooldown per shunt in the running
HA process, including setup retries. Reloading the integration retains that
cooldown; restarting HA clears it. A bonded link can reconnect without user input
when the adapter and device retain their bond. Polling releases the connection
slot after each read (default 15 seconds; configurable during manual setup).

ESPHome proxies must support active GATT connections and pairing. The backend
checks the firmware's PAIRING capability. Pairing is between the shunt and the
actual adapter/proxy: pairing your phone or running `bluetoothctl` against a
host adapter does not bond an ESPHome proxy. Another proxy may need its own
bond. The shunt's bond capacity and behavior across multiple proxies are untested.

If a passkey or confirmation is required, fully unattended pairing may fail.
This release does not implement a passkey agent and never guesses or writes the
custom PIN characteristic. It does not unpair devices or erase stored bonds.
Close phone connections, check range and firmware, then check HA logs for the
specific pairing/read failure. An unsupported adapter gets a distinct setup error.

Discovery matches TBD device names; a generic SDK service UUID alone is not
sufficient. Manual entry remains available for renamed devices. The expected
service and characteristic must exist before any telemetry read or pairing.

## Protocol (provisional)

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
negative voltage are rejected. Precision is retained internally; display rounding
is handled by sensor descriptions. This is a read-only measurement integration
apart from Bluetooth pairing; no configuration/calibration characteristic writes.

## Development and validation

Run `python -B -m unittest discover -s tests -v`. Tests cover captured packets,
malformed values and the read/pair/read transaction. Mock pairing tests do not
prove hardware compatibility. See CHANGELOG.md for changes and live-test results.

References:
- https://developers.home-assistant.io/docs/bluetooth/
- https://esphome.io/components/bluetooth_proxy/
- https://github.com/Bluetooth-Devices/bleak-esphome

MIT license.
