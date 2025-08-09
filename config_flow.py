import asyncio
import logging
from typing import Tuple, Iterator

from anyio import sleep
from homeassistant import config_entries
import voluptuous as vol
from homeassistant.components.persistent_notification import async_create
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry

from .somfy.classes.SomfyPoeBlindClient import SomfyPoeBlindClient
from .const import DOMAIN
from .helpers.devices import get_devices_for_entry, get_device_by_name
from .somfy.dtos.somfy_objects import Device
from .somfy.classes.Scanner import Scanner

logger = logging.getLogger("Somfy")

class SomfyIntegrationConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Main entry point. Called for both integration setup and Add Device."""
        source = self.context.get("source")

        logger.info(self.context)
        logger.info(f"user_input: {user_input}")
        logger.info(f"source: {source}")

        if user_input is not None:
            return self.async_create_entry(
                title=user_input["name"],
                data={"subnet": user_input["subnet"]}
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("name"): str,
                vol.Optional("subnet", default="10.0.7.0/24"): str
            })
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        return DeviceOptionsFlowHandler(config_entry)

class DeviceOptionsFlowHandler(config_entries.OptionsFlow):
    discovery_task = None
    discovered_devices = None

    def __init__(self, config_entry):
        self.devices = config_entry.options
        super().__init__()

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(
            step_id="init",
            menu_options={
                "start_discovery": "Start Discovery",
                "edit_settings": "Edit Settings",
                "add_device": "Add Device",
                "edit_device": "Edit Device",
                "remove_device": "Remove Device",
                "clear_devices": "Clear Devices",
            },
        )

    async def get_device_choices(self):
        devices = await get_devices_for_entry(self.hass, self.config_entry)

        if not devices:
            return None, None

        device_by_id = {}
        choices = {}
        for device in devices:
            device_by_id[device.id] = device
            choices[device.id] = device.name

        return choices, device_by_id

    def reload(self):
        async def _reload_entry_later():
            await asyncio.sleep(0)  # yield to let the flow finish
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)

        self.hass.async_create_task(_reload_entry_later())

    async def async_step_start_discovery(self, user_input=None):
        logger.info("start discovery called")

        if not self.discovery_task:
            self.discovery_task = self.hass.async_create_task(self.discover_devices())

        if not self.discovery_task.done():
            progress_action = "start_discovery"
            return self.async_show_progress(
                progress_action=progress_action,
                progress_task=self.discovery_task,
                description_placeholders={
                    "status": "Scanning for Somfy devices...",
                }
            )

        return self.async_show_progress_done(next_step_id="discovery_done")

    async def discover_devices(self):
        subnet = self.config_entry.data.get("subnet")
        logger.info(f'discovering devices on {subnet}')
        self.discovered_devices = await self.get_devices(subnet) or []

    async def get_devices(self, subnet):
        new_devices = dict(self.config_entry.options)
        check_counter = 0
        devices_count = 0

        for (ip, mac) in Scanner.get_devices(subnet):
            draft_device = await self.create_draft_device(ip, mac)
            new_devices[draft_device.id] = {
                "ip": ip,
                "mac": mac,
            }
            devices_count += 1

            check_counter += 1
            if check_counter % 30 == 0:
                logger.info(f'Checked {check_counter} devices.')
                logger.info(f'Found {devices_count} devices.')

        return new_devices

    async def async_step_discovery_done(self, user_input=None):
        # logger.info(f'{len(self.discovered_devices)} devices found.')
        devices = {
            **dict(self.config_entry.options),
            **self.discovered_devices
        }

        self.reload()
        return self.async_create_entry(title="", data=devices)

    @callback
    def async_remove(self):
        """Clean up resources or tasks associated with the flow."""
        if self.discovery_task:
            self.discovery_task.cancel()

    async def async_step_add_device(self, user_input=None):
        if user_input is not None:
            device, device_info = await self._create_device(user_input)
            devices = dict(self.config_entry.options)
            devices[device.id] = {
                "pin": user_input["pin"],
                **device_info.to_dict(),
            }

            # Schedule reload after this flow completes
            self.reload()
            return self.async_create_entry(title="", data=devices)

        return self.async_show_form(
            step_id="add_device",
            data_schema=vol.Schema({
                vol.Required("ip"): str,
                vol.Required("pin"): str,
            })
        )

    async def create_draft_device(self, ip, mac):
        device_registry = dr.async_get(self.hass)
        return device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            identifiers={(self.config_entry.domain, mac)},
            name=f"Draft {ip} - {mac}",
            manufacturer="Somfy",
            configuration_url=f"https://{ip}",
        )

    async def _create_device(self, user_input) -> Tuple[DeviceEntry, Device]:
        device_registry = dr.async_get(self.hass)
        client = SomfyPoeBlindClient("Draft", user_input["ip"], user_input["pin"], lambda _: None)
        await self.hass.async_add_executor_job(client.login)
        device_info = await self.hass.async_add_executor_job(client.get_info)

        device = device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            identifiers={(self.config_entry.domain, device_info.mac)},
            name=device_info.name or "Untitled",
            manufacturer="Somfy",
            model=device_info.model,
            configuration_url=f"https://{device_info.ip}",
        )

        return device, device_info

    async def async_step_remove_device(self, user_input=None):
        choices, device_by_id = await self.get_device_choices()
        if not choices:
            return self.async_abort(reason="No devices")

        if user_input is not None:
            device_id = user_input["device"]
            await self.remove_device_by_id(device_id)
            self.reload()

            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="remove_device",
            data_schema=vol.Schema({
                vol.Required("device"): vol.In(choices)
            })
        )

    async def get_device_by_id(self, device_id):
        device_registry = dr.async_get(self.hass)
        return device_registry.async_get(device_id)

    async def remove_device_by_id(self, device_id: int):
        device_registry = dr.async_get(self.hass)
        entity_registry = er.async_get(self.hass)

        # Get the device
        device = device_registry.async_get(device_id)
        if not device:
            raise ValueError(f"Device with ID {device_id} not found")

        # Find all entities linked to this device
        linked_entities = [
            entry for entry in entity_registry.entities.values()
            if entry.device_id == device_id
        ]

        # Remove all entities first
        for entity in linked_entities:
            entity_registry.async_remove(entity.entity_id)

        # Now you can remove the device
        device_registry.async_remove_device(device_id)

    async def async_step_edit_device(self, user_input=None):
        choices, device_by_id = await self.get_device_choices()
        if not choices:
            return self.async_abort(reason="No devices")

        if user_input is not None:
            self._editing_device_id = user_input["device"]
            return await self.async_step_edit_device_details()

        return self.async_show_form(
            step_id="edit_device",
            data_schema=vol.Schema({
                vol.Required("device"): vol.In(choices)
            })
        )

    async def async_step_edit_device_details(self, user_input=None):
        device_id = self._editing_device_id
        current_devices = dict(self.config_entry.options)
        current_data = current_devices.get(device_id, {})
        is_draft = current_data.get("pin") is None

        if user_input is not None:
            # Update only the selected device
            current_devices[device_id] = {
                **current_data,
                "ip": user_input["ip"],
                "pin": user_input["pin"],
            }

            logger.info(user_input)
            if is_draft:
                logger.info(f'Draft device with IP {current_data.get("ip")} was replaced')
                await self.remove_device_by_id(device_id)

                device, device_info = await self._create_device(user_input)
                current_devices.pop(device_id, None)
                current_devices[device.id] = {
                    "pin": user_input["pin"],
                    **device_info.to_dict(),
                }

            self.reload()

            return self.async_create_entry(title="", data=current_devices)

        return self.async_show_form(
            step_id="edit_device_details",
            data_schema=vol.Schema({
                vol.Required("ip", default=current_data.get("ip", "")): str,
                vol.Required("pin", default=current_data.get("pin", "")): str,
            })
        )

    async def async_step_edit_settings(self, user_input=None):
        if user_input is not None:
            # Save the updated options
            return self.async_create_entry(
                title="",
                data={"subnet": user_input["subnet"]}
            )

        return self.async_show_form(
            step_id="edit_settings",
            data_schema=vol.Schema({
                vol.Required("subnet", default=self.config_entry.data.get("subnet")): str,
            })
        )

    async def async_step_clear_devices(self, user_input=None):
        if user_input is not None:
            self.hass.config_entries.async_update_entry(
                self.config_entry, options={}
            )

            # Also remove devices from the device registry
            device_registry = dr.async_get(self.hass)
            for device_id in list(device_registry.devices):
                device = device_registry.devices[device_id]
                if self.config_entry.entry_id in device.config_entries:
                    device_registry.async_remove_device(device.id)

            # Reload the config entry to apply changes
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)

            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="clear_devices",
            data_schema=vol.Schema({
                vol.Required("confirm"): bool
            })
        )
