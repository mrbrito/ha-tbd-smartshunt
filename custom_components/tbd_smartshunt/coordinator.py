"""DataUpdateCoordinator for the TBD Smartshunt integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.components import bluetooth
from bleak_retry_connector import establish_connection, BleakClientWithServiceCache
from bleak import BleakError

from .const import DOMAIN, CHAR_STATE_OF_CHARGE, DEFAULT_POLL_INTERVAL
from .parser import ShuntData, parse_state_of_charge

_LOGGER = logging.getLogger(__name__)


class TbdSmartshuntCoordinator(DataUpdateCoordinator[ShuntData]):
    """Coordinator to manage fetching data from TBD Smartshunt via Bluetooth."""

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        name: str,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{name} ({address})",
            update_interval=timedelta(seconds=poll_interval),
        )
        self.address = address
        self.device_name = name

    async def _async_update_data(self) -> ShuntData:
        """Connect to the shunt, read the telemetry characteristic, and return parsed data."""
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if not ble_device:
            raise UpdateFailed(
                f"TBD Smartshunt at {self.address} not found via local adapters or ESPHome Bluetooth proxies"
            )

        try:
            client = await establish_connection(
                BleakClientWithServiceCache,
                ble_device,
                self.device_name,
                max_attempts=3,
            )
            try:
                raw_bytes = await client.read_gatt_char(CHAR_STATE_OF_CHARGE)
                data = parse_state_of_charge(raw_bytes)
                if not data:
                    raise UpdateFailed(
                        f"Received invalid or truncated payload from {self.address}"
                    )
                return data
            finally:
                await client.disconnect()
        except BleakError as err:
            raise UpdateFailed(
                f"Bluetooth communication failure with {self.address}: {err}"
            ) from err
        except Exception as err:
            raise UpdateFailed(
                f"Unexpected error communicating with {self.address}: {err}"
            ) from err
