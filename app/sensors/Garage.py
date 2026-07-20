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

# Toggle-only relays have no open/close/stop distinction and no position
# feedback, so they are exposed as a single-action button (mirrors
# AutomaticDoor) instead of a Cover with three buttons that all send the
# same pulse.
button_config_topic = "homeassistant/button/tydom/{id}/config"
button_command_topic = "button/tydom/{id}/set_garageLevelCmd"
button_state_topic = "button/tydom/{id}/state"


class Garage:
    def __init__(self, tydom_attributes, set_level=None, mqtt=None):
        self.device = None
        self.config = None
        self.config_topic = None
        self.is_button = False
        self.attributes = tydom_attributes
        self.device_id = self.attributes["device_id"]
        self.endpoint_id = self.attributes["endpoint_id"]
        self.id = self.attributes["id"]
        self.name = self.attributes["cover_name"]
        # Toggle-only relays never report "level" (no position feedback).
        self.current_level = self.attributes.get("level")

        self.set_level = set_level
        self.current_position = set_level

        if "position" in tydom_attributes:
            self.current_position = self.attributes["position"]

        self.mqtt = mqtt

    def is_toggle_only(self):
        # Some relays (e.g. Tyxia 4620, x3d_rm) only expose a single
        # "TOGGLE" levelCmd, with no OPEN/CLOSE/STOP and no position
        # feedback; the connected gate/garage motor decides what a pulse
        # means. Real positional garage motors advertise a genuine
        # multi-value enum and must keep the ON/OFF/STOP mapping.
        # Metadata may not have arrived yet (install-sync race) -- default
        # to False (ON/OFF/STOP) in that case.
        # Imported lazily (tydom.MessageHandler imports this module at its
        # own top level, so a module-level import here would deadlock
        # whichever module loads first).
        import tydom.MessageHandler as message_handler

        unique_id = str(self.endpoint_id) + "_" + str(self.device_id)
        capabilities = message_handler.device_metadata.get(unique_id, {})
        return capabilities.get("levelCmd") == ["TOGGLE"]

    async def setup(self):
        self.device = {
            "manufacturer": "Delta Dore",
            "model": "Garage Door Horizontal",
            "name": self.name,
            "identifiers": self.id,
        }
        self.is_button = self.is_toggle_only()

        if self.is_button:
            self.config_topic = button_config_topic.format(id=self.id)
            self.config = {
                "name": None,  # set an MQTT entity's name to None to mark it as the main feature of a device
                "unique_id": self.id,
                "device": self.device,
                "command_topic": button_command_topic.format(id=self.id),
                "button_state_topic": button_state_topic.format(id=self.id),
                "payload_press": "TOGGLE",
                "icon": "mdi:gate"
                if self.attributes["cover_class"] == "gate"
                else "mdi:garage",
            }

            if self.mqtt is not None:
                # Clear a stale Cover entity, in case this device was first
                # set up as ON/OFF/STOP before its capability metadata
                # (install-sync) confirmed it's toggle-only.
                self.mqtt.mqtt_client.publish(
                    cover_config_topic.format(id=self.id), "", qos=0, retain=True
                )
        else:
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
            self.config["json_attributes_topic"] = cover_attributes_topic.format(
                id=self.id
            )

            if self.mqtt is not None:
                # Clear a stale button entity, in case capability metadata
                # changed since this device was last set up as toggle-only.
                self.mqtt.mqtt_client.publish(
                    button_config_topic.format(id=self.id), "", qos=0, retain=True
                )

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

        if self.is_button:
            if self.mqtt is not None:
                self.mqtt.mqtt_client.publish(
                    self.config["button_state_topic"],
                    self.attributes,
                    qos=0,
                    retain=True,
                )

            logger.info(
                "GarageDoor Horizontal (toggle button) created / updated : %s %s",
                self.name,
                self.id,
            )
            return

        self.level_topic = cover_state_topic.format(id=self.id)

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
