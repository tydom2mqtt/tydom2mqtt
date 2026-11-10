#!/usr/bin/env python3
"""Docker healthcheck script for tydom2mqtt."""

import http.client
import os
import sys


def main():
    port = int(os.getenv("HEALTH_PORT", 8080))
    try:
        conn = http.client.HTTPConnection("localhost", port, timeout=5)
        conn.request("GET", "/health")
        response = conn.getresponse()
        conn.close()
        sys.exit(0 if response.status == 200 else 1)
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
