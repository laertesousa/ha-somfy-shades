from homeassistant import config_entries
import voluptuous as vol

from .const import DOMAIN

class CustomShadesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title=user_input["name"], data=user_input)

        return self.async_show_form(step_id="user", data_schema=vol.Schema({
            vol.Required("name"): str,
            vol.Required("ip"): str,
            vol.Required("pin"): str,
        }))

    @staticmethod
    def async_get_options_flow(config_entry):
        return SomfyOptionsFlowHandler(config_entry)

class SomfyOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("ip", default=self.config_entry.options.get("ip", self.config_entry.data.get("ip"))): str,
                vol.Required("pin", default=self.config_entry.options.get("pin", self.config_entry.data.get("pin"))): str,
            })
        )
