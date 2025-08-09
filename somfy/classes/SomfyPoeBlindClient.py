import logging

import urllib3
from typing import Optional, Callable
from enum import Enum

from ..dtos.somfy_objects import Status, Device
from ..utils.session import get_legacy_session

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger("Somfy Client")

SOMFY_MAC_PREFIXES = [
    "4C:C2:06",
]

class LimitSetting(Enum):
    up = 'up'
    down = 'down'

class SomfyPoeBlindClient:
    def __init__(self, name, ip, password, on_failure):
        self.session = None
        self.name = name
        self.ip = ip
        self.password = password
        self.on_failure = on_failure

    @classmethod
    def init_with_device(cls, device: dict, on_failure: Optional[Callable] = None):
        if on_failure:
            return cls(device["name"], device["ip"], device["pin"], on_failure)

        return cls(device["name"], device["ip"], device["pin"], lambda: None)

    @staticmethod
    def _get_log_prefix(instance=None):
        if instance is None:
            return "[Somfy Poe Blind Client]"

        return f'[Somfy Poe Blind Client][{instance.name}]'

    def login(self):
        self.session = get_legacy_session()
        login_response = self.session.post(
            f"https://{self.ip}/",
            data={"password": self.password},
            verify=False
        )

        if "sessionId" not in self.session.cookies:
            logger.error("%s Login failed. No sessionId found.", self._get_log_prefix(self))
            logger.info("%s Response: %s", self._get_log_prefix(self), login_response.text)
            return

        logger.debug("Cookies: %s", self.session.cookies)
        logger.debug("%s Authenticated. Session ID: %s", self._get_log_prefix(self), self.session.cookies["sessionId"])

    @staticmethod
    def ping(ip) -> bool:
        session = get_legacy_session()
        try:
            response = session.post(
                f"https://{ip}",
                data="",
                verify=False,
                # Anything below 1.2s we will get a false negative from Somfy Device.
                timeout=1.2
            )
        except Exception as e:
            logger.debug(e)
            return False


        return response.status_code == 200 and 'SOMFY PoE WebGUI' in response.text

    def send_command(
        self, 
        command, 
        priority=None, position=None, direction=None, duration=None, end_limit: str = None, mode: str = None, wink: bool = None
    ):
        logger.debug("%s start command: %s", self._get_log_prefix(self), command)
        logger.debug("%s send_command - Session:", self._get_log_prefix(self), command)

        params = {}
        if priority is not None:
            params["priority"] = priority
        if position is not None:
            params["position"] = position
        if direction is not None:
            params["direction"] = direction
        if duration is not None:
            params["duration"] = duration
        if end_limit is not None:
            params["endLimit"] = end_limit
        if mode is not None:
            params["mode"] = mode
        if wink is not None:
            params["wink"] = wink

        command_payload = {
            "method": command,
            "params": params,
            "id": 1
        }
        try:
            response = self.session.post(
                f"https://{self.ip}/req",
                headers={"Content-Type": "application/json"},
                json=command_payload,
                verify=False
            )
        except Exception as e:
            logger.error("%s failed command: %s", self._get_log_prefix(self), command)
            self.on_failure(e)
            return None

        logger.debug("%s completed command: %s", self._get_log_prefix(self), command)

        return response.json()

    def get_status(self) -> Status:
        data = self.send_command("status.position")
        logger.debug(f"Status Response: {data}")
        status = Status.from_data(data)
        logger.debug(f"Status object: {status}")
        if status.error is not None:
            logger.warning("%s Status, %s", self._get_log_prefix(self), status)

        return status

    def get_info(self) -> Device:
        data = self.send_command("status.info")
        device = Device.from_data(data['info'])
        device.ip = self.ip

        return device

    def down(self):
        self.send_command("move.down", priority=0)

    def up(self):
        self.send_command("move.up", priority=0)

    def move(self, position: int):
        self.send_command(f"move.to", priority=1, position=position)

    def move_relative(self, direction: str, duration: int):
        self.send_command("settings.moverelative", direction=direction, duration=duration)

    def stop(self):
        self.send_command("move.stop", priority=1)
    
    def set_limit(self, setting: LimitSetting):
        self.send_command("settings.endlimit", end_limit=setting, mode="atcurrentposition")
