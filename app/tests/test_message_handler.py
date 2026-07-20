import asyncio
import json
from unittest.mock import MagicMock

import pytest

from tydom.MessageHandler import (
    MessageHandler,
    device_metadata,
    device_name,
    device_type,
)


@pytest.fixture(autouse=True)
def _clean_registries():
    # These dicts are shared module-level state (mirroring the app's own
    # long-lived process), so tests must not leak entries into each other.
    device_metadata.clear()
    device_name.clear()
    device_type.clear()
    yield
    device_metadata.clear()
    device_name.clear()
    device_type.clear()


def make_handler():
    return MessageHandler(
        incoming_bytes=b"", tydom_client=MagicMock(), mqtt_client=MagicMock()
    )


# Regression guard: an endpoint `metadata` push (device capability
# description) used to fall through to parse_devices_data -> parse_endpoint_data,
# which assumed every endpoint has a "data" key and raised KeyError('data').
def test_metadata_push_does_not_crash_for_non_garage_device():
    device_type["55_100"] = "light"
    device_name["55_100"] = "Kitchen Light"

    payload = [
        {
            "id": 100,
            "endpoints": [
                {
                    "id": 55,
                    "error": 0,
                    "metadata": [
                        {
                            "name": "levelCmd",
                            "type": "string",
                            "permission": "w",
                            "enum_values": ["ON", "OFF", "TOGGLE"],
                        }
                    ],
                }
            ],
        }
    ]

    handler = make_handler()
    asyncio.run(handler.parse_response(json.dumps(payload)))

    assert device_metadata["55_100"]["levelCmd"] == ["ON", "OFF", "TOGGLE"]
    # Not a garage/gate device: no discovery config should be (re)published.
    handler.mqtt_client.mqtt_client.publish.assert_not_called()


def test_metadata_push_captures_toggle_only_levelcmd():
    device_type["1784555123_1784555123"] = "garage_door_horizontal"
    device_name["1784555123_1784555123"] = "Gate 1"

    payload = [
        {
            "id": 1784555123,
            "endpoints": [
                {
                    "id": 1784555123,
                    "error": 0,
                    "metadata": [
                        {
                            "name": "levelCmd",
                            "type": "string",
                            "permission": "w",
                            "validity": "INFINITE",
                            "shared": False,
                            "enum_values": ["TOGGLE"],
                        },
                        {
                            "name": "thermicDefect",
                            "type": "boolean",
                            "permission": "r",
                        },
                        {
                            "name": "localisation",
                            "type": "string",
                            "permission": "w",
                            "enum_values": ["START"],
                        },
                    ],
                }
            ],
        }
    ]

    handler = make_handler()
    asyncio.run(handler.parse_response(json.dumps(payload)))

    assert device_metadata["1784555123_1784555123"]["levelCmd"] == ["TOGGLE"]
    assert device_metadata["1784555123_1784555123"]["localisation"] == ["START"]


def test_metadata_arrival_republishes_garage_discovery_as_toggle():
    unique_id = "1784555123_1784555123"
    device_type[unique_id] = "garage_door_horizontal"
    device_name[unique_id] = "Gate 1"

    payload = [
        {
            "id": 1784555123,
            "endpoints": [
                {
                    "id": 1784555123,
                    "error": 0,
                    "metadata": [
                        {"name": "levelCmd", "enum_values": ["TOGGLE"]},
                    ],
                }
            ],
        }
    ]

    handler = make_handler()
    asyncio.run(handler.parse_response(json.dumps(payload)))

    calls = handler.mqtt_client.mqtt_client.publish.call_args_list
    assert len(calls) == 2
    # The old ON/OFF/STOP Cover entity (published before metadata confirmed
    # this device is toggle-only) is cleared out...
    assert calls[0][0][:2] == (f"homeassistant/cover/tydom/{unique_id}/config", "")
    # ...and replaced by a single-action button entity.
    topic, config_json = calls[1][0]
    assert topic == f"homeassistant/button/tydom/{unique_id}/config"
    config = json.loads(config_json)
    assert config["payload_press"] == "TOGGLE"


def test_metadata_with_real_enum_does_not_trigger_republish():
    # A genuine positional garage motor advertising a real multi-value enum:
    # the toggle-only determination never becomes True, so no republish is
    # needed the first time metadata is learned (still not "changed").
    unique_id = "42_42"
    device_type[unique_id] = "garage_door"
    device_name[unique_id] = "Real Garage Motor"

    payload = [
        {
            "id": 42,
            "endpoints": [
                {
                    "id": 42,
                    "error": 0,
                    "metadata": [
                        {"name": "levelCmd", "enum_values": ["OPEN", "CLOSE", "STOP"]},
                    ],
                }
            ],
        }
    ]

    handler = make_handler()
    asyncio.run(handler.parse_response(json.dumps(payload)))

    assert device_metadata[unique_id]["levelCmd"] == ["OPEN", "CLOSE", "STOP"]
    handler.mqtt_client.mqtt_client.publish.assert_not_called()
