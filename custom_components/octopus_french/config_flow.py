"""Config flow for Octopus French integration."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries

from .const import DOMAIN

class OctopusFrenchConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Octopus French."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            email = user_input.get("email")
            password = user_input.get("password")
            # Ici, on pourrait tester la connexion si on avait le client
            return self.async_create_entry(title=email, data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required("email"): str,
                vol.Required("password"): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)
