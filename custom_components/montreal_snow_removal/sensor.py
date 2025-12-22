"""Sensor platform for Montreal Snow Removal integration."""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_ADRESSE_DEBUT,
    ATTR_ADRESSE_FIN,
    ATTR_COTE,
    ATTR_COTE_RUE_ID,
    ATTR_DATE_DEBUT_PLANIF,
    ATTR_DATE_DEBUT_REPLANIF,
    ATTR_DATE_FIN_PLANIF,
    ATTR_DATE_FIN_REPLANIF,
    ATTR_DERNIERE_MAJ,
    ATTR_HEURES_AVANT_DEBUT,
    ATTR_NOM_VOIE,
    ATTR_TYPE_VOIE,
    CONF_ADDRESSES,
    CONF_COTE_RUE_ID,
    CONF_NAME,
    DOMAIN,
    ICON_MAP,
    STATE_DEGAGE,
)
from .coordinator import SnowRemovalCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Montreal Snow Removal sensors from a config entry."""
    coordinator: SnowRemovalCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    addresses = hass.data[DOMAIN][entry.entry_id]["addresses"]

    # Create sensor for each address
    sensors = []
    for address in addresses:
        sensors.append(
            SnowRemovalSensor(
                coordinator,
                address[CONF_COTE_RUE_ID],
                address[CONF_NAME],
                entry.entry_id,
            )
        )

    async_add_entities(sensors)


class SnowRemovalSensor(CoordinatorEntity, SensorEntity):
    """Sensor for snow removal status."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SnowRemovalCoordinator,
        cote_rue_id: int,
        name: str,
        entry_id: str,
    ) -> None:
        """Initialize the sensor.

        Args:
            coordinator: Data update coordinator
            cote_rue_id: Street side ID to track
            name: User-friendly name for the address
            entry_id: Config entry ID
        """
        super().__init__(coordinator)

        self._cote_rue_id = cote_rue_id
        self._name = name
        self._entry_id = entry_id

        # Entity IDs and unique ID
        self._attr_unique_id = f"{DOMAIN}_{cote_rue_id}"
        self._attr_name = f"Snow Removal {name}"

        # Device info for grouping
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry_id}_{cote_rue_id}")},
            "name": f"Snow Removal - {name}",
            "manufacturer": "ludodefgh",
            "model": "Data from Ville de Montréal",
        }

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        street_data = self.coordinator.get_street_data(self._cote_rue_id)

        if not street_data:
            return STATE_DEGAGE  # Default to "clear" if no data

        return street_data.get("state")

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        state = self.native_value
        return ICON_MAP.get(state, "mdi:snowflake")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        street_data = self.coordinator.get_street_data(self._cote_rue_id)

        if not street_data:
            return {
                ATTR_COTE_RUE_ID: self._cote_rue_id,
            }

        attributes = {
            ATTR_COTE_RUE_ID: self._cote_rue_id,
        }

        # Add street info
        if street_data.get("nom_voie"):
            attributes[ATTR_NOM_VOIE] = street_data["nom_voie"]
        if street_data.get("type_voie"):
            attributes[ATTR_TYPE_VOIE] = street_data["type_voie"]
        if street_data.get("debut_adresse"):
            attributes[ATTR_ADRESSE_DEBUT] = street_data["debut_adresse"]
        if street_data.get("fin_adresse"):
            attributes[ATTR_ADRESSE_FIN] = street_data["fin_adresse"]
        if street_data.get("cote"):
            attributes[ATTR_COTE] = street_data["cote"]

        # Add dates
        if street_data.get("date_deb_planif"):
            attributes[ATTR_DATE_DEBUT_PLANIF] = self._format_datetime(
                street_data["date_deb_planif"]
            )
        if street_data.get("date_fin_planif"):
            attributes[ATTR_DATE_FIN_PLANIF] = self._format_datetime(
                street_data["date_fin_planif"]
            )
        if street_data.get("date_deb_replanif"):
            attributes[ATTR_DATE_DEBUT_REPLANIF] = self._format_datetime(
                street_data["date_deb_replanif"]
            )
        if street_data.get("date_fin_replanif"):
            attributes[ATTR_DATE_FIN_REPLANIF] = self._format_datetime(
                street_data["date_fin_replanif"]
            )
        if street_data.get("date_maj"):
            attributes[ATTR_DERNIERE_MAJ] = self._format_datetime(
                street_data["date_maj"]
            )

        # Add hours before start if available
        hours_before = street_data.get("heures_avant_debut")
        if hours_before is not None:
            attributes[ATTR_HEURES_AVANT_DEBUT] = round(hours_before, 1)

        return attributes

    def _format_datetime(self, dt: datetime | None) -> str | None:
        """Format datetime for display.

        Args:
            dt: Datetime object

        Returns:
            ISO formatted string or None
        """
        if not dt:
            return None

        return dt.isoformat()
