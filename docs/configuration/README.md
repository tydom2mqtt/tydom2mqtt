# Configuration
`tydom2mqtt` can be configured using environment variables.

## Environment variables

You need one of the following to authenticate: `TYDOM_PASSWORD`, `DELTADORE_LOGIN` +
`DELTADORE_PASSWORD` (your Delta Dore account is used to retrieve the Tydom
password), or nothing at all when `TYDOM_IP` points at a hub on your LAN — in
that case `tydom2mqtt` pairs with the hub instead: on the first start it asks
you to press the button on the hub, reads the local password it hands out,
and stores it under `TYDOM_STATE_DIR`. The button is only needed that once.

| Environment variable              | Required       | Supported values                                                                                                                                                                                                           | Default value when missing |
|-----------------------------------|----------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------|
| TYDOM_MAC                         | :red_circle:   | Tydom MAC address (starting with `001A...`)                                                                                                                                                                                |                            |
| DELTADORE_LOGIN                   | :white_circle: | Delta Dore account login                                                                                                                                                                                                   |                            |
| DELTADORE_PASSWORD                | :white_circle: | Delta Dore account password                                                                                                                                                                                                |                            |
| TYDOM_PASSWORD                    | :white_circle: | Tydom password. Not needed for a local connection, see above                                                                                                                                                              |                            |
| TYDOM_IP                          | :white_circle: | Tydom IPv4 address or FQDN. Set it to connect locally and pair with the hub's button                                                                                                                                       | `mediation.tydom.com`      |
| TYDOM_STATE_DIR                   | :white_circle: | Where the local password obtained by pairing is stored. Must be persistent, otherwise the button is needed on every start                                                                                                   | `/data`                    |
| TYDOM_PAIRING_TIMEOUT             | :white_circle: | How long to wait for the hub's button at startup, in seconds                                                                                                                                                               | `180`                      |
| TYDOM_POLLING_INTERVAL            | :white_circle: | Tydom polling interval (in second) for devices need polling (like Tywatt)                                                                                                                                                  | `300`                      |   
| TYDOM_ALARM_PIN                   | :white_circle: | Tydom Alarm PIN                                                                                                                                                                                                            | `None`                     |
| TYDOM_ALARM_HOME_ZONE             | :white_circle: | Tydom alarm home zone                                                                                                                                                                                                      | `1`                        |
| TYDOM_ALARM_NIGHT_ZONE            | :white_circle: | Tydom alarm night zone                                                                                                                                                                                                     | `2`                        |
| MQTT_HOST                         | :white_circle: | Mqtt broker IPv4 or FQDN                                                                                                                                                                                                   | `localhost`                |
| MQTT_PORT                         | :white_circle: | Mqtt broker port                                                                                                                                                                                                           | `1883`                     |
| MQTT_USER                         | :white_circle: | Mqtt broker user if authentication is enabled                                                                                                                                                                              | `None`                     |
| MQTT_PASSWORD                     | :white_circle: | Mqtt broker password if authentication is enabled                                                                                                                                                                          | `None`                     |
| MQTT_SSL                          | :white_circle: | Mqtt broker ssl enabled                                                                                                                                                                                                    | `false`                    |
| LOG_LEVEL                         | :white_circle: | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`)                                                                                                                                                                            | `ERROR`                    |
| THERMOSTAT_CUSTOM_PRESETS         | :white_circle: | Set custom Presets for THERMOSTATS like [4890](https://www.deltadore.fr/domotique/gestion-chauffage/micromodule-recepteur/recepteur-rf4890-ref-6050615) <br/> Format : { 'preset': 'temp'} <br/> Example { 'ECO' : '17' }  |                            |
| THERMOSTAT_COOL_MODE_TEMP_DEFAULT | :white_circle: | Default temperature when switching to cooling mode                                                                                                                                                                         | `26`                       |   
| THERMOSTAT_HEAT_MODE_TEMP_DEFAULT | :white_circle: | Default temperature when switching to heating mode                                                                                                                                                                         | `16`                       |                                                                                                                                                                            

## Complete example

Using a Tydom password (works locally or through the Delta Dore relay):

<!-- tabs:start -->
#### **Docker Compose**
```yaml
version: '3'

services:
  tydom2mqtt:
    image: ghcr.io/tydom2mqtt/tydom2mqtt
    container_name: tydom2mqtt
    environment:
      - TYDOM_MAC=001A25XXXXXX
      - TYDOM_PASSWORD=azerty123456789
      - TYDOM_IP=192.168.1.33
```
#### **Docker**
```bash
docker run -d --name tydom2mqtt \
  -e TYDOM_MAC="001A25XXXXXX" \
  -e TYDOM_PASSWORD="azerty123456789" \
  -e TYDOM_IP="192.168.1.33" \  
  ghcr.io/tydom2mqtt/tydom2mqtt
```
<!-- tabs:end -->

Or, for a local connection, pairing with the hub's button instead (a
persistent volume on `/data` is required, otherwise the button is needed on
every start):

<!-- tabs:start -->
#### **Docker Compose**
```yaml
version: '3'

services:
  tydom2mqtt:
    image: ghcr.io/tydom2mqtt/tydom2mqtt
    container_name: tydom2mqtt
    environment:
      - TYDOM_MAC=001A25XXXXXX
      - TYDOM_IP=192.168.1.33
    volumes:
      - ./tydom-data:/data
```
#### **Docker**
```bash
docker run -d --name tydom2mqtt \
  -e TYDOM_MAC="001A25XXXXXX" \
  -e TYDOM_IP="192.168.1.33" \
  -v "$(pwd)/tydom-data:/data" \
  ghcr.io/tydom2mqtt/tydom2mqtt
```
<!-- tabs:end -->

## THERMOSTAT_CUSTOM_PRESETS property

### Why this configuration property?

Delta Dore sells underfloor heating devices to other brands (Thermor...); [for example this one](https://www.deltadore.fr/domotique/gestion-chauffage/micromodule-recepteur/recepteur-rf4890-ref-6050615). \
These sensors are controlled from an offline Thermostat but can also be controlled from Tydom using the X3D radio protocol. \
The problem is that these sensors don't have presets built-in on their own. \
It's on the controller end to manage and set presets if needed; that's the purpose of this configuration property.

### How to use

Set the environment variables `THERMOSTAT_CUSTOM_PRESETS` with a JSON map of compatible presets among
`"STOP", "ANTI_FROST", "ECO", "COMFORT", "AUTO"`

### Example


<!-- tabs:start -->
#### **Docker Compose**
```yaml
version: '3'

services:
  tydom2mqtt:
    image: ghcr.io/tydom2mqtt/tydom2mqtt
    environment:
      - THERMOSTAT_CUSTOM_PRESETS='{"ECO": "17", "COMFORT": "20"}'
    ...
```
#### **Docker**
```bash
docker run -d --name tydom2mqtt \
  ...
  -e THERMOSTAT_CUSTOM_PRESETS='{"ECO": "17", "COMFORT": "20"}'
  ghcr.io/tydom2mqtt/tydom2mqtt
```
<!-- tabs:end -->
