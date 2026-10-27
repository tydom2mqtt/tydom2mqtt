import json
import logging
from unittest.mock import mock_open

import pytest

from configuration.Configuration import Configuration


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    # Keep boolean settings under test isolated from the ambient environment.
    monkeypatch.delenv("MQTT_SSL", raising=False)
    monkeypatch.delenv("HEALTH_ENABLED", raising=False)


# Regression guard for the gmqtt `'str' object has no attribute 'wrap_bio'`
# crash: MQTT_SSL must resolve to a real bool, never a truthy string.
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("true", True),
        ("True", True),
        ("1", True),
        ("yes", True),
        ("false", False),
        ("FALSE", False),
        ("0", False),
        ("no", False),
        ("", False),
        ("garbage", False),
    ],
)
def test_mqtt_ssl_parsed_to_bool(monkeypatch, raw, expected):
    monkeypatch.setenv("MQTT_SSL", raw)
    cfg = Configuration()
    # `is` rather than `==`: the whole point of the fix is a real bool.
    assert cfg.mqtt_ssl is expected


def test_mqtt_ssl_unset_defaults_false():
    cfg = Configuration()
    assert cfg.mqtt_ssl is False


def test_health_enabled_unset_defaults_true():
    cfg = Configuration()
    assert cfg.health_enabled is True


def test_unrecognized_mqtt_ssl_warns(monkeypatch, caplog):
    monkeypatch.setenv("MQTT_SSL", "enable")
    with caplog.at_level(logging.WARNING):
        cfg = Configuration()
    assert cfg.mqtt_ssl is False
    assert any(
        "MQTT_SSL" in record.message and record.levelno == logging.WARNING
        for record in caplog.records
    )


@pytest.mark.parametrize(
    "ssl_value,expected",
    [
        (False, False),
        (True, True),
        ("false", False),
        ("true", True),
    ],
)
def test_hassio_mqtt_ssl_parsed_to_bool(monkeypatch, ssl_value, expected):
    payload = json.dumps(
        {"TYDOM_MAC": "001A25", "TYDOM_PASSWORD": "secret", "MQTT_SSL": ssl_value}
    )
    cfg = Configuration()  # constructor does no file I/O
    # Patch open only for the override so the Hass.io options file is faked.
    monkeypatch.setattr("builtins.open", mock_open(read_data=payload))
    cfg.override_configuration_for_hassio()
    assert cfg.mqtt_ssl is expected


@pytest.mark.parametrize(
    "presets",
    ['{"ECO": "17", "COMFORT": "20"}', {"ECO": "17", "COMFORT": "20"}],
)
def test_hassio_thermostat_custom_presets(monkeypatch, presets):
    payload = json.dumps(
        {
            "TYDOM_MAC": "001A25",
            "TYDOM_PASSWORD": "secret",
            "THERMOSTAT_CUSTOM_PRESETS": presets,
        }
    )
    cfg = Configuration()
    monkeypatch.setattr("builtins.open", mock_open(read_data=payload))
    cfg.override_configuration_for_hassio()
    assert json.loads(cfg.thermostat_custom_presets) == {"ECO": "17", "COMFORT": "20"}


def test_config_refresh_interval_defaults_to_one_hour(monkeypatch):
    monkeypatch.delenv("TYDOM_CONFIG_REFRESH_INTERVAL", raising=False)
    cfg = Configuration()
    assert cfg.tydom_config_refresh_interval == 3600


def test_config_refresh_interval_from_env(monkeypatch):
    monkeypatch.setenv("TYDOM_CONFIG_REFRESH_INTERVAL", "0")
    cfg = Configuration()
    assert cfg.tydom_config_refresh_interval == 0


def test_hassio_config_refresh_interval(monkeypatch):
    payload = json.dumps(
        {
            "TYDOM_MAC": "001A25",
            "TYDOM_PASSWORD": "secret",
            "TYDOM_CONFIG_REFRESH_INTERVAL": 900,
        }
    )
    cfg = Configuration()
    monkeypatch.setattr("builtins.open", mock_open(read_data=payload))
    cfg.override_configuration_for_hassio()
    assert cfg.tydom_config_refresh_interval == 900
