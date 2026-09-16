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
PAIR_COOLDOWN = 10
ENCRYPTION_DELAY = 1.5
READ_RETRIES = 3


class PairingFailed(Exception):
    """Pairing or the subsequent authenticated read did not succeed."""


class PairingUnsupported(PairingFailed):
    """The chosen backend cannot pair."""


def authentication_required(error: Exception | None) -> bool:
    """Recognize ATT failures, including wrapped proxy errors.

    An arbitrary OS 'error 5' must not trigger Bluetooth pairing.
    """
    if error is None:
        return False
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        message = str(error).lower()
        if any(text in message for text in (
            "insufficient authentication", "insufficient encryption",
            "insufficient_authentication", "insufficient_encryption",
            "insuf_authentication", "insuf_encryption",
            "authentication failed", "authentication required",
        )):
            return True
        if "gatt" in message and re.search(r"(?:error|status)\s*[:=]?\s*(?:0x0?5|0x0?f|5|15)\b", message):
            return True
        error = error.__cause__ or error.__context__
    return False


class PairingReader:
    """Pair once per auth failure, with delay and retry for link encryption."""

    def __init__(self) -> None:
        self._next_pair: dict[str, float] = {}

    def reset_cooldown(self, peer: str | None = None) -> None:
        """Reset cooldown for testing or reload."""
        if peer:
            self._next_pair.pop(peer, None)
        else:
            self._next_pair.clear()

    async def read(self, client, peer: str) -> bytes:
        # First attempt: read directly (succeeds if link is already encrypted/bonded)
        try:
            async with asyncio.timeout(READ_TIMEOUT):
                return bytes(await client.read_gatt_char(CHAR_STATE_OF_CHARGE))
        except Exception as err:
            if not authentication_required(err):
                raise
            _LOGGER.warning("[%s] Telemetry read requires authentication (%s). Starting pairing sequence...", peer, err)

        # Check cooldown to prevent hammering on repeated hard failures
        remaining = int(self._next_pair.get(peer, 0) - time.monotonic())
        if remaining > 0:
            raise PairingFailed(
                f"Authentication still required; automatic pairing is cooling down ({remaining}s remaining). "
                f"Pairing must use the connecting adapter; phone or host pairing does not bond a proxy."
            )
        self._next_pair[peer] = time.monotonic() + PAIR_COOLDOWN

        # Attempt pairing
        _LOGGER.warning("[%s] Initiating BLE pairing with device...", peer)
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

        # Wait for link encryption to settle (BlueZ kernel & peripheral SMP key exchange)
        if ENCRYPTION_DELAY > 0:
            _LOGGER.warning("[%s] Pairing completed. Waiting %.1fs for link encryption to stabilize...", peer, ENCRYPTION_DELAY)
            await asyncio.sleep(ENCRYPTION_DELAY)

        # Retry telemetry read with backoff
        last_err: Exception | None = None
        for attempt in range(1, READ_RETRIES + 1):
            try:
                _LOGGER.warning("[%s] Reading telemetry characteristic (attempt %d/%d)...", peer, attempt, READ_RETRIES)
                async with asyncio.timeout(READ_TIMEOUT):
                    payload = bytes(await client.read_gatt_char(CHAR_STATE_OF_CHARGE))
                self._next_pair.pop(peer, None)
                _LOGGER.warning("[%s] Authenticated telemetry read succeeded on attempt %d!", peer, attempt)
                return payload
            except Exception as err:
                last_err = err
                if authentication_required(err) and attempt < READ_RETRIES:
                    _LOGGER.warning(
                        "[%s] Read attempt %d still awaiting encryption (%s); retrying in %.1fs...",
                        peer, attempt, err, ENCRYPTION_DELAY
                    )
                    if ENCRYPTION_DELAY > 0:
                        await asyncio.sleep(ENCRYPTION_DELAY)
                    continue
                break

        # If read still failed with Insufficient Authentication after pairing, the bond in BlueZ may be stale.
        # Purge the stale bond so the next attempt starts fresh.
        if authentication_required(last_err):
            _LOGGER.warning("[%s] Telemetry read failed with Insufficient Authentication after pairing. Clearing potentially stale bond...", peer)
            if hasattr(client, "unpair"):
                try:
                    await client.unpair()
                    _LOGGER.warning("[%s] Cleared stale bond via client.unpair()", peer)
                except Exception as unpair_err:
                    _LOGGER.debug("[%s] Unpair error: %s", peer, unpair_err)

        raise PairingFailed(
            f"Pairing completed but telemetry read failed: {last_err}. "
            f"Pairing must use the connecting adapter; phone or host pairing does not bond a proxy."
        ) from last_err
