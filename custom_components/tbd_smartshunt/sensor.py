"""Support for TBD Smartshunt sensors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfElectricCurrent,
    UnitOfPower,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TbdSmartshuntCoordinator
from .parser import ShuntData


@dataclass(frozen=True, kw_only=True)
class TbdShuntSensorEntityDescription(SensorEntityDescription):
    """Class describing TBD Smartshunt sensor entities."""
    value_fn: Callable[[ShuntData], Any]


SENSOR_TYPES: tuple[TbdShuntSensorEntityDescription, ...] = (
    TbdShuntSensorEntityDescription(
        key="soc",
        name="Reported State of Charge",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: data.soc,
    ),
    TbdShuntSensorEntityDescription(
        key="voltage",
        name="Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        value_fn=lambda data: data.voltage,
    ),
    TbdShuntSensorEntityDescription(
        key="current",
        name="Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        value_fn=lambda data: data.current,
    ),
    TbdShuntSensorEntityDescription(
        key="power",
        name="Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=1,
        value_fn=lambda data: data.power,
    ),

)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TBD Smartshunt sensors from a config entry."""
    coordinator: TbdSmartshuntCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        TbdShuntSensor(coordinator, entry, description)
        for description in SENSOR_TYPES
    ]

    async_add_entities(entities)


class TbdShuntSensor(CoordinatorEntity[TbdSmartshuntCoordinator], SensorEntity):
    """Representation of a TBD Smartshunt sensor."""

    entity_description: TbdShuntSensorEntityDescription

    def __init__(
        self,
        coordinator: TbdSmartshuntCoordinator,
        entry: ConfigEntry,
        description: TbdShuntSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.address}_{description.key}"
        self._attr_has_entity_name = True

        device_name = entry.data.get(CONF_NAME, f"TBD Smartshunt {coordinator.address}")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
            name=device_name,
            manufacturer="DaYan Co.LTD",
            model="DA1",
        )

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
