"""Client for the public Planif-Neige API (GitHub-hosted)."""
from __future__ import annotations

import asyncio
from datetime import datetime
import json
import logging
from typing import Any

import aiohttp

from ..const import (
    PUBLIC_API_PLANIF_URL,
    PUBLIC_API_METADATA_URL,
    PUBLIC_API_GEOBASE_URL,
)

_LOGGER = logging.getLogger(__name__)


class PublicAPIError(Exception):
    """Exception raised for API errors."""


class PublicAPIClient:
    """Client for the public Planif-Neige API."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the API client.

        Args:
            session: aiohttp ClientSession for making requests
        """
        self.session = session
        _LOGGER.debug("Initialized PublicAPIClient")

    async def async_get_planifications(self) -> dict[str, Any]:
        """Retrieve snow removal planifications from public API.

        Returns:
            Dictionary containing planifications data

        Raises:
            PublicAPIError: API request failed
        """
        _LOGGER.debug("Fetching planifications from public API")

        try:
            async with self.session.get(
                PUBLIC_API_PLANIF_URL,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                response.raise_for_status()
                # GitHub raw serves JSON as text/plain, need to parse manually
                text = await response.text()
                data = json.loads(text)

                planifications = data.get("planifications", [])
                _LOGGER.debug("Retrieved %d planifications", len(planifications))

                return {
                    "code": 0,  # Success
                    "planifications": self._normalize_planifications(planifications),
                    "generated_at": data.get("generated_at"),
                }

        except aiohttp.ClientError as err:
            _LOGGER.error("HTTP error fetching planifications: %s", err)
            raise PublicAPIError(f"Failed to fetch planifications: {err}") from err

        except Exception as err:
            _LOGGER.error("Error fetching planifications: %s", err)
            raise PublicAPIError(f"Unexpected error: {err}") from err

    async def async_get_metadata(self) -> dict[str, Any]:
        """Retrieve API metadata (last update, status, etc.).

        Returns:
            Dictionary containing metadata

        Raises:
            PublicAPIError: API request failed
        """
        _LOGGER.debug("Fetching metadata from public API")

        try:
            async with self.session.get(
                PUBLIC_API_METADATA_URL,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                response.raise_for_status()
                # GitHub raw serves JSON as text/plain, need to parse manually
                text = await response.text()
                return json.loads(text)

        except aiohttp.ClientError as err:
            _LOGGER.error("HTTP error fetching metadata: %s", err)
            raise PublicAPIError(f"Failed to fetch metadata: {err}") from err

        except Exception as err:
            _LOGGER.error("Error fetching metadata: %s", err)
            raise PublicAPIError(f"Unexpected error: {err}") from err

    async def async_get_geobase_mapping(self) -> dict[str, dict[str, Any]]:
        """Retrieve geobase mapping (COTE_RUE_ID -> street info).

        Returns:
            Dictionary mapping COTE_RUE_ID to street information

        Raises:
            PublicAPIError: API request failed
        """
        _LOGGER.debug("Fetching geobase mapping from public API")

        try:
            async with self.session.get(
                PUBLIC_API_GEOBASE_URL,
                timeout=aiohttp.ClientTimeout(total=60),  # Large file
            ) as response:
                response.raise_for_status()
                # GitHub raw serves JSON as text/plain, need to parse manually
                text = await response.text()
                mapping = json.loads(text)
                _LOGGER.debug("Retrieved geobase mapping with %d entries", len(mapping))
                return mapping

        except aiohttp.ClientError as err:
            _LOGGER.error("HTTP error fetching geobase: %s", err)
            raise PublicAPIError(f"Failed to fetch geobase: {err}") from err

        except Exception as err:
            _LOGGER.error("Error fetching geobase: %s", err)
            raise PublicAPIError(f"Unexpected error: {err}") from err

    def _normalize_planifications(
        self, planifications: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Normalize planification data from public API to match expected format.

        The public API uses snake_case field names, we need to ensure
        compatibility with the existing integration code.

        Args:
            planifications: Raw planification list from public API

        Returns:
            Normalized planification list
        """
        normalized = []

        for planif in planifications:
            # Public API already uses snake_case, just ensure datetime parsing
            normalized.append({
                "mun_id": planif.get("mun_id"),
                "cote_rue_id": planif.get("cote_rue_id"),
                "etat_deneig": planif.get("etat_deneig"),
                "date_deb_planif": self._parse_datetime(
                    planif.get("date_deb_planif")
                ),
                "date_fin_planif": self._parse_datetime(
                    planif.get("date_fin_planif")
                ),
                "date_deb_replanif": self._parse_datetime(
                    planif.get("date_deb_replanif")
                ),
                "date_fin_replanif": self._parse_datetime(
                    planif.get("date_fin_replanif")
                ),
                "date_maj": self._parse_datetime(planif.get("date_maj")),
            })

        return normalized

    def _parse_datetime(self, dt_str: str | datetime | None) -> datetime | None:
        """Parse datetime string from API.

        Args:
            dt_str: ISO 8601 datetime string, datetime object, or None

        Returns:
            Parsed datetime object or None
        """
        if not dt_str:
            return None

        # If already a datetime object, return it directly
        if isinstance(dt_str, datetime):
            return dt_str

        try:
            # Handle various datetime formats from API
            # Try with timezone first, then without
            for fmt in [
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
            ]:
                try:
                    return datetime.strptime(dt_str, fmt)
                except ValueError:
                    continue

            _LOGGER.warning("Unable to parse datetime: %s", dt_str)
            return None

        except Exception as err:
            _LOGGER.error("Error parsing datetime '%s': %s", dt_str, err)
            return None
