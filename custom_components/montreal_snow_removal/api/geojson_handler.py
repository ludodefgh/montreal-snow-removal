"""GeoJSON handler for extracting street geometry from Montreal Open Data."""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

# Montreal Open Data GeoJSON URL (Geobase Double)
GEOBASE_GEOJSON_URL = (
    "https://donnees.montreal.ca/dataset/88493b16-220f-4709-b57b-1ea57c5ba405/"
    "resource/16f7fa0a-9ce6-4b29-a7fc-00842c593927/download/gbdouble.json"
)


class GeoJSONError(Exception):
    """Exception raised for GeoJSON errors."""


class GeoJSONHandler:
    """Handler for Montreal GeoJSON street geometry data."""

    def __init__(self, data_dir: Path) -> None:
        """Initialize GeoJSON handler.

        Args:
            data_dir: Directory to store cached GeoJSON data
        """
        self.data_dir = data_dir
        self.cache_file = data_dir / "geobase_geometry.json"
        self._geometry_map: dict[int, dict[str, Any]] = {}
        self._loaded = False

    async def async_load(self) -> None:
        """Load GeoJSON data from cache or download if needed."""
        # Try loading from cache first
        if self.cache_file.exists():
            try:
                _LOGGER.debug("Loading GeoJSON from cache: %s", self.cache_file)
                await self._load_from_cache()
                self._loaded = True
                _LOGGER.info("Loaded %d street geometries from cache", len(self._geometry_map))
                return
            except Exception as err:
                _LOGGER.warning("Failed to load cache, will download: %s", err)

        # Download and cache
        await self.async_update()

    async def async_update(self) -> None:
        """Download latest GeoJSON data and update cache."""
        _LOGGER.info("Downloading GeoJSON data from Montreal Open Data")

        try:
            # Download GeoJSON file
            geojson_data = await self._download_geojson()

            # Parse and extract geometries
            self._geometry_map = self._parse_geojson(geojson_data)
            _LOGGER.info("Parsed %d street geometries", len(self._geometry_map))

            # Save to cache
            await self._save_to_cache()
            self._loaded = True

        except Exception as err:
            _LOGGER.error("Failed to update GeoJSON: %s", err)
            raise GeoJSONError(f"Failed to update GeoJSON: {err}") from err

    async def _download_geojson(self) -> dict[str, Any]:
        """Download GeoJSON file from Montreal Open Data.

        Returns:
            GeoJSON data as dictionary

        Raises:
            GeoJSONError: Download failed
        """
        async with aiohttp.ClientSession() as session:
            _LOGGER.debug("Downloading from: %s", GEOBASE_GEOJSON_URL)

            try:
                async with session.get(
                    GEOBASE_GEOJSON_URL,
                    timeout=aiohttp.ClientTimeout(total=300),  # 5 minutes for large file
                ) as response:
                    if response.status != 200:
                        raise GeoJSONError(
                            f"HTTP {response.status}: {await response.text()}"
                        )

                    # Download and parse JSON
                    data = await response.json()
                    _LOGGER.debug("Downloaded GeoJSON successfully")
                    return data

            except asyncio.TimeoutError as err:
                raise GeoJSONError("Timeout downloading GeoJSON file") from err
            except aiohttp.ClientError as err:
                raise GeoJSONError(f"Network error: {err}") from err

    def _parse_geojson(self, geojson_data: dict[str, Any]) -> dict[int, dict[str, Any]]:
        """Parse GeoJSON and extract geometry for each COTE_RUE_ID.

        Args:
            geojson_data: GeoJSON FeatureCollection

        Returns:
            Dictionary mapping COTE_RUE_ID to geometry info
        """
        geometry_map = {}

        # Handle FeatureCollection format
        if geojson_data.get("type") == "FeatureCollection":
            features = geojson_data.get("features", [])
        else:
            # Fallback: assume it's a list of features
            features = geojson_data if isinstance(geojson_data, list) else []

        _LOGGER.debug("Processing %d features", len(features))

        for feature in features:
            try:
                # Extract properties
                properties = feature.get("properties", {})
                geometry = feature.get("geometry", {})

                # Get COTE_RUE_ID
                cote_rue_id = properties.get("COTE_RUE_ID")
                if not cote_rue_id:
                    continue

                try:
                    cote_rue_id = int(cote_rue_id)
                except (ValueError, TypeError):
                    continue

                # Extract coordinates (LineString geometry)
                coordinates = geometry.get("coordinates", [])
                if not coordinates:
                    continue

                # Calculate center point (average of all coordinates)
                center_lat, center_lon = self._calculate_center(coordinates)

                geometry_map[cote_rue_id] = {
                    "geometry_type": geometry.get("type"),
                    "coordinates": coordinates,
                    "center_latitude": center_lat,
                    "center_longitude": center_lon,
                }

            except Exception as err:
                _LOGGER.debug("Error parsing feature: %s", err)
                continue

        return geometry_map

    def _calculate_center(self, coordinates: list[list[float]]) -> tuple[float, float]:
        """Calculate center point of a LineString.

        Args:
            coordinates: List of [lon, lat] coordinate pairs

        Returns:
            Tuple of (latitude, longitude)
        """
        if not coordinates:
            return (0.0, 0.0)

        # For LineString: coordinates is [[lon, lat], [lon, lat], ...]
        # Average all points to find center
        total_lon = 0.0
        total_lat = 0.0
        count = 0

        for coord in coordinates:
            if len(coord) >= 2:
                total_lon += coord[0]  # longitude
                total_lat += coord[1]  # latitude
                count += 1

        if count == 0:
            return (0.0, 0.0)

        avg_lon = total_lon / count
        avg_lat = total_lat / count

        return (avg_lat, avg_lon)

    async def _load_from_cache(self) -> None:
        """Load geometry mapping from cache file."""

        def _load() -> dict[int, dict[str, Any]]:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Convert string keys back to int
                return {int(k): v for k, v in data.items()}

        self._geometry_map = await asyncio.get_event_loop().run_in_executor(None, _load)

    async def _save_to_cache(self) -> None:
        """Save geometry mapping to cache file."""

        def _save() -> None:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                # Convert int keys to string for JSON
                data = {str(k): v for k, v in self._geometry_map.items()}
                json.dump(data, f, ensure_ascii=False, indent=2)

        await asyncio.get_event_loop().run_in_executor(None, _save)
        _LOGGER.debug("Saved GeoJSON cache to %s", self.cache_file)

    def get_geometry(self, cote_rue_id: int) -> dict[str, Any] | None:
        """Get geometry information for a COTE_RUE_ID.

        Args:
            cote_rue_id: Street side ID

        Returns:
            Geometry dict with coordinates and center point, or None
        """
        if not self._loaded:
            _LOGGER.warning("GeoJSON not loaded yet")
            return None

        return self._geometry_map.get(cote_rue_id)

    def get_center_coordinates(self, cote_rue_id: int) -> tuple[float, float] | None:
        """Get center coordinates for a street.

        Args:
            cote_rue_id: Street side ID

        Returns:
            Tuple of (latitude, longitude) or None
        """
        geometry = self.get_geometry(cote_rue_id)
        if not geometry:
            return None

        lat = geometry.get("center_latitude")
        lon = geometry.get("center_longitude")

        if lat is None or lon is None:
            return None

        return (lat, lon)

    @property
    def is_loaded(self) -> bool:
        """Return whether GeoJSON is loaded."""
        return self._loaded

    @property
    def geometry_count(self) -> int:
        """Return number of geometries in mapping."""
        return len(self._geometry_map)
