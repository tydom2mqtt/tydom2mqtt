"""Dump everything a Tydom gateway exposes locally, and what tydom2mqtt reads.

Connects like tydom2mqtt (local digest auth + websocket), queries the
configuration / metadata / data endpoints, saves each raw JSON response and
prints a per-device summary: parent device -> endpoints (name, usage) ->
data elements, flagging what tydom2mqtt handles.

Credentials are read from a flat ``KEY: value`` file (e.g. a copy of the
add-on YAML options) or from the TYDOM_MAC / TYDOM_PASSWORD / TYDOM_IP env vars.
The password is never printed.

    python tools/tydom_discover.py --options ~/tydom-options.yaml --out tydom-dump
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from tydom import MessageHandler as mh  # noqa: E402
from tydom.TydomClient import TydomClient  # noqa: E402

ENDPOINTS = [
    "/info",
    "/configs/file",
    "/devices/meta",
    "/devices/cmeta",
    "/devices/data",
    "/areas/meta",
    "/areas/data",
    "/groups/file",
    "/moments/file",
    "/scenarios/file",
]

# Elements tydom2mqtt reads, per Tydom usage (mirrors MessageHandler)
HANDLED_ELEMENTS = {
    "shutter": mh.deviceCoverKeywords,
    "klineShutter": mh.deviceCoverKeywords,
    "awning": mh.deviceCoverKeywords,
    "window": mh.deviceDoorKeywords,
    "windowFrench": mh.deviceDoorKeywords,
    "windowSliding": mh.deviceDoorKeywords,
    "klineWindowFrench": mh.deviceDoorKeywords,
    "klineWindowSliding": mh.deviceDoorKeywords,
    "belmDoor": mh.deviceDoorKeywords + mh.deviceAutomaticDoorKeywords,
    "klineDoor": mh.deviceDoorKeywords + mh.deviceAutomaticDoorKeywords,
    "light": mh.deviceLightKeywords,
    "garage_door": mh.deviceGaragelKeywords,
    "gate": mh.deviceGaragelKeywords,
    "boiler": mh.deviceBoilerKeywords,
    "electric": mh.deviceBoilerKeywords,
    "sensorThermo": mh.deviceSensorsKeywords,
    "sensorSun": mh.deviceSensorsKeywords,
    "alarm": mh.deviceAlarmKeywords,
    "sensorDFR": mh.deviceSmokeKeywords,
}


def read_options(path):
    options = {}
    if path:
        for line in Path(path).expanduser().read_text().splitlines():
            key, sep, value = line.partition(":")
            if sep and not line.lstrip().startswith("#"):
                options[key.strip()] = value.split(" #")[0].strip().strip("'\"")
    for key in ("TYDOM_MAC", "TYDOM_PASSWORD", "TYDOM_IP"):
        options.setdefault(key, os.getenv(key, ""))
    return options


async def query(client, uri, timeout):
    """Send GET uri and return the decoded body of its response."""
    await client.send_message("GET", uri)
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            return None
        try:
            raw = await asyncio.wait_for(client.connection.recv(), remaining)
        except asyncio.TimeoutError:
            return None
        raw = raw[len(client.cmd_prefix) :] if client.cmd_prefix else raw
        if not raw.startswith(b"HTTP/"):
            continue  # unsolicited push (PUT /devices/data, ...)
        head = raw.split(b"\r\n\r\n", 1)[0].decode(errors="replace")
        if f"Uri-Origin: {uri}" not in head:
            continue  # answer to another request
        body = mh.MessageHandler.response_from_bytes(raw)
        try:
            return json.loads(body)
        except ValueError:
            return body.decode(errors="replace")


def summarize(results):
    config = results.get("/configs/file") or {}
    data = results.get("/devices/data") or []
    meta = results.get("/devices/meta") or []

    elements = {}
    for device in data if isinstance(data, list) else []:
        for endpoint in device.get("endpoints", []):
            elements[(device["id"], endpoint["id"])] = endpoint.get("data", [])

    enums = {}
    for device in meta if isinstance(meta, list) else []:
        for endpoint in device.get("endpoints", []):
            for item in endpoint.get("metadata", []):
                if item.get("enum_values"):
                    enums[(device["id"], endpoint["id"], item["name"])] = item[
                        "enum_values"
                    ]

    by_device = {}
    for endpoint in config.get("endpoints", []):
        by_device.setdefault(endpoint["id_device"], []).append(endpoint)

    for device_id, endpoints in sorted(by_device.items()):
        print(f"\n=== device {device_id} ({len(endpoints)} endpoint(s))")
        for endpoint in endpoints:
            usage = endpoint.get("last_usage")
            main = " [main]" if endpoint["id_endpoint"] == device_id else ""
            supported = (
                "" if usage in mh.supported_usages else "  <-- UNSUPPORTED usage"
            )
            print(
                f"  endpoint {endpoint['id_endpoint']}{main}: name={endpoint.get('name')!r}"
                f" first_usage={endpoint.get('first_usage')} last_usage={usage}{supported}"
            )
            handled = HANDLED_ELEMENTS.get(usage, [])
            for item in elements.get((device_id, endpoint["id_endpoint"]), []):
                flag = "read" if item["name"] in handled else "IGNORED"
                enum = enums.get((device_id, endpoint["id_endpoint"], item["name"]))
                enum_txt = f" enum={enum}" if enum else ""
                print(
                    f"      {item['name']} = {item.get('value')!r}"
                    f" ({item.get('validity')}) -> {flag}{enum_txt}"
                )


async def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--options", help="flat KEY: value file (add-on YAML)")
    parser.add_argument("--out", default="tydom-dump", help="output directory")
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()

    options = read_options(args.options)
    if not options["TYDOM_MAC"] or not options["TYDOM_PASSWORD"]:
        sys.exit("TYDOM_MAC and TYDOM_PASSWORD are required")
    if not options["TYDOM_IP"]:
        sys.exit("TYDOM_IP (local gateway IP) is required: this tool stays local")

    client = TydomClient(
        mac=options["TYDOM_MAC"],
        password=options["TYDOM_PASSWORD"],
        polling_interval=300,
        thermostat_cool_mode_temp_default=26,
        thermostat_heat_mode_temp_default=16,
        host=options["TYDOM_IP"],
    )
    await client.connect()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    results = {}
    try:
        for uri in ENDPOINTS:
            result = await query(client, uri, args.timeout)
            results[uri] = result
            status = "no answer" if result is None else "ok"
            print(f"{uri}: {status}")
            if result is not None:
                name = uri.strip("/").replace("/", "_") + ".json"
                (out / name).write_text(
                    json.dumps(result, indent=2, ensure_ascii=False)
                )
    finally:
        await client.disconnect()

    summarize(results)
    print(f"\nRaw responses saved in {out.resolve()}")


if __name__ == "__main__":
    asyncio.run(main())
