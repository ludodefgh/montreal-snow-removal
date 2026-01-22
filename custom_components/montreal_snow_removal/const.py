"""Constants for the Montreal Snow Removal integration."""
from typing import Final

DOMAIN: Final = "montreal_snow_removal"

# Public API URLs (from planif-neige-public-api)
PUBLIC_API_BASE_URL: Final = "https://raw.githubusercontent.com/ludodefgh/planif-neige-public-api/main/data"
PUBLIC_API_PLANIF_URL: Final = f"{PUBLIC_API_BASE_URL}/planif-neige.json"
PUBLIC_API_METADATA_URL: Final = f"{PUBLIC_API_BASE_URL}/planif-neige-metadata.json"
PUBLIC_API_GEOBASE_URL: Final = f"{PUBLIC_API_BASE_URL}/geobase-map.json"

# Legacy API Configuration (deprecated - kept for reference)
API_URL_PROD: Final = "https://servicesenligne2.ville.montreal.qc.ca/api/infoneige/InfoneigeWebService"
API_URL_TEST: Final = "https://servicesenlignedev.ville.montreal.qc.ca/api/infoneige/InfoneigeWebService"
API_WSDL_SUFFIX: Final = "?wsdl"

# Rate Limiting
MIN_SCAN_INTERVAL: Final = 300  # 5 minutes minimum (public API updates every 10 min)
DEFAULT_SCAN_INTERVAL: Final = 600  # 10 minutes default

# Geobase Configuration (legacy - now using public API)
GEOBASE_URL: Final = "https://data.montreal.ca/api/3/action/datastore_search"
GEOBASE_RESOURCE_ID: Final = "2f1717e9-0141-48ef-8943-ea348373667f"
GEOBASE_UPDATE_INTERVAL: Final = 604800  # 1 week in seconds

# Snow Removal States (ETAT_DENEIG mapping)
STATE_ENNEIGE: Final = "enneige"  # 0: Not yet cleared, no planning
STATE_DENEIGE: Final = "deneige"  # 1: Clearing completed
STATE_PLANIFIE: Final = "planifie"  # 2: Clearing planned with dates
STATE_REPLANIFIE: Final = "replanifie"  # 3: Rescheduled to new date
STATE_SERA_REPLANIFIE: Final = "sera_replanifie"  # 4: Will be rescheduled (no specific date)
STATE_EN_COURS: Final = "en_cours"  # 5: Clearing in progress (GPS snowplows)
STATE_DEGAGE: Final = "degage"  # 10: Clear (between snow clearing operations)
# Derived state (not from API, calculated when current time is within planning interval)
STATE_STATIONNEMENT_INTERDIT: Final = "stationnement_interdit"

STATE_MAP: Final = {
    0: STATE_ENNEIGE,
    1: STATE_DENEIGE,
    2: STATE_PLANIFIE,
    3: STATE_REPLANIFIE,
    4: STATE_SERA_REPLANIFIE,
    5: STATE_EN_COURS,
    10: STATE_DEGAGE,
}

# API Error Codes
API_ERROR_OK: Final = 0
API_ERROR_INVALID_ACCESS: Final = 1
API_ERROR_ACCESS_DENIED: Final = 2
API_ERROR_NO_DATA: Final = 8
API_ERROR_INVALID_DATE: Final = 9
API_ERROR_RATE_LIMIT: Final = 14

API_ERROR_MESSAGES: Final = {
    API_ERROR_OK: "OK",
    API_ERROR_INVALID_ACCESS: "Invalid access - check parameters",
    API_ERROR_ACCESS_DENIED: "Access denied - check token",
    API_ERROR_NO_DATA: "No data for requested range",
    API_ERROR_INVALID_DATE: "Invalid date format",
    API_ERROR_RATE_LIMIT: "Minimum delay between requests not respected",
}

# Icons
ICON_ENNEIGE: Final = "mdi:snowflake"
ICON_PLANIFIE: Final = "mdi:snowflake-alert"
ICON_EN_COURS: Final = "mdi:snowplow"
ICON_DENEIGE: Final = "mdi:check-circle"
ICON_REPLANIFIE: Final = "mdi:calendar-refresh"
ICON_DEGAGE: Final = "mdi:snowflake-off"
ICON_PARKING_BAN: Final = "mdi:car-off"

ICON_MAP: Final = {
    STATE_ENNEIGE: ICON_ENNEIGE,
    STATE_PLANIFIE: ICON_PLANIFIE,
    STATE_EN_COURS: ICON_EN_COURS,
    STATE_DENEIGE: ICON_DENEIGE,
    STATE_REPLANIFIE: ICON_REPLANIFIE,
    STATE_SERA_REPLANIFIE: ICON_REPLANIFIE,
    STATE_DEGAGE: ICON_DEGAGE,
    STATE_STATIONNEMENT_INTERDIT: ICON_PARKING_BAN,
}

# Configuration Keys
CONF_API_TOKEN: Final = "api_token"
CONF_ADDRESSES: Final = "addresses"
CONF_ADDRESS: Final = "address"
CONF_FULL_ADDRESS: Final = "full_address"
CONF_NAME: Final = "name"
CONF_COTE_RUE_ID: Final = "cote_rue_id"
CONF_USE_PRODUCTION: Final = "use_production"

# Vehicle Tracking Configuration
CONF_TRACKED_VEHICLES: Final = "tracked_vehicles"
CONF_VEHICLE_NAME: Final = "vehicle_name"
CONF_SOURCE_ENTITY: Final = "source_entity"

# Known address attributes from common integrations (in priority order)
KNOWN_ADDRESS_ATTRIBUTES: Final = [
    "street",  # Places integration
    "formatted_address",  # OpenStreetMap
    "address",  # Generic
]

# Vehicle states
STATE_OUTSIDE_COVERAGE: Final = "outside_coverage"
STATE_RESOLVING: Final = "resolving"
STATE_SOURCE_UNAVAILABLE: Final = "source_unavailable"

# Vehicle-specific attributes
ATTR_CURRENT_STREET: Final = "current_street"
ATTR_SOURCE_ENTITY: Final = "source_entity"
ATTR_LAST_RESOLUTION: Final = "last_resolution"
ATTR_RESOLUTION_METHOD: Final = "resolution_method"
ATTR_SOURCE_AVAILABLE: Final = "source_available"
ATTR_STREET_SIDE: Final = "street_side"

# Platforms
PLATFORMS: Final = ["sensor", "binary_sensor", "device_tracker"]

# Attributes
ATTR_COTE_RUE_ID: Final = "cote_rue_id"
ATTR_NOM_VOIE: Final = "nom_voie"
ATTR_TYPE_VOIE: Final = "type_voie"
ATTR_ADRESSE_DEBUT: Final = "adresse_debut"
ATTR_ADRESSE_FIN: Final = "adresse_fin"
ATTR_COTE: Final = "cote"
ATTR_DATE_DEBUT_PLANIF: Final = "date_debut_planif"
ATTR_DATE_FIN_PLANIF: Final = "date_fin_planif"
ATTR_DATE_DEBUT_REPLANIF: Final = "date_debut_replanif"
ATTR_DATE_FIN_REPLANIF: Final = "date_fin_replanif"
ATTR_DERNIERE_MAJ: Final = "derniere_mise_a_jour"
ATTR_HEURES_AVANT_DEBUT: Final = "heures_avant_debut"
ATTR_DEBUT_INTERDICTION: Final = "debut_interdiction"
ATTR_FIN_INTERDICTION: Final = "fin_interdiction"
