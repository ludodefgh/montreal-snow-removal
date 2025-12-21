"""Config flow for Montreal Snow Removal integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_ADDRESS,
    CONF_ADDRESSES,
    CONF_COTE_RUE_ID,
    CONF_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class MontrealSnowRemovalConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Montreal Snow Removal."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._addresses: list[dict[str, Any]] = []
        self._geobase = None  # GeobaseHandler for address search
        self._search_results: list[dict] = []
        self._current_address_search: str = ""
        self._selected_cote_rue_id: int | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - go directly to address entry."""
        # No API token needed anymore - using public API!
        # Go directly to address entry (automatic search)
        return await self.async_step_address_entry()

    async def async_step_address_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual address configuration (fallback)."""
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
            step_id="address_manual",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "address_count": str(len(self._addresses)),
            },
        )

    async def async_step_address_entry(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle address entry step (automatic search)."""
        errors = {}

        if user_input is not None:
            # Check if user wants manual entry
            if user_input.get("use_manual_entry", False):
                return await self.async_step_address_manual()

            # Get full address
            full_address = user_input.get("full_address", "").strip()

            if not full_address:
                errors["full_address"] = "invalid_address_format"
            else:
                # Store for search
                self._current_address_search = full_address
                # Proceed to search
                return await self.async_step_address_search()

        data_schema = vol.Schema(
            {
                vol.Required("full_address"): str,
                vol.Optional("use_manual_entry", default=False): bool,
            }
        )

        return self.async_show_form(
            step_id="address_entry",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "address_count": str(len(self._addresses)),
            },
        )

    async def async_step_address_search(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Perform address search."""
        from .address_parser import AddressParser
        from .api.geobase import GeobaseHandler

        errors = {}

        # Parse address
        parsed = AddressParser.parse_address(self._current_address_search)

        if not parsed or not parsed.get("street_name"):
            # Parsing failed
            errors["base"] = "invalid_address_format"
            return self.async_show_form(
                step_id="address_entry",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            "full_address", default=self._current_address_search
                        ): str,
                        vol.Optional("use_manual_entry", default=False): bool,
                    }
                ),
                errors=errors,
            )

        # Ensure geobase is loaded
        try:
            await self._ensure_geobase_loaded()
        except Exception as err:
            _LOGGER.error("Failed to load geobase: %s", err)
            errors["base"] = "geobase_unavailable"
            return self.async_show_form(
                step_id="address_entry",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            "full_address", default=self._current_address_search
                        ): str,
                        vol.Optional("use_manual_entry", default=False): bool,
                    }
                ),
                errors=errors,
            )

        # Search address
        self._search_results = self._geobase.search_address(
            parsed.get("street_number"), parsed.get("street_name")
        )

        if not self._search_results:
            # No matches found
            errors["base"] = "address_not_found"
            return self.async_show_form(
                step_id="address_entry",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            "full_address", default=self._current_address_search
                        ): str,
                        vol.Optional("use_manual_entry", default=False): bool,
                    }
                ),
                errors=errors,
            )

        if len(self._search_results) == 1:
            # Single match - auto-select
            self._selected_cote_rue_id = self._search_results[0]["cote_rue_id"]
            return await self.async_step_address_confirm()

        # Multiple matches - let user choose
        return await self.async_step_address_select()

    async def async_step_address_select(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle address selection (multiple matches)."""
        if user_input is not None:
            # Get selected COTE_RUE_ID
            self._selected_cote_rue_id = int(user_input.get("selected_cote_rue_id"))
            return await self.async_step_address_confirm()

        # Build selection options
        options = {}
        for match in self._search_results:
            cote_rue_id = match["cote_rue_id"]
            info = match["info"]

            # Format label: "Avenue Something (2100-2198) - Côté Gauche"
            type_voie = info.get("type_voie", "").capitalize()
            nom_voie = info.get("nom_voie", "")
            debut = info.get("debut_adresse", "")
            fin = info.get("fin_adresse", "")
            cote = info.get("cote", "")

            label = f"{type_voie} {nom_voie}"
            if debut and fin:
                label += f" ({debut}-{fin})"
            if cote:
                label += f" - {cote}"

            # Mark in-range matches
            if match.get("in_range"):
                label += " ✓"

            options[str(cote_rue_id)] = label

        data_schema = vol.Schema(
            {
                vol.Required("selected_cote_rue_id"): vol.In(options),
            }
        )

        return self.async_show_form(
            step_id="address_select",
            data_schema=data_schema,
        )

    async def async_step_address_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm selected address."""
        if user_input is not None:
            # Get name
            name = user_input.get(CONF_NAME, "").strip()

            if not name:
                # Show error
                return self.async_show_form(
                    step_id="address_confirm",
                    data_schema=vol.Schema(
                        {
                            vol.Required(CONF_NAME): str,
                        }
                    ),
                    errors={CONF_NAME: "name_required"},
                    description_placeholders=self._get_street_info_description(),
                )

            # Add address to list
            self._addresses.append(
                {
                    CONF_NAME: name,
                    CONF_ADDRESS: self._current_address_search,
                    CONF_COTE_RUE_ID: self._selected_cote_rue_id,
                }
            )

            # Ask if user wants to add another
            return await self.async_step_add_another()

        # Get street info for display
        street_info = self._get_street_info_description()

        # Default name based on street
        default_name = street_info.get("default_name", f"Address {len(self._addresses) + 1}")

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=default_name): str,
            }
        )

        return self.async_show_form(
            step_id="address_confirm",
            data_schema=data_schema,
            description_placeholders=street_info,
        )

    async def _ensure_geobase_loaded(self) -> None:
        """Ensure geobase is loaded for searching."""
        from .api.geobase import GeobaseHandler

        if self._geobase is None or not self._geobase.is_loaded:
            self._geobase = await GeobaseHandler.async_create_temporary()

    def _get_street_info_description(self) -> dict[str, str]:
        """Get street info for description placeholders."""
        if not self._geobase or not self._selected_cote_rue_id:
            return {"street_info": "Unknown", "default_name": "Address"}

        info = self._geobase.get_street_info(self._selected_cote_rue_id)
        if not info:
            return {"street_info": "Unknown", "default_name": "Address"}

        type_voie = info.get("type_voie", "").capitalize()
        nom_voie = info.get("nom_voie", "")
        debut = info.get("debut_adresse", "")
        fin = info.get("fin_adresse", "")
        cote = info.get("cote", "")

        street_info = f"{type_voie} {nom_voie}"
        if debut and fin:
            street_info += f" ({debut}-{fin})"
        if cote:
            street_info += f" - {cote}"

        default_name = f"{type_voie} {nom_voie}".strip()

        return {
            "street_info": street_info,
            "default_name": default_name,
        }

    async def async_step_add_another(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ask if user wants to add another address."""
        if user_input is not None:
            if user_input.get("add_another"):
                # Reset for next address
                self._search_results = []
                self._current_address_search = ""
                self._selected_cote_rue_id = None
                return await self.async_step_address_entry()

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

    def __init__(self) -> None:
        """Initialize options flow."""
        self._addresses: list[dict[str, Any]] = []
        self._geobase = None  # GeobaseHandler for address search
        self._search_results: list[dict] = []
        self._current_address_search: str = ""
        self._selected_cote_rue_id: int | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options - show main menu."""
        if user_input is not None:
            next_step = user_input.get("next_step")
            if next_step == "scan_interval":
                return await self.async_step_scan_interval()
            elif next_step == "manage_addresses":
                return await self.async_step_manage_addresses()
            return self.async_create_entry(title="", data=self.config_entry.options)

        data_schema = vol.Schema(
            {
                vol.Required("next_step"): vol.In(
                    {
                        "scan_interval": "Configure scan interval",
                        "manage_addresses": "Manage addresses",
                    }
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
        )

    async def async_step_scan_interval(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure scan interval."""
        if user_input is not None:
            # Merge with existing options
            new_options = {**self.config_entry.options, **user_input}
            return self.async_create_entry(title="", data=new_options)

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
            step_id="scan_interval",
            data_schema=data_schema,
        )

    async def async_step_manage_addresses(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage addresses - show list with options."""
        if user_input is not None:
            action = user_input.get("action")
            if action == "add":
                # Initialize empty address list for new address
                self._addresses = list(self.config_entry.data.get(CONF_ADDRESSES, []))
                return await self.async_step_add_address()
            elif action.startswith("delete_"):
                # Extract index from action (e.g., "delete_0")
                index = int(action.split("_")[1])
                return await self.async_step_confirm_delete(index)
            return await self.async_step_init()

        # Get current addresses
        current_addresses = self.config_entry.data.get(CONF_ADDRESSES, [])

        # Build action choices
        actions = {"add": "➕ Add new address"}
        for idx, addr in enumerate(current_addresses):
            addr_name = addr.get(CONF_NAME, f"Address {idx + 1}")
            actions[f"delete_{idx}"] = f"🗑️ Delete: {addr_name}"

        data_schema = vol.Schema(
            {
                vol.Required("action"): vol.In(actions),
            }
        )

        return self.async_show_form(
            step_id="manage_addresses",
            data_schema=data_schema,
            description_placeholders={
                "address_count": str(len(current_addresses)),
            },
        )

    async def async_step_add_address(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a new address - entry point (automatic search)."""
        errors = {}

        if user_input is not None:
            # Check if user wants manual entry
            if user_input.get("use_manual_entry", False):
                return await self.async_step_add_address_manual()

            # Get full address
            full_address = user_input.get("full_address", "").strip()

            if not full_address:
                errors["full_address"] = "invalid_address_format"
            else:
                # Store for search
                self._current_address_search = full_address
                # Proceed to search
                return await self.async_step_add_address_search()

        data_schema = vol.Schema(
            {
                vol.Required("full_address"): str,
                vol.Optional("use_manual_entry", default=False): bool,
            }
        )

        return self.async_show_form(
            step_id="add_address",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_add_address_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a new address manually (fallback)."""
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

                    # Update config entry
                    new_data = {**self.config_entry.data}
                    new_data[CONF_ADDRESSES] = self._addresses

                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        data=new_data,
                        title=f"Montreal Snow Removal ({len(self._addresses)} address(es))",
                    )

                    return self.async_create_entry(title="", data=self.config_entry.options)

                except ValueError:
                    errors[CONF_COTE_RUE_ID] = "invalid_cote_rue_id"

        # Default name
        default_name = f"Address {len(self._addresses) + 1}"

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=default_name): str,
                vol.Optional(CONF_ADDRESS, default=""): str,
                vol.Required(CONF_COTE_RUE_ID): str,
            }
        )

        return self.async_show_form(
            step_id="add_address_manual",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_add_address_search(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Perform address search in options flow."""
        from .address_parser import AddressParser
        from .api.geobase import GeobaseHandler

        errors = {}

        # Parse address
        parsed = AddressParser.parse_address(self._current_address_search)

        if not parsed or not parsed.get("street_name"):
            # Parsing failed
            errors["base"] = "invalid_address_format"
            return self.async_show_form(
                step_id="add_address",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            "full_address", default=self._current_address_search
                        ): str,
                        vol.Optional("use_manual_entry", default=False): bool,
                    }
                ),
                errors=errors,
            )

        # Ensure geobase is loaded
        try:
            await self._ensure_geobase_loaded()
        except Exception as err:
            _LOGGER.error("Failed to load geobase: %s", err)
            errors["base"] = "geobase_unavailable"
            return self.async_show_form(
                step_id="add_address",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            "full_address", default=self._current_address_search
                        ): str,
                        vol.Optional("use_manual_entry", default=False): bool,
                    }
                ),
                errors=errors,
            )

        # Search address
        self._search_results = self._geobase.search_address(
            parsed.get("street_number"), parsed.get("street_name")
        )

        if not self._search_results:
            # No matches found
            errors["base"] = "address_not_found"
            return self.async_show_form(
                step_id="add_address",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            "full_address", default=self._current_address_search
                        ): str,
                        vol.Optional("use_manual_entry", default=False): bool,
                    }
                ),
                errors=errors,
            )

        if len(self._search_results) == 1:
            # Single match - auto-select
            self._selected_cote_rue_id = self._search_results[0]["cote_rue_id"]
            return await self.async_step_add_address_confirm()

        # Multiple matches - let user choose
        return await self.async_step_add_address_select()

    async def async_step_add_address_select(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle address selection (multiple matches) in options flow."""
        if user_input is not None:
            # Get selected COTE_RUE_ID
            self._selected_cote_rue_id = int(user_input.get("selected_cote_rue_id"))
            return await self.async_step_add_address_confirm()

        # Build selection options
        options = {}
        for match in self._search_results:
            cote_rue_id = match["cote_rue_id"]
            info = match["info"]

            # Format label: "Avenue Something (2100-2198) - Côté Gauche"
            type_voie = info.get("type_voie", "").capitalize()
            nom_voie = info.get("nom_voie", "")
            debut = info.get("debut_adresse", "")
            fin = info.get("fin_adresse", "")
            cote = info.get("cote", "")

            label = f"{type_voie} {nom_voie}"
            if debut and fin:
                label += f" ({debut}-{fin})"
            if cote:
                label += f" - {cote}"

            # Mark in-range matches
            if match.get("in_range"):
                label += " ✓"

            options[str(cote_rue_id)] = label

        data_schema = vol.Schema(
            {
                vol.Required("selected_cote_rue_id"): vol.In(options),
            }
        )

        return self.async_show_form(
            step_id="add_address_select",
            data_schema=data_schema,
        )

    async def async_step_add_address_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm selected address in options flow."""
        if user_input is not None:
            # Get name
            name = user_input.get(CONF_NAME, "").strip()

            if not name:
                # Show error
                return self.async_show_form(
                    step_id="add_address_confirm",
                    data_schema=vol.Schema(
                        {
                            vol.Required(CONF_NAME): str,
                        }
                    ),
                    errors={CONF_NAME: "name_required"},
                    description_placeholders=self._get_street_info_description(),
                )

            # Add address to list
            self._addresses.append(
                {
                    CONF_NAME: name,
                    CONF_ADDRESS: self._current_address_search,
                    CONF_COTE_RUE_ID: self._selected_cote_rue_id,
                }
            )

            # Update config entry
            new_data = {**self.config_entry.data}
            new_data[CONF_ADDRESSES] = self._addresses

            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=new_data,
                title=f"Montreal Snow Removal ({len(self._addresses)} address(es))",
            )

            return self.async_create_entry(title="", data=self.config_entry.options)

        # Get street info for display
        street_info = self._get_street_info_description()

        # Default name based on street
        default_name = street_info.get("default_name", f"Address {len(self._addresses) + 1}")

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=default_name): str,
            }
        )

        return self.async_show_form(
            step_id="add_address_confirm",
            data_schema=data_schema,
            description_placeholders=street_info,
        )

    async def _ensure_geobase_loaded(self) -> None:
        """Ensure geobase is loaded for searching."""
        from .api.geobase import GeobaseHandler

        if self._geobase is None or not self._geobase.is_loaded:
            self._geobase = await GeobaseHandler.async_create_temporary()

    def _get_street_info_description(self) -> dict[str, str]:
        """Get street info for description placeholders."""
        if not self._geobase or not self._selected_cote_rue_id:
            return {"street_info": "Unknown", "default_name": "Address"}

        info = self._geobase.get_street_info(self._selected_cote_rue_id)
        if not info:
            return {"street_info": "Unknown", "default_name": "Address"}

        type_voie = info.get("type_voie", "").capitalize()
        nom_voie = info.get("nom_voie", "")
        debut = info.get("debut_adresse", "")
        fin = info.get("fin_adresse", "")
        cote = info.get("cote", "")

        street_info = f"{type_voie} {nom_voie}"
        if debut and fin:
            street_info += f" ({debut}-{fin})"
        if cote:
            street_info += f" - {cote}"

        default_name = f"{type_voie} {nom_voie}".strip()

        return {
            "street_info": street_info,
            "default_name": default_name,
        }

    async def async_step_confirm_delete(
        self, index: int, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm deletion of an address."""
        current_addresses = list(self.config_entry.data.get(CONF_ADDRESSES, []))

        if index >= len(current_addresses):
            return await self.async_step_manage_addresses()

        if user_input is not None:
            if user_input.get("confirm"):
                # Remove the address
                current_addresses.pop(index)

                # Update config entry
                new_data = {**self.config_entry.data}
                new_data[CONF_ADDRESSES] = current_addresses

                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=new_data,
                    title=f"Montreal Snow Removal ({len(current_addresses)} address(es))",
                )

                return self.async_create_entry(title="", data=self.config_entry.options)

            # User cancelled, go back to manage addresses
            return await self.async_step_manage_addresses()

        addr = current_addresses[index]
        addr_name = addr.get(CONF_NAME, f"Address {index + 1}")

        data_schema = vol.Schema(
            {
                vol.Required("confirm", default=False): bool,
            }
        )

        return self.async_show_form(
            step_id="confirm_delete",
            data_schema=data_schema,
            description_placeholders={
                "address_name": addr_name,
            },
        )
