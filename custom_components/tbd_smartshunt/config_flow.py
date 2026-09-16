"""Discover TBD devices and validate read/pair/read before setup succeeds."""
from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import DOMAIN, CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL, MIN_POLL_INTERVAL, MAX_POLL_INTERVAL
from .coordinator import TbdSmartshuntCoordinator
from .transport import PairingFailed, PairingUnsupported

_LOGGER = logging.getLogger(__name__)


def is_tbd_name(name: str | None) -> bool:
    return bool(name and name.lower().startswith("tbdsmartshunt"))


class TbdSmartshuntConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._discovery_info: BluetoothServiceInfoBleak | None = None

    async def _validate(self, address: str, name: str) -> str | None:
        coordinator = TbdSmartshuntCoordinator(self.hass, address, name)
        try:
            await coordinator.async_read_data()
        except PairingUnsupported as err:
            _LOGGER.warning("Setup pairing unsupported for %s: %s", address, err)
            return "pairing_unsupported"
        except PairingFailed as err:
            _LOGGER.warning("Setup pairing failed for %s: %s", address, err)
            return "pairing_failed"
        except UpdateFailed as err:
            _LOGGER.warning("Setup read failed for %s: %s", address, err)
            return "cannot_connect"
        return None

    async def async_step_bluetooth(self, discovery_info: BluetoothServiceInfoBleak) -> FlowResult:
        if not is_tbd_name(discovery_info.name):
            return self.async_abort(reason="not_supported")
        await self.async_set_unique_id(discovery_info.address.upper())
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {"name": discovery_info.name}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        assert self._discovery_info is not None
        info = self._discovery_info
        errors = {}
        if user_input is not None:
            error = await self._validate(info.address, info.name or "TBD Smartshunt")
            if error is None:
                return self.async_create_entry(title=info.name or "TBD Smartshunt", data={
                    CONF_ADDRESS: info.address.upper(), CONF_NAME: info.name or "TBD Smartshunt",
                    CONF_POLL_INTERVAL: DEFAULT_POLL_INTERVAL,
                })
            errors["base"] = error
        self._set_confirm_only()
        return self.async_show_form(step_id="bluetooth_confirm", errors=errors,
                                   description_placeholders={"name": info.name or info.address})

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors = {}
        if user_input is not None:
            address = user_input[CONF_ADDRESS].strip().upper()
            if re.fullmatch(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}", address) is None:
                errors[CONF_ADDRESS] = "invalid_address"
            else:
                await self.async_set_unique_id(address)
                self._abort_if_unique_id_configured()
                name = user_input.get(CONF_NAME) or f"TBD Smartshunt {address[-5:]}"
                error = await self._validate(address, name)
                if error is None:
                    return self.async_create_entry(title=name, data={
                        CONF_ADDRESS: address, CONF_NAME: name,
                        CONF_POLL_INTERVAL: user_input.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
                    })
                errors["base"] = error
        candidates = [info.address for info in bluetooth.async_discovered_service_info(self.hass, connectable=True)
                      if is_tbd_name(info.name) and info.address not in self._async_current_ids()]
        defaults = user_input or {}
        schema = vol.Schema({
            vol.Required(CONF_ADDRESS, default=defaults.get(CONF_ADDRESS, candidates[0] if candidates else "")): str,
            vol.Optional(CONF_NAME, default=defaults.get(CONF_NAME, "TBD Smartshunt")): str,
            vol.Optional(CONF_POLL_INTERVAL, default=defaults.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)):
                vol.All(vol.Coerce(int), vol.Range(min=MIN_POLL_INTERVAL, max=MAX_POLL_INTERVAL)),
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
