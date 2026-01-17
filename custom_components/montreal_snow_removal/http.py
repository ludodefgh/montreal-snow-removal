"""HTTP endpoints for Montreal Snow Removal integration."""
from __future__ import annotations

import logging
from pathlib import Path

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).parent / "frontend"
MAP_CARD_FILENAME = "montreal-snow-removal-map-card.js"


class MontrealSnowRemovalCardView(HomeAssistantView):
    """View to serve the Montreal Snow Removal map card JavaScript."""

    requires_auth = False
    url = f"/api/{DOMAIN}/map-card.js"
    name = f"api:{DOMAIN}:map-card"

    def __init__(self) -> None:
        """Initialize the view."""
        self._card_content: str | None = None

    async def get(self, request: web.Request) -> web.Response:
        """Serve the map card JavaScript file."""
        if self._card_content is None:
            card_path = FRONTEND_DIR / MAP_CARD_FILENAME
            if not card_path.exists():
                _LOGGER.error("Map card file not found: %s", card_path)
                return web.Response(status=404, text="Map card not found")

            self._card_content = card_path.read_text(encoding="utf-8")
            _LOGGER.debug("Loaded map card from %s", card_path)

        return web.Response(
            body=self._card_content,
            content_type="application/javascript",
            headers={
                "Cache-Control": "public, max-age=3600",
            },
        )


async def async_register_http(hass: HomeAssistant) -> None:
    """Register HTTP views for the integration."""
    hass.http.register_view(MontrealSnowRemovalCardView())
    _LOGGER.info(
        "Registered map card at /api/%s/map-card.js",
        DOMAIN,
    )
