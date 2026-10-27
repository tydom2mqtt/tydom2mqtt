import json
import logging

from .Sensor import Sensor

logger = logging.getLogger(__name__)
thermostat_config_topic = "homeassistant/climate/tydom/{id}/config"
thermostat_json_attributes_topic = "climate/tydom/{id}/attributes"
thermostat_target_temperature_topic = "climate/tydom/{id}/target_temperature"
thermostat_current_temperature_topic = "climate/tydom/{id}/current_temperature"
thermostat_temperature_command_topic = "climate/tydom/{id}/set_shHvacTemperature"
thermostat_mode_state_topic = "climate/tydom/{id}/mode_state"
thermpstat_boost_config_topic = "homeassistant/switch/tydom/{id}/config"
thermostat_boost_command_topic = "climate/tydom/{id}/set_shHvacBoost"
thermpstat_boost_state_topic = "climate/tydom/{id}/get_shHvacBoost"


class ShHvac:
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
            "model": "Heater with thermostat",
            "identifiers": self.id,
        }
        self.config["device"] = self.device

        self.config_topic = thermostat_config_topic.format(id=self.id)
        self.config = {
            "name": None,  # set an MQTT entity's name to None to mark it as the main feature of a device
            "unique_id": self.id,
            "device": self.device,
            "temperature_unit": "C",
            # from what we can do in the android app,
            # it seems we can only shut down the whole heating system, not just one heater,
            # so the only mode we can use is heat, no 'off' mode
            "modes": ["off", "heat"],
            "max_temp": 30,
            "min_temp": 5,
            "temperature_state_topic": thermostat_target_temperature_topic.format(
                id=self.id
            ),
            "current_temperature_topic": thermostat_current_temperature_topic.format(
                id=self.id
            ),
            "json_attributes_topic": thermostat_json_attributes_topic.format(
                id=self.id
            ),
            "temperature_command_topic": thermostat_temperature_command_topic.format(
                id=self.id
            ),
            "mode_state_topic": thermostat_mode_state_topic.format(id=self.id),
        }

        # create a switch for boost mode
        self.switch_config_topic = thermpstat_boost_config_topic.format(id=self.id)
        self.switch_config = {
            "name": "Boost",
            "unique_id": self.id + "_boost",
            "device": self.device,
            "payload_on": "ON",
            "payload_off": "OFF",
            "state_on": "ON",
            "state_off": "OFF",
            "command_topic": thermostat_boost_command_topic.format(id=self.id),
            "state_topic": thermpstat_boost_state_topic.format(id=self.id),
        }

        if self.mqtt is not None:
            self.mqtt.mqtt_client.publish(
                self.config_topic, json.dumps(self.config), qos=0, retain=True
            )

            self.mqtt.mqtt_client.publish(
                self.switch_config_topic,
                json.dumps(self.switch_config),
                qos=0,
                retain=True,
            )

    async def update(self):
        await self.setup()

        if self.mqtt is not None:
            # create sensors for some attributes
            sensors = {}

            if "battDefect" in self.attributes:
                sensors["batt_defect"] = {
                    "batt_defect": self.attributes["battDefect"],
                    "device_class": None,
                } | self.attributes
            if "waterFlowReq" in self.attributes:
                sensors["water_flow_req"] = {
                    "water_flow_req": self.attributes["waterFlowReq"],
                    "device_class": None,
                } | self.attributes
            if "regTemperature" in self.attributes:
                sensors["reg_temperature"] = {
                    "reg_temperature": "None"
                    if not isinstance(self.attributes["regTemperature"], float)
                    else self.attributes["regTemperature"],
                    "device_class": "temperature",
                    "unit_of_measurement": "°C",
                } | self.attributes
            if "devTemperature" in self.attributes:
                sensors["dev_temperature"] = {
                    "dev_temperature": "None"
                    if not isinstance(self.attributes["devTemperature"], float)
                    else self.attributes["devTemperature"],
                    "device_class": "temperature",
                    "unit_of_measurement": "°C",
                } | self.attributes
            if "activationIndex" in self.attributes:
                sensors["activation_index"] = {
                    "activation_index": "None"
                    if not isinstance(self.attributes["activationIndex"], int)
                    else self.attributes["activationIndex"],
                    "device_class": "water",
                    "unit_of_measurement": "m³",
                } | self.attributes
            if "boost" in self.attributes:
                sensors["boost"] = {
                    "boost": self.attributes["boost"],
                    "device_class": None,
                } | self.attributes
            if "boostRemainingTime" in self.attributes:
                sensors["boost_remaining_time"] = {
                    "boost_remaining_time": "None"
                    if not isinstance(self.attributes["boostRemainingTime"], int)
                    else self.attributes["boostRemainingTime"],
                    "device_class": "duration",
                    "unit_of_measurement": "min",
                } | self.attributes
            if "currentSetpoint" in self.attributes:
                sensors["current_setpoint"] = {
                    "current_setpoint": "None"
                    if not isinstance(self.attributes["currentSetpoint"], float)
                    else self.attributes["currentSetpoint"],
                    "device_class": "temperature",
                    "unit_of_measurement": "°C",
                } | self.attributes

            # create sensors
            for i, j in sensors.items():
                new_sensor = Sensor(
                    elem_name=i, tydom_attributes_payload=j, mqtt=self.mqtt
                )
                await new_sensor.update()

            # publish current temperature topic
            # not sure the diff of regTemperature and devTemperature, use
            # regTemperature for now
            if "regTemperature" in self.attributes:
                self.mqtt.mqtt_client.publish(
                    self.config["current_temperature_topic"],
                    sensors["reg_temperature"]["reg_temperature"],
                    qos=0,
                    retain=True,
                )

            # publish current set temperature topic
            # not sure the diff of currentSetpoint and a localSetpoint, use
            # currentSetpoint for now
            if "currentSetpoint" in self.attributes:
                self.mqtt.mqtt_client.publish(
                    self.config["temperature_state_topic"],
                    sensors["current_setpoint"]["current_setpoint"],
                    qos=0,
                    retain=True,
                )

            # publish current mode topic
            # if waterFlowReq is true, then the mode is 'heat', otherwise it's
            # 'off'
            if "waterFlowReq" in self.attributes:
                self.mqtt.mqtt_client.publish(
                    self.config["mode_state_topic"],
                    "heat" if sensors["water_flow_req"]["water_flow_req"] else "off",
                    qos=0,
                    retain=True,
                )

            # publish all attributes
            self.mqtt.mqtt_client.publish(
                self.config["json_attributes_topic"],
                self.attributes,
                qos=0,
                retain=True,
            )

            # publish boost state
            if "boost" in self.attributes:
                self.mqtt.mqtt_client.publish(
                    self.switch_config["state_topic"],
                    self.attributes["boost"],
                    qos=0,
                    retain=True,
                )

    @staticmethod
    async def put_temperature(tydom_client, device_id, temperature):
        logger.info("put_temperature: %s to %s", device_id, temperature)
        if not (temperature == ""):
            data = {
                "localSetpoint": temperature,
                "localSetpRemainingTimeStr": "UNTIL_SCHED",
                "localMode": "LOCAL_SETPOINT",
            }
            await tydom_client.put_areas_data(device_id, data)

    @staticmethod
    async def put_boost(tydom_client, device_id, boost):
        logger.info("put_boost: %s to %s", device_id, boost)
        data = {"boost": boost}  # ex: 'boost': 'ON'
        await tydom_client.put_areas_data(device_id, data)
