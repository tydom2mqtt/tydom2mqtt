import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from sensors.Alarm import Alarm
from sensors.Boiler import Boiler


def _alarm_config(alarm_pin):
    attributes = {"device_id": 1, "endpoint_id": 1, "id": "1_1", "name": "Tyxal"}
    alarm = Alarm(
        current_state="disarmed", alarm_pin=alarm_pin, tydom_attributes=attributes
    )
    asyncio.run(alarm.setup())
    return alarm.config


# Home Assistant rejects an alarm discovery payload holding `"code": null`,
# which used to make the alarm entity disappear when no PIN was configured.
@pytest.mark.parametrize("alarm_pin", [None, "123456"])
def test_alarm_config_never_publishes_null_code(alarm_pin):
    config = _alarm_config(alarm_pin)
    assert "code" not in config
    assert config["code_arm_required"] is False


@pytest.mark.parametrize("mode,expected_setpoint", [("cool", "26"), ("heat", "16")])
def test_hvac_mode_applies_matching_default_setpoint(mode, expected_setpoint):
    tydom_client = MagicMock()
    tydom_client.put_devices_data = AsyncMock()
    tydom_client.put_home_hvac_mode = AsyncMock()
    tydom_client.thermostat_cool_mode_temp_default = 26
    tydom_client.thermostat_heat_mode_temp_default = 16

    asyncio.run(Boiler.put_hvac_mode(tydom_client, 1, 2, mode))

    tydom_client.put_devices_data.assert_any_await(1, 2, "setpoint", expected_setpoint)
