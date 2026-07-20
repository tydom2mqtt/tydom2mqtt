import asyncio
import json
from unittest.mock import MagicMock

import pytest

from sensors.Garage import Garage
from tydom.MessageHandler import device_metadata


@pytest.fixture(autouse=True)
def _clean_device_metadata():
    device_metadata.clear()
    yield
    device_metadata.clear()


def make_garage(device_id=1, endpoint_id=2, cover_class="gate"):
    return Garage(
        tydom_attributes={
            "device_id": device_id,
            "endpoint_id": endpoint_id,
            "id": f"{device_id}_{endpoint_id}",
            "cover_name": "Gate 1",
            "cover_class": cover_class,
        },
        mqtt=MagicMock(),
    )


def test_is_toggle_only_defaults_false_when_metadata_missing():
    # Race between install-sync and the first parse_endpoint_data call: no
    # metadata known yet for this device -- must not crash and must default
    # to the existing ON/OFF/STOP behavior.
    garage = make_garage()
    assert garage.is_toggle_only() is False


def test_is_toggle_only_true_for_toggle_only_relay():
    device_metadata["2_1"] = {"levelCmd": ["TOGGLE"]}
    garage = make_garage(device_id=1, endpoint_id=2)
    assert garage.is_toggle_only() is True


def test_is_toggle_only_false_for_real_positional_motor():
    device_metadata["2_1"] = {"levelCmd": ["OPEN", "CLOSE", "STOP"]}
    garage = make_garage(device_id=1, endpoint_id=2)
    assert garage.is_toggle_only() is False


def test_setup_publishes_button_entity_for_toggle_only_relay():
    device_metadata["2_1"] = {"levelCmd": ["TOGGLE"]}
    garage = make_garage(device_id=1, endpoint_id=2)

    asyncio.run(garage.setup())

    topic, payload = garage.mqtt.mqtt_client.publish.call_args[0][:2]
    config = json.loads(payload)
    assert topic == "homeassistant/button/tydom/1_2/config"
    assert config["payload_press"] == "TOGGLE"
    assert config["command_topic"] == "button/tydom/1_2/set_garageLevelCmd"


def test_setup_clears_stale_cover_entity_for_toggle_only_relay():
    device_metadata["2_1"] = {"levelCmd": ["TOGGLE"]}
    garage = make_garage(device_id=1, endpoint_id=2)

    asyncio.run(garage.setup())

    calls = garage.mqtt.mqtt_client.publish.call_args_list
    assert (
        "homeassistant/cover/tydom/1_2/config",
        "",
    ) == calls[0][0][:2]


def test_setup_publishes_on_off_stop_for_positional_motor():
    device_metadata["2_1"] = {"levelCmd": ["OPEN", "CLOSE", "STOP"]}
    garage = make_garage(device_id=1, endpoint_id=2)

    asyncio.run(garage.setup())

    config = json.loads(garage.mqtt.mqtt_client.publish.call_args[0][1])
    assert config["payload_open"] == "ON"
    assert config["payload_close"] == "OFF"
    assert config["payload_stop"] == "STOP"


def test_setup_clears_stale_button_entity_for_positional_motor():
    device_metadata["2_1"] = {"levelCmd": ["OPEN", "CLOSE", "STOP"]}
    garage = make_garage(device_id=1, endpoint_id=2)

    asyncio.run(garage.setup())

    calls = garage.mqtt.mqtt_client.publish.call_args_list
    assert (
        "homeassistant/button/tydom/1_2/config",
        "",
    ) == calls[0][0][:2]


def test_put_garage_positioncmd_forwards_toggle_verbatim():
    async def scenario():
        tydom_client = MagicMock()

        async def fake_put_devices_data(*args):
            fake_put_devices_data.calls.append(args)

        fake_put_devices_data.calls = []
        tydom_client.put_devices_data = fake_put_devices_data

        await Garage.put_garage_positionCmd(tydom_client, "device1", "cover1", "TOGGLE")
        return fake_put_devices_data.calls

    calls = asyncio.run(scenario())
    assert calls == [("device1", "cover1", "levelCmd", "TOGGLE")]
