"""Decode only fields supported by captured TBD measurement packets."""
from __future__ import annotations
from dataclasses import dataclass
import math
import struct


@dataclass(frozen=True)
class ShuntData:
    soc: int
    voltage: float
    current: float
    power: float
    raw_tail: bytes


def parse_state_of_charge(raw_bytes: bytes) -> ShuntData | None:
    """SOC is device-reported. Offsets 16..43 have unverified meanings."""
    if len(raw_bytes) != 44:
        return None
    soc, voltage, current, power = struct.unpack_from("<Ifff", raw_bytes)
    if not 0 <= soc <= 100 or not all(math.isfinite(v) for v in (voltage, current, power)):
        return None
    if voltage < 0:
        return None
    return ShuntData(soc, voltage, current, power, bytes(raw_bytes[16:]))
