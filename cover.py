import logging
from homeassistant.components.cover import CoverEntity, CoverEntityFeature
from homeassistant.core import callback
from .const import DOMAIN

from .somfy.classes.SomfyPoeBlindClient import SomfyPoeBlindClient
from .somfy.dtos.somfy_objects import Direction

logger = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    entry_id = entry.entry_id
    data = hass.data[DOMAIN][entry.entry_id]
    def on_failure(e):
        logger.error('Somfy callback error: %s', e)
        hass.async_create_task(
            hass.config_entries.async_reload(entry_id)
        )

    client = SomfyPoeBlindClient(data["name"], data["ip"], data["pin"], on_failure)
    await hass.async_add_executor_job(client.login)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "config": data
    }

    async_add_entities([SomfyCover(data, client)])

class SomfyCover(CoverEntity):
    supported_features = (
            CoverEntityFeature.OPEN |
            CoverEntityFeature.CLOSE |
            CoverEntityFeature.STOP |
            CoverEntityFeature.SET_POSITION
    )

    def __init__(self, data, client):
        self._client = client
        self._name = data["name"]
        self._ip = data["ip"]
        self._pin = data["pin"]
        self._id = f"somfy_cover_{self._ip.replace('.', '_')}"

        # Generate a unique_id based on IP address or another unique identifier
        self._attr_unique_id = self._id
        self._attr_name = self._name
        self._position = None
        self._is_closing = None
        self._is_opening = None

    @property
    def device_info(self):
        """Information about this entity/device."""
        return {
            "identifiers": {(DOMAIN, self._id)},
            # If desired, the name for the device could be different to the entity
            "name": self._name,
            "sw_version": "0.0",
            "model": "Somfy",
            "manufacturer": "Clara Shades",
        }

    @property
    def available(self) -> bool:
        return True

    @property
    def current_cover_position(self):
        """Return the current position of the cover."""
        return self._position

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed, same as position 0."""
        return self._position == 0

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing or not."""
        return self._is_closing

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening or not."""
        return self._is_opening

    async def async_open_cover(self, **kwargs):
        await self.hass.async_add_executor_job(self._client.up)
        self._is_closing = False
        self._is_opening = True
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs):
        await self.hass.async_add_executor_job(self._client.down)
        self._is_closing = True
        self._is_opening = False
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs):
        await self.hass.async_add_executor_job(self._client.stop)
        self._is_closing = False
        self._is_opening = False
        self.async_write_ha_state()

    async def async_update(self):
        # await self.hass.async_add_executor_job(self._client.login)
        logger.info("update triggered: %s:%s", self._is_closing, self._is_opening)
        if self._is_closing is False and self._is_opening is False:
            return

        status = await self.hass.async_add_executor_job(self._client.get_status)
        logger.debug(f"Shade status - {status}")
        if status is not None and status.error is None:
            # This is basic. You can refine it based on actual status/direction data
            self._position = 100 - status.position.value
            self._is_closing = status.is_moving() and status.get_direction() == Direction.down
            self._is_opening = status.is_moving() and status.get_direction() == Direction.up
            self.async_write_ha_state()
        else:
            logger.warning("Unable to retrieve shade status")

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        logger.debug(f"setting position {kwargs}")
        position = kwargs.get("position")
        await self.hass.async_add_executor_job(self._client.move, 100 - position)