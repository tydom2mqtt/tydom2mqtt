import json
import logging

logger = logging.getLogger(__name__)
opening_config_topic = "homeassistant/binary_sensor/tydom/opening_tydom_{id}/config"
opening_state_topic = "binary_sensor/tydom/opening_tydom_{id}/state"

# Tydom reports a window / door as closed only when its openState is LOCKED;
# any other value (UNLOCKED, OPEN_FRENCH, OPEN_HOPPER, ...) means open.
# K-Line detectors whose openState is LOCKED / UNLOCKED only report UNLOCKED
# (with intrusionDetect true) as soon as the sash is opened, even slightly
# (checked on a real installation).
CLOSED_OPEN_STATE = "LOCKED"


class Opening:
    """Open / closed binary sensor of a Tydom window or door (openState)."""

    def __init__(self, tydom_attributes, mqtt=None):
        self.attributes = tydom_attributes
        self.id = str(self.attributes["id"])
        # A detector member of a window group is published on the window's
        # device (named after the group), under its own detector name
        self.attached_to_parent = "parent_id" in self.attributes
        self.device_id = str(self.attributes.get("parent_id", self.id))
        self.name = str(self.attributes.get("parent_name", self.attributes["name"]))
        self.member_name = self.attributes.get("member_name")
        self.device_class = self.attributes.get("opening_class", "window")
        self.open_state = self.attributes["openState"]
        self.mqtt = mqtt
        self.config = None

    async def setup(self):
        self.config = {
            # In a window group: named after the detector ("Ouvrant gauche");
            # standalone: name None, the opening is the device's main feature
            "name": self.member_name if self.attached_to_parent else None,
            "unique_id": "opening_tydom_" + self.id,
            "device_class": self.device_class,
            "state_topic": opening_state_topic.format(id=self.id),
            "payload_on": "ON",
            "payload_off": "OFF",
            "device": {
                "manufacturer": "Delta Dore",
                "identifiers": self.device_id,
                "model": "Window" if self.attached_to_parent else "Sensor",
                "name": self.name,
            },
        }

        if self.mqtt is not None:
            self.mqtt.mqtt_client.publish(
                opening_config_topic.format(id=self.id),
                json.dumps(self.config),
                qos=0,
                retain=True,
            )

    def state(self):
        return "OFF" if self.open_state == CLOSED_OPEN_STATE else "ON"

    async def update(self):
        await self.setup()
        if self.mqtt is not None:
            self.mqtt.mqtt_client.publish(
                self.config["state_topic"], self.state(), qos=0, retain=True
            )
        logger.info(
            "Opening created / updated : %s %s (%s)",
            self.name,
            self.state(),
            self.open_state,
        )
