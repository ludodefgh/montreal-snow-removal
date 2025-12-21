"""Address parser for Montreal addresses."""
from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

_LOGGER = logging.getLogger(__name__)


class AddressParser:
    """Parser for Montreal addresses with street name normalization."""

    # Street type synonyms (French/English)
    STREET_TYPE_SYNONYMS = {
        "avenue": ["ave", "av"],
        "boulevard": ["boul", "blvd", "bd"],
        "rue": ["street", "st", "r"],
        "chemin": ["ch"],
        "place": ["pl"],
        "cercle": ["circle"],
        "croissant": ["crescent", "cres"],
        "terrasse": ["terrace", "terr"],
        "allee": ["allée"],
        "montee": ["montée"],
        "cote": ["côte"],
    }

    # Reverse mapping for all synonyms
    SYNONYM_TO_TYPE = {}
    for main_type, synonyms in STREET_TYPE_SYNONYMS.items():
        SYNONYM_TO_TYPE[main_type] = main_type
        for synonym in synonyms:
            SYNONYM_TO_TYPE[synonym] = main_type

    @staticmethod
    def parse_address(full_address: str) -> dict[str, Any] | None:
        """
        Parse full address into components.

        Args:
            full_address: Full address string (e.g., "1234 avenue Something")

        Returns:
            Dictionary with parsed components:
            {
                "street_number": 1234,
                "street_name": "Something",
                "street_type": "avenue",
                "original": "1234 avenue Something"
            }
            Or None if parsing fails
        """
        if not full_address or not full_address.strip():
            return None

        original = full_address.strip()

        # Try to extract street number at the beginning
        # Pattern: optional spaces, digits, then remaining text
        match = re.match(r"^\s*(\d+)\s+(.+)$", original)

        if not match:
            # No street number found - try without number
            _LOGGER.debug("No street number found in: %s", original)
            remaining = original
            street_number = None
        else:
            street_number = int(match.group(1))
            remaining = match.group(2)

        # Parse remaining text to extract type and name
        # Normalize for comparison
        remaining_normalized = AddressParser.normalize_street_name(remaining)
        parts = remaining_normalized.split()

        if not parts:
            _LOGGER.warning("No street parts found in: %s", original)
            return None

        # Try to identify street type
        street_type = None
        street_name_parts = []

        for i, part in enumerate(parts):
            # Check if this part is a known street type
            if part in AddressParser.SYNONYM_TO_TYPE:
                street_type = AddressParser.SYNONYM_TO_TYPE[part]
                # Everything else is the street name
                street_name_parts = parts[:i] + parts[i + 1 :]
                break

        # If no type found, all parts are the street name
        if street_type is None:
            street_name_parts = parts
            _LOGGER.debug("No street type identified in: %s", remaining)

        street_name = " ".join(street_name_parts)

        if not street_name:
            _LOGGER.warning("No street name found in: %s", original)
            return None

        return {
            "street_number": street_number,
            "street_name": street_name,
            "street_type": street_type,
            "original": original,
        }

    @staticmethod
    def normalize_street_name(name: str) -> str:
        """
        Normalize street name for comparison.

        - Remove accents (Montréal → Montreal)
        - Convert to lowercase
        - Strip whitespace

        Args:
            name: Street name to normalize

        Returns:
            Normalized street name
        """
        if not name:
            return ""

        # Remove accents using Unicode normalization
        # NFD = decompose accented characters (é → e + ´)
        # Filter out combining characters
        nfd = unicodedata.normalize("NFD", name)
        without_accents = "".join(
            char for char in nfd if unicodedata.category(char) != "Mn"
        )

        # Lowercase and strip
        return without_accents.lower().strip()

    @staticmethod
    def expand_street_types(street_type: str | None) -> list[str]:
        """
        Get all synonyms for a street type.

        Args:
            street_type: Street type (e.g., "rue")

        Returns:
            List of all synonyms including the type itself
            Examples:
            - "rue" → ["rue", "street", "st", "r"]
            - None → []
        """
        if not street_type:
            return []

        normalized_type = AddressParser.normalize_street_name(street_type)

        # Find the main type for this synonym
        main_type = AddressParser.SYNONYM_TO_TYPE.get(normalized_type)

        if not main_type:
            return [normalized_type]

        # Return main type + all its synonyms
        result = [main_type]
        result.extend(AddressParser.STREET_TYPE_SYNONYMS.get(main_type, []))

        return result
