"""Config flow for Montreal Snow Removal integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .api.planif_neige import (
    PlanifNeigeAuthError,
    PlanifNeigeClient,
)
from .const import (
    CONF_ADDRESS,
    CONF_ADDRESSES,
    CONF_API_TOKEN,
    CONF_COTE_RUE_ID,
    CONF_NAME,
    CONF_USE_PRODUCTION,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class MontrealSnowRemovalConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Montreal Snow Removal."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._api_token: str | None = None
        self._use_production: bool = True
        self._addresses: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Validate API token
            api_token = user_input[CONF_API_TOKEN]
            use_production = user_input.get(CONF_USE_PRODUCTION, True)

            # Test API connection
            try:
                client = PlanifNeigeClient(api_token, use_production)
                is_valid = await client.async_validate_token()

                if not is_valid:
                    errors["base"] = "invalid_auth"
                else:
                    # Store token and proceed to address configuration
                    self._api_token = api_token
                    self._use_production = use_production
                    return await self.async_step_address()

            except PlanifNeigeAuthError:
                errors["base"] = "invalid_auth"
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                # Check if it's a connection/server error
                if "520" in str(err) or "Server Error" in str(err):
                    errors["base"] = "cannot_connect"
                elif "HTTP" in str(err) or "Connection" in str(err):
                    errors["base"] = "cannot_connect"
                else:
                    errors["base"] = "unknown"

        # Show form
        data_schema = vol.Schema(
            {
                vol.Required(CONF_API_TOKEN): str,
                vol.Optional(CONF_USE_PRODUCTION, default=True): bool,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_address(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle address configuration step."""
        errors = {}

        if user_input is not None:
            # Get address details
            address = user_input.get(CONF_ADDRESS, "").strip()
            name = user_input.get(CONF_NAME, "").strip()
            cote_rue_id_str = user_input.get(CONF_COTE_RUE_ID, "").strip()

            # Validate inputs
            if not name:
                errors[CONF_NAME] = "name_required"
            elif not cote_rue_id_str:
                errors[CONF_COTE_RUE_ID] = "cote_rue_id_required"
            else:
                try:
                    cote_rue_id = int(cote_rue_id_str)

                    # Add address to list
                    self._addresses.append(
                        {
                            CONF_NAME: name,
                            CONF_ADDRESS: address,
                            CONF_COTE_RUE_ID: cote_rue_id,
                        }
                    )

                    # Ask if user wants to add another address
                    return await self.async_step_add_another()

                except ValueError:
                    errors[CONF_COTE_RUE_ID] = "invalid_cote_rue_id"

        # Default name from address count
        default_name = f"Address {len(self._addresses) + 1}"

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=default_name): str,
                vol.Optional(CONF_ADDRESS, default=""): str,
                vol.Required(CONF_COTE_RUE_ID): str,
            }
        )

        return self.async_show_form(
            step_id="address",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "address_count": str(len(self._addresses)),
            },
        )

    async def async_step_add_another(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ask if user wants to add another address."""
        if user_input is not None:
            if user_input.get("add_another"):
                return await self.async_step_address()

            # Create the entry
            return await self._create_entry()

        data_schema = vol.Schema(
            {
                vol.Required("add_another", default=False): bool,
            }
        )

        return self.async_show_form(
            step_id="add_another",
            data_schema=data_schema,
            description_placeholders={
                "address_count": str(len(self._addresses)),
            },
        )
    
    async def _create_entry(self) -> FlowResult:
        """Create the config entry."""
        if not self._addresses:
            # Should not happen, but fallback to address step
            return self.async_abort(reason="no_addresses")

        # Create unique ID from first address COTE_RUE_ID
        unique_id = f"montreal_snow_removal_{self._addresses[0][CONF_COTE_RUE_ID]}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"Montreal Snow Removal ({len(self._addresses)} address(es))",
            data={
                CONF_API_TOKEN: self._api_token,
                CONF_USE_PRODUCTION: self._use_production,
                CONF_ADDRESSES: self._addresses,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> MontrealSnowRemovalOptionsFlow:
        """Get the options flow for this handler."""
        return MontrealSnowRemovalOptionsFlow()


class MontrealSnowRemovalOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Montreal Snow Removal."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Get current options
        scan_interval = self.config_entry.options.get(
            "scan_interval", DEFAULT_SCAN_INTERVAL
        )

        data_schema = vol.Schema(
            {
                vol.Optional("scan_interval", default=scan_interval): vol.All(
                    vol.Coerce(int), vol.Range(min=300, max=3600)
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
        )
