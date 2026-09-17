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
        # Architecture Audit: We must use the Home Assistant host Bluetooth framework
        # to initiate start_pairing via Bleak such that cryptographic keys save to the host's
        # BlueZ stack database. This prevents proxy-roaming auth failures.
        # Thus, we must prioritize local host adapters over ESPHome proxies.
        all_scanner_devices = bluetooth.async_scanner_devices_by_address(self.hass, self.address, connectable=True)
        if not all_scanner_devices:
            raise UpdateFailed(f"{self.address} is not visible to a connectable Bluetooth adapter/proxy")
        
        # Prioritize local BlueZ adapters to ensure server-side bonding works
        device = None
        for scanner_device in all_scanner_devices:
            # async_scanner_devices_by_address returns BluetoothScannerDevice objects
            ble_device = getattr(scanner_device, "ble_device", scanner_device)
            details = getattr(ble_device, "details", None)
            if isinstance(details, dict):
                source = details.get("source", "")
                if "hci" in source.lower() or "path" in details:
                    device = ble_device
                    _LOGGER.info("[%s] Selected local BlueZ host adapter '%s' to implement server-side bonding", self.address, source)
                    break
        
        # Fallback to the best available if no local adapter is found
        if device is None:
            device = getattr(all_scanner_devices[0], "ble_device", all_scanner_devices[0])
            _LOGGER.warning("[%s] No local BlueZ host adapter found. Falling back to default proxy. "
                            "Server-side bonding to the BlueZ database may not be possible.", self.address)

        details = getattr(device, "details", None)
        source = details.get("source") if isinstance(details, dict) else "local/unknown"
        is_proxy = isinstance(details, dict) and "source" in details and "hci" not in source.lower() and "path" not in details
        client = None
        try:
            _LOGGER.warning("[%s] Connecting to TBD Smartshunt via %s: %s...",
                            self.address, "ESPHome proxy" if is_proxy else "local adapter", source)
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
        except (PairingFailed, UpdateFailed) as err:
            if is_proxy:
                _LOGGER.error(
                    "[%s] Authentication failed via ESPHome proxy '%s'. "
                    "ESPHome Bluetooth Proxies cannot perform real SMP pairing with the "
                    "Dialog DA14531 chip on TBD Smartshunts. "
                    "RECOMMENDED: Use the ESPHome native ble_client config in the esphome/ "
                    "directory to flash a dedicated ESP32 as a direct BLE client. "
                    "ALTERNATIVE: Use a USB Bluetooth dongle on your HA host.",
                    self.address, source,
                )
            raise
        except (BleakError, TimeoutError) as err:
            err_msg = str(err)
            if "Pairing is not available" in err_msg or "insufficient authentication" in err_msg.lower():
                raise UpdateFailed(
                    f"{self.address}: Bluetooth proxy cannot establish encrypted link. "
                    f"The TBD Smartshunt requires SMP pairing that ESPHome proxies cannot perform. "
                    f"Use the ESPHome native ble_client approach (see esphome/ directory) "
                    f"or a local USB Bluetooth adapter on the HA host."
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
