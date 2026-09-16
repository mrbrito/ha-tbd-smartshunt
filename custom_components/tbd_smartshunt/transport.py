"""Bounded read/pair/read transaction, independent of Home Assistant."""
from __future__ import annotations

import asyncio
import logging
import re
import time

from .const import CHAR_STATE_OF_CHARGE

_LOGGER = logging.getLogger(__name__)
PAIR_TIMEOUT = 30
READ_TIMEOUT = 20
PAIR_COOLDOWN = 15


class PairingFailed(Exception):
    """Pairing or the subsequent authenticated read did not succeed."""


class PairingUnsupported(PairingFailed):
    """The chosen backend cannot pair."""


def authentication_required(error: Exception) -> bool:
    """Recognize ATT failures, including wrapped proxy errors.

    An arbitrary OS 'error 5' must not trigger Bluetooth pairing.
    """
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        message = str(error).lower()
        if any(text in message for text in (
            "insufficient authentication", "insufficient encryption",
            "insufficient_authentication", "insufficient_encryption",
            "insuf_authentication", "insuf_encryption",
        )):
            return True
        if "gatt" in message and re.search(r"(?:error|status)\s*[:=]?\s*(?:0x0?5|0x0?f|5|15)\b", message):
            return True
        error = error.__cause__ or error.__context__
    return False


class PairingReader:
    """Pair once per auth failure, with cooldown after failed pairing.

    No application PIN writes, unpairing, or factory resets.
    """

    def __init__(self) -> None:
        self._next_pair: dict[str, float] = {}

    async def read(self, client, peer: str) -> bytes:
        try:
            async with asyncio.timeout(READ_TIMEOUT):
                return bytes(await client.read_gatt_char(CHAR_STATE_OF_CHARGE))
        except Exception as err:
            if not authentication_required(err):
                raise
        remaining = int(self._next_pair.get(peer, 0) - time.monotonic())
        if remaining > 0:
            raise PairingFailed(f"Authentication still required; automatic pairing is cooling down ({remaining}s remaining)")
        self._next_pair[peer] = time.monotonic() + PAIR_COOLDOWN
        _LOGGER.info("Authentication required for %s; attempting pairing through connected adapter", peer)
        try:
            async with asyncio.timeout(PAIR_TIMEOUT):
                result = await client.pair()
            # Old Bleak returns bool, new Bleak returns None.
            if result is False:
                raise PairingFailed("Adapter reported pairing failure")
        except NotImplementedError as err:
            raise PairingUnsupported("Selected adapter cannot pair; check its pairing capability and ESPHome firmware") from err
        except TimeoutError as err:
            raise PairingFailed("Pairing timed out; disconnect phone apps and check whether the shunt requires a passkey") from err
        except PairingFailed:
            raise
        except Exception as err:
            raise PairingFailed(f"Pairing failed through selected adapter: {err}") from err
        try:
            async with asyncio.timeout(READ_TIMEOUT):
                payload = bytes(await client.read_gatt_char(CHAR_STATE_OF_CHARGE))
        except Exception as err:
            raise PairingFailed(f"Pairing completed but telemetry read failed: {err}") from err
        self._next_pair.pop(peer, None)
        _LOGGER.info("Authenticated telemetry read succeeded for %s", peer)
        return payload
