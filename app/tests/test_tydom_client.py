from tydom.TydomClient import TydomClient


def _client():
    return TydomClient(
        mac="001A25123456",
        password="secret",
        polling_interval=300,
        thermostat_cool_mode_temp_default=26,
        thermostat_heat_mode_temp_default=16,
        host="192.168.1.10",
    )


# /devices/cmeta is re-parsed on every reconnect and periodic config refresh:
# the poll list must not accumulate duplicates.
def test_add_poll_device_url_skips_duplicates():
    client = _client()
    index_url = "/devices/1/endpoints/1/cdata?name=energyIndex&dest=ELEC&reset=false"
    instant_url = "/devices/1/endpoints/1/cdata?name=energyInstant&unit=AMPERE"
    client.add_poll_device_url(index_url)
    client.add_poll_device_url(index_url)
    client.add_poll_device_url(instant_url)
    assert client.poll_device_urls == [index_url, instant_url]
