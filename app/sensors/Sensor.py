import json
import logging

logger = logging.getLogger(__name__)
sensor_topic = "sensor/tydom/#"
sensor_config_topic = "homeassistant/sensor/tydom/{id}/config"
sensor_json_attributes_topic = "sensor/tydom/{id}/state"

binary_sensor_topic = "binary_sensor/tydom/#"
binary_sensor_config_topic = "homeassistant/binary_sensor/tydom/{id}/config"
binary_sensor_json_attributes_topic = "binary_sensor/tydom/{id}/state"


class Sensor:
    def __init__(self, elem_name, tydom_attributes_payload, mqtt=None):
        self.config = None
        self.config_sensor_topic = None
        self.device = None
        self.elem_name = elem_name
        self.elem_value = tydom_attributes_payload[self.elem_name]

        # init a state json
        state_dict = {elem_name: self.elem_value}
        self.attributes = state_dict

        # extracted from json, but it will make sensor not in payload to be
        # considered offline....
        self.parent_device_id = str(tydom_attributes_payload["id"])
        self.parent_name = str(tydom_attributes_payload["name"])
        self.id = elem_name + "_tydom_" + str(tydom_attributes_payload["id"])
        self.name = elem_name
        if "device_class" in tydom_attributes_payload.keys():
            self.device_class = tydom_attributes_payload["device_class"]

        if "state_class" in tydom_attributes_payload.keys():
            self.state_class = tydom_attributes_payload["state_class"]

        if "unit_of_measurement" in tydom_attributes_payload.keys():
            self.unit_of_measurement = tydom_attributes_payload["unit_of_measurement"]

        self.mqtt = mqtt
        self.binary = False

        if "unit_of_measurement" not in tydom_attributes_payload.keys() and (
            self.elem_value in ["0", "1", "true", "false", "True", "False", "ON", "OFF"]
            or isinstance(self.elem_value, bool)
        ):
            self.binary = True

            if (
                (isinstance(self.elem_value, bool) and self.elem_value)
                or self.elem_value == "True"
                or self.elem_value == "true"
                or self.elem_value == "1"
                or self.elem_value == "ON"
            ):
                self.elem_value = "ON"
            else:
                self.elem_value = "OFF"

            self.json_attributes_topic = binary_sensor_json_attributes_topic.format(
                id=self.id
            )
            self.config_topic = binary_sensor_config_topic.format(id=self.id)
        else:
            self.json_attributes_topic = sensor_json_attributes_topic.format(id=self.id)
            self.config_topic = sensor_config_topic.format(id=self.id)

    # SENSOR:
    # None: Generic sensor. This is the default and doesn’t need to be set.
    # battery: Percentage of battery that is left.
    # humidity: Percentage of humidity in the air.
    # illuminance: The current light level in lx or lm.
    # signal_strength: Signal strength in dB or dBm.
    # temperature: Temperature in °C or °F.
    # power: Power in W or kW.
    # pressure: Pressure in hPa or mbar.
    # timestamp: Datetime object or timestamp string.
    # BINARY :
    # None: Generic on/off. This is the default and doesn’t need to be set.
    # battery: on means low, off means normal
    # cold: on means cold, off means normal
    # connectivity: on means connected, off means disconnected
    # door: on means open, off means closed
    # garage_door: on means open, off means closed
    # gas: on means gas detected, off means no gas (clear)
    # heat: on means hot, off means normal
    # light: on means light detected, off means no light
    # lock: on means open (unlocked), off means closed (locked)
    # moisture: on means moisture detected (wet), off means no moisture (dry)
    # motion: on means motion detected, off means no motion (clear)
    # moving: on means moving, off means not moving (stopped)
    # occupancy: on means occupied, off means not occupied (clear)
    # opening: on means open, off means closed
    # plug: on means device is plugged in, off means device is unplugged
    # power: on means power detected, off means no power
    # presence: on means home, off means away
    # problem: on means problem detected, off means no problem (OK)
    # safety: on means unsafe, off means safe
    # smoke: on means smoke detected, off means no smoke (clear)
    # sound: on means sound detected, off means no sound (clear)
    # vibration: on means vibration detected, off means no vibration (clear)
    # window: on means open, off means closed

    async def setup(self):
        self.device = {
            "manufacturer": "Delta Dore",
            "identifiers": self.parent_device_id,
            "model": "Sensor",
            "name": self.parent_name,
        }

        self.config_sensor_topic = sensor_config_topic.format(id=self.id)

        self.config = {"name": self.name, "unique_id": self.id}
        try:
            self.config["device_class"] = self.device_class
        except AttributeError:
            pass
        try:
            self.config["state_class"] = self.state_class
        except AttributeError:
            pass
        try:
            self.config["unit_of_measurement"] = self.unit_of_measurement
        except AttributeError:
            pass

        self.config["device"] = self.device
        self.config["state_topic"] = self.json_attributes_topic

        if self.mqtt is not None:
            self.mqtt.mqtt_client.publish(
                self.config_topic.lower(), json.dumps(self.config), qos=0, retain=True
            )  # sensor Config

    async def update(self):
        # 3 items are necessary :
        # config to config config_sensor_topic + config payload is the schema
        # state payload to state topic in config with all attributes

        if (
            "name" in self.elem_name
            or "device_type" in self.elem_name
            or self.elem_value is None
        ):
            pass  # OOOOOOOOOH that's quick and dirty
        else:
            await self.setup()  # Publish config
            # Publish state json to state topic
            if self.mqtt is not None:
                self.mqtt.mqtt_client.publish(
                    self.json_attributes_topic, self.elem_value, qos=0, retain=True
                )
            if not self.binary:
                logger.info(
                    "Sensor created / updated : %s %s", self.name, self.elem_value
                )
            else:
                logger.info(
                    "Binary sensor created / updated : %s %s",
                    self.name,
                    self.elem_value,
                )
