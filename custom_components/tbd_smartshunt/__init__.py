"""The TBD Smartshunt Bluetooth integration."""

from __future__ import annotations

import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
from .coordinator import TbdSmartshuntCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TBD Smartshunt from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    address: str = entry.data[CONF_ADDRESS]
    name: str = entry.data.get(CONF_NAME, "TBD Smartshunt")
    poll_interval: int = entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)

    coordinator = TbdSmartshuntCoordinator(
        hass=hass,
        address=address,
        name=name,
        poll_interval=poll_interval,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        address = entry.data.get(CONF_ADDRESS)
        if address and "_pairing_readers" in hass.data.get(DOMAIN, {}):
            hass.data[DOMAIN]["_pairing_readers"].pop(address, None)

    return unload_ok
