"""Config flow for the TBD Smartshunt integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    SERVICE_UUID,
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    MIN_POLL_INTERVAL,
    MAX_POLL_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class TbdSmartshuntConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TBD Smartshunt."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, str] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle discovery via Bluetooth / ESPHome proxy."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info
        device_name = discovery_info.name or f"TBD Smartshunt ({discovery_info.address})"
        self.context["title_placeholders"] = {"name": device_name}

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery of a TBD Smartshunt."""
        assert self._discovery_info is not None

        if user_input is not None:
            return self.async_create_entry(
                title=self._discovery_info.name or f"TBD Smartshunt ({self._discovery_info.address})",
                data={
                    CONF_ADDRESS: self._discovery_info.address,
                    CONF_NAME: self._discovery_info.name or "TBD Smartshunt",
                    CONF_POLL_INTERVAL: DEFAULT_POLL_INTERVAL,
                },
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={
                "name": self._discovery_info.name or self._discovery_info.address
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual setup or selecting from discovered devices."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS].strip().upper()
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            device_name = user_input.get(CONF_NAME) or f"TBD Smartshunt {address[-5:].replace(':', '')}"

            return self.async_create_entry(
                title=device_name,
                data={
                    CONF_ADDRESS: address,
                    CONF_NAME: device_name,
                    CONF_POLL_INTERVAL: user_input.get(
                        CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
                    ),
                },
            )

        current_addresses = self._async_current_ids()
        for service_info in bluetooth.async_discovered_service_info(self.hass, connectable=True):
            if (
                service_info.address not in current_addresses
                and (
                    (service_info.name and service_info.name.startswith("TBDsmartshunt"))
                    or SERVICE_UUID.lower() in [u.lower() for u in service_info.service_uuids]
                )
            ):
                label = f"{service_info.name} ({service_info.address})"
                self._discovered_devices[service_info.address] = label

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_ADDRESS,
                    default=list(self._discovered_devices.keys())[0]
                    if self._discovered_devices
                    else "",
                ): (
                    vol.In(self._discovered_devices)
                    if self._discovered_devices
                    else str
                ),
                vol.Optional(CONF_NAME, default="TBD Smartshunt"): str,
                vol.Optional(
                    CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_POLL_INTERVAL, max=MAX_POLL_INTERVAL),
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )
