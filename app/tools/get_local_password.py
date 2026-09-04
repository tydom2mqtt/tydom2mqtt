#!/usr/bin/env python3
"""Read a Tydom hub's *local* password by pairing with it once.

tydom2mqtt normally does this on its own: start it with no TYDOM_PASSWORD in
local mode, press the hub's button when asked, and it stores the password for
you. This tool is the manual equivalent, useful to inspect the value or to
recover it without running the app.

Why the password matters
------------------------
The password the Delta Dore cloud API returns for a gateway is *not* the one
that gateway expects on a direct LAN connection: they are two different
secrets. Using the cloud one locally fails with a permanent HTTP 401 that
looks exactly like a misconfiguration.

Usage
-----
    python tools/get_local_password.py --host 192.168.1.33 --mac 001A25XXXXXX
"""

import argparse
import asyncio
import os
import ssl
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tydom.TydomClient import TydomClient, PAIRING_RETRY_DELAY  # noqa: E402


async def read_password(host, mac, timeout):
    ssl_context = ssl._create_unverified_context()
    ssl_context.options |= 0x4  # OP_LEGACY_SERVER_CONNECT

    deadline = time.monotonic() + timeout
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        password = await TydomClient.read_local_password(host, mac, ssl_context)
        if password is not None:
            return password
        print(f"  attempt {attempt}: hub still locked, press its button now...")
        await asyncio.sleep(PAIRING_RETRY_DELAY)

    return None


def main():
    parser = argparse.ArgumentParser(
        description="Read a Tydom hub's local password (one-time pairing)."
    )
    parser.add_argument("--host", required=True, help="gateway IP address on your LAN")
    parser.add_argument(
        "--mac", required=True, help="gateway MAC address, e.g. 001A25XXXXXX"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="how long to wait for the button press (seconds)",
    )
    args = parser.parse_args()

    print(f"Connecting to {args.host} ({args.mac}).")
    print(
        "Press the button on the Tydom hub now; waiting up to "
        f"{args.timeout}s for its pairing window.\n"
    )

    password = asyncio.run(read_password(args.host, args.mac, args.timeout))

    if password is None:
        print(
            "\nCould not read the password. Make sure you pressed the "
            "button on the hub, and that the MAC and IP are correct."
        )
        sys.exit(1)

    print(f"\nLocal password: {password}")
    print(
        "Do not use the Delta Dore cloud password for a local connection: "
        "it is a different secret."
    )


if __name__ == "__main__":
    main()
