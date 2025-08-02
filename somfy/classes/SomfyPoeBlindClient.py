import ipaddress
import logging
import socket
import urllib3
from typing import List
from enum import Enum

from ..dtos.somfy_objects import Status, Direction, Device
from ..utils.session import get_legacy_session

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)

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
    def ping(ip):
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

    @staticmethod
    def get_possible_subnet_address():
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        # assume /24 subnet
        network = ipaddress.IPv4Network(local_ip + '/24', strict=False)

        return str(network)

    @classmethod
    def discover_devices(cls, subnet_str=None) -> List[Device]:
        if subnet_str is None:
            subnet_str = cls.get_possible_subnet_address()

        logger.info("%s search for devices in %s", cls._get_log_prefix(), subnet_str)

        devices = []
        # This is slower than scanning the network for actual used IPs but more reliable to find
        # Somfy devices. Potential optimization is to retrieve existing IPs using ARP first, then
        # scan the other IPs for any missing device with the slower method.
        for ip in ipaddress.IPv4Network(subnet_str).hosts():
            logger.info('checking %s', ip)
            if ip and cls.ping(ip):
                devices.append(Device(ip=str(ip), mac=''))

        return devices
