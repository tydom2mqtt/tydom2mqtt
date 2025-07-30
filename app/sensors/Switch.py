import json
import logging
from .Sensor import Sensor

logger = logging.getLogger(__name__)
switch_config_topic = "homeassistant/switch/tydom/{id}/config"
switch_state_topic = "switch/tydom/{id}/state"
switch_attributes_topic = "switch/tydom/{id}/attributes"
switch_command_topic = "switch/tydom/{id}/set_levelCmdGate"
switch_level_topic = "switch/tydom/{id}/current_level"
switch_set_level_topic = "switch/tydom/{id}/set_levelGate"


class Switch:
    def __init__(self, tydom_attributes, set_level=None, mqtt=None):
        self.level_topic = None
        self.config_topic = None
        self.config = None
        self.device = None
        self.attributes = tydom_attributes
        self.device_id = self.attributes["device_id"]
        self.endpoint_id = self.attributes["endpoint_id"]
        self.id = self.attributes["id"]
        self.name = self.attributes.get("name", f"Switch_{self.device_id}")

        try:
            self.current_level = self.attributes["level"]
        except KeyError:
            logger.warning("Attribute 'level' missing for switch %s", self.name)
            self.current_level = 0
        except Exception as e:
            logger.error(e)
            self.current_level = None
        self.set_level = set_level
        self.mqtt = mqtt

    async def setup(self):
        self.device = {
            "manufacturer": "Delta Dore",
            "model": "Porte",
            "name": self.name,
            "identifiers": self.id,
        }
        self.config_topic = switch_config_topic.format(id=self.id)
        self.config = {
            "name": None,  # set an MQTT entity's name to None to mark it as the main feature of a device
            "unique_id": self.id,
            "command_topic": switch_command_topic.format(id=self.id),
            "state_topic": switch_state_topic.format(id=self.id),
            "json_attributes_topic": switch_attributes_topic.format(id=self.id),
            "payload_on": "TOGGLE",
            "payload_off": "TOGGLE",
            "retain": "false",
            "device": self.device,
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
            logger.error("Switch sensors Error :")
            logger.error(e)

        self.level_topic = switch_state_topic.format(
            id=self.id, current_level=self.current_level
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
            "Switch created / updated : %s %s %s",
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

    @staticmethod
    async def put_level_gate(tydom_client, device_id, switch_id, level):
        logger.info("%s %s %s", switch_id, "level", level)
        if not (level == ""):
            await tydom_client.put_devices_data(device_id, switch_id, "level", level)

    @staticmethod
    async def put_level_cmd_gate(tydom_client, device_id, switch_id, level_cmd):
        logger.info("%s %s %s", switch_id, "levelCmd", level_cmd)
        if not (level_cmd == ""):
            await tydom_client.put_devices_data(
                device_id, switch_id, "levelCmd", level_cmd
            )

