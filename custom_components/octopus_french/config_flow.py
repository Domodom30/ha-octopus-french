import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from .const import DOMAIN
from .api import OctopusFrenchAPI

class OctopusFrenchConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            api = OctopusFrenchAPI(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
            try:
                token = await self.hass.async_add_executor_job(api.login)
                if token:
                    return self.async_create_entry(title="Octopus France", data=user_input)
            except Exception:
                errors["base"] = "auth"

        schema = vol.Schema({
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
