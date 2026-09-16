"""Telemetry parser for TBD Smartshunt (DaYan DA1) BLE devices."""

from __future__ import annotations
from dataclasses import dataclass
import struct
from typing import Optional
import logging

_LOGGER = logging.getLogger(__name__)


@dataclass
class ShuntData:
    """Parsed telemetry data from TBD Smartshunt."""
    soc: int
    voltage: float
    current: float
    power: float
    consumed_ah: float
    time_remaining_minutes: Optional[int]
    uptime_seconds: int
    aux_voltage: Optional[float] = None


def parse_state_of_charge(raw_bytes: bytes) -> Optional[ShuntData]:
    """Parse the 44-byte STATE OF CHARGE payload.

    Structure:
      Offset 0-3  : uint32 SoC (%)
      Offset 4-7  : float32 Battery Voltage (V)
      Offset 8-11 : float32 Battery Current (A)
      Offset 12-15: float32 Instantaneous Power (W)
      Offset 16-19: float32 Auxiliary Voltage / Starter Battery (V)
      Offset 20-23: uint32 Time Remaining (min, 0xFFFFFFFF = Infinite / Charging)
      Offset 24-27: uint32 Uptime / Counter (sec)
      Offset 28-31: float32 Consumed Amp-Hours (Ah)
      Offset 32-43: Reserved / padding
    """
    if not raw_bytes or len(raw_bytes) < 32:
        _LOGGER.debug("Received payload too short (%d bytes)", len(raw_bytes) if raw_bytes else 0)
        return None

    try:
        soc = struct.unpack_from("<I", raw_bytes, 0)[0]
        voltage = struct.unpack_from("<f", raw_bytes, 4)[0]
        current = struct.unpack_from("<f", raw_bytes, 8)[0]
        power = struct.unpack_from("<f", raw_bytes, 12)[0]
        aux_raw = struct.unpack_from("<f", raw_bytes, 16)[0]
        time_rem_raw = struct.unpack_from("<I", raw_bytes, 20)[0]
        uptime = struct.unpack_from("<I", raw_bytes, 24)[0]
        consumed_ah = struct.unpack_from("<f", raw_bytes, 28)[0]

        # 0xFFFFFFFF represents infinite time remaining (e.g. charging or zero current)
        time_remaining = None if time_rem_raw == 0xFFFFFFFF else int(time_rem_raw)

        return ShuntData(
            soc=int(soc),
            voltage=round(float(voltage), 2),
            current=round(float(current), 2),
            power=round(float(power), 2),
            consumed_ah=round(float(consumed_ah), 2),
            time_remaining_minutes=time_remaining,
            uptime_seconds=int(uptime),
            aux_voltage=round(float(aux_raw), 2) if aux_raw > 0.1 else None,
        )
    except struct.error as err:
        _LOGGER.warning("Error unpacking TBD shunt payload: %s", err)
        return None
