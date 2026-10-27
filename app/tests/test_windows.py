import asyncio
import json
from unittest.mock import MagicMock

import pytest

from sensors.Opening import Opening
from sensors.Sensor import Sensor
from tydom import MessageHandler as message_handler_module
from tydom.MessageHandler import MessageHandler

DEVICE_ID = 1789228300
ENDPOINT_ID = 1789228300


def _published(mqtt):
    """Map of topic -> payload published through the mocked MQTT client."""
    return {
        call.args[0]: call.args[1] for call in mqtt.mqtt_client.publish.call_args_list
    }


def _parse_window(last_usage, data, name="Fenetre Cuisine"):
    mqtt = MagicMock()
    handler = MessageHandler(b"", MagicMock(cmd_prefix=""), mqtt)
    config = {
        "endpoints": [
            {
                "id_endpoint": ENDPOINT_ID,
                "id_device": DEVICE_ID,
                "name": name,
                "last_usage": last_usage,
            }
        ]
    }
    endpoint = {
        "id": ENDPOINT_ID,
        "error": 0,
        "data": [
            {"name": key, "validity": "upToDate", "value": value}
            for key, value in data.items()
        ],
    }
    asyncio.run(handler.parse_config_data(config))
    asyncio.run(handler.parse_endpoint_data(endpoint, DEVICE_ID))
    return _published(mqtt)


@pytest.fixture(autouse=True)
def _clean_device_cache():
    yield
    for cache in (
        "device_name",
        "device_type",
        "device_endpoint",
        "opening_groups",
        "endpoint_groups",
    ):
        getattr(message_handler_module, cache).clear()


# Regression: only the last element of a window used to be published, so the
# opening state could be missing in Home Assistant.
def test_kline_window_publishes_every_element_and_opening():
    published = _parse_window(
        "klineWindowFrench",
        {"openState": "OPEN_FRENCH", "intrusionDetect": True, "battDefect": False},
    )
    uid = f"{DEVICE_ID}_{ENDPOINT_ID}"

    for element in ("openstate", "intrusiondetect", "battdefect"):
        assert any(
            topic.endswith(f"/{element}_tydom_{uid}/config") for topic in published
        ), element

    opening_config = json.loads(
        published[f"homeassistant/binary_sensor/tydom/opening_tydom_{uid}/config"]
    )
    assert opening_config["device_class"] == "window"
    assert opening_config["device"]["name"] == "Fenetre Cuisine"
    assert published[f"binary_sensor/tydom/opening_tydom_{uid}/state"] == "ON"


# K-Line bays: each opening detector is a standalone Tydom device named
# "Ouvrant droit / gauche"; the window name comes from a windowFrench group
# (/configs/file) whose members are listed in /groups/file.
RIGHT, LEFT, SHUTTER = 11, 12, 13
KLINE_CONFIG = {
    "id_catalog": "x",
    "groups": [
        {"id": 500, "name": "Baie salon", "usage": "windowFrench", "group_all": False},
        {"id": 900, "name": "TOTAL", "usage": "shutter", "group_all": True},
    ],
    "endpoints": [
        {
            "id_device": RIGHT,
            "id_endpoint": RIGHT,
            "name": "Ouvrant droit",
            "first_usage": "window",
            "last_usage": "windowFrench",
        },
        {
            "id_device": LEFT,
            "id_endpoint": LEFT,
            "name": "Ouvrant gauche",
            "first_usage": "window",
            "last_usage": "windowFrench",
        },
        {
            "id_device": SHUTTER,
            "id_endpoint": SHUTTER,
            "name": "Baie Salon",
            "first_usage": "shutter",
            "last_usage": "shutter",
        },
    ],
}
KLINE_GROUPS = {
    "groups": [
        {
            "id": 500,
            "areas": [],
            "devices": [
                {"id": RIGHT, "endpoints": [{"id": RIGHT}]},
                {"id": LEFT, "endpoints": [{"id": LEFT}]},
            ],
        },
        {
            "id": 900,
            "areas": [],
            "devices": [
                {"id": SHUTTER, "endpoints": [{"id": SHUTTER}]},
            ],
        },
    ]
}


def _detector_data(device_id, open_state, validity="upToDate"):
    return {
        "id": device_id,
        "error": 0,
        "data": [
            {"name": "battDefect", "validity": "upToDate", "value": False},
            {"name": "intrusionDetect", "validity": validity, "value": False},
            {"name": "openState", "validity": validity, "value": open_state},
        ],
    }


def test_groups_file_response_is_routed():
    handler = MessageHandler(b"", MagicMock(cmd_prefix=""), MagicMock())
    asyncio.run(handler.parse_response(json.dumps(KLINE_CONFIG)))
    asyncio.run(handler.parse_response(json.dumps(KLINE_GROUPS, separators=(",", ":"))))
    assert message_handler_module.opening_groups == {"500": "Baie salon"}
    assert message_handler_module.endpoint_groups[f"{RIGHT}_{RIGHT}"] == ["500"]


def test_kline_detectors_published_on_their_window_group_device():
    mqtt = MagicMock()
    handler = MessageHandler(b"", MagicMock(cmd_prefix=""), mqtt)
    asyncio.run(handler.parse_config_data(KLINE_CONFIG))
    asyncio.run(handler.parse_groups_data(KLINE_GROUPS))
    asyncio.run(handler.parse_endpoint_data(_detector_data(RIGHT, "UNLOCKED"), RIGHT))
    asyncio.run(handler.parse_endpoint_data(_detector_data(LEFT, "LOCKED"), LEFT))
    published = _published(mqtt)

    for member, name, state in (
        (RIGHT, "Ouvrant droit", "ON"),
        (LEFT, "Ouvrant gauche", "OFF"),
    ):
        uid = f"{member}_{member}"
        opening = json.loads(
            published[f"homeassistant/binary_sensor/tydom/opening_tydom_{uid}/config"]
        )
        open_state = json.loads(
            published[f"homeassistant/sensor/tydom/openstate_tydom_{uid}/config"]
        )
        # One HA device per window, named after the Tydom group
        for config_payload in (opening, open_state):
            assert config_payload["device"]["identifiers"] == "tydom_window_group_500"
            assert config_payload["device"]["name"] == "Baie salon"
        # Unique ids unchanged, entities named after their detector
        assert opening["unique_id"] == f"opening_tydom_{uid}"
        assert opening["name"] == name
        assert open_state["name"] == f"{name} openState"
        assert published[f"binary_sensor/tydom/opening_tydom_{uid}/state"] == state


def test_detector_outside_window_group_stays_standalone():
    mqtt = MagicMock()
    handler = MessageHandler(b"", MagicMock(cmd_prefix=""), mqtt)
    asyncio.run(handler.parse_config_data(KLINE_CONFIG))
    asyncio.run(handler.parse_endpoint_data(_detector_data(RIGHT, "LOCKED"), RIGHT))
    opening = json.loads(
        _published(mqtt)[
            f"homeassistant/binary_sensor/tydom/opening_tydom_{RIGHT}_{RIGHT}/config"
        ]
    )
    assert opening["device"]["identifiers"] == f"{RIGHT}_{RIGHT}"
    assert opening["name"] is None


# An expired openState is not trusted: no opening state is published
def test_expired_open_state_not_published():
    mqtt = MagicMock()
    handler = MessageHandler(b"", MagicMock(cmd_prefix=""), mqtt)
    asyncio.run(handler.parse_config_data(KLINE_CONFIG))
    asyncio.run(handler.parse_groups_data(KLINE_GROUPS))
    asyncio.run(
        handler.parse_endpoint_data(_detector_data(RIGHT, "LOCKED", "expired"), RIGHT)
    )
    published = _published(mqtt)
    assert not any("opening_tydom" in topic for topic in published)


def test_door_opening_uses_door_class():
    published = _parse_window("klineDoor", {"openState": "LOCKED"})
    uid = f"{DEVICE_ID}_{ENDPOINT_ID}"
    opening_config = json.loads(
        published[f"homeassistant/binary_sensor/tydom/opening_tydom_{uid}/config"]
    )
    assert opening_config["device_class"] == "door"
    assert published[f"binary_sensor/tydom/opening_tydom_{uid}/state"] == "OFF"


# Names were only kept for known usages, so unsupported devices lost theirs.
def test_name_kept_for_unsupported_usage():
    _parse_window("someNewUsage", {}, name="Detecteur Garage")
    handler = MessageHandler(b"", MagicMock(cmd_prefix=""), None)
    assert handler.get_name_from_id(f"{ENDPOINT_ID}_{DEVICE_ID}") == "Detecteur Garage"


@pytest.mark.parametrize(
    "open_state,expected",
    [("LOCKED", "OFF"), ("UNLOCKED", "ON"), ("OPEN_HOPPER", "ON")],
)
def test_opening_state(open_state, expected):
    opening = Opening(
        tydom_attributes={"id": "1_1", "name": "Baie", "openState": open_state}
    )
    assert opening.state() == expected


def test_batt_defect_is_diagnostic_battery():
    payload = {"id": "1_1", "name": "Baie", "battDefect": False}
    sensor = Sensor(elem_name="battDefect", tydom_attributes_payload=payload)
    asyncio.run(sensor.setup())
    assert sensor.binary is True
    assert sensor.config["device_class"] == "battery"
    assert sensor.config["entity_category"] == "diagnostic"


def test_element_meta_overrides_device_wide_class():
    payload = {
        "id": "1_1",
        "name": "Sonde",
        "outTemperature": 12.5,
        "lightPower": 300,
        "element_meta": {
            "outTemperature": {
                "device_class": "temperature",
                "unit_of_measurement": "°C",
            },
            "lightPower": {"device_class": "power", "unit_of_measurement": "W"},
        },
    }
    temperature = Sensor(elem_name="outTemperature", tydom_attributes_payload=payload)
    power = Sensor(elem_name="lightPower", tydom_attributes_payload=payload)
    asyncio.run(temperature.setup())
    asyncio.run(power.setup())
    assert temperature.config["device_class"] == "temperature"
    assert power.config["device_class"] == "power"
    assert power.config["unit_of_measurement"] == "W"
