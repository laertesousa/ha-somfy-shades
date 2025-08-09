import logging
import asyncio

# Configure logging to stdout at INFO level
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

logger = logging.getLogger("ha-somfy-shades")
print("Testing scanner")

from somfy.classes.Scanner import Scanner

scanner = Scanner("10.0.7.0/24", True, "http://localhost:5001")
async def test():
    logger.info(f"Testing scanner")
    async for (ip, mac) in scanner.get_devices():
        logger.info(f"found ip: {ip} - {mac}")


asyncio.run(test())

# test_ip = "10.0.7.117"
# mac_address = Scanner.ping_and_get_mac(test_ip)
# print(test_ip, mac_address, Scanner.get_hostname(test_ip))
# print(Scanner.is_mac_match(mac_address))
