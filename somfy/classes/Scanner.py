import logging
import ipaddress
import re
import subprocess

logger = logging.getLogger("Network Scanner")
SOMFY_MAC_PREFIXES = [
    "4C:C2:06"
]

class Scanner:
    @classmethod
    def get_devices(cls, subnet_str: str):
        logger.info("Searchin for devices in %s", subnet_str)

        check_count = 0
        found_count = 0
        for ip in ipaddress.IPv4Network(subnet_str).hosts():
            ip_str = str(ip)
            mac_address = cls.ping_and_get_mac(ip_str)
            if mac_address and cls.is_mac_match(mac_address):
                found_count += 1
                yield ip_str, mac_address

            check_count += 1
            if check_count % 25 == 0:
                logger.info(f"Checked {check_count} ips.  Found {found_count} ips.")

    @classmethod
    def is_mac_match(cls, mac_address: str):
        for prefix in SOMFY_MAC_PREFIXES:
            if mac_address.startswith(prefix):
                return True

        return False

    @classmethod
    def ping_and_get_mac(cls, ip):
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
        return cls.get_mac(ip)

    @classmethod
    def get_mac(cls, ip: str) -> str | None:
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
