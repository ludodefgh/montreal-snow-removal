"""DataUpdateCoordinator for Montreal Snow Removal integration."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api.public_api import (
    PublicAPIClient,
    PublicAPIError,
)
from .api.geobase import GeobaseHandler
from .api.geojson_handler import GeoJSONHandler
from .const import (
    DOMAIN,
    MIN_SCAN_INTERVAL,
    STATE_MAP,
    STATE_PLANIFIE,
    STATE_REPLANIFIE,
    STATE_STATIONNEMENT_INTERDIT,
)

_LOGGER = logging.getLogger(__name__)


class SnowRemovalCoordinator(DataUpdateCoordinator):
    """Coordinator to manage snow removal data updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: PublicAPIClient,
        geobase: GeobaseHandler,
        geojson_handler: GeoJSONHandler,
        update_interval: int,
        tracked_cote_rue_ids: list[int],
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance
            api_client: Public API client
            geobase: Geobase handler for street name mapping
            geojson_handler: GeoJSON handler for street geometry
            update_interval: Update interval in seconds (min 300)
            tracked_cote_rue_ids: List of COTE_RUE_ID to track
        """
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=max(update_interval, MIN_SCAN_INTERVAL)
            ),
        )

        self.api_client = api_client
        self.geobase = geobase
        self.geojson_handler = geojson_handler
        self.tracked_cote_rue_ids = set(tracked_cote_rue_ids)
        self.last_update_time: datetime | None = None

        # Store current state for each tracked street
        self._street_data: dict[int, dict[str, Any]] = {}

        _LOGGER.debug(
            "Initialized coordinator for %d streets", len(self.tracked_cote_rue_ids)
        )

    async def _async_update_data(self) -> dict[int, dict[str, Any]]:
        """Fetch data from API.

        Returns:
            Dictionary mapping COTE_RUE_ID to street data

        Raises:
            UpdateFailed: When update fails
        """
        try:
            # Fetch all planifications from public API
            # (Public API already returns all active planifications)
            _LOGGER.debug("Fetching planifications from public API")
            response = await self.api_client.async_get_planifications()

            # Update last update time
            self.last_update_time = datetime.now()

            # Process planifications
            planifications = response.get("planifications", [])
            _LOGGER.debug("Received %d planifications", len(planifications))

            # Update street data with new planifications
            for planif in planifications:
                cote_rue_id = planif.get("cote_rue_id")

                # Only process tracked streets
                if cote_rue_id not in self.tracked_cote_rue_ids:
                    continue

                # Get street info from geobase
                street_info = self.geobase.get_street_info(cote_rue_id)

                # Map state
                etat_code = planif.get("etat_deneig", 0)
                state = STATE_MAP.get(etat_code, "unknown")

                # Build street data
                street_data = {
                    "cote_rue_id": cote_rue_id,
                    "state": state,
                    "etat_code": etat_code,
                    "date_deb_planif": planif.get("date_deb_planif"),
                    "date_fin_planif": planif.get("date_fin_planif"),
                    "date_deb_replanif": planif.get("date_deb_replanif"),
                    "date_fin_replanif": planif.get("date_fin_replanif"),
                    "date_maj": planif.get("date_maj"),
                }

                # Add street info if available
                if street_info:
                    street_data.update({
                        "nom_voie": street_info.get("nom_voie"),
                        "type_voie": street_info.get("type_voie"),
                        "debut_adresse": street_info.get("debut_adresse"),
                        "fin_adresse": street_info.get("fin_adresse"),
                        "cote": street_info.get("cote"),
                        "nom_ville": street_info.get("nom_ville"),
                    })

                # Add GPS coordinates if available from GeoJSON
                if self.geojson_handler.is_loaded:
                    coords = self.geojson_handler.get_center_coordinates(cote_rue_id)
                    if coords:
                        street_data["latitude"] = coords[0]
                        street_data["longitude"] = coords[1]

                # Calculate hours before start (if planned)
                if planif.get("date_deb_planif"):
                    hours_before = self._calculate_hours_before(
                        planif["date_deb_planif"]
                    )
                    street_data["heures_avant_debut"] = hours_before
                elif planif.get("date_deb_replanif"):
                    hours_before = self._calculate_hours_before(
                        planif["date_deb_replanif"]
                    )
                    street_data["heures_avant_debut"] = hours_before
                else:
                    street_data["heures_avant_debut"] = None

                # Update stored data
                self._street_data[cote_rue_id] = street_data

                _LOGGER.debug(
                    "Updated COTE_RUE_ID %d: state=%s",
                    cote_rue_id,
                    state,
                )

            # Return current state for all tracked streets
            return self._street_data

        except PublicAPIError as err:
            _LOGGER.error("Public API error: %s", err)
            raise UpdateFailed(f"API error: {err}") from err

        except Exception as err:
            _LOGGER.exception("Unexpected error during update: %s", err)
            raise UpdateFailed(f"Unexpected error: {err}") from err

    def _calculate_hours_before(self, target_date: datetime) -> float | None:
        """Calculate hours before a target date.

        Args:
            target_date: Target datetime

        Returns:
            Hours before target date, or None if target is in the past
        """
        if not target_date:
            return None

        now = datetime.now()

        # If target_date is naive, assume same timezone as now
        if target_date.tzinfo is None and now.tzinfo is not None:
            target_date = target_date.replace(tzinfo=now.tzinfo)
        elif target_date.tzinfo is not None and now.tzinfo is None:
            now = now.replace(tzinfo=target_date.tzinfo)

        delta = target_date - now
        hours = delta.total_seconds() / 3600

        return hours if hours > 0 else None

    def get_street_data(self, cote_rue_id: int) -> dict[str, Any] | None:
        """Get current data for a specific street.

        Args:
            cote_rue_id: Street side ID

        Returns:
            Street data dictionary or None
        """
        return self._street_data.get(cote_rue_id)

    def _map_etat_deneig(self, etat_value: int) -> str:
        """Map ETAT_DENEIG numeric value to state string.

        Args:
            etat_value: Numeric state value from API

        Returns:
            State string constant
        """
        return STATE_MAP.get(etat_value, "enneige")

    def derive_state_with_parking_ban(
        self,
        etat_code: int,
        date_deb_planif: datetime | None,
        date_fin_planif: datetime | None,
        date_deb_replanif: datetime | None = None,
        date_fin_replanif: datetime | None = None,
    ) -> str:
        """Derive the display state, including 'stationnement_interdit' when applicable.

        The official Montreal app shows 'stationnement_interdit' (parking banned, red)
        when the current time is within the planning interval. This method replicates
        that behavior.

        Args:
            etat_code: Numeric state value from API (0-10)
            date_deb_planif: Planning start datetime
            date_fin_planif: Planning end datetime
            date_deb_replanif: Rescheduled start datetime (optional)
            date_fin_replanif: Rescheduled end datetime (optional)

        Returns:
            State string, potentially 'stationnement_interdit' if within interval
        """
        base_state = STATE_MAP.get(etat_code, "enneige")

        # Only derive parking ban for planned or rescheduled states
        if base_state not in (STATE_PLANIFIE, STATE_REPLANIFIE):
            return base_state

        now = datetime.now()

        # Check rescheduled interval first (takes priority if state is replanifie)
        if base_state == STATE_REPLANIFIE and date_deb_replanif and date_fin_replanif:
            if self._is_within_interval(now, date_deb_replanif, date_fin_replanif):
                return STATE_STATIONNEMENT_INTERDIT

        # Check original planning interval
        if date_deb_planif and date_fin_planif:
            if self._is_within_interval(now, date_deb_planif, date_fin_planif):
                return STATE_STATIONNEMENT_INTERDIT

        return base_state

    def _is_within_interval(
        self, now: datetime, start: datetime, end: datetime
    ) -> bool:
        """Check if current time is within the given interval.

        Args:
            now: Current datetime
            start: Interval start datetime
            end: Interval end datetime

        Returns:
            True if now is between start and end
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

    def add_tracked_street(self, cote_rue_id: int) -> None:
        """Add a street to track.

        Args:
            cote_rue_id: Street side ID to add
        """
        if cote_rue_id not in self.tracked_cote_rue_ids:
            self.tracked_cote_rue_ids.add(cote_rue_id)
            _LOGGER.debug("Added COTE_RUE_ID %d to tracking", cote_rue_id)

    def remove_tracked_street(self, cote_rue_id: int) -> None:
        """Remove a street from tracking.

        Args:
            cote_rue_id: Street side ID to remove
        """
        if cote_rue_id in self.tracked_cote_rue_ids:
            self.tracked_cote_rue_ids.discard(cote_rue_id)
            self._street_data.pop(cote_rue_id, None)
            _LOGGER.debug("Removed COTE_RUE_ID %d from tracking", cote_rue_id)
