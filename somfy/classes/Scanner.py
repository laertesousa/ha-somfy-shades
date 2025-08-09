import logging
import ipaddress
import re
import subprocess
import aiohttp

logger = logging.getLogger("Network Scanner")
SOMFY_MAC_PREFIXES = [
    "4C:C2:06"
]

class Scanner:
    def __init__(self, subnet, use_mac_mock = False, base_url: str = "http://host.docker.internal:5001"):
        self.subnet = subnet
        self.use_mac_mock = use_mac_mock
        self.base_url = base_url


    async def get_devices(self):
        logger.info("Searchin for devices in %s", self.subnet)

        check_count = 0
        found_count = 0
        for ip in ipaddress.IPv4Network(self.subnet).hosts():
            ip_str = str(ip)
            # Use for testing
            # if ip_str not in ['10.0.7.117']:
            #     continue

            mac_address = await self.ping_and_get_mac(ip_str)
            if mac_address and self.is_mac_match(mac_address):
                found_count += 1
                yield ip_str, mac_address

            check_count += 1
            if check_count % 25 == 0:
                logger.info(f"Checked {check_count} ips.  Found {found_count} ips.")

    @staticmethod
    def is_mac_match(mac_address: str):
        for prefix in SOMFY_MAC_PREFIXES:
            if mac_address.startswith(prefix):
                return True

        return False

    async def ping_and_get_mac(self, ip):
        logger.info(f"Pinging {ip}")
        try:
            subprocess.run(
                ["ping", "-c", "1", "-W", "1", ip],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True
            )
        except subprocess.CalledProcessError:
            return None

        logger.info(f"Find mac for {ip}")
        if self.use_mac_mock:
            return await self.get_mac_from_host_async(ip)
        else:
            return self.get_mac(ip)

    @staticmethod
    def get_mac(ip: str) -> str | None:
        try:
            output = subprocess.check_output(["arp", "-n", ip]).decode()
        except subprocess.CalledProcessError:
            return None

        logger.info(f"get_mac: {output}")
        # Match MAC parts that may be 1 or 2 hex digits
        m = re.search(r"(([0-9a-fA-F]{1,2}:){5}[0-9a-fA-F]{1,2})", output)
        if not m:
            return None

        mac_raw = m.group(1)
        # Normalize to 2-digit hex per octet
        mac_normalized = ":".join(part.zfill(2) for part in mac_raw.split(":")).lower()
        return mac_normalized.upper()

    async def get_mac_from_host_async(self, ip: str) -> str | None:
        """Call host ARP endpoint (async) and return MAC or None."""
        # session = aiohttp_client.async_get_clientsession(hass)
        session = aiohttp.ClientSession()
        url = f"{self.base_url}/arp/{ip}"
        try:
            timeout = aiohttp.ClientTimeout(total=2)
            async with session.get(url, timeout=timeout) as resp:
                if resp.status != 200:
                    logger.info("ARP endpoint %s returned HTTP %s", url, resp.status)
                    return None

                data = await resp.json(content_type=None)
                logger.info(f"ARP endpoint {url} returned {data}")
                if isinstance(data, list) and data:
                    mac = data[0].get("mac")
                    return mac.upper() if mac else None
                return None
        except Exception as e:
            logger.info("ARP request failed %s: %s", url, e)
            return None
        finally:
            await session.close()
