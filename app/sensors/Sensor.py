import json
import logging

logger = logging.getLogger(__name__)
sensor_topic = "sensor/tydom/#"
sensor_config_topic = "homeassistant/sensor/tydom/{id}/config"
sensor_json_attributes_topic = "sensor/tydom/{id}/state"

binary_sensor_topic = "binary_sensor/tydom/#"
binary_sensor_config_topic = "homeassistant/binary_sensor/tydom/{id}/config"
binary_sensor_json_attributes_topic = "binary_sensor/tydom/{id}/state"

# Binary Tydom health flags and their Home Assistant device class
binary_diagnostic_classes = {
    "battDefect": "battery",
    "thermicDefect": "problem",
    "obstacleDefect": "problem",
    "calibrationDefect": "problem",
    "cmdDefect": "problem",
    "loadDefect": "problem",
    "techSmokeDefect": "problem",
}


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
        # An opening detector may be published on its window group's device
        self.attached_to_parent = "parent_id" in tydom_attributes_payload
        self.parent_device_id = str(
            tydom_attributes_payload.get("parent_id", tydom_attributes_payload["id"])
        )
        self.parent_name = str(
            tydom_attributes_payload.get(
                "parent_name", tydom_attributes_payload["name"]
            )
        )
        self.id = elem_name + "_tydom_" + str(tydom_attributes_payload["id"])
        # Several detectors share the window device: prefix with their name
        member_name = tydom_attributes_payload.get("member_name")
        self.name = f"{member_name} {elem_name}" if member_name else elem_name
        self.entity_category = None

        # Per-element metadata wins over the device-wide one, so a device
        # publishing several elements doesn't share one class / unit
        meta = tydom_attributes_payload.get("element_meta", {}).get(elem_name)
        if meta is None:
            meta = tydom_attributes_payload

        if "device_class" in meta.keys():
            self.device_class = meta["device_class"]

        if "state_class" in meta.keys():
            self.state_class = meta["state_class"]

        if "unit_of_measurement" in meta.keys():
            self.unit_of_measurement = meta["unit_of_measurement"]
        else:
            # Fallback for known sensor types that should have units
            self.unit_of_measurement = self._get_default_unit_for_sensor(elem_name)

        self.mqtt = mqtt
        self.binary = False

        # Check if this should be a binary sensor (no units and boolean-like values)
        has_unit = self.unit_of_measurement is not None

        if not has_unit and (
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

            # Health / defect flags: proper class, kept out of main dashboards
            if elem_name in binary_diagnostic_classes:
                self.device_class = binary_diagnostic_classes[elem_name]
                self.entity_category = "diagnostic"
        else:
            self.json_attributes_topic = sensor_json_attributes_topic.format(id=self.id)
            self.config_topic = sensor_config_topic.format(id=self.id)

    def _get_default_unit_for_sensor(self, elem_name):
        """Get default unit of measurement for known sensor types."""
        default_units = {
            "outTemperature": "°C",
            "temperature": "°C",
            "lightPower": "W",
            "power": "W",
            "energyInstantTotElec": "A",
            "energyInstantTotElecP": "W",
            "energyTotIndexWatt": "Wh",
            "energyIndexHeatWatt": "Wh",
            "energyIndexECSWatt": "Wh",
            "energyIndexHeatGas": "Wh",
            # Add more common sensor types
            "humidity": "%",
            "pressure": "hPa",
            "batteryLevel": "%",
            "current": "A",
            "voltage": "V",
            "energy": "Wh",
            "setpoint": "°C",
        }
        return default_units.get(elem_name, None)

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
            "model": "Window" if self.attached_to_parent else "Sensor",
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
            if self.unit_of_measurement is not None:
                self.config["unit_of_measurement"] = self.unit_of_measurement
        except AttributeError:
            pass

        if self.entity_category is not None:
            self.config["entity_category"] = self.entity_category

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
                unit_info = (
                    f" {self.unit_of_measurement}" if self.unit_of_measurement else ""
                )
                logger.info(
                    "Sensor created / updated : %s %s%s",
                    self.name,
                    self.elem_value,
                    unit_info,
                )
            else:
                logger.info(
                    "Binary sensor created / updated : %s %s",
                    self.name,
                    self.elem_value,
                )
