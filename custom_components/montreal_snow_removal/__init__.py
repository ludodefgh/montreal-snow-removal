"""The Montreal Snow Removal integration."""
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .api.geobase import GeobaseError, GeobaseHandler
from .api.planif_neige import PlanifNeigeClient
from .const import (
    CONF_ADDRESSES,
    CONF_API_TOKEN,
    CONF_COTE_RUE_ID,
    CONF_USE_PRODUCTION,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import SnowRemovalCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Montreal Snow Removal from a config entry."""
    _LOGGER.debug("Setting up Montreal Snow Removal integration")

    # Get configuration
    api_token = entry.data[CONF_API_TOKEN]
    use_production = entry.data.get(CONF_USE_PRODUCTION, True)
    addresses = entry.data[CONF_ADDRESSES]

    # Extract COTE_RUE_IDs to track
    tracked_cote_rue_ids = [addr[CONF_COTE_RUE_ID] for addr in addresses]

    _LOGGER.info(
        "Setting up integration with %d address(es)", len(tracked_cote_rue_ids)
    )

    # Initialize API client
    api_client = PlanifNeigeClient(api_token, use_production)

    # Initialize Geobase handler
    # Store data in HA config directory, not in custom_components
    data_dir = Path(hass.config.config_dir) / DOMAIN
    geobase = GeobaseHandler(data_dir)

    # Load geobase (from cache or download)
    try:
        await geobase.async_load()
        _LOGGER.info("Geobase loaded with %d streets", geobase.street_count)
    except GeobaseError as err:
        _LOGGER.error("Failed to load geobase: %s", err)
        raise ConfigEntryNotReady(f"Failed to load geobase: {err}") from err

    # Get scan interval from options or use default
    scan_interval = entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)

    # Create coordinator
    coordinator = SnowRemovalCoordinator(
        hass,
        api_client,
        geobase,
        scan_interval,
        tracked_cote_rue_ids,
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api_client": api_client,
        "geobase": geobase,
        "addresses": addresses,
    }

    # Forward entry setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register update listener for options changes
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    _LOGGER.info("Montreal Snow Removal integration setup complete")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Montreal Snow Removal integration")

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Remove data
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

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
