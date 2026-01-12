"""Device tracker platform for Montreal Snow Removal integration.

This creates device tracker entities that can be displayed on the Home Assistant map.
Each entity represents a tracked street with its GPS coordinates.
"""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ADDRESSES,
    CONF_COTE_RUE_ID,
    CONF_NAME,
    DOMAIN,
    ICON_MAP,
    STATE_DEGAGE,
    STATE_DENEIGE,
    STATE_EN_COURS,
    STATE_ENNEIGE,
    STATE_PLANIFIE,
    STATE_REPLANIFIE,
)
from .coordinator import SnowRemovalCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Montreal Snow Removal device trackers from a config entry."""
    coordinator: SnowRemovalCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    addresses = hass.data[DOMAIN][entry.entry_id]["addresses"]

    # Only create trackers if GeoJSON is loaded
    if not coordinator.geojson_handler.is_loaded:
        _LOGGER.info("GeoJSON not loaded, skipping device tracker creation")
        return

    # Create device tracker for each address
    trackers = []
    for address in addresses:
        cote_rue_id = address[CONF_COTE_RUE_ID]

        # Check if we have coordinates for this street
        coords = coordinator.geojson_handler.get_center_coordinates(cote_rue_id)
        if coords:
            trackers.append(
                SnowRemovalTracker(
                    coordinator,
                    cote_rue_id,
                    address[CONF_NAME],
                    entry.entry_id,
                )
            )
        else:
            _LOGGER.debug(
                "No GPS coordinates available for COTE_RUE_ID %d, skipping tracker",
                cote_rue_id,
            )

    if trackers:
        async_add_entities(trackers)
        _LOGGER.info("Created %d device trackers for map display", len(trackers))


class SnowRemovalTracker(CoordinatorEntity, TrackerEntity):
    """Device tracker for snow removal street location."""

    _attr_has_entity_name = True
    _attr_translation_key = "street_location"

    def __init__(
        self,
        coordinator: SnowRemovalCoordinator,
        cote_rue_id: int,
        name: str,
        entry_id: str,
    ) -> None:
        """Initialize the device tracker.

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
        self._attr_unique_id = f"{DOMAIN}_tracker_{cote_rue_id}"
        self._attr_name = f"Map {name}"

        # Device info for grouping (same device as sensors)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry_id}_{cote_rue_id}")},
            "name": f"Snow Removal - {name}",
            "manufacturer": "ludodefgh",
            "model": "Data from Ville de Montréal",
        }

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        street_data = self.coordinator.get_street_data(self._cote_rue_id)
        if not street_data:
            return None
        return street_data.get("latitude")

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        street_data = self.coordinator.get_street_data(self._cote_rue_id)
        if not street_data:
            return None
        return street_data.get("longitude")

    @property
    def source_type(self) -> SourceType:
        """Return the source type."""
        return SourceType.GPS

    @property
    def icon(self) -> str:
        """Return the icon based on snow removal state."""
        street_data = self.coordinator.get_street_data(self._cote_rue_id)
        if not street_data:
            return "mdi:snowflake"

        state = street_data.get("state", STATE_ENNEIGE)
        return ICON_MAP.get(state, "mdi:snowflake")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes for map display."""
        street_data = self.coordinator.get_street_data(self._cote_rue_id)

        if not street_data:
            return {}

        attributes = {
            "cote_rue_id": self._cote_rue_id,
            "snow_removal_state": street_data.get("state"),
        }

        # Add street info
        if street_data.get("nom_voie"):
            type_voie = street_data.get("type_voie", "")
            nom_voie = street_data.get("nom_voie", "")
            attributes["street_name"] = f"{type_voie} {nom_voie}".strip()

        if street_data.get("cote"):
            attributes["street_side"] = street_data.get("cote")

        # Add planning dates
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
            attributes["start_time"] = self._format_datetime(date_deb)
        if date_fin:
            attributes["end_time"] = self._format_datetime(date_fin)

        # Add visual color hint for map display
        attributes["marker_color"] = self._get_marker_color(state)

        # Add full street geometry for advanced map displays
        geometry = self.coordinator.geojson_handler.get_geometry(self._cote_rue_id)
        if geometry:
            # Add GeoJSON-compatible geometry
            attributes["gps_accuracy"] = 0  # Street segment, not a point
            attributes["geometry_type"] = geometry.get("geometry_type")

            # Store coordinates for custom cards
            coordinates = geometry.get("coordinates", [])
            if coordinates:
                # Convert to list of [lat, lon] pairs for easier consumption
                attributes["street_coordinates"] = [
                    [coord[1], coord[0]]  # GeoJSON is [lon, lat], flip to [lat, lon]
                    for coord in coordinates
                    if len(coord) >= 2
                ]
                attributes["coordinate_count"] = len(attributes["street_coordinates"])

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

    def _get_marker_color(self, state: str | None) -> str:
        """Get marker color for map display based on state.

        Args:
            state: Snow removal state

        Returns:
            Color name for map marker
        """
        color_map = {
            STATE_PLANIFIE: "red",  # Planned
            STATE_EN_COURS: "yellow",  # In progress
            STATE_DENEIGE: "green",  # Completed
            STATE_DEGAGE: "gray",  # Clear
            STATE_REPLANIFIE: "orange",  # Rescheduled
            STATE_ENNEIGE: "blue",  # Snowy/not yet planned
        }
        return color_map.get(state, "blue")
