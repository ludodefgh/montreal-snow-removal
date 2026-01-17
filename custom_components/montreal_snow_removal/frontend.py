"""Frontend registration for Montreal Snow Removal integration."""
from __future__ import annotations

import logging

from homeassistant.components.frontend import async_register_built_in_panel
from homeassistant.components.lovelace.resources import ResourceStorageCollection
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CARD_URL = f"/api/{DOMAIN}/map-card.js"
RESOURCE_TYPE = "module"


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Register the frontend resources for the integration.

    This adds the map card JavaScript as a Lovelace resource automatically.
    """
    # Check if lovelace resources are available
    if "lovelace" not in hass.data:
        _LOGGER.debug("Lovelace not yet loaded, skipping automatic resource registration")
        return

    lovelace_data = hass.data.get("lovelace")
    if not lovelace_data:
        return

    # Get the resources collection
    resources = lovelace_data.get("resources")
    if not isinstance(resources, ResourceStorageCollection):
        _LOGGER.debug(
            "Lovelace resources not using storage mode (YAML mode), "
            "user must add resource manually"
        )
        return

    # Check if resource already exists
    existing_resources = resources.async_items()
    for resource in existing_resources:
        if resource.get("url") == CARD_URL:
            _LOGGER.debug("Map card resource already registered")
            return

    # Register the resource
    try:
        await resources.async_create_item(
            {
                "url": CARD_URL,
                "type": RESOURCE_TYPE,
            }
        )
        _LOGGER.info(
            "Automatically registered map card resource: %s",
            CARD_URL,
        )
    except Exception as err:
        _LOGGER.warning(
            "Could not automatically register map card resource: %s. "
            "Please add it manually in Settings > Dashboards > Resources",
            err,
        )
