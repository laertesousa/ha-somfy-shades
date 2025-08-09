from homeassistant.helpers.config_validation import configuration_url
from homeassistant.helpers.device_registry import async_get as get_device_registry, DeviceInfo


async def get_devices_for_entry(hass, config_entry):
    device_registry = get_device_registry(hass)

    return [
        device for device in device_registry.devices.values()
        if config_entry.entry_id in device.config_entries
    ]

def get_device_by_name(hass, name: str):
    device_registry = get_device_registry(hass)

    for device in device_registry.devices.values():
        if device.name == name:
            return device

    return None  # Not found

def get_device_options(config_entry, device_id):
    return config_entry.options.get(device_id)

def build_device_info(device, ip = None):
    configuration_url = None
    if ip:
        configuration_url = f"https://{ip}"

    return DeviceInfo(
        identifiers=device.identifiers,
        name=device.name,
        manufacturer=device.manufacturer,
        model=device.model,
        sw_version=device.sw_version,
        configuration_url=configuration_url
    )

