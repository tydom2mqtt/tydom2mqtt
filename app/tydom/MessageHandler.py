import json
import logging
from http.client import HTTPResponse
from http.server import BaseHTTPRequestHandler
from io import BytesIO

from sensors.Alarm import Alarm
from sensors.Boiler import Boiler
from sensors.Cover import Cover
from sensors.Garage import Garage
from sensors.Light import Light
from sensors.Sensor import Sensor
from sensors.Switch import Switch
from sensors.ShHvac import ShHvac
from sensors.AutomaticDoor import AutomaticDoor

logger = logging.getLogger(__name__)

# Dicts
deviceAlarmKeywords = [
    "alarmMode",
    "alarmState",
    "alarmSOS",
    "zone1State",
    "zone2State",
    "zone3State",
    "zone4State",
    "zone5State",
    "zone6State",
    "zone7State",
    "zone8State",
    "gsmLevel",
    "inactiveProduct",
    "zone1State",
    "liveCheckRunning",
    "networkDefect",
    "unitAutoProtect",
    "unitBatteryDefect",
    "unackedEvent",
    "alarmTechnical",
    "systAutoProtect",
    "systBatteryDefect",
    "systSupervisionDefect",
    "systOpenIssue",
    "systTechnicalDefect",
    "videoLinkDefect",
    "outTemperature",
    "kernelUpToDate",
    "irv1State",
    "irv2State",
    "irv3State",
    "irv4State",
    "simDefect",
    "remoteSurveyDefect",
    "systSectorDefect",
]
deviceAlarmDetailsKeywords = [
    "alarmSOS",
    "zone1State",
    "zone2State",
    "zone3State",
    "zone4State",
    "zone5State",
    "zone6State",
    "zone7State",
    "zone8State",
    "gsmLevel",
    "inactiveProduct",
    "zone1State",
    "liveCheckRunning",
    "networkDefect",
    "unitAutoProtect",
    "unitBatteryDefect",
    "unackedEvent",
    "alarmTechnical",
    "systAutoProtect",
    "systBatteryDefect",
    "systSupervisionDefect",
    "systOpenIssue",
    "systTechnicalDefect",
    "videoLinkDefect",
    "outTemperature",
]

deviceLightKeywords = [
    "level",
    "onFavPos",
    "thermicDefect",
    "battDefect",
    "loadDefect",
    "cmdDefect",
    "onPresenceDetected",
    "onDusk",
]
deviceLightDetailsKeywords = [
    "onFavPos",
    "thermicDefect",
    "battDefect",
    "loadDefect",
    "cmdDefect",
    "onPresenceDetected",
    "onDusk",
]

deviceDoorKeywords = [
    "openState",
    "intrusionDetect",
    "battDefect",
    "supervisionMode",
    "calibrationDefect",
]
deviceDoorDetailsKeywords = [
    "onFavPos",
    "thermicDefect",
    "obstacleDefect",
    "intrusionDetect",
    "battDefect",
    "supervisionMode" "calibrationDefect",
]

deviceAutomaticDoorKeywords = ["podPosition"]
deviceAutomaticDoorDetailsKeywords = ["podPosition"]

deviceGaragelKeywords = [
    "level",
    "onDusk",
    "onFavPos",
    "onPresenceDetected" "thermicDefect",
    "loadDefect",
    "cmdDefect",
    "battDefect",
]

deviceGarageDetailsKeywords = [
    "level",
    "onDusk",
    "onFavPos",
    "onPresenceDetected" "thermicDefect",
    "loadDefect",
    "cmdDefect",
    "battDefect",
]

deviceCoverKeywords = [
    "position",
    "slope",
    "onFavPos",
    "thermicDefect",
    "obstacleDefect",
    "intrusion",
    "battDefect",
]
deviceCoverDetailsKeywords = [
    "onFavPos",
    "thermicDefect",
    "obstacleDefect",
    "intrusion",
    "battDefect",
    "position",
    "slope",
]

deviceSensorsKeywords = [
    "outTemperature",
    "lightPower",
    "configSensor",
    "configTemp",
    "battDefect",
]
deviceSensorsDetailsKeywords = [
    "outTemperature" "lightPower",
    "battDefect",
    "configSensor",
    "configTemp",
]
deviceBoilerKeywords = [
    "thermicLevel",
    "delayThermicLevel",
    "temperature",
    "authorization",
    "hvacMode",
    "timeDelay",
    "tempoOn",
    "antifrostOn",
    "openingDetected",
    "presenceDetected",
    "absence",
    "loadSheddingOn",
    "setpoint",
    "delaySetpoint",
    "anticipCoeff",
    "outTemperature",
]

deviceShHvacKeywords = [
    # from /devices/data
    "battDefect",
    "waterFlowReq",
    "regTemperature",
    "devTemperature",
    "activationIndex",
    "calibrationStatus",
    "indexTimeOn",
    "tempOffset",
    "jobs",
    "jobsMP",
    "softVersion0",
    "softPlan0",
    "softVersion1",
    "softPlan1",
    "softVersion2",
    "softPlan2",
    "uid",
    # from /areas/data
    "jobs",
    "masterSchedSetpoint",
    "masterAbsSetpoint",
    "localSetpoint",
    "antiFrostSetpoint",
    "currentSetpoint",
    "masterMode",
    "localMode",
    "localSetpRemainingTime",
    "localSetpRemainingTimeStr",
    "optionMode",
    "boost",
    "boostDuration",
    "boostRemainingTime",
    "openWinActive",
    "winOpened",
    "localSetpDuration",
    "localSetpDurationStr",
    "antiSeizurePeriod",
    "lockConfig",
    "displayConfig",
    "anticipCoeff",
]

deviceSwitchKeywords = ["thermicDefect"]
deviceSwitchDetailsKeywords = ["thermicDefect"]

deviceMotionKeywords = ["motionDetect"]
deviceMotionDetailsKeywords = ["motionDetect"]

device_conso_classes = {
    "energyInstantTotElec": "current",
    "energyInstantTotElec_Min": "current",
    "energyInstantTotElec_Max": "current",
    "energyScaleTotElec_Min": "current",
    "energyScaleTotElec_Max": "current",
    "energyInstantTotElecP": "power",
    "energyInstantTotElec_P_Min": "power",
    "energyInstantTotElec_P_Max": "power",
    "energyScaleTotElec_P_Min": "power",
    "energyScaleTotElec_P_Max": "power",
    "energyInstantTi1P": "power",
    "energyInstantTi1P_Min": "power",
    "energyInstantTi1P_Max": "power",
    "energyScaleTi1P_Min": "power",
    "energyScaleTi1P_Max": "power",
    "energyInstantTi1I": "current",
    "energyInstantTi1I_Min": "current",
    "energyInstantTi1I_Max": "current",
    "energyScaleTi1I_Min": "current",
    "energyScaleTi1I_Max": "current",
    "energyTotIndexWatt": "energy",
    "energyIndexHeatWatt": "energy",
    "energyIndexECSWatt": "energy",
    "energyIndexHeatGas": "energy",
    "outTemperature": "temperature",
}

device_conso_unit_of_measurement = {
    "energyInstantTotElec": "A",
    "energyInstantTotElec_Min": "A",
    "energyInstantTotElec_Max": "A",
    "energyScaleTotElec_Min": "A",
    "energyScaleTotElec_Max": "A",
    "energyInstantTotElecP": "W",
    "energyInstantTotElec_P_Min": "W",
    "energyInstantTotElec_P_Max": "W",
    "energyScaleTotElec_P_Min": "W",
    "energyScaleTotElec_P_Max": "W",
    "energyInstantTi1P": "W",
    "energyInstantTi1P_Min": "W",
    "energyInstantTi1P_Max": "W",
    "energyScaleTi1P_Min": "W",
    "energyScaleTi1P_Max": "W",
    "energyInstantTi1I": "A",
    "energyInstantTi1I_Min": "A",
    "energyInstantTi1I_Max": "A",
    "energyScaleTi1I_Min": "A",
    "energyScaleTi1I_Max": "A",
    "energyTotIndexWatt": "Wh",
    "energyIndexHeatWatt": "Wh",
    "energyIndexECSWatt": "Wh",
    "energyIndexHeatGas": "Wh",
    "outTemperature": "C",
}
device_conso_keywords = device_conso_classes.keys()

deviceSmokeKeywords = ["techSmokeDefect"]

# Device dict for parsing
device_name = dict()
device_endpoint = dict()
device_type = dict()


class MessageHandler:
    def __init__(self, incoming_bytes, tydom_client, mqtt_client):
        self.incoming_bytes = incoming_bytes
        self.tydom_client = tydom_client
        self.cmd_prefix = tydom_client.cmd_prefix
        self.mqtt_client = mqtt_client

    async def incoming_triage(self):
        bytes_str = self.incoming_bytes
        incoming = None
        first = str(bytes_str[:40])

        try:
            if "Uri-Origin: /refresh/all" in first in first:
                pass
            elif (
                ("PUT /devices/data" in first)
                or ("/devices/cdata" in first)
                or ("PUT /areas/data" in first)
            ):
                logger.debug("PUT /devices/data or /areas/data message detected !")
                try:
                    try:
                        incoming = self.parse_put_response(bytes_str)
                    except BaseException:
                        # Tywatt response starts at 7
                        incoming = self.parse_put_response(bytes_str, 7)
                    await self.parse_response(incoming)
                except BaseException as e:
                    logger.error(
                        "Error when parsing devices/data tydom message (%s)", bytes_str
                    )
                    logger.exception(e)
            elif "scn" in first:
                try:
                    await self.parse_response(bytes_str)
                    logger.debug("Scenarii message processed")
                except BaseException as e:
                    logger.error(
                        "Error when parsing Scenarii tydom message (%s)", bytes_str
                    )
                    logger.exception(e)
            elif "POST" in first:
                try:
                    incoming = self.parse_put_response(bytes_str)
                    await self.parse_response(incoming)
                    logger.debug("POST message processed")
                except BaseException as e:
                    logger.error(
                        "Error when parsing POST tydom message (%s)", bytes_str
                    )
                    logger.exception(e)
            elif "HTTP/1.1" in first:
                response = self.response_from_bytes(bytes_str[len(self.cmd_prefix) :])
                incoming = response.decode("utf-8")
                try:
                    await self.parse_response(incoming)
                except BaseException as e:
                    logger.error(
                        "Error when parsing HTTP/1.1 tydom message (%s)", bytes_str
                    )
                    logger.exception(e)
            else:
                logger.warning("Unknown tydom message type received (%s)", bytes_str)

        except Exception as e:
            logger.error(
                "Technical error when parsing tydom message (error=%s), (message=%s)",
                e,
                bytes_str,
            )
            logger.debug("Incoming payload (%s)", incoming)
            logger.exception(e)

    # Basic response parsing. Typically GET responses + instanciate covers and
    # alarm class for updating data
    async def parse_response(self, incoming):
        data = incoming
        msg_type = None
        first = str(data[:40])

        if data != "":
            if "id_catalog" in data:
                msg_type = "msg_config"
            elif "cmetadata" in data:
                msg_type = "msg_cmetadata"
            elif "cdata" in data:
                msg_type = "msg_cdata"
            elif "id" in first:
                msg_type = "msg_data"
            elif "doctype" in first:
                msg_type = "msg_html"
            elif "productName" in first:
                msg_type = "msg_info"

            if msg_type is None:
                logger.warning("Unknown message type received (%s)", data)
            else:
                logger.debug("Message received detected as (%s)", msg_type)
                try:
                    if msg_type == "msg_config":
                        parsed = json.loads(data)
                        await self.parse_config_data(parsed=parsed)

                    elif msg_type == "msg_cmetadata":
                        parsed = json.loads(data)
                        await self.parse_cmeta_data(parsed=parsed)

                    elif msg_type == "msg_data":
                        parsed = json.loads(data)
                        await self.parse_devices_data(parsed=parsed)

                    elif msg_type == "msg_cdata":
                        parsed = json.loads(data)
                        await self.parse_devices_cdata(parsed=parsed)

                    elif msg_type == "msg_html":
                        logger.debug("HTML Response ?")

                    elif msg_type == "msg_info":
                        pass
                except Exception as e:
                    logger.error("Error on parsing tydom response (%s)", e)
                    logger.error("Incoming data (%s)", data)
                    logger.exception(e)
            logger.debug("Incoming data parsed with success")

    @staticmethod
    async def parse_config_data(parsed):
        for i in parsed["endpoints"]:
            device_unique_id = str(i["id_endpoint"]) + "_" + str(i["id_device"])

            if (
                i["last_usage"] == "shutter"
                or i["last_usage"] == "klineShutter"
                or i["last_usage"] == "light"
                or i["last_usage"] == "window"
                or i["last_usage"] == "windowFrench"
                or i["last_usage"] == "windowSliding"
                or i["last_usage"] == "belmDoor"
                or i["last_usage"] == "klineDoor"
                or i["last_usage"] == "klineWindowFrench"
                or i["last_usage"] == "klineWindowSliding"
                or i["last_usage"] == "garage_door"
                or i["last_usage"] == "gate"
                or i["last_usage"] == "awning"
                or i["last_usage"] == "garage_door_horizontal"
                or i["last_usage"] == "others"
                or i["last_usage"] == "sensorSun"
                or i["last_usage"] == "sensorThermo"
            ):
                device_name[device_unique_id] = i["name"]
                device_type[device_unique_id] = i["last_usage"]
                device_endpoint[device_unique_id] = i["id_endpoint"]

            if (
                i["last_usage"] == "boiler"
                or i["last_usage"] == "conso"
                or i["last_usage"] == "sh_hvac"
            ):
                device_name[device_unique_id] = i["name"]
                device_type[device_unique_id] = i["last_usage"]
                device_endpoint[device_unique_id] = i["id_endpoint"]

            if i["last_usage"] == "alarm":
                device_name[device_unique_id] = "Tyxal Alarm"
                device_type[device_unique_id] = "alarm"
                device_endpoint[device_unique_id] = i["id_endpoint"]

            if i["last_usage"] == "electric":
                device_name[device_unique_id] = i["name"]
                device_type[device_unique_id] = "boiler"
                device_endpoint[device_unique_id] = i["id_endpoint"]

            if i["last_usage"] == "sensorDFR":
                device_name[device_unique_id] = i["name"]
                device_type[device_unique_id] = "smoke"
                device_endpoint[device_unique_id] = i["id_endpoint"]

            if i["last_usage"] == "":
                device_name[device_unique_id] = i["name"]
                device_type[device_unique_id] = "unknown"
                device_endpoint[device_unique_id] = i["id_endpoint"]

        logger.debug("Configuration updated")

    async def parse_cmeta_data(self, parsed):
        for i in parsed:
            for endpoint in i["endpoints"]:
                if len(endpoint["cmetadata"]) > 0:
                    for elem in endpoint["cmetadata"]:
                        device_id = i["id"]
                        endpoint_id = endpoint["id"]
                        unique_id = str(endpoint_id) + "_" + str(device_id)

                        if elem["name"] == "energyIndex":
                            device_name[unique_id] = "Tywatt"
                            device_type[unique_id] = "conso"
                            for params in elem["parameters"]:
                                if params["name"] == "dest":
                                    for dest in params["enum_values"]:
                                        url = (
                                            "/devices/"
                                            + str(i["id"])
                                            + "/endpoints/"
                                            + str(endpoint["id"])
                                            + "/cdata?name="
                                            + elem["name"]
                                            + "&dest="
                                            + dest
                                            + "&reset=false"
                                        )
                                        self.tydom_client.add_poll_device_url(url)
                                        logger.debug("Add poll device : " + url)
                        elif elem["name"] == "energyInstant":
                            device_name[unique_id] = "Tywatt"
                            device_type[unique_id] = "conso"
                            for params in elem["parameters"]:
                                if params["name"] == "unit":
                                    for unit in params["enum_values"]:
                                        url = (
                                            "/devices/"
                                            + str(i["id"])
                                            + "/endpoints/"
                                            + str(endpoint["id"])
                                            + "/cdata?name="
                                            + elem["name"]
                                            + "&unit="
                                            + unit
                                            + "&reset=false"
                                        )
                                        self.tydom_client.add_poll_device_url(url)
                                        logger.debug("Add poll device : " + url)
                        elif elem["name"] == "energyDistrib":
                            device_name[unique_id] = "Tywatt"
                            device_type[unique_id] = "conso"
                            for params in elem["parameters"]:
                                if params["name"] == "src":
                                    for src in params["enum_values"]:
                                        url = (
                                            "/devices/"
                                            + str(i["id"])
                                            + "/endpoints/"
                                            + str(endpoint["id"])
                                            + "/cdata?name="
                                            + elem["name"]
                                            + "&period=YEAR&periodOffset=0&src="
                                            + src
                                        )
                                        self.tydom_client.add_poll_device_url(url)
                                        logger.debug("Add poll device : " + url)

        logger.debug("Metadata configuration updated")

    async def parse_devices_data(self, parsed):
        if isinstance(parsed, list):
            for i in parsed:
                if "endpoints" in i:  # case of GET /devices/data
                    for endpoint in i["endpoints"]:
                        await self.parse_endpoint_data(endpoint, i["id"])
                else:  # case of GET /areas/data
                    await self.parse_endpoint_data(i, i["id"])
        elif isinstance(parsed, dict):
            await self.parse_endpoint_data(parsed, parsed["id"])
        else:
            logger.error("Unknown data type")
            logger.debug(parsed)

    async def parse_endpoint_data(self, endpoint, device_id):
        if endpoint["error"] == 0 and len(endpoint["data"]) > 0:
            try:
                attr_alarm = {}
                attr_cover = {}
                attr_garage = {}
                attr_door = {}
                attr_ukn = {}
                attr_window = {}
                attr_light = {}
                attr_gate = {}
                attr_boiler = {}
                attr_sh_hvac = {}
                attr_smoke = {}
                attr_sensor = {}
                attr_automatic_door = {}

                endpoint_id = endpoint["id"]
                unique_id = str(endpoint_id) + "_" + str(device_id)
                name_of_id = self.get_name_from_id(unique_id)
                type_of_id = self.get_type_from_id(unique_id)

                logger.info(
                    "Device update (id=%s, endpoint=%s, name=%s, type=%s)",
                    device_id,
                    endpoint_id,
                    name_of_id,
                    type_of_id,
                )

                for elem in endpoint["data"]:
                    element_name = elem["name"]
                    element_value = elem["value"]
                    element_validity = elem["validity"]
                    print_id = name_of_id if len(name_of_id) != 0 else device_id

                    if type_of_id == "light":
                        if (
                            element_name in deviceLightKeywords
                            and element_validity == "upToDate"
                        ):
                            attr_light["device_id"] = device_id
                            attr_light["endpoint_id"] = endpoint_id
                            attr_light["id"] = str(device_id) + "_" + str(endpoint_id)
                            attr_light["light_name"] = print_id
                            attr_light["name"] = print_id
                            attr_light["device_type"] = "light"
                            attr_light[element_name] = element_value

                    if (
                        type_of_id == "shutter"
                        or type_of_id == "awning"
                        or type_of_id == "klineShutter"
                    ):
                        if (
                            element_name in deviceCoverKeywords
                            and element_validity == "upToDate"
                        ):
                            attr_cover["device_id"] = device_id
                            attr_cover["endpoint_id"] = endpoint_id
                            attr_cover["id"] = str(device_id) + "_" + str(endpoint_id)
                            attr_cover["cover_name"] = print_id
                            attr_cover["name"] = print_id
                            attr_cover["device_type"] = "cover"

                            if element_name == "slope":
                                attr_cover["tilt"] = element_value
                            else:
                                attr_cover[element_name] = element_value

                    if type_of_id == "belmDoor" or type_of_id == "klineDoor":
                        if (
                            element_name in deviceDoorKeywords
                            and element_validity == "upToDate"
                        ):
                            attr_door["device_id"] = device_id
                            attr_door["endpoint_id"] = endpoint_id
                            attr_door["id"] = str(device_id) + "_" + str(endpoint_id)
                            attr_door["door_name"] = print_id
                            attr_door["name"] = print_id
                            attr_door["device_type"] = "sensor"
                            attr_door["element_name"] = element_name
                            attr_door[element_name] = element_value

                    if type_of_id == "belmDoor" or type_of_id == "klineDoor":
                        if (
                            element_name in deviceAutomaticDoorKeywords
                            and element_validity == "upToDate"
                        ):
                            attr_automatic_door["device_id"] = device_id
                            attr_automatic_door["endpoint_id"] = endpoint_id
                            attr_automatic_door["id"] = (
                                str(device_id) + "_" + str(endpoint_id)
                            )
                            attr_automatic_door["name"] = print_id
                            attr_automatic_door["device_type"] = "AutomaticDoor"
                            attr_automatic_door["element_name"] = element_name
                            attr_automatic_door[element_name] = element_value

                    if (
                        type_of_id == "windowFrench"
                        or type_of_id == "window"
                        or type_of_id == "windowSliding"
                        or type_of_id == "klineWindowFrench"
                        or type_of_id == "klineWindowSliding"
                    ):
                        if (
                            element_name in deviceDoorKeywords
                            and element_validity == "upToDate"
                        ):
                            attr_window["device_id"] = device_id
                            attr_window["endpoint_id"] = endpoint_id
                            attr_window["id"] = str(device_id) + "_" + str(endpoint_id)
                            attr_window["door_name"] = print_id
                            attr_window["name"] = print_id
                            attr_window["device_type"] = "sensor"
                            attr_window["element_name"] = element_name
                            attr_window[element_name] = element_value

                    if type_of_id == "sensorThermo" or type_of_id == "sensorSun":
                        if (
                            element_name in deviceSensorsKeywords
                            and element_validity == "upToDate"
                        ):
                            attr_sensor["device_id"] = device_id
                            attr_sensor["endpoint_id"] = endpoint_id
                            attr_sensor["id"] = str(device_id) + "_" + str(endpoint_id)
                            attr_sensor["name"] = print_id
                            attr_sensor["device_type"] = "sensor"
                            attr_sensor["element_name"] = element_name
                            attr_sensor[element_name] = element_value

                    if type_of_id == "boiler":
                        if (
                            element_name in deviceBoilerKeywords
                            and element_validity == "upToDate"
                        ):
                            attr_boiler["device_id"] = device_id
                            attr_boiler["endpoint_id"] = endpoint_id
                            attr_boiler["id"] = str(device_id) + "_" + str(endpoint_id)
                            # attr_boiler['boiler_name'] = print_id
                            attr_boiler["name"] = print_id
                            attr_boiler["device_type"] = "climate"
                            attr_boiler[element_name] = element_value

                    if type_of_id == "alarm":
                        if (
                            element_name in deviceAlarmKeywords
                            and element_validity == "upToDate"
                        ):
                            attr_alarm["device_id"] = device_id
                            attr_alarm["endpoint_id"] = endpoint_id
                            attr_alarm["id"] = str(device_id) + "_" + str(endpoint_id)
                            attr_alarm["alarm_name"] = "Tyxal Alarm"
                            attr_alarm["name"] = "Tyxal Alarm"
                            attr_alarm["device_type"] = "alarm_control_panel"
                            attr_alarm[element_name] = element_value

                    if (
                        type_of_id == "garage_door_horizontal"
                        or type_of_id == "garage_door"
                        or type_of_id == "gate"
                    ):
                        if (
                            element_name in deviceGaragelKeywords
                            and element_validity == "upToDate"
                        ):
                            attr_garage["device_id"] = device_id
                            attr_garage["endpoint_id"] = endpoint_id
                            attr_garage["id"] = str(device_id) + "_" + str(endpoint_id)
                            attr_garage["cover_name"] = print_id
                            attr_garage["name"] = print_id
                            attr_garage["device_type"] = "garage"
                            if type_of_id == "garage_door":
                                attr_garage["cover_class"] = "garage"
                            else:
                                attr_garage["cover_class"] = "gate"
                            attr_garage[element_name] = element_value

                    if type_of_id == "conso":
                        if (
                            element_name in device_conso_keywords
                            and element_validity == "upToDate"
                        ):
                            attr_conso = {
                                "device_id": device_id,
                                "endpoint_id": endpoint_id,
                                "id": str(device_id) + "_" + str(endpoint_id),
                                "name": print_id,
                                "device_type": "sensor",
                                element_name: element_value,
                            }

                            if element_name in device_conso_classes:
                                attr_conso["device_class"] = device_conso_classes[
                                    element_name
                                ]

                            if element_name in device_conso_unit_of_measurement:
                                attr_conso["unit_of_measurement"] = (
                                    device_conso_unit_of_measurement[element_name]
                                )

                            new_conso = Sensor(
                                elem_name=element_name,
                                tydom_attributes_payload=attr_conso,
                                mqtt=self.mqtt_client,
                            )
                            await new_conso.update()

                    if type_of_id == "sh_hvac":
                        if (
                            element_name in deviceShHvacKeywords
                            and element_validity == "upToDate"
                        ):
                            attr_sh_hvac["device_id"] = device_id
                            attr_sh_hvac["endpoint_id"] = endpoint_id
                            attr_sh_hvac["id"] = str(device_id) + "_" + str(endpoint_id)
                            attr_sh_hvac["name"] = print_id
                            attr_sh_hvac["device_type"] = "sh_hvac"
                            attr_sh_hvac[element_name] = element_value

                    if type_of_id == "smoke":
                        if (
                            element_name in deviceSmokeKeywords
                            and element_validity == "upToDate"
                        ):
                            attr_smoke["device_id"] = device_id
                            attr_smoke["device_class"] = "smoke"
                            attr_smoke["endpoint_id"] = endpoint_id
                            attr_smoke["id"] = str(device_id) + "_" + str(endpoint_id)
                            attr_smoke["name"] = print_id
                            attr_smoke["device_type"] = "sensor"
                            attr_smoke["element_name"] = element_name
                            attr_smoke[element_name] = element_value

                    if type_of_id == "unknown":
                        if (
                            element_name in deviceMotionKeywords
                            and element_validity == "upToDate"
                        ):
                            attr_ukn["device_id"] = device_id
                            attr_ukn["endpoint_id"] = endpoint_id
                            attr_ukn["id"] = str(device_id) + "_" + str(endpoint_id)
                            attr_ukn["name"] = print_id
                            attr_ukn["device_type"] = "sensor"
                            attr_ukn["element_name"] = element_name
                            attr_ukn[element_name] = element_value
                        elif (
                            element_name in deviceDoorKeywords
                            and element_validity == "upToDate"
                        ):
                            attr_ukn["device_id"] = device_id
                            attr_ukn["endpoint_id"] = endpoint_id
                            attr_ukn["id"] = str(device_id) + "_" + str(endpoint_id)
                            attr_ukn["name"] = print_id
                            attr_ukn["device_type"] = "sensor"
                            attr_ukn["element_name"] = element_name
                            attr_ukn[element_name] = element_value

                    if type_of_id == "others":
                        if (
                            element_name in deviceLightKeywords
                            and element_validity == "upToDate"
                        ):
                            attr_light["device_id"] = device_id
                            attr_light["endpoint_id"] = endpoint_id
                            attr_light["id"] = str(device_id) + "_" + str(endpoint_id)
                            attr_light["light_name"] = print_id
                            attr_light["name"] = print_id
                            # later replace with commented condition below
                            attr_light["device_type"] = "light"
                            attr_light[element_name] = element_value

                            # if condition_to_define_light_or_switch:
                            #    attr_light['device_type'] = 'light'
                            # else:
                            #    attr_light['device_type'] = 'switch'

            except Exception as e:
                logger.error("msg_data error in parsing !")
                logger.error(e)
                logger.exception(e)

            if "device_type" in attr_cover and attr_cover["device_type"] == "cover":
                new_cover = Cover(tydom_attributes=attr_cover, mqtt=self.mqtt_client)
                await new_cover.update()
            elif (
                "device_type" in attr_garage and attr_garage["device_type"] == "garage"
            ):
                new_garage = Garage(tydom_attributes=attr_garage, mqtt=self.mqtt_client)
                await new_garage.update()
            elif "device_type" in attr_door and attr_door["device_type"] == "sensor":
                new_door = Sensor(
                    elem_name=attr_door["element_name"],
                    tydom_attributes_payload=attr_door,
                    mqtt=self.mqtt_client,
                )
                await new_door.update()
            elif (
                "device_type" in attr_window and attr_window["device_type"] == "sensor"
            ):
                new_window = Sensor(
                    elem_name=attr_window["element_name"],
                    tydom_attributes_payload=attr_window,
                    mqtt=self.mqtt_client,
                )
                await new_window.update()
            elif (
                "device_type" in attr_sensor and attr_sensor["device_type"] == "sensor"
            ):
                new_sensor = Sensor(
                    elem_name=attr_sensor["element_name"],
                    tydom_attributes_payload=attr_sensor,
                    mqtt=self.mqtt_client,
                )
                await new_sensor.update()
            elif "device_type" in attr_light and attr_light["device_type"] == "light":
                new_light = Light(tydom_attributes=attr_light, mqtt=self.mqtt_client)
                await new_light.update()
            elif (
                "device_type" in attr_boiler and attr_boiler["device_type"] == "climate"
            ):
                new_sh_hvac = Boiler(
                    tydom_attributes=attr_boiler,
                    tydom_client=self.tydom_client,
                    mqtt=self.mqtt_client,
                )
                await new_sh_hvac.update()
            elif "device_type" in attr_gate and attr_gate["device_type"] == "switch":
                new_gate = Switch(tydom_attributes=attr_gate, mqtt=self.mqtt_client)
                await new_gate.update()
            elif "device_type" in attr_smoke and attr_smoke["device_type"] == "sensor":
                new_smoke = Sensor(
                    elem_name=attr_smoke["element_name"],
                    tydom_attributes_payload=attr_smoke,
                    mqtt=self.mqtt_client,
                )
                await new_smoke.update()
            elif "device_type" in attr_ukn and attr_ukn["device_type"] == "sensor":
                new_ukn = Sensor(
                    elem_name=attr_ukn["element_name"],
                    tydom_attributes_payload=attr_ukn,
                    mqtt=self.mqtt_client,
                )
                await new_ukn.update()
            elif (
                "device_type" in attr_sh_hvac
                and attr_sh_hvac["device_type"] == "sh_hvac"
            ):
                new_sh_hvac = ShHvac(
                    tydom_attributes=attr_sh_hvac,
                    tydom_client=self.tydom_client,
                    mqtt=self.mqtt_client,
                )
                await new_sh_hvac.update()
            elif (
                "device_type" in attr_automatic_door
                and attr_automatic_door["device_type"] == "AutomaticDoor"
            ):
                new_automatic_door = AutomaticDoor(
                    tydom_attributes=attr_automatic_door,
                    tydom_client=self.tydom_client,
                    mqtt=self.mqtt_client,
                )
                await new_automatic_door.update()

            # Get last known state (for alarm) # NEW METHOD
            elif (
                "device_type" in attr_alarm
                and attr_alarm["device_type"] == "alarm_control_panel"
            ):
                state = None
                sos_state = False
                try:
                    if (
                        "alarmState" in attr_alarm and attr_alarm["alarmState"] == "ON"
                    ) or (
                        "alarmState" in attr_alarm and attr_alarm["alarmState"]
                    ) == "QUIET":
                        state = "triggered"

                    elif (
                        "alarmState" in attr_alarm
                        and attr_alarm["alarmState"] == "DELAYED"
                    ):
                        state = "pending"

                    if "alarmSOS" in attr_alarm and attr_alarm["alarmSOS"] == "true":
                        state = "triggered"
                        sos_state = True

                    elif "alarmMode" in attr_alarm and attr_alarm["alarmMode"] == "ON":
                        state = "armed_away"
                    elif (
                        "alarmMode" in attr_alarm and attr_alarm["alarmMode"] == "ZONE"
                    ):
                        state = "armed_home"
                    elif "alarmMode" in attr_alarm and attr_alarm["alarmMode"] == "OFF":
                        state = "disarmed"
                    elif (
                        "alarmMode" in attr_alarm
                        and attr_alarm["alarmMode"] == "MAINTENANCE"
                    ):
                        state = "disarmed"

                    if sos_state:
                        logger.warning("SOS !")

                    # alarm shall be update Whatever its state because sensor
                    # can be updated without any state
                    alarm = Alarm(
                        current_state=state,
                        alarm_pin=self.tydom_client.alarm_pin,
                        tydom_attributes=attr_alarm,
                        mqtt=self.mqtt_client,
                    )
                    if state is not None:
                        await alarm.update()
                    else:
                        await alarm.update_sensors()

                except Exception as e:
                    logger.error("Error in alarm parsing !")
                    logger.error(e)
                    pass
            else:
                pass

    async def parse_devices_cdata(self, parsed):
        for i in parsed:
            for endpoint in i["endpoints"]:
                if endpoint["error"] == 0 and len(endpoint["cdata"]) > 0:
                    try:
                        device_id = i["id"]
                        endpoint_id = endpoint["id"]
                        unique_id = str(endpoint_id) + "_" + str(device_id)
                        name_of_id = self.get_name_from_id(unique_id)
                        type_of_id = self.get_type_from_id(unique_id)
                        logger.info(
                            "Device configured (id=%s, endpoint=%s, name=%s, type=%s)",
                            device_id,
                            endpoint_id,
                            name_of_id,
                            type_of_id,
                        )

                        for elem in endpoint["cdata"]:
                            if type_of_id == "conso":
                                if elem["name"] == "energyIndex":
                                    device_class_of_id = "energy"
                                    state_class_of_id = "total_increasing"
                                    unit_of_measurement_of_id = "Wh"
                                    element_name = elem["parameters"]["dest"]
                                    element_index = "counter"

                                    attr_conso = {
                                        "device_id": device_id,
                                        "endpoint_id": endpoint_id,
                                        "id": unique_id,
                                        "name": name_of_id,
                                        "device_type": "sensor",
                                        "device_class": device_class_of_id,
                                        "state_class": state_class_of_id,
                                        "unit_of_measurement": unit_of_measurement_of_id,
                                        element_name: elem["values"][element_index],
                                    }

                                    new_conso = Sensor(
                                        elem_name=element_name,
                                        tydom_attributes_payload=attr_conso,
                                        mqtt=self.mqtt_client,
                                    )
                                    await new_conso.update()

                                elif elem["name"] == "energyInstant":
                                    device_class_of_id = "current"
                                    state_class_of_id = "measurement"
                                    unit_of_measurement_of_id = "A"
                                    element_name = elem["parameters"]["unit"]
                                    element_index = "measure"

                                    element_value = elem["values"][element_index]
                                    if (
                                        element_value is not None
                                        and type(element_value) is int
                                    ):
                                        element_value = element_value / 100

                                    attr_conso = {
                                        "device_id": device_id,
                                        "endpoint_id": endpoint_id,
                                        "id": unique_id,
                                        "name": name_of_id,
                                        "device_type": "sensor",
                                        "device_class": device_class_of_id,
                                        "state_class": state_class_of_id,
                                        "unit_of_measurement": unit_of_measurement_of_id,
                                        element_name: element_value,
                                    }

                                    new_conso = Sensor(
                                        elem_name=element_name,
                                        tydom_attributes_payload=attr_conso,
                                        mqtt=self.mqtt_client,
                                    )
                                    await new_conso.update()

                                elif elem["name"] == "energyDistrib":
                                    for elName in elem["values"]:
                                        if elName != "date":
                                            element_name = elName
                                            element_index = elName
                                            attr_conso = {
                                                "device_id": device_id,
                                                "endpoint_id": endpoint_id,
                                                "id": unique_id,
                                                "name": name_of_id,
                                                "device_type": "sensor",
                                                "device_class": "energy",
                                                "state_class": "total_increasing",
                                                "unit_of_measurement": "Wh",
                                                element_name: elem["values"][
                                                    element_index
                                                ],
                                            }

                                            new_conso = Sensor(
                                                elem_name=element_name,
                                                tydom_attributes_payload=attr_conso,
                                                mqtt=self.mqtt_client,
                                            )
                                            await new_conso.update()

                    except Exception as e:
                        logger.error("Error when parsing msg_cdata (%s)", e)

    # PUT response DIRTY parsing
    def parse_put_response(self, bytes_str, start=6):
        # TODO : Find a cooler way to parse nicely the PUT HTTP response
        resp = bytes_str[len(self.cmd_prefix) :].decode("utf-8")
        fields = resp.split("\r\n")
        fields = fields[start:]  # ignore the PUT / HTTP/1.1
        end_parsing = False
        i = 0
        output = str()
        while not end_parsing:
            field = fields[i]
            if len(field) == 0 or field == "0":
                end_parsing = True
            else:
                output += field
                i = i + 2
        parsed = json.loads(output)
        return json.dumps(parsed)

    # FUNCTIONS

    @staticmethod
    def response_from_bytes(data):
        sock = BytesIOSocket(data)
        response = HTTPResponse(sock)
        response.begin()
        return response.read()

    @staticmethod
    def put_response_from_bytes(data):
        request = HTTPRequest(data)
        return request

    def get_type_from_id(self, id):
        device_type_detected = ""
        if id in device_type.keys():
            device_type_detected = device_type[id]
        else:
            logger.warning("Unknown device type (%s)", id)
        return device_type_detected

    # Get pretty name for a device id
    def get_name_from_id(self, id):
        name = ""
        if id in device_name.keys():
            name = device_name[id]
        else:
            logger.warning("Unknown device name (%s)", id)
        return name


class BytesIOSocket:
    def __init__(self, content):
        self.handle = BytesIO(content)

    def makefile(self, mode):
        return self.handle


class HTTPRequest(BaseHTTPRequestHandler):
    def __init__(self, request_text):
        self.raw_requestline = request_text
        self.error_code = self.error_message = None
        self.parse_request()

    def send_error(self, code, message):
        self.error_code = code
        self.error_message = message
