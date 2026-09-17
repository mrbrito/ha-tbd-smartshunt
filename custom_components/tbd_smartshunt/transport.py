"""Bounded read/pair/read transaction, independent of Home Assistant."""
from __future__ import annotations

import asyncio
import logging
import re
import time

from .const import CHAR_STATE_OF_CHARGE
from .parser import parse_state_of_charge

_LOGGER = logging.getLogger(__name__)
PAIR_TIMEOUT = 30
READ_TIMEOUT = 20
NOTIFY_TIMEOUT = 6
PAIR_COOLDOWN = 30
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
        self._prefer_notify: set[str] = set()

    def reset_cooldown(self, peer: str | None = None) -> None:
        """Reset cooldown for testing or reload."""
        if peer:
            self._next_pair.pop(peer, None)
            self._prefer_notify.discard(peer)
        else:
            self._next_pair.clear()
            self._prefer_notify.clear()

    async def _read_via_notify(self, client, peer: str, timeout: float = NOTIFY_TIMEOUT) -> bytes | None:
        """Attempt to receive telemetry via GATT notification (CCCD 0x2902)."""
        if not hasattr(client, "start_notify"):
            return None

        received = bytearray()
        event = asyncio.Event()
        valid_payload: list[bytes] = []

        def _notification_handler(_char, data: bytes | bytearray) -> None:
            received.extend(data)
            if len(received) >= 44:
                for i in range(len(received) - 43):
                    candidate = bytes(received[i:i + 44])
                    if parse_state_of_charge(candidate) is not None:
                        valid_payload.append(candidate)
                        event.set()
                        return
                if len(received) >= 88:
                    event.set()

        try:
            _LOGGER.warning("[%s] Subscribing to telemetry notifications on %s...", peer, CHAR_STATE_OF_CHARGE)
            await client.start_notify(CHAR_STATE_OF_CHARGE, _notification_handler)
            try:
                async with asyncio.timeout(timeout):
                    await event.wait()
            finally:
                if hasattr(client, "stop_notify"):
                    try:
                        await client.stop_notify(CHAR_STATE_OF_CHARGE)
                    except Exception as stop_err:
                        _LOGGER.debug("[%s] Cleanup stop_notify: %s", peer, stop_err)

            if valid_payload:
                _LOGGER.warning(
                    "[%s] Successfully received valid telemetry via notification (%d bytes)!",
                    peer, len(valid_payload[0])
                )
                return valid_payload[0]
            if len(received) >= 44:
                _LOGGER.warning("[%s] Received %d notification bytes (raw fallback)", peer, len(received))
                return bytes(received[:44])
            _LOGGER.warning("[%s] Notification subscription finished without receiving 44 bytes (got %d bytes)", peer, len(received))
        except Exception as err:
            _LOGGER.warning("[%s] Notification subscription failed: %s", peer, err)
        return None

    async def read(self, client, peer: str) -> bytes:
        # If notifications previously succeeded on this peer, prefer notifications
        if peer in self._prefer_notify:
            notify_data = await self._read_via_notify(client, peer)
            if notify_data:
                return notify_data
            self._prefer_notify.discard(peer)

        # First attempt: read directly (succeeds if link is already encrypted/bonded)
        try:
            async with asyncio.timeout(READ_TIMEOUT):
                payload = bytes(await client.read_gatt_char(CHAR_STATE_OF_CHARGE))
                self._prefer_notify.discard(peer)
                return payload
        except Exception as err:
            if not authentication_required(err):
                raise
            _LOGGER.warning("[%s] Telemetry read requires authentication (%s). Trying notification stream...", peer, err)

        # Second attempt: try notification stream before attempting pairing
        notify_data = await self._read_via_notify(client, peer)
        if notify_data:
            self._prefer_notify.add(peer)
            return notify_data

        # Third attempt: Check cooldown to prevent hammering on repeated hard failures
        remaining = int(self._next_pair.get(peer, 0) - time.monotonic())
        if remaining > 0:
            raise PairingFailed(
                f"Authentication still required; automatic pairing is cooling down ({remaining}s remaining). "
                f"ESPHome Bluetooth Proxies cannot perform real SMP pairing with this device. "
                f"RECOMMENDED: Use the ESPHome native ble_client config (see esphome/ directory) "
                f"or a local USB Bluetooth adapter on the HA host."
            )
        self._next_pair[peer] = time.monotonic() + PAIR_COOLDOWN

        # Attempt pairing
        _LOGGER.warning("[%s] Initiating BLE pairing with device to establish server-side bonding...", peer)
        try:
            async with asyncio.timeout(PAIR_TIMEOUT):
                # Pass protection_level=1 (Just Works/Encryption) to BlueZ if backend supports it
                try:
                    result = await client.pair(protection_level=1)
                except TypeError:
                    # Fallback for backends (like bleak-esphome) that don't accept protection_level
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

        # Also try notification stream one last time after pairing
        _LOGGER.warning("[%s] Direct read failed after pairing; attempting notification stream as final fallback...", peer)
        notify_data = await self._read_via_notify(client, peer)
        if notify_data:
            self._prefer_notify.add(peer)
            self._next_pair.pop(peer, None)
            return notify_data

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
            f"ESPHome Bluetooth Proxies cannot perform real SMP key exchange with the "
            f"Dialog DA14531 chip on TBD Smartshunts. "
            f"RECOMMENDED: Use the ESPHome native ble_client config (see esphome/ directory) "
            f"to flash a dedicated ESP32 as a direct BLE client. "
            f"ALTERNATIVE: Use a USB Bluetooth dongle on your HA host."
        ) from last_err
