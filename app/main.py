#!/usr/bin/env python3
import asyncio
import logging.config
import socket
import sys
import signal
import websockets

from configuration.Configuration import Configuration
from mqtt.MqttClient import MqttClient
from tydom.TydomClient import TydomClient
from tydom.MessageHandler import MessageHandler
from health.HealthState import HealthState
from health.HealthServer import HealthServer

# Setup logger configuration
logging.basicConfig(level="INFO", format="%(asctime)s - %(message)s")

# Init logger
logger = logging.getLogger(__name__)

logger.info("Starting tydom2mqtt")

# Load configuration from env vars (+ fallback to default values)
configuration = Configuration.load()

# Reconfigure logger after having loaded the configuration (because the
# log level can have changed)
for logger_handler in logging.root.handlers[:]:
    logging.root.removeHandler(logger_handler)
logging.basicConfig(
    level=configuration.log_level,
    format="%(asctime)s - %(name)-20s - %(levelname)-7s - %(message)s",
)

# Warning levels only for the following chatty modules (if not debug)
if configuration.log_level != "DEBUG":
    logging.getLogger("gmqtt").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)

# Initialize health state singleton
health_state = HealthState()
# Derive the health timeouts from the polling interval (see HealthState).
health_state.set_timeouts_from_polling_interval(
    int(configuration.tydom_polling_interval)
)

# Initialize health server if enabled
health_server = None
if configuration.health_enabled:
    health_server = HealthServer(port=configuration.health_port)


# Listen to tydom events.
async def listen_tydom():
    while True:
        try:
            await tydom_client.connect()
            await tydom_client.setup()
            while True:
                try:
                    try:
                        incoming_bytes_str = await asyncio.wait_for(
                            tydom_client.connection.recv(),
                            timeout=tydom_client.polling_interval,
                        )
                    except asyncio.TimeoutError:
                        # No message within the window: the task is still alive
                        # and listening. Refresh the heartbeat (liveness) without
                        # touching the message-freshness clock, then keep waiting.
                        health_state.update_task_heartbeat("listen_tydom")
                        continue
                    health_state.update_task_heartbeat("listen_tydom")
                    health_state.update_tydom_message_time()
                    message_handler = MessageHandler(
                        incoming_bytes=incoming_bytes_str,
                        tydom_client=tydom_client,
                        mqtt_client=mqtt_client,
                    )
                    await message_handler.incoming_triage()
                except websockets.ConnectionClosed as e:
                    logger.error("Websocket connection closed: %s", e)
                    await tydom_client.disconnect()
                    break
                except Exception as e:
                    logger.warning("Unable to handle message: %s", e)
                    await tydom_client.disconnect()

        except socket.gaierror as e:
            logger.error("Socket error (%s)", e)
            sys.exit(1)
        except ConnectionRefusedError as e:
            logger.error("Connection refused (%s)", e)
            sys.exit(1)


async def poll_device_tydom():
    while True:
        try:
            await asyncio.sleep(tydom_client.polling_interval)
            await tydom_client.post_refresh()
            # Heartbeat after a successful refresh so a hung post_refresh()
            # goes stale and is detected instead of looking alive for a cycle.
            health_state.update_task_heartbeat("poll_device_tydom")
        except Exception as e:
            logger.warning("poll_device_tydom error : %s", e)
            break


# Create tydom client
tydom_client = TydomClient(
    mac=configuration.tydom_mac,
    host=configuration.tydom_ip,
    password=configuration.tydom_password,
    polling_interval=configuration.tydom_polling_interval,
    thermostat_cool_mode_temp_default=configuration.thermostat_cool_mode_temp_default,
    thermostat_heat_mode_temp_default=configuration.thermostat_heat_mode_temp_default,
    alarm_pin=configuration.tydom_alarm_pin,
    thermostat_custom_presets=configuration.thermostat_custom_presets,
)

# Create mqtt client
mqtt_client = MqttClient(
    broker_host=configuration.mqtt_host,
    port=configuration.mqtt_port,
    user=configuration.mqtt_user,
    password=configuration.mqtt_password,
    mqtt_ssl=configuration.mqtt_ssl,
    home_zone=configuration.tydom_alarm_home_zone,
    night_zone=configuration.tydom_alarm_night_zone,
    tydom=tydom_client,
)


async def shutdown(signal, loop):
    logging.info("Received exit signal %s", signal.name)
    logging.info("Cancelling running tasks")

    try:
        # Stop health server
        if health_server is not None:
            await health_server.stop()

        # Close connections
        await tydom_client.disconnect()

        # Cancel async tasks
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        [task.cancel() for task in tasks]
        await asyncio.gather(*tasks)
        logging.info("All running tasks cancelled")
    except Exception as e:
        logging.info("Some errors occurred when stopping tasks (%s)", e)
    finally:
        loop.stop()


def main():
    loop = asyncio.new_event_loop()
    signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
    for s in signals:
        loop.add_signal_handler(s, lambda s=s: asyncio.create_task(shutdown(s, loop)))

    # Start the health server synchronously so a bind failure (e.g. port in
    # use) surfaces immediately and stops startup, instead of being lost in a
    # fire-and-forget task while the container reports itself unhealthy.
    if health_server is not None:
        loop.run_until_complete(health_server.start())

    loop.create_task(mqtt_client.connect())
    loop.create_task(listen_tydom())
    loop.create_task(poll_device_tydom())
    loop.run_forever()


if __name__ == "__main__":
    main()
