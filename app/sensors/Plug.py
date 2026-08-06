import json
import logging
from .Sensor import Sensor

logger = logging.getLogger(__name__)
plug_config_topic = "homeassistant/switch/tydom/{id}/config"
plug_state_topic = "plug/tydom/{id}/plug_state"
plug_attributes_topic = "plug/tydom/{id}/attributes"
plug_command_topic = "plug/tydom/{id}/set_plug_state"


class Plug:
    def __init__(self, tydom_attributes, set_state=None, mqtt=None):
        self.state_topic = None
        self.config_topic = None
        self.config = None
        self.device = None
        self.attributes = tydom_attributes
        self.device_id = self.attributes["device_id"]
        self.endpoint_id = self.attributes["endpoint_id"]
        self.id = self.attributes["id"]
        self.name = self.attributes["plug_name"]

        try:
            self.current_state = self.attributes["plugCmd"]
        except Exception as e:
            logger.warning(e)
            self.current_state = None
        self.set_state = set_state
        self.mqtt = mqtt

    async def setup(self):
        self.device = {
            "manufacturer": "Delta Dore",
            "model": "Prise",
            "name": self.name,
            "identifiers": self.id,
        }
        self.config_topic = plug_config_topic.format(id=self.id)
        self.config = {
            "name": None,  # set an MQTT entity's name to None to mark it as the main feature of a device
            "unique_id": self.id,
            "command_topic": plug_command_topic.format(id=self.id),
            "state_topic": plug_state_topic.format(id=self.id),
            "json_attributes_topic": plug_attributes_topic.format(id=self.id),
            "payload_on": "ON",
            "state_on": "ON",
            "payload_off": "OFF",
            "state_off": "OFF",
            "retain": True,
            "optimistic": True,
            "device": self.device,
        }

        if self.mqtt is not None:
            self.mqtt.mqtt_client.publish(
                self.config_topic, json.dumps(self.config), qos=0, retain=False
            )

    async def update(self):
        await self.setup()

        try:
            await self.update_sensors()
        except Exception as e:
            logger.error("Plug sensors Error :")
            logger.error(e)

        self.state_topic = plug_state_topic.format(
            id=self.id, current_state=self.current_state
        )

        if self.mqtt is not None:
            self.mqtt.mqtt_client.publish(
                self.state_topic, self.current_state, qos=0, retain=True
            )
            self.mqtt.mqtt_client.publish(
                self.config["json_attributes_topic"],
                self.attributes,
                qos=0,
                retain=True,
            )
        logger.info(
            "Plug created / updated : %s %s %s",
            self.name,
            self.id,
            self.current_state,
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

    @staticmethod
    async def put_plug_state(tydom_client, device_id, plug_id, plug_state):
        logger.info("%s %s %s", plug_id, "plug_state", plug_state)
        if not (plug_state == ""):
            await tydom_client.put_devices_data(device_id, plug_id, "plugCmd", plug_state)

