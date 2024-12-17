import json
import logging

from .Sensor import Sensor

logger = logging.getLogger(__name__)
button_config_topic = "homeassistant/button/tydom/{id}/config"
button_state_topic = "button/tydom/{id}/state"
button_command_topic = "button/tydom/{id}/open_automatic_door"


class AutomaticDoor:
    def __init__(self, tydom_attributes, tydom_client=None, mqtt=None):
        self.config_topic = None
        self.topic_to_func = None
        self.config = None
        self.device = None
        self.attributes = tydom_attributes
        self.device_id = self.attributes["device_id"]
        self.endpoint_id = self.attributes["endpoint_id"]
        self.id = self.attributes["id"]
        self.name = self.attributes["name"]
        self.mqtt = mqtt
        self.tydom_client = tydom_client

    async def setup(self):
        self.config = {}
        self.device = {
            "manufacturer": "Delta Dore",
            "name": self.name,
            "model": "Automatic Door",
            "identifiers": self.id,
        }
        self.config["device"] = self.device

        self.config_topic = button_config_topic.format(id=self.id)
        self.config = {
            "name": None,  # set an MQTT entity's name to None to mark it as the main feature of a device
            "unique_id": self.id,
            "device": self.device,
            "button_state_topic": button_state_topic.format(id=self.id),
            "command_topic": button_command_topic.format(id=self.id),
            "icon": "mdi:lock-open-outline",
            "availability_topic": button_state_topic.format(id=self.id),
            "availability_template": '{% if value_json.podPosition == "CLOSE" -%}online{%- else -%}offline{%- endif %}',
            "payload_press": "OPEN",
        }
        if self.mqtt is not None:
            self.mqtt.mqtt_client.publish(
                self.config_topic, json.dumps(self.config), qos=0, retain=True
            )

    async def update(self):
        await self.setup()

        try:
            await self.update_sensors()
        except Exception as e:
            logger.error("AutomaticDoor sensors Error :")
            logger.error(e)

        if self.mqtt is not None:
            self.mqtt.mqtt_client.publish(
                self.config["button_state_topic"], self.attributes, qos=0, retain=True
            )

        logger.info("AutomaticDoor created / updated : %s %s", self.name, self.id)

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

    @staticmethod
    async def put_podPosition(tydom_client, device_id, door_id, position):
        logger.info("put_podPosition: %s to %s", device_id, position)
        if not (position == ""):
            # ex: 'podPosition': 'OPEN'
            await tydom_client.put_devices_data(
                device_id, door_id, "podPosition", position
            )
