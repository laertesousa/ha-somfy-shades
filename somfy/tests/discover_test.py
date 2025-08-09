import logging

from ..classes.SomfyPoeBlindClient import SomfyPoeBlindClient

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    # print(SomfyPoeBlindClient.get_possible_subnet_address())
    devices = SomfyPoeBlindClient.discover_devices('10.0.7.0/24')
    if not devices:
        print("No Somfy devices found.")
    else:
        for d in devices:
            print(f"✅ Somfy device detected: IP = {d.ip}, MAC = {d.mac}")

    # is_device = SomfyPoeBlindClient.ping('192.168.6.128')
    # print(is_device)
