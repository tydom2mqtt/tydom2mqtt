import json
import logging
import socket
import sys
import time
from datetime import datetime

from gmqtt import Client as MQTTClient

from sensors.Alarm import Alarm
from sensors.Boiler import Boiler
from sensors.Cover import Cover
from sensors.Garage import Garage
from sensors.Light import Light
from sensors.Switch import Switch
from sensors.ShHvac import ShHvac
from sensors.AutomaticDoor import AutomaticDoor

logger = logging.getLogger(__name__)

tydom_topic = "+/tydom/#"
refresh_topic = "homeassistant/requests/tydom/refresh"


class MqttClient:
    def __init__(
        self,
        broker_host="localhost",
        port=1883,
        user="",
        password="",
        mqtt_ssl=False,
        home_zone=1,
        night_zone=2,
        tydom=None,
        tydom_alarm_pin=None,
    ):
        self.broker_host = broker_host
        self.port = port
        self.user = user if user is not None else ""
        self.password = password if password is not None else ""
        self.ssl = mqtt_ssl
        self.tydom = tydom
        self.tydom_alarm_pin = tydom_alarm_pin
        self.mqtt_client = None
        self.home_zone = home_zone
        self.night_zone = night_zone

    async def connect(self):
        try:
            logger.info(
                "Connecting to mqtt broker (host=%s, port=%s, user=%s, ssl=%s)",
                self.broker_host,
                self.port,
                self.user,
                self.ssl,
            )
            address = socket.gethostname() + str(datetime.fromtimestamp(time.time()))
            client = MQTTClient(address)
            client.on_connect = self.on_connect
            client.on_message = self.on_message
            client.on_disconnect = self.on_disconnect
            client.set_auth_credentials(self.user, self.password)
            await client.connect(self.broker_host, self.port, self.ssl)
            logger.info("Connected to mqtt broker")
            self.mqtt_client = client
            return self.mqtt_client
        except Exception as e:
            logger.warning("MQTT connection error : %s", e)

    def on_connect(self, client, flags, rc, properties):
        try:
            logger.debug("Subscribing to topics (%s)", tydom_topic)
            client.subscribe("homeassistant/status", qos=0)
            client.subscribe(tydom_topic, qos=0)
        except Exception as e:
            logger.info("Mqtt connection error (%s)", e)

    async def on_message(self, client, topic, payload, qos, properties):
        if "update" in str(topic):
            value = payload.decode()
            logger.info("update message received (topic=%s, message=%s)", topic, value)
            await self.tydom.get_data()
        elif "kill" in str(topic):
            value = payload.decode()
            logger.info("kill message received (topic=%s, message=%s)", topic, value)
            logger.info("Exiting")
            sys.exit()
        elif topic == "homeassistant/requests/tydom/refresh":
            value = payload.decode()
            logger.info("refresh message received (topic=%s, message=%s)", topic, value)
            await self.tydom.post_refresh()
        elif topic == "homeassistant/requests/tydom/scenarii":
            value = payload.decode()
            logger.info(
                "scenarii message received (topic=%s, message=%s)", topic, value
            )
            await self.tydom.get_scenarii()
        elif topic == "homeassistant/status" and payload.decode() == "online":
            value = payload.decode()
            logger.info("status message received (topic=%s, message=%s)", topic, value)
            await self.tydom.get_devices_data()
        elif topic == "/tydom/init":
            value = payload.decode()
            logger.info("init message received (topic=%s, message=%s)", topic, value)
            await self.tydom.connect()

        elif "set_positionCmd" in str(topic):
            value = payload.decode()
            logger.info(
                "set_positionCmd message received (topic=%s, message=%s)", topic, value
            )
            get_id = (topic.split("/"))[2]
            device_id = (get_id.split("_"))[0]
            endpoint_id = (get_id.split("_"))[1]
            await Cover.put_positionCmd(
                tydom_client=self.tydom,
                device_id=device_id,
                cover_id=endpoint_id,
                positionCmd=str(value),
            )

        elif ("set_position" in str(topic)) and "set_positionCmd" not in str(topic):
            value = json.loads(payload)
            logger.info(
                "set_position message received (topic=%s, message=%s)", topic, value
            )
            get_id = (topic.split("/"))[2]
            device_id = (get_id.split("_"))[0]
            endpoint_id = (get_id.split("_"))[1]
            await Cover.put_position(
                tydom_client=self.tydom,
                device_id=device_id,
                cover_id=endpoint_id,
                position=str(value),
            )

        elif "set_garageLevelCmd" in str(topic):
            value = payload.decode()
            logger.info(
                "set_garageLevelCmd message received (topic=%s, message=%s)",
                topic,
                value,
            )
            get_id = (topic.split("/"))[2]
            device_id = (get_id.split("_"))[0]
            endpoint_id = (get_id.split("_"))[1]
            await Garage.put_garage_positionCmd(
                tydom_client=self.tydom,
                device_id=device_id,
                cover_id=endpoint_id,
                positionCmd=str(value),
            )

        elif ("set_garageLevel" in str(topic)) and "set_garageLevelCmd" not in str(
            topic
        ):
            value = json.loads(payload)
            logger.info(
                "set_garageLevel message received (topic=%s, message=%s)", topic, value
            )
            get_id = (topic.split("/"))[2]
            device_id = (get_id.split("_"))[0]
            endpoint_id = (get_id.split("_"))[1]
            await Garage.put_garage_position(
                tydom_client=self.tydom,
                device_id=device_id,
                cover_id=endpoint_id,
                position=str(value),
            )

        elif "set_tilt" in str(topic):
            value = json.loads(payload)
            logger.info(
                "set_tilt message received (topic=%s, message=%s)", topic, value
            )
            get_id = (topic.split("/"))[2]
            device_id = (get_id.split("_"))[0]
            endpoint_id = (get_id.split("_"))[1]
            await Cover.put_tilt(
                tydom_client=self.tydom,
                device_id=device_id,
                cover_id=endpoint_id,
                tilt=str(value),
            )

        elif "set_levelCmd" in str(topic):
            value = payload.decode()
            logger.info(
                "set_levelCmd message received (topic=%s, message=%s)", topic, value
            )
            get_id = (topic.split("/"))[2]
            device_id = (get_id.split("_"))[0]
            endpoint_id = (get_id.split("_"))[1]
            await Light.put_level_cmd(
                tydom_client=self.tydom,
                device_id=device_id,
                light_id=endpoint_id,
                level_cmd=str(value),
            )

        elif ("set_level" in str(topic)) and "set_levelCmd" not in str(topic):
            value = json.loads(payload)
            logger.info(
                "set_level message received (topic=%s, message=%s)", topic, value
            )
            get_id = (topic.split("/"))[2]
            device_id = (get_id.split("_"))[0]
            endpoint_id = (get_id.split("_"))[1]
            await Light.put_level(
                tydom_client=self.tydom,
                device_id=device_id,
                light_id=endpoint_id,
                level=str(value),
            )

        elif "open_automatic_door" in str(topic):
            value = payload.decode()
            logger.info(
                "open_automatic_door message received (topic=%s, message=%s)",
                topic,
                value,
            )
            get_id = (topic.split("/"))[2]
            device_id = (get_id.split("_"))[0]
            endpoint_id = (get_id.split("_"))[1]
            await AutomaticDoor.put_podPosition(
                tydom_client=self.tydom,
                device_id=device_id,
                door_id=endpoint_id,
                position="OPEN",
            )

        elif ("set_alarm_state" in str(topic)) and "homeassistant" not in str(topic):
            value = payload.decode()
            logger.info(
                "set_alarm_state message received (topic=%s, message=%s)", topic, value
            )
            get_id = (topic.split("/"))[2]
            device_id = (get_id.split("_"))[0]
            endpoint_id = (get_id.split("_"))[1]
            await Alarm.put_alarm_state(
                tydom_client=self.tydom,
                device_id=device_id,
                alarm_id=endpoint_id,
                asked_state=value,
                home_zone=self.home_zone,
                night_zone=self.night_zone,
            )

        elif "set_setpoint" in str(topic):
            value = json.loads(payload)
            logger.info(
                "set_setpoint message received (topic=%s, message=%s)", topic, value
            )
            get_id = (topic.split("/"))[2]
            device_id = (get_id.split("_"))[0]
            endpoint_id = (get_id.split("_"))[1]

            await Boiler.put_temperature(
                tydom_client=self.tydom,
                device_id=device_id,
                boiler_id=endpoint_id,
                set_setpoint=str(value),
            )

        elif "set_hvacMode" in str(topic):
            value = payload.decode()
            logger.info(
                "set_hvacMode message received (topic=%s, message=%s)", topic, value
            )
            get_id = (topic.split("/"))[2]
            device_id = (get_id.split("_"))[0]
            endpoint_id = (get_id.split("_"))[1]

            await Boiler.put_hvac_mode(
                tydom_client=self.tydom,
                device_id=device_id,
                boiler_id=endpoint_id,
                set_hvac_mode=str(value),
            )

        elif "set_thermicLevel" in str(topic):
            value = payload.decode()
            logger.info(
                "set_thermicLevel message received (topic=%s, message=%s)", topic, value
            )
            get_id = (topic.split("/"))[2]
            device_id = (get_id.split("_"))[0]
            endpoint_id = (get_id.split("_"))[1]

            await Boiler.put_thermic_level(
                tydom_client=self.tydom,
                device_id=device_id,
                boiler_id=endpoint_id,
                set_thermic_level=str(value),
            )

        elif ("set_switch_state" in str(topic)) and "homeassistant" not in str(topic):
            value = payload.decode()
            logger.info(
                "set_switch_state message received (topic=%s, message=%s)", topic, value
            )
            get_id = (topic.split("/"))[2]
            device_id = (get_id.split("_"))[0]
            endpoint_id = (get_id.split("_"))[1]

            # This seems broken, but I'm not entirely clear what it is meant to
            # do?
            await Switch.put_switch_state(
                tydom_client=self.tydom,
                device_id=device_id,
                switch_id=endpoint_id,
                state=value,
            )

        elif "set_levelCmdGate" in str(topic):
            value = payload.decode()
            logger.info(
                "set_switch_state message received (topic=%s, message=%s)", topic, value
            )
            get_id = (topic.split("/"))[2]
            device_id = (get_id.split("_"))[0]
            endpoint_id = (get_id.split("_"))[1]
            await Switch.put_level_cmd_gate(
                tydom_client=self.tydom,
                device_id=device_id,
                switch_id=endpoint_id,
                level_cmd=str(value),
            )

        elif ("set_levelGate" in str(topic)) and "set_levelCmd" not in str(topic):
            value = json.loads(payload)
            logger.info(
                "set_levelGate message received (topic=%s, message=%s)", topic, value
            )
            get_id = (topic.split("/"))[2]
            device_id = (get_id.split("_"))[0]
            endpoint_id = (get_id.split("_"))[1]
            await Switch.put_level_gate(
                tydom_client=self.tydom,
                device_id=device_id,
                switch_id=endpoint_id,
                level=str(value),
            )

        elif "set_shHvacTemperature" in str(topic):
            value = payload.decode()
            logger.info(
                "set_shHvacTemperature message received (topic=%s, message=%s)",
                topic,
                value,
            )
            get_id = (topic.split("/"))[2]
            device_id = (get_id.split("_"))[0]
            await ShHvac.put_temperature(
                tydom_client=self.tydom, device_id=device_id, temperature=str(value)
            )

        elif "set_shHvacBoost" in str(topic):
            value = payload.decode()
            logger.info(
                "set_shHvacBoost message received (topic=%s, message=%s)", topic, value
            )
            get_id = (topic.split("/"))[2]
            device_id = (get_id.split("_"))[0]
            await ShHvac.put_boost(
                tydom_client=self.tydom, device_id=device_id, boost=value
            )

    @staticmethod
    def on_disconnect(cmd, packet):
        logger.info("Disconnected")
