"""Geobase handler for mapping COTE_RUE_ID to street names."""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import aiohttp

from ..const import GEOBASE_RESOURCE_ID, GEOBASE_URL

_LOGGER = logging.getLogger(__name__)


class GeobaseError(Exception):
    """Exception raised for Geobase errors."""


class GeobaseHandler:
    """Handler for Geobase street mapping."""

    def __init__(self, data_dir: Path) -> None:
        """Initialize Geobase handler.

        Args:
            data_dir: Directory to store cached geobase data
        """
        self.data_dir = data_dir
        self.cache_file = data_dir / "geobase_map.json"
        self._mapping: dict[int, dict[str, Any]] = {}
        self._loaded = False

    async def async_load(self) -> None:
        """Load geobase mapping from cache or download if needed."""
        # Try loading from cache first
        if self.cache_file.exists():
            try:
                _LOGGER.debug("Loading geobase from cache: %s", self.cache_file)
                await self._load_from_cache()
                self._loaded = True
                _LOGGER.info("Loaded %d streets from cache", len(self._mapping))
                return
            except Exception as err:
                _LOGGER.warning("Failed to load cache, will download: %s", err)

        # Download and cache
        await self.async_update()

    async def async_update(self) -> None:
        """Download latest geobase data and update cache."""
        _LOGGER.info("Downloading geobase data from CKAN API")

        try:
            # Download all records (paginated)
            all_records = await self._download_all_records()

            # Build mapping
            self._mapping = {}
            for record in all_records:
                cote_rue_id = record.get("COTE_RUE_ID")
                if cote_rue_id:
                    try:
                        cote_rue_id = int(cote_rue_id)
                        self._mapping[cote_rue_id] = {
                            "nom_voie": record.get("NOM_VOIE", ""),
                            "type_voie": record.get("TYPE_F", ""),
                            "debut_adresse": record.get("DEBUT_ADRESSE"),
                            "fin_adresse": record.get("FIN_ADRESSE"),
                            "cote": record.get("COTE", ""),
                            "nom_ville": record.get("NOM_VILLE", ""),
                        }
                    except (ValueError, TypeError) as err:
                        _LOGGER.debug("Invalid COTE_RUE_ID: %s (%s)", cote_rue_id, err)

            _LOGGER.info("Built mapping for %d streets", len(self._mapping))

            # Save to cache
            await self._save_to_cache()
            self._loaded = True

        except Exception as err:
            _LOGGER.error("Failed to update geobase: %s", err)
            raise GeobaseError(f"Failed to update geobase: {err}") from err

    async def _download_all_records(self) -> list[dict[str, Any]]:
        """Download all records from CKAN API with pagination.

        Returns:
            List of all records
        """
        all_records = []
        offset = 0
        limit = 5000  # CKAN default max

        async with aiohttp.ClientSession() as session:
            while True:
                url = f"{GEOBASE_URL}?resource_id={GEOBASE_RESOURCE_ID}&limit={limit}&offset={offset}"

                _LOGGER.debug("Fetching records: offset=%d, limit=%d", offset, limit)

                async with session.get(url) as response:
                    if response.status != 200:
                        raise GeobaseError(
                            f"HTTP {response.status}: {await response.text()}"
                        )

                    data = await response.json()

                    if not data.get("success"):
                        raise GeobaseError("API returned success=false")

                    result = data.get("result", {})
                    records = result.get("records", [])

                    if not records:
                        break

                    all_records.extend(records)
                    _LOGGER.debug("Downloaded %d total records", len(all_records))

                    # Check if there are more records
                    total = result.get("total", 0)
                    if len(all_records) >= total:
                        break

                    offset += limit

                # Small delay to be nice to the API
                await asyncio.sleep(0.5)

        return all_records

    async def _load_from_cache(self) -> None:
        """Load mapping from cache file."""

        def _load() -> dict[int, dict[str, Any]]:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Convert string keys back to int
                return {int(k): v for k, v in data.items()}

        self._mapping = await asyncio.get_event_loop().run_in_executor(None, _load)

    async def _save_to_cache(self) -> None:
        """Save mapping to cache file."""

        def _save() -> None:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                # Convert int keys to string for JSON
                data = {str(k): v for k, v in self._mapping.items()}
                json.dump(data, f, ensure_ascii=False, indent=2)

        await asyncio.get_event_loop().run_in_executor(None, _save)
        _LOGGER.debug("Saved geobase cache to %s", self.cache_file)

    def get_street_info(self, cote_rue_id: int) -> dict[str, Any] | None:
        """Get street information for a COTE_RUE_ID.

        Args:
            cote_rue_id: Street side ID

        Returns:
            Street information dict or None if not found
        """
        if not self._loaded:
            _LOGGER.warning("Geobase not loaded yet")
            return None

        return self._mapping.get(cote_rue_id)

    def get_full_street_name(self, cote_rue_id: int) -> str:
        """Get formatted full street name.

        Args:
            cote_rue_id: Street side ID

        Returns:
            Formatted street name or fallback string
        """
        info = self.get_street_info(cote_rue_id)

        if not info:
            return f"Unknown street (ID: {cote_rue_id})"

        nom_voie = info.get("nom_voie", "")
        type_voie = info.get("type_voie", "")
        cote = info.get("cote", "")
        debut_adresse = info.get("debut_adresse")
        fin_adresse = info.get("fin_adresse")

        # Build street name
        parts = []
        if type_voie:
            parts.append(type_voie.capitalize())
        if nom_voie:
            parts.append(nom_voie)

        street_name = " ".join(parts) if parts else f"ID {cote_rue_id}"

        # Add address range and side if available
        if debut_adresse and fin_adresse:
            street_name += f" ({debut_adresse}-{fin_adresse})"

        if cote:
            street_name += f" - {cote}"

        return street_name

    @property
    def is_loaded(self) -> bool:
        """Return whether geobase is loaded."""
        return self._loaded

    @property
    def street_count(self) -> int:
        """Return number of streets in mapping."""
        return len(self._mapping)
