"""Binary sensor platform for Montreal Snow Removal integration."""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_DEBUT_INTERDICTION,
    ATTR_FIN_INTERDICTION,
    CONF_ADDRESSES,
    CONF_COTE_RUE_ID,
    CONF_NAME,
    CONF_SOURCE_ENTITY,
    CONF_TRACKED_VEHICLES,
    CONF_VEHICLE_NAME,
    DOMAIN,
    ICON_PARKING_BAN,
    STATE_EN_COURS,
    STATE_PLANIFIE,
    STATE_REPLANIFIE,
)
from .coordinator import SnowRemovalCoordinator
from .vehicle_entities import VehicleParkingBanSensor

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Montreal Snow Removal binary sensors from a config entry."""
    coordinator: SnowRemovalCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    addresses = hass.data[DOMAIN][entry.entry_id]["addresses"]

    # Create binary sensor for each address
    sensors = []
    for address in addresses:
        sensors.append(
            ParkingBanSensor(
                coordinator,
                address[CONF_COTE_RUE_ID],
                address[CONF_NAME],
                entry.entry_id,
            )
        )

    # Create binary sensors for tracked vehicles
    tracked_vehicles = hass.data[DOMAIN][entry.entry_id].get(CONF_TRACKED_VEHICLES, [])
    vehicle_resolvers = hass.data[DOMAIN][entry.entry_id].get("vehicle_resolvers", {})

    for vehicle in tracked_vehicles:
        vehicle_name = vehicle[CONF_VEHICLE_NAME]
        source_entity = vehicle[CONF_SOURCE_ENTITY]

        resolver = vehicle_resolvers.get(source_entity)
        if not resolver:
            _LOGGER.warning(
                "No resolver found for vehicle %s, skipping binary sensor creation",
                vehicle_name,
            )
            continue

        # Vehicle parking ban sensor
        sensors.append(
            VehicleParkingBanSensor(
                coordinator, resolver, vehicle_name, source_entity, entry.entry_id
            )
        )

        _LOGGER.debug("Created parking ban sensor for vehicle %s", vehicle_name)

    async_add_entities(sensors)


class ParkingBanSensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor for parking ban status."""

    _attr_has_entity_name = True
    _attr_translation_key = "parking_ban"

    def __init__(
        self,
        coordinator: SnowRemovalCoordinator,
        cote_rue_id: int,
        name: str,
        entry_id: str,
    ) -> None:
        """Initialize the binary sensor.

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
        self._attr_unique_id = f"{DOMAIN}_parking_ban_{cote_rue_id}"
        self._attr_name = f"Parking {name}"

        # Device info for grouping (same device as main sensor)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry_id}_{cote_rue_id}")},
            "name": f"Snow Removal - {name}",
            "manufacturer": "ludodefgh",
            "model": "Data from Ville de Montréal",
        }

    @property
    def is_on(self) -> bool:
        """Return True if parking is banned."""
        street_data = self.coordinator.get_street_data(self._cote_rue_id)

        if not street_data:
            return False

        state = street_data.get("state")
        now = datetime.now()

        # Parking is banned if:
        # 1. State is "planned" and within the planned period
        # 2. State is "in progress"
        # 3. State is "rescheduled" and within the rescheduled period

        if state == STATE_EN_COURS:
            # Always banned when work is in progress
            return True

        if state == STATE_PLANIFIE:
            # Check if we're within planned period
            date_deb = street_data.get("date_deb_planif")
            date_fin = street_data.get("date_fin_planif")

            if date_deb and date_fin:
                return self._is_within_period(now, date_deb, date_fin)

        if state == STATE_REPLANIFIE:
            # Check if we're within rescheduled period
            date_deb = street_data.get("date_deb_replanif")
            date_fin = street_data.get("date_fin_replanif")

            if date_deb and date_fin:
                return self._is_within_period(now, date_deb, date_fin)

            # If no replan dates but state is rescheduled, it might be imminent
            # Fall back to original plan dates
            date_deb = street_data.get("date_deb_planif")
            date_fin = street_data.get("date_fin_planif")

            if date_deb and date_fin:
                return self._is_within_period(now, date_deb, date_fin)

        return False


    def _is_within_period(
        self, now: datetime, start: datetime, end: datetime
    ) -> bool:
        """Check if current time is within a period.

        Args:
            now: Current datetime
            start: Period start datetime
            end: Period end datetime

        Returns:
            True if now is within [start, end]
        """
        # Handle timezone-naive vs timezone-aware comparisons
        if start.tzinfo is None and now.tzinfo is not None:
            start = start.replace(tzinfo=now.tzinfo)
        elif start.tzinfo is not None and now.tzinfo is None:
            now = now.replace(tzinfo=start.tzinfo)

        if end.tzinfo is None and now.tzinfo is not None:
            end = end.replace(tzinfo=now.tzinfo)
        elif end.tzinfo is not None and now.tzinfo is None:
            now = now.replace(tzinfo=end.tzinfo)

        return start <= now <= end

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        return ICON_PARKING_BAN

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        street_data = self.coordinator.get_street_data(self._cote_rue_id)

        if not street_data:
            return {}

        attributes = {}

        # Determine which dates to show based on state
        state = street_data.get("state")

        if state == STATE_REPLANIFIE:
            # Show rescheduled dates if available
            date_deb = street_data.get("date_deb_replanif")
            date_fin = street_data.get("date_fin_replanif")

            # Fall back to original dates if no replan dates
            if not date_deb:
                date_deb = street_data.get("date_deb_planif")
            if not date_fin:
                date_fin = street_data.get("date_fin_planif")
        else:
            # Use planned dates
            date_deb = street_data.get("date_deb_planif")
            date_fin = street_data.get("date_fin_planif")

        if date_deb:
            attributes[ATTR_DEBUT_INTERDICTION] = self._format_datetime(date_deb)
        if date_fin:
            attributes[ATTR_FIN_INTERDICTION] = self._format_datetime(date_fin)

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
