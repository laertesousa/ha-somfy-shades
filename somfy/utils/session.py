import ssl

import requests

from ..classes.HttpAdapter import HttpAdapter


def get_legacy_session():
    ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    ctx.options |= 0x4  # OP_LEGACY_SERVER_CONNECT
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    _session = requests.session()
    _session.mount('https://', HttpAdapter(ctx))
    return _session