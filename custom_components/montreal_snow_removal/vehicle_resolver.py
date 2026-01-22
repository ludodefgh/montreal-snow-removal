"""Vehicle address resolver for dynamic location tracking."""
from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable

from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.event import async_track_state_change_event

from .address_parser import AddressParser
from .const import KNOWN_ADDRESS_ATTRIBUTES

if TYPE_CHECKING:
    from .api.geobase import GeobaseHandler
    from .api.geojson_handler import GeoJSONHandler

_LOGGER = logging.getLogger(__name__)

# Montreal approximate bounding box
MONTREAL_BOUNDS = {
    "min_lat": 45.40,
    "max_lat": 45.70,
    "min_lon": -73.98,
    "max_lon": -73.47,
}

# Minimum distance change to trigger re-resolution (meters)
MIN_DISTANCE_THRESHOLD = 5


class VehicleAddressResolver:
    """Resolves vehicle location to Montreal street COTE_RUE_ID."""

    def __init__(
        self,
        hass: HomeAssistant,
        vehicle_name: str,
        source_entity_id: str,
        geobase: GeobaseHandler,
        geojson: GeoJSONHandler | None,
        on_street_change: Callable[[int | None, int | None], None] | None = None,
    ) -> None:
        """Initialize vehicle resolver.

        Args:
            hass: Home Assistant instance
            vehicle_name: User-friendly name for the vehicle
            source_entity_id: Entity ID of the device_tracker or sensor to follow
            geobase: GeobaseHandler for address resolution
            geojson: GeoJSONHandler for GPS reverse geocoding (optional)
            on_street_change: Callback when street changes (old_id, new_id)
        """
        self.hass = hass
        self.vehicle_name = vehicle_name
        self.source_entity_id = source_entity_id
        self._geobase = geobase
        self._geojson = geojson
        self._on_street_change = on_street_change

        # Current state
        self._current_cote_rue_id: int | None = None
        self._current_street_name: str | None = None
        self._current_street_side: str | None = None
        self._last_resolution: datetime | None = None
        self._resolution_method: str | None = None
        self._source_available: bool = False
        self._last_latitude: float | None = None
        self._last_longitude: float | None = None

        # Unsubscribe callback
        self._unsub_state_change: Callable[[], None] | None = None

    async def async_start(self) -> None:
        """Start listening to source entity changes."""
        # Perform initial resolution
        state = self.hass.states.get(self.source_entity_id)
        if state:
            await self._async_resolve_from_state(state)

        # Subscribe to state changes
        self._unsub_state_change = async_track_state_change_event(
            self.hass,
            [self.source_entity_id],
            self._async_on_state_change,
        )
        _LOGGER.debug(
            "Started tracking %s for vehicle %s",
            self.source_entity_id,
            self.vehicle_name,
        )

    async def async_stop(self) -> None:
        """Stop listening to source entity changes."""
        if self._unsub_state_change:
            self._unsub_state_change()
            self._unsub_state_change = None
        _LOGGER.debug("Stopped tracking for vehicle %s", self.vehicle_name)

    @callback
    def _async_on_state_change(self, event) -> None:
        """Handle state change event."""
        new_state = event.data.get("new_state")
        if new_state is None:
            self._source_available = False
            return

        # Schedule async resolution
        self.hass.async_create_task(self._async_resolve_from_state(new_state))

    async def _async_resolve_from_state(self, state: State) -> None:
        """Resolve address from entity state.

        Uses auto-detect strategy:
        1. Try known address attributes first
        2. Fall back to GPS reverse geocoding
        """
        if state.state in ("unavailable", "unknown"):
            self._source_available = False
            _LOGGER.debug(
                "Source entity %s is %s", self.source_entity_id, state.state
            )
            return

        self._source_available = True
        attributes = state.attributes

        # Strategy 1: Try address attributes
        address = self._extract_address_from_attributes(attributes)
        if address:
            await self._async_resolve_from_address(address)
            return

        # Strategy 2: Try GPS coordinates
        latitude = attributes.get("latitude")
        longitude = attributes.get("longitude")

        if latitude is not None and longitude is not None:
            await self._async_resolve_from_gps(float(latitude), float(longitude))
            return

        _LOGGER.warning(
            "Cannot resolve location for %s: no address attributes or GPS coordinates",
            self.source_entity_id,
        )

    def _extract_address_from_attributes(
        self, attributes: dict[str, Any]
    ) -> str | None:
        """Extract address from known attributes.

        Args:
            attributes: Entity attributes

        Returns:
            Address string or None
        """
        for attr_name in KNOWN_ADDRESS_ATTRIBUTES:
            value = attributes.get(attr_name)
            if value and isinstance(value, str) and value.strip():
                _LOGGER.debug(
                    "Found address in attribute '%s': %s", attr_name, value
                )
                return value.strip()
        return None

    async def _async_resolve_from_address(self, address: str) -> None:
        """Resolve COTE_RUE_ID from address string.

        Args:
            address: Full or partial address string
        """
        _LOGGER.debug("Resolving address: %s", address)

        # Parse address
        parsed = AddressParser.parse_address(address)
        if not parsed or not parsed.get("street_name"):
            _LOGGER.warning("Could not parse address: %s", address)
            self._update_resolution(None, None, "address_attribute")
            return

        # Search geobase
        matches = self._geobase.search_address(
            parsed.get("street_number"),
            parsed["street_name"],
        )

        if not matches:
            _LOGGER.debug("No geobase matches for: %s", address)
            self._update_resolution(None, None, "address_attribute")
            return

        # Use best match
        best_match = matches[0]
        cote_rue_id = best_match["cote_rue_id"]
        street_info = best_match.get("info", {})
        street_name = self._format_street_name(street_info)

        _LOGGER.info(
            "Resolved %s to %s (COTE_RUE_ID: %d)",
            address,
            street_name,
            cote_rue_id,
        )

        self._update_resolution(cote_rue_id, street_name, "address_attribute")

    async def _async_resolve_from_gps(
        self, latitude: float, longitude: float
    ) -> None:
        """Resolve COTE_RUE_ID from GPS coordinates.

        Args:
            latitude: GPS latitude
            longitude: GPS longitude
        """
        # Check if within Montreal bounds
        if not self._is_in_montreal(latitude, longitude):
            _LOGGER.debug(
                "Coordinates (%.4f, %.4f) outside Montreal bounds",
                latitude,
                longitude,
            )
            self._update_resolution(None, None, "gps")
            return

        # Check if moved significantly from last position
        if self._last_latitude is not None and self._last_longitude is not None:
            distance = self._haversine_distance(
                self._last_latitude,
                self._last_longitude,
                latitude,
                longitude,
            )
            if distance < MIN_DISTANCE_THRESHOLD:
                _LOGGER.debug(
                    "Moved only %.1fm, skipping re-resolution", distance
                )
                return

        self._last_latitude = latitude
        self._last_longitude = longitude

        # Find nearest street using GeoJSON data
        if not self._geojson or not self._geojson.is_loaded:
            _LOGGER.warning("GeoJSON not available for GPS resolution")
            self._update_resolution(None, None, "gps")
            return

        nearest = self._find_nearest_street(latitude, longitude)
        if nearest:
            cote_rue_id, street_name, distance, street_side = nearest
            _LOGGER.info(
                "GPS (%.4f, %.4f) resolved to %s (COTE_RUE_ID: %d, side: %s, distance: %.0fm)",
                latitude,
                longitude,
                street_name,
                cote_rue_id,
                street_side,
                distance,
            )
            self._update_resolution(cote_rue_id, street_name, "gps", street_side)
        else:
            _LOGGER.debug(
                "No street found near (%.4f, %.4f)", latitude, longitude
            )
            self._update_resolution(None, None, "gps")

    def _find_nearest_street(
        self, latitude: float, longitude: float
    ) -> tuple[int, str, float, str | None] | None:
        """Find the nearest street to given coordinates using point-to-segment distance.

        Args:
            latitude: GPS latitude
            longitude: GPS longitude

        Returns:
            Tuple of (cote_rue_id, street_name, distance_meters, street_side) or None
        """
        if not self._geojson:
            return None

        best_match: dict[str, Any] | None = None
        best_distance = float("inf")

        # Iterate through all streets with geometry
        for cote_rue_id in self._geojson._geometry_map:
            geometry = self._geojson.get_geometry(cote_rue_id)
            if not geometry:
                continue

            coordinates = geometry.get("coordinates", [])
            if not coordinates or len(coordinates) < 2:
                continue

            # Calculate minimum distance from point to any segment of the LineString
            min_segment_distance, position_ratio = self._point_to_linestring_distance(
                latitude, longitude, coordinates
            )

            if min_segment_distance < best_distance:
                best_distance = min_segment_distance
                street_info = self._geobase.get_street_info(cote_rue_id)

                if street_info:
                    street_name = self._format_street_name(street_info)
                    street_side = street_info.get("cote")
                else:
                    street_name = f"Street {cote_rue_id}"
                    street_side = None

                best_match = {
                    "cote_rue_id": cote_rue_id,
                    "street_name": street_name,
                    "distance": min_segment_distance,
                    "street_side": street_side,
                }

        # Only return if within reasonable distance (100m for better accuracy)
        if best_match and best_match["distance"] < 100:
            return (
                best_match["cote_rue_id"],
                best_match["street_name"],
                best_match["distance"],
                best_match["street_side"],
            )

        return None

    def _point_to_linestring_distance(
        self, lat: float, lon: float, coordinates: list[list[float]]
    ) -> tuple[float, float]:
        """Calculate minimum distance from point to LineString and position ratio.

        Args:
            lat: Point latitude
            lon: Point longitude
            coordinates: List of [lon, lat] coordinate pairs forming the LineString

        Returns:
            Tuple of (distance_meters, position_ratio) where position_ratio is 0.0-1.0
            indicating position along the street (0.0 = start, 1.0 = end)
        """
        min_distance = float("inf")
        best_position_ratio = 0.0
        total_length = 0.0
        segment_lengths = []

        # Calculate total length and segment lengths
        for i in range(len(coordinates) - 1):
            seg_start = coordinates[i]
            seg_end = coordinates[i + 1]
            seg_length = self._haversine_distance(
                seg_start[1], seg_start[0], seg_end[1], seg_end[0]
            )
            segment_lengths.append(seg_length)
            total_length += seg_length

        if total_length == 0:
            return (float("inf"), 0.0)

        # Find closest point on any segment
        cumulative_length = 0.0
        for i in range(len(coordinates) - 1):
            seg_start = coordinates[i]  # [lon, lat]
            seg_end = coordinates[i + 1]

            distance, t = self._point_to_segment_distance(
                lat, lon,
                seg_start[1], seg_start[0],  # start lat, lon
                seg_end[1], seg_end[0]        # end lat, lon
            )

            if distance < min_distance:
                min_distance = distance
                # Calculate position ratio along entire LineString
                position_in_segment = t * segment_lengths[i]
                best_position_ratio = (cumulative_length + position_in_segment) / total_length

            cumulative_length += segment_lengths[i]

        return (min_distance, best_position_ratio)

    def _point_to_segment_distance(
        self,
        point_lat: float, point_lon: float,
        seg_start_lat: float, seg_start_lon: float,
        seg_end_lat: float, seg_end_lon: float,
    ) -> tuple[float, float]:
        """Calculate distance from point to line segment and position along segment.

        Uses projection to find closest point on segment.

        Args:
            point_lat, point_lon: The point coordinates
            seg_start_lat, seg_start_lon: Segment start coordinates
            seg_end_lat, seg_end_lon: Segment end coordinates

        Returns:
            Tuple of (distance_meters, t) where t is 0.0-1.0 position along segment
        """
        # Convert to approximate Cartesian (good enough for small distances)
        # Use segment start as origin
        cos_lat = math.cos(math.radians(seg_start_lat))

        # Convert to meters from segment start
        px = (point_lon - seg_start_lon) * cos_lat * 111320
        py = (point_lat - seg_start_lat) * 111320

        ex = (seg_end_lon - seg_start_lon) * cos_lat * 111320
        ey = (seg_end_lat - seg_start_lat) * 111320

        # Calculate projection
        seg_length_sq = ex * ex + ey * ey

        if seg_length_sq == 0:
            # Segment is a point
            return (math.sqrt(px * px + py * py), 0.0)

        # t is the position along the segment (0 = start, 1 = end)
        t = max(0, min(1, (px * ex + py * ey) / seg_length_sq))

        # Closest point on segment
        closest_x = t * ex
        closest_y = t * ey

        # Distance from point to closest point on segment
        dx = px - closest_x
        dy = py - closest_y
        distance = math.sqrt(dx * dx + dy * dy)

        return (distance, t)

    def _update_resolution(
        self,
        cote_rue_id: int | None,
        street_name: str | None,
        method: str,
        street_side: str | None = None,
    ) -> None:
        """Update resolution state and notify if changed.

        Args:
            cote_rue_id: Resolved COTE_RUE_ID or None
            street_name: Human-readable street name or None
            method: Resolution method used
            street_side: Street side (e.g., "Impair", "Pair") or None
        """
        old_id = self._current_cote_rue_id

        self._current_cote_rue_id = cote_rue_id
        self._current_street_name = street_name
        self._current_street_side = street_side
        self._last_resolution = datetime.now()
        self._resolution_method = method

        # Notify if street changed
        if old_id != cote_rue_id and self._on_street_change:
            self._on_street_change(old_id, cote_rue_id)

    def _format_street_name(self, street_info: dict[str, Any]) -> str:
        """Format street info into readable name.

        Args:
            street_info: Street info from geobase

        Returns:
            Formatted street name
        """
        type_voie = street_info.get("type_voie", "")
        nom_voie = street_info.get("nom_voie", "")

        parts = []
        if type_voie:
            parts.append(type_voie.capitalize())
        if nom_voie:
            parts.append(nom_voie)

        return " ".join(parts) if parts else "Unknown"

    def _is_in_montreal(self, latitude: float, longitude: float) -> bool:
        """Check if coordinates are within Montreal bounds.

        Args:
            latitude: GPS latitude
            longitude: GPS longitude

        Returns:
            True if within Montreal bounds
        """
        return (
            MONTREAL_BOUNDS["min_lat"] <= latitude <= MONTREAL_BOUNDS["max_lat"]
            and MONTREAL_BOUNDS["min_lon"]
            <= longitude
            <= MONTREAL_BOUNDS["max_lon"]
        )

    @staticmethod
    def _haversine_distance(
        lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """Calculate distance between two points using Haversine formula.

        Args:
            lat1, lon1: First point coordinates
            lat2, lon2: Second point coordinates

        Returns:
            Distance in meters
        """
        R = 6371000  # Earth radius in meters

        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(
            phi2
        ) * math.sin(delta_lambda / 2) ** 2

        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    # Properties for entity access
    @property
    def current_cote_rue_id(self) -> int | None:
        """Return current resolved COTE_RUE_ID."""
        return self._current_cote_rue_id

    @property
    def current_street_name(self) -> str | None:
        """Return current street name."""
        return self._current_street_name

    @property
    def current_street_side(self) -> str | None:
        """Return current street side (e.g., 'Impair', 'Pair')."""
        return self._current_street_side

    @property
    def last_resolution(self) -> datetime | None:
        """Return timestamp of last resolution."""
        return self._last_resolution

    @property
    def resolution_method(self) -> str | None:
        """Return method used for last resolution."""
        return self._resolution_method

    @property
    def source_available(self) -> bool:
        """Return whether source entity is available."""
        return self._source_available

    @property
    def is_resolved(self) -> bool:
        """Return whether a valid street is currently resolved."""
        return self._current_cote_rue_id is not None
