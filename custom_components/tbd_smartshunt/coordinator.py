"""Polling through Home Assistant's shared Bluetooth adapters and proxies."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from bleak import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, CHAR_STATE_OF_CHARGE, DEFAULT_POLL_INTERVAL, SERVICE_UUID
from .parser import ShuntData, parse_state_of_charge
from .transport import PairingFailed, PairingReader

_LOGGER = logging.getLogger(__name__)


class TbdSmartshuntCoordinator(DataUpdateCoordinator[ShuntData]):
    """Read one shunt without monopolizing a proxy connection slot."""

    def __init__(self, hass: HomeAssistant, address: str, name: str,
                 poll_interval: int = DEFAULT_POLL_INTERVAL) -> None:
        super().__init__(hass, _LOGGER, name=f"{name} ({address})",
                         update_interval=timedelta(seconds=poll_interval))
        self.address = address
        self.device_name = name
        self._reader: PairingReader = hass.data.setdefault(DOMAIN, {}).setdefault("_pairing_readers", {}).setdefault(address, PairingReader())
        # Clear any leftover cooldown on reload/init so testing is never blocked
        self._reader.reset_cooldown(address)

    async def async_read_data(self) -> ShuntData:
        """Also used by config flow to validate before creating an entry."""
        device = bluetooth.async_ble_device_from_address(self.hass, self.address, connectable=True)
        if device is None:
            raise UpdateFailed(f"{self.address} is not visible to a connectable Bluetooth adapter/proxy")
        details = getattr(device, "details", None)
        source = details.get("source") if isinstance(details, dict) else "local/unknown"
        client = None
        try:
            _LOGGER.warning("[%s] Connecting to TBD Smartshunt via adapter/proxy: %s...", self.address, source)
            try:
                async with asyncio.timeout(45):
                    client = await establish_connection(
                        BleakClientWithServiceCache, device, self.device_name, max_attempts=2, pair=True,
                    )
            except TypeError:
                # In case older bleak_retry_connector without pair argument is installed
                async with asyncio.timeout(45):
                    client = await establish_connection(
                        BleakClientWithServiceCache, device, self.device_name, max_attempts=2,
                    )
            backend_name = type(getattr(client, "_backend", client)).__name__
            _LOGGER.warning("[%s] Connected to TBD Smartshunt via %s (backend: %s)", self.address, source, backend_name)
            service = client.services.get_service(SERVICE_UUID)
            if service is None or not any(c.uuid.lower() == CHAR_STATE_OF_CHARGE for c in service.characteristics):
                raise UpdateFailed("Device does not expose the expected TBD telemetry characteristic")
            raw = await self._reader.read(client, self.address)
            data = parse_state_of_charge(raw)
            if data is None:
                raise UpdateFailed(
                    f"Invalid telemetry from {self.address}: expected valid 44-byte packet, "
                    f"received {len(raw)} bytes (hex: {raw.hex()})"
                )
            _LOGGER.warning(
                "[%s] Telemetry read successful! SoC=%d%%, Voltage=%.2fV, Current=%.2fA, Power=%.2fW",
                self.address, data.soc, data.voltage, data.current, data.power,
            )
            return data
        except (PairingFailed, UpdateFailed):
            raise
        except (BleakError, TimeoutError) as err:
            err_msg = str(err)
            if "Pairing is not available" in err_msg:
                raise UpdateFailed(
                    f"{self.address}: Bluetooth proxy does not support BLE pairing. "
                    f"The TBD Smartshunt requires an encrypted link. "
                    f"Please use a local Bluetooth adapter or configure ESPHome with "
                    f"'esp32_ble: auth_req_mode: sc_bond' and 'io_capability: none'."
                ) from err
            raise UpdateFailed(f"Bluetooth communication failed for {self.address}: {err}") from err
        finally:
            if client is not None:
                try:
                    async with asyncio.timeout(10):
                        await client.disconnect()
                except Exception as err:
                    _LOGGER.debug("[%s] Disconnect cleanup: %s", self.address, err)

    async def _async_update_data(self) -> ShuntData:
        try:
            return await self.async_read_data()
        except PairingFailed as err:
            raise UpdateFailed(f"{self.address}: {err}") from err
