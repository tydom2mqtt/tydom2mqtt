# Introduction

![License](https://img.shields.io/github/license/tydom2mqtt/tydom2mqtt)
![🤖 CI](https://github.com/tydom2mqtt/tydom2mqtt/actions/workflows/ci.yaml/badge.svg)

**tydom2mqtt** allows you to integrate Deltadore Tydom Hubs to MQTT.

## Quick start

### Run the Docker image
The easiest way to start is to deploy the official _**tydom2mqtt**_ image.

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

?> Connecting to a hub on your local network? You don't need `TYDOM_PASSWORD`
at all: leave it out and press the button on the hub when asked, see
[the configuration options](/configuration/) for details.

?> [Please find here all the configuration options.](/configuration/)

!> Are you a Home-Assistant user? \
So maybe take a look at the [Hass.io add-on version](/hass/)!
## Contact & Support

- Create a [GitHub issue](https://github.com/tydom2mqtt/tydom2mqtt/issues) for bug reports, feature requests, or questions
- Add a ⭐️ [star on GitHub](https://github.com/tydom2mqtt/tydom2mqtt) to support the project!

## License

This project is licensed under the [MIT license](https://github.com/tydom2mqtt/tydom2mqtt/blob/master/LICENSE).

<!-- GitHub Buttons -->
<script async defer src="https://buttons.github.io/buttons.js"></script>
