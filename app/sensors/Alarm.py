import json
import logging
from .Sensor import Sensor

logger = logging.getLogger(__name__)
alarm_topic = "alarm_control_panel/tydom/#"
alarm_config_topic = "homeassistant/alarm_control_panel/tydom/{id}/config"
alarm_state_topic = "alarm_control_panel/tydom/{id}/state"
alarm_command_topic = "alarm_control_panel/tydom/{id}/set_alarm_state"
alarm_attributes_topic = "alarm_control_panel/tydom/{id}/attributes"


class Alarm:
    def __init__(self, current_state, alarm_pin=None, tydom_attributes=None, mqtt=None):
        self.state_topic = None
        self.device = None
        self.config = None
        self.config_alarm_topic = None
        self.attributes = tydom_attributes
        self.device_id = self.attributes["device_id"]
        self.endpoint_id = self.attributes["endpoint_id"]
        self.id = self.attributes["id"]
        self.name = self.attributes["name"]
        self.current_state = current_state
        self.mqtt = mqtt
        self.alarm_pin = alarm_pin

    async def setup(self):
        self.device = {
            "manufacturer": "Delta Dore",
            "model": "Tyxal",
            "name": self.name,
            "identifiers": self.id,
        }
        self.config = {
            "name": None,  # set an MQTT entity's name to None to mark it as the main feature of a device
            "unique_id": self.id,
            "device": self.device,
            "command_topic": alarm_command_topic.format(id=self.id),
            "state_topic": alarm_state_topic.format(id=self.id),
            "code_arm_required": False,
        }
        self.config_alarm_topic = alarm_config_topic.format(id=self.id)

        if self.alarm_pin is None:
            self.config["code"] = "REMOTE_CODE"
            self.config["command_template"] = '{ "action": "{{ action }}", "code": "{{ code }}" }'
            self.config["code_arm_required"] = True

        self.config["json_attributes_topic"] = alarm_attributes_topic.format(id=self.id)

        if self.mqtt is not None:
            self.mqtt.mqtt_client.publish(
                self.config_alarm_topic, json.dumps(self.config), qos=0, retain=True
            )  # Alarm Config

    async def update(self):
        await self.setup()
        try:
            await self.update_sensors()
        except Exception as e:
            logger.error("Alarm sensors Error :")
            logger.error(e)

        self.state_topic = alarm_state_topic.format(
            id=self.id, state=self.current_state
        )
        if self.mqtt is not None:
            self.mqtt.mqtt_client.publish(
                self.state_topic, self.current_state, qos=0, retain=True
            )  # Alarm State
            self.mqtt.mqtt_client.publish(
                self.config["json_attributes_topic"],
                self.attributes,
                qos=0,
                retain=True,
            )
        logger.info(
            "Alarm created / updated : %s %s %s", self.name, self.id, self.current_state
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
    async def put_alarm_state(
        tydom_client, device_id, alarm_id, home_zone, night_zone, asked_state=None, pin=None
    ):
        value = None
        zone_id = None

        if asked_state == "ARM_AWAY":
            value = "ON"
            zone_id = None
        elif (
            asked_state == "ARM_HOME"
        ):  # TODO : Separate both and let user specify with zone is what
            value = "ON"
            zone_id = home_zone
        elif (
            asked_state == "ARM_NIGHT"
        ):  # TODO : Separate both and let user specify with zone is what
            value = "ON"
            zone_id = night_zone
        elif asked_state == "DISARM":
            value = "OFF"
            zone_id = None
        elif asked_state == "PANIC":
            value = "PANIC"
            zone_id = None
        elif asked_state == "ACK":
            value = "ACK"
            zone_id = None

        await tydom_client.put_alarm_cdata(
            device_id=device_id, alarm_id=alarm_id, value=value, zone_id=zone_id, pin=pin
        )
