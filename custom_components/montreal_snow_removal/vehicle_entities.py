"""Vehicle-based entities for Montreal Snow Removal integration."""
from __future__ import annotations

from datetime import datetime
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_COTE_RUE_ID,
    ATTR_CURRENT_STREET,
    ATTR_DEBUT_INTERDICTION,
    ATTR_FIN_INTERDICTION,
    ATTR_LAST_RESOLUTION,
    ATTR_RESOLUTION_METHOD,
    ATTR_SOURCE_AVAILABLE,
    ATTR_SOURCE_ENTITY,
    ATTR_STREET_SIDE,
    CONF_SOURCE_ENTITY,
    CONF_TRACKED_VEHICLES,
    CONF_VEHICLE_NAME,
    DOMAIN,
    ICON_MAP,
    ICON_PARKING_BAN,
    STATE_DEGAGE,
    STATE_DENEIGE,
    STATE_EN_COURS,
    STATE_ENNEIGE,
    STATE_OUTSIDE_COVERAGE,
    STATE_PLANIFIE,
    STATE_REPLANIFIE,
    STATE_SERA_REPLANIFIE,
    STATE_SOURCE_UNAVAILABLE,
    STATE_STATIONNEMENT_INTERDIT,
)

if TYPE_CHECKING:
    from .coordinator import SnowRemovalCoordinator
    from .vehicle_resolver import VehicleAddressResolver

_LOGGER = logging.getLogger(__name__)


def _sanitize_entity_id(source_entity: str) -> str:
    """Sanitize source entity ID for use in unique_id.

    Replaces dots and other special characters with underscores.
    """
    return source_entity.replace(".", "_").replace("-", "_")


class VehicleEntityMixin:
    """Mixin for vehicle-based entities."""

    _resolver: VehicleAddressResolver
    _vehicle_name: str
    _source_entity_id: str
    _entry_id: str
    coordinator: SnowRemovalCoordinator

    def _get_street_data(self) -> dict[str, Any] | None:
        """Get current street data from resolver."""
        cote_rue_id = self._resolver.current_cote_rue_id
        if cote_rue_id is None:
            return None
        return self.coordinator.get_street_data(cote_rue_id)

    def _get_vehicle_attributes(self) -> dict[str, Any]:
        """Get common vehicle attributes."""
        attributes = {
            ATTR_SOURCE_ENTITY: self._source_entity_id,
            ATTR_SOURCE_AVAILABLE: self._resolver.source_available,
        }

        if self._resolver.current_street_name:
            attributes[ATTR_CURRENT_STREET] = self._resolver.current_street_name

        if self._resolver.current_cote_rue_id:
            attributes[ATTR_COTE_RUE_ID] = self._resolver.current_cote_rue_id

        if self._resolver.current_street_side:
            attributes[ATTR_STREET_SIDE] = self._resolver.current_street_side

        if self._resolver.last_resolution:
            attributes[ATTR_LAST_RESOLUTION] = (
                self._resolver.last_resolution.isoformat()
            )

        if self._resolver.resolution_method:
            attributes[ATTR_RESOLUTION_METHOD] = self._resolver.resolution_method

        return attributes

    def _is_within_period(
        self, now: datetime, start: datetime, end: datetime
    ) -> bool:
        """Check if current time is within a period."""
        if start.tzinfo is None and now.tzinfo is not None:
            start = start.replace(tzinfo=now.tzinfo)
        elif start.tzinfo is not None and now.tzinfo is None:
            now = now.replace(tzinfo=start.tzinfo)

        if end.tzinfo is None and now.tzinfo is not None:
            end = end.replace(tzinfo=now.tzinfo)
        elif end.tzinfo is not None and now.tzinfo is None:
            now = now.replace(tzinfo=end.tzinfo)

        return start <= now <= end

    def _format_datetime(self, dt: datetime | None) -> str | None:
        """Format datetime for display."""
        if not dt:
            return None
        return dt.isoformat()

    def _get_marker_color(self, state: str | None) -> str:
        """Get marker color for map display based on state."""
        color_map = {
            STATE_STATIONNEMENT_INTERDIT: "red",
            STATE_PLANIFIE: "orange",
            STATE_REPLANIFIE: "orange",
            STATE_SERA_REPLANIFIE: "yellow",
            STATE_EN_COURS: "purple",
            STATE_DENEIGE: "green",
            STATE_DEGAGE: "gray",
            STATE_ENNEIGE: "blue",
        }
        return color_map.get(state, "blue")

    def _get_derived_state(self, street_data: dict[str, Any]) -> str:
        """Get the derived state including parking ban logic."""
        return self.coordinator.derive_state_with_parking_ban(
            etat_code=street_data.get("etat_code", 0),
            date_deb_planif=street_data.get("date_deb_planif"),
            date_fin_planif=street_data.get("date_fin_planif"),
            date_deb_replanif=street_data.get("date_deb_replanif"),
            date_fin_replanif=street_data.get("date_fin_replanif"),
        )

    def _get_street_coordinates(self) -> list[list[float]] | None:
        """Get street coordinates for map display."""
        cote_rue_id = self._resolver.current_cote_rue_id
        if cote_rue_id is None:
            return None

        geometry = self.coordinator.geojson_handler.get_geometry(cote_rue_id)
        if not geometry:
            return None

        coordinates = geometry.get("coordinates", [])
        if not coordinates:
            return None

        # Convert to list of [lat, lon] pairs (flip from GeoJSON [lon, lat])
        return [
            [coord[1], coord[0]]
            for coord in coordinates
            if len(coord) >= 2
        ]


class VehicleParkingBanSensor(VehicleEntityMixin, CoordinatorEntity, BinarySensorEntity):
    """Binary sensor for vehicle parking ban status."""

    _attr_has_entity_name = True
    _attr_translation_key = "vehicle_parking_ban"

    def __init__(
        self,
        coordinator: SnowRemovalCoordinator,
        resolver: VehicleAddressResolver,
        vehicle_name: str,
        source_entity_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the vehicle parking ban sensor."""
        super().__init__(coordinator)

        self._resolver = resolver
        self._vehicle_name = vehicle_name
        self._source_entity_id = source_entity_id
        self._entry_id = entry_id

        # Stable unique ID based on source entity
        sanitized_id = _sanitize_entity_id(source_entity_id)
        self._attr_unique_id = f"{DOMAIN}_vehicle_{sanitized_id}_parking_ban"
        self._attr_name = f"Parking {vehicle_name}"

        # Device info - groups all vehicle entities together
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"vehicle_{sanitized_id}")},
            "name": f"Snow Removal - {vehicle_name}",
            "manufacturer": "ludodefgh",
            "model": "Vehicle Tracker",
        }

    @property
    def is_on(self) -> bool | None:
        """Return True if parking is banned at current location."""
        if not self._resolver.source_available:
            return None

        if not self._resolver.is_resolved:
            return None  # Outside coverage or not resolved

        street_data = self._get_street_data()
        if not street_data:
            return False

        state = street_data.get("state")
        now = datetime.now()

        if state == STATE_EN_COURS:
            return True

        if state == STATE_PLANIFIE:
            date_deb = street_data.get("date_deb_planif")
            date_fin = street_data.get("date_fin_planif")
            if date_deb and date_fin:
                return self._is_within_period(now, date_deb, date_fin)

        if state == STATE_REPLANIFIE:
            date_deb = street_data.get("date_deb_replanif")
            date_fin = street_data.get("date_fin_replanif")
            if date_deb and date_fin:
                return self._is_within_period(now, date_deb, date_fin)

            date_deb = street_data.get("date_deb_planif")
            date_fin = street_data.get("date_fin_planif")
            if date_deb and date_fin:
                return self._is_within_period(now, date_deb, date_fin)

        return False

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        return ICON_PARKING_BAN

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attributes = self._get_vehicle_attributes()

        street_data = self._get_street_data()
        if not street_data:
            return attributes

        state = street_data.get("state")

        if state == STATE_REPLANIFIE:
            date_deb = street_data.get("date_deb_replanif")
            date_fin = street_data.get("date_fin_replanif")
            if not date_deb:
                date_deb = street_data.get("date_deb_planif")
            if not date_fin:
                date_fin = street_data.get("date_fin_planif")
        else:
            date_deb = street_data.get("date_deb_planif")
            date_fin = street_data.get("date_fin_planif")

        if date_deb:
            attributes[ATTR_DEBUT_INTERDICTION] = self._format_datetime(date_deb)
        if date_fin:
            attributes[ATTR_FIN_INTERDICTION] = self._format_datetime(date_fin)

        return attributes


class VehicleStatusSensor(VehicleEntityMixin, CoordinatorEntity, SensorEntity):
    """Sensor for vehicle snow removal status."""

    _attr_has_entity_name = True
    _attr_translation_key = "vehicle_status"

    def __init__(
        self,
        coordinator: SnowRemovalCoordinator,
        resolver: VehicleAddressResolver,
        vehicle_name: str,
        source_entity_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the vehicle status sensor."""
        super().__init__(coordinator)

        self._resolver = resolver
        self._vehicle_name = vehicle_name
        self._source_entity_id = source_entity_id
        self._entry_id = entry_id

        sanitized_id = _sanitize_entity_id(source_entity_id)
        self._attr_unique_id = f"{DOMAIN}_vehicle_{sanitized_id}_status"
        self._attr_name = f"Snow Removal {vehicle_name}"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"vehicle_{sanitized_id}")},
            "name": f"Snow Removal - {vehicle_name}",
            "manufacturer": "ludodefgh",
            "model": "Vehicle Tracker",
        }

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if not self._resolver.source_available:
            return STATE_SOURCE_UNAVAILABLE

        if not self._resolver.is_resolved:
            return STATE_OUTSIDE_COVERAGE

        street_data = self._get_street_data()
        if not street_data:
            return STATE_OUTSIDE_COVERAGE

        return street_data.get("state")

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        state = self.native_value
        if state in (STATE_OUTSIDE_COVERAGE, STATE_SOURCE_UNAVAILABLE):
            return "mdi:map-marker-question"
        return ICON_MAP.get(state, "mdi:snowflake")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attributes = self._get_vehicle_attributes()

        street_data = self._get_street_data()
        if not street_data:
            return attributes

        # Add street info for map display
        street_name_parts = []
        if street_data.get("type_voie"):
            street_name_parts.append(street_data["type_voie"])
        if street_data.get("nom_voie"):
            street_name_parts.append(street_data["nom_voie"])
        if street_name_parts:
            attributes["street_name"] = " ".join(street_name_parts)

        # Add derived state and marker color for map
        derived_state = self._get_derived_state(street_data)
        attributes["snow_removal_state"] = derived_state
        attributes["marker_color"] = self._get_marker_color(derived_state)

        # Add street coordinates for map display
        street_coordinates = self._get_street_coordinates()
        if street_coordinates:
            attributes["street_coordinates"] = street_coordinates
            attributes["coordinate_count"] = len(street_coordinates)

        # Add planning dates with start_time/end_time format for map popup
        if street_data.get("state") == STATE_REPLANIFIE:
            date_deb = street_data.get("date_deb_replanif")
            date_fin = street_data.get("date_fin_replanif")
            if not date_deb:
                date_deb = street_data.get("date_deb_planif")
            if not date_fin:
                date_fin = street_data.get("date_fin_planif")
        else:
            date_deb = street_data.get("date_deb_planif")
            date_fin = street_data.get("date_fin_planif")

        if date_deb:
            attributes["start_time"] = self._format_datetime(date_deb)
            attributes["date_debut_planif"] = attributes["start_time"]
        if date_fin:
            attributes["end_time"] = self._format_datetime(date_fin)
            attributes["date_fin_planif"] = attributes["end_time"]

        # Keep replanif dates if different
        if street_data.get("date_deb_replanif"):
            attributes["date_debut_replanif"] = self._format_datetime(
                street_data["date_deb_replanif"]
            )
        if street_data.get("date_fin_replanif"):
            attributes["date_fin_replanif"] = self._format_datetime(
                street_data["date_fin_replanif"]
            )

        return attributes


class VehicleNextOperationSensor(VehicleEntityMixin, CoordinatorEntity, SensorEntity):
    """Sensor showing next snow removal operation for vehicle location."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SnowRemovalCoordinator,
        resolver: VehicleAddressResolver,
        vehicle_name: str,
        source_entity_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._resolver = resolver
        self._vehicle_name = vehicle_name
        self._source_entity_id = source_entity_id
        self._entry_id = entry_id

        sanitized_id = _sanitize_entity_id(source_entity_id)
        self._attr_unique_id = f"{DOMAIN}_vehicle_{sanitized_id}_next_operation"
        self._attr_name = f"Next Operation {vehicle_name}"
        self._attr_icon = "mdi:clock-outline"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"vehicle_{sanitized_id}")},
            "name": f"Snow Removal - {vehicle_name}",
            "manufacturer": "ludodefgh",
            "model": "Vehicle Tracker",
        }

    @property
    def native_value(self) -> str | None:
        """Return the time until next operation."""
        if not self._resolver.source_available:
            return None

        if not self._resolver.is_resolved:
            return None

        street_data = self._get_street_data()
        if not street_data:
            return None

        state = street_data.get("state")

        if state == "en_cours":
            return "En cours"

        now = datetime.now()

        # Check replanified dates
        date_deb_replanif = street_data.get("date_deb_replanif")
        date_fin_replanif = street_data.get("date_fin_replanif")

        if date_deb_replanif and date_fin_replanif:
            if self._is_within_period(now, date_deb_replanif, date_fin_replanif):
                return "En cours"

        # Check planned dates
        date_deb_planif = street_data.get("date_deb_planif")
        date_fin_planif = street_data.get("date_fin_planif")

        if date_deb_planif and date_fin_planif:
            if self._is_within_period(now, date_deb_planif, date_fin_planif):
                return "En cours"

        # Calculate hours before start
        heures_avant = street_data.get("heures_avant_debut")

        if heures_avant is not None and heures_avant > 0:
            hours = int(heures_avant)
            if hours < 24:
                return f"{hours}h"
            else:
                days = hours // 24
                remaining_hours = hours % 24
                if remaining_hours > 0:
                    return f"{days}j {remaining_hours}h"
                return f"{days}j"

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attributes = self._get_vehicle_attributes()

        street_data = self._get_street_data()
        if not street_data:
            return attributes

        date_deb = street_data.get("date_deb_planif") or street_data.get(
            "date_deb_replanif"
        )
        date_fin = street_data.get("date_fin_planif") or street_data.get(
            "date_fin_replanif"
        )

        if date_deb:
            attributes["start_time"] = self._format_datetime(date_deb)
        if date_fin:
            attributes["end_time"] = self._format_datetime(date_fin)

        return attributes


async def async_setup_vehicle_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: SnowRemovalCoordinator,
    resolvers: dict[str, VehicleAddressResolver],
    async_add_sensors: AddEntitiesCallback,
    async_add_binary_sensors: AddEntitiesCallback,
) -> None:
    """Set up vehicle entities.

    Args:
        hass: Home Assistant instance
        entry: Config entry
        coordinator: Data coordinator
        resolvers: Dict mapping source_entity_id to VehicleAddressResolver
        async_add_sensors: Callback to add sensor entities
        async_add_binary_sensors: Callback to add binary sensor entities
    """
    vehicles = entry.data.get(CONF_TRACKED_VEHICLES, [])

    sensors = []
    binary_sensors = []

    for vehicle in vehicles:
        vehicle_name = vehicle[CONF_VEHICLE_NAME]
        source_entity_id = vehicle[CONF_SOURCE_ENTITY]

        resolver = resolvers.get(source_entity_id)
        if not resolver:
            _LOGGER.warning(
                "No resolver found for vehicle %s (source: %s)",
                vehicle_name,
                source_entity_id,
            )
            continue

        # Create sensors
        sensors.append(
            VehicleStatusSensor(
                coordinator,
                resolver,
                vehicle_name,
                source_entity_id,
                entry.entry_id,
            )
        )
        sensors.append(
            VehicleNextOperationSensor(
                coordinator,
                resolver,
                vehicle_name,
                source_entity_id,
                entry.entry_id,
            )
        )

        # Create binary sensor
        binary_sensors.append(
            VehicleParkingBanSensor(
                coordinator,
                resolver,
                vehicle_name,
                source_entity_id,
                entry.entry_id,
            )
        )

        _LOGGER.debug(
            "Created entities for vehicle %s (source: %s)",
            vehicle_name,
            source_entity_id,
        )

    if sensors:
        async_add_sensors(sensors)
    if binary_sensors:
        async_add_binary_sensors(binary_sensors)
