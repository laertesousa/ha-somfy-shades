import ipaddress
import logging
import socket
from typing import List

from ..dtos.somfy_objects import Status, Direction, Device
from ..utils.session import get_legacy_session

logger = logging.getLogger(__name__)

SOMFY_MAC_PREFIXES = [
    "4C:C2:06",
]

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

        logger.info("Cookies: %s", self.session.cookies)
        logger.info("%s Authenticated. Session ID: %s", self._get_log_prefix(self), self.session.cookies["sessionId"])

    @property
    def is_logged_in(self):
        return self.session is not None

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

    def send_command(self, command, priority=0, position=None):
        logger.info("Session: %s", self.session)
        if self.session is not None:
            logger.info("Cookies: %s", self.session.cookies)

        params = {"priority": priority}
        if position is not None:
            params["position"] = position

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
            self.on_failure(e)
            return None

        return response.json()

    def get_status(self) -> Status:
        data = self.send_command("status.position")
        logger.info(f"Status Response: {data}")
        status = Status.from_data(data)
        logger.info(f"Status object: {status}")
        if status.error is not None:
            logger.debug("%s Status, %s", self._get_log_prefix(self), status)
            logger.info("%s Current direction, %s", self._get_log_prefix(self), status.get_direction())

        return status

    def down(self):
        self.send_command("move.down")
        logger.info("%s Moving Down", self._get_log_prefix(self))

    def up(self):
        self.send_command("move.up")
        logger.info("%s Moving Up", self._get_log_prefix(self))

    def move(self, position: int):
        logger.info("%s Moving to %s", self._get_log_prefix(self), position)
        self.send_command(f"move.to", position=position)

    def stop(self):
        self.send_command("move.stop")
        logger.info("%s Stopping", self._get_log_prefix(self))

    def toggle(self):
        status = self.get_status()
        if status.is_moving():
            self.stop()
        elif status.get_direction() == Direction.up:
            self.down()
        else:
            self.up()

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
