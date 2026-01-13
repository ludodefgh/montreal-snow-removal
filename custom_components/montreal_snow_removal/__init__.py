"""The Montreal Snow Removal integration."""
from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ConfigEntryNotReady

import aiohttp

from .api.geobase import GeobaseError, GeobaseHandler
from .api.geojson_handler import GeoJSONHandler, GeoJSONError
from .api.public_api import PublicAPIClient
from .const import (
    CONF_ADDRESSES,
    CONF_COTE_RUE_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import SnowRemovalCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.DEVICE_TRACKER]

# Module-level cache for planifications data
# Used by the viewport service to avoid repeated API calls
_planif_cache = {"data": None, "timestamp": None}
_CACHE_DURATION = 600  # 10 minutes in seconds


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Montreal Snow Removal from a config entry."""
    _LOGGER.debug("Setting up Montreal Snow Removal integration")

    # Get configuration
    addresses = entry.data[CONF_ADDRESSES]

    # Extract COTE_RUE_IDs to track
    tracked_cote_rue_ids = [addr[CONF_COTE_RUE_ID] for addr in addresses]

    _LOGGER.info(
        "Setting up integration with %d address(es)", len(tracked_cote_rue_ids)
    )

    # Initialize API client with shared aiohttp session
    session = aiohttp.ClientSession()
    api_client = PublicAPIClient(session)

    # Initialize Geobase handler
    # Now using public API for geobase data (no local cache needed)
    data_dir = Path(hass.config.config_dir) / DOMAIN
    geobase = GeobaseHandler(data_dir)

    try:
        geobase_data = await api_client.async_get_geobase_mapping()
        # Convert string keys to int for compatibility
        geobase._mapping = {int(k): v for k, v in geobase_data.items()}
        geobase._loaded = True
        _LOGGER.info("Geobase loaded with %d streets from public API", len(geobase._mapping))
    except Exception as err:
        _LOGGER.error("Failed to load geobase from public API: %s", err)
        raise ConfigEntryNotReady(f"Failed to load geobase: {err}") from err

    # Initialize GeoJSON handler for street geometry
    geojson_handler = GeoJSONHandler(data_dir)
    try:
        await geojson_handler.async_load()
        _LOGGER.info("GeoJSON loaded with %d geometries", geojson_handler.geometry_count)
    except GeoJSONError as err:
        # GeoJSON is optional - log warning but don't fail setup
        _LOGGER.warning("Failed to load GeoJSON (map features will be unavailable): %s", err)

    # Get scan interval from options or use default
    scan_interval = entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)

    # Create coordinator
    coordinator = SnowRemovalCoordinator(
        hass,
        api_client,
        geobase,
        geojson_handler,
        scan_interval,
        tracked_cote_rue_ids,
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator and session in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api_client": api_client,
        "geobase": geobase,
        "geojson_handler": geojson_handler,
        "addresses": addresses,
        "session": session,  # Store session for cleanup
    }

    # Forward entry setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register service for map card to fetch streets in viewport
    await _register_services(hass, entry.entry_id)

    # Register update listener for options changes
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    _LOGGER.info("Montreal Snow Removal integration setup complete")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Montreal Snow Removal integration")

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Close aiohttp session and remove data
    if unload_ok:
        entry_data = hass.data[DOMAIN].pop(entry.entry_id)
        session = entry_data.get("session")
        if session:
            await session.close()

    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    _LOGGER.debug("Updating options")
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", entry.version)

    # Currently at version 1, no migration needed
    # Add migration logic here when bumping version

    return True


async def _register_services(hass: HomeAssistant, entry_id: str) -> None:
    """Register services for the integration.

    Args:
        hass: Home Assistant instance
        entry_id: Config entry ID
    """
    async def get_streets_in_viewport(call: ServiceCall) -> ServiceResponse:
        """Service to get streets within a geographic viewport.

        Parameters:
            north: Northern latitude boundary
            south: Southern latitude boundary
            east: Eastern longitude boundary
            west: Western longitude boundary
            max_results: Maximum number of streets to return (default: 100)

        Returns:
            ServiceResponse with streets data
        """
        # Get parameters
        north = call.data.get("north")
        south = call.data.get("south")
        east = call.data.get("east")
        west = call.data.get("west")
        max_results = call.data.get("max_results", 100)

        # Validate parameters
        if None in (north, south, east, west):
            _LOGGER.error("Missing viewport boundaries")
            return {"streets": []}

        # Get data from first available entry (or specific entry_id if needed)
        domain_data = hass.data.get(DOMAIN, {})
        if not domain_data:
            _LOGGER.warning("No integration data available")
            return {"streets": []}

        # Get first entry's data
        entry_data = domain_data.get(entry_id)
        if not entry_data:
            # Fallback to first available entry
            entry_data = next(iter(domain_data.values()), None)
            if not entry_data:
                return {"streets": []}

        coordinator = entry_data.get("coordinator")
        geojson_handler = entry_data.get("geojson_handler")
        api_client = entry_data.get("api_client")

        if not coordinator or not geojson_handler or not geojson_handler.is_loaded:
            _LOGGER.warning("Coordinator or GeoJSON not available")
            return {"streets": []}

        # Get all street data from API (not just tracked streets)
        # Use module-level cache to avoid repeated API calls
        try:
            now = datetime.now()
            planifications = None

            # Check cache first
            if _planif_cache["data"] and _planif_cache["timestamp"]:
                cache_age = (now - _planif_cache["timestamp"]).total_seconds()
                if cache_age < _CACHE_DURATION:
                    planifications = _planif_cache["data"]
                    _LOGGER.debug(
                        "Using cached planifications (%d streets, cache age: %.1fs)",
                        len(planifications),
                        cache_age
                    )

            # Fetch from API if cache miss or expired
            if planifications is None:
                _LOGGER.debug("Cache miss or expired, fetching from API")
                response = await api_client.async_get_planifications()
                planifications = response.get("planifications", [])

                # Update cache
                _planif_cache["data"] = planifications
                _planif_cache["timestamp"] = now

                _LOGGER.debug(
                    "Fetched %d streets from API, cache updated",
                    len(planifications)
                )

        except Exception as err:
            _LOGGER.error("Failed to fetch street data: %s", err)
            return {"streets": []}

        streets_in_viewport = []

        # Iterate through streets and filter by viewport
        for planif in planifications:
            # Get COTE_RUE_ID from planification
            cote_rue_id = planif.get("cote_rue_id")
            if not cote_rue_id:
                continue

            try:
                cote_rue_id_int = int(cote_rue_id)
            except (ValueError, TypeError):
                continue

            # Get geometry for this street
            geometry = geojson_handler.get_geometry(cote_rue_id_int)
            if not geometry:
                continue

            # Get center coordinates
            center_lat = geometry.get("center_latitude")
            center_lon = geometry.get("center_longitude")

            if center_lat is None or center_lon is None:
                continue

            # Check if center is within viewport
            if not (south <= center_lat <= north and west <= center_lon <= east):
                continue

            # Get street info from geobase
            geobase = entry_data.get("geobase")
            street_info = geobase.get_street_info(cote_rue_id_int) if geobase else {}

            # Build street data
            coordinates = geometry.get("coordinates", [])
            street_data = {
                "cote_rue_id": cote_rue_id_int,
                "coordinates": [[coord[1], coord[0]] for coord in coordinates],  # Flip to [lat, lon]
                "center_latitude": center_lat,
                "center_longitude": center_lon,
                "state": coordinator._map_etat_deneig(planif.get("etat_deneig", 0)),
                "street_name": f"{street_info.get('type_voie', '')} {street_info.get('nom_voie', '')}".strip(),
                "street_side": street_info.get("cote", ""),
            }

            # Add dates if available
            if planif.get("date_deb_planif"):
                street_data["start_time"] = planif["date_deb_planif"].isoformat()
            if planif.get("date_fin_planif"):
                street_data["end_time"] = planif["date_fin_planif"].isoformat()
            if planif.get("date_deb_replanif"):
                street_data["replan_start_time"] = planif["date_deb_replanif"].isoformat()
            if planif.get("date_fin_replanif"):
                street_data["replan_end_time"] = planif["date_fin_replanif"].isoformat()

            streets_in_viewport.append(street_data)

            # Limit results to avoid overwhelming the frontend
            if len(streets_in_viewport) >= max_results:
                break

        _LOGGER.debug("Found %d streets in viewport (max: %d)", len(streets_in_viewport), max_results)

        return {"streets": streets_in_viewport}

    # Register the service with optional response support
    # OPTIONAL allows both return_response=True (desktop) and legacy calls (mobile app)
    hass.services.async_register(
        DOMAIN,
        "get_streets_in_viewport",
        get_streets_in_viewport,
        supports_response=SupportsResponse.OPTIONAL,
    )
