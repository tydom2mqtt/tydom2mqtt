import json
import logging
from .Sensor import Sensor

logger = logging.getLogger(__name__)
cover_command_topic = "cover/tydom/{id}/set_garageLevelCmd"
cover_config_topic = "homeassistant/cover/tydom/{id}/config"
cover_position_topic = "cover/tydom/{id}/current_position"
cover_state_topic = "cover/tydom/{id}/state"
cover_level_topic = "cover/tydom/{id}/current_level"
cover_set_level_topic = "cover/tydom/{id}/set_garageLevel"
cover_attributes_topic = "cover/tydom/{id}/attributes"


class Garage:
    def __init__(self, tydom_attributes, set_level=None, mqtt=None):
        self.device = None
        self.config = None
        self.config_topic = None
        self.attributes = tydom_attributes
        self.device_id = self.attributes["device_id"]
        self.endpoint_id = self.attributes["endpoint_id"]
        self.id = self.attributes["id"]
        self.name = self.attributes["cover_name"]
        try:
            self.current_level = self.attributes["level"]
        except Exception as e:
            logger.error(e)
            self.current_level = None

        self.set_level = set_level
        self.current_position = set_level

        if "position" in tydom_attributes:
            self.current_position = self.attributes["position"]

        self.mqtt = mqtt

    async def setup(self):
        self.device = {
            "manufacturer": "Delta Dore",
            "model": "Garage Door Horizontal",
            "name": self.name,
            "identifiers": self.id,
        }
        self.config_topic = cover_config_topic.format(id=self.id)
        self.config = {
            "name": None,  # set an MQTT entity's name to None to mark it as the main feature of a device
            "unique_id": self.id,
            "command_topic": cover_command_topic.format(id=self.id),
            "position_topic": cover_position_topic.format(id=self.id),
            "level_topic": cover_level_topic.format(id=self.id),
            "set_position_topic": cover_set_level_topic.format(id=self.id),
            "payload_open": "ON",
            "payload_close": "OFF",
            "payload_stop": "STOP",
            "retain": "false",
            "device": self.device,
            "device_class": self.attributes["cover_class"],
        }

        self.config["json_attributes_topic"] = cover_attributes_topic.format(id=self.id)

        if self.mqtt is not None:
            self.mqtt.mqtt_client.publish(
                self.config_topic, json.dumps(self.config), qos=0, retain=True
            )

    async def update(self):
        await self.setup()

        try:
            await self.update_sensors()
        except Exception as e:
            logger.error("GarageDoor Horizontal sensors Error :")
            logger.error(e)

        self.level_topic = cover_state_topic.format(
            id=self.id, current_level=self.current_level
        )

        if self.mqtt is not None:
            # and 'position' in self.attributes:
            self.mqtt.mqtt_client.publish(
                self.config["position_topic"], self.current_level, qos=0, retain=True
            )

        if self.mqtt is not None:
            self.mqtt.mqtt_client.publish(
                self.level_topic, self.current_level, qos=0, retain=True
            )
            self.mqtt.mqtt_client.publish(
                self.config["json_attributes_topic"],
                self.attributes,
                qos=0,
                retain=True,
            )

        logger.info(
            "GarageDoor Horizontal created / updated : %s %s %s",
            self.name,
            self.id,
            self.current_level,
        )

    async def update_sensors(self):
        for i, j in self.attributes.items():
            if (
                not i == "device_type"
                and not i == "id"
                and not i == "device_id"
                and not i == "endpoint_id"
            ):
                new_sensor = Sensor(
                    elem_name=i,
                    tydom_attributes_payload=self.attributes,
                    mqtt=self.mqtt,
                )
                await new_sensor.update()

    async def put_garage_position(tydom_client, device_id, cover_id, position):
        logger.info("%s %s %s", cover_id, "level", position)
        if not (position == ""):
            await tydom_client.put_devices_data(device_id, cover_id, "level", position)

    async def put_garage_positionCmd(tydom_client, device_id, cover_id, positionCmd):
        logger.info("%s %s %s", cover_id, "levelCmd", positionCmd)
        if not (positionCmd == ""):
            await tydom_client.put_devices_data(
                device_id, cover_id, "levelCmd", positionCmd
            )
