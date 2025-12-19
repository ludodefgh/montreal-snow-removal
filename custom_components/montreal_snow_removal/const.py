"""Constants for the Montreal Snow Removal integration."""
from typing import Final

DOMAIN: Final = "montreal_snow_removal"

# API Configuration
API_URL_PROD: Final = "https://servicesenligne2.ville.montreal.qc.ca/api/infoneige/InfoneigeWebService"
API_URL_TEST: Final = "https://servicesenlignedev.ville.montreal.qc.ca/api/infoneige/InfoneigeWebService"
API_WSDL_SUFFIX: Final = "?wsdl"

# Rate Limiting
MIN_SCAN_INTERVAL: Final = 300  # 5 minutes minimum (API requirement)
DEFAULT_SCAN_INTERVAL: Final = 600  # 10 minutes default

# Geobase Configuration
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
}

# Configuration Keys
CONF_API_TOKEN: Final = "api_token"
CONF_ADDRESSES: Final = "addresses"
CONF_ADDRESS: Final = "address"
CONF_NAME: Final = "name"
CONF_COTE_RUE_ID: Final = "cote_rue_id"
CONF_USE_PRODUCTION: Final = "use_production"

# Platforms
PLATFORMS: Final = ["sensor", "binary_sensor"]

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
