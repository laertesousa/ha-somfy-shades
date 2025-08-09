import logging

# Configure logging to stdout at INFO level
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

print("Testing scanner")

from somfy.classes.Scanner import Scanner

for (ip, mac) in Scanner.get_devices("10.0.7.0/24"):
    print(f"found ip: {ip}:{mac}")


# test_ip = "10.0.7.117"
# mac_address = Scanner.ping_and_get_mac(test_ip)
# print(test_ip, mac_address, Scanner.get_hostname(test_ip))
# print(Scanner.is_mac_match(mac_address))
