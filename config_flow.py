from homeassistant import config_entries
import voluptuous as vol

from .const import DOMAIN

class CustomShadesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title=user_input["name"], data=user_input)

        data_schema = vol.Schema({
            vol.Required("name"): str,
            vol.Required("ip"): str,
            vol.Required("pin"): str,
        })

        return self.async_show_form(step_id="user", data_schema=data_schema)
