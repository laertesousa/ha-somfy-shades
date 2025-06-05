import logging

import urllib3

from src.classes.SomfyPoeBlindClient import SomfyPoeBlindClient

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO)
somfy = SomfyPoeBlindClient("Test Blind", "192.168.6.128", "8217")

somfy.login()
somfy.toggle()

