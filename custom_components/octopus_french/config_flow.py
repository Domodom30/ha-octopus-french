"""Config flow for Octopus French."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD

class OctopusFrenchConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Octopus French."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Valider les identifiants
            from .lib.octopus_french import OctopusFrench
            
            api = OctopusFrench(user_input[CONF_EMAIL], user_input[CONF_PASSWORD])
            if await api.login():
                return self.async_create_entry(
                    title=f"Octopus French ({user_input[CONF_EMAIL]})",
                    data=user_input,
                )
            else:
                errors["base"] = "invalid_auth"

        data_schema = vol.Schema({
            vol.Required(CONF_EMAIL): str,
            vol.Required(CONF_PASSWORD): str,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OctopusFrenchOptionsFlow(config_entry)

class OctopusFrenchOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Octopus French."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({}),
        )