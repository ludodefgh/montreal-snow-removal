"""Client for Planif-Neige SOAP API."""
from __future__ import annotations

import asyncio
from datetime import datetime
import logging
from typing import Any

from zeep import Client
from zeep.exceptions import Fault
from zeep.transports import Transport
from requests import Session

from ..const import (
    API_ERROR_ACCESS_DENIED,
    API_ERROR_INVALID_ACCESS,
    API_ERROR_INVALID_DATE,
    API_ERROR_NO_DATA,
    API_ERROR_OK,
    API_ERROR_RATE_LIMIT,
    API_URL_PROD,
    API_URL_TEST,
    API_WSDL_SUFFIX,
)

_LOGGER = logging.getLogger(__name__)


class PlanifNeigeAPIError(Exception):
    """Exception raised for API errors."""


class PlanifNeigeRateLimitError(PlanifNeigeAPIError):
    """Exception raised when rate limit is exceeded."""


class PlanifNeigeAuthError(PlanifNeigeAPIError):
    """Exception raised for authentication errors."""


class PlanifNeigeClient:
    """Client for the Planif-Neige SOAP API."""

    def __init__(self, api_token: str, use_production: bool = True) -> None:
        """Initialize the API client.

        Args:
            api_token: Authentication token for the API
            use_production: Whether to use production or test environment
        """
        self.api_token = api_token
        self.use_production = use_production

        # Set WSDL URL based on environment
        base_url = API_URL_PROD if use_production else API_URL_TEST
        self.wsdl_url = f"{base_url}{API_WSDL_SUFFIX}"

        # SOAP client will be initialized lazily
        self.client = None
        self._session = None
        self._transport = None

        _LOGGER.debug(
            "Initialized PlanifNeigeClient (production=%s)", use_production
        )

    async def _ensure_client(self) -> None:
        """Ensure SOAP client is initialized (lazy initialization in executor).

        This must be called before any API operations.
        """
        if self.client is not None:
            return

        _LOGGER.debug("Initializing SOAP client for %s", self.wsdl_url)

        # Initialize SOAP client in executor to avoid blocking
        await asyncio.get_event_loop().run_in_executor(
            None,
            self._init_soap_client,
        )

        _LOGGER.debug("SOAP client initialized successfully")

    def _init_soap_client(self) -> None:
        """Initialize SOAP client (runs in executor).

        Raises:
            PlanifNeigeAPIError: If WSDL cannot be loaded
        """
        try:
            self._session = Session()
            self._session.verify = True
            self._transport = Transport(session=self._session, timeout=30)
            self.client = Client(wsdl=self.wsdl_url, transport=self._transport)
        except Exception as err:
            _LOGGER.error("Failed to initialize SOAP client: %s", err)
            raise PlanifNeigeAPIError(f"Cannot connect to API server: {err}") from err

    async def async_get_planifications(
        self, from_date: datetime
    ) -> dict[str, Any]:
        """Retrieve snow removal planifications from a specific date.

        Args:
            from_date: Date from which to retrieve modifications

        Returns:
            Dictionary containing API response with planifications

        Raises:
            PlanifNeigeAuthError: Authentication failed
            PlanifNeigeRateLimitError: Rate limit exceeded
            PlanifNeigeAPIError: Other API errors
        """
        # Ensure SOAP client is initialized
        await self._ensure_client()

        from_date_str = from_date.strftime("%Y-%m-%dT%H:%M:%S")

        _LOGGER.debug("Fetching planifications from %s", from_date_str)

        try:
            # Run SOAP call in executor to avoid blocking
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                self._get_planifications_sync,
                from_date_str,
            )
            return self._parse_response(response)

        except Fault as err:
            _LOGGER.error("SOAP Fault: %s", err)
            raise PlanifNeigeAPIError(f"SOAP Fault: {err}") from err

        except Exception as err:
            _LOGGER.error("Error calling API: %s", err)
            raise PlanifNeigeAPIError(f"API call failed: {err}") from err

    def _get_planifications_sync(self, from_date_str: str) -> Any:
        """Synchronous SOAP call (run in executor).

        Args:
            from_date_str: ISO 8601 formatted date string

        Returns:
            Raw SOAP response
        """
        return self.client.service.GetPlanificationsForDate(
            fromDate=from_date_str,
            tokenString=self.api_token,
        )

    def _parse_response(self, response: Any) -> dict[str, Any]:
        """Parse SOAP response.

        Args:
            response: Raw SOAP response object

        Returns:
            Parsed response dictionary

        Raises:
            PlanifNeigeAuthError: Authentication failed
            PlanifNeigeRateLimitError: Rate limit exceeded
            PlanifNeigeAPIError: Other API errors
        """
        try:
            # Extract return code
            return_code = getattr(response, "codeRetour", None)

            if return_code is None:
                raise PlanifNeigeAPIError("Missing return code in response")

            _LOGGER.debug("API returned code: %s", return_code)

            # Handle error codes
            if return_code == API_ERROR_ACCESS_DENIED:
                raise PlanifNeigeAuthError("Access denied - invalid token")

            if return_code == API_ERROR_INVALID_ACCESS:
                raise PlanifNeigeAuthError("Invalid access - check parameters")

            if return_code == API_ERROR_RATE_LIMIT:
                raise PlanifNeigeRateLimitError(
                    "Rate limit exceeded - wait 5 minutes"
                )

            if return_code == API_ERROR_INVALID_DATE:
                raise PlanifNeigeAPIError("Invalid date format")

            # Code 8 (no data) is not an error, just means no updates
            if return_code == API_ERROR_NO_DATA:
                _LOGGER.debug("No data for requested range")
                return {"code": return_code, "planifications": []}

            if return_code != API_ERROR_OK:
                raise PlanifNeigeAPIError(f"Unknown error code: {return_code}")

            # Extract planifications
            planifications = []
            planif_list = getattr(response, "listePlanifications", None)

            if planif_list:
                # Handle both single item and list
                if not isinstance(planif_list, list):
                    planif_list = [planif_list]

                for planif in planif_list:
                    planifications.append(self._parse_planification(planif))

            _LOGGER.debug("Parsed %d planifications", len(planifications))

            return {
                "code": return_code,
                "planifications": planifications,
            }

        except (PlanifNeigeAuthError, PlanifNeigeRateLimitError):
            raise
        except Exception as err:
            _LOGGER.error("Error parsing response: %s", err)
            raise PlanifNeigeAPIError(f"Failed to parse response: {err}") from err

    def _parse_planification(self, planif: Any) -> dict[str, Any]:
        """Parse a single planification object.

        Args:
            planif: Raw planification object from SOAP response

        Returns:
            Parsed planification dictionary
        """
        return {
            "mun_id": getattr(planif, "MUNID", None),
            "cote_rue_id": getattr(planif, "COTE_RUE_ID", None),
            "etat_deneig": getattr(planif, "ETAT_DENEIG", None),
            "date_deb_planif": self._parse_datetime(
                getattr(planif, "DATE_DEB_PLANIF", None)
            ),
            "date_fin_planif": self._parse_datetime(
                getattr(planif, "DATE_FIN_PLANIF", None)
            ),
            "date_deb_replanif": self._parse_datetime(
                getattr(planif, "DATE_DEB_REPLANIF", None)
            ),
            "date_fin_replanif": self._parse_datetime(
                getattr(planif, "DATE_FIN_REPLANIF", None)
            ),
            "date_maj": self._parse_datetime(
                getattr(planif, "DATE_MAJ", None)
            ),
        }

    def _parse_datetime(self, dt_str: str | None) -> datetime | None:
        """Parse datetime string from API.

        Args:
            dt_str: ISO 8601 datetime string or None

        Returns:
            Parsed datetime object or None
        """
        if not dt_str:
            return None

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

    async def async_validate_token(self) -> bool:
        """Validate API token by making a test call.

        Returns:
            True if token is valid, False otherwise
        """
        try:
            # Ensure SOAP client is initialized first
            await self._ensure_client()

            # Try to get planifications from last week
            from datetime import timedelta
            test_date = datetime.now() - timedelta(days=7)
            await self.async_get_planifications(test_date)
            return True

        except PlanifNeigeAuthError:
            return False

        except (PlanifNeigeRateLimitError, PlanifNeigeAPIError) as err:
            # Rate limit or other errors don't mean invalid token
            _LOGGER.warning("Token validation inconclusive: %s", err)
            # Assume valid if we got past authentication
            return True
